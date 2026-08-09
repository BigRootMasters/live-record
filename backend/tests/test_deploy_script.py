import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = PROJECT_ROOT / 'deploy.sh'


class DeployScriptTestCase(unittest.TestCase):
    def test_script_has_valid_bash_syntax(self):
        result = subprocess.run(
            ['bash', '-n', str(DEPLOY_SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_is_available_without_deploying(self):
        result = subprocess.run(
            ['bash', str(DEPLOY_SCRIPT), '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Usage: ./deploy.sh', result.stdout)
        self.assertIn('--skip-pull', result.stdout)


if __name__ == '__main__':
    unittest.main()
