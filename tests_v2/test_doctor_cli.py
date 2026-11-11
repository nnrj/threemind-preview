import json
import sys
from types import SimpleNamespace

import pytest

from threemind_lab import cli, database
from threemind_runtime import host


@pytest.mark.parametrize("failure", ["schema", "construct", "metrics", None])
def test_doctor_checks_schema_and_closes_pool_on_each_exit(monkeypatch, capsys, failure):
    import threemind_runtime

    events = []
    error = ValueError("unknown continuous kernel identity")

    class ProbeDatabase:
        def __init__(self, url):
            assert url == "postgresql://localhost/isolated-doctor"
            events.append("connect")

        def require_current_schema(self):
            events.append("schema")
            if failure == "schema":
                raise error

        def close(self):
            events.append("close")

    def metrics():
        events.append("metrics")
        if failure == "metrics":
            raise error
        return {"kernel_id": "threemind.continuous-memory/3"}

    def create_engine(*, backend):
        assert backend == "native"
        events.append("construct")
        if failure == "construct":
            raise error
        return SimpleNamespace(metrics=metrics)

    monkeypatch.setattr(sys, "argv", ["threemind", "doctor"])
    monkeypatch.setattr(cli, "load_env", lambda: None)
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        lambda: SimpleNamespace(
            database_url="postgresql://localhost/isolated-doctor", mode="workstation", backend="native"
        ),
    )
    monkeypatch.setattr(database, "Database", ProbeDatabase)
    monkeypatch.setattr(threemind_runtime, "create_engine", create_engine)
    # A mismatched native extension must remain a failure, without fallback.
    monkeypatch.setattr(host, "create_engine", create_engine)
    if failure:
        with pytest.raises(ValueError) as caught:
            cli.main()
        assert caught.value is error
        assert not capsys.readouterr().out
    else:
        cli.main()
        assert json.loads(capsys.readouterr().out)["engine"]["kernel_id"] == "threemind.continuous-memory/3"
    assert events[0:2] == ["connect", "schema"]
    assert events[-1] == "close" and events.count("close") == 1
    assert events.count("construct") == (0 if failure == "schema" else 1)
