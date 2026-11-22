"""Authenticated REST client shared by CLI and MCP. No database or arbitrary URL access."""

import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import httpx

from .client_auth import SOURCES, AuthenticationRequired, CredentialStore, expiry_seconds, origin
from .operation_catalog import VERSION
from .operation_receipts import HEADER


class OperationsClient:
    def __init__(self, url="http://127.0.0.1:8877", *, username=None, password=None, token=None, transport=None,
                 reuse_session=False, require_auth=False, auth_store=None, source="script", remember=False):
        url = origin(url)
        if source not in SOURCES:
            raise ValueError("execution source must be human, ai or script")
        self.client = httpx.Client(base_url=url, transport=transport, timeout=30, follow_redirects=False)
        self.client.headers["X-ThreeMind-Execution-Source"] = source
        self.logged_in = False
        self.catalogue = None
        self.store = auth_store or CredentialStore(url)
        self.credential = None
        self._stored = False
        self._authentication_request = False
        self._ephemeral = False
        try:
            if token:
                self._set_credential({"access_token": token, "kind": "external", "source": source})
            else:
                cached = self.store.load() if reuse_session else None
                if cached and (not username or cached.get("username") == username):
                    self._set_credential(cached)
                    self._stored = True
                elif username and password:
                    self.login(username, password, remember=remember, source=source, persist=reuse_session)
                    self._ephemeral = not reuse_session
                elif require_auth or username:
                    raise AuthenticationRequired(
                        "No reusable API credentials. Run threemind auth login or configure "
                        "THREEMIND_API_TOKEN / THREEMIND_API_USERNAME and THREEMIND_API_PASSWORD; "
                        "chat authorization is not a login credential."
                    )
        except Exception:
            self.client.close()
            raise

    @classmethod
    def from_environment(cls, url=None, *, username=None, profile=None, directory=None, source=None,
                         interactive=False, transport=None):
        url = url or os.getenv("THREEMIND_API_URL", "http://127.0.0.1:8877")
        username = username if username is not None else os.getenv("THREEMIND_API_USERNAME")
        password = os.getenv("THREEMIND_API_PASSWORD")
        store = CredentialStore(url, directory=directory,
                                profile=profile or os.getenv("THREEMIND_AUTH_PROFILE", "default"))
        if interactive and username and not password and not store.load() and not os.getenv("THREEMIND_API_TOKEN"):
            import getpass
            import sys

            if not sys.stdin.isatty():
                raise AuthenticationRequired("Interactive login requires a terminal; use threemind auth login")
            password = getpass.getpass("Password: ")
        return cls(url, username=username, password=password, token=os.getenv("THREEMIND_API_TOKEN"),
                   transport=transport, reuse_session=True, require_auth=True, auth_store=store,
                   source=source or os.getenv("THREEMIND_EXECUTION_SOURCE", "script"))

    def _set_credential(self, value):
        self.credential = value
        self.client.headers["Authorization"] = "Bearer " + value["access_token"]
        self.logged_in = True

    @staticmethod
    def _credential_identity(value):
        # Account-session rotation changes tokens, never the acting account.
        # A new delegation is an explicit reconnect even for the same issuer.
        user, delegation = value.get("user") or {}, value.get("delegation") or {}
        return (value.get("kind"), value.get("username"), user.get("id"),
                delegation.get("user_id"), delegation.get("id"))

    def login(self, username, password, *, remember=False, source="human", persist=True):
        if not username or not password:
            raise AuthenticationRequired("Username and password are required for explicit login")
        result = self.request("POST", "/api/v2/auth/token",
                              body={"username": username, "password": password, "remember": remember, "source": source})
        credential = {"access_token": result["access_token"], "expires_at": result["expires_at"],
                      "kind": "session", "source": source, "username": username, "user": result.get("user")}
        if persist:
            try:
                self.store.save(credential)
            except (OSError, ValueError):
                self._set_credential(credential)
                self._authentication_request = True
                try:
                    self.request("POST", "/api/v2/logout", body={})
                except (OSError, ValueError, httpx.HTTPError):
                    pass
                finally:
                    self._authentication_request = False
                raise
        self._set_credential(credential)
        self._stored = persist
        return CredentialStore.metadata(credential)

    def refresh(self):
        if not self.credential or self.credential.get("kind") != "session":
            raise AuthenticationRequired("Only account sessions can renew; delegated credentials require a new grant")
        self._authentication_request = True
        try:
            if self._stored:
                with self.store.locked():
                    current = self.store.load()
                    if not current:
                        raise AuthenticationRequired("Saved session was removed; run threemind auth login")
                    if self._credential_identity(current) != self._credential_identity(self.credential):
                        raise AuthenticationRequired("Credential profile changed identity; reconnect explicitly")
                    self._set_credential(current)
                    return self._refresh_current(persist=True)
            return self._refresh_current(persist=False)
        finally:
            self._authentication_request = False

    def _refresh_current(self, *, persist):
        if self.credential.get("kind") != "session":
            raise AuthenticationRequired("Delegated credentials cannot renew themselves")
        result = self.request("POST", "/api/v2/auth/refresh", body={})
        value = self.credential | {"access_token": result["access_token"], "expires_at": result["expires_at"],
                                  "user": result.get("user")}
        if persist:
            self.store.save_locked(value)
        self._set_credential(value)
        return CredentialStore.metadata(value)

    def _prepare_authentication(self):
        if self._stored:
            value = self.store.load()
            if not value:
                raise AuthenticationRequired("Saved credentials were removed; run threemind auth login")
            if self._credential_identity(value) != self._credential_identity(self.credential):
                raise AuthenticationRequired("Credential profile changed identity; reconnect explicitly")
            self._set_credential(value)
        if self.credential:
            remaining = expiry_seconds(self.credential.get("expires_at"))
            if remaining is not None and remaining <= 0:
                raise AuthenticationRequired("API credentials expired; run threemind auth login or request a new delegation")
            if remaining is not None and remaining < 300 and self.credential.get("kind") == "session":
                self.refresh()

    def logout(self):
        delegated = self.credential and self.credential.get("kind") == "delegation"
        self._authentication_request = True
        try:
            if self.credential and self.credential.get("kind") == "external":
                # Environment tokens may represent either an account session or
                # a bounded delegation. Only the server can distinguish them.
                identity = self.request("GET", "/api/v2/me")
                delegated = identity.get("user", identity).get("auth_type") == "delegation"
            if self.logged_in and not delegated:
                self.request("POST", "/api/v2/logout", body={})
        finally:
            self._authentication_request = False
            if self._stored:
                self.store.clear()
            self.client.headers.pop("Authorization", None)
            self.credential, self._stored, self.logged_in = None, False, False
        return {"logged_out": True, "delegation_revocation_required": bool(delegated)}

    def close(self):
        if self.logged_in and self._ephemeral:
            try:
                self.logout()
            except (OSError, ValueError, httpx.HTTPError):
                pass
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def request(
        self, method, path, *, body=None, content=None, params=None, headers=None, output=None,
        maximum=8 * 1024 * 1024, expected_sha256=None
    ):
        if not path.startswith("/api/v2/") or ".." in path.split("/") or "?" in path or "#" in path:
            raise ValueError("Only canonical ThreeMind API paths are accepted")
        if body is not None and content is not None:
            raise ValueError("cannot combine JSON and binary content")
        if not self._authentication_request and path not in ("/api/v2/auth/token", "/api/v2/login"):
            self._prepare_authentication()
        payload = {"content": content} if content is not None else {"json": body}
        with self.client.stream(method, path, **payload, params=params, headers=headers) as response:
            if response.status_code >= 300:
                raw = bytearray()
                for piece in response.iter_bytes():
                    raw.extend(piece[: max(0, 8192 - len(raw))])
                    if len(raw) >= 8192:
                        break
                try:
                    detail = json.loads(raw).get("detail", "request rejected")
                except (ValueError, AttributeError):
                    detail = "request rejected"
                if response.status_code == 401:
                    raise AuthenticationRequired(f"HTTP 401: {detail}; run threemind auth login or request a valid delegation. "
                                                 "No operation was automatically retried; reconcile the original receipt.")
                raise ValueError(f"HTTP {response.status_code}: {detail}")
            if output is not None:
                path_out = Path(output)
                count = 0
                # Exclusive create: interrupted downloads remain identifiable and are never treated as complete.
                temporary = path_out.with_name(path_out.name + ".partial")
                if path_out.exists():
                    raise ValueError("output exists; evidence is never overwritten")
                import hashlib

                sha = hashlib.sha256()
                with temporary.open("xb") as stream:
                    for piece in response.iter_bytes(1024 * 1024):
                        import shutil

                        if shutil.disk_usage(path_out.parent).free < 15 * 1024**3:
                            raise ValueError("download reached the 15 GiB free-disk reserve")
                        count += len(piece)
                        if count > maximum:
                            raise ValueError("download exceeds configured byte budget")
                        sha.update(piece)
                        stream.write(piece)
                if expected_sha256 is not None and (count != maximum or sha.hexdigest() != expected_sha256):
                    raise ValueError("download differs from the published volume manifest; retained as .partial")
                # Hard-link gives exclusive publication even if another process creates the output meanwhile.
                import os

                os.link(temporary, path_out)
                temporary.unlink()
                return {"path": str(path_out.resolve()), "bytes": count, "sha256": sha.hexdigest()}
            raw = bytearray()
            for piece in response.iter_bytes():
                raw.extend(piece)
                if len(raw) > maximum:
                    raise ValueError("response exceeds budget; use pagination or an explicit file download")
            if not raw:
                return None
            try:
                return json.loads(raw)
            except ValueError as exc:
                raise ValueError("response is not JSON; use an explicit file download") from exc

    def catalog(self, refresh=False):
        if self.catalogue is None or refresh:
            self.catalogue = self.request("GET", "/api/v2/operations/catalog")
            if self.catalogue.get("schema") != VERSION:
                raise ValueError("unsupported operation catalog version")
        return self.catalogue

    def describe(self, identity):
        row = next((r for r in self.catalog()["operations"] if r["id"] == identity), None)
        if row is None:
            raise ValueError("unknown operation; inspect the service catalog")
        return row

    def prepare(self, identity, arguments, *, request_id=None):
        from jsonschema import Draft202012Validator, FormatChecker, ValidationError

        row = self.describe(identity)
        if not isinstance(arguments, dict) or set(arguments) - {"path", "query", "body"}:
            raise ValueError("arguments must contain only path, query and body")
        path_values, query = arguments.get("path", {}), arguments.get("query", {})
        if not isinstance(path_values, dict) or not isinstance(query, dict):
            raise TypeError("path and query must be objects")
        definitions = self.catalog()["components"]

        def reject_remote_refs(value):
            if isinstance(value, dict):
                if "$ref" in value and not str(value["$ref"]).startswith("#/components/"):
                    raise ValueError("only local API schema references are permitted")
                for item in value.values():
                    reject_remote_refs(item)
            elif isinstance(value, list):
                for item in value:
                    reject_remote_refs(item)

        reject_remote_refs(definitions)

        def validate(value, schema):
            reject_remote_refs(schema)
            try:
                Draft202012Validator(schema | {"components": definitions}, format_checker=FormatChecker()).validate(
                    value
                )
            except ValidationError as exc:
                raise ValueError(f"Invalid arguments at {list(exc.absolute_path)} ({exc.validator})") from None

        path = row["path"]
        for location, values in (("path", path_values), ("query", query)):
            fields = [p for p in row["parameters"] if p["in"] == location]
            if set(values) - {p["name"] for p in fields}:
                raise ValueError(f"unknown {location} parameters")
            for param in fields:
                if param["name"] not in values:
                    if param.get("required"):
                        raise ValueError(f"missing {location} parameter: {param['name']}")
                    continue
                validate(values[param["name"]], param["schema"])
                if location == "path":
                    path = path.replace("{" + param["name"] + "}", quote(str(values[param["name"]]), safe=""))
        body = arguments.get("body")
        if row["request_body"]:
            if "application/json" not in row["request_body"]:
                raise ValueError("this operation needs multipart/chunked transfer; use its dedicated upload command")
            validate(body, row["request_body"]["application/json"]["schema"])
        elif body is not None:
            raise ValueError("operation does not accept a JSON body")
        headers = {}
        if row["request_receipt"]:
            if request_id is None:
                raise ValueError("a stable request_id is required; reuse it after an uncertain response")
            headers[HEADER] = str(UUID(str(request_id)))
        return row, path, query, body, headers

    def preflight(self, identity, arguments, *, request_id=None):
        row, path, _, _, _ = self.prepare(identity, arguments, request_id=request_id)
        return {
            "valid": True,
            "operation": identity,
            "method": row["method"],
            "path": path,
            "coverage": "schema_only",
            "unchecked": [
                "current_project_role",
                "current_model_revision",
                "execution_lock",
                "live_worker_capability",
                "remaining_budget",
            ],
            "note": "The canonical service checks these conditions again at execution.",
        }

    def call(self, identity, arguments, *, request_id=None, output=None, maximum=8 * 1024 * 1024):
        row, path, query, body, headers = self.prepare(identity, arguments, request_id=request_id)
        return self.request(
            row["method"], path, params=query, body=body, headers=headers, output=output, maximum=maximum
        )
