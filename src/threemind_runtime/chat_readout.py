"""Legacy readable presentation of current evidence; no Core or scoring changes."""

import hashlib

CHAT_VERSION = "threemind.chat-readout/2"


def display_readout(value, limit=None, *, offset=0, order="activation", scope=None):
    temporal = value["kind"] == "temporal_readout"
    scope = scope or ("candidates" if temporal else "active")
    limit = (7 if temporal else 128) if limit is None else limit
    if limit < 0 or offset < 0 or order not in ("activation", "id") or scope not in ("candidates", "active", "all"):
        raise ValueError("invalid chat presentation selection")
    raw = value.get("nodes", []) if temporal else value.get("raw_nodes", value.get("activity_nodes", []))
    labels = value.get("annotations", {})
    identity = lambda n: int(n.get("node_id", n.get("id")))
    strength = lambda n: (
        (
            (n.get("decision_activation") or 0)
            if value.get("analysis_schema")
            else n.get("peak_activation", n.get("activation", 0))
        )
        if temporal
        else n.get("activation", 0)
    )
    active_count = sum(strength(n) > 0 for n in raw)
    rows = list(raw) if scope == "all" else [n for n in raw if strength(n) > 0]
    if temporal and scope == "candidates":
        # Recorded candidate order is authoritative; never substitute peak or ID.
        by_id = {identity(n): n for n in raw}
        rows = [by_id[int(k)] for k in value.get("candidate_ids", []) if int(k) in by_id]
    elif not temporal and order == "activation":
        # Legacy display tie-breaks, using current names for the trace fields.
        rows.sort(
            key=lambda n: (
                -strength(n),
                -n.get("direct", 0) - n.get("associative", 0),
                -n.get("stability", 0),
                identity(n),
            )
        )
    else:
        rows.sort(key=identity)
    selected = rows[offset : offset + limit] if limit else rows[offset:]
    nodes = [
        {
            "id": identity(n),
            "activation": strength(n),
            "labels": labels.get(str(identity(n)), []),
            **(
                {
                    k: n.get(k)
                    for k in ("score", "last_activation", "decision_activation", "active_us", "excess_integral")
                }
                if temporal
                else {}
            ),
        }
        for n in selected
    ]
    readable = list(dict.fromkeys(label for n in nodes for label in n["labels"] if label))
    fingerprint = value.get("window_id") or (value.get("structure") or {}).get("state_signature")
    if not fingerprint:
        fingerprint = hashlib.blake2b(
            repr((value.get("time_us"), value.get("sequence"), [identity(n) for n in raw])).encode(), digest_size=8
        ).hexdigest()
    anonymous = f"{'temporal response' if temporal else 'anonymous activation'} {fingerprint}"
    return {
        "schema": CHAT_VERSION,
        "text": " · ".join(readable) or anonymous,
        "anonymous_text": anonymous,
        "readable_labels": readable,
        "node_ids": [n["id"] for n in nodes],
        "nodes": nodes,
        "active_count": active_count,
        "item_count": len(rows),
        "offset": offset,
        "next": offset + len(nodes) if offset + len(nodes) < len(rows) else None,
        "truncated": offset > 0 or len(nodes) < len(rows),
        "scope": scope,
        "order": "recorded-scientific-ranking" if temporal and scope == "candidates" else order,
        "semantic_reply": False,
        **(
            {"ranking_time_us": value.get("ranking_time_us"), "ranking": "end-activation"}
            if value.get("analysis_schema")
            else {}
        ),
    }
