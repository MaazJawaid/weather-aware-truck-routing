from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from routing.services.analyze import analyze_trip
from routing.services.directions import parse_directions_payload, tonnes_from_pounds
from routing.services.errors import TripError
from routing.services.geocoding import geocode, parse_geocode_payload
from routing.services.weather import Hour, hours_from_block
from routing.views import AnalyzeView, HealthView


class ParserTests(SimpleTestCase):
    def test_geocode_payload_reads_lon_lat(self):
        hit = parse_geocode_payload(
            {
                "features": [
                    {
                        "geometry": {"coordinates": [-87.6, 41.8]},
                        "properties": {"label": "Chicago"},
                    }
                ]
            }
        )
        self.assertEqual(hit["lat"], 41.8)
        self.assertEqual(hit["lon"], -87.6)
        self.assertIsNone(parse_geocode_payload({"features": []}))

    def test_directions_payload_keeps_three_routes_in_lat_lon(self):
        features = []
        for index in range(4):
            features.append(
                {
                    "geometry": {"coordinates": [[-87.6, 41.8], [-83.0, 42.3]]},
                    "properties": {
                        "summary": {"distance": 280 + index, "duration": 18_000},
                        "segments": [{"steps": [{"distance": 280 + index, "duration": 18_000}]}],
                    },
                }
            )
        routes = parse_directions_payload({"features": features})
        self.assertEqual(len(routes), 3)
        self.assertEqual(routes[0]["coords"][0], (41.8, -87.6))

    def test_forecast_units_convert_to_inches(self):
        hours = hours_from_block(
            {
                "hourly": {
                    "time": ["2026-10-18T15:00"],
                    "wind_speed_10m": [12.5],
                    "rain": [25.4],
                    "snowfall": [2.54],
                }
            }
        )
        self.assertEqual(hours[0].wind_mph, 12.5)
        self.assertAlmostEqual(hours[0].rain_in_hr, 1.0)
        self.assertAlmostEqual(hours[0].snow_in_hr, 1.0)

    def test_pounds_become_metric_tonnes(self):
        self.assertAlmostEqual(tonnes_from_pounds(35_000), 15.88, places=2)


class CorridorTests(SimpleTestCase):
    def test_points_stay_inside_the_buffer(self):
        from routing.services.corridor import build_corridor
        from routing.services.geo import haversine_miles

        line = [(41.0, -88.0 + offset * 0.05) for offset in range(21)]
        points = build_corridor([line], buffer_miles=25, spacing_miles=16)
        self.assertGreater(len(points), 0)
        self.assertLessEqual(len(points), 250)
        for lat, lon in points:
            nearest = min(haversine_miles(lat, lon, sample[0], sample[1]) for sample in line)
            self.assertLessEqual(nearest, 25.5)
        self.assertTrue(all(abs(lat - 45) > 1 for lat, _lon in points))


@override_settings(OPENROUTESERVICE_API_KEY="")
class MissingKeyTests(SimpleTestCase):
    def test_geocode_reports_a_missing_key(self):
        with self.assertRaises(TripError) as raised:
            geocode("Chicago, IL")
        self.assertEqual(raised.exception.status, 500)


class AnalyzePipelineTests(SimpleTestCase):
    def test_shorter_route_loses_when_wind_closes_it(self):
        start = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)

        def fake_geocode(text):
            if "Detroit" in text:
                return {"lat": 42.33, "lon": -83.05, "label": text}
            return {"lat": 41.88, "lon": -87.63, "label": text}

        def fake_routes(_origin, _destination, _load):
            return [
                {
                    "distance_mi": 100,
                    "duration_seconds": 7200,
                    "coords": [(41.0, -88.0), (41.0, -87.0)],
                    "steps": [{"distance": 100, "duration": 7200}],
                },
                {
                    "distance_mi": 80,
                    "duration_seconds": 5000,
                    "coords": [(42.2, -88.0), (42.2, -87.0)],
                    "steps": [{"distance": 80, "duration": 5000}],
                },
            ]

        def fake_forecasts(coords):
            found = {}
            for lat, lon in coords:
                key = (round(lat, 2), round(lon, 2))
                wind = 50.0 if key[0] >= 42 else 10.0
                found[key] = [
                    Hour(
                        time=start + timedelta(hours=offset),
                        wind_mph=wind,
                        rain_in_hr=0.0,
                        snow_in_hr=0.0,
                    )
                    for offset in range(80)
                ]
            return found

        with (
            patch("routing.services.analyze.geocode", side_effect=fake_geocode),
            patch("routing.services.analyze.fetch_routes", side_effect=fake_routes),
            patch("routing.services.analyze.fetch_forecasts", side_effect=fake_forecasts),
        ):
            payload = analyze_trip(
                origin="Chicago, IL",
                destination="Detroit, MI",
                departure=datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc),
                load_lb=35_000,
                sample_miles=25,
                now=start,
            )

        self.assertEqual(payload["recommended_route_id"], "route_1")
        self.assertFalse(payload["no_fully_safe_route"])
        self.assertIn("2 routes", payload["notice"])
        self.assertEqual(len(payload["heatmap"]["hours"]), 49)
        self.assertEqual(len(payload["heatmap"]["points"][0]["risks"]), 49)
        closed = next(route for route in payload["routes"] if route["id"] == "route_2")
        self.assertGreater(closed["summary"]["no_travel_miles"], 0)
        calm = next(route for route in payload["routes"] if route["id"] == "route_1")
        self.assertEqual(calm["summary"]["no_travel_miles"], 0)
        self.assertEqual(calm["checkpoints"][0]["risk"], "low")
        self.assertTrue(calm["checkpoints"][0]["eta"].endswith("Z"))


class ViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_health(self):
        request = self.factory.get("/api/v1/health")
        response = HealthView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_rejects_a_bad_interval_and_a_naive_time(self):
        request = self.factory.post(
            "/api/v1/analyze",
            {
                "origin": "Chicago, IL",
                "destination": "Detroit, MI",
                "departure": "2026-10-18T08:00:00",
                "load_lb": 35000,
                "sample_miles": 15,
            },
            format="json",
        )
        response = AnalyzeView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("sample_miles", response.data["detail"])

    @patch("routing.views.analyze_trip", return_value={"routes": []})
    def test_returns_the_analysis(self, _analyze):
        request = self.factory.post(
            "/api/v1/analyze",
            {
                "origin": "Chicago, IL",
                "destination": "Detroit, MI",
                "departure": "2026-10-18T15:00:00Z",
                "load_lb": 35000,
                "sample_miles": 25,
            },
            format="json",
        )
        response = AnalyzeView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["routes"], [])
