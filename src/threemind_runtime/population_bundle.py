"""Explicit, complete population interchange; never extracts archive paths."""

import json
import re
import shutil
import zipfile
from tempfile import SpooledTemporaryFile

from .codec import MAX_ARTIFACT_BYTES, ArtifactCodec, _json
from .cold_state import StateReference
from .ecology_job import parse_job
from .world_schema import digest

BUNDLE_SCHEMA = "threemind.population-bundle/1"
MAX_BUNDLE_BYTES = 2 * 1024**3
MAX_METADATA_BYTES = 64 * 1024**2


def export_bundle(path, protocol, checkpoint):
    protocol = parse_job(protocol.model_dump(mode="json") if hasattr(protocol, "model_dump") else protocol)
    metadata, images = checkpoint
    if metadata.get("checkpoint_hash") != digest({k: v for k, v in metadata.items() if k != "checkpoint_hash"}):
        raise ValueError("population checkpoint metadata checksum mismatch")
    if set(images) != set(metadata["members"]):
        raise ValueError("cannot export a partial population")
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "protocol_hash": protocol.digest,
        "checkpoint_hash": metadata["checkpoint_hash"],
        "models": {},
    }
    with SpooledTemporaryFile(max_size=8 * 1024**2, mode="w+b") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            size = 0

            def write(name, data):
                nonlocal size
                size += len(data)
                if size > MAX_BUNDLE_BYTES:
                    raise ValueError("population bundle exceeds the 2 GiB expanded-file budget")
                archive.writestr(name, data)

            write("protocol.json", protocol.model_dump_json().encode())
            raw_metadata = json.dumps(metadata, allow_nan=False).encode()
            if len(raw_metadata) > MAX_METADATA_BYTES:
                raise ValueError("population metadata exceeds 64 MiB")
            write("population-state.json", raw_metadata)
            for identity, image in images.items():
                if not re.fullmatch("n[0-9]+", identity) or image.digest != metadata["members"][identity]["state_hash"]:
                    raise ValueError("invalid population member or state checksum")
                name = f"models/{identity}.tmind"
                model = ArtifactCodec.encode(image, "tmind", profile=protocol.profile)
                if len(model) > MAX_ARTIFACT_BYTES:
                    raise ValueError("individual artifact exceeds its 512 MiB import budget")
                write(name, model)
                manifest["models"][identity] = {"file": name, "state_hash": image.digest}
            write("manifest.json", json.dumps(manifest, allow_nan=False).encode())
        output.seek(0)
        # Build successfully before creating the target; never replace a model,
        # store, input protocol or an existing user export.
        with open(path, "xb") as destination:
            shutil.copyfileobj(output, destination, length=1048576)


class PopulationBundle:
    def __init__(self, path):
        self.archive = zipfile.ZipFile(path)
        try:
            infos = self.archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) > 100259 or len(set(names)) != len(names) or any(info.flag_bits & 1 for info in infos):
                raise ValueError("duplicate, encrypted or excessive population bundle members")
            if sum(info.file_size for info in infos) > MAX_BUNDLE_BYTES:
                raise ValueError("population bundle exceeds 2 GiB")
            self.manifest = _json(self.read("manifest.json", 32 * 1024**2))
            if (
                set(self.manifest) != {"schema", "protocol_hash", "checkpoint_hash", "models"}
                or self.manifest["schema"] != BUNDLE_SCHEMA
            ):
                raise ValueError(
                    "this file is not a portable population bundle; a brain or Lab evidence package cannot be resumed as a whole population"
                )
            self.protocol = parse_job(self.read("protocol.json", 8 * 1024**2))
            self.metadata = _json(self.read("population-state.json", MAX_METADATA_BYTES))
            if (
                self.protocol.digest != self.manifest["protocol_hash"]
                or self.metadata.get("checkpoint_hash") != self.manifest["checkpoint_hash"]
                or digest({k: v for k, v in self.metadata.items() if k != "checkpoint_hash"})
                != self.manifest["checkpoint_hash"]
            ):
                raise ValueError("population bundle protocol or checkpoint checksum mismatch")
            if set(self.manifest["models"]) != set(self.metadata["members"]):
                raise ValueError("population bundle has missing or unexpected brains")
            expected = {"manifest.json", "protocol.json", "population-state.json"}
            self.images = {}
            for identity, member in self.manifest["models"].items():
                name = f"models/{identity}.tmind"
                if (
                    not re.fullmatch("n[0-9]+", identity)
                    or set(member) != {"file", "state_hash"}
                    or member["file"] != name
                    or member["state_hash"] != self.metadata["members"][identity]["state_hash"]
                ):
                    raise ValueError("invalid population model identity")
                expected.add(name)
                self.images[identity] = StateReference(member["state_hash"], lambda name=name: self.model(name))
            if set(names) != expected:
                raise ValueError("population bundle contains missing or undeclared files")
        except BaseException:
            self.archive.close()
            raise

    def read(self, name, maximum):
        if self.archive.getinfo(name).file_size > maximum:
            raise ValueError("population bundle member exceeds its read budget")
        return self.archive.read(name)

    def model(self, name):
        image, profile = ArtifactCodec.decode(self.read(name, MAX_ARTIFACT_BYTES), with_profile=True)
        if profile != self.protocol.profile:
            raise ValueError("individual sensory profile differs from the frozen population protocol")
        return image

    @property
    def checkpoint(self):
        return self.metadata, self.images

    def close(self):
        self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
