"""受控 producer 的最小无进程验证；所有命令由 stub 替代，夹具保留。"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("controlled_grid", ROOT / "scripts/grid_producer.py")
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)
SHA = "a" * 40


class ProducerTest(unittest.TestCase):
    def setUp(self):
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="grid-ci-check-", dir=local))
        self.grid, self.output = self.root / "grid", self.root / "output"
        (self.grid / "ohos").mkdir(parents=True)
        (self.grid / "ohos/native-compiler-toolchain.json").write_text('{"scope":"TEST_ONLY_HOST_LOCK"}', encoding="utf-8")
        self.work = self.output / "work/grid-test"
        self.work.mkdir(parents=True)
        self.calls = []
        self.fail = None
        self.env = {"GRID_SHA": SHA, "GRID_CHECKOUT": str(self.grid), "GRID_PRODUCER_OUTPUT": str(self.output),
                    "CI_RUN_ID": "123", "CI_RUN_ATTEMPT": "2", "CI_TOOLING_SHA": "b" * 40,
                    "JAVA_HOME": str(self.root / "jdk"), "PATH": "stub-only",
                    "ACTIONS_RUNTIME_TOKEN": "TEST_ONLY_MUST_NOT_FORWARD",
                    "GITHUB_TOKEN": "TEST_ONLY_MUST_NOT_FORWARD", "GITCODE_TOKEN": "TEST_ONLY_MUST_NOT_FORWARD",
                    "LD_LIBRARY_PATH": str(self.root / "python/lib")}

    def command(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs["env"]["LD_LIBRARY_PATH"], self.env["LD_LIBRARY_PATH"])
        for token in ("ACTIONS_RUNTIME_TOKEN", "GITHUB_TOKEN", "GITCODE_TOKEN"):
            self.assertNotIn(token, kwargs["env"])
        if argv[0] == "git":
            return SimpleNamespace(stdout=SHA, returncode=0)
        if argv[2].endswith("bootstrap-native.py"):
            kwargs["stdout"].write(str(self.output / "native-bootstrap/native").encode())
            return SimpleNamespace(returncode=0)
        stage = argv[3]
        if stage == self.fail:
            logs = self.work / "invocations"
            logs.mkdir(exist_ok=True)
            (logs / (stage + "-1.stdout.log")).write_text("".join(f"line{i:03}\n" for i in range(100)), encoding="utf-8")
            kwargs["stderr"].write(b"stub stage failure")
            return SimpleNamespace(returncode=42)
        kwargs["stdout"].write(json.dumps({"work": str(self.work), "fingerprint": "f" * 64, "stage": stage}).encode())
        if stage == "Resolve":
            (self.work / "evidence").mkdir(exist_ok=True)
            (self.work / "evidence/resolve.json").write_text('{"nativeCompiler":{"configuration":"kotlinCompilerClasspath","artifacts":[]}}', encoding="utf-8")
        if stage == "NativeArm64":
            (self.work / "evidence/native-compiler-host.json").write_text('{"scope":"TEST_ONLY_HOST_RECEIPT"}', encoding="utf-8")
        if stage == "Verify":
            (self.work / "publication.json").write_text('{"status":"TEST_ONLY_VERIFIED"}', encoding="utf-8")
        return SimpleNamespace(returncode=0)

    def invoke(self):
        with patch.dict(os.environ, self.env, clear=True), patch.object(producer.subprocess, "run", side_effect=self.command), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return producer.main()

    def test_all_stages_use_fixed_group_unique_preview_and_staging(self):
        self.assertEqual(self.invoke(), 0)
        stages = [args[3] for args in self.calls if len(args) > 3 and args[2].endswith("GridPort.py")]
        self.assertEqual(stages, list(producer.STAGES))
        command = self.calls[-1]
        self.assertEqual(command[command.index("--group") + 1], producer.GROUP)
        self.assertEqual(command[command.index("--version") + 1], "2.8.0-cpf11-preview-" + SHA[:12] + "-123-2")
        self.assertEqual(command[command.index("--repository") + 1], str(self.output / "staging"))
        manifest = json.loads((self.output / "evidence/run.json").read_text())
        self.assertEqual(manifest["status"], "VERIFIED_STAGING_READY_FOR_MANUAL_REVIEW")
        self.assertTrue((self.output / "evidence/publication.json").is_file())
        self.assertTrue((self.output / "evidence/locks/native-compiler-toolchain.json").is_file())
        self.assertTrue((self.output / "evidence/native-compiler-host.json").is_file())
        summary = json.loads((self.output / "evidence/resolve-summary.json").read_text())
        self.assertEqual(summary["nativeCompiler"]["configuration"], "kotlinCompilerClasspath")

    def test_failure_keeps_bounded_current_stage_diagnostics_and_fails(self):
        self.fail = "Metadata"
        self.assertEqual(self.invoke(), 1)
        manifest = json.loads((self.output / "evidence/run.json").read_text())
        self.assertEqual(manifest["failedStage"], "Metadata")
        self.assertEqual(manifest["status"], "FAILED")
        tail = (self.output / "evidence/Metadata.gradle-stdout-tail.log").read_text()
        self.assertNotIn("line019", tail)
        self.assertIn("line020", tail)
        self.assertLessEqual(len(tail.encode()), 16384)
        self.assertFalse((self.output / "evidence/publication.json").exists())

    def test_invalid_source_identifier_never_starts_a_command(self):
        self.env["GRID_SHA"] = "$(untrusted)"
        self.assertEqual(self.invoke(), 1)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
