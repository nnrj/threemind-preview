import copy, importlib.util, unittest
from pathlib import Path
from threemind_transformer.local_activity import local_process

path = Path(__file__).resolve().parents[1] / "lab/explorations/2026-10-05-graph-expression/local_activity.py"
spec = importlib.util.spec_from_file_location("local_reader_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LocalGraphTests(unittest.TestCase):
    def test_participation_not_rank_or_historical_weight(self):
        def node(i, a, inh):
            return dict(
                id=i,
                channel=i,
                activation=a,
                inhibition=inh,
                direct=0,
                associative=0,
                generated_inhibition=0,
                pending_inhibition=0,
                touches=999999,
                support=1,
            )

        p = {
            "start_us": "0",
            "end_us": "20",
            "trajectory": [
                {"time_us": "0", "nodes": [node(1, 0.1, 0.3), node(2, 0, 0.1), node(3, 0, 0.8)]},
                {"time_us": "10", "nodes": [node(1, 0.00001, 0.2), node(2, 0, 0.2), node(3, 0, 0.7)]},
                {"time_us": "20", "nodes": [node(1, 0, 0.1), node(2, 0, 0.1), node(3, 0, 0.6)]},
            ],
        }
        before = copy.deepcopy(p)
        q = module.local_process(p, samples=3)
        self.assertEqual(local_process(p, samples=3), q)
        self.assertEqual(p, before)
        self.assertEqual([n["channel"] for n in q["frames"][0]["nodes"]], [1, 2])
        self.assertEqual(q["frames"][1]["nodes"][0]["values"][0], 0.00001)
        self.assertEqual(q["frames"][-1]["nodes"][0]["values"][0], 0)
        self.assertNotIn("touches", q["node_fields"])
        self.assertFalse(any(f["edges"] for f in q["frames"]))

    def test_malformed_measurements_not_hidden_by_selection(self):
        def node(inhibition):
            return dict(
                id=1,
                channel=1,
                activation=0,
                inhibition=inhibition,
                direct=0,
                associative=0,
                generated_inhibition=0,
                pending_inhibition=0,
            )

        p = {
            "start_us": "0",
            "end_us": "1",
            "trajectory": [{"time_us": "0", "nodes": [node(float("nan"))]}, {"time_us": "1", "nodes": [node(0)]}],
        }
        with self.assertRaises(ValueError):
            local_process(p)
        p["trajectory"][0]["nodes"] = [node(0)]
        p["trajectory"][1]["time_us"] = "0"
        with self.assertRaises(ValueError):
            local_process(p)


if __name__ == "__main__":
    unittest.main()
