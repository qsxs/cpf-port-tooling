"""静态核验 Poko 输入来源、工具锁和 consumer 配置；不执行 Gradle/Native。"""
import ast
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
if len(sys.argv) != 2:
    raise SystemExit("usage: python -B tests/check_poko_port_static.py <Poko-ohos-directory>")
ROOT = Path(__file__).resolve().parents[1]
OHOS = Path(sys.argv[1]).resolve()
sha = lambda data: hashlib.sha256(data).hexdigest()
source = json.loads((OHOS / "source-inputs.json").read_text(encoding="utf-8"))
config = json.loads((OHOS / "port-config.json").read_text(encoding="utf-8"))
lock = json.loads((OHOS / "tooling-lock.json").read_text(encoding="utf-8"))
assert (OHOS / "tooling-lock.json").read_bytes() == (ROOT / "consumers/poko/tooling-lock.json").read_bytes()
assert lock["revision"] == "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285" and len(lock["files"]) == 20
for item in lock["files"]:
    data = (ROOT / item["path"]).read_bytes()
    assert (len(data), sha(data)) == (item["size"], item["sha256"])
assert config["metadataPolicy"] == "STANDARD_KGP_FIRST" and config["gradle"] == "9.5.0"
assert config["kotlin"] == config["stdlib"] == "2.4.20-0.1.0-08"
assert (config["group"], config["artifact"], config["versionBase"]) == ("io.github.qsxs.cpf.poko", "poko-annotations", "0.23.1")
for key in ("sources", "pom", "module", "license"):
    item = source[key]
    data = (OHOS / item["path"]).read_bytes()
    assert (len(data), sha(data)) == (item["size"], item["sha256"])
assert source["license"]["sha256"] == "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
assert source["upstream"]["commit"] == "7f2bb9beeea0b9590b27056a613d9fa42b20f068"
source_root = (OHOS / source["sourceRoot"]).resolve()
rows = {row["member"]: row for row in source["sourceMembers"]}
assert len(rows) == 3 and {"commonMain/" + p.relative_to(source_root).as_posix() for p in source_root.rglob("*.kt")} == set(rows)
with zipfile.ZipFile(OHOS / source["sources"]["path"]) as archive:
    assert {name for name in archive.namelist() if name.endswith(".kt")} == set(rows)
    for member, row in rows.items():
        data = (source_root / member.removeprefix("commonMain/")).read_bytes()
        assert archive.read(member) == data and (len(data), sha(data)) == (row["size"], row["sha256"])
ns = {"m": "http://maven.apache.org/POM/4.0.0"}
pom = ET.parse(OHOS / source["pom"]["path"])
assert [pom.findtext("m:" + x, namespaces=ns) for x in ("groupId", "artifactId", "version")] == ["dev.drewhamilton.poko", "poko-annotations", "0.23.1"]
deps = pom.findall("m:dependencies/m:dependency", ns)
assert len(deps) == 1 and [deps[0].findtext("m:" + x, namespaces=ns) for x in ("groupId", "artifactId", "version", "scope")] == ["org.jetbrains.kotlin", "kotlin-stdlib", "2.4.0", "runtime"]
gmm = json.loads((OHOS / source["module"]["path"]).read_text(encoding="utf-8"))
assert all(gmm["component"][key] == value for key, value in (("group", "dev.drewhamilton.poko"), ("module", "poko-annotations"), ("version", "0.23.1")))
wrapper = json.loads((ROOT / "consumers/poko/wrapper-inputs.json").read_text(encoding="utf-8"))
for item in wrapper["files"]:
    data = (OHOS / item["path"]).read_bytes()
    assert (len(data), sha(data)) == (item["size"], item["sha256"])
assert "gradle-9.5.0-bin.zip" in (OHOS / "gradle/wrapper/gradle-wrapper.properties").read_text(encoding="utf-8")
for path in (OHOS / "PokoPort.py", ROOT / "scripts/poko_producer.py", ROOT / "scripts/poko_remote_consumer.py", ROOT / "tests/test_poko_declarations.py"):
    ast.parse(path.read_text(encoding="utf-8"))
for path in (OHOS / "port-config.json", OHOS / "source-inputs.json", OHOS / "tooling-lock.json", ROOT / "consumers/poko/tooling-lock.json", ROOT / "consumers/poko/wrapper-inputs.json"):
    json.loads(path.read_text(encoding="utf-8"))
probe = (ROOT / "consumers/poko/src/commonMain/kotlin/PokoConsumer.kt").read_text(encoding="utf-8")
assert "@Poko" in probe and "class PokoConsumerProbe(" in probe and "data class" not in probe
assert not any("fun " + method + "(" in probe for method in ("equals", "hashCode", "toString"))
settings = (ROOT / "consumers/poko/settings.gradle.kts").read_text(encoding="utf-8").lower()
host_settings = (ROOT / "consumers/poko/gradle8/settings.gradle.kts").read_text(encoding="utf-8").lower()
host_build = (ROOT / "consumers/poko/gradle8/build.gradle.kts").read_text(encoding="utf-8")
for value in (settings, host_settings):
    assert "mavenlocal(" not in value and "includebuild(" not in value and "maven(file(" not in value
assert 'id("dev.drewhamilton.poko")' not in host_settings and 'id("dev.drewhamilton.poko")' not in host_build
assert 'id("dev.drewhamilton.poko")' in (ROOT / "consumers/poko/build.gradle.kts").read_text(encoding="utf-8")
host_probe = (ROOT / "consumers/poko/gradle8/src/commonMain/kotlin/PokoHostConsumer.kt").read_text(encoding="utf-8")
assert "import dev.drewhamilton.poko.Poko" in host_probe and "annotation: Poko" in host_probe and "@Poko" not in host_probe
host_wrapper = json.loads((ROOT / "consumers/poko/wrapper-inputs-gradle8.json").read_text(encoding="utf-8"))
assert host_wrapper["sourceApplicationCommit"] == "35ce89e5f91a23aaa5657c21510afd6ee593fad9"
assert host_wrapper["gradleVersion"] == "8.11.1" and host_wrapper["distributionSha256"] == "f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6"
expected = {"gradle/wrapper/gradle-wrapper.jar": (59203, "e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637"),
            "gradle/wrapper/gradle-wrapper.properties": (340, "1b9cd6961ee86eea17b2f912bddb22030492db23fc6dff07da6c30eccaaab0c4")}
assert {item["path"] for item in host_wrapper["files"]} == set(expected)
for item in host_wrapper["files"]:
    data = (ROOT / "consumers/poko/gradle8" / item["path"]).read_bytes()
    assert (len(data), sha(data)) == (item["size"], item["sha256"]) == expected[item["path"]]
properties = (ROOT / "consumers/poko/gradle8/gradle/wrapper/gradle-wrapper.properties").read_text(encoding="utf-8")
assert "gradle-8.11.1-bin.zip" in properties and host_wrapper["distributionSha256"] in properties
producer_build = (OHOS / "build.gradle.kts").read_text(encoding="utf-8")
plugin_build = (ROOT / "consumers/poko/build.gradle.kts").read_text(encoding="utf-8")
assert 'file(sources.getValue("sourceRoot") as String)' in producer_build
for build in (producer_build, plugin_build, host_build):
    assert ".state.failure" not in build
assert 'getValue("selected").toString()' not in plugin_build
print(json.dumps({"status": "PASSED", "originalKotlinSources": 3, "toolFiles": 20, "officialPom": "dev.drewhamilton.poko:poko-annotations:0.23.1", "producerGradle": "9.5.0", "consumerGradle": ["9.5.0", "8.11.1"], "gradle8PokoPlugin": "NOT_DECLARED"}))
