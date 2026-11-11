from __future__ import annotations

import argparse
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path

import uvicorn

from .model import READABLE_MODEL_PACKAGE_SUFFIXES, ModelManifest, ModelPackage
from .runtime import ConsciousnessRuntime
from threemind_adapters import (
    AdapterRegistry,
    DEFAULT_AUDITORY_CONFIG,
    DEFAULT_VISUAL_CONFIG,
    TextSensorAdapter,
    default_telemetry_config,
)


_CLI_MODEL_ADAPTER_DEFAULTS = {
    "ambient-field": False,
    "host-telemetry-field": True,
    "process-telemetry-field": False,
    "runtime-telemetry-field": False,
    "auditory-sensor": False,
    "visual-sensor": False,
    "acoustic-output-organ": False,
    "activation-image-projector": False,
}


def _adapter_route(adapter_id: str) -> str:
    return {
        "ambient-field": "environment.frame -> input.bus",
        "host-telemetry-field": "host.telemetry -> sensory.frame -> input.bus",
        "process-telemetry-field": "process.telemetry -> sensory.frame -> input.bus",
        "runtime-telemetry-field": "runtime.telemetry -> sensory.frame -> input.bus",
        "auditory-sensor": "audio.pcm -> sensory.frame -> input.bus",
        "visual-sensor": "image.pixels|video.pixels -> sensory.frame -> input.bus",
        "acoustic-output-organ": "output.bus -> audio.control",
        "activation-image-projector": "output.bus -> image.pixels",
    }.get(adapter_id, "adapter -> bus")


def _resolve_model_adapter_declarations(runtime: ConsciousnessRuntime) -> None:
    """Make offline CLI package writes as explicit as API-host writes.

    The Core runtime has no dependency on physical telemetry.  This CLI is an
    application host, however, so it records the adapter defaults it used in
    the package rather than leaving behavior dependent on a later host.
    """
    bindings = {
        str(row.get("adapter_id")): row
        for row in runtime.manifest.adapter_bindings
        if isinstance(row, dict) and row.get("adapter_id")
    }
    for adapter_id, default_enabled in _CLI_MODEL_ADAPTER_DEFAULTS.items():
        binding = bindings.get(adapter_id)
        if binding is None:
            binding = {
                "adapter_id": adapter_id,
                "enabled": default_enabled,
                "route": _adapter_route(adapter_id),
            }
            runtime.manifest.adapter_bindings.append(binding)
            bindings[adapter_id] = binding
        binding["enabled"] = bool(binding.get("enabled", default_enabled))
        if adapter_id == "host-telemetry-field":
            resolved = default_telemetry_config("host")
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "process-telemetry-field":
            resolved = default_telemetry_config("process")
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "runtime-telemetry-field":
            resolved = default_telemetry_config("runtime")
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "auditory-sensor":
            resolved = dict(DEFAULT_AUDITORY_CONFIG)
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "visual-sensor":
            resolved = dict(DEFAULT_VISUAL_CONFIG)
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "acoustic-output-organ":
            resolved = {"maximum_voices": 12, "minimum_activation": .08, "output_interval_ms": 100}
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        elif adapter_id == "activation-image-projector":
            resolved = {"width": 48, "height": 32, "output_interval_ms": 150}
            if isinstance(binding.get("config"), dict):
                AdapterRegistry._deep_merge(resolved, binding["config"])
            binding["config"] = resolved
        else:
            binding.setdefault("config", {})
    runtime.manifest.parameters.setdefault("homeostasis_enabled", bool(runtime.config.homeostasis_enabled))


def _save_runtime_package(runtime: ConsciousnessRuntime, path: Path | str) -> str:
    _resolve_model_adapter_declarations(runtime)
    return runtime.save_package(str(path))


def main() -> None:
    parser = argparse.ArgumentParser(prog="threemind")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8877)
    serve.add_argument("--data-dir", type=Path, help="persistent data directory")
    create = sub.add_parser("create")
    create.add_argument("path", type=Path)
    create.add_argument("--name", default="Unnamed consciousness")
    create.add_argument("--spatial-dimensions", type=int, default=0)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("path", type=Path)
    stimulate = sub.add_parser("stimulate")
    stimulate.add_argument("path", type=Path)
    stimulate.add_argument("text")
    stimulate.add_argument("--source", default="cli")
    stimulate.add_argument("--intensity", type=float, default=1.0)
    stimulate.add_argument(
        "--frame-characters",
        type=int,
        default=24,
        help="characters per causally delivered text frame (default: 24; never truncates input)",
    )
    stimulate.add_argument(
        "--inter-frame-epochs",
        type=int,
        default=1,
        help="environmental epochs between consecutive text frames (default: 1)",
    )
    stimulate.add_argument(
        "--step",
        type=int,
        default=1,
        help="additional environmental epochs after the complete text stream is delivered (default: 1)",
    )
    clone = sub.add_parser("clone")
    clone.add_argument("path", type=Path)
    clone.add_argument("output", type=Path)
    clone.add_argument("--name")
    snapshot = sub.add_parser("snapshot", help="save a snapshot of the running consciousness")
    snapshot.add_argument("--label", help="optional human-readable snapshot name")
    snapshot.add_argument("--portrait", action="store_true", help="save a portrait (post-mortem/archive style) record")
    snapshot.add_argument("--base-url", default="http://127.0.0.1:8877")
    listing = sub.add_parser("list")
    listing.add_argument("directory", type=Path, nargs="?", default=Path("data"))
    providers = sub.add_parser("providers", help="inspect providers through a running Core")
    providers.add_argument("--base-url", default="http://127.0.0.1:8877")
    history = sub.add_parser("history", help="read history from a running Core")
    history.add_argument("kind", choices=("events", "stimuli", "interpretations"))
    history.add_argument("--base-url", default="http://127.0.0.1:8877")
    history.add_argument("--page", type=int, default=1)
    history.add_argument("--page-size", type=int, default=50)
    instances = sub.add_parser("instances", help="list running consciousness instances")
    instances.add_argument("--base-url", default="http://127.0.0.1:8877")
    instance_create = sub.add_parser("instance-create")
    instance_create.add_argument("--name", default="Unnamed consciousness"); instance_create.add_argument("--base-url", default="http://127.0.0.1:8877")
    instance_control = sub.add_parser("instance-control")
    instance_control.add_argument("id"); instance_control.add_argument("action", choices=("start","pause","resume","stop")); instance_control.add_argument("--base-url", default="http://127.0.0.1:8877")
    provider_save = sub.add_parser("provider-save")
    provider_save.add_argument("id"); provider_save.add_argument("base_url"); provider_save.add_argument("api_key"); provider_save.add_argument("--model", default=""); provider_save.add_argument("--name"); provider_save.add_argument("--base-api-url", default="http://127.0.0.1:8877")
    provider_delete = sub.add_parser("provider-delete"); provider_delete.add_argument("id"); provider_delete.add_argument("--base-url", default="http://127.0.0.1:8877")
    ai_settings = sub.add_parser("ai-environment"); ai_settings.add_argument("provider_id"); ai_settings.add_argument("--enable", action="store_true"); ai_settings.add_argument("--frequency", type=int, default=120); ai_settings.add_argument("--base-url", default="http://127.0.0.1:8877")
    interpreter_settings = sub.add_parser("interpreter"); interpreter_settings.add_argument("provider_id"); interpreter_settings.add_argument("--enable", action="store_true"); interpreter_settings.add_argument("--frequency", type=int, default=300); interpreter_settings.add_argument("--base-url", default="http://127.0.0.1:8877")
    args = parser.parse_args()
    if args.command == "serve":
        if args.data_dir:
            os.environ["THREEMIND_DATA"] = str(args.data_dir.resolve())
        uvicorn.run("threemind.api:app", host=args.host, port=args.port, reload=False)
    elif args.command == "create":
        manifest = ModelManifest(spatial_embedding=args.spatial_dimensions > 0, spatial_dimensions=args.spatial_dimensions)
        runtime = ConsciousnessRuntime(ModelPackage.empty(manifest, name=args.name))
        _save_runtime_package(runtime, args.path)
        print(json.dumps(runtime.metrics(), ensure_ascii=False, indent=2))
    elif args.command == "inspect":
        package = ModelPackage.load(args.path)
        print(json.dumps({"manifest": package.manifest.to_dict(), "consciousness": package.to_payload()}, ensure_ascii=False, indent=2))
    elif args.command == "stimulate":
        runtime = ConsciousnessRuntime(ModelPackage.load(args.path))
        adapter = TextSensorAdapter(runtime.sensory_seed, labeled=runtime.manifest.node_payload == "labeled")
        if args.frame_characters < 1:
            parser.error("--frame-characters must be positive")
        if args.inter_frame_epochs < 1:
            parser.error("--inter-frame-epochs must be positive")
        if args.step < 0:
            parser.error("--step cannot be negative")
        frames = adapter.encode_stream(
            args.text,
            source=args.source,
            intensity=args.intensity,
            frame_characters=args.frame_characters,
        )
        before_epoch = runtime.input_queue_status()["input_epoch"]
        receipt = runtime.enqueue_frames(
            frames,
            metadata={"text": args.text, "carrier": "text", "carrier_length": len(args.text)},
            adapter_id="text-sensor",
            inter_frame_epochs=args.inter_frame_epochs,
        )
        # The CLI is an offline, explicit operation: deliver every queued
        # frame causally before saving.  This preserves the full carrier and
        # its ordering while retaining the old command's "one settling tick"
        # default via --step.
        delivery_epochs = int(receipt["last_due_epoch"]) - int(before_epoch)
        total_epochs = delivery_epochs + int(args.step)
        if total_epochs:
            runtime.step(ticks=total_epochs)
        _save_runtime_package(runtime, args.path)
        print(json.dumps(runtime.metrics(), ensure_ascii=False, indent=2))
    elif args.command == "clone":
        package = ModelPackage.load(args.path).clone(name=args.name)
        runtime = ConsciousnessRuntime(package)
        _save_runtime_package(runtime, args.output)
        print(json.dumps(runtime.metrics(), ensure_ascii=False, indent=2))
    elif args.command == "snapshot":
        query = urllib.parse.urlencode({
            "portrait": "true" if args.portrait else "false",
            **({"label": args.label} if args.label else {}),
        })
        request = urllib.request.Request(
            f"{args.base_url.rstrip('/')}/api/snapshot?{query}",
            data=b"", headers={"content-type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            print(json.dumps(json.loads(response.read()), ensure_ascii=False, indent=2))
    elif args.command == "list":
        items = []
        candidates = args.directory.iterdir() if args.directory.exists() else ()
        for path in sorted(
            item
            for item in candidates
            if item.is_file() and item.suffix.casefold() in READABLE_MODEL_PACKAGE_SUFFIXES
        ):
            try:
                package = ModelPackage.load(path)
                items.append({"path": str(path), "name": package.consciousness_name, "id": package.consciousness_id, "kernel_id": package.manifest.kernel_id})
            except ValueError:
                items.append({"path": str(path), "invalid": True})
        print(json.dumps(items, ensure_ascii=False, indent=2))
    elif args.command in {"providers", "instances", "history"}:
        endpoint = "/api/ai/providers" if args.command == "providers" else "/api/consciousnesses" if args.command == "instances" else f"/api/{args.kind}?page={args.page}&page_size={args.page_size}"
        with urllib.request.urlopen(args.base_url.rstrip("/") + endpoint, timeout=10) as response:
            print(json.dumps(json.loads(response.read()), ensure_ascii=False, indent=2))
    elif args.command in {"instance-create", "instance-control", "provider-save", "provider-delete", "ai-environment", "interpreter"}:
        if args.command == "instance-create": method, endpoint, body = "POST", "/api/consciousnesses", {"name": args.name, "manifest": {}}
        elif args.command == "instance-control": method, endpoint, body = "POST", f"/api/consciousnesses/{args.id}/runtime/{args.action}", None
        elif args.command == "provider-save": method, endpoint, body = "POST", "/api/ai/providers", {"id": args.id, "name": args.name or args.id, "base_url": args.base_url, "model": args.model, "api_key": args.api_key, "kind": "openai-compatible"}
        elif args.command == "provider-delete": method, endpoint, body = "DELETE", f"/api/ai/providers/{args.id}", None
        elif args.command == "ai-environment": method, endpoint, body = "POST", "/api/ai/environment/settings", {"enabled": args.enable, "provider_id": args.provider_id, "frequency_ticks": args.frequency, "random_frequency": True, "intensity": .7, "irregularity": .65}
        else: method, endpoint, body = "POST", "/api/ai/interpreter/settings", {"enabled": args.enable, "provider_id": args.provider_id, "frequency_ticks": args.frequency, "language": "auto"}
        base = getattr(args, "base_api_url", None) or getattr(args, "base_url", "http://127.0.0.1:8877")
        request = urllib.request.Request(base.rstrip("/") + endpoint, data=json.dumps(body).encode() if body is not None else None, headers={"content-type":"application/json"}, method=method)
        with urllib.request.urlopen(request, timeout=10) as response: print(json.dumps(json.loads(response.read()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
