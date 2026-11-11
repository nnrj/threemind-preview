"""Read recorded resource transfers without advancing or altering an ocean."""

import argparse
import json
from pathlib import Path

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_view import recorded_segments


def summarize(folder):
    parts = recorded_segments(folder)
    initial = read_json(parts[0] / "initial/manifest.json")["context"]
    result = read_json(parts[-1] / "result.json")
    members = {m["id"]: m for m in result["members"]}
    maturity = initial["protocol"]["maturity_us"]
    relations = {
        key: {"steps": 0, "sent": 0.0, "received": 0.0, "to_immature_received": 0.0}
        for key in ("parent_to_child", "child_to_parent", "other")
    }
    pairs = set()
    for part in parts:
        for event in read_json(part / "events.json"):
            if event["kind"] != "resource_exchange":
                continue
            if not initial["time_us"] < event["time_us"] <= result["time_us"]:
                raise ValueError("transfer outside this observation interval")
            donor, receiver = event["donor"], event["receiver"]
            if donor == receiver or not 0 <= event["received"] <= event["sent"]:
                raise ValueError("invalid recorded transfer")
            if members[receiver]["parent"] == donor:
                relation = "parent_to_child"
            elif members[donor]["parent"] == receiver:
                relation = "child_to_parent"
            else:
                relation = "other"
            values = relations[relation]
            values["steps"] += 1
            values["sent"] += event["sent"]
            values["received"] += event["received"]
            if event["time_us"] - members[receiver]["birth_us"] < maturity:
                values["to_immature_received"] += event["received"]
            pairs.add(tuple(sorted((donor, receiver))))
    steps = sum(r["steps"] for r in relations.values())
    recorded_count = result["totals"]["sharing_contacts"] - initial["totals"]["sharing_contacts"]
    if steps != recorded_count:
        raise ValueError("event count differs from the recorded transfer ledger")
    return {
        "schema": "threemind.ocean-exchange-summary/1",
        "transfer_steps": steps,
        "distinct_pairs": len(pairs),
        "relationships": relations,
        "sent": sum(r["sent"] for r in relations.values()),
        "received": sum(r["received"] for r in relations.values()),
        "meaning": "genealogical descriptions of physical transfers; neither intention nor independent cooperative acts",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    answer = summarize(args.folder)
    if args.output:
        write_json(args.output, answer)
    print(json.dumps(answer, ensure_ascii=False, indent=2))
