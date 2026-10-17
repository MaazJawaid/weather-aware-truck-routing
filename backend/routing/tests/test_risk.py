from django.test import SimpleTestCase

from routing.services.risk import apply_wind_load, classify, merge_risk, rain_band, snow_band, wind_band


class WindBandTests(SimpleTestCase):
    def test_printed_edges(self):
        cases = {
            24.9: "low",
            25: "moderate",
            34: "moderate",
            34.9: "moderate",
            35: "high",
            44: "high",
            44.9: "high",
            45: "severe",
            54: "severe",
            54.9: "severe",
            55: "no_travel",
            70: "no_travel",
        }
        for mph, expected in cases.items():
            self.assertEqual(wind_band(mph), expected, mph)


class RainBandTests(SimpleTestCase):
    def test_overlapping_edge_uses_the_worse_band(self):
        cases = {
            0.0: "low",
            0.09: "low",
            0.099: "low",
            0.10: "moderate",
            0.249: "moderate",
            0.25: "high",
            0.49: "high",
            0.50: "severe",
            1.0: "severe",
            1.01: "no_travel",
        }
        for rate, expected in cases.items():
            self.assertEqual(rain_band(rate), expected, rate)


class SnowBandTests(SimpleTestCase):
    def test_overlapping_edge_uses_the_worse_band(self):
        cases = {
            0.49: "low",
            0.5: "moderate",
            0.99: "moderate",
            1.0: "high",
            1.99: "high",
            2.0: "severe",
            3.0: "severe",
            3.01: "no_travel",
        }
        for rate, expected in cases.items():
            self.assertEqual(snow_band(rate), expected, rate)


class LoadRuleTests(SimpleTestCase):
    def test_cutovers_are_strict(self):
        self.assertEqual(apply_wind_load(54, 30_000, "severe")[0], "severe")
        self.assertEqual(apply_wind_load(54, 30_001, "severe")[0], "no_travel")
        self.assertEqual(apply_wind_load(45, 30_000, "severe")[0], "severe")
        self.assertEqual(apply_wind_load(45, 30_001, "severe")[0], "no_travel")
        self.assertEqual(apply_wind_load(35, 40_000, "high")[0], "high")
        self.assertEqual(apply_wind_load(35, 40_001, "high")[0], "severe")
        self.assertEqual(apply_wind_load(44.9, 50_000, "high")[0], "severe")
        self.assertEqual(apply_wind_load(34.9, 80_000, "moderate")[0], "moderate")
        self.assertEqual(apply_wind_load(55, 1, "no_travel")[0], "no_travel")
        self.assertEqual(apply_wind_load(20, 80_000, "low")[0], "low")

    def test_worst_condition_wins_and_load_does_not_change_rain(self):
        heavy = classify(10, 0.6, 0.0, 80_000)
        self.assertEqual(heavy["risk"], "severe")
        self.assertIn("rain:severe", heavy["rules"])

        upgraded = classify(40, 0.0, 0.0, 45_000)
        self.assertEqual(upgraded["risk"], "severe")
        self.assertIn("load:35-44mph>40000lb→severe", upgraded["rules"])

        closed = classify(50, 0.0, 0.0, 35_000)
        self.assertEqual(closed["risk"], "no_travel")

        mixed = classify(10, 0.3, 0.2, 10_000)
        self.assertEqual(mixed["risk"], "high")

    def test_missing_forecast_is_unknown(self):
        missing = classify(None, None, None, 10_000)
        self.assertEqual(missing["risk"], "unknown")
        self.assertEqual(missing["wind_mph"], None)


class MergeRiskTests(SimpleTestCase):
    def test_unknown_does_not_count_as_low(self):
        self.assertEqual(merge_risk("unknown", "low"), "unknown")
        self.assertEqual(merge_risk("unknown", "moderate"), "unknown")
        self.assertEqual(merge_risk("unknown", "severe"), "severe")
        self.assertEqual(merge_risk("low", "severe"), "severe")
        self.assertEqual(merge_risk("unknown", "unknown"), "unknown")
