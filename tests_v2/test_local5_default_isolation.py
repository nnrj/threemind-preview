"""The opt-in coincident receiver must not alter the default /5 path.

Synthetic current-state fixtures only; no historical or formal organism runs.
The reference below removes only the coincident dispatch branch, without
changing the sequential receiver's grouping, formulas or event order.
"""

import json

import pytest

from threemind_core import Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local5 import Local5Config, Local5Engine
from threemind_kernels.local5_native import NativeLocal5Engine


class _WithoutCoincident(Local5Engine):
    def _receive(self, packets):
        internal = [m for _, messages, direct, _ in packets if not direct for m in messages]
        emitted_internal = False
        for serial, messages, direct, intensity in packets:
            if direct:
                self._receive_group([(serial, messages, True, intensity)])
            elif not emitted_internal:
                self._receive_group([(serial, internal, False, 1.0)])
                emitted_internal = True


def _curriculum(engine):
    for when, channels in (
        (0, ((1, 0.9), (2, 0.8))),
        (70000, ((1, 0.7), (3, 0.8))),
        (110000, ((1, 0.4), (3, 0.2))),
        (110000, ((2, 0.3),)),
        (611337, ((1, 0.8), (2, 0.6))),
    ):
        engine.inject(Stimulus(when, channels))


def _mixed_same_time_exists(engine):
    state = engine.capture_state().to_dict()
    due = [event for event in state["queue"] if event["time_us"] == "110000"]
    receptor = next(node["id"] for node in state["nodes"] if node["channel"] == 1)
    assert any(
        event["kind"] == "stimulus" and any(channel == 1 for channel, _ in event["payload"]["channels"])
        for event in due
    )
    assert any(
        event["kind"] == "signal" and any(message[1] == receptor for message in event["payload"]["messages"])
        for event in due
    )


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("source", ["legacy-source", "unified"])
def test_default_equals_explicit_sequential_and_branch_removed_reference(mode, source):
    default = Local5Config(consolidation_mode=mode, reception_mode=source, quiescence_death_us=10**12)
    explicit = Local5Config(**(default.to_dict() | {"arrival_mode": "sequential"}))
    engines = [Local5Engine(default), Local5Engine(explicit), _WithoutCoincident(default)]
    one_advance = Local5Engine(default)
    for engine in [*engines, one_advance]:
        _curriculum(engine)
    for when in (100000, 110000, 170000, 611337, 2000000):
        for engine in engines:
            engine.advance_to(when)
            if when == 100000:
                _mixed_same_time_exists(engine)
        expected = canonical_bytes(engines[0].capture_state().to_dict())
        assert all(canonical_bytes(engine.capture_state().to_dict()) == expected for engine in engines[1:])
        engines = [type(engine)(state=engine.capture_state()) for engine in engines]
    one_advance.advance_to(2000000)
    assert canonical_bytes(one_advance.capture_state().to_dict()) == canonical_bytes(
        engines[0].capture_state().to_dict()
    )


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("source", ["legacy-source", "unified"])
def test_native_default_equals_explicit_sequential_with_mixed_events_and_restore(mode, source):
    native = pytest.importorskip("_threemind_native")
    if not hasattr(native, "NativeLocal5"):
        pytest.skip("memory/5 native binding is required")
    default = Local5Config(consolidation_mode=mode, reception_mode=source, quiescence_death_us=10**12)
    explicit = Local5Config(**(default.to_dict() | {"arrival_mode": "sequential"}))
    engines = [NativeLocal5Engine(default), NativeLocal5Engine(explicit)]
    one_advance = NativeLocal5Engine(default)
    for engine in [*engines, one_advance]:
        _curriculum(engine)
    for when in (100000, 110000, 170000, 611337, 2000000):
        for engine in engines:
            engine.advance_to(when)
            if when == 100000:
                _mixed_same_time_exists(engine)
        assert canonical_bytes(engines[0].capture_state().to_dict()) == canonical_bytes(
            engines[1].capture_state().to_dict()
        )
        engines = [NativeLocal5Engine(state=engine.capture_state()) for engine in engines]
    one_advance.advance_to(2000000)
    assert canonical_bytes(one_advance.capture_state().to_dict()) == canonical_bytes(
        engines[0].capture_state().to_dict()
    )


def test_raw_native_omitted_arrival_mode_is_sequential():
    native = pytest.importorskip("_threemind_native")
    if not hasattr(native, "NativeLocal5"):
        pytest.skip("memory/5 native binding is required")
    default = native.NativeLocal5("{}")
    explicit = native.NativeLocal5('{"arrival_mode":"sequential"}')
    assert json.loads(default.config_json())["arrival_mode"] == "sequential"
    for engine in (default, explicit):
        for when, channels in ((0, ((1, 0.9), (2, 0.8))), (110000, ((1, 0.2), (3, 0.5)))):
            engine.inject(json.dumps(Stimulus(when, channels).to_dict()))
        engine.advance("110000", False)
    assert canonical_bytes(json.loads(default.state_json())) == canonical_bytes(json.loads(explicit.state_json()))
