"""Observe input and optional spike events without copying every synaptic arrival."""


def advance_observed(engine, target, observer, *, record_spikes=True):
    options = {"inputs_only": True}
    if getattr(engine, "dynamics", None) == "threemind.lif/1":
        options["record_spikes"] = record_spikes
    engine.advance_to(target, observer, **options)


def spike_record(event):
    return {
        "key": f"spikes:{event['sequence']}",
        "time_us": event["time_us"],
        "kind": "spikes",
        "payload": event["payload"] | {"kernel_id": "threemind.lif/1", "sequence": event["sequence"]},
    }
