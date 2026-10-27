"""手动 Actions 的 Colormath producer；只上传已核验 staging，不发布。"""
from collections import deque
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
STAGES = ("Prepare", "Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64", "Publish", "Verify")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tail(path):
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as source:
        return "".join(deque(source, maxlen=80)).encode()[-16384:].decode(errors="replace")


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


def collect_evidence_file(source, evidence, compressed_files):
    if source.stat().st_size <= 2 * 1024 * 1024:
        shutil.copyfile(source, evidence / source.name)
        return

    original_size = source.stat().st_size
    destination = evidence / (source.name + ".gz")
    if (evidence / source.name).exists():
        raise RuntimeError("Uncompressed evidence already exists: " + source.name)
    hasher = hashlib.sha256()
    size = 0
    with source.open("rb") as original, destination.open("wb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as archive:
            while True:
                chunk = original.read(1024 * 1024)
                if not chunk:
                    break
                archive.write(chunk)
                hasher.update(chunk)
                size += len(chunk)
    original_info = {"size": size, "sha256": hasher.hexdigest()}
    if size != original_size or source.stat().st_size != original_size:
        raise RuntimeError("Evidence changed during collection: " + source.name)

    with destination.open("rb") as compressed:
        with gzip.GzipFile(fileobj=compressed, mode="rb") as restored:
            if stream_digest(restored) != original_info:
                raise RuntimeError("Compressed evidence verification failed: " + source.name)
    with destination.open("rb") as compressed:
        compressed_info = stream_digest(compressed)
    compressed_files.append({
        "sourceName": source.name,
        "archiveName": destination.name,
        "originalSize": original_info["size"],
        "originalSha256": original_info["sha256"],
        "compressedSize": compressed_info["size"],
        "compressedSha256": compressed_info["sha256"],
    })


def mark_evidence_failure(state, failed, error):
    state["evidenceError"] = str(error)
    if failed is None:
        state["status"] = "FAILED_EVIDENCE_COLLECTION"
        return error
    return failed


def main():
    output = Path(os.environ["COLORMATH_PRODUCER_OUTPUT"]).resolve()
    colormath = Path(os.environ["COLORMATH_CHECKOUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "repository": "qsxs/colormath", "link": "NOT_RUN", "runtime": "NOT_RUN"}
    failed = None
    work = output / "work"
    try:
        source, workflow = os.environ["COLORMATH_SHA"], os.environ["CI_TOOLING_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt):
            raise RuntimeError("Full source/workflow commits and positive run identifiers are required")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, name in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / name
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        for repo, expected in ((colormath, source), (ROOT, workflow)):
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
            print("Running Colormath " + label, flush=True)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=colormath, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        staging = output / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        cli = [sys.executable, "-B", str(colormath / "ohos/ColormathPort.py")]
        args = ["--source-sha", source, "--run-id", run_id, "--run-attempt", attempt,
                "--work", str(work), "--repository", str(staging)]
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
            for stage in ("BootstrapNative", *STAGES):
                for stream in ("stdout", "stderr"):
                    for source in (output / "logs" / (stage + "." + stream + ".log"), work / "logs" / (stage + "." + stream + ".log")):
                        text = tail(source)
                        if text:
                            label = "gradle" if source.parent == work / "logs" else "cli"
                            (evidence / (stage + "." + label + "-" + stream + "-tail.log")).write_text(text, encoding="utf-8")
                            if failed is not None and state.get("stage") == stage:
                                print(text, file=sys.stderr)
            for source in (work / "publication.json", work / "source-manifest.json", work / "task-discovery.json",
                           output / "native-bootstrap/bootstrap-receipt.json", colormath / "ohos/tooling-lock.json"):
                if source.is_file():
                    collect_evidence_file(source, evidence, compressed_files)
            if (work / "evidence").is_dir():
                for source in (work / "evidence").glob("*.json"):
                    collect_evidence_file(source, evidence, compressed_files)
            if compressed_files:
                write(evidence / "evidence-index.json", {"schemaVersion": 1, "compressedFiles": compressed_files})
        except Exception as error:
            failed = mark_evidence_failure(state, failed, error)
        state["finished"] = time.time()
        write(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
