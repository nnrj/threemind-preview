"""Scientific protocol invariants, independent of output quality."""

from runner import END_US, HISTORIES, PROFILES, TAUS, identities


def test_equal_dose_courses_share_final_time_but_differ_in_spacing():
    for name in ("single4", "massed", "spaced"):
        assert abs(sum(d for _, d in HISTORIES[name]) - 4) < 1e-12
        assert HISTORIES[name][-1][0] == END_US
    gaps = [b[0] - a[0] for a, b in zip(HISTORIES["spaced"], HISTORIES["spaced"][1:])]
    assert gaps == sorted(gaps) and len(set(gaps)) > 1


def test_only_registered_local_parameters_change_and_channels_are_distinct():
    assert set(PROFILES["ordinary2"]) == {"first_gain", "repeat_gain"}
    assert set(PROFILES["stability2"]) == {"stability_gain"}
    assert 0 in TAUS and 1 in TAUS
    ids = identities(100101)
    assert len(set(ids.values())) == len(ids)
    assert ids == identities(100101)
    assert not set(ids.values()) & set(identities(100111).values())


def test_expression_factorial_preserves_all_unregistered_parameters():
    from dataclasses import replace

    from reversal import FIELDS, VARIANTS

    from threemind_kernels.novelty import NoveltyConfig

    baseline = NoveltyConfig()
    assert len(VARIANTS) == 17 and VARIANTS["1111"] == VARIANTS["silence"] == {}
    for variant, patch in VARIANTS.items():
        changed = replace(baseline, **patch)
        assert set(patch) <= set(FIELDS)
        assert changed.forgetting_rate == baseline.forgetting_rate
        assert changed.intensity_gain == baseline.intensity_gain == 0.075
        assert changed.stp_enabled and changed.plasticity
        if variant != "silence":
            assert tuple(bool(getattr(changed, k)) for k in FIELDS) == tuple(c == "1" for c in variant)


def test_order_state_comparison_does_not_confuse_node_numbers_with_information():
    import copy

    from analyze_sequence import NODE_FIELDS, difference, vector

    from threemind_kernels.novelty import NoveltyConfig

    image = {
        "config": NoveltyConfig().to_dict(),
        "time_us": "1000000",
        "nodes": [{"id": i, "channel": 100 * i, **dict.fromkeys(NODE_FIELDS, 0.1)} for i in (1, 2)],
        "edges": [{"source": 1, "target": 2, "weight": 0.2, "stability": 0.1, "eligibility": 0.01}],
        "operator_state": {
            "short_term": [{"source": 1, "target": 2, "state": {"time_us": 0}}],
            "fast": [{"source": 1, "target": 2, "state": {"value": 0.1, "time_us": 0}}],
        },
    }
    renamed = copy.deepcopy(image)
    mapping = {1: 8, 2: 4}
    for n in renamed["nodes"]:
        n["id"] = mapping[n["id"]]
    renamed["nodes"].reverse()
    for row in renamed["edges"] + renamed["operator_state"]["short_term"] + renamed["operator_state"]["fast"]:
        row["source"], row["target"] = mapping[row["source"]], mapping[row["target"]]
    assert vector(image) == vector(renamed)
    assert not any(difference(vector(image), vector(renamed)).values())
