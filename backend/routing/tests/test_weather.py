from django.test import SimpleTestCase

from routing.services.weather import forecasts_for_request


def _block(latitude, longitude, wind):
    return {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": {
            "time": ["2026-10-17T12:00"],
            "wind_speed_10m": [wind],
            "rain": [0],
            "snowfall": [0],
        },
    }


class ForecastKeyTests(SimpleTestCase):
    def test_grid_point_is_stored_under_the_requested_coordinate(self):
        requested = [(41.88, -87.63), (42.33, -83.05)]
        # These are the grid points Open-Meteo actually returned for that pair.
        payload = [
            _block(41.879498, -87.64974, 12.0),
            _block(42.324814, -83.06703, 9.4),
        ]
        parsed = forecasts_for_request(requested, payload)

        self.assertEqual(list(parsed), requested)
        self.assertEqual(parsed[(41.88, -87.63)][0].wind_mph, 12.0)
        self.assertEqual(parsed[(42.33, -83.05)][0].wind_mph, 9.4)
        self.assertNotIn((41.88, -87.65), parsed)
        self.assertNotIn((42.32, -83.07), parsed)

    def test_a_single_object_stays_on_the_one_requested_point(self):
        parsed = forecasts_for_request([(41.88, -87.63)], _block(41.879498, -87.64974, 8.0))
        self.assertEqual(parsed[(41.88, -87.63)][0].wind_mph, 8.0)

    def test_a_short_response_is_not_shifted_onto_later_points(self):
        parsed = forecasts_for_request(
            [(41.88, -87.63), (42.33, -83.05)],
            [_block(41.879498, -87.64974, 12.0)],
        )
        self.assertEqual(parsed, {})

    def test_a_missing_hourly_block_does_not_move_the_next_point(self):
        parsed = forecasts_for_request(
            [(41.88, -87.63), (42.33, -83.05)],
            [{"error": True, "reason": "missing"}, _block(42.324814, -83.06703, 9.4)],
        )
        self.assertEqual(parsed[(41.88, -87.63)], [])
        self.assertEqual(parsed[(42.33, -83.05)][0].wind_mph, 9.4)
