"""固定版本 CPF 端口使用的最小文件与 Maven 缓存快照工具。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

def physical(path):
    path = Path(path).absolute()
    return Path("\\\\?\\" + str(path)) if os.name == "nt" and not str(path).startswith("\\\\?\\") else path


def load(path):
    return json.loads(physical(path).read_text(encoding="utf-8-sig"))


def record(path, base=None):
    path = Path(path)
    item = physical(path)
    display = Path(str(path)[4:]) if str(path).startswith("\\\\?\\") else path
    return {"path": display.relative_to(base).as_posix() if base else str(display),
            "size": item.stat().st_size, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}


def write(path, value):
    path = physical(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError("Immutable preparation differs: " + str(path))
    path.write_bytes(data)


def copy_exact(source, target):
    source, target = physical(source), physical(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise RuntimeError("Existing input differs: " + str(target))
    else:
        shutil.copyfile(source, target)


def _snapshot_component(version, destination, tool, gradle_api):
    """先核单个 GAV 的必需原件和官方 URL，再允许将该组件暴露给 Gradle。"""
    from urllib.parse import unquote, urlsplit
    import xml.etree.ElementTree as ET

    version, destination = physical(version), physical(destination)
    module = version.parent.name
    gav = version.parent.parent.name + ":" + module + ":" + version.name
    files = sorted(p for p in version.rglob("*") if p.is_file())
    identities = {}
    planned, redirects, required = {}, [], []

    def identity(path):
        if path not in identities:
            data = path.read_bytes()
            identities[path] = {"size": len(data), **{key: hashlib.new(key, data).hexdigest()
                                                    for key in ("sha512", "sha256", "sha1", "md5")}}
        return identities[path]

    def unique(name):
        found = [p for p in files if p.name == name]
        if len({identity(p)["sha256"] for p in found}) > 1:
            raise ValueError("CONFLICTING_CACHE_FILES: " + name)
        return found[0] if found else None

    def relative_target(url, base, boundary):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in url:
            raise ValueError("UNSUPPORTED_ARTIFACT_URL: " + url)
        relative = unquote(parsed.path)
        if not relative or ":" in relative or Path(relative).is_absolute():
            raise ValueError("UNSUPPORTED_ARTIFACT_URL: " + url)
        target = physical(base / relative).resolve()
        if not target.is_relative_to(physical(boundary).resolve()):
            raise ValueError("ARTIFACT_URL_OUTSIDE_SNAPSHOT: " + url)
        return target

    def add(source, target, declaration=None, variant=None):
        item = {"source": str(source), "target": str(target), "size": identity(source)["size"],
                "sha256": identity(source)["sha256"], "variant": variant,
                "declaredName": declaration.get("name") if declaration else None,
                "declaredUrl": declaration.get("url") if declaration else None,
                "alias": bool(declaration and source.name != declaration["url"])}
        if target in planned and planned[target]["sha256"] != item["sha256"]:
            raise ValueError("CONFLICTING_MAVEN_TARGET: " + str(target))
        planned[target] = item

    try:
        gmm = unique(module + "-" + version.name + ".module")
        pom = unique(module + "-" + version.name + ".pom")
        if gmm:
            metadata = load(gmm)
            variants = metadata.get("variants", [])
            jvm = []
            selected = []
            for variant in variants:
                attrs = variant.get("attributes", {})
                category = attrs.get("org.gradle.category")
                if category not in ("library", "platform", "enforced-platform"):
                    continue
                platform = attrs.get("org.jetbrains.kotlin.platform.type")
                usage = attrs.get("org.gradle.usage")
                target = attrs.get("org.jetbrains.kotlin.native.target")
                if category in ("platform", "enforced-platform") and not target and usage in ("java-api", "java-runtime"):
                    selected.append(variant)
                    continue
                if ((category == "library" and platform == "common" and usage == "kotlin-metadata" and not target) or
                        (category == "library" and target in ("ohos_x64", "ohos_arm64") and
                         usage in ("kotlin-api", "kotlin-metadata", "kotlin-runtime"))):
                    selected.append(variant)
                if ((tool or gav == "androidx.arch.core:core-common:2.2.0") and
                        usage in ("java-api", "java-runtime") and platform in (None, "jvm") and not target and
                        attrs.get("org.gradle.jvm.environment") not in ("android", "non-jvm") and
                        int(attrs.get("org.gradle.jvm.version", 8)) <= 17):
                    api = tuple(int(part) for part in attrs.get("org.gradle.plugin.api-version", "0").split("."))
                    if api <= gradle_api:
                        jvm.append((variant, api, int(attrs.get("org.gradle.jvm.version", 8))))
            for usage in ("java-api", "java-runtime"):
                compatible = [entry for entry in jvm if entry[0]["attributes"].get("org.gradle.usage") == usage]
                if compatible:
                    artifact_sets = {json.dumps(entry[0].get("files", []), sort_keys=True) for entry in compatible}
                    if len(artifact_sets) > 1:
                        raise ValueError("AMBIGUOUS_COMPATIBLE_JVM_ARTIFACTS_DEFER_TO_GRADLE: " + usage)
                    selected.extend(entry[0] for entry in compatible)
            if not selected:
                raise ValueError("NO_REQUIRED_COMMON_OHOS_OR_COMPATIBLE_JVM_VARIANT")
            for variant in selected:
                required.append(variant["name"])
                redirect = variant.get("available-at")
                if redirect:
                    # available-at 原字节保留，交由 Gradle 处理，不要求重定向组件已在本地。
                    redirects.append({"variant": variant["name"], **redirect})
                    continue
                for declaration in variant.get("files", []):
                    target = relative_target(declaration["url"], destination, destination)
                    names = {declaration["name"], target.name}
                    checksums = {key: declaration[key].lower() for key in ("sha512", "sha256", "sha1", "md5") if key in declaration}
                    if not any(key in checksums for key in ("sha512", "sha256")) or "size" not in declaration:
                        raise ValueError("MISSING_DECLARED_STRONG_ARTIFACT_IDENTITY: " + declaration["url"])
                    matches = [p for p in files if p.name in names and p.stat().st_size == declaration["size"] and
                               all(identity(p)[key] == value for key, value in checksums.items())]
                    if not matches or len({identity(p)["sha256"] for p in matches}) != 1:
                        raise ValueError("MISSING_OR_MISMATCHED_REQUIRED_ARTIFACT: " + variant["name"] + ":" + declaration["url"])
                    add(matches[0], target, declaration, variant["name"])
            add(gmm, destination / gmm.name)
            if pom:
                add(pom, destination / pom.name)
        elif pom:
            tree = ET.fromstring(pom.read_bytes())
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            packaging = tree.findtext("m:packaging", default="jar", namespaces=ns)
            if packaging == "pom":
                required.append("POM_ONLY_PLATFORM_OR_PLUGIN_MARKER")
            elif packaging == "jar" and (tool or gav == "androidx.arch.core:core-common:2.2.0"):
                artifact = unique(module + "-" + version.name + ".jar")
                if artifact is None:
                    raise ValueError("MISSING_REQUIRED_POM_ONLY_JVM_JAR")
                add(artifact, destination / artifact.name)
                required.append("POM_ONLY_JVM_JAR_CACHE_IDENTITY")
            else:
                raise ValueError("UNSUPPORTED_POM_ONLY_COMPONENT: " + packaging)
            add(pom, destination / pom.name)
        else:
            raise ValueError("NO_CACHED_GMM_OR_POM")
    except (ValueError, KeyError, TypeError, ET.ParseError) as error:
        return {"gav": gav, "files": [], "requiredVariants": required, "redirects": redirects, "omission": str(error)}
    return {"gav": gav, "files": list(planned.values()), "requiredVariants": required, "redirects": redirects, "omission": None}


def mirror_cache(work, pins, *, cache_root, gradle_api, tool_allowlist):
    # 原 GMM/POM 不改字节；整个 GAV 完整预判后才复制，缺件组件留给正常同版远端解析。
    cache = physical(cache_root) if cache_root is not None else None
    work = physical(work)
    gradle_api = tuple(int(part) for part in gradle_api)
    if not gradle_api or any(not isinstance(rule, dict) for rule in tool_allowlist):
        raise ValueError("Explicit Gradle API and tool allowlist are required")
    rows, components, seen = [], [], set()
    for group in sorted(cache.iterdir()) if cache is not None and cache.is_dir() else []:
        if not group.is_dir():
            continue
        for module in sorted(group.iterdir()):
            if not module.is_dir():
                continue
            ga = group.name + ":" + module.name
            for version in sorted(module.iterdir()):
                tool = any(version.name in rule["versions"] and
                           (rule.get("group") == group.name or
                            (rule.get("groupPrefix") and group.name.startswith(rule["groupPrefix"]))) and
                           (not rule.get("modules") or module.name in rule["modules"])
                           for rule in tool_allowlist)
                if not version.is_dir() or not (pins.get(ga) == version.name or tool):
                    continue
                destination = work / "frozen-maven" / group.name.replace(".", "/") / module.name / version.name
                component = _snapshot_component(version, destination, tool, gradle_api)
                seen.add(component["gav"])
                components.append(component)
                if component["omission"]:
                    if destination.exists():
                        raise RuntimeError("Omitted component is already exposed; preserve this failed preparation: " + component["gav"])
                    continue
                for item in component["files"]:
                    copy_exact(item["source"], item["target"])
                    actual = record(item["target"])
                    if actual["size"] != item["size"] or actual["sha256"] != item["sha256"]:
                        raise RuntimeError("Snapshot source changed during preparation: " + item["source"])
                    rows.append({"gav": component["gav"], "source": item["source"], **actual})
    for ga, version in sorted(pins.items()):
        if ga + ":" + version not in seen:
            components.append({"gav": ga + ":" + version, "files": [], "requiredVariants": [], "redirects": [],
                               "omission": "CACHE_GAV_NOT_PRESENT_DEFER_TO_GRADLE"})
    write(work / "maven-snapshot.json", {"policy": "ORIGINAL_GMM_URL_LAYOUT_COMPLETE_REQUIRED_COMPONENTS_ONLY",
          "gradleApi": list(gradle_api), "components": components,
          "aliases": [item for component in components if not component["omission"] for item in component["files"] if item["alias"]],
          "omissions": [{"gav": component["gav"], "reason": component["omission"]} for component in components if component["omission"]]})
    return rows
