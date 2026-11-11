"""One-worker execution of the frozen formal grid, with per-route output evaluation."""

import json

import torch
from experiment import WORK, formal, read_json, study
from language_analysis import evaluate


def main():
    torch.set_num_threads(2)
    routes = read_json(WORK / "selection.json")["routes"]
    for seed in (11, 37, 53):
        for route in reversed(routes):
            s = study()
            try:
                s.allow_extension()
                formal(s, route, seed)
            finally:
                s.db.close()
            evaluate(route, seed)
            print(json.dumps({"completed_formal_cell": [route, seed]}), flush=True)


if __name__ == "__main__":
    main()
