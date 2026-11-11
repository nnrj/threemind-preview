"""Read projections for the original frame runtime; never a Core state adapter."""

import json

from psycopg.types.json import Jsonb

PROJECTION = {
    "schema": "threemind.unified-observation/1",
    "aliases": {
        "channel": "package.state.receptor_index",
        "direct": "direct_touch",
        "associative": "associative_touch",
        "touches": "touch_count",
        "local_plasticity": "plasticity",
    },
    "identity_encoding": "Original identities; integers outside JavaScript's exact range are decimal strings.",
}


def display_identity(value):
    """Encode an observation identity without changing saved scientific state."""
    return str(value) if isinstance(value, int) and abs(value) > 2**53 - 1 else value


def node_view(node, channels=None):
    """Keep original fields and add the historical runtime's named read aliases."""
    return {
        **node,
        "id": display_identity(node["id"]),
        "channel": display_identity(channels.get(str(node["id"])) if channels is not None else node.get("channel")),
        "direct": node.get("direct_touch"),
        "associative": node.get("associative_touch"),
        "touches": node.get("touch_count"),
        "local_plasticity": node.get("plasticity"),
    }


def edge_view(edge):
    return {
        **edge,
        "source": display_identity(edge["source"]),
        "target": display_identity(edge["target"]),
        "touches": edge.get("touch_count"),
    }


def state_nodes(state, nodes=None):
    # Build the receptor inverse once when a checkpoint is already available.
    # Current projection queries read these registered values without decoding it.
    raw = state.get("package", {}).get("state", {})
    channels = {str(node): int(channel) for channel, node in raw.get("receptor_index", {}).items()}
    return [node_view(node, channels) for node in (state["nodes"] if nodes is None else nodes)]


def save(db, project, run_id, state):
    for table in ("nodes", "edges"):
        identities = []
        projected = state_nodes(state) if table == "nodes" else [edge_view(row) for row in state[table]]
        for row in projected:
            identity = str(row["id"]) if table == "nodes" else json.dumps([row["source"], row["target"]])
            identities.append(identity)
            db.execute(
                "INSERT INTO legacy_graph_rows(project_id,run_id,kind,identity,payload) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(run_id,kind,identity) DO UPDATE SET payload=EXCLUDED.payload "
                "WHERE legacy_graph_rows.payload IS DISTINCT FROM EXCLUDED.payload",
                (project, run_id, table, identity, Jsonb(row)),
            )
        db.execute(
            "DELETE FROM legacy_graph_rows WHERE run_id=%s AND kind=%s AND NOT(identity=ANY(%s::text[]))",
            (run_id, table, identities),
        )


def rows(db, run_id, table, *, after=0, limit=200, minimum=0.0, source=None):
    quantity = "activation" if table == "nodes" else "weight"
    return [
        (node_view(row["payload"]) if table == "nodes" else edge_view(row["payload"]))
        for row in db.execute(
            "SELECT payload FROM legacy_graph_rows WHERE run_id=%s AND kind=%s "
            "AND (payload->>%s)::double precision>=%s AND (%s::text IS NULL OR payload->>'source'=%s) "
            "ORDER BY identity OFFSET %s LIMIT %s",
            (run_id, table, quantity, minimum, source, source, after, limit),
        ).fetchall()
    ]


def graph(db, run_id, limit, edge_limit):
    nodes = rows(db, run_id, "nodes", limit=limit)
    ids = [str(node["id"]) for node in nodes]
    edges = [
        edge_view(row["payload"])
        for row in db.execute(
            "SELECT payload FROM legacy_graph_rows WHERE run_id=%s AND kind='edges' "
            "AND payload->>'source'=ANY(%s::text[]) AND payload->>'target'=ANY(%s::text[]) "
            "ORDER BY identity LIMIT %s",
            (run_id, ids, ids, edge_limit),
        ).fetchall()
    ]
    return nodes, edges
