import pytest

from lab.tools.ocean_cli import write_json
from lab.tools.ocean_exchange_summary import summarize


def test_exchange_observer_counts_direction_age_and_rejects_missing_evidence(tmp_path):
    write_json(
        tmp_path / "initial/manifest.json",
        {"context": {"time_us": 100, "protocol": {"maturity_us": 60}, "totals": {"sharing_contacts": 5}}},
    )
    members = [
        {"id": 0, "parent": None, "birth_us": 0},
        {"id": 1, "parent": 0, "birth_us": 100},
        {"id": 2, "parent": None, "birth_us": 0},
    ]
    write_json(tmp_path / "result.json", {"time_us": 200, "members": members, "totals": {"sharing_contacts": 9}})
    events = [
        {"kind": "resource_exchange", "time_us": t, "donor": a, "receiver": b, "sent": 10, "received": 9}
        for t, a, b in ((110, 0, 1), (120, 1, 0), (160, 0, 1), (180, 2, 1))
    ]
    write_json(tmp_path / "events.json", events)
    r = summarize(tmp_path)
    assert r["transfer_steps"] == 4
    assert r["distinct_pairs"] == 2
    assert r["sent"] == 40
    assert r["received"] == 36
    assert r["relationships"]["parent_to_child"]["steps"] == 2
    assert r["relationships"]["parent_to_child"]["to_immature_received"] == 9
    assert r["relationships"]["child_to_parent"]["steps"] == 1
    assert r["relationships"]["other"]["steps"] == 1
    (tmp_path / "events.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="ledger"):
        summarize(tmp_path)
