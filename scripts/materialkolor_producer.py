"""手动 Actions 的 MaterialKolor producer；只上传已核验 staging，不发布。"""
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

from grid_remote_consumer import klib_payload
from poko_remote_consumer import fetch_graph as fetch_poko_graph
from colormath_remote_consumer import fetch_graph as fetch_colormath_graph

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
    output = Path(os.environ["MATERIALKOLOR_PRODUCER_OUTPUT"]).resolve()
    materialkolor = Path(os.environ["MATERIALKOLOR_CHECKOUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "repository": "qsxs/MaterialKolor", "link": "NOT_RUN", "runtime": "NOT_RUN"}
    failed = None
    work = output / "work"
    try:
        source, workflow = os.environ["MATERIALKOLOR_SHA"], os.environ["CI_TOOLING_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt):
            raise RuntimeError("Full source/workflow commits and positive run identifiers are required")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, name in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / name
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        for repo, expected in ((materialkolor, source), (ROOT, workflow)):
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
            print("Running MaterialKolor " + label, flush=True)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=materialkolor, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        dependency_specs = {
            "poko": ("io.github.qsxs.cpf.poko", "poko-annotations", "0.23.1", fetch_poko_graph),
            "colormath": ("io.github.qsxs.cpf.colormath", "colormath", "3.6.1", fetch_colormath_graph),
        }
        dependency_lock = {"schemaVersion": 1, "repository": "https://qsxs.github.io/cpf-maven/", "dependencies": {}}
        state["stage"] = "PublicDependencies"
        write(evidence / "run.json", state)
        for name, (group, module, base, fetch_graph) in dependency_specs.items():
            key = name.upper()
            version = os.environ["MATERIALKOLOR_" + key + "_VERSION"]
            source_commit = os.environ["MATERIALKOLOR_" + key + "_SOURCE_SHA"]
            root_sha = os.environ["MATERIALKOLOR_" + key + "_ROOT_GMM_SHA256"]
            if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or not re.fullmatch(re.escape(base) + r"-cpf11-preview-" + source_commit[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
                raise RuntimeError("Explicit public dependency version/source differs: " + name)
            if not re.fullmatch(r"[0-9a-f]{64}", root_sha):
                raise RuntimeError("Dependency GMM hash is required: " + name)
            graph = fetch_graph(version, output / "dependency-check" / name)
            root_http = graph["requests"][0]
            if graph["group"] != group or graph["module"] != module or root_http["sha256"] != root_sha:
                raise RuntimeError("Public dependency GMM differs from supplied verified identity: " + name)
            metadata = graph["metadataArtifacts"]
            if len(metadata) != 1:
                raise RuntimeError("Public metadata artifact set differs: " + name)
            artifacts = {"metadata": {"size": metadata[0]["size"], "sha256": metadata[0]["sha256"],
                                      "payload": graph["metadataPayload"]}}
            for target in ("ohos_x64", "ohos_arm64"):
                native = graph["nativeArtifacts"][target]
                if len(native) != 1:
                    raise RuntimeError("Public Native artifact set differs: " + name + ":" + target)
                payload, properties = klib_payload(Path(native[0]["path"]).read_bytes())
                if set(properties.get("native_targets", "").split()) != {target}:
                    raise RuntimeError("Public Native target differs: " + name + ":" + target)
                artifacts[target] = {"size": native[0]["size"], "sha256": native[0]["sha256"], "payload": payload}
            dependency_lock["dependencies"][name] = {
                "group": group, "module": module, "version": version, "sourceCommit": source_commit,
                "rootGmmSha256": root_sha, "artifacts": artifacts,
            }
        dependency_file = work / "dependency-versions.json"
        write(dependency_file, dependency_lock)
        state["dependencyLockSha256"] = hashlib.sha256(dependency_file.read_bytes()).hexdigest()
        state["dependencies"] = {name: {key: item[key] for key in ("group", "module", "version", "sourceCommit", "rootGmmSha256")}
                                 for name, item in dependency_lock["dependencies"].items()}

        staging = output / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        cli = [sys.executable, "-B", str(materialkolor / "ohos/MaterialKolorPort.py")]
        args = ["--source-sha", source, "--run-id", run_id, "--run-attempt", attempt,
                "--work", str(work), "--repository", str(staging), "--dependency-lock", str(dependency_file)]
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
                           output / "native-bootstrap/bootstrap-receipt.json", materialkolor / "ohos/tooling-lock.json", work / "dependency-versions.json"):
                if source.is_file():
                    collect_evidence_file(source, evidence, compressed_files)
            if (work / "evidence").is_dir():
                for source in (work / "evidence").glob("*.json"):
                    collect_evidence_file(source, evidence, compressed_files)
            if (output / "dependency-check").is_dir():
                for name in ("poko", "colormath"):
                    source_root = output / "dependency-check" / name / "evidence"
                    if source_root.is_dir():
                        for source in sorted(source_root.rglob("*.json")):
                            relative = source.relative_to(source_root)
                            target_dir = evidence / "dependencies" / name / relative.parent
                            target_dir.mkdir(parents=True, exist_ok=True)
                            before = len(compressed_files)
                            collect_evidence_file(source, target_dir, compressed_files)
                            if len(compressed_files) != before:
                                compressed_files[-1]["directory"] = target_dir.relative_to(evidence).as_posix()
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
