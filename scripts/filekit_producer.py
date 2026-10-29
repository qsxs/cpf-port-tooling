"""手动 Actions 的 FileKit producer；只交付已核验的独立 staging。"""
from collections import deque
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
KOTLIN_VERSION = "2.4.20-0.1.0-08"
GRADLE_VERSION = "8.11.1"
GRADLE_SHA256 = "f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6"
STAGES = ("Plan", "Prepare", "Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64", "Publish", "Verify")
MAX_EVIDENCE_FILES = 64
MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
SMALL_FILE_BYTES = 2 * 1024 * 1024


def write_new(path, data):
    with path.open("xb") as target:
        target.write(data)


def write_json_new(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def publish_run_evidence(output, evidence, state):
    # 在证据目录外完整写入并同步，成功后才原子地创建不可覆盖的证据链接。
    pending = output / "run-evidence.pending"
    data = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with pending.open("xb") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    os.link(pending, evidence / "run.json")


def stream_digest(stream):
    hasher = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(chunk)
        hasher.update(chunk)
    return {"size": size, "sha256": hasher.hexdigest()}


def collect_file(source, evidence, name, index, total):
    # 大日志先无损压缩并验证；超限时失败，不上传截断的“完整”日志。
    original_size = source.stat().st_size
    if original_size <= SMALL_FILE_BYTES:
        with source.open("rb") as stream:
            data = stream.read(SMALL_FILE_BYTES + 1)
        if len(data) != original_size or source.stat().st_size != original_size:
            raise RuntimeError("Evidence changed during collection: " + name)
        original = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        archive_name = name
    else:
        compressed = io.BytesIO()
        hasher = hashlib.sha256()
        size = 0
        with source.open("rb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as archive:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    archive.write(chunk)
                    size += len(chunk)
                    hasher.update(chunk)
                    if compressed.tell() > MAX_COMPRESSED_BYTES:
                        raise RuntimeError("Compressed evidence exceeds 32 MiB: " + name)
        data = compressed.getvalue()
        if len(data) > MAX_COMPRESSED_BYTES:
            raise RuntimeError("Compressed evidence exceeds 32 MiB: " + name)
        if size != original_size or source.stat().st_size != original_size:
            raise RuntimeError("Evidence changed during collection: " + name)
        original = {"size": size, "sha256": hasher.hexdigest()}
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as restored:
            if stream_digest(restored) != original:
                raise RuntimeError("Compressed evidence verification failed: " + name)
        archive_name = name + ".gz"
    if total + len(data) > MAX_TOTAL_BYTES:
        raise RuntimeError("Evidence exceeds the 128 MiB total limit")
    write_new(evidence / archive_name, data)
    index.append({
        "sourceName": name,
        "archiveName": archive_name,
        "originalSize": original["size"],
        "originalSha256": original["sha256"],
        "storedSize": len(data),
        "storedSha256": hashlib.sha256(data).hexdigest(),
    })
    return total + len(data)


def collect_evidence(output, filekit, evidence, index):
    work = output / "work"
    sources = []
    for stage in ("JavaVersion", "BootstrapNative", *STAGES):
        for stream in ("stdout", "stderr"):
            for parent, kind in ((output / "logs", "cli"), (work / "logs", "gradle")):
                path = parent / (stage + "." + stream + ".log")
                if path.is_file():
                    sources.append((path, stage + "." + kind + "-" + stream + ".log"))
    for name in ("prepared.json", "prepare-failure.json", "source-manifest.json",
                 "compiled-source-manifest.json", "provenance.json",
                 "publication-verification.json", "verification-failure.json"):
        path = work / name
        if path.is_file():
            sources.append((path, name))
    for folder, prefix in ((work / "evidence", "build-evidence-"), (work / "invocations", "invocation-")):
        if folder.is_dir():
            sources.extend((path, prefix + path.name) for path in sorted(folder.glob("*.json")) if path.is_file())
    for path, name in (
        (output / "native-bootstrap/bootstrap-receipt.json", "bootstrap-receipt.json"),
        (filekit / "ohos/tooling-lock.json", "tooling-lock.json"),
        (filekit / "ohos/port-config.json", "port-config.json"),
        (filekit / "ohos/dependency-pins.json", "dependency-pins.json"),
        (filekit / "ohos/provenance/source-map.json", "source-map.json"),
    ):
        if path.is_file():
            sources.append((path, name))
    # 为 workflow 上下文、run.json 和索引预留文件数。
    if len(sources) + 4 > MAX_EVIDENCE_FILES:
        raise RuntimeError("Evidence file count exceeds 64")
    if len({name for _, name in sources}) != len(sources):
        raise RuntimeError("Evidence names are not unique")
    total = 0
    for path, name in sources:
        total = collect_file(path, evidence, name, index, total)


def check_head(repo, expected, env):
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True, capture_output=True, text=True, env=env,
    )
    if result.stdout.strip() != expected:
        raise RuntimeError("Checkout does not match the requested commit: " + str(repo))


def check_tool_lock(filekit, tools):
    lock = json.loads((filekit / "ohos/tooling-lock.json").read_text(encoding="utf-8"))
    if lock.get("repository") != "https://github.com/qsxs/cpf-port-tooling" or lock.get("revision") != TOOL_REVISION:
        raise RuntimeError("FileKit tooling lock does not match the locked checkout")
    rows = lock.get("files", [])
    if len(rows) != 20 or len({row["path"] for row in rows}) != 20:
        raise RuntimeError("FileKit tooling lock file list differs")
    for row in rows:
        relative = row["path"]
        parts = PurePosixPath(relative)
        if (not relative.startswith(TOOL_DIR + "/") or parts.is_absolute() or
                "\\" in relative or any(part in ("", ".", "..") for part in parts.parts)):
            raise RuntimeError("Unsafe locked tooling path: " + relative)
        path = (tools / Path(*parts.parts)).resolve()
        if not path.is_relative_to(tools):
            raise RuntimeError("Locked tooling path escapes its checkout: " + relative)
        with path.open("rb") as stream:
            actual = stream_digest(stream)
        if (actual["size"], actual["sha256"]) != (row["size"], row["sha256"]):
            raise RuntimeError("Locked tooling file differs: " + relative)


def check_wrapper(filekit):
    properties = {}
    path = filekit / "ohos/gradle/wrapper/gradle-wrapper.properties"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")) and "=" in line:
            key, value = line.split("=", 1)
            if key in properties:
                raise RuntimeError("Duplicate Gradle wrapper property: " + key)
            properties[key] = value
    url = properties.get("distributionUrl", "").replace("\\:", ":")
    if (url != "https://services.gradle.org/distributions/gradle-8.11.1-bin.zip" or
            properties.get("distributionSha256Sum") != GRADLE_SHA256):
        raise RuntimeError("FileKit Gradle wrapper version or checksum differs")


def main():
    output = Path(os.environ["FILEKIT_PRODUCER_OUTPUT"]).resolve()
    filekit = Path(os.environ["FILEKIT_CHECKOUT"]).resolve()
    tools = Path(os.environ["FILEKIT_LOCKED_TOOLS"]).resolve()
    evidence = output / "evidence"
    work = output / "work"
    staging = output / "staging"
    bootstrap = output / "native-bootstrap"
    state = {
        "status": "STARTED",
        "started": time.time(),
        "repository": "qsxs/FileKit",
        "link": "NOT_RUN",
        "consumer": "NOT_RUN",
        "runtime": "NOT_RUN",
        "device": "NOT_RUN",
        "armDevice": "NOT_RUN",
        "androidIosRegression": "NOT_RUN",
        "stages": [],
        "evidenceLimits": {"files": MAX_EVIDENCE_FILES, "compressedFileBytes": MAX_COMPRESSED_BYTES,
                           "totalBytes": MAX_TOTAL_BYTES},
    }
    failed = None
    index = []
    try:
        source = os.environ["FILEKIT_SHA"]
        workflow = os.environ["CI_TOOLING_SHA"]
        run_id = os.environ["CI_RUN_ID"]
        attempt = os.environ["CI_RUN_ATTEMPT"]
        if (not re.fullmatch(r"[0-9a-f]{40}", source) or
                not re.fullmatch(r"[0-9a-f]{40}", workflow) or
                not re.fullmatch(r"[1-9][0-9]*", run_id) or
                not re.fullmatch(r"[1-9][0-9]*", attempt)):
            raise RuntimeError("Full source/workflow commits and positive run identifiers are required")
        if output.parent != Path(os.environ["RUNNER_TEMP"]).resolve() or output.name != (
                "filekit-producer-" + run_id + "-" + attempt):
            raise RuntimeError("Producer output must use the isolated runner temporary directory")
        if not evidence.is_dir() or not (evidence / "workflow-context.txt").is_file():
            raise RuntimeError("Fresh workflow diagnostics directory is required")
        if any(path.exists() for path in (work, staging, bootstrap, output / "logs",
                                          evidence / "run.json", evidence / "evidence-index.json")):
            raise RuntimeError("Producer output already contains evidence or build paths")
        for repo in (ROOT, filekit, tools):
            if repo == output or repo.is_relative_to(output) or output.is_relative_to(repo):
                raise RuntimeError("Checkouts must be separate from the producer output")
        if sys.version_info[:2] != (3, 13):
            raise RuntimeError("Python 3.13 is required")
        state.update(sourceCommit=source, workflowToolingCommit=workflow, runtimeToolingCommit=TOOL_REVISION,
                     runId=run_id, runAttempt=attempt, pythonVersion=sys.version,
                     kotlinVersion=KOTLIN_VERSION, gradleVersion=GRADLE_VERSION,
                     workPolicy="FRESH_PER_RUN_NO_RESTORED_CACHES")
        scratch = output / "scratch"
        scratch.mkdir()
        home = scratch / "home"
        temp = scratch / "temp"
        home.mkdir()
        temp.mkdir()
        env = {key: os.environ[key] for key in ("PATH", "JAVA_HOME", "LANG", "LC_ALL",
                                                 "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        if "PATH" not in env or "JAVA_HOME" not in env:
            raise RuntimeError("PATH and JAVA_HOME are required")
        env.update(HOME=str(home), TMPDIR=str(temp), TEMP=str(temp), TMP=str(temp),
                   GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", GIT_CONFIG_NOSYSTEM="1")
        for repo, expected in ((ROOT, workflow), (filekit, source), (tools, TOOL_REVISION)):
            check_head(repo, expected, env)
        check_tool_lock(filekit, tools)
        check_wrapper(filekit)
        logs = output / "logs"
        logs.mkdir()

        def run(stage, argv):
            state["stage"] = stage
            entry = {"stage": stage, "started": time.time()}
            state["stages"].append(entry)
            print("Running FileKit " + stage, flush=True)
            stdout = logs / (stage + ".stdout.log")
            stderr = logs / (stage + ".stderr.log")
            try:
                with stdout.open("xb") as out, stderr.open("xb") as err:
                    result = subprocess.run(argv, env=env, cwd=filekit, stdout=out, stderr=err, check=False)
                entry["exitCode"] = result.returncode
                if result.returncode != 0:
                    raise RuntimeError(stage + " failed with exit " + str(result.returncode))
                return stdout.read_text(encoding="utf-8").strip()
            except Exception as error:
                entry["error"] = str(error)
                raise
            finally:
                entry["finished"] = time.time()

        run("JavaVersion", [str(Path(env["JAVA_HOME"]) / "bin/java"), "-version"])
        java_output = (logs / "JavaVersion.stderr.log").read_text(encoding="utf-8")
        if not re.search(r'version "17(?:[.+"]|$)', java_output):
            raise RuntimeError("JDK 17 is required")
        native_output = run(
            "BootstrapNative",
            [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"),
             "--destination", str(bootstrap), "--kotlin-version", KOTLIN_VERSION],
        )
        native = Path(native_output).resolve()
        receipt = json.loads((bootstrap / "bootstrap-receipt.json").read_text(encoding="utf-8"))
        if (native.parent != bootstrap or not native.is_dir() or
                Path(receipt["nativeHome"]).resolve() != native or receipt["compilerVersion"] != KOTLIN_VERSION):
            raise RuntimeError("Native bootstrap output or receipt differs")
        cli = [sys.executable, "-B", str(filekit / "ohos/FileKitPort.py")]
        args = ["--source-sha", source, "--run-id", run_id, "--run-attempt", attempt,
                "--work", str(work), "--repository", str(staging),
                "--native-home", str(native), "--tooling", str(tools)]
        plan = json.loads(run("Plan", [*cli, "Plan", *args]))
        fingerprint, version = plan["fingerprint"], plan["version"]
        if (plan.get("sourceCommit") != source or plan.get("expectedToolingCommit") != TOOL_REVISION or
                not re.fullmatch(r"[0-9a-f]{64}", fingerprint) or
                not version.endswith("-" + source[:12] + "-" + run_id + "-" + attempt)):
            raise RuntimeError("FileKit plan identity differs")
        state.update(fingerprint=fingerprint, version=version)
        prepared = json.loads(run("Prepare", [*cli, "Prepare", *args]))
        if prepared.get("fingerprint") != fingerprint or prepared.get("version") != version:
            raise RuntimeError("FileKit prepare identity differs from plan")
        for stage in STAGES[2:-1]:
            run(stage, [*cli, stage, *args])
        verified = json.loads(run("Verify", [*cli, "Verify", *args]))
        if (verified.get("status") != "PRODUCER_PUBLICATION_VERIFIED_CONSUMER_RUNTIME_NOT_RUN" or
                verified.get("fingerprint") != fingerprint or verified.get("version") != version or
                verified.get("sourceCommit") != source or
                any(verified.get(key) != "NOT_RUN" for key in ("consumer", "runtime", "armDevice")) or
                not staging.is_dir() or not any(path.is_file() for path in staging.rglob("*"))):
            raise RuntimeError("FileKit publication verification identity or staging differs")
        state["status"] = "VERIFIED_STAGING_READY_FOR_MANUAL_REVIEW"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        try:
            collect_evidence(output, filekit, evidence, index)
        except Exception as error:
            state["evidenceError"] = str(error)
            if failed is None:
                failed = error
                state["status"] = "FAILED_EVIDENCE_COLLECTION"
        try:
            write_json_new(evidence / "evidence-index.json", {"schemaVersion": 1, "files": index})
        except Exception as error:
            state["evidenceIndexError"] = str(error)
            if failed is None:
                failed = error
                state["status"] = "FAILED_EVIDENCE_COLLECTION"
        state["finished"] = time.time()
        try:
            publish_run_evidence(output, evidence, state)
        except Exception as error:
            state["status"] = "FAILED_EVIDENCE_COLLECTION"
            state["finalEvidenceError"] = str(error)
            if failed is None:
                failed = error
            print("Final evidence write failed: " + str(error), file=sys.stderr)
    if failed is not None:
        print("Producer failure: " + str(failed), file=sys.stderr)
        stage = state.get("stage")
        if stage:
            for parent in (output / "logs", work / "logs"):
                path = parent / (stage + ".stderr.log")
                if path.is_file():
                    with path.open(encoding="utf-8", errors="replace") as stream:
                        tail = "".join(deque(stream, maxlen=80)).encode()[-16384:].decode(errors="ignore")
                    if tail:
                        print(tail, file=sys.stderr)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())