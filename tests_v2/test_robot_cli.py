import json

import pytest

from threemind_runtime.robot_cli import main


def test_standalone_robot_cli_keeps_complete_world_and_brain(tmp_path, capsys):
    task, store = tmp_path / "arm.json", tmp_path / "arm.sqlite"
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    main(["template", "custom-arm-reach", "--output", str(task)])
    main(["run", "--task", str(task), "--store", str(store), "--until-us", "87000", "--evidence", str(first)])
    assert json.loads(capsys.readouterr().out)["revision"] == 1
    main(["run", "--store", str(store), "--resume", "--until-us", "170000", "--evidence", str(second)])
    resumed = json.loads(capsys.readouterr().out)
    main(["run", "--task", str(task), "--until-us", "170000"])
    direct = json.loads(capsys.readouterr().out)
    assert resumed["state_hash"] == direct["state_hash"]
    for key, value in direct["metrics"].items():
        # Native aggregate iteration can round at different final bits after
        # restore; the complete dynamics hash above must still be bit-exact.
        assert resumed["metrics"][key] == (
            pytest.approx(value, rel=1e-14, abs=1e-14) if type(value) is float else value
        )
    assert all(json.loads(row)["kind"] == "robot_sample" for row in second.read_text(encoding="utf-8").splitlines()[1:])
    assert len(first.read_text(encoding="utf-8").splitlines()) == 10
    with pytest.raises(SystemExit):
        main(["run", "--store", str(store), "--resume", "--until-us", "180000", "--seed", "19"])
    with pytest.raises(FileExistsError):
        main(["template", "custom-arm-reach", "--output", str(task)])
