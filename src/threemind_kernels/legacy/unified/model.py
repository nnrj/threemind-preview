from __future__ import annotations

import json
import copy
import os
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


MODEL_PACKAGE_SUFFIX = ".tmind"
# Read-only compatibility for packages created before the product rename.
# New packages are always written with MODEL_PACKAGE_SUFFIX.
LEGACY_MODEL_PACKAGE_SUFFIXES = (".bbx",)
READABLE_MODEL_PACKAGE_SUFFIXES = frozenset((MODEL_PACKAGE_SUFFIX, *LEGACY_MODEL_PACKAGE_SUFFIXES))


def is_model_package_path(path: Path | str) -> bool:
    return Path(path).suffix.casefold() in READABLE_MODEL_PACKAGE_SUFFIXES


@dataclass(slots=True)
class ModelManifest:
    """Declarative description of a runnable model package.

    ``package_schema_version`` describes the package schema. ``kernel_id`` is only an
    identity/capability label; the runtime never executes code from a package.
    """

    # This names a package/data schema, never a consciousness-kernel version.
    # A semantic value makes that distinction visible in every API consumer.
    package_schema_version: str = "3.0.0"
    kernel_id: str = "unified-associative"
    name: str = "Unified Associative Model"
    node_payload: str = "anonymous"
    weighted_edges: bool = True
    spatial_embedding: bool = False
    spatial_dimensions: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    # Desired adapter topology for this model.  It declares intent only: the
    # host registry remains the runtime authority for installed/attached
    # devices and can report a missing binding without blocking Core.
    adapter_bindings: list[dict[str, Any]] = field(default_factory=lambda: [
        {"adapter_id": "ambient-field", "enabled": False, "route": "environment.frame -> input.bus"},
        {"adapter_id": "body-background", "enabled": False, "upstream": "ambient-field", "route": "environment.frame -> sensory.frame -> input.bus"},
        {"adapter_id": "host-telemetry-field", "enabled": True, "route": "host.telemetry -> sensory.frame -> input.bus"},
        {"adapter_id": "process-telemetry-field", "enabled": False, "route": "process.telemetry -> sensory.frame -> input.bus"},
        {"adapter_id": "runtime-telemetry-field", "enabled": False, "route": "runtime.telemetry -> sensory.frame -> input.bus"},
        {"adapter_id": "energy-budget", "enabled": False, "route": "external.energy -> resource.input"},
    ])

    def validate(self) -> None:
        if self.package_schema_version != "3.0.0":
            raise ValueError(f"unsupported model package schema: {self.package_schema_version}")
        if self.node_payload not in {"anonymous", "labeled"}:
            raise ValueError("node_payload must be anonymous or labeled")
        if self.spatial_embedding and not 1 <= self.spatial_dimensions <= 64:
            raise ValueError("spatial_dimensions must be between 1 and 64")
        if not self.spatial_embedding and self.spatial_dimensions != 0:
            raise ValueError("spatial_dimensions must be zero when spatial_embedding is disabled")
        encoding = self.parameters.get("sensory_encoding")
        if encoding is not None and encoding not in {"anonymous-distributed", "labeled-observation", "literal-character", "legacy-labeled"}:
            raise ValueError("unsupported sensory_encoding")
        if not isinstance(self.adapter_bindings, list):
            raise ValueError("adapter_bindings must be a list")
        for binding in self.adapter_bindings:
            if not isinstance(binding, dict) or not isinstance(binding.get("adapter_id"), str):
                raise ValueError("each adapter binding must declare adapter_id")
            if "enabled" in binding and not isinstance(binding["enabled"], bool):
                raise ValueError("adapter binding enabled must be boolean")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ModelManifest":
        manifest = cls(
            package_schema_version=str(value.get("package_schema_version", "3.0.0")),
            kernel_id=str(value.get("kernel_id", "unified-associative")),
            name=str(value.get("name", "Unified Associative Model")),
            node_payload=str(value.get("node_payload", "anonymous")),
            weighted_edges=bool(value.get("weighted_edges", True)),
            spatial_embedding=bool(value.get("spatial_embedding", False)),
            spatial_dimensions=int(value.get("spatial_dimensions", 0)),
            parameters=dict(value.get("parameters", {})),
            adapter_bindings=list(value["adapter_bindings"]) if "adapter_bindings" in value else cls().adapter_bindings,
        )
        manifest.validate()
        return manifest


@dataclass(slots=True)
class ModelPackage:
    manifest: ModelManifest
    consciousness_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consciousness_name: str = "Unnamed consciousness"
    state: dict[str, Any] = field(default_factory=dict)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    portraits: list[dict[str, Any]] = field(default_factory=list)
    logs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # Describes the *file artifact* being written, not a property of the
    # consciousness dynamics.  It lets catalogues distinguish a deliberate
    # model-package save from a manual or automatic snapshot without guessing
    # from a filename.
    archive: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "consciousness_id": self.consciousness_id,
            "consciousness_name": self.consciousness_name,
            "state": self.state,
            "snapshots": self.snapshots,
            "portraits": self.portraits,
            "logs": self.logs,
            "archive": self.archive,
        }

    def catalog_metadata(self) -> dict[str, Any]:
        """Return the small, query-oriented header for a package artifact.

        The runtime state remains in ``state/consciousness.json``.  This
        header is deliberately redundant: catalogue and management views must
        never need to deserialize an entire consciousness just to show its
        name, tick, or archive provenance.
        """
        state = self.state if isinstance(self.state, dict) else {}
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])
        return {
            "schema": "threemind-package-metadata/1",
            "consciousness_id": self.consciousness_id,
            "consciousness_name": self.consciousness_name,
            "manifest": self.manifest.to_dict(),
            "archive": dict(self.archive),
            "state": {
                "tick": int(state.get("tick", 0)),
                "life_state": str(state.get("life_state", "active")),
                "parent_id": state.get("parent_id"),
                "node_count": len(nodes) if isinstance(nodes, list) else 0,
                "edge_count": len(edges) if isinstance(edges, list) else 0,
            },
            "snapshot_count": len(self.snapshots),
            "portrait_count": len(self.portraits),
        }

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.manifest.validate()
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(self.manifest.to_dict(), ensure_ascii=False, indent=2))
                archive.writestr("metadata.json", json.dumps(self.catalog_metadata(), ensure_ascii=False, indent=2))
                archive.writestr("state/consciousness.json", json.dumps(self.to_payload(), ensure_ascii=False, indent=2))
                archive.writestr("snapshots/index.json", json.dumps(self.snapshots, ensure_ascii=False, indent=2))
                archive.writestr("portraits/index.json", json.dumps(self.portraits, ensure_ascii=False, indent=2))
                for name, entries in self.logs.items():
                    safe_name = name.replace("/", "_").replace("\\", "_")
                    archive.writestr(f"logs/{safe_name}.jsonl", "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries))
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    @classmethod
    def read_catalog_metadata(cls, path: Path | str) -> dict[str, Any]:
        """Read the compact header without hydrating the graph when possible.

        Packages written before the header existed are intentionally supported
        by a one-time legacy fallback.  Callers should persist that result in
        an index, rather than repeatedly taking this fallback on hot paths.
        """
        try:
            with zipfile.ZipFile(path) as archive:
                if "metadata.json" in archive.namelist():
                    metadata = json.loads(archive.read("metadata.json"))
                    if isinstance(metadata, dict):
                        return metadata
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            raise ValueError(f"invalid model package: {error}") from error
        return cls.load(path).catalog_metadata()

    @classmethod
    def load(cls, path: Path | str) -> "ModelPackage":
        try:
            with zipfile.ZipFile(path) as archive:
                try:
                    names = set(archive.namelist())
                    required = {"manifest.json", "state/consciousness.json"}
                    missing = required - names
                    if missing:
                        raise ValueError(f"invalid model package; missing {sorted(missing)[0]}")
                    manifest_data = json.loads(archive.read("manifest.json"))
                    state_data = json.loads(archive.read("state/consciousness.json"))
                except KeyError as error:
                    raise ValueError(f"invalid model package; missing {error.args[0]}") from error
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            raise ValueError(f"invalid model package: {error}") from error
        if not isinstance(manifest_data, dict) or not isinstance(state_data, dict):
            raise ValueError("invalid model package: manifest and state must be objects")
        manifest = ModelManifest.from_dict(manifest_data)
        return cls(
            manifest=manifest,
            consciousness_id=str(state_data.get("consciousness_id") or uuid.uuid4()),
            consciousness_name=str(state_data.get("consciousness_name") or "Unnamed consciousness"),
            state=dict(state_data.get("state", {})),
            snapshots=list(state_data.get("snapshots", [])),
            portraits=list(state_data.get("portraits", [])),
            logs=dict(state_data.get("logs", {})),
            archive=dict(state_data.get("archive", {})),
        )

    @classmethod
    def empty(cls, manifest: ModelManifest | None = None, *, name: str | None = None) -> "ModelPackage":
        return cls(manifest or ModelManifest(), consciousness_name=name or "Unnamed consciousness")

    def clone(self, *, name: str | None = None) -> "ModelPackage":
        cloned = copy.deepcopy(self)
        cloned.consciousness_id = str(uuid.uuid4())
        cloned.consciousness_name = name or f"{self.consciousness_name} clone"
        cloned.snapshots = []
        cloned.portraits = []
        cloned.archive = {}
        return cloned
