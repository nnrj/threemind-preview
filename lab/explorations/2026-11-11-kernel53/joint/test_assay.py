"""Whole-system preservation, temporal readout and truth isolation checks."""

import gzip
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from apparatus import Learner, pairs, torch
from spec import cases, CURVES


@pytest.mark.parametrize("curve", CURVES)
def test_complete_resume_and_next_learning_update(tmp_path, curve):
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    a = Learner(98765069, curve, "engineering-only")
    a.lesson("P0", 0, "synthetic-teaching")
    a.lesson("P1", 1, "synthetic-teaching")
    a.sample("initial")
    a.fit("initial", steps=3)
    a.checkpoint(tmp_path, Path("whole.json.gz"))
    value = json.loads(gzip.decompress((tmp_path / "whole.json.gz").read_bytes()))
    b = Learner.restore(tmp_path, value)
    x = a.query("P0", 0.79, "verification")
    y = b.query("P0", 0.79, "verification")
    assert x == y and a.state() == b.state()
    a.fit("initial", steps=2)
    b.fit("initial", steps=2)
    assert a.state() == b.state()
    assert len(x["frames"]) == 20 and len(x["reader_frames"]) == 8
    assert len(x["reader_frames"][0]) == 8
    assert set(x["frames"][0]["out0"]) == {"activation", "inhibition", "direct", "associative"}
    assert x["events"][-1]["role"] == "body-feedback"
    assert x["events"][-1]["channels"] == [[a.mapping[f"body{x['choice']}"], 0.2]]


def test_declared_materials_and_reversal():
    assert len(cases()) == 32 and len({r["seed"] for r in cases()}) == 8
    assert all(261111700 <= r["seed"] <= 261111707 for r in cases())
    assert pairs("initial") == dict(P0=0, P1=1, A0=0, A1=1)
    assert pairs("reversal") == dict(P0=0, P1=1, A0=1, A1=0, B0=0, B1=1)
    assert pairs("return") == pairs("new")


def test_observation_does_not_advance_or_change_state():
    x = Learner(98765070, "power-law", "read-only-check")
    x.lesson("P0", 0, "synthetic-teaching")
    before = x.state()
    for _ in range(4):
        x.core.graph()
        x.core.observation_nodes()
        x.reader_digest()
    assert x.state() == before
