"""验证 bootstrap 的版本门禁、失败现场与原始配置；夹具保留在 .local。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "toolchains/kotlin-native/2.4.20-0.1.0-08"
spec = importlib.util.spec_from_file_location("bootstrap_native_08", ROOT / "bootstrap-native.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapNativeTest(unittest.TestCase):
    def setUp(self):
        local = REPO / ".local"
        local.mkdir(exist_ok=True)
        self.fixture = Path(tempfile.mkdtemp(prefix="bootstrap-08-", dir=local))
        self.output = self.fixture / "output"
        self.manifest = copy.deepcopy(json.loads((ROOT / "bootstrap-linux.json").read_text(encoding="utf-8")))
        self.archive_bytes = b"fixture-native-archive"
        self.manifest["nativeBundle"]["bytes"] = len(self.archive_bytes)
        self.manifest["nativeBundle"]["sha256"] = hashlib.sha256(self.archive_bytes).hexdigest()
        (self.fixture / "bootstrap-linux.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        self.version = self.manifest["kotlinVersion"]
        self.archive = self.output / (self.manifest["nativeBundle"]["directory"] + ".tar.gz")
        self.home = self.output / self.manifest["nativeBundle"]["directory"]
        self.receipt = self.output / "bootstrap-receipt.json"
        self.patches = [patch.object(bootstrap, "HERE", self.fixture),
                        patch.object(bootstrap.platform, "system", return_value="Linux"),
                        patch.object(bootstrap.platform, "machine", return_value="x86_64")]
        for context in self.patches:
            context.start()
            self.addCleanup(context.stop)

    def test_requested_version_mismatch_precedes_filesystem_and_download(self):
        with patch.object(bootstrap, "urlopen") as download, patch.object(bootstrap.subprocess, "run") as extract:
            with self.assertRaisesRegex(RuntimeError, "requested library version"):
                bootstrap.bootstrap(self.output, "2.4.20-0.1.0-09")
            self.assertFalse(self.output.exists())
            download.assert_not_called()
            extract.assert_not_called()

    def test_bad_archive_is_retained_and_not_extracted(self):
        self.output.mkdir()
        self.archive.write_bytes(b"partial")
        with patch.object(bootstrap, "urlopen") as download, patch.object(bootstrap.subprocess, "run") as extract:
            with self.assertRaisesRegex(RuntimeError, "size/SHA256 mismatch"):
                bootstrap.bootstrap(self.output, self.version)
            self.assertEqual(self.archive.read_bytes(), b"partial")
            self.assertFalse(self.home.exists())
            self.assertFalse(self.receipt.exists())
            download.assert_not_called()
            extract.assert_not_called()

    def test_extracted_version_and_properties_are_checked_without_rewriting(self):
        self.output.mkdir()
        self.archive.write_bytes(self.archive_bytes)
        properties = "compilerVersion=" + self.version + "\ntargetSysRoot.ohos_x64=original\n"
        def fake_extract(*args, **kwargs):
            path = self.home / "konan/konan.properties"
            path.parent.mkdir(parents=True)
            path.write_text(properties, encoding="utf-8", newline="\n")
        with patch.object(bootstrap, "urlopen") as download, patch.object(bootstrap.subprocess, "run", side_effect=fake_extract):
            self.assertEqual(bootstrap.bootstrap(self.output, self.version), self.home.resolve())
            download.assert_not_called()
        self.assertEqual((self.home / "konan/konan.properties").read_text(encoding="utf-8"), properties)
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(receipt["compilerVersion"], self.version)
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.archive_bytes).hexdigest())

    def test_wrong_extracted_compiler_is_retained_without_receipt(self):
        self.output.mkdir()
        self.archive.write_bytes(self.archive_bytes)
        def fake_extract(*args, **kwargs):
            path = self.home / "konan/konan.properties"
            path.parent.mkdir(parents=True)
            path.write_text("compilerVersion=2.4.20-0.1.0-09\n", encoding="utf-8", newline="\n")
        with patch.object(bootstrap.subprocess, "run", side_effect=fake_extract):
            with self.assertRaisesRegex(RuntimeError, "compilerVersion differs"):
                bootstrap.bootstrap(self.output, self.version)
        self.assertTrue((self.home / "konan/konan.properties").is_file())
        self.assertEqual(self.archive.read_bytes(), self.archive_bytes)
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
