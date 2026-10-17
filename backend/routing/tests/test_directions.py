from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from routing.services.directions import (
    alternative_limit_error,
    fetch_routes,
    merge_routes,
    route_request_body,
    within_alternative_limit,
)
from routing.services.errors import TripError


CHICAGO = {"lat": 41.8781, "lon": -87.6298}
DETROIT = {"lat": 42.3314, "lon": -83.0458}
NEARBY = {"lat": 41.8781, "lon": -87.6298}
ALSO_NEARBY = {"lat": 41.95, "lon": -87.70}


def _response(status, payload):
    class Response:
        status_code = status
        headers = {"content-type": "application/json"}

        def json(self):
            return payload

    return Response()


def _feature(distance, mid_lat):
    return {
        "geometry": {"coordinates": [[-87.6, 41.8], [-85.0, mid_lat], [-83.0, 42.3]]},
        "properties": {
            "summary": {"distance": distance, "duration": 10_000},
            "segments": [{"steps": [{"distance": distance, "duration": 10_000}]}],
        },
    }


@override_settings(OPENROUTESERVICE_API_KEY="test-key")
class DirectionRequestTests(SimpleTestCase):
    def test_long_trip_skips_the_alternative_algorithm(self):
        self.assertFalse(within_alternative_limit(CHICAGO, DETROIT))
        body = route_request_body(CHICAGO, DETROIT, 35_000, alternatives=False)
        self.assertNotIn("alternative_routes", body)

    def test_short_trip_asks_for_two_alternatives(self):
        self.assertTrue(within_alternative_limit(NEARBY, ALSO_NEARBY))
        body = route_request_body(NEARBY, ALSO_NEARBY, 35_000, alternatives=True)
        self.assertEqual(body["alternative_routes"]["target_count"], 2)

    def test_limit_error_retries_without_alternatives(self):
        rejected = _response(
            400,
            {
                "error": {
                    "message": (
                        "Request parameters exceed the server configuration limits. "
                        "The approximated route distance must not be greater than 100000.0 meters "
                        "for use with the alternative Routes algorithm."
                    )
                }
            },
        )
        accepted = _response(200, {"features": [_feature(40, 42.0)]})

        with patch("routing.services.directions.requests.post", side_effect=[rejected, accepted, accepted, accepted]) as post:
            routes = fetch_routes(NEARBY, ALSO_NEARBY, 35_000)

        self.assertEqual(len(routes), 1)
        self.assertNotIn("alternative_routes", post.call_args_list[1].kwargs["json"])
        self.assertTrue(alternative_limit_error(str(TripError("alternative 100000"))))

    def test_distinct_preferences_are_kept_and_duplicates_dropped(self):
        recommended = _response(200, {"features": [_feature(280, 42.0)]})
        fastest = _response(200, {"features": [_feature(280, 42.0)]})
        shortest = _response(200, {"features": [_feature(266, 40.4)]})

        with patch("routing.services.directions.requests.post", side_effect=[recommended, fastest, shortest]):
            routes = fetch_routes(CHICAGO, DETROIT, 35_000)

        self.assertEqual(len(routes), 2)
        self.assertEqual([route["distance_mi"] for route in routes], [280, 266])

    def test_merge_stops_at_three_distinct_routes(self):
        base = [{"coords": [(41.8, -87.6), (42.0, -85.0), (42.3, -83.0)], "distance_mi": 280}]
        incoming = [
            {"coords": [(41.8, -87.6), (40.4, -85.0), (42.3, -83.0)], "distance_mi": 266},
            {"coords": [(41.8, -87.6), (43.4, -85.0), (42.3, -83.0)], "distance_mi": 310},
            {"coords": [(41.8, -87.6), (39.0, -85.0), (42.3, -83.0)], "distance_mi": 340},
        ]
        self.assertEqual(len(merge_routes(base, incoming)), 3)
