"""手动构建完整 Material Icons；只交付验证后的独立 staging。"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from filekit_producer import check_head, check_tool_lock, collect_file, publish_run_evidence, write_json_new

ROOT = Path(__file__).resolve().parents[1]
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
KOTLIN_VERSION = "2.4.20-0.1.0-08"
GROUP = "io.github.qsxs.cpf.materialicons"
MODULES = ("material-icons-core", "material-icons-extended")


def collect(output, source, evidence, index):
    work = output / "work"
    sources = []
    for folder, prefix in ((output / "logs", "cli-"), (work / "invocations", "invocation-"),
                           (work / "evidence", "build-")):
        if folder.is_dir():
            sources.extend((p, prefix + p.name) for p in sorted(folder.iterdir()) if p.is_file() and not p.name.endswith(".claim"))
    for path, name in (
        (work / "prepared.json", "prepared.json"),
        (work / "source-manifest.json", "source-manifest.json"),
        (work / "build-provenance.json", "build-provenance.json"),
        (work / "tooling-verification.json", "tooling-verification.json"),
        (work / "task-discovery.json", "task-discovery.json"),
        (work / "publication.json", "publication.json"),
        (output / "native-bootstrap/bootstrap-receipt.json", "bootstrap-receipt.json"),
        (source / "ohos/tooling-lock.json", "tooling-lock.json"),
        (source / "ohos/source-inputs.json", "source-inputs.json"),
        (source / "ohos/original-port-inputs.json", "original-port-inputs.json"),
    ):
        if path.is_file():
            sources.append((path, name))
    if len(sources) > 120 or len({name for _, name in sources}) != len(sources):
        raise RuntimeError("Evidence file count or names differ")
    total = 0
    errors = []
    for path, name in sources:
        try:
            total = collect_file(path, evidence, name, index, total)
        except Exception as error:
            errors.append(name + ": " + str(error))
            # 原文件过大时仍保留有明确标记的末尾诊断，不冒充完整日志。
            if name.endswith(".log"):
                with path.open(encoding="utf-8", errors="replace") as stream:
                    tail = "".join(deque(stream, maxlen=120)).encode()[-32768:]
                (evidence / (name + ".tail")).write_bytes(tail)
    if errors:
        raise RuntimeError("Evidence collection failed: " + "; ".join(errors))


def main():
    output = Path(os.environ["ICONS_PRODUCER_OUTPUT"]).resolve()
    source = Path(os.environ["ICONS_CHECKOUT"]).resolve()
    tools = Path(os.environ["ICONS_LOCKED_TOOLS"]).resolve()
    evidence, work, staging = output / "evidence", output / "work", output / "staging"
    bootstrap = output / "native-bootstrap"
    state = {"status": "STARTED", "started": time.time(), "repository": "qsxs/compose-multiplatform-core",
             "group": GROUP, "link": "NOT_RUN", "consumer": "NOT_RUN", "runtime": "NOT_RUN",
             "device": "NOT_RUN", "androidIosRegression": "NOT_RUN", "stages": []}
    failed = None
    index = []
    try:
        sha, workflow = os.environ["ICONS_SOURCE_SHA"], os.environ["CI_TOOLING_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if (not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or
                not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt)):
            raise RuntimeError("Full commits and positive run identifiers are required")
        if (output.parent != Path(os.environ["RUNNER_TEMP"]).resolve() or
                output.name != "material-icons-producer-" + run_id + "-" + attempt or
                not evidence.is_dir() or not (evidence / "workflow-context.txt").is_file()):
            raise RuntimeError("Fresh isolated workflow diagnostics are required")
        if any(path.exists() for path in (work, staging, bootstrap, output / "logs", output / "scratch", evidence / "run.json")):
            raise RuntimeError("Producer paths must be fresh")
        if any(repo == output or repo.is_relative_to(output) or output.is_relative_to(repo) for repo in (ROOT, source, tools)):
            raise RuntimeError("Checkouts and output must be separate")
        if sys.version_info[:2] != (3, 13):
            raise RuntimeError("Python 3.13 is required")
        version = "1.7.3-cpf11-preview-" + sha[:12] + "-" + run_id + "-" + attempt
        state.update(sourceCommit=sha, version=version, workflowToolingCommit=workflow,
                     runtimeToolingCommit=TOOL_REVISION, runId=run_id, runAttempt=attempt,
                     pythonVersion=sys.version, kotlinVersion=KOTLIN_VERSION, gradleVersion="9.5.0",
                     workPolicy="FRESH_PER_RUN_NO_RESTORED_CACHES")
        scratch = output / "scratch"
        scratch.mkdir()
        for name in ("home", "temp", "gradle-home", "konan"):
            (scratch / name).mkdir()
        env = {key: os.environ[key] for key in ("PATH", "JAVA_HOME", "LANG", "LC_ALL",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        if "PATH" not in env or "JAVA_HOME" not in env:
            raise RuntimeError("PATH and JAVA_HOME are required")
        env.update(HOME=str(scratch / "home"), TMPDIR=str(scratch / "temp"), TEMP=str(scratch / "temp"),
                   TMP=str(scratch / "temp"), GRADLE_USER_HOME=str(scratch / "gradle-home"),
                   KONAN_DATA_DIR=str(scratch / "konan"), GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
                   GIT_CONFIG_NOSYSTEM="1")
        for repo, expected in ((ROOT, workflow), (source, sha), (tools, TOOL_REVISION)):
            check_head(repo, expected, env)
        check_tool_lock(source, tools)
        logs = output / "logs"
        logs.mkdir()

        def run(label, argv):
            state["stage"] = label
            item = {"stage": label, "argv": argv, "started": time.time(), "exitCode": None}
            state["stages"].append(item)
            print("Running Material Icons producer " + label, flush=True)
            try:
                with (logs / (label + ".stdout.log")).open("xb") as out, (logs / (label + ".stderr.log")).open("xb") as err:
                    result = subprocess.run(argv, cwd=source, env=env, stdout=out, stderr=err, check=False)
                item["exitCode"] = result.returncode
                if result.returncode:
                    raise RuntimeError(label + " failed with exit " + str(result.returncode))
                return (logs / (label + ".stdout.log")).read_text(encoding="utf-8").strip()
            except Exception as error:
                item["error"] = str(error)
                raise
            finally:
                item["finished"] = time.time()

        run("JavaVersion", [str(Path(env["JAVA_HOME"]) / "bin/java"), "-version"])
        if not re.search(r'version "17(?:[.+"]|$)', (logs / "JavaVersion.stderr.log").read_text(encoding="utf-8")):
            raise RuntimeError("JDK 17 is required")
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"),
                     "--destination", str(bootstrap), "--kotlin-version", KOTLIN_VERSION])).resolve()
        receipt = json.loads((bootstrap / "bootstrap-receipt.json").read_text(encoding="utf-8"))
        if (native.parent != bootstrap or not native.is_dir() or Path(receipt["nativeHome"]).resolve() != native or
                receipt["compilerVersion"] != KOTLIN_VERSION):
            raise RuntimeError("Native bootstrap output or receipt differs")
        cli = [sys.executable, "-B", str(source / "ohos/MaterialIconsPort.py")]
        args = ["--source-sha", sha, "--run-id", run_id, "--run-attempt", attempt,
                "--work", str(work), "--repository", str(staging), "--native-home", str(native), "--tooling", str(tools)]
        plan = json.loads(run("Plan", [*cli, "Plan", *args]))
        fingerprint = plan.get("fingerprint")
        if (plan.get("sourceCommit") != sha or plan.get("group") != GROUP or plan.get("version") != version or
                plan.get("expectedToolingCommit") != TOOL_REVISION or plan.get("recipeMatchesCommit") is not True or
                not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint) or
                plan.get("versions") != {module: version for module in MODULES}):
            raise RuntimeError("Material Icons plan identity differs")
        state.update(fingerprint=fingerprint, sourceFacts=plan["sourceFacts"])
        stages = [("Prepare", None), ("Tasks", None), ("Resolve", None)]
        stages += [(stage, module) for stage in ("Metadata", "NativeX64", "NativeArm64") for module in ("Core", "Extended")]
        stages += [("Publish", None), ("Verify", None)]
        for stage, module in stages:
            label = stage + ("-" + module if module else "")
            result = json.loads(run(label, [*cli, stage, *args, *(["--module", module] if module else [])]))
            if result.get("stage") != stage or result.get("fingerprint") != fingerprint:
                raise RuntimeError("Stage identity differs: " + label)
            if stage == "Verify" and result.get("publication") != "PUBLISHED_COORDINATES_AND_BYTES_VERIFIED_RUNTIME_NOT_RUN":
                raise RuntimeError("Publication verification did not report success")
        publication = json.loads((work / "publication.json").read_text(encoding="utf-8"))
        if (publication.get("sourceCommit") != sha or publication.get("version") != version or
                publication.get("group") != GROUP or publication.get("fingerprint") != fingerprint or
                len(publication.get("compilations", [])) != 6 or not staging.is_dir() or
                not any(path.is_file() for path in staging.rglob("*"))):
            raise RuntimeError("Publication identity or staging differs")
        state["status"] = "VERIFIED_STAGING_READY_FOR_MANUAL_REVIEW"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        try:
            collect(output, source, evidence, index)
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
            state["finalEvidenceError"] = str(error)
            failed = failed or error
            print("Final evidence write failed: " + str(error), file=sys.stderr)
    if failed:
        print("Producer failure: " + str(failed), file=sys.stderr)
        label = state.get("stage")
        if label and (output / "logs" / (label + ".stderr.log")).is_file():
            with (output / "logs" / (label + ".stderr.log")).open(encoding="utf-8", errors="replace") as stream:
                print("".join(deque(stream, maxlen=80)).encode()[-16384:].decode(errors="replace"), file=sys.stderr)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
