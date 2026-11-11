"""Synthetic offscreen renderer probe, isolated from the worker and Lab."""

import json

from .capabilities import check, world_probe


def main():
    result = check("世界离屏 RGB 感官", lambda: world_probe(True))
    print(json.dumps({"schema": "threemind.render-probe/1", "result": result}, ensure_ascii=True))


if __name__ == "__main__":
    main()
