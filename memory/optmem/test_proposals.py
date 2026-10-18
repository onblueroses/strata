import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SCRIPT = Path(__file__).with_name("optmem-proposals")


class ProposalTelemetryTests(unittest.TestCase):
    def archive(self, temp, sink):
        base = Path(temp)
        env = dict(os.environ, OPTMEM_DIR=str(base / "state"),
                   OPTMEM_CONTRACT_FILE=str(Path(__file__).with_name("README.md")),
                   OPTMEM_SESSION_ID="01a14a2a")
        if sink is None:
            env.pop("OPTMEM_DRAIN_TELEMETRY_SINK", None)
        else:
            env["OPTMEM_DRAIN_TELEMETRY_SINK"] = str(sink)

        def call(*args):
            return subprocess.run([str(SCRIPT), *args], env=env, text=True,
                                  capture_output=True, check=True)

        call("append", "codex/test", "F @e/example @s/01a14a2a @k/example test fact")
        claim = call("claim", "primary").stdout.strip()
        decisions = base / "decisions.tsv"
        decisions.write_text("KEEP\tverified\n")
        result = call("archive", claim, str(decisions))
        self.assertTrue(Path(result.stdout.strip()).exists())
        return result

    def test_configured_sink_gets_counts_after_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            output = base / "telemetry.txt"
            sink = base / "sink.sh"
            sink.write_text(f'printf "%s|%s|%s\\n" "$1" "$2" "$3" > "{output}"\n')
            self.archive(temp, sink)
            self.assertEqual(output.read_text().strip(),
                             'optmem_drain|01a14a2a|{"op":"archive","claimed":1,"keep":1,"rewrite":0,"reject":0}')

    def test_missing_sink_is_silent_and_archive_stays_durable(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.archive(temp, Path(temp) / "missing.sh")
            self.assertEqual(result.stderr, "")

    def test_unset_sink_falls_back_to_the_conventional_path(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            (home / ".local" / "bin").mkdir(parents=True)
            output = Path(temp) / "telemetry.txt"
            (home / ".local" / "bin" / "telemetry-emit").write_text(f'printf "%s\\n" "$1" > "{output}"\n')
            with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
                self.archive(temp, None)
            self.assertEqual(output.read_text().strip(), "optmem_drain")


if __name__ == "__main__":
    unittest.main()
