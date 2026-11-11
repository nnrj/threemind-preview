"""Resolve append-only continuation segments without rewriting partial trials."""

import json


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def segments(folder):
    result = [folder.resolve()]
    while (result[-1] / "completion.json").exists():
        pointer = read_json(result[-1] / "completion.json")
        path = (result[-1] / pointer["segment"]).resolve()
        if not path.is_relative_to(folder.resolve()) or path in result:
            raise ValueError("invalid continuation path")
        result.append(path)
    return result


def complete(folder):
    return segments(folder)[-1]
