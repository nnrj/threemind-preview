import unittest
from lab.tools.teaching_clock import TeachingClock


class TeachingClockTests(unittest.TestCase):
    def test_elapsed_time_and_no_semantic_fields(self):
        clock = TeachingClock()
        self.assertEqual(clock.sample(0)["light_levels"], [1, 0, 0, 0])
        self.assertEqual(clock.sample(1)["light_levels"], [0, 1, 0, 0])
        self.assertEqual(clock.sample(4)["light_levels"], clock.sample(0)["light_levels"])
        self.assertEqual(clock.frame(clock.sample(4)), clock.frame(clock.sample(0)))
        shifted = TeachingClock(origin_s=100)
        self.assertEqual(shifted.frame(shifted.sample(101)), clock.frame(clock.sample(1)))
        faster = TeachingClock(period_s=2)
        self.assertEqual(faster.frame(faster.sample(0.5)), clock.frame(clock.sample(1)))
        observation = clock.sample(1)
        observation["answer"] = "red ball"
        self.assertEqual(clock.frame(observation), clock.frame(clock.sample(1)))


if __name__ == "__main__":
    unittest.main()
