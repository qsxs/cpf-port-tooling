"""校验共享 .08 宿主闭包及原始 POM，不运行 Gradle。"""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1] / "toolchains/kotlin-native/2.4.20-0.1.0-08"
read = lambda name: json.loads((ROOT / name).read_text(encoding="utf-8"))
metadata = read("metadata-toolchain.json")
commonizer = read("commonizer-toolchain.json")
plugin = read("compiler-plugin-toolchain.json")
native = read("native-compiler-toolchain.json")
bootstrap = read("bootstrap-linux.json")
version = "2.4.20-0.1.0-08"
assert all(lock["compilerVersion"] == version for lock in (metadata, commonizer, plugin, native))
assert bootstrap["schemaVersion"] == 1 and bootstrap["host"] == "linux-x86_64"
assert bootstrap["kotlinVersion"] == version
assert bootstrap["nativeBundle"]["bytes"] == 177306208
assert bootstrap["nativeBundle"]["sha256"] == "014411e74a0a0733aaf5cdcf7883e1b43c66f5b0a9fec390866bb8d459acad9f"
assert bootstrap["configurationPolicy"] == "UNMODIFIED_ARCHIVE_KONAN_PROPERTIES_STANDARD_ON_DEMAND_DEPENDENCIES"
assert "publication" not in bootstrap
for lock in (commonizer, plugin, native):
    assert lock["schemaVersion"] == 1
    assert set(lock["pins"]) == set(lock["artifacts"])
assert len(metadata["launcherPins"]) == len(metadata["launcherArtifacts"]) == 8
assert set(metadata["launcherPins"]) == set(metadata["launcherArtifacts"])
assert len(commonizer["pins"]) == 1 and commonizer["inheritsLauncherToolchain"] == "metadata-toolchain.json"
assert not (set(commonizer["pins"]) & set(metadata["launcherPins"]))
assert len(plugin["pins"]) == 1
assert len(native["pins"]) == len(native["sourcePoms"]) == 14
assert metadata["launcherPins"]["org.jetbrains:annotations"] == "13.0"
assert native["pins"]["org.jetbrains:annotations"] == "23.0.0"
for pins, items in ((metadata["launcherPins"], metadata["launcherArtifacts"]),
                    (commonizer["pins"], commonizer["artifacts"]),
                    (plugin["pins"], plugin["artifacts"]), (native["pins"], native["artifacts"])):
    for ga in pins:
        item = items[ga]
        assert isinstance(item["size"], int) and item["size"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
for ga in set(metadata["launcherPins"]) - {"org.jetbrains:annotations"}:
    assert metadata["launcherPins"][ga] == native["pins"][ga]
    assert all(metadata["launcherArtifacts"][ga][key] == native["artifacts"][ga][key]
               for key in ("size", "sha256"))

ns = {"m": "http://maven.apache.org/POM/4.0.0"}
def source_pom(item):
    data = (ROOT / item["path"]).read_bytes()
    assert len(data) == item["size"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    assert item["url"].startswith("https://")
    return ET.fromstring(data)

def gav(xml):
    return ":".join(xml.findtext("m:" + part, namespaces=ns) for part in ("groupId", "artifactId", "version"))

edges = {}
for item in native["sourcePoms"]:
    xml = source_pom(item)
    ga = item["gav"].rsplit(":", 1)[0]
    assert gav(xml) == item["gav"] == ga + ":" + native["pins"][ga]
    edges[ga] = []
    for dep in xml.findall("m:dependencies/m:dependency", ns):
        if dep.findtext("m:scope", default="compile", namespaces=ns) not in ("compile", "runtime"):
            continue
        child = dep.findtext("m:groupId", namespaces=ns) + ":" + dep.findtext("m:artifactId", namespaces=ns)
        requested = dep.findtext("m:version", namespaces=ns)
        assert child in native["pins"]
        if requested != native["pins"][child]:
            assert child in ("org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains:annotations")
            selection = native["versionSelection"]["stdlib" if child.endswith(":kotlin-stdlib") else "annotations"]
            assert requested in selection["requested"] and native["pins"][child] == selection["selected"]
        edges[ga].append(child)
seen, pending = set(), [root.rsplit(":", 1)[0] for root in native["roots"]]
while pending:
    ga = pending.pop()
    if ga not in seen:
        seen.add(ga)
        pending.extend(edges[ga])
assert seen == set(native["pins"])
for lock in (commonizer, plugin):
    ga, selected = next(iter(lock["pins"].items()))
    assert gav(source_pom(lock["sourcePom"])) == ga + ":" + selected
launcher = next(p for p in native["sourcePoms"] if p["gav"].startswith("org.jetbrains.kotlin:kotlin-compiler-embeddable:"))
assert launcher["url"] == metadata["launcherPomUrl"] and launcher["sha256"] == metadata["launcherPomSha256"]
assert b"\r\n" in (ROOT / "vendor/native-compiler-host/annotations-23.0.0.pom").read_bytes()
ast.parse((ROOT / "bootstrap-native.py").read_text(encoding="utf-8"))
print(json.dumps({"status": "PASSED", "metadataLauncher": 8, "commonizer": 9,
                  "nativeHost": 14, "composePlugin": 1, "sourcePoms": 16}))
