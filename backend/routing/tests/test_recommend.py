from django.test import SimpleTestCase

from routing.services.recommend import build_segments, rank_routes, summarize_segments


def _route(route_id, no_travel, severe, high, average, duration, unknown=0):
    return {
        "id": route_id,
        "summary": {
            "no_travel_miles": no_travel,
            "severe_miles": severe,
            "high_miles": high,
            "unknown_miles": unknown,
            "average_risk": average,
            "duration_seconds": duration,
        },
    }


class SegmentTests(SimpleTestCase):
    def test_segment_takes_the_worse_endpoint(self):
        checkpoints = [
            {"vertex": 0, "mile": 0, "risk": "low"},
            {"vertex": 4, "mile": 25, "risk": "severe"},
            {"vertex": 8, "mile": 50, "risk": "low"},
        ]
        segments = build_segments(checkpoints)
        summary = summarize_segments(segments, 50, 3600)
        self.assertEqual(summary["severe_miles"], 50.0)
        self.assertEqual(summary["low_miles"], 0.0)
        self.assertEqual(summary["average_risk"], 4.0)

    def test_unknown_miles_stay_out_of_the_low_bucket(self):
        checkpoints = [
            {"vertex": 0, "mile": 0, "risk": "unknown"},
            {"vertex": 2, "mile": 10, "risk": "low"},
            {"vertex": 4, "mile": 20, "risk": "severe"},
        ]
        summary = summarize_segments(build_segments(checkpoints), 20, 1000)
        self.assertEqual(summary["unknown_miles"], 10.0)
        self.assertEqual(summary["severe_miles"], 10.0)
        self.assertEqual(summary["low_miles"], 0.0)
        self.assertEqual(summary["average_risk"], 4.0)


class RankTests(SimpleTestCase):
    def test_four_route_order_follows_the_brief(self):
        ordered = rank_routes(
            [
                _route("fast_but_closed", 5, 0, 0, 1.0, 10),
                _route("severe", 0, 20, 0, 1.0, 10),
                _route("high", 0, 5, 30, 1.0, 10),
                _route("winner", 0, 5, 10, 2.5, 400),
            ]
        )
        self.assertEqual([route["id"] for route in ordered], ["winner", "high", "severe", "fast_but_closed"])

    def test_average_beats_a_shorter_time_and_time_breaks_ties(self):
        ordered = rank_routes(
            [
                _route("slower_cleaner", 0, 0, 0, 1.2, 800),
                _route("faster_dirtier", 0, 0, 0, 2.0, 100),
                _route("same_risk_faster", 0, 0, 0, 1.2, 300),
            ]
        )
        self.assertEqual(
            [route["id"] for route in ordered],
            ["same_risk_faster", "slower_cleaner", "faster_dirtier"],
        )

    def test_unknown_miles_do_not_outrank_a_known_route(self):
        ordered = rank_routes(
            [
                _route("missing", 0, 0, 0, 1.0, 100, unknown=40),
                _route("known", 0, 0, 0, 1.5, 400),
            ]
        )
        self.assertEqual(ordered[0]["id"], "known")
