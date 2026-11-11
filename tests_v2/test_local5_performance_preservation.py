"""Exact /5 transition witnesses frozen before the bounded performance pass.

Only compact digests are tracked; original synthetic snapshots stay in .work.
These are engineering witnesses, not research experiments or organism results.
"""

import hashlib
import itertools
from dataclasses import replace

import pytest

from threemind_core import Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local import LocalConfig, LocalEngine
from threemind_kernels.local5 import Local5Config, Local5Engine, Local5Node
from threemind_kernels.mechanisms import FastTrace

CONFIGURATIONS = list(
    itertools.product(
        ("adaptive-half-life", "legacy-stability"),
        ("legacy-source", "unified"),
        ("sequential", "coincident"),
        ("aligned", "asynchronous"),
    )
)
FROZEN = (
    "2772fac58839671659f05c377ea93cd94b54d5fafb5697334d44ba5d39b2a7d6",
    "aa40c26f26e995a5bffd0c7a303d8adccade21b81b8263f8ad21f8ed1e180d1e",
    "0b5d1bbd779e44fcc3373de33e9c35f446729e3a5da264c931087127be5db253",
    "d323a2aaec42b8938b671cd9b7b062d3fd4f4838234aceac2c7f018acdcb9e56",
    "917f48265340bd806a54a36f96bdb1a9e30d4a1f45a22f2f755f5ddcc354a0de",
    "458af86db77aaf7d71febf6efd9ecb05cf74a3acc08ddb9d1e80d27216df71f1",
    "902d8b68b2e2dadbf1608beb31b765e7d3aafb83b26013d2154ba695eee38305",
    "e79d66b1b5e9b5aa71ab2ba14b518b4660786347c7b094fb5bf385681707c92e",
    "7d4e7432b7c2328d672197c0150e21c647a752742146627d340992ec99a36fb9",
    "a4fc36bc2d907827390ebdc594873a9cc499834259cef153f5ed05928ad3e120",
    "85612085bb8b984b929fbcec59a1f95999c6d1093022a4745e2b6a82395b6428",
    "a6091384d1240805f44b1b638db9dc0ff25253ad5c50403c2e7cfb14fb20513b",
    "9bb6828e72a62c548fec0818cdbe5aba65abc1744d409161fbc643498d7eb703",
    "ad3bd916e4fdabeddcdd513cc8f027819c4e7cfa11d7e3de7d42f57ff7229eb3",
    "8c567f1b8e1ee9adac9b9ba790bc19c11b68999b2f946f0ac8357f697f452549",
    "674a316f81e217798e919e431151625219cf9e9e52e608c5c22976b9eda26aba",
)


@pytest.mark.parametrize("choices,digest", list(zip(CONFIGURATIONS, FROZEN)))
def test_performance_cleanup_keeps_seven_boundaries_bit_identical(choices, digest):
    mode, source, arrival, phase = choices
    config = Local5Config(
        consolidation_mode=mode,
        reception_mode=source,
        arrival_mode=arrival,
        propagation_phase=phase,
        quiescence_death_us=10**12,
    )
    engine, snapshots = Local5Engine(config), []
    for when, channels in (
        (0, ((1, 0.8), (2, 0.7))),
        (70000, ((1, 0.5), (3, 0.5))),
        (80000, ((1, 0.1),)),
        (110000, ((1, 0.6), (4, 0.7))),
        (611337, ((1, 0.6), (3, 0.7))),
    ):
        engine.inject(Stimulus(when, channels))
        engine.advance_to(when)
        snapshots.append(engine.capture_state().to_dict())
    engine.advance_to(1000000)
    engine.inject(Stimulus(1000000, ((1, 0.1), (4, 0.2))))
    engine.advance_to(1000000)
    snapshots.append(engine.capture_state().to_dict())
    engine = Local5Engine(state=engine.capture_state())
    engine.reconfigure(replace(config, plasticity=False))
    engine.advance_to(2000000)
    engine.reconfigure(config)
    engine.advance_to(2300000)
    snapshots.append(engine.capture_state().to_dict())
    assert hashlib.sha256(canonical_bytes(snapshots)).hexdigest() == digest


@pytest.mark.parametrize("fatigue,salience", [(0.0, 0.0), (0.0, 0.8), (0.6, 0.0), (0.6, 0.8)])
def test_fatigue_projection_matches_prior_formula_even_when_disabled(fatigue, salience):
    current = Local5Engine(Local5Config(strong_fatigue_enabled=False))
    reference = LocalEngine(LocalConfig(strong_fatigue_enabled=False))
    node = Local5Node(0, 1, fatigue=fatigue, salience=salience, half_life=30.0)
    assert current._project_node(node, 1731111) == reference._project_node(node, 1731111)


def test_successful_transmission_projects_each_fast_trace_once(monkeypatch):
    calls = []
    projected = FastTrace.projected

    def counted(self, when, config):
        calls.append((self.time_us, when))
        return projected(self, when, config)

    monkeypatch.setattr(FastTrace, "projected", counted)
    engine = Local5Engine(Local5Config(inhibition=False))
    engine.inject(Stimulus(0, ((1, 0.9), (2, 0.9))))
    engine.advance_to(100000)
    transmitted = [edge for edge in engine.edges.values() if edge.last_pass_us == "100000"]
    assert len(transmitted) == 2 and len(calls) == len(transmitted)


def test_single_valid_arrival_needs_no_attention_softmax(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("one message has no attention competition")

    monkeypatch.setattr("threemind_kernels.local5.local_attention", unexpected)
    engine = Local5Engine(Local5Config(reception_mode="unified", context_mix=0.37))
    engine.inject(Stimulus(0, ((1, 0.3),)))
    engine.advance_to(0)
    assert engine.nodes[0].activation == 0.27
