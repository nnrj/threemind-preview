"""Read-only whole-course command and local food-gradient observations for Ocean /2."""

import argparse
import json
from pathlib import Path

import numpy as np
from pyarrow import compute as pc
from pyarrow import ipc, memory_map

from lab.tools.ocean_cli import write_json
from lab.tools.ocean_evolution_cli import SCHEMA
from lab.tools.ocean_view import recorded_segments


def summarize(folder):
    count = zero = saturated = directional = enclosure = neighbors = 0
    translation = rotation = cosine = 0.0
    files = 0
    for part in recorded_segments(folder):
        if not (part / "result.json").exists():
            raise ValueError("use a completed saved segment, not an open recording")
        for path in sorted((part / "inputs").glob("*.arrow")):
            with memory_map(str(path), "r") as source:
                reader = ipc.open_file(source)
                if reader.schema != SCHEMA:
                    raise ValueError("unsupported input record schema")
                files += 1
                for k in range(reader.num_record_batches):
                    rows = pc.list_flatten(reader.get_batch(k).column("inputs"))
                    n = len(rows)
                    if not n:
                        continue
                    commands, raw = rows.field("action"), rows.field("raw")
                    if not pc.all(pc.equal(pc.list_value_length(commands), 3)).as_py():
                        raise ValueError("three action components required")
                    if not pc.all(pc.equal(pc.list_value_length(raw), 18)).as_py():
                        raise ValueError("Ocean /2 measured sensor layout required")
                    action = pc.list_flatten(commands).to_numpy().reshape(n, 3)
                    measured = pc.list_flatten(raw).to_numpy().reshape(n, 18)
                    neighbors += int(np.any(measured[:, 13:17] > 0, axis=1).sum())
                    enclosure += int((measured[:, 17] > 0).sum())
                    count += n
                    translation += float(np.square(action[:, :2]).sum())
                    rotation += float(np.abs(action[:, 2]).sum())
                    zero += int((np.max(np.abs(action), axis=1) < 0.1).sum())
                    saturated += int((np.abs(action) >= 0.95).sum())
                    gradient = np.column_stack((measured[:, 1] - measured[:, 3], measured[:, 2] - measured[:, 4]))
                    velocity = measured[:, 5:7] * 0.03  # Measured body-local velocity relative to water.
                    denominator = np.linalg.norm(gradient, axis=1) * np.linalg.norm(velocity, axis=1)
                    valid = denominator > 1e-12  # Observer numerical exclusion, never a dynamics parameter.
                    directional += int(valid.sum())
                    cosine += float(((gradient[valid] * velocity[valid]).sum(axis=1) / denominator[valid]).sum())
    return {
        "schema": "threemind.ocean-input-summary/1",
        "record_files": files,
        "input_samples": count,
        "mean_squared_translation_command": translation / count if count else None,
        "mean_absolute_rotation_command": rotation / count if count else None,
        "all_commands_below_point1_fraction": zero / count if count else None,
        "axis_command_at_least_point95_fraction": saturated / (3 * count) if count else None,
        "nonzero_gradient_and_velocity_samples": directional,
        "mean_velocity_food_gradient_cosine": cosine / directional if directional else None,
        "nonzero_neighbor_measurement_samples": neighbors,
        "nonzero_enclosure_measurement_samples": enclosure,
        "encounter_scope": "recorded local reflectance/enclosure signals; not unique encounters or mating opportunities",
        "meaning": "whole-course descriptive exposure averages; commands are not fuel-limited forces; gradient alignment is not proof of a learned strategy",
        "statistical_unit": "world, not individual input samples",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = summarize(args.folder)
    if args.output:
        write_json(args.output, value)
    print(json.dumps(value, ensure_ascii=False, indent=2))
