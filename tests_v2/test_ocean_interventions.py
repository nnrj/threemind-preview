from lab.tools.ocean_evolution import EvolutionOcean, EvolutionProtocol
from lab.tools.ocean_interventions import make_control


def prepared():
    w = EvolutionOcean(EvolutionProtocol(founders=2, reproduction=False).model_dump(by_alias=True))
    for _ in range(50):
        w.step()
    assert all(e.capture_state().to_dict()["edges"] for e in w.engines.values())
    return w


def test_common_garden_keeps_mapping_and_body_but_separates_history():
    source = prepared()
    before = source.capture()
    retained, _ = make_control(source, "inherited", environment_seed=9123)
    erased, _ = make_control(source, "naive", environment_seed=9123)
    a, b = retained.capture(), erased.capture()
    assert {k: v for k, v in a.items() if k != "core_hashes"} == {k: v for k, v in b.items() if k != "core_hashes"}
    for i in retained.engines:
        x, y = retained.engines[i], erased.engines[i]
        assert x.config == y.config
        dx, dy = x.capture_state().to_dict(), y.capture_state().to_dict()
        assert [(n["id"], n["channel"]) for n in dx["nodes"]] == [(n["id"], n["channel"]) for n in dy["nodes"]]
        assert dx["edges"] and not dy["edges"]
        assert x.metrics()["energy"] == y.metrics()["energy"]
        assert list(x.activations()) == list(y.activations())
        assert all(value == 0 for _, value in x.activations())
    assert source.capture() == before
    assert abs(retained.metrics()["energy_balance_error"]) < 1e-7
    assert abs(erased.metrics()["energy_balance_error"]) < 1e-7


def test_edge_silence_is_reversible_and_preserves_energy_signals_and_source():
    source = prepared()
    before = source.capture()
    sham, _ = make_control(source, "sham")
    muted, receipt = make_control(source, "silence")
    for i in sham.engines:
        a, b = sham.engines[i], muted.engines[i]
        x, y = a.capture_state().to_dict(), b.capture_state().to_dict()
        assert x["queue"] == y["queue"]
        assert x["energy"] == y["energy"]
        assert set(map(tuple, y["silenced_edges"])) == {(e["source"], e["target"]) for e in y["edges"]}
        assert x | {"silenced_edges": y["silenced_edges"]} == y
        a.intervene(action="unsilence")
        b.intervene(edges=receipt["edges"][i], action="unsilence")
        assert a.capture_state().digest == b.capture_state().digest
    assert source.capture() == before
