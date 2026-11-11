"""Executable SDK checks for small, supplied adapter fixtures; no database or UI.

Callables are trusted developer code, not loaded from uploaded manifests. A pass
covers only these fixtures and the selected backend, never arbitrary devices.
"""

from copy import deepcopy
from hashlib import sha256
from itertools import islice, pairwise

from threemind_core import Stimulus

from .adapter_contracts import canonical
from .bus import InputBus, LatestOutput, OutputBus
from .host import create_engine
from .sensory import InputBusConfig


def fingerprint(value):
    return sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def check_input_encoder(encode, carrier, *, backend="reference", maximum_frames=64, maximum_channels=256):
    """Check a stateless encoder returning ordered Stimulus objects for one fixture.

    Stateful sensors must provide an explicit restored encoder for the same
    fixture; passing a live camera or consuming device would not be equivalent.
    """
    raw = deepcopy(carrier)
    before = fingerprint(raw)
    frames = list(islice(encode(raw), maximum_frames + 1))
    if fingerprint(raw) != before:
        raise ValueError("encoder mutated the original carrier fixture")
    if not 1 <= len(frames) <= maximum_frames or any(not isinstance(f, Stimulus) for f in frames):
        raise ValueError("encoder must return a bounded, nonempty sequence of Stimulus objects")
    payload = [f.to_dict() for f in frames]
    repeated = deepcopy(carrier)
    second = list(islice(encode(repeated), maximum_frames + 1))
    if fingerprint(repeated) != before or any(not isinstance(f, Stimulus) for f in second):
        raise ValueError("repeated encoding mutated its carrier or returned invalid frames")
    if [f.to_dict() for f in second] != payload:
        raise ValueError("encoder is not deterministic for this fixed fixture and configuration")
    if sum(len(f.channels) for f in frames) > maximum_channels:
        raise ValueError("fixture exceeds the executable check channel budget")
    if any(a.time_us > b.time_us for a, b in pairwise(frames)) or frames[-1].time_us > 1_000_000:
        raise ValueError("fixture times must be ordered within one model second")

    baseline = create_engine(backend=backend)
    bus = InputBus(baseline)
    bus.reserve(len(frames), sum(len(f.channels) for f in frames))
    for index, frame in enumerate(frames):
        bus.schedule(frame, {"envelope_id": "fixture-" + str(index), "source": "manual-anonymous"})
    queued, bus_state = baseline.capture_state(), bus.capture()
    resumed = create_engine(state=queued, backend=backend)
    restored = InputBus(resumed, bus_state)
    restored.verify(queued.to_dict())
    observed = create_engine(backend=backend)
    observed_bus = InputBus(observed)
    for index, frame in enumerate(frames):
        observed_bus.schedule(frame, {"envelope_id": "different-label-" + str(index), "note": "observation metadata"})
    if observed.capture_state().digest != queued.digest:
        raise ValueError("observation metadata changed queued Core state")
    output, facts, view = OutputBus(), [], LatestOutput()
    output.subscribe("malicious-observer-fixture", lambda value: value.clear())
    output.subscribe("faithful-evidence", facts.append)
    output.subscribe("lossy-view", view)
    expected = []

    def observe(event):
        observed_bus.observe(event)
        expected.append(deepcopy(event))
        output.publish(event)

    until = frames[-1].time_us + 20_000
    baseline.advance_to(until, bus.observe)
    resumed.advance_to(until, restored.observe)
    observed.advance_to(until, observe)
    hashes = [engine.capture_state().digest for engine in (baseline, resumed, observed)]
    if len(set(hashes)) != 1 or facts != expected:
        raise ValueError("pending recovery or independent observation changed scientific evidence")
    if any(b.pending_count() for b in (bus, restored, observed_bus)):
        raise ValueError("a scheduled frame was not delivered")
    latest = view.take()
    if latest["skipped"] != max(0, len(facts) - 1):
        raise ValueError("lossy view did not report all skipped frames")
    bounded = InputBus(create_engine(backend=backend), config=InputBusConfig(max_pending_frames=1))
    empty_hash = bounded.engine.capture_state().digest
    try:
        bounded.reserve(2, 1)
    except ValueError:
        pass
    else:
        raise ValueError("input capacity refusal was not visible")
    if bounded.engine.capture_state().digest != empty_hash:
        raise ValueError("capacity refusal changed Core state")

    def failed_consumer(value):
        raise RuntimeError("explicit consumer fixture failure")

    failing = OutputBus()
    detach = failing.subscribe("fixture", failed_consumer)
    try:
        failing.publish({"raw": "fixture"})
    except RuntimeError:
        pass
    else:
        raise ValueError("consumer failure was silently swallowed")
    detach()
    failing.publish({"raw": "detached fixture"})
    return {
        "version": "threemind.adapter-check/1",
        "backend": backend,
        "carrier_sha256": before,
        "encoded_frames_sha256": fingerprint(payload),
        "frame_count": len(frames),
        "delivered_events": len(facts),
        "state_hash": hashes[0],
        "checks": {
            "deterministic_encoding": True,
            "carrier_unchanged": True,
            "pending_recovery": True,
            "metadata_invariance": True,
            "observer_isolation": True,
            "explicit_view_skips": True,
            "capacity_refusal_without_core_change": True,
            "consumer_failure_and_detach": True,
        },
        "limits": [
            "Only the supplied fixture, fixed delivered inputs, protocol and chosen backend were exercised.",
            "This does not validate physical hardware, arbitrary adapter code, learnt control or semantic intent.",
            "Observation consumer failure still needs the owning host's recovery policy.",
        ],
    }


def builtin_checks(adapter_id, *, backend="reference"):
    from .network import decode_frames
    from .sensory import TextSensor, carrier_frames

    fixture = [{"time_us": "0", "channels": [[1, 0.5], [2, 0.3]]}, {"time_us": "30000", "channels": [[2, 0.4]]}]
    if adapter_id == "remote-anonymous":

        def encode(value):
            rows, _ = decode_frames(value, seed=23, wiring_id="fefb3009-5c18-4de6-bd60-bdfe781f3393")
            return [Stimulus.from_dict(row) for row in rows]

        carrier = fixture + [{"time_us": "45000", "channels": [[1, -0.2]]}]
    elif adapter_id == "anonymous-frames":

        def encode(value):
            return [f["stimulus"] for f in carrier_frames(adapter_id, value, 23, {})]

        carrier = {"frames": fixture}
    elif adapter_id == "text-sensor":

        def encode(value):
            return [f["stimulus"] for f in TextSensor(23).frames(value)]

        carrier = "蜂蜜 / fixture"
    else:
        raise ValueError("no bundled executable fixture for this adapter; supply an explicit SDK check")
    return check_input_encoder(encode, carrier, backend=backend) | {"adapter_id": adapter_id}
