"""手动 Actions 的 Calendar producer；只上传已核验 staging，不发布。"""
from collections import deque
import gzip
from http.client import IncompleteRead
import io
import hashlib
import json
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import tarfile
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
STAGES = ("Prepare", "Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64", "Publish", "Verify")
# 保留完整签名输出；无损压缩后超限即失败，绝不上传截断内容。
MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
MAX_EVIDENCE_FILES = 64
MAX_SYSROOT_ATTEMPTS = 3
APPROVED_SYSROOT = {'url': 'https://maven.eazytec-cloud.com/nexus/repository/file-storage/sysroot-ohos-26.0.0.38-01.tar.gz',
 'size': 12199536,
 'sha256': '8f37196b1c1aaadc5684a49e2776db6320747403902d980c8c678a8156a3a619',
 'archiveRoot': 'sysroot-ohos-26.0.0.38-01',
 'files': [{'path': 'usr/lib/aarch64-linux-ohos/libicu.so',
            'size': 31112,
            'sha256': '3d6c6c4f2ff7bc866e0388ba27e7f890bf4f6f973f28ee0d766b6e9298d86e21'},
           {'path': 'usr/lib/x86_64-linux-ohos/libicu.so',
            'size': 35528,
            'sha256': '67f21ee3ac3f035d83ffccd7fe66200f76bb4c1a022e1cefeec69a60fb218cb3'},
           {'path': 'usr/include/unicode/ucal.h',
            'size': 62926,
            'sha256': '872305a5c1cce318780e07f29841b0e8dbaeb37c4802e85719551a92eb2fb5f2'},
           {'path': 'usr/include/unicode/uloc.h',
            'size': 56986,
            'sha256': 'f317b1bc0ff44cd7924706296981276c1a41154dd70040e2060037602bff7413'},
           {'path': 'usr/include/unicode/utypes.h',
            'size': 29638,
            'sha256': '5ca8441d683f931f84f9beb3c2136e971e463297ca51d8e21812015a3f994663'}]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tail(path):
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as source:
        return "".join(deque(source, maxlen=80)).encode()[-16384:].decode(errors="ignore")


def head(path):
    if not path.is_file():
        return ""
    with path.open("rb") as source:
        data = source.read(16 * 1024)
    return data.decode("utf-8", errors="replace").encode("utf-8")[:16 * 1024].decode("utf-8", errors="ignore")


def stream_digest(stream):
    hasher = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        hasher.update(chunk)
    return {"size": size, "sha256": hasher.hexdigest()}


def collect_evidence_file(source, evidence, compressed_files, name=None):
    name = name or source.name
    if source.stat().st_size <= 2 * 1024 * 1024:
        shutil.copyfile(source, evidence / name)
        return

    original_size = source.stat().st_size
    destination = evidence / (name + ".gz")
    if (evidence / name).exists():
        raise RuntimeError("Uncompressed evidence already exists: " + name)
    hasher = hashlib.sha256()
    size = 0
    compressed = io.BytesIO()
    with source.open("rb") as original:
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as archive:
            while True:
                chunk = original.read(1024 * 1024)
                if not chunk:
                    break
                archive.write(chunk)
                hasher.update(chunk)
                size += len(chunk)
                if compressed.tell() > MAX_COMPRESSED_BYTES:
                    raise RuntimeError("Compressed evidence exceeds 32 MiB: " + name)
    data = compressed.getvalue()
    if len(data) > MAX_COMPRESSED_BYTES:
        raise RuntimeError("Compressed evidence exceeds 32 MiB: " + name)
    original_info = {"size": size, "sha256": hasher.hexdigest()}
    if size != original_size or source.stat().st_size != original_size:
        raise RuntimeError("Evidence changed during collection: " + name)
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as restored:
        if stream_digest(restored) != original_info:
            raise RuntimeError("Compressed evidence verification failed: " + name)
    with destination.open("xb") as target:
        target.write(data)
    compressed_files.append({
        "sourceName": name,
        "archiveName": destination.name,
        "originalSize": original_info["size"],
        "originalSha256": original_info["sha256"],
        "compressedSize": len(data),
        "compressedSha256": hashlib.sha256(data).hexdigest(),
    })


def mark_evidence_failure(state, failed, error):
    state["evidenceError"] = str(error)
    if failed is None:
        state["status"] = "FAILED_EVIDENCE_COLLECTION"
        return error
    return failed


def validate_sysroot_archive(data, candidate):
    if len(data) != candidate["size"] or hashlib.sha256(data).hexdigest() != candidate["sha256"]:
        raise RuntimeError("CPF sysroot archive bytes differ")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        for item in members:
            path = PurePosixPath(item.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != candidate["archiveRoot"] or
                    "\\" in item.name or "\x00" in item.name or not (item.isfile() or item.isdir() or item.issym() or item.islnk())):
                raise RuntimeError("Unsafe CPF sysroot archive entry: " + item.name)
            if item.issym() or item.islnk():
                if not item.linkname or PurePosixPath(item.linkname).is_absolute() or "\\" in item.linkname or "\x00" in item.linkname:
                    raise RuntimeError("Unsafe CPF sysroot archive link: " + item.name)
                parent = posixpath.dirname(item.name) if item.issym() else ""
                target = posixpath.normpath(posixpath.join(parent, item.linkname))
                if target != candidate["archiveRoot"] and not target.startswith(candidate["archiveRoot"] + "/"):
                    raise RuntimeError("CPF sysroot archive link escapes root: " + item.name)
        return {"archiveMemberCount": len(members), "regularFileCount": sum(item.isfile() for item in members),
                "directoryCount": sum(item.isdir() for item in members), "linkCount": sum(item.issym() or item.islnk() for item in members)}


def download_sysroot(output, candidate):
    evidence = output / "evidence"
    attempts = []
    receipt = evidence / "sysroot-download-attempts.json"
    opener = build_opener(ProxyHandler({}))
    for attempt in range(1, MAX_SYSROOT_ATTEMPTS + 1):
        try:
            with opener.open(Request(candidate["url"], headers={"User-Agent": "Calendar-CPF-Sysroot-Input"}), timeout=60) as response:
                if response.status != 200 or response.geturl() != candidate["url"]:
                    raise RuntimeError("CPF sysroot archive response differs")
                data = response.read(candidate["size"] + 1)
            if len(data) < candidate["size"]:
                raise IncompleteRead(data, candidate["size"] - len(data))
            if len(data) > candidate["size"]:
                raise RuntimeError("CPF sysroot archive response exceeds pinned size")
        except (HTTPError, URLError, IncompleteRead, TimeoutError, ConnectionError, OSError) as error:
            retryable = not isinstance(error, HTTPError) or error.code in (408, 425, 429) or 500 <= error.code <= 599
            row = {"attempt": attempt, "status": "TRANSPORT_FAILED", "errorType": type(error).__name__, "error": str(error), "retryable": retryable}
            if isinstance(error, IncompleteRead):
                row["partialBytes"] = len(error.partial)
            attempts.append(row)
            write(receipt, {"url": candidate["url"], "attempts": attempts})
            print("CPF sysroot download attempt " + str(attempt) + " failed: " + str(error), file=sys.stderr, flush=True)
            if not retryable or attempt == MAX_SYSROOT_ATTEMPTS:
                raise RuntimeError("CPF sysroot download failed on attempt " + str(attempt) + ": " + str(error)) from error
            time.sleep(2 * attempt)
            continue
        except RuntimeError as error:
            attempts.append({"attempt": attempt, "status": "REJECTED", "error": str(error)})
            write(receipt, {"url": candidate["url"], "attempts": attempts})
            raise
        attempts.append({"attempt": attempt, "status": "RECEIVED", "bytes": len(data)})
        write(receipt, {"url": candidate["url"], "attempts": attempts})
        return data, attempts
    raise RuntimeError("CPF sysroot download did not complete")


def bootstrap_sysroot(output, candidate):
    if candidate != APPROVED_SYSROOT:
        raise RuntimeError("Calendar sysroot lock differs from the approved CPF input")
    destination = output / "sysroot-input"
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise RuntimeError("Existing sysroot input; use a fresh run")
    destination.mkdir(parents=True, exist_ok=True)
    data, attempts = download_sysroot(output, candidate)
    archive_path = destination / (candidate["archiveRoot"] + ".tar.gz")
    with archive_path.open("xb") as saved:
        saved.write(data)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    attempts[-1].update(sha256=actual_sha256, status="VERIFIED" if actual_sha256 == candidate["sha256"] else "HASH_MISMATCH")
    write(output / "evidence/sysroot-download-attempts.json", {"url": candidate["url"], "attempts": attempts})
    counts = validate_sysroot_archive(data, candidate)
    sysroot = destination / candidate["archiveRoot"]
    if sysroot.exists() or sysroot.is_symlink():
        raise RuntimeError("Existing sysroot extraction; use a fresh run")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        archive.extractall(destination, filter="data")
    selected = []
    for item in candidate["files"]:
        path = sysroot / item["path"]
        content = path.read_bytes()
        if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise RuntimeError("CPF sysroot selected input differs: " + item["path"])
        selected.append({"path": item["path"], "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return sysroot, {"url": candidate["url"], "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     **counts, "downloadAttempts": attempts, "selectedInputs": selected, "libraryBundled": False,
                     "role": "EXTERNAL_CINTEROP_INPUT", "nativeDependencyCache": "NO_MANUAL_PREFILL_STANDARD_KONAN_ON_DEMAND",
                     "abiOrRuntimeEquivalence": "NOT_ESTABLISHED", "runtime": "NOT_RUN"}


def main():
    output = Path(os.environ["CALENDAR_PRODUCER_OUTPUT"]).resolve()
    calendar = Path(os.environ["CALENDAR_CHECKOUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    if (evidence / "run.json").exists():
        raise RuntimeError("Existing Calendar producer evidence; use a fresh run")
    state = {"status": "STARTED", "started": time.time(), "repository": "qsxs/Calendar", "link": "NOT_RUN", "runtime": "NOT_RUN"}
    failed = None
    work = output / "work"
    try:
        source, workflow = os.environ["CALENDAR_SHA"], os.environ["CI_TOOLING_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt):
            raise RuntimeError("Full source/workflow commits and positive run identifiers are required")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, name in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / name
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        for repo, expected in ((calendar, source), (ROOT, workflow)):
            actual = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env).stdout.strip()
            if actual != expected:
                raise RuntimeError("Checkout does not match the requested commit: " + str(repo))
        state.update(sourceCommit=source, workflowToolingCommit=workflow, runtimeToolingCommit=TOOL_REVISION,
                     runId=run_id, runAttempt=attempt, pythonVersion=sys.version,
                     workPolicy="FRESH_PER_RUN_NO_RESTORED_CACHES")
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write(evidence / "run.json", state)
            print("Running Calendar " + label, flush=True)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            with stdout.open("xb") as out, stderr.open("xb") as err:
                result = subprocess.run(argv, env=env, cwd=calendar, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip() if label in ("Prepare", "BootstrapNative") else None
        state["stage"] = "PinnedSysroot"
        write(evidence / "run.json", state)
        sysroot_lock = json.loads((calendar / "ohos/sysroot-input.json").read_text(encoding="utf-8"))
        sysroot, sysroot_receipt = bootstrap_sysroot(output, sysroot_lock["candidate"])
        write(evidence / "sysroot-bootstrap.json", sysroot_receipt)
        staging = output / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        cli = [sys.executable, "-B", str(calendar / "ohos/CalendarPort.py")]
        args = ["--source-sha", source, "--run-id", run_id, "--run-attempt", attempt,
                "--work", str(work), "--repository", str(staging), "--sysroot", str(sysroot), "--sysroot-kind", "cpf"]
        prepared = json.loads(run("Prepare", [*cli, "Prepare", *args]))
        tools = Path(prepared["toolingHome"])
        if tools.name != TOOL_REVISION:
            raise RuntimeError("Runtime tool directory does not match its locked revision")
        native = run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"),
                                        "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"])
        args += ["--native-home", native]
        state.update(fingerprint=prepared["fingerprint"], version=prepared["version"])
        for stage in STAGES[1:]:
            run(stage, [*cli, stage, *args])
        state["status"] = "VERIFIED_STAGING_READY_FOR_MANUAL_REVIEW"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        try:
            compressed_files = []
            for stage in ("PinnedSysroot", "BootstrapNative", *STAGES):
                for stream in ("stdout", "stderr"):
                    for source in (output / "logs" / (stage + "." + stream + ".log"), work / "logs" / (stage + "." + stream + ".log")):
                        label = "gradle" if source.parent == work / "logs" else "cli"
                        text = tail(source)
                        if text:
                            (evidence / (stage + "." + label + "-" + stream + "-tail.log")).write_text(text, encoding="utf-8")
                            if failed is not None and state.get("stage") == stage:
                                print(text, file=sys.stderr)
                        if stream == "stderr" and failed is not None and state.get("stage") == stage:
                            try:
                                prefix = head(source)
                                if prefix:
                                    (evidence / (stage + "." + label + "-stderr-head.log")).write_text(prefix, encoding="utf-8")
                            except OSError as error:
                                state.setdefault("logCaptureWarnings", []).append(
                                    {"stage": stage, "source": label, "errorType": type(error).__name__}
                                )
            sources = [(path, path.name) for path in (work / "publication.json", work / "source-manifest.json", work / "provenance.json",
                           work / "prepared.json", work / "task-discovery.json", output / "native-bootstrap/bootstrap-receipt.json",
                           calendar / "ohos/tooling-lock.json", calendar / "ohos/sysroot-input.json") if path.is_file()]
            if (work / "evidence").is_dir():
                sources.extend((path, path.name) for path in sorted((work / "evidence").glob("*.json")) if path.is_file())
            if (work / "invocations").is_dir():
                sources.extend((path, path.name) for path in sorted((work / "invocations").iterdir()) if path.is_file())
            if failed is not None and state.get("stage"):
                stage = state["stage"]
                for stream in ("stdout", "stderr"):
                    for parent, label in ((output / "logs", "cli"), (work / "logs", "gradle")):
                        path = parent / (stage + "." + stream + ".log")
                        if path.is_file():
                            sources.append((path, stage + "." + label + "-" + stream + ".full.log"))
            if len(sources) > MAX_EVIDENCE_FILES:
                raise RuntimeError("Evidence file count exceeds 64")
            for source, name in sources:
                collect_evidence_file(source, evidence, compressed_files, name)
        except Exception as error:
            failed = mark_evidence_failure(state, failed, error)
        finally:
            if compressed_files:
                try:
                    write(evidence / "evidence-index.json", {"schemaVersion": 1, "compressedFiles": compressed_files})
                except Exception as error:
                    failed = mark_evidence_failure(state, failed, error)
        state["finished"] = time.time()
        write(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
