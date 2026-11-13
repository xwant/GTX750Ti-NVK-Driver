from pathlib import Path
import tempfile
import unittest
from h3.hardware_validation import preflight

class PreflightTests(unittest.TestCase):
    def test_requires_real_expected_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'devices';root.mkdir()
            with self.assertRaises(ValueError):preflight(root)
            p=root/'0000:01:00.0';p.mkdir()
            for k,v in {'vendor':'0x10de','device':'0x1380','class':'0x030000'}.items():
                (p/k).write_text(v)
            driver=Path(d)/'nouveau';driver.mkdir();(p/'driver').symlink_to(driver)
            self.assertEqual(preflight(root)[0]['driver'],'nouveau')
            (p/'driver').unlink();driver=Path(d)/'nvidia';driver.mkdir();(p/'driver').symlink_to(driver)
            with self.assertRaises(ValueError):preflight(root)
    def test_wrong_bdf_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'0000:02:00.0';p.mkdir()
            for k,v in {'vendor':'0x10de','device':'0x1380','class':'0x030000'}.items():(p/k).write_text(v)
            (p/'driver').symlink_to('/tmp')
            with self.assertRaises(ValueError):preflight(Path(d))
