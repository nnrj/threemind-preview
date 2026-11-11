import unittest

from threemind_runtime.activity_stream import RawActivityStream


class RawActivityTests(unittest.TestCase):
    def test_complete_isolated_transport(self):
        stream = RawActivityStream()
        received = []
        stream.subscribe("bad-consumer", lambda f: f["nodes"].clear())
        stream.subscribe("evidence", received.append)
        nodes = [{"id": 1, "channel": 7, "activation": 0, "inhibition": .9, "trace": .1}]
        stream.publish({"time_us": 17, "nodes": nodes})
        self.assertEqual(received[0]["nodes"], nodes)
        self.assertEqual(received[0]["time_us"], "17")
        self.assertEqual(len(nodes), 1)

    def test_failure_is_not_silently_dropped(self):
        stream = RawActivityStream()
        def fail(_):
            raise RuntimeError("consumer failed")
        stream.subscribe("evidence", fail)
        with self.assertRaises(RuntimeError):
            stream.publish({"time_us": 0, "nodes": []})
        self.assertEqual(stream.published, 0)

    def test_sample_does_not_advance(self):
        class Engine:
            time_us = 10
            def observation_nodes(self):
                return [{"channel": 1, "activation": .2, "inhibition": .3}]
        engine = Engine()
        received = []
        stream = RawActivityStream()
        stream.subscribe("reader", received.append)
        stream.sample(engine)
        self.assertEqual(engine.time_us, 10)
        self.assertEqual(received[0]["nodes"][0]["inhibition"], .3)


if __name__ == "__main__":
    unittest.main()
