"""Explicit account login and protected non-interactive experiment credentials."""

import argparse
import getpass
import json
import os
import sys
from uuid import UUID

import httpx

from .client_auth import CredentialStore, client_from_arguments, connection_arguments
from .operations_client import OperationsClient


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("login", "status", "logout", "refresh", "delegations", "delegate", "revoke"))
    connection_arguments(parser)
    parser.add_argument("--remember", action="store_true", help="Request a longer-lived account session")
    parser.add_argument("--json", help="Bounded delegation definition: name/source/actions/resources/expires_at")
    parser.add_argument("--delegate-profile", help="Save the new delegated credential in a separate protected profile")
    parser.add_argument("--id", type=UUID, help="Delegation identity to revoke")
    args = parser.parse_args(argv)
    store = CredentialStore(args.url, directory=args.auth_dir, profile=args.auth_profile)
    try:
        if args.action == "login":
            if not args.username:
                raise ValueError("login requires --username or THREEMIND_API_USERNAME")
            password = os.getenv("THREEMIND_API_PASSWORD")
            if not password:
                if not args.interactive or not sys.stdin.isatty():
                    raise ValueError("Configure THREEMIND_API_PASSWORD in the host environment or explicitly use --interactive")
                password = getpass.getpass("Password: ")
            with OperationsClient(args.url, auth_store=store, source=args.execution_source) as client:
                result = client.login(args.username, password, remember=args.remember, source=args.execution_source)
        else:
            with client_from_arguments(args) as client:
                if args.action == "status":
                    result = {"authenticated": True, "origin": store.origin, "profile": store.profile,
                              "credential": CredentialStore.metadata(client.credential),
                              "identity": client.request("GET", "/api/v2/me")}
                elif args.action == "logout":
                    result = client.logout()
                elif args.action == "refresh":
                    result = client.refresh()
                elif args.action == "delegations":
                    result = client.request("GET", "/api/v2/account/delegations")
                elif args.action == "revoke":
                    if not args.id:
                        raise ValueError("revoke requires --id")
                    result = client.request("DELETE", f"/api/v2/account/delegations/{args.id}")
                else:
                    if not args.json or not args.delegate_profile or args.delegate_profile == args.auth_profile:
                        raise ValueError("delegate requires --json and a separate --delegate-profile")
                    from .data_cli import read_object

                    target = CredentialStore(args.url, directory=args.auth_dir, profile=args.delegate_profile)
                    with target.locked():
                        if target.path.exists():
                            raise ValueError("delegation profile exists; explicitly logout that profile before replacing it")
                        response = client.request("POST", "/api/v2/account/delegations", body=read_object(args.json))
                        metadata = response["delegation"]
                        value = {"access_token": response["access_token"], "kind": "delegation",
                                 "delegation": metadata, "expires_at": metadata["expires_at"],
                                 "source": metadata["source"], "username": client.credential.get("username"),
                                 "user": client.credential.get("user")}
                        try:
                            target.save_locked(value)
                        except (ValueError, OSError):
                            # Never leave an issued but unrecorded credential usable if local publication fails.
                            client.request("DELETE", f"/api/v2/account/delegations/{metadata['id']}")
                            raise
                    result = {"delegation": metadata, "credential_profile": target.profile,
                              "origin": target.origin, "credential_saved": True}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, default=str, indent=2))
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
