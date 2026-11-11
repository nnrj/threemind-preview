from unittest.mock import Mock

import pytest

from threemind_core import Config, Stimulus
from threemind_runtime import create_engine
from threemind_runtime.cold_state import FrozenCore, StateReference


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_archived_dead_core_releases_mutability_and_preserves_all_observations(backend):
    engine = create_engine(Config(activation_tau=0.001), backend=backend)
    engine.inject(Stimulus(1000, ((101, 1.0), (202, 0.7), (303, 0.4))))
    engine.advance_to(10000)
    engine.close_inputs()
    engine.advance_to(1200000)  # allow the default one-second quiescence grace
    assert engine.life == "dead"
    image = engine.capture_state()
    read = Mock(return_value=image)
    reference = StateReference(image.digest, read)
    frozen = FrozenCore(engine, reference, backend=backend)
    for _ in range(100):
        assert frozen.capture_state() == image
        assert frozen.metrics() == engine.metrics()
        assert frozen.time_us == engine.time_us
    read.assert_not_called()
    nodes = engine.observation_nodes()
    assert len(nodes) == 3 and engine.metrics()["edges"] > 0
    assert frozen.observation_nodes() == nodes
    ids = [n["id"] for n in nodes]
    assert frozen.induced_edges(ids) == engine.induced_edges(ids)
    assert frozen.graph() == engine.graph()
    assert frozen.activations() == engine.activations()
    assert frozen.capture_state().payload == image.payload
    from threemind_runtime.codec import ArtifactCodec

    assert ArtifactCodec.decode(ArtifactCodec.encode(frozen.capture_state(), "tmind")).digest == image.digest
    for operation in ("inject", "close_inputs", "advance_to", "intervene", "reconfigure"):
        with pytest.raises(ValueError, match="cannot"):
            getattr(frozen, operation)(None)


def test_state_reference_rejects_corruption_and_archival_of_a_live_core():
    engine = create_engine()
    image = engine.capture_state()
    source = StateReference(image.digest, lambda: image)
    with pytest.raises(ValueError, match="dead core"):
        FrozenCore(engine, source)
    with pytest.raises(ValueError, match="checksum"):
        StateReference("0" * 64, lambda: image).materialize()
