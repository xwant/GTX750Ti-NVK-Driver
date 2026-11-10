import unittest
from autotune import build, decide

def record(a=1000, b=900, count=8):
    return dict(gpu="GM107", mesa_commit="mesa26.2.6", compiler_flags="h2-test",
                shader_sha256="shader", layout_sha256="layout",
                pairs=[dict(base_ns=a, h2_ns=b) for _ in range(count)])

class PolicyTests(unittest.TestCase):
    def test_clear_gain(self):
        self.assertEqual(decide(record())[1], "h2")
    def test_regression(self):
        self.assertEqual(decide(record(b=1100))[1], "base")
    def test_small_gain(self):
        self.assertEqual(decide(record(b=990))[1], "base")
    def test_too_few_pairs(self):
        self.assertEqual(decide(record(count=7))[1], "base")
    def test_invalid_measurement(self):
        r=record();r["pairs"][0]["h2_ns"]=0
        self.assertEqual(decide(r)[1], "base")
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            build([record(),record()])
    def test_non_gm107_rejected(self):
        r=record();r["gpu"]="TU102"
        with self.assertRaises(ValueError):
            decide(r)
    def test_key_includes_layout(self):
        a=record();b=record();b["layout_sha256"]="other"
        self.assertNotEqual(decide(a)[0],decide(b)[0])

if __name__ == "__main__":
    unittest.main()
