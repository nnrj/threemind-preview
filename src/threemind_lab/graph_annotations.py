"""Bounded external carrier labels. Never inserted into the Core state."""

import heapq


def annotations(db, run_id, revision, time_us, nodes, maximum):
    selected = heapq.nsmallest(maximum, nodes, key=lambda n: (-n["activation"], n["id"]))
    channels = [str(n["channel"]) for n in selected if "channel" in n]
    if not channels:
        return {"annotations": {}, "annotation_scope": "no selected channels"}
    rows = db.execute(
        """WITH recent AS MATERIALIZED (
            SELECT labels FROM input_frames
            WHERE run_id=%s AND status='delivered' AND delivered_revision<=%s AND delivered_time_us<=%s
              AND labels<>'{}'::jsonb AND labels ?| %s
            ORDER BY delivered_revision DESC,envelope_id,frame_index DESC LIMIT 256
        ), pairs AS (
            SELECT p.key AS channel,left(v.value,60) AS label FROM recent r
            CROSS JOIN LATERAL jsonb_each(r.labels) p
            CROSS JOIN LATERAL jsonb_array_elements_text(p.value) WITH ORDINALITY v(value,ordinal)
            WHERE p.key=ANY(%s) AND v.ordinal<=8
        )
        SELECT channel,(array_agg(DISTINCT label ORDER BY label))[1:8] AS labels FROM pairs GROUP BY channel""",
        (run_id, revision, time_us, channels, channels),
    ).fetchall()
    by_channel = {row["channel"]: row["labels"] for row in rows}
    return {
        "annotations": {
            str(n["id"]): by_channel[str(n["channel"])] for n in selected if str(n.get("channel")) in by_channel
        },
        "annotation_scope": "external channel annotations from at most 256 recent matching delivered carriers; at most 8 labels per channel, not semantics or proof every channel passed competition",
        "annotation_node_limit": maximum,
        "annotation_revision": revision,
    }
