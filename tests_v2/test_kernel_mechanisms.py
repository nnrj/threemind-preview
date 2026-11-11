import json
import math
from dataclasses import asdict

import pytest

from threemind_kernels.mechanisms import (
    FastTrace,
    FastTraceConfig,
    ShortTermConfig,
    ShortTermState,
    local_attention,
    membrane_response,
)


def test_short_term_depletion_and_rest_recovery_conserve_resources():
    config = ShortTermConfig()
    state, first = ShortTermState().release(0, config)
    assert first == 0.5
    state, second = state.release(0, config)
    assert second == 0.25
    assert state.available == 0.25 and state.active == 0.75
    recovered = state.recovered(800_000, config)
    assert recovered.available > state.available
    assert recovered.utilization == config.utilization
    assert recovered.active >= 0 and 0 <= recovered.available + recovered.active <= 1.0
    rested, last = recovered.release(30_000_000, config)
    assert last == pytest.approx(0.5, abs=1e-14)
    assert rested.available == pytest.approx(0.5, abs=1e-14)


def test_facilitation_and_equal_time_constant_analytic_limit():
    config = ShortTermConfig(utilization=0.04, recovery_tau_s=0.1, facilitation_tau_s=1.0)
    state, first = ShortTermState().release(0, config)
    state, second = state.release(20_000, config)
    assert second > first
    equal = ShortTermConfig(recovery_tau_s=0.01, active_tau_s=0.01)
    state, _ = ShortTermState().release(0, equal)
    recovered = state.recovered(10_000, equal)
    assert recovered.active == pytest.approx(0.5 / math.e)
    assert recovered.available == pytest.approx(1 - 1 / math.e)


@pytest.mark.parametrize("facilitation", [0.0, 1.0])
def test_short_term_recovery_partition_invariance(facilitation):
    config = ShortTermConfig(facilitation_tau_s=facilitation)
    origin, _ = ShortTermState().release(0, config)
    direct = origin.recovered(123_456, config)
    split = origin.recovered(17_131, config).recovered(123_456, config)
    for key in ("available", "active", "utilization"):
        assert getattr(direct, key) == pytest.approx(getattr(split, key), rel=1e-12, abs=1e-14)
    assert origin.time_us == 0  # Observation/projection never mutates the source.


def test_fast_trace_tracks_actual_transmission_without_changing_slow_weight():
    config = FastTraceConfig()
    origin = FastTrace()
    learned = origin.transmit(0.7, 0, config)
    assert learned.value == pytest.approx(1 - math.exp(-0.07))
    assert learned.projected(2_000_000, config) == pytest.approx(learned.value / math.e)
    assert learned.efficacy(0.3, 0, config) > 0.3
    assert learned.efficacy(0.3, 0, FastTraceConfig(gain=0)) == 0.3
    assert origin.value == 0
    assert FastTrace().transmit(0, 0, config).value == 0


def test_receiver_local_attention_is_permutation_equivariant_and_preserves_raw_data():
    query, keys, amounts = [1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], [0.7, 0.2]
    response, coefficients = local_attention(query, keys, amounts)
    reverse, reverse_coefficients = local_attention(query, keys[::-1], amounts[::-1])
    assert response == pytest.approx(reverse)
    assert coefficients == pytest.approx(reverse_coefficients[::-1])
    assert coefficients[0] > coefficients[1]
    assert sum(coefficients) == pytest.approx(1.0)
    assert 0 <= response <= sum(amounts)
    assert amounts == [0.7, 0.2]
    assert local_attention(query, keys, amounts, mix=0) == (sum(amounts), [1.0, 1.0])
    assert local_attention(query, [keys[0]], [0.7])[0] == 0.7


def test_membrane_analytic_response_and_zero_input_relaxation():
    voltage, current = membrane_response(-55, 0, 0.02)
    assert voltage == pytest.approx(-65 + 10 / math.e)
    assert current == 0
    voltage, current = membrane_response(-65, 0.1, 0.02, current_tau_s=0.02)
    assert voltage == pytest.approx(-65 + 10 / math.e)
    assert current == pytest.approx(0.1 / math.e)
    direct = membrane_response(-63, 0.3, 0.1)
    mid = membrane_response(-63, 0.3, 0.031)
    split = membrane_response(*mid, 0.069)
    assert direct == pytest.approx(split, rel=1e-12, abs=1e-14)


@pytest.mark.parametrize("source_tau", [0.02, 0.02 + 1e-14, 0.02 - 1e-14, 0.005, 0.8])
def test_membrane_near_equal_taus_and_large_elapsed_time(source_tau):
    a = membrane_response(-65, 0.1, 0.02, current_tau_s=source_tau)
    if abs(source_tau - 0.02) < 1e-12:
        assert a[0] == pytest.approx(-65 + 10 / math.e, abs=1e-10)
    assert membrane_response(-55, 0.1, 1e30, current_tau_s=source_tau) == (-65, 0)


def test_invalid_operator_state_and_time_are_rejected():
    with pytest.raises(ValueError):
        ShortTermState(available=0.8, active=0.4)
    with pytest.raises(ValueError):
        ShortTermState(time_us=10).release(9, ShortTermConfig())
    with pytest.raises(ValueError):
        FastTrace(float("nan"))
    with pytest.raises(ValueError):
        local_attention([1], [[1, 2]], [0.1])
    with pytest.raises(ValueError):
        membrane_response(-65, 1, -0.1)


def native_probe(**request):
    from _threemind_native import mechanism_probe

    return json.loads(mechanism_probe(json.dumps(request, allow_nan=False).encode()))


def serialized_state(state):
    value = asdict(state)
    value["time_us"] = str(value["time_us"])
    return value


@pytest.mark.parametrize(
    "config",
    [
        ShortTermConfig(),
        ShortTermConfig(utilization=0.04, recovery_tau_s=0.1, facilitation_tau_s=1.0),
        ShortTermConfig(active_tau_s=0.8),
        ShortTermConfig(active_tau_s=0.8 + 1e-14),
        ShortTermConfig(utilization=0.0),
        ShortTermConfig(utilization=1.0),
    ],
)
def test_native_short_term_matches_reference_through_repeated_events(config):
    state = ShortTermState()
    native = serialized_state(state)
    for when in (0, 0, 1171, 20_000, 20_001, 93_703, 800_000, 2_000_000, 30_000_000):
        result = native_probe(
            operator="threemind.tm-synapse/1", config=asdict(config), state=native, time_us=str(when), release=True
        )
        state, release = state.release(when, config)
        assert result["released"] == pytest.approx(release, rel=1e-12, abs=1e-14)
        for key in ("available", "active", "utilization"):
            assert result["state"][key] == pytest.approx(getattr(state, key), rel=1e-12, abs=1e-14)
        assert result["state"]["time_us"] == str(state.time_us)
        native = result["state"]


def test_native_fast_trace_and_attention_match_reference():
    state, config = FastTrace(), FastTraceConfig()
    for when, amount in ((0, 0.7), (39_379, 0.2), (2_001_231, 0.0)):
        native = native_probe(
            operator="threemind.leaky-fast-trace/1",
            config=asdict(config),
            state=serialized_state(state),
            time_us=str(when),
            amount=amount,
            slow_weight=0.4,
        )
        assert native["efficacy_before_transmission"] == pytest.approx(state.efficacy(0.4, when, config))
        state = state.transmit(amount, when, config)
        assert native["state"]["value"] == pytest.approx(state.value, rel=1e-12, abs=1e-14)
    for mix in (0.0, 0.5, 1.0):
        for temperature in (1e-6, 1.0, 1e6):
            parameters = {
                "query": [1.0, -1.0],
                "keys": [[1.0, -1.0], [0.2, 0.1], [-1.0, 1.0]],
                "amounts": [0.3, 0.8, 0.4],
                "temperature": temperature,
                "mix": mix,
            }
            reference, factors = local_attention(**parameters)
            native = native_probe(operator="threemind.local-context-attention/1", **parameters)
            assert native["response"] == pytest.approx(reference, rel=1e-12, abs=1e-14)
            assert native["coefficients"] == pytest.approx(factors, rel=1e-12, abs=1e-14)


@pytest.mark.parametrize("tau", [0.005, 0.02, 0.02 + 1e-14, 0.02 - 1e-14])
def test_native_membrane_matches_reference(tau):
    for dt in (0, 0.001379, 0.02, 1e30):
        reference = membrane_response(-63, 0.1, dt, current_tau_s=tau)
        native = native_probe(
            operator="threemind.rc-membrane/1", config={"current_tau_s": tau}, voltage_mv=-63, current_na=0.1, dt_s=dt
        )
        assert [native["voltage_mv"], native["current_na"]] == pytest.approx(reference, rel=1e-12, abs=1e-14)


def test_native_probe_rejects_unknown_fields_and_invalid_state():
    with pytest.raises(ValueError):
        native_probe(operator="threemind.rc-membrane/1", config={}, voltage_mv=-65, current_na=1, dt_s=-1)
    with pytest.raises(ValueError):
        native_probe(operator="threemind.rc-membrane/1", config={}, voltage_mv=-65, current_na=1, dt_s=1, code="unused")
    with pytest.raises(ValueError):
        native_probe(operator="unimplemented")
