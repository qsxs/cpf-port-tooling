"""匿名 Pages Poko 消费者；只取公开制品与固定工具，不取库源码。"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

# 复用 Grid 已验的匿名 HTTP、Klib payload 和有界日志读取；不修改 Grid 行为。
from grid_remote_consumer import digest, klib_payload, public_url, read_http, record, tail, write_json

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "consumers/poko"
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.poko"
MODULE = "poko-annotations"
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
GRID_COMMIT = "ed3472803fdb637d601391f62f43aba1bfea551f"
PLUGIN_URL = "https://repo.maven.apache.org/maven2/dev/drewhamilton/poko/poko-compiler-plugin/0.23.2/poko-compiler-plugin-0.23.2.jar"
PLUGIN_SHA256 = "7bdd55014b8e0d8115e99c49d1167c8d85bf1367fdec59ef4af28d0788a114c6"
STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}


def fetch_graph(version, output):
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    root_url = PAGES + GROUP.replace(".", "/") + "/" + MODULE + "/" + version + "/" + MODULE + "-" + version + ".module"
    requests = []

    def gmm(url, label):
        data, row = read_http(url, PAGES)
        requests.append(row)
        value = json.loads(data)
        write_json(evidence / "remote-gmm" / (label + ".json"), value)
        owner = value["component"]
        if any(owner.get(key) != expected for key, expected in (("group", GROUP), ("module", MODULE), ("version", version))):
            raise RuntimeError("Poko GMM owner differs: " + label)
        return value

    def artifact(module_url, declaration, role, target=None):
        directory = module_url.rsplit("/", 1)[0] + "/"
        url = public_url(urljoin(module_url, declaration["url"]), directory)
        data, row = read_http(url, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Poko GMM artifact size/SHA256 differs: " + role)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(data)
        row.update(role=role, expectedTarget=target, path=str(path), declaredName=declaration["name"])
        entries, props = klib_payload(data)
        if target is not None and (set(props.get("native_targets", "").split()) != {target} or not any("/ir/" in name and item["size"] > 0 for name, item in entries.items())):
            raise RuntimeError("Poko HTTP Native target or IR differs: " + target)
        requests.append(row)
        return row, entries

    def pom(module_url, module, target):
        url = module_url.removesuffix(".module") + ".pom"
        data, row = read_http(url, PAGES)
        requests.append(row)
        xml = ET.fromstring(data)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + key, namespaces=ns) != expected for key, expected in (("groupId", GROUP), ("artifactId", module), ("version", version))):
            raise RuntimeError("Poko Pages POM coordinates differ")
        deps = xml.findall("m:dependencies/m:dependency", ns)
        if len(deps) != 1:
            raise RuntimeError("Poko Pages POM dependency set differs")
        dep = deps[0]
        if dep.findtext("m:groupId", namespaces=ns) != "org.jetbrains.kotlin" or dep.findtext("m:artifactId", namespaces=ns) != "kotlin-stdlib" or dep.findtext("m:version", namespaces=ns) != "2.4.20-0.1.0-08" or dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
            raise RuntimeError("Poko Pages POM dependency or scope differs")

    root = gmm(root_url, MODULE)
    pom(root_url, MODULE, None)
    common = [v for v in root["variants"] if v.get("attributes", {}).get("org.gradle.usage") == "kotlin-metadata" and v.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == "common" and v.get("attributes", {}).get("org.gradle.category") == "library"]
    metadata, payload = [], None
    for variant in common:
        for declaration in variant.get("files", []):
            row, entries = artifact(root_url, declaration, "metadata")
            metadata.append(row)
            if payload is not None and payload != entries:
                raise RuntimeError("Multiple incompatible Poko common payloads")
            payload = entries
    if len(metadata) != 1:
        raise RuntimeError("Expected one Poko common metadata artifact")
    native, owners = {}, []
    for target, module in (("ohos_x64", MODULE + "-ohosx64"), ("ohos_arm64", MODULE + "-ohosarm64")):
        links = [v["available-at"] for v in root["variants"] if v.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and v.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and v.get("attributes", {}).get("org.gradle.category") == "library" and "available-at" in v]
        expected_url = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/" + module + "-" + version + ".module"
        if not links or any(link["group"] != GROUP or link["module"] != module or link["version"] != version or urljoin(root_url, link["url"]) != expected_url for link in links):
            raise RuntimeError("Poko root available-at differs: " + target)
        leaf = gmm(expected_url, module)
        pom(expected_url, module, target)
        if urljoin(expected_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Poko Native leaf owner differs")
        owners.append({"target": target, "leafModule": module, "leafUrl": expected_url, "ownerUrl": root_url})
        native[target] = []
        for variant in leaf["variants"]:
            attrs = variant.get("attributes", {})
            if attrs.get("org.jetbrains.kotlin.native.target") == target and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.gradle.category") == "library":
                for declaration in variant.get("files", []):
                    row, _ = artifact(expected_url, declaration, "native", target)
                    native[target].append(row)
        if len(native[target]) != 1:
            raise RuntimeError("Expected one Poko Native API Klib: " + target)
    manifest = {"status": "ANONYMOUS_PAGES_GRAPH_AND_BYTES_VERIFIED", "baseUrl": PAGES, "group": GROUP, "module": MODULE,
                "version": version, "rootUrl": root_url, "owners": owners, "requests": requests, "metadataArtifacts": metadata,
                "metadataPayload": payload, "nativeArtifacts": native, "librarySourcesDownloaded": False}
    write_json(evidence / "remote-http-manifest.json", manifest)
    return manifest


def fetch_tools(output, mode):
    lock = json.loads((TEMPLATE / "tooling-lock.json").read_text(encoding="utf-8"))
    if lock["revision"] != TOOL_REVISION or len(lock["files"]) != 20 or len({item["path"] for item in lock["files"]}) != 20:
        raise RuntimeError("Shared tooling content lock differs")
    tools = output / "shared-tools"
    prefix = "https://raw.githubusercontent.com/qsxs/cpf-port-tooling/" + TOOL_REVISION + "/"
    rows = []
    for item in lock["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not item["path"].startswith(TOOL_DIR + "/"):
            raise RuntimeError("Unsafe shared tooling member")
        data, http = read_http(prefix + item["path"], prefix)
        if len(data) != item["size"] or digest(data) != item["sha256"]:
            raise RuntimeError("Shared tooling bytes differ: " + item["path"])
        target = tools / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({"path": item["path"], **http})
    wrapper = json.loads((TEMPLATE / "wrapper-inputs.json").read_text(encoding="utf-8"))
    if wrapper["sourceCommit"] != GRID_COMMIT or {item["path"] for item in wrapper["files"]} != {"gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties", "gradle.properties"}:
        raise RuntimeError("Fixed Gradle wrapper input set differs")
    prefix = "https://raw.githubusercontent.com/qsxs/gridlayout-compose/" + GRID_COMMIT + "/ohos/"
    wrapper_root = output / "wrapper"
    for item in wrapper["files"]:
        if mode == "gradle8" and item["path"].startswith("gradle/wrapper/"):
            continue
        if item["url"] != prefix + item["path"]:
            raise RuntimeError("Gradle wrapper URL differs")
        data, http = read_http(item["url"], prefix)
        if len(data) != item["size"] or digest(data) != item["sha256"]:
            raise RuntimeError("Gradle wrapper bytes differ")
        target = wrapper_root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({"path": item["path"], **http})
    host_commit = None
    if mode == "gradle8":
        host = json.loads((TEMPLATE / "wrapper-inputs-gradle8.json").read_text(encoding="utf-8"))
        host_commit = "35ce89e5f91a23aaa5657c21510afd6ee593fad9"
        expected = {"gradle/wrapper/gradle-wrapper.jar": (59203, "e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637"),
                    "gradle/wrapper/gradle-wrapper.properties": (340, "1b9cd6961ee86eea17b2f912bddb22030492db23fc6dff07da6c30eccaaab0c4")}
        if host["sourceApplicationCommit"] != host_commit or host["gradleVersion"] != "8.11.1" or host["distributionSha256"] != "f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6" or {item["path"] for item in host["files"]} != set(expected):
            raise RuntimeError("Gradle 8 wrapper provenance differs")
        for item in host["files"]:
            if (item["size"], item["sha256"]) != expected[item["path"]]:
                raise RuntimeError("Gradle 8 wrapper lock differs")
            source = TEMPLATE / "gradle8" / item["path"]
            data = source.read_bytes()
            if (len(data), digest(data)) != expected[item["path"]]:
                raise RuntimeError("Gradle 8 wrapper bytes differ")
            target = wrapper_root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append({"path": item["path"], "size": len(data), "sha256": digest(data),
                         "sourceApplicationCommit": host_commit, "sourceGitPath": item["sourceGitPath"]})
    write_json(output / "evidence/toolchain-inputs.json", {"runtimeToolingCommit": TOOL_REVISION, "wrapperSourceCommit": GRID_COMMIT,
        "wrapperSourceApplicationCommit": host_commit, "gradleVersion": "8.11.1" if mode == "gradle8" else "9.5.0",
        "files": rows, "librarySourceCheckout": False})
    return tools, wrapper_root


def fetch_plugin(output):
    data, row = read_http(PLUGIN_URL, "https://repo.maven.apache.org/maven2/")
    if len(data) != 88604 or digest(data) != PLUGIN_SHA256:
        raise RuntimeError("Official Poko compiler plugin 0.23.2 bytes differ from P5 evidence")
    write_json(output / "evidence/poko-plugin-http.json", {"gav": "dev.drewhamilton.poko:poko-compiler-plugin:0.23.2", **row})


def own_declarations(native_home, compilation, label, output, env):
    roots = set()
    for item in compilation["outputs"]:
        path = Path(item["path"])
        if path.suffix == ".klib":
            roots.add(path)
        if path.as_posix().endswith("/default/manifest"):
            roots.add(path.parent.parent)
    if len(roots) != 1:
        raise RuntimeError("Cannot identify exactly one consumer Klib for " + label)
    klib = roots.pop()
    command = str(native_home / "bin/klib")
    results = {}
    for operation in ("dump-metadata", "dump-metadata-signatures"):
        result = subprocess.run([command, operation, str(klib)], env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Klib " + operation + " failed for " + label + ": " + result.stderr[-4000:])
        results[operation] = result.stdout
        (output / "evidence" / (label + "." + operation + ".txt")).write_text(result.stdout, encoding="utf-8")
    metadata = results["dump-metadata"].splitlines()
    headers = [i for i, line in enumerate(metadata) if re.search(r"\bclass\s+acceptance/PokoConsumerProbe\s*:\s*kotlin/Any\s*\{", line)]
    if len(headers) != 1:
        raise RuntimeError("Probe class is absent from " + label + " metadata")
    block = []
    for line in metadata[headers[0] + 1:]:
        if re.fullmatch(r"\s*}\s*", line):
            break
        block.append(line)
    signatures = results["dump-metadata-signatures"].splitlines()
    methods = {}
    for method in ("equals", "hashCode", "toString"):
        declarations = [line.strip() for line in block if re.search(r"\bfun\s+" + method + r"\s*\(", line)]
        matching = [line.strip() for line in signatures if "acceptance/PokoConsumerProbe." + method + "|" + method + "(" in line]
        if len(declarations) != 1 or len(matching) != 1:
            raise RuntimeError("Probe class does not declare generated " + method + " in " + label)
        methods[method] = {"declaration": declarations[0], "signature": matching[0]}
    return {"klib": str(klib), "classHeader": metadata[headers[0]].strip(), "methods": methods,
            "plugin": "dev.drewhamilton.poko:poko-compiler-plugin:0.23.2", "irPayload": compilation["irPayload"]}


def verify_records(output, native_home, env, mode):
    evidence = output / "evidence"
    resolution = json.loads((evidence / "consumer-resolution.json").read_text())
    if len(resolution["configurations"]) != 3:
        raise RuntimeError("Consumer resolution evidence is incomplete")
    if mode == "gradle8" and (resolution.get("gradleVersion") != "8.11.1" or resolution.get("pokoPluginApplied") is not False):
        raise RuntimeError("Gradle 8 resolution host or plugin evidence differs")
    compilations, declarations = [], []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
        data = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text())
        if data["target"] != target or len(data["sources"]) != 1 or not data["metadataPayload"] or not data["outputs"]:
            raise RuntimeError("Consumer compilation proof is incomplete: " + name)
        if target is not None and (not data["irPayload"] or set(data["nativeTargets"]) != {target}):
            raise RuntimeError("Consumer Native IR or target differs: " + name)
        if target is None and not data["metadataTrace"]:
            raise RuntimeError("Consumer common metadata transform has no Pages trace")
        if mode == "gradle9":
            if len(data["plugins"]) != 1 or data["plugins"][0]["sha256"] != PLUGIN_SHA256 or data["plugins"][0]["size"] != 88604:
                raise RuntimeError("Consumer compiler did not use the fixed Poko plugin")
        else:
            if data.get("gradleVersion") != "8.11.1" or data.get("pokoPluginApplied") is not False:
                raise RuntimeError("Gradle 8 compilation host or plugin evidence differs")
            if any(item["sha256"] == PLUGIN_SHA256 or Path(item["path"]).name.startswith("poko-compiler-plugin-") for item in data["plugins"]):
                raise RuntimeError("Poko compiler plugin leaked into Gradle 8 consumer")
            if any(option.startswith("plugin:dev.drewhamilton.poko:") for option in data["pluginOptions"]):
                raise RuntimeError("Poko compiler option leaked into Gradle 8 consumer")
        for item in [*data["sources"], *data["outputs"], *data["plugins"]]:
            if record(Path(item["path"])) != item:
                raise RuntimeError("Consumer compiler input/output bytes changed")
        if mode == "gradle9":
            declarations.append({"stage": name, **own_declarations(native_home, data, name, output, env)})
        compilations.append(data)
    write_json(evidence / "consumer-compilation.json", {"status": "METADATA_AND_DUAL_ABI_CONSUMER_COMPILED", "mode": mode,
        "gradleVersion": "8.11.1" if mode == "gradle8" else "9.5.0", "pokoPluginApplied": mode == "gradle9",
        "compilations": compilations, "ownGeneratedDeclarations": declarations if mode == "gradle9" else "NOT_CHECKED_PLUGIN_NOT_APPLIED",
        "link": "NOT_RUN", "runtime": "NOT_RUN"})


def main():
    output = Path(os.environ["POKO_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN"}
    code = 1
    try:
        version, source = os.environ["POKO_VERSION"], os.environ["POKO_SOURCE_SHA"]
        mode = os.environ["POKO_CONSUMER_MODE"]
        if mode not in ("gradle9", "gradle8"):
            raise RuntimeError("Explicit gradle9 or gradle8 consumer mode is required")
        state.update(mode=mode, gradleVersion="8.11.1" if mode == "gradle8" else "9.5.0",
                     pokoPlugin="NOT_APPLIED" if mode == "gradle8" else "0.23.2")
        workflow = os.environ["CI_TOOLING_SHA"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"0\.23\.1-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete Poko version must match the full producer source SHA")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, folder in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / folder
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        actual = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env).stdout.strip()
        if actual != workflow:
            raise RuntimeError("Consumer workflow checkout does not match its commit")
        state.update(version=version, sourceCommit=source, workflowToolingCommit=workflow, runtimeToolingCommit=TOOL_REVISION,
                     runId=os.environ.get("CI_RUN_ID"), runAttempt=os.environ.get("CI_RUN_ATTEMPT"))
        state["stage"] = "AnonymousHTTP"
        fetch_graph(version, output)
        state["stage"] = "PinnedBuildTools"
        tools, wrapper = fetch_tools(output, mode)
        if mode == "gradle9":
            fetch_plugin(output)
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running Poko consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError("Consumer " + label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        template = TEMPLATE / "gradle8" if mode == "gradle8" else TEMPLATE
        probe_name = "src/commonMain/kotlin/PokoHostConsumer.kt" if mode == "gradle8" else "src/commonMain/kotlin/PokoConsumer.kt"
        for name in ("settings.gradle.kts", "build.gradle.kts", probe_name):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template / name, target)
        shutil.copyfile(wrapper / "gradle.properties", project / "gradle.properties")
        probe = project / probe_name
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "remote-http-manifest.json"), "-PpokoVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Consumer tasks absent from actual discovery")
                write_json(evidence / "task-discovery.json", {"required": sorted(REQUIRED), "stdout": record(logs / "Tasks.stdout.log")})
        state["stage"] = "VerifyPublicConsumption" if mode == "gradle8" else "VerifyDeclarations"
        verify_records(output, native, env, mode)
        state["status"] = "GRADLE8_PUBLIC_CONSUMER_COMPILED" if mode == "gradle8" else "GRADLE9_PLUGIN_CONSUMER_COMPILED"
        code = 0
    except Exception as error:
        state.update(status="FAILED", error=str(error))
    finally:
        for stage in ("BootstrapNative", *STAGES):
            for stream in ("stdout", "stderr"):
                text = tail(output / "logs" / (stage + "." + stream + ".log"))
                if text:
                    (evidence / (stage + "." + stream + "-tail.log")).write_text(text, encoding="utf-8")
                    if state["status"] == "FAILED" and state.get("stage") == stage:
                        print(text, file=sys.stderr)
        for path in evidence.rglob("*"):
            if path.is_file() and path.stat().st_size > 8 * 1024 * 1024:
                state.update(status="FAILED", error="Consumer structured evidence exceeds 8 MiB")
                code = 1
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
