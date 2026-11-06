import random
from statistics import mean

import pandas as pd
from django.test import SimpleTestCase
from scipy.stats import theilslopes

from core import analytics as an

# The planted students (same percentages as seed_demo.py)
PLANTED = {
    "01 Steady high": [78, 80, 76, 79, 81, 80],
    "02 Improving": [45, 48, 52, 57, 61, 66],
    "03 Declining": [82, 78, 73, 67, 60, 52],
    "04 Persistently low": [31, 33, 29, 32, 30, 31],
    "05 One bad day": [70, 72, 71, 73, 40, 72],
    "06 Insufficient": [62, 60, 64],
    "07 After extra class": [72, 66, 58, 50, 58, 67],
    "08 Stable middle": [55, 57, 54, 56, 55, 56],
}


class MethodsMatchLibraries(SimpleTestCase):
    def test_theil_sen_matches_scipy(self):
        random.seed(1)
        for _ in range(200):
            n = random.randint(2, 12)
            y = [random.uniform(0, 100) for _ in range(n)]
            expected = theilslopes(y, list(range(n)))[0]
            self.assertAlmostEqual(an.theil_sen_slope(y), expected, places=9)

    def test_ewma_matches_pandas(self):
        random.seed(2)
        for alpha in (0.1, 0.3, 0.5):
            for _ in range(100):
                y = [random.uniform(0, 100) for _ in range(random.randint(1, 12))]
                expected = pd.Series(y).ewm(alpha=alpha, adjust=False).mean().tolist()
                for a, b in zip(an.ewma(y, alpha), expected):
                    self.assertAlmostEqual(a, b, places=9)

    def test_known_slope(self):
        self.assertEqual(an.theil_sen_slope([10, 12, 14, 16]), 2)
        self.assertIsNone(an.theil_sen_slope([50]))


class PlantedStudents(SimpleTestCase):
    def status(self, key, values=None):
        return an.classify(values or PLANTED[key])["status"]

    def test_declining_needs_attention(self):
        self.assertEqual(self.status("03 Declining"), an.NEEDS_ATTENTION)

    def test_persistently_low_is_found(self):
        self.assertEqual(self.status("04 Persistently low"), an.PERSISTENTLY_LOW)

    def test_one_bad_day_is_not_flagged(self):
        self.assertEqual(self.status("05 One bad day"), an.STABLE)

    def test_too_little_data(self):
        self.assertEqual(self.status("06 Insufficient"), an.INSUFFICIENT)

    def test_stable_students(self):
        for key in ("01 Steady high", "02 Improving", "08 Stable middle"):
            self.assertEqual(self.status(key), an.STABLE, key)

    def test_flagged_before_intervention_then_stable_after(self):
        values = PLANTED["07 After extra class"]
        self.assertEqual(an.classify(values[:4])["status"], an.NEEDS_ATTENTION)
        self.assertEqual(an.classify(values)["status"], an.STABLE)

    def test_baseline_excludes_latest_score(self):
        y = [60, 60, 60, 60, 20]
        result = an.classify(y)
        self.assertAlmostEqual(result["ewma_previous"], 60)   # not pulled down by the 20

    def test_settings_are_configurable(self):
        y = PLANTED["04 Persistently low"]
        self.assertEqual(an.classify(y, low_score_threshold=20)["status"], an.STABLE)
        self.assertEqual(an.classify(y, min_assessments=10)["status"], an.INSUFFICIENT)


class Recovery(SimpleTestCase):
    def test_class_adjusted_recovery(self):
        n_tests = 6
        class_means = []
        for i in range(n_tests):
            class_means.append(mean(v[i] for v in PLANTED.values() if len(v) > i))
        r = an.recovery(PLANTED["07 After extra class"], class_means, start_index=4, window=2)
        self.assertTrue(r["ready"])
        self.assertAlmostEqual(r["pre"], 54)
        self.assertAlmostEqual(r["post"], 62.5)
        self.assertAlmostEqual(r["change"], 8.5)
        self.assertAlmostEqual(r["adjusted"], r["change"] - r["class_change"])

    def test_not_enough_scores_after(self):
        r = an.recovery([50, 50, 50, 50, 60], [50] * 5, start_index=4, window=2)
        self.assertFalse(r["ready"])

    def test_no_improvement_label(self):
        r = an.recovery([60, 60, 50, 50], [60, 60, 60, 60], start_index=2, window=2)
        self.assertEqual(r["label"], "Score did not improve after the intervention.")