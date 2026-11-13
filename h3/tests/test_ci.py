"""Real Git ownership-guard regression, without changing filesystem ownership."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

class ContainerMetadataTests(unittest.TestCase):
    def test_revision_on_mount_with_different_owner(self):
        helper=Path(__file__).resolve().parents[2]/'ci/git_revision.sh'
        with tempfile.TemporaryDirectory() as d:
            def git(*args,env=None,check=True):
                return subprocess.run(['git','-C',d,*args],env=env,check=check,
                                      capture_output=True,text=True)
            git('init','-q')
            git('-c','user.name=CI test','-c','user.email=test@example.invalid',
                'commit','-q','--allow-empty','-m','fixture')
            expected=git('rev-parse','HEAD').stdout.strip()
            env=dict(os.environ,GIT_TEST_ASSUME_DIFFERENT_OWNER='1',
                     GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull)
            control=git('rev-parse','HEAD',env=env,check=False)
            self.assertNotEqual(control.returncode,0,'ownership guard must be active')
            result=subprocess.run(['bash',str(helper),d],env=env,check=True,
                                  capture_output=True,text=True)
            self.assertEqual(result.stdout.strip(),expected)
