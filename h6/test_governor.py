import unittest

from governor import Governor


def sample(t, temp=55.0, busy=90.0, trusted=True, active=True,
           gpu="GM107", driver="nouveau"):
    return dict(t_s=t, temp_c=temp, busy_pct=busy,
                busy_trusted=trusted, game_active=active,
                gpu=gpu, driver=driver)


class GovernorTests(unittest.TestCase):
    def test_sustained_load_boosts_only_after_dwell(self):
        gov = Governor()
        self.assertEqual(gov.step(sample(0))["proposed_pstate"], "07")
        self.assertEqual(gov.step(sample(9))["proposed_pstate"], "07")
        result = gov.step(sample(10))
        self.assertEqual(result["proposed_pstate"], "0f")
        self.assertEqual(result["reason"], "sustained_demand")
        self.assertIs(result["applied_to_hardware"], False)

    def test_thermal_down_immediate(self):
        gov = Governor()
        gov.step(sample(0))
        gov.step(sample(10))
        result = gov.step(sample(11, temp=80))
        self.assertEqual(result["proposed_pstate"], "07")
        self.assertEqual(result["reason"], "thermal_down")

    def test_missing_temperature_fails_closed(self):
        gov = Governor()
        gov.step(sample(0))
        gov.step(sample(10))
        self.assertEqual(gov.step(sample(11, temp=None))["proposed_pstate"], "07")

    def test_untrusted_busy_never_boosts(self):
        gov = Governor()
        for t in (0, 10, 30):
            self.assertEqual(gov.step(sample(t, busy=0, trusted=False))["proposed_pstate"], "07")

    def test_driver_guard(self):
        gov = Governor()
        gov.step(sample(0, driver="nvidia"))
        self.assertEqual(gov.step(sample(11, driver="nvidia"))["proposed_pstate"], "07")

    def test_gpu_guard(self):
        gov = Governor()
        gov.step(sample(0, gpu="GK107"))
        self.assertEqual(gov.step(sample(11, gpu="GK107"))["proposed_pstate"], "07")

    def test_idle_down_dwell_and_cooldown(self):
        gov = Governor()
        gov.step(sample(0))
        gov.step(sample(10))
        self.assertEqual(gov.step(sample(15, busy=10))["proposed_pstate"], "0f")
        self.assertEqual(gov.step(sample(29, busy=10))["proposed_pstate"], "0f")
        self.assertEqual(gov.step(sample(30, busy=10))["proposed_pstate"], "07")

    def test_no_boost_when_temp_above_boost_gate(self):
        gov = Governor()
        gov.step(sample(0, temp=70))
        self.assertEqual(gov.step(sample(12, temp=70))["proposed_pstate"], "07")

    def test_hysteresis_hold(self):
        gov = Governor()
        gov.step(sample(0))
        gov.step(sample(10))
        result = gov.step(sample(15, busy=50))
        self.assertEqual(result["proposed_pstate"], "0f")
        self.assertEqual(result["reason"], "hysteresis_hold")

    def test_unordered_samples_rejected(self):
        gov = Governor()
        gov.step(sample(10))
        with self.assertRaises(ValueError):
            gov.step(sample(9))

    def test_invalid_busy_fails_closed(self):
        gov = Governor()
        gov.step(sample(0, busy=float("nan")))
        self.assertEqual(gov.step(sample(12, busy=102))["proposed_pstate"], "07")

    def test_never_write_to_hardware(self):
        gov = Governor()
        for t in (0, 10, 20, 30):
            self.assertFalse(gov.step(sample(t))["applied_to_hardware"])


if __name__ == "__main__":
    unittest.main()
