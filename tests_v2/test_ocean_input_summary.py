import pytest

from lab.tools.ocean_evolution_cli import RecordWriter
from lab.tools.ocean_input_summary import summarize


def test_whole_course_summary_separates_commands_from_measured_gradient_alignment(tmp_path):
    writer = RecordWriter(tmp_path / "inputs")
    cases = [
        ([1, 0, 0], [1, 0, 0, 0], [1, 0]),
        ([0, -1, 0], [0, 1, 0, 0], [0, -1]),
        ([0, 0, 0], [0, 0, 0, 0], [0, 0]),
        ([1, 1, 1], [1, 1, 0, 0], [1, 1]),
    ]
    for k, (action, food, velocity) in enumerate(cases):
        raw = [1, *food, *velocity, *([0] * 11)]
        raw[13] = 0.2 if k < 3 else 0.0
        raw[17] = 0.1 if k == 1 else 0.0
        writer.record(
            {
                "time_us": (k + 1) * 20000,
                "inputs": [
                    {
                        "individual": 0,
                        "stimulus": {"time_us": str((k + 1) * 20000), "channels": [[1, 1.0]], "intensity": 1.0},
                        "raw": raw,
                        "action": action,
                        "food": 0.0,
                    }
                ],
                "events": [],
            }
        )
    writer.flush()
    with pytest.raises(ValueError, match="completed saved segment"):
        summarize(tmp_path)
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")
    r = summarize(tmp_path)
    assert r["input_samples"] == 4
    assert r["mean_squared_translation_command"] == 1.0
    assert r["mean_absolute_rotation_command"] == 0.25
    assert r["all_commands_below_point1_fraction"] == 0.25
    assert r["axis_command_at_least_point95_fraction"] == pytest.approx(5 / 12)
    assert r["nonzero_gradient_and_velocity_samples"] == 3
    assert r["mean_velocity_food_gradient_cosine"] == pytest.approx(1 / 3)
    assert r["nonzero_neighbor_measurement_samples"] == 3
    assert r["nonzero_enclosure_measurement_samples"] == 1
