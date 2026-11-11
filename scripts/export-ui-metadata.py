"""Export source-owned presentation metadata for the UI translation audit.

No database, model files, secrets or document bodies are read.
"""

import json

from threemind_lab.configuration import catalogue
from threemind_lab.documents import CATEGORIES
from threemind_lab.evolution_protocol import SELECTION_METRICS
from threemind_lab.protocols import RunSpec
from threemind_lab.research_commands import catalog as command_catalogue
from threemind_runtime.registry import default_adapter_registry


def metadata():
    parameters = catalogue()
    adapters = default_adapter_registry().list(RunSpec().model_dump())
    commands = command_catalogue()["commands"]
    texts = []
    for field in parameters["fields"]:
        texts.extend(field.get(key) or "" for key in ("label", "hint", "unit", "null_label"))
        texts.extend(label for _, label in (field.get("choices") or []))
    texts.extend(group["label"] for group in parameters["groups"])
    for adapter in adapters:
        texts.extend(adapter[key] for key in ("name", "description"))
    for command in commands:
        texts.extend(command[key] for key in ("label", "hint"))
    texts.extend(title for _, title in CATEGORIES)
    for values in SELECTION_METRICS.values():
        texts.extend(values)
    return {
        "parameters": len(parameters["fields"]),
        "adapters": len(adapters),
        "commands": len(commands),
        "texts": sorted(set(texts)),
    }


if __name__ == "__main__":
    print(json.dumps(metadata(), ensure_ascii=False))
