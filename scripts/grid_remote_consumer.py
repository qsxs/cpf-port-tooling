"""固定 Pages 的匿名 Grid 编译消费者；不取库源码，不部署，不读取令牌。"""
from __future__ import annotations

from collections import deque
import hashlib
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "consumers/grid"
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "com.github.qsxs.gridlayout-compose"
TOOL_COMMIT = "ed3472803fdb637d601391f62f43aba1bfea551f"
TOOL_PATHS = {"gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
              "bootstrap-native.py", "bootstrap-linux.json", "port-config.json", "dependency-pins.json", "metadata-pins.json",
              "metadata-toolchain.json", "commonizer-toolchain.json", "compiler-plugin-toolchain.json", "native-compiler-toolchain.json", "gradle.properties"}
STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(path):
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest(path.read_bytes())}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def public_url(url, prefix):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or not url.startswith(prefix):
        raise RuntimeError("URL escaped the fixed anonymous repository: " + url)
    if ".." in unquote(parsed.path).split("/") or "\\" in unquote(parsed.path):
        raise RuntimeError("Unsafe public artifact URL")
    return url


def read_http(url, prefix):
    public_url(url, prefix)
    transport_failures = []
    for attempt in range(1, 4):
        try:
            # 不读取代理认证环境，不安装 Cookie 或认证处理器。
            opener = build_opener(ProxyHandler({}))
            with opener.open(Request(url, headers={"User-Agent": "Grid-Pages-Anonymous-Acceptance"}), timeout=60) as response:
                declared = response.headers.get("Content-Length")
                length = int(declared) if declared is not None else None
                if length is not None and length > 64 * 1024 * 1024:
                    raise RuntimeError("Anonymous artifact response exceeds the Grid limit")
                data = response.read()
                if length is not None and len(data) != length:
                    raise IncompleteRead(data, max(0, length - len(data)))
                final = response.geturl()
                status = response.status
                content_type = response.headers.get("Content-Type", "")
            if status != 200 or final != url or len(data) > 64 * 1024 * 1024 or not data:
                raise RuntimeError("Anonymous artifact response differs: " + url)
            if "text/html" in content_type.lower() or data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise RuntimeError("Anonymous artifact response is HTML: " + url)
            return data, {"url": url, "finalUrl": final, "status": status, "size": len(data), "sha256": digest(data), "contentType": content_type,
                          "authorizationSent": False, "cookieSent": False, "requestAttempts": attempt, "transportFailures": transport_failures}
        except IncompleteRead as error:
            transport_failures.append({"kind": "TRANSPORT_INCOMPLETE_READ", "attempt": attempt, "partialBytes": len(error.partial), "expectedRemaining": error.expected})
            if attempt == 3:
                raise RuntimeError("TRANSPORT_INCOMPLETE_READ after three requests: " + url + "; attempts=" + json.dumps(transport_failures)) from error
            time.sleep(2)


def klib_payload(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = {}
        for item in archive.infolist():
            name = item.filename.removeprefix("commonMain/")
            if not item.is_dir() and name.startswith("default/"):
                content = archive.read(item)
                entries[name] = {"size": len(content), "sha256": digest(content)}
        manifest_name = next((name for name in archive.namelist() if name.removeprefix("commonMain/") == "default/manifest"), None)
        properties = {}
        if manifest_name:
            properties = dict(line.split("=", 1) for line in archive.read(manifest_name).decode().splitlines() if "=" in line)
    if "default/manifest" not in entries or not any("/linkdata/" in name and item["size"] > 0 for name, item in entries.items()):
        raise RuntimeError("Downloaded Grid artifact has no Klib metadata payload")
    return entries, properties


def fetch_graph(version, output):
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    root_url = PAGES + GROUP.replace(".", "/") + "/grid/" + version + "/grid-" + version + ".module"
    requests = []

    def gmm(url, label):
        data, row = read_http(url, PAGES)
        requests.append(row)
        value = json.loads(data)
        write_json(evidence / "remote-gmm" / (label + ".json"), value)
        owner = value["component"]
        if any(owner.get(key) != expected for key, expected in (("group", GROUP), ("module", "grid"), ("version", version))):
            raise RuntimeError("Grid GMM owner differs: " + label)
        return value

    def artifact(module_url, declaration, role, target=None):
        directory = module_url.rsplit("/", 1)[0] + "/"
        url = public_url(urljoin(module_url, declaration["url"]), directory)
        data, row = read_http(url, PAGES)
        if not re.fullmatch(r"[0-9a-f]{64}", declaration["sha256"]) or row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Grid GMM artifact size/SHA256 differs: " + role)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(data)
        row.update(role=role, expectedTarget=target, path=str(path), declaredName=declaration["name"])
        entries, props = klib_payload(data)
        if target is not None:
            if set(props.get("native_targets", "").split()) != {target} or not any("/ir/" in name and item["size"] > 0 for name, item in entries.items()):
                raise RuntimeError("Grid HTTP Native target or IR differs: " + target)
        requests.append(row)
        return row, entries

    root = gmm(root_url, "grid-root")
    metadata = []
    payload = None
    common_variants = [variant for variant in root["variants"] if variant.get("attributes", {}).get("org.gradle.usage") == "kotlin-metadata" and variant.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == "common" and variant.get("attributes", {}).get("org.gradle.category") == "library"]
    for variant in common_variants:
        for declaration in variant.get("files", []):
            row, entries = artifact(root_url, declaration, "metadata")
            metadata.append(row)
            if payload is not None and payload != entries:
                raise RuntimeError("Multiple incompatible Grid common payloads")
            payload = entries
    if len(metadata) != 1:
        raise RuntimeError("Expected one complete Grid root metadata artifact")
    native, owners = {}, []
    for target, module in (("ohos_x64", "grid-ohosx64"), ("ohos_arm64", "grid-ohosarm64")):
        links = [variant["available-at"] for variant in root["variants"] if variant.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and variant.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and variant.get("attributes", {}).get("org.gradle.category") == "library" and "available-at" in variant]
        expected_url = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/" + module + "-" + version + ".module"
        if not links or any(link["group"] != GROUP or link["module"] != module or link["version"] != version or urljoin(root_url, link["url"]) != expected_url for link in links):
            raise RuntimeError("Grid root available-at differs: " + target)
        leaf = gmm(expected_url, module)
        if urljoin(expected_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Grid Native leaf owner URL differs")
        owners.append({"target": target, "leafModule": module, "leafUrl": expected_url, "ownerUrl": root_url})
        native[target] = []
        for variant in leaf["variants"]:
            attrs = variant.get("attributes", {})
            if attrs.get("org.jetbrains.kotlin.native.target") == target and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.gradle.category") == "library":
                for declaration in variant.get("files", []):
                    row, _ = artifact(expected_url, declaration, "native", target)
                    native[target].append(row)
        if len(native[target]) != 1:
            raise RuntimeError("Expected one API Klib for " + target)
    manifest = {"status": "ANONYMOUS_HTTP_GRAPH_AND_KLIB_BYTES_VERIFIED", "baseUrl": PAGES, "group": GROUP, "module": "grid", "version": version,
                "rootUrl": root_url, "owners": owners, "requests": requests, "metadataArtifacts": metadata, "metadataPayload": payload,
                "nativeArtifacts": native, "librarySourcesDownloaded": False}
    write_json(evidence / "remote-http-manifest.json", manifest)
    return manifest


def fetch_tools(output):
    manifest = json.loads((TEMPLATE / "toolchain-inputs.json").read_text(encoding="utf-8"))
    if manifest["sourceCommit"] != TOOL_COMMIT or len(manifest["files"]) != len(TOOL_PATHS) or {item["path"] for item in manifest["files"]} != TOOL_PATHS:
        raise RuntimeError("Consumer fixed build tool input set differs")
    tools = output / "tools"
    actual = []
    prefix = "https://raw.githubusercontent.com/qsxs/gridlayout-compose/" + TOOL_COMMIT + "/ohos/"
    for item in manifest["files"]:
        if item["url"] != prefix + item["path"] or item["path"] not in TOOL_PATHS:
            raise RuntimeError("Unexpected raw tool input")
        data, row = read_http(item["url"], prefix)
        if len(data) != item["size"] or digest(data) != item["sha256"]:
            raise RuntimeError("Pinned build tool bytes differ: " + item["path"])
        target = tools / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        actual.append({"path": item["path"], **row})
    write_json(output / "evidence/toolchain-inputs.json", {"sourceCommit": TOOL_COMMIT, "files": actual, "librarySourceCheckout": False})
    return tools


def tail(path):
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as source:
        return "".join(deque(source, maxlen=80)).encode()[-16384:].decode(errors="replace")


def verify_records(output):
    evidence = output / "evidence"
    resolution = json.loads((evidence / "consumer-resolution.json").read_text())
    if len(resolution["configurations"]) != 3:
        raise RuntimeError("Consumer resolution evidence incomplete")
    compilations = []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
        data = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text())
        if data["target"] != target or len(data["sources"]) != 1 or not data["metadataPayload"] or not data["outputs"]:
            raise RuntimeError("Consumer compilation proof is incomplete: " + name)
        if target is not None and (not data["irPayload"] or set(data["nativeTargets"]) != {target}):
            raise RuntimeError("Consumer Native proof differs: " + name)
        if target is None and not data["metadataTrace"]:
            raise RuntimeError("Consumer common metadata transform lacks root trace")
        for item in [*data["sources"], *data["outputs"]]:
            if record(Path(item["path"])) != item:
                raise RuntimeError("Consumer input/output bytes changed")
        compilations.append(data)
    write_json(evidence / "consumer-compilation.json", {"status": "ISOLATED_METADATA_AND_DUAL_ABI_CONSUMER_COMPILED", "compilations": compilations,
                                                       "link": "NOT_RUN", "runtime": "NOT_RUN"})


def main():
    output = Path(os.environ["GRID_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN"}
    code = 1
    try:
        version, source_sha = os.environ["GRID_VERSION"], os.environ["GRID_SOURCE_SHA"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}", version) or "SNAPSHOT" in version.upper() or version.upper() in ("LATEST", "RELEASE") or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise RuntimeError("A concrete immutable version and full source SHA are required")
        if version.startswith("2.8.0-cpf11-preview-") and not version.startswith("2.8.0-cpf11-preview-" + source_sha[:12] + "-"):
            raise RuntimeError("Preview version/source identifier differs")
        state.update(version=version, sourceCommit=source_sha, toolingCommit=os.environ.get("CI_TOOLING_SHA"), runId=os.environ.get("CI_RUN_ID"), runAttempt=os.environ.get("CI_RUN_ATTEMPT"))
        state["stage"] = "AnonymousHTTP"
        fetch_graph(version, output)
        state["stage"] = "PinnedBuildTools"
        tools = fetch_tools(output)
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, folder in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / folder
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)

        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError("Consumer " + label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()

        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap")]))
        properties = dict(line.split("=", 1) for line in (native / "konan/konan.properties").read_text().splitlines() if "=" in line)
        if properties.get("compilerVersion") != "2.4.20-0.1.0-08":
            raise RuntimeError("Consumer Native compilerVersion differs")
        project = output / "project"
        for name in ("settings.gradle.kts", "build.gradle.kts", "src/commonMain/kotlin/GridConsumer.kt"):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATE / name, target)
        shutil.copyfile(tools / "gradle.properties", project / "gradle.properties")
        probe = project / "src/commonMain/kotlin/GridConsumer.kt"
        args = ["sh", str(tools / "gradlew"), "-p", str(project), "--console=plain", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "remote-http-manifest.json"), "-PgridVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Consumer tasks absent from actual discovery")
                write_json(evidence / "task-discovery.json", {"required": sorted(REQUIRED), "actualTasks": sorted(names), "stdout": record(logs / "Tasks.stdout.log")})
        verify_records(output)
        state["status"] = "ISOLATED_METADATA_AND_DUAL_ABI_CONSUMER_COMPILED"
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
        for path in evidence.rglob("*.json"):
            if path.stat().st_size > 8 * 1024 * 1024:
                state.update(status="FAILED", error="Consumer structured evidence exceeds 8 MiB")
                code = 1
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
