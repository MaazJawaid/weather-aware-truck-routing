from django.test import SimpleTestCase

from routing.services.sampling import duration_at_mile, sample_route, sample_targets


class SamplingTests(SimpleTestCase):
    def test_targets_include_the_end_of_a_short_trip(self):
        self.assertEqual(sample_targets(12, 25), [0.0, 12])
        self.assertEqual(sample_targets(100, 25), [0.0, 25, 50, 75, 100])

    def test_even_spacing_uses_road_miles_and_a_flat_profile(self):
        coords = [(40.0, -100.0 + index * 0.1) for index in range(11)]
        points = sample_route(coords, distance_mi=100, duration_seconds=4000, interval_mi=25)
        self.assertEqual([point.mile for point in points], [0.0, 25.0, 50.0, 75.0, 100.0])
        self.assertEqual(
            [point.eta_offset_seconds for point in points],
            [0.0, 1000.0, 2000.0, 3000.0, 4000.0],
        )
        self.assertEqual(points[0].lon, coords[0][1])
        self.assertEqual(points[-1].lon, coords[-1][1])
        self.assertLess(points[0].lon, points[2].lon)
        self.assertLess(points[2].lon, points[-1].lon)

    def test_step_profile_is_not_a_flat_speed(self):
        table = [(0.0, 0.0), (40.0, 1000.0), (100.0, 6000.0)]
        self.assertAlmostEqual(duration_at_mile(table, 20), 500.0)
        self.assertAlmostEqual(duration_at_mile(table, 50), 1000 + (10 / 60) * 5000)

        coords = [(40.0, -100.0), (40.0, -99.0)]
        points = sample_route(
            coords,
            distance_mi=100,
            duration_seconds=6000,
            interval_mi=25,
            steps=[
                {"distance": 40, "duration": 1000},
                {"distance": 60, "duration": 5000},
            ],
        )
        by_mile = {point.mile: point.eta_offset_seconds for point in points}
        self.assertAlmostEqual(by_mile[50.0], 1833.3, places=1)
        self.assertEqual(by_mile[100.0], 6000.0)
