import copy, unittest, uuid
from pathlib import Path
import torch
from threemind_runtime.graph_observation import NODE_FIELDS, EDGE_FIELDS, GraphActivityStream, VERSION
from threemind_transformer.graph_expression import GraphExpressionConfig, GraphExpression, pack_graphs, save, load


def process():
    def node(i, c, v):
        return {"id": str(i), "channel": c, "values": [v] + [0.1] * (len(NODE_FIELDS) - 1)}

    edge = {"source": "1", "target": "2", "values": [0.3] + [0] * (len(EDGE_FIELDS) - 1)}
    return {
        "schema": VERSION,
        "node_fields": list(NODE_FIELDS),
        "edge_fields": list(EDGE_FIELDS),
        "start_us": "100",
        "end_us": "20100",
        "frames": [
            {"time_us": "100", "nodes": [node(1, 123, 0.2), node(2, 987, 0.3)], "edges": [copy.deepcopy(edge)]},
            {
                "time_us": "20100",
                "nodes": [node(1, 123, 0.1), node(2, 987, 0.5), node(9, 419430, 0.7)],
                "edges": [copy.deepcopy(edge)],
            },
        ],
    }


class GraphExpressionTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        self.cfg = GraphExpressionConfig(width=32, heads=4, queries=2, decoder_layers=1)
        self.model = GraphExpression(self.cfg).eval()

    def test_permutation_and_local_id_invariance(self):
        a = process()
        b = copy.deepcopy(a)
        for f in b["frames"]:
            f["nodes"].reverse()
            for n in f["nodes"]:
                n["id"] = "alias-" + n["id"]
            for e in f["edges"]:
                e["source"] = "alias-" + e["source"]
                e["target"] = "alias-" + e["target"]
        with torch.no_grad():
            x, p = self.model.encode(pack_graphs([a], self.cfg))
            y, q = self.model.encode(pack_graphs([b], self.cfg))
            ids = torch.tensor([[256, 10]])
            # Memory tokens may permute; generated logits must not.
            x = self.model.logits(ids, x, p)
            y = self.model.logits(ids, y, q)
        torch.testing.assert_close(x, y, rtol=1e-5, atol=1e-5)

    def test_original_version_remains_loadable(self):
        from dataclasses import replace

        cfg = replace(self.cfg, schema="threemind.graph-expression/1")
        old = GraphExpression(cfg)
        self.assertEqual(old.config.schema, "threemind.graph-expression/1")
        self.assertFalse(hasattr(old, "identity"))
        self.assertEqual(len(old.decode([process()], maximum_tokens=4)), 1)

    def test_graph_and_timing_are_used(self):
        a = process()
        b = copy.deepcopy(a)
        c = copy.deepcopy(a)
        for f in b["frames"]:
            f["edges"] = []
        c["end_us"] = "10000100"
        c["frames"][-1]["time_us"] = c["end_us"]
        with torch.no_grad():
            x, _ = self.model.encode(pack_graphs([a], self.cfg))
            y, _ = self.model.encode(pack_graphs([b], self.cfg))
            z, _ = self.model.encode(pack_graphs([c], self.cfg))
        self.assertGreater(float((x - y).abs().max()), 1e-5)
        self.assertGreater(float((x - z).abs().max()), 1e-5)

    def test_growth_empty_frame_and_roundtrip(self):
        a = process()
        a["frames"][0]["nodes"] = []
        a["frames"][0]["edges"] = []
        expected = self.model.decode([a], maximum_tokens=4)
        root = Path(__file__).resolve().parents[1] / ".work"
        root.mkdir(exist_ok=True)
        folder = root / ("test-graph-" + uuid.uuid4().hex)
        folder.mkdir()
        path = folder / "reader.safetensors"
        try:
            save(self.model, path, {"test": True})
            restored, _ = load(path)
            self.assertEqual(restored.decode([a], maximum_tokens=4), expected)
        finally:
            path.unlink(missing_ok=True)
            folder.rmdir()

    def test_no_input_mutation_no_hidden_labels_and_limits(self):
        a = process()
        original = copy.deepcopy(a)
        pack_graphs([a], self.cfg)
        self.assertEqual(a, original)
        a["answer"] = "x"
        with self.assertRaises(ValueError):
            pack_graphs([a], self.cfg)
        a = process()
        a["frames"][1]["nodes"][0]["values"][0] = float("nan")
        with self.assertRaises(ValueError):
            pack_graphs([a], self.cfg)
        with self.assertRaises(ValueError):
            pack_graphs([process()], GraphExpressionConfig(maximum_nodes=2))

    def test_actual_training_gradient_and_stream_copy(self):
        a = process()
        loss = self.model.loss(pack_graphs([a], self.cfg), ["甲。"])
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(float(self.model.edge[0].weight.grad.abs().sum()), 0)
        stream = GraphActivityStream()
        received = []
        stream.subscribe("mutate", lambda f: f["nodes"].clear())
        stream.subscribe("evidence", received.append)
        stream.publish(a["frames"][0])
        self.assertEqual(received[0], a["frames"][0])
        self.assertEqual(len(a["frames"][0]["nodes"]), 2)


if __name__ == "__main__":
    unittest.main()
