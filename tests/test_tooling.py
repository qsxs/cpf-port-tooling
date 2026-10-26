"""轻量语义检查；所有夹具留在本仓 .local，不自动删除。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cpf_port_tooling", ROOT / "cpf_port_tooling.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class ToolingSemanticsTest(unittest.TestCase):
    def setUp(self):
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="helper-check-", dir=local))
        self.cache = self.root / "cache"

    def component(self, group="example", module="sample", version="1.0"):
        directory = self.cache / group / module / version / "cache-key"
        directory.mkdir(parents=True)
        return directory

    def put(self, directory, name, data):
        path = directory / name
        path.write_bytes(data)
        return path

    def common(self, directory, missing=False, escaping=False):
        data = b"locked metadata payload"
        declaration = {"name": "sample-1.0.jar", "url": "../escape.jar" if escaping else "sample-metadata-1.0.jar",
                       "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        metadata = {"variants": [{"name": "metadataApiElements", "attributes": {
            "org.gradle.category": "library", "org.gradle.usage": "kotlin-metadata",
            "org.jetbrains.kotlin.platform.type": "common"}, "files": [declaration]}]}
        self.put(directory, "sample-1.0.module", json.dumps(metadata).encode())
        if not missing:
            self.put(directory, "sample-1.0.jar", data)
        return metadata

    def test_immutable_json_and_exact_copy(self):
        path = self.root / "identity.json"
        tools.write(path, {"identity": 1})
        tools.write(path, {"identity": 1})
        with self.assertRaises(RuntimeError):
            tools.write(path, {"identity": 2})
        self.assertEqual(tools.load(path), {"identity": 1})
        target = self.root / "copy.json"
        tools.copy_exact(path, target)
        self.assertEqual(tools.record(path)["sha256"], tools.record(target)["sha256"])
        target.write_bytes(b"different")
        with self.assertRaises(RuntimeError):
            tools.copy_exact(path, target)

    def test_common_alias_preserves_original_metadata(self):
        directory = self.component()
        self.common(directory)
        work = self.root / "work"
        rows = tools.mirror_cache(work, {"example:sample": "1.0"}, cache_root=self.cache,
                                  gradle_api=(9, 5, 0), tool_allowlist=[])
        exposed = work / "frozen-maven/example/sample/1.0"
        self.assertEqual((exposed / "sample-metadata-1.0.jar").read_bytes(), b"locked metadata payload")
        self.assertEqual((exposed / "sample-1.0.module").read_bytes(), (directory / "sample-1.0.module").read_bytes())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(tools.load(work / "maven-snapshot.json")["aliases"]), 1)

    def test_missing_artifact_exposes_no_partial_component(self):
        directory = self.component()
        self.common(directory, missing=True)
        work = self.root / "work"
        rows = tools.mirror_cache(work, {"example:sample": "1.0"}, cache_root=self.cache,
                                  gradle_api=(9, 5, 0), tool_allowlist=[])
        self.assertEqual(rows, [])
        self.assertFalse((work / "frozen-maven/example/sample/1.0").exists())
        self.assertIn("MISSING_OR_MISMATCHED", tools.load(work / "maven-snapshot.json")["omissions"][0]["reason"])

    def test_artifact_url_escape_is_omitted(self):
        directory = self.component()
        self.common(directory, escaping=True)
        row = tools._snapshot_component(directory.parent, self.root / "target", False, (9, 5, 0))
        self.assertEqual(row["files"], [])
        self.assertIn("ARTIFACT_URL_OUTSIDE_SNAPSHOT", row["omission"])

    def test_conflicting_cache_files_fail_closed(self):
        directory = self.component()
        self.common(directory)
        other = directory.parent / "conflict"
        other.mkdir()
        self.put(other, "sample-1.0.module", b"{}")
        row = tools._snapshot_component(directory.parent, self.root / "target", False, (9, 5, 0))
        self.assertIn("CONFLICTING_CACHE_FILES", row["omission"])
        self.assertEqual(row["files"], [])

    def test_explicit_tool_allowlist_controls_pom_only_jar(self):
        directory = self.component(group="example.tools", module="compiler")
        pom = b'<project xmlns="http://maven.apache.org/POM/4.0.0"><packaging>jar</packaging></project>'
        self.put(directory, "compiler-1.0.pom", pom)
        self.put(directory, "compiler-1.0.jar", b"compiler payload")
        for allowed, expected in [(False, 0), (True, 2)]:
            work = self.root / ("allow" if allowed else "deny")
            rows = tools.mirror_cache(work, {"example.tools:compiler": "1.0"}, cache_root=self.cache,
                                      gradle_api=(9, 5, 0), tool_allowlist=[{"group": "example.tools", "modules": ["compiler"], "versions": ["1.0"]}] if allowed else [])
            self.assertEqual(len(rows), expected)

    def test_no_cache_defers_all_pins_to_gradle(self):
        work = self.root / "empty"
        self.assertEqual(tools.mirror_cache(work, {"example:sample": "1.0"}, cache_root=None,
                                           gradle_api=(9, 5, 0), tool_allowlist=[]), [])
        self.assertEqual(tools.load(work / "maven-snapshot.json")["omissions"][0]["reason"], "CACHE_GAV_NOT_PRESENT_DEFER_TO_GRADLE")

    def test_compatible_jvm_gradle_api_is_parameterized(self):
        directory = self.component(group="example.tools", module="compiler")
        data = b"compiler payload"
        variant = {"name": "gradle95Runtime", "attributes": {"org.gradle.category": "library",
            "org.gradle.usage": "java-runtime", "org.gradle.jvm.version": 17,
            "org.gradle.plugin.api-version": "9.5"}, "files": [{"name": "compiler-1.0.jar", "url": "compiler-1.0.jar",
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]}
        self.put(directory, "compiler-1.0.module", json.dumps({"variants": [variant]}).encode())
        self.put(directory, "compiler-1.0.jar", data)
        self.assertIsNone(tools._snapshot_component(directory.parent, self.root / "yes", True, (9, 5, 0))["omission"])
        self.assertEqual(tools._snapshot_component(directory.parent, self.root / "no", True, (8, 11, 1))["files"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
