"""External model declarations without importing an optional computation package."""


def probability_contract():
    from threemind_runtime.adapter_contracts import AdapterContract

    return AdapterContract(
        adapter_id="transformer-probability",
        protocol="threemind.probabilities/1",
        roles=["observer", "input"],
        transports=["in_process", "http"],
        signals=[
            {"payload": "token.ids", "direction": "receives", "units": "declared categorical IDs"},
            {"payload": "probability.vector", "direction": "emits", "units": "dimensionless probability"},
        ],
        clocks=["model_us"],
        identity_fields=["model.sha256", "mapping.sha256"],
        identity_rule="Weights and token-channel mapping are explicit hashed external resources.",
        mapping="recorded_channels",
        recovery="external_state_required",
        recovery_rule="Restore the named numeric model and recorded requests; no cloud dependency or implicit retraining.",
        backpressure="Bounded synchronous call with timeout; errors do not create fabricated input.",
        lifecycle="Off unless explicitly called; prepare-frame does not inject into Core.",
        errors="Reject mismatched model hashes, malformed distributions and excessive payloads.",
        required_capabilities=[],
    )


def language_contract():
    from threemind_runtime.adapter_contracts import AdapterContract

    return AdapterContract(
        adapter_id="language-transformer",
        protocol="threemind.language-adapter/1",
        roles=["input", "observer"],
        transports=["in_process"],
        signals=[
            {"payload": "language.text", "direction": "receives", "units": "UTF-8"},
            {"payload": "core.activity", "direction": "receives", "units": "activation, model microseconds"},
            {"payload": "core.stimulus", "direction": "emits", "units": "anonymous channel amplitudes"},
            {"payload": "language.interpretation", "direction": "emits", "units": "text, separately attributed"},
        ],
        clocks=["model_us"],
        identity_fields=["mapping_hash", "input_checkpoint_sha256", "output_checkpoint_sha256"],
        identity_rule="Pinned mappings and weight digests; never upgrade an existing session silently.",
        mapping="fixed_engineering_projection",
        recovery="external_state_required",
        recovery_rule="Restore Core and readout/bus state with exactly the same frozen protocol and converter artifacts.",
        backpressure="One admitted turn per consciousness, bounded compute child and evidence budget.",
        lifecycle="Explicitly created external adapter; stopped between turns; dead Core is never revived.",
        errors="Missing models, invalid mappings and lost jobs are explicit; CUDA faults retry frozen inputs on CPU.",
        required_capabilities=["worker.language_v1"],
    )
