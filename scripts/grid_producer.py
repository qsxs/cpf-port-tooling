"""仅供手动 Actions 的单库 Grid producer；不部署，不读取令牌。"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

STAGES = ("Prepare", "Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64", "Publish", "Verify")
GROUP = "com.github.qsxs.gridlayout-compose"


class StageFailure(RuntimeError):
    def __init__(self, stage, code):
        super().__init__(stage + " failed with exit " + str(code))
        self.stage, self.code = stage, code


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tail(path):
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as source:
        lines = "".join(deque(source, maxlen=80))
    return lines.encode("utf-8")[-16384:].decode("utf-8", errors="replace")


def copy_small(source, target):
    if source.is_file():
        if source.stat().st_size > 2 * 1024 * 1024:
            raise RuntimeError("Evidence receipt exceeds 2 MiB: " + source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def collect_evidence(output, grid, work):
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    for label in ("BootstrapNative", *STAGES):
        for stream in ("stdout", "stderr"):
            text = tail(output / "command-logs" / (label + "." + stream + ".log"))
            if text:
                (evidence / (label + ".cli-" + stream + "-tail.log")).write_text(text, encoding="utf-8")
            if work is not None:
                text = tail(work / "invocations" / (label + "-1." + stream + ".log"))
                if text:
                    (evidence / (label + ".gradle-" + stream + "-tail.log")).write_text(text, encoding="utf-8")
        if work is not None:
            copy_small(work / "invocations" / (label + "-1.json"), evidence / "invocations" / (label + "-1.json"))
    for name in ("port-config.json", "metadata-toolchain.json", "commonizer-toolchain.json", "compiler-plugin-toolchain.json", "tooling-lock.json", "bootstrap-linux.json"):
        copy_small(grid / "ohos" / name, evidence / "locks" / name)
    copy_small(output / "native-bootstrap/bootstrap-receipt.json", evidence / "native-bootstrap-receipt.json")
    if work is not None:
        for name in ("publication.json", "source-manifest.json", "task-discovery.json"):
            copy_small(work / name, evidence / name)
        for stage in ("resolve", "metadata", "native-x64", "native-arm64"):
            source = work / "evidence" / (stage + ".json")
            if source.is_file():
                data = json.loads(source.read_text(encoding="utf-8"))
                summary = {key: data[key] for key in ("fingerprint", "stage", "sourceCount", "sourceSetSha256", "producers", "metadataLauncher", "commonizer", "compilerPlugins") if key in data}
                if "configurations" in data:
                    summary["configurationCounts"] = [{"name": item["configuration"], "edges": len(item["edges"]), "artifacts": len(item["artifacts"])} for item in data["configurations"]]
                write_json(evidence / (stage + "-summary.json"), summary)


def main():
    output = Path(os.environ["GRID_PRODUCER_OUTPUT"]).resolve()
    grid = Path(os.environ["GRID_CHECKOUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "STARTED", "repository": "qsxs/gridlayout-compose", "started": time.time()}
    work = None
    failed = None
    try:
        sha = os.environ["GRID_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"[0-9]+", attempt):
            raise RuntimeError("Full immutable Grid SHA and numeric run identifiers are required")
        # 子进程仅得到已需的公开宿主变量与本次隔离路径，不转发 Actions 凭据。
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, name in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            directory = output / name
            directory.mkdir(parents=True, exist_ok=True)
            env[key] = str(directory)
        actual = subprocess.run(["git", "-C", str(grid), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env).stdout.strip()
        if actual != sha:
            raise RuntimeError("Grid checkout differs from the requested immutable commit")
        version = "2.8.0-cpf11-preview-" + sha[:12] + "-" + run_id + "-" + attempt
        manifest.update(sourceCommit=sha, toolingCommit=os.environ.get("CI_TOOLING_SHA"), group=GROUP, version=version,
                        runId=run_id, runAttempt=attempt, pythonVersion=sys.version, staging="staging", workPolicy="FRESH_PER_RUN_NO_RESTORED_CACHES")
        write_json(evidence / "run.json", manifest)
        logs = output / "command-logs"
        logs.mkdir(parents=True, exist_ok=True)

        def invoke(label, argv):
            print("Running " + label, flush=True)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, cwd=grid, env=env, stdout=out, stderr=err)
            if result.returncode:
                for stream, path in (("stdout", stdout), ("stderr", stderr)):
                    print(label + " CLI " + stream + " tail:\n" + tail(path), file=sys.stderr)
                    if work is not None:
                        print(label + " Gradle " + stream + " tail:\n" + tail(work / "invocations" / (label + "-1." + stream + ".log")), file=sys.stderr)
                raise StageFailure(label, result.returncode)
            return stdout.read_text(encoding="utf-8").strip()

        native = invoke("BootstrapNative", [sys.executable, "-B", str(grid / "ohos/bootstrap-native.py"), "--destination", str(output / "native-bootstrap")])
        staging = output / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        args = ["--jdk", env["JAVA_HOME"], "--native-home", native, "--konan-data", env["KONAN_DATA_DIR"],
                "--gradle-user-home", env["GRADLE_USER_HOME"], "--work-root", str(output / "work"),
                "--group", GROUP, "--version", version, "--repository", str(staging), "--online"]
        for stage in STAGES:
            result = invoke(stage, [sys.executable, "-B", str(grid / "ohos/GridPort.py"), stage, *args])
            if stage == "Prepare":
                work = Path(json.loads(result)["work"])
                manifest["fingerprint"] = json.loads(result)["fingerprint"]
        manifest["status"] = "VERIFIED_STAGING_READY_FOR_MANUAL_REVIEW"
    except Exception as error:
        failed = error
        manifest.update(status="FAILED", error=str(error))
        if isinstance(error, StageFailure):
            manifest["failedStage"] = error.stage
    finally:
        manifest["finished"] = time.time()
        try:
            collect_evidence(output, grid, work)
        except Exception as error:
            manifest["evidenceError"] = str(error)
            if failed is None:
                failed = error
                manifest["status"] = "FAILED_EVIDENCE_COLLECTION"
        write_json(evidence / "run.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False))
    return 1 if failed is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
