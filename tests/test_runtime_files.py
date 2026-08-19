import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeFilesTests(unittest.TestCase):
    def test_launch_agent_has_expected_hourly_runtime(self):
        with (ROOT / "com.johnvoorhees.ourstate-rss.plist").open("rb") as handle:
            plist = plistlib.load(handle)

        runtime = "/Users/johnvoorhees/Code/ourstate-rss"
        self.assertEqual("com.johnvoorhees.ourstate-rss", plist["Label"])
        self.assertEqual([f"{runtime}/scripts/publish.sh"], plist["ProgramArguments"])
        self.assertEqual(runtime, plist["WorkingDirectory"])
        self.assertEqual(3600, plist["StartInterval"])
        self.assertTrue(plist["RunAtLoad"])
        self.assertEqual("/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", plist["EnvironmentVariables"]["PATH"])
        self.assertEqual(f"{runtime}/logs/publish-out.log", plist["StandardOutPath"])
        self.assertEqual(f"{runtime}/logs/publish-err.log", plist["StandardErrorPath"])

    def test_publish_script_is_locked_idempotent_and_scoped(self):
        script = (ROOT / "scripts" / "publish.sh").read_text()
        required = [
            "set -euo pipefail",
            'mkdir "$LOCK_DIR"',
            "trap cleanup EXIT",
            "git pull --quiet --ff-only origin main",
            "PYTHONPATH=src python3 scripts/update_feed.py",
            "git diff --quiet -- docs/feed.xml",
            "git add -- docs/feed.xml",
            'git commit -m "Update Our State feed" -- docs/feed.xml',
            "git push --quiet origin main",
        ]
        for fragment in required:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, script)


if __name__ == "__main__":
    unittest.main()
