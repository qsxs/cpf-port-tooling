"""匿名 Pages Calendar 消费者；只取公开制品与固定工具，不取库源码。"""
from __future__ import annotations

from collections import deque
import hashlib
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET
import zipfile

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
            with opener.open(Request(url, headers={"User-Agent": "Calendar-Pages-Anonymous-Acceptance"}), timeout=60) as response:
                declared = response.headers.get("Content-Length")
                length = int(declared) if declared is not None else None
                if length is not None and length > 64 * 1024 * 1024:
                    raise RuntimeError("Anonymous artifact response exceeds the Calendar limit")
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
        raise RuntimeError("Downloaded Calendar artifact has no Klib metadata payload")
    return entries, properties


def tail(path):
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", errors="replace") as source:
        return "".join(deque(source, maxlen=80)).encode()[-16384:].decode(errors="ignore")

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.calendar"
MODULE = "compose-multiplatform"
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
WRAPPER_COMMIT = "03ea871e06df80e2bd96bb11f94c0b389c07be15"

TOOL_LOCK = {'schemaVersion': 1,
 'repository': 'https://github.com/qsxs/cpf-port-tooling',
 'revision': 'd0cff88fd1ea2e4f08bb4409f1c802cca0c7f285',
 'archiveUrl': 'https://github.com/qsxs/cpf-port-tooling/archive/d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285.tar.gz',
 'identityPolicy': 'COMMIT_AND_INDIVIDUAL_FILE_SIZE_SHA256',
 'files': [{'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/bootstrap-linux.json',
            'size': 625,
            'sha256': 'c094380a4ade09483b0bfee4d0a3e72de27d0dd3d3d72d23799824946f4fc7a6'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/bootstrap-native.py',
            'size': 3699,
            'sha256': 'd33253c94e0cbba26a38bbeb6e06244a9038c1caec921eb72cf9f4493d0a4163'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/commonizer-toolchain.json',
            'size': 1283,
            'sha256': 'fb9ad59f80e8057fdc2422dc4ccacff9d54ea3ad261f83962434812f72d1685b'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/metadata-toolchain.json',
            'size': 2195,
            'sha256': 'db18a9dbf5253532369ee76dd4f62a9160bb3a498b0c33f23aff13720b93b4dd'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/native-compiler-toolchain.json',
            'size': 12577,
            'sha256': '4c1d515a19c8618be34243205b919301ac716f8d6dc683aa42980b690203802f'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/kotlin-klib-commonizer-embeddable-2.4.20-0.1.0-08.pom',
            'size': 1657,
            'sha256': '63572fb57b2546f41b191cb8606db980824918173c070aa8b97018f76f981c46'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/annotations-23.0.0.pom',
            'size': 1354,
            'sha256': 'c9490f655132328df2cfbcfdf743f53fc3916d6c1d10437175a6ca6e3a67771c'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-build-tools-api-2.4.20-0.1.0-08.pom',
            'size': 1146,
            'sha256': '0c92c737538279dce88476b7d3bd06cbddb4f939b731566b539d13588589f579'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-build-tools-compat-2.4.20-0.1.0-08.pom',
            'size': 1392,
            'sha256': 'e75e821de06e320b924d3b16da9744ff1aaa86f9f4f17911016efca18b2b39d9'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-build-tools-cri-impl-2.4.20-0.1.0-08.pom',
            'size': 1597,
            'sha256': '1a061cdf4b67673d2cf893bf5bf141468c997564a5ff0d1d565825b9f6488f2a'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-build-tools-impl-2.4.20-0.1.0-08.pom',
            'size': 2411,
            'sha256': '9890c4b0206b609c15e06434fa5e00ed14319c43951fbbed32c29c15a3f5a704'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-compiler-embeddable-2.4.20-0.1.0-08.pom',
            'size': 2692,
            'sha256': '448c9621d4b0a4f03b446f0fbacfdad0b7d5bba7f028c60e65a5b88f7a8a83cb'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-compiler-runner-2.4.20-0.1.0-08.pom',
            'size': 1951,
            'sha256': '8b636f0efcd09742dffeaa7e00611ee92d1bcff6c050e418e272ee102921cf35'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-daemon-client-2.4.20-0.1.0-08.pom',
            'size': 1362,
            'sha256': '6554544779db9a147aec2b6a343da69796c872280750320c2929b673252af7e9'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-daemon-embeddable-2.4.20-0.1.0-08.pom',
            'size': 1182,
            'sha256': '6776aaee9ff9abda0150adf23d522c5b1a53dcf6d35e78c7f65560f5163f9128'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-reflect-1.6.10.pom',
            'size': 1375,
            'sha256': '57905524274a00ae028aaccc27283f6bc5925a934a046c1cc5d06c8ee4d6d5a9'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-script-runtime-2.4.20-0.1.0-08.pom',
            'size': 1143,
            'sha256': '9126f7d26568d0ce52dce9ab2ef8dd9d0f199617a4a3452cff62dfa80774b94a'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-stdlib-2.4.20-0.1.0-08.pom',
            'size': 2319,
            'sha256': '95fa99bc5463f6d8293c5ec09732b9088189a99fd5988025da3bda35f0736854'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlin-tooling-core-2.4.20-0.1.0-08.pom',
            'size': 1137,
            'sha256': '2b51096477fc8eb79b3cf9c120d760cd7f5759f896d8e968b636e5cf4418927f'},
           {'path': 'toolchains/kotlin-native/2.4.20-0.1.0-08/vendor/native-compiler-host/kotlinx-coroutines-core-jvm-1.8.0.pom',
            'size': 2196,
            'sha256': 'a5633abd53467ceb91622d81f2e982080877145e0b76e1b75788715434885d0b'}]}
WRAPPER_INPUTS = {'schemaVersion': 1,
 'sourceRepository': 'qsxs/Calendar',
 'sourceCommit': '03ea871e06df80e2bd96bb11f94c0b389c07be15',
 'files': [{'path': 'gradlew',
            'size': 363,
            'sha256': '0e96228f9589965a5e171190f69f6e820f128bdae180f7e2acc6e4d65f788ed5',
            'url': 'https://raw.githubusercontent.com/qsxs/Calendar/03ea871e06df80e2bd96bb11f94c0b389c07be15/ohos/gradlew'},
           {'path': 'gradle/wrapper/gradle-wrapper.jar',
            'size': 43764,
            'sha256': '7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172',
            'url': 'https://raw.githubusercontent.com/qsxs/Calendar/03ea871e06df80e2bd96bb11f94c0b389c07be15/ohos/gradle/wrapper/gradle-wrapper.jar'},
           {'path': 'gradle/wrapper/gradle-wrapper.properties',
            'size': 339,
            'sha256': '93b4f2c5ddcfc9e6f630fc7e004b31b389695cd0228be6da42e196e5d4af7acb',
            'url': 'https://raw.githubusercontent.com/qsxs/Calendar/03ea871e06df80e2bd96bb11f94c0b389c07be15/ohos/gradle/wrapper/gradle-wrapper.properties'},
           {'path': 'gradle.properties',
            'size': 332,
            'sha256': '2080798d1a7ef5cc29db9107cdf49c4313328c30c40a8bad0a82b50f876cbc9e',
            'url': 'https://raw.githubusercontent.com/qsxs/Calendar/03ea871e06df80e2bd96bb11f94c0b389c07be15/ohos/gradle.properties'}]}
PINS = {'org.jetbrains.androidx.graphics:graphics-shapes': '1.1.0-0.1.0-11',
 'org.jetbrains.androidx.graphics:graphics-shapes-ohosarm64': '1.1.0-0.1.0-11',
 'org.jetbrains.androidx.graphics:graphics-shapes-ohosx64': '1.1.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-common': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-common-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-common-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime-compose': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime-compose-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime-compose-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-runtime-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-compose': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-compose-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-compose-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-savedstate': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-savedstate-ohosarm64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-savedstate-ohosx64': '2.11.0-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent-compose': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent-compose-ohosarm64': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent-compose-ohosx64': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent-ohosarm64': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.navigationevent:navigationevent-ohosx64': '1.1.1-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate': '1.5.0-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate-compose': '1.5.0-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate-compose-ohosarm64': '1.5.0-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate-compose-ohosx64': '1.5.0-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate-ohosarm64': '1.5.0-0.1.0-11',
 'org.jetbrains.androidx.savedstate:savedstate-ohosx64': '1.5.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation-core': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation-core-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation-core-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.animation:animation-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.annotation-internal:annotation': '1.9.1-0.1.0-11',
 'org.jetbrains.compose.annotation-internal:annotation-ohosarm64': '1.9.1-0.1.0-11',
 'org.jetbrains.compose.annotation-internal:annotation-ohosx64': '1.9.1-0.1.0-11',
 'org.jetbrains.compose.collection-internal:collection': '1.5.0-0.1.0-11',
 'org.jetbrains.compose.collection-internal:collection-ohosarm64': '1.5.0-0.1.0-11',
 'org.jetbrains.compose.collection-internal:collection-ohosx64': '1.5.0-0.1.0-11',
 'org.jetbrains.compose.components:components-resources': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.components:components-resources-ohosArm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.components:components-resources-ohosX64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.export:export': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.export:export-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.export:export-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material3:material3': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material3:material3-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material3:material3-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material:material-ripple': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material:material-ripple-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.material:material-ripple-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-annotation': '1.9.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-annotation-ohosarm64': '1.9.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-annotation-ohosx64': '1.9.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-retain': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-retain-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-retain-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-saveable': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-saveable-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.runtime:runtime-saveable-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-arkui': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-arkui-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-arkui-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-backhandler': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-backhandler-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-backhandler-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-geometry': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-geometry-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-geometry-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-graphics': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-graphics-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-graphics-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-text': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-text-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-text-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-unit': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-unit-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-unit-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-util': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-util-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.ui:ui-util-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.kotlin:atomicfu': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-build-tools-api': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-gradle-plugin-annotations': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-gradle-plugin-api': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-gradle-plugins-bom': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-native-utils': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-stdlib': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-tooling-core': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlin:kotlin-util-io': '2.4.20-0.1.0-08',
 'org.jetbrains.kotlinx:atomicfu': '0.33.0-0.1.0-07',
 'org.jetbrains.kotlinx:atomicfu-ohosarm64': '0.33.0-0.1.0-07',
 'org.jetbrains.kotlinx:atomicfu-ohosx64': '0.33.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-coroutines-bom': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-coroutines-core': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-coroutines-core-ohosarm64': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-coroutines-core-ohosx64': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-datetime': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-datetime-ohosarm64': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-datetime-ohosx64': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-bom': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core-ohosarm64': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core-ohosx64': '1.11.0-0.1.0-07',
 'org.jetbrains.skiko:skiko': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64-api': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64-fusionrenderer': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64-api': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64-fusionrenderer': '0.150.1-0.1.0-10',
 'org.jetbrains.compose.components:components-ui-tooling-preview': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.components:components-ui-tooling-preview-ohosX64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.components:components-ui-tooling-preview-ohosArm64': '1.12.0-0.1.0-11'}
METADATA_PINS = {'androidx.annotation:annotation': '1.9.1',
 'androidx.arch.core:core-common': '2.2.0',
 'androidx.collection:collection': '1.5.0',
 'androidx.compose.runtime:runtime': '1.12.0',
 'androidx.compose.runtime:runtime-annotation': '1.12.0',
 'androidx.compose.runtime:runtime-saveable': '1.12.0',
 'androidx.graphics:graphics-shapes': '1.1.0',
 'androidx.lifecycle:lifecycle-common': '2.11.0',
 'androidx.lifecycle:lifecycle-runtime': '2.11.0',
 'androidx.lifecycle:lifecycle-runtime-compose': '2.11.0',
 'androidx.lifecycle:lifecycle-viewmodel': '2.11.0',
 'androidx.lifecycle:lifecycle-viewmodel-compose': '2.11.0',
 'androidx.lifecycle:lifecycle-viewmodel-savedstate': '2.11.0',
 'androidx.savedstate:savedstate': '1.5.0-alpha01',
 'androidx.savedstate:savedstate-compose': '1.5.0-alpha01',
 'org.jetbrains.compose.ui:ui-uikit': '1.12.0-0.1.0-11'}
COMPOSE_TOOL = {'schemaVersion': 1,
 'compilerVersion': '2.4.20-0.1.0-08',
 'scope': 'HOST_COMPILER_PLUGINS_ONLY',
 'compilerTasks': ['compileCommonMainKotlinMetadata', 'compileKotlinOhosX64', 'compileKotlinOhosArm64'],
 'pins': {'org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable': '2.4.20-0.1.0-08',
          'org.jetbrains.kotlin:kotlin-serialization-compiler-plugin-embeddable': '2.4.20-0.1.0-08'},
 'artifacts': {'org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable': {'size': 870498,
                                                                                  'sha256': '4ffe7f38089fa4acdda5d67fa3a858b9fc2fe7ed1f2e58bedbf8d3447c15df39',
                                                                                  'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-compose-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.jar'},
               'org.jetbrains.kotlin:kotlin-serialization-compiler-plugin-embeddable': {'size': 452111,
                                                                                        'sha256': '4145f75461232632f8aea9aceedf6d82e6cb5f154946370afb187a190251c646',
                                                                                        'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-serialization-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-serialization-compiler-plugin-embeddable-2.4.20-0.1.0-08.jar'}},
 'sourcePom': {'path': 'vendor/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom',
               'size': 1257,
               'sha256': 'd38ccafd8914713808fb9d66a5deb11b742dcd05d6420e8b0351ca146795540b',
               'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-compose-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom'},
 'directRuntimeDependencies': [],
 'serializationSourcePom': {'path': 'vendor/kotlin-serialization-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom',
                            'size': 1223,
                            'sha256': '1565b5bcf81e7b4c9bf017220f0bf6b1f5a18b7ade338749c94529a32078c843',
                            'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-serialization-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-serialization-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom'}}

SOURCE_MANIFEST_SHA256 = '58030409ae040b5e453ac5a445c6c9a28481ed503c6c1ef9a37162bd09f790ad'
PLATFORM_INPUTS = [{'relativePath': 'compose-multiplatform/library/src/ohosMain/kotlin/com/kizitonwose/calendar/core/Extensions.ohos.kt',
  'size': 2015,
  'sha256': '04ea84b367ddd937bca5391c220209ba2f89367f64bda8049caafd6db1e08888'},
 {'relativePath': 'compose-multiplatform/library/src/ohosMain/kotlin/com/kizitonwose/calendar/data/Utils.ohos.kt',
  'size': 569,
  'sha256': 'c7dba7884070b816b00ec234de4023ee06e211cbb0157914d92d17b04c98500d'},
 {'relativePath': 'compose-multiplatform/library/src/nativeInterop/cinterop/calendar_icu.def',
  'size': 235,
  'sha256': 'd0ac6312b8781c35103e649192b7b1dea53415a44d795cfc0a401349ad2815ac'}]

SYSROOT_CANDIDATE = {'url': 'https://maven.eazytec-cloud.com/nexus/repository/file-storage/sysroot-ohos-26.0.0.38-01.tar.gz',
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


DIRECT_DEPENDENCIES = {"org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains.kotlinx:kotlinx-datetime",
                       "org.jetbrains.kotlinx:kotlinx-serialization-core", "org.jetbrains.compose.runtime:runtime",
                       "org.jetbrains.compose.foundation:foundation", "org.jetbrains.compose.ui:ui",
                       "org.jetbrains.compose.components:components-resources", "org.jetbrains.compose.components:components-ui-tooling-preview",
                       "org.jetbrains.compose.annotation-internal:annotation"}


SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.calendar") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.calendar") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.calendar") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.calendar") } }
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.compose") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.serialization") version "2.4.20-0.1.0-08"
        id("org.jetbrains.compose") version "1.12.0-0.1.0-11"
    }
}
val tools = file(providers.gradleProperty("consumerTools").get())
fun json(name: String) = JsonSlurper().parse(tools.resolve(name)) as Map<*, *>
val metadataPins = json("metadata-pins.json")
val allowed = json("dependency-pins.json").entries + metadataPins.entries + (json("compiler-plugin-toolchain.json")["pins"] as Map<*, *>).entries +
    (json("metadata-toolchain.json")["launcherPins"] as Map<*, *>).entries +
    (json("commonizer-toolchain.json")["pins"] as Map<*, *>).entries +
    (json("native-compiler-toolchain.json")["pins"] as Map<*, *>).entries

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven { name = "CalendarPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.calendar") }
        }
        google { content { metadataPins.forEach { (ga, version) ->
            val parts = ga.toString().split(":")
            if (parts[0].startsWith("androidx.")) includeVersion(parts[0], parts[1], version.toString())
        } } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") {
            content { allowed.forEach { (ga, version) -> val parts = ga.toString().split(":"); includeVersion(parts[0], parts[1], version.toString()) } }
        }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") {
            content { allowed.forEach { (ga, version) -> val parts = ga.toString().split(":"); includeVersion(parts[0], parts[1], version.toString()) } }
        }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.calendar") } }
    }
}
rootProject.name = "calendar-pages-consumer"
'''
BUILD = r'''import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.security.MessageDigest
import java.util.zip.ZipFile
import org.gradle.api.artifacts.Configuration
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.gradle.api.artifacts.result.UnresolvedDependencyResult
import org.jetbrains.kotlin.gradle.tasks.KotlinNativeCompile

plugins {
    kotlin("multiplatform")
    kotlin("plugin.compose")
    kotlin("plugin.serialization")
    id("org.jetbrains.compose")
}
fun readMap(file: File): Map<String, Any?> = (JsonSlurper().parse(file) as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun asMap(value: Any?): Map<String, Any?> = (value as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
fun sha(file: File) = digest(file.readBytes())
fun leaves(file: File): List<File> = if (file.isDirectory) file.walkTopDown().filter(File::isFile).toList() else if (file.isFile) listOf(file) else emptyList()
fun records(files: Iterable<File>) = files.flatMap(::leaves).distinct().sortedBy { it.path }.map {
    mapOf("path" to it.absolutePath, "size" to it.length(), "sha256" to sha(it))
}
val tools = file(providers.gradleProperty("consumerTools").get())
val output = file(providers.gradleProperty("consumerOutput").get())
val evidenceDir = file(providers.gradleProperty("consumerEvidence").get())
val http = readMap(file(providers.gradleProperty("consumerHttp").get()))
val calendarGroup = "io.github.qsxs.cpf.calendar"
val calendarVersion = providers.gradleProperty("calendarVersion").get()
val probe = file("src/commonMain/kotlin/CalendarConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val metadataTools = readMap(tools.resolve("metadata-toolchain.json"))
val commonizer = readMap(tools.resolve("commonizer-toolchain.json"))
val commonizerPins = asMap(metadataTools.getValue("launcherPins")) + asMap(commonizer.getValue("pins"))
val commonizerArtifacts = asMap(metadataTools.getValue("launcherArtifacts")) + asMap(commonizer.getValue("artifacts"))
val host = readMap(tools.resolve("native-compiler-toolchain.json"))
val pins = readMap(tools.resolve("dependency-pins.json"))
val metadataPins = readMap(tools.resolve("metadata-pins.json"))
val compilerPlugins = readMap(tools.resolve("compiler-plugin-toolchain.json"))
val compilerPluginPins = asMap(compilerPlugins.getValue("pins"))
val compilerPluginArtifacts = asMap(compilerPlugins.getValue("artifacts"))
val hostPins = asMap(host.getValue("pins"))
val hostArtifacts = asMap(host.getValue("artifacts"))
val compileTasks = listOf("compileCommonMainKotlinMetadata", "compileKotlinOhosX64", "compileKotlinOhosArm64")
layout.buildDirectory.set(output.resolve("build"))
kotlin {
    ohosX64()
    ohosArm64()
    sourceSets {
        val commonMain by getting {
            kotlin.setSrcDirs(listOf(file("src/commonMain/kotlin")))
            dependencies { implementation("$calendarGroup:compose-multiplatform:$calendarVersion") }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
configurations.configureEach {
    if (name == host["configuration"] || name == commonizer["configuration"]) {
        val fixedPins = if (name == host["configuration"]) hostPins else commonizerPins
        resolutionStrategy.eachDependency {
            val ga = "${requested.group}:${requested.name}"
            val fixed = fixedPins[ga]?.toString() ?: error("Unpinned consumer host tool: $ga")
            if (requested.version != fixed) useVersion(fixed)
        }
    }
    val metadata = name.endsWith("ResolvableDependenciesMetadata") || name == "allSourceSetsCompileDependenciesMetadata"
    val library = metadata || name.endsWith("CompileKlibraries") || name.endsWith("CompilationDependenciesMetadata")
    if (library && !name.contains("Test", ignoreCase = true)) resolutionStrategy.eachDependency {
        val ga = "${requested.group}:${requested.name}"
        if (requested.group == calendarGroup) {
            check(requested.version == calendarVersion) { "Calendar version escaped explicit Pages coordinate" }
        } else {
            val fixed = (if (metadata) metadataPins[ga] ?: pins[ga] else pins[ga])?.toString()
                ?: error("Unpinned consumer library dependency: $ga")
            if (requested.version != fixed) useVersion(fixed)
        }
    }
}
fun evidence(name: String, data: Any) {
    evidenceDir.mkdirs()
    evidenceDir.resolve(name).writeText(JsonOutput.prettyPrint(JsonOutput.toJson(data)) + "\n")
}
fun edges(configuration: Configuration) = configuration.incoming.resolutionResult.allDependencies.map { edge ->
    if (edge !is ResolvedDependencyResult) throw GradleException("Unresolved consumer dependency: $edge", (edge as? UnresolvedDependencyResult)?.failure)
    mapOf("from" to edge.from.id.displayName, "requested" to edge.requested.displayName, "selected" to edge.selected.id.displayName)
}
fun checkedTools(name: String, fixed: Map<String, Any?>, expected: Map<String, Any?>): Map<String, Any> {
    val configuration = configurations.getByName(name)
    val actual = configuration.resolvedConfiguration.resolvedArtifacts.map { artifact ->
        val id = artifact.moduleVersion.id
        val ga = "${id.group}:${id.name}"
        check(fixed[ga] == id.version) { "Consumer host tool version differs: $id" }
        val item = asMap(expected.getValue(ga))
        check(sha(artifact.file) == item["sha256"] && artifact.file.length() == (item.getValue("size") as Number).toLong())
        mapOf("gav" to id.toString(), "files" to records(listOf(artifact.file)))
    }
    check(actual.size == fixed.size && actual.map { it.getValue("gav") }.toSet() == fixed.map { "${it.key}:${it.value}" }.toSet())
    return mapOf("configuration" to name, "edges" to edges(configuration), "artifacts" to actual)
}
fun toolRecords() = mapOf("nativeCompiler" to checkedTools(host.getValue("configuration").toString(), hostPins, hostArtifacts),
    "commonizer" to checkedTools(commonizer.getValue("configuration").toString(), commonizerPins, commonizerArtifacts))
fun resolution() = listOf("commonMainResolvableDependenciesMetadata", "ohosX64CompileKlibraries", "ohosArm64CompileKlibraries").map { name ->
    val configuration = configurations.getByName(name)
    val target = when (name) { "ohosX64CompileKlibraries" -> "ohos_x64"; "ohosArm64CompileKlibraries" -> "ohos_arm64"; else -> null }
    val expected = if (target == null) (http.getValue("metadataArtifacts") as List<*>).map(::asMap) else
        (asMap(http.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
    var count = 0
    val matched = mutableSetOf<Pair<String, Long>>()
    val artifacts = configuration.incoming.artifacts.artifacts.map { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier)
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        if (id.group == calendarGroup) {
            count++
            check(id.version == calendarVersion)
            if (target == null) check(id.module == "compose-multiplatform" && attrs["org.jetbrains.kotlin.platform.type"] == "common" && attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf("compose-multiplatform", if (target == "ohos_x64") "compose-multiplatform-ohosx64" else "compose-multiplatform-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            val identity = sha(artifact.file) to artifact.file.length()
            check(expected.any { it["sha256"] == identity.first && (it.getValue("size") as Number).toLong() == identity.second }) { "Calendar artifact differs from anonymous HTTP: $id" }
            matched.add(identity)
        } else {
            val ga = "${id.group}:${id.module}"
            val metadata = target == null
            check((if (metadata) metadataPins[ga] ?: pins[ga] else pins[ga]) == id.version)
            if (metadataPins.containsKey(ga)) {
                val common = attrs["org.gradle.usage"] == "kotlin-metadata" && attrs["org.jetbrains.kotlin.platform.type"] == "common"
                val javaAlias = ga == "androidx.arch.core:core-common" && id.version == "2.2.0" &&
                    attrs["org.gradle.usage"] in listOf("java-api", "java-runtime") &&
                    attrs["org.jetbrains.kotlin.platform.type"] in listOf(null, "jvm") && attrs["org.gradle.category"] == "library"
                check(metadata && (common || javaAlias) && attrs["org.jetbrains.kotlin.native.target"] == null)
            }
        }
        mapOf("component" to id.displayName, "attributes" to attrs, "files" to records(listOf(artifact.file)))
    }
    val expectedIdentities = expected.map { it.getValue("sha256").toString() to (it.getValue("size") as Number).toLong() }.toSet()
    check(count == expected.size && count > 0 && expectedIdentities.size == expected.size && matched == expectedIdentities) { "Calendar selected artifact set differs: $name" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$calendarGroup:compose-multiplatform:$calendarVersion" })
    mapOf("configuration" to name, "target" to target, "edges" to graph, "artifacts" to artifacts)
}
fun payload(file: File): Map<String, Map<String, Any>> {
    val found = mutableMapOf<String, Map<String, Any>>()
    fun add(name: String, bytes: ByteArray) {
        val normalized = name.removePrefix("commonMain/")
        if (normalized.startsWith("default/")) found[normalized] = mapOf("size" to bytes.size.toLong(), "sha256" to digest(bytes))
    }
    if (file.isDirectory) leaves(file).forEach { add(it.relativeTo(file).invariantSeparatorsPath, it.readBytes()) }
    else if (file.isFile && file.extension in listOf("jar", "klib", "bin")) ZipFile(file).use { zip ->
        zip.entries().asSequence().filter { !it.isDirectory }.forEach { add(it.name, zip.getInputStream(it).use { stream -> stream.readBytes() }) }
    }
    return found
}
fun metadataTrace(compiler: KotlinNativeCompile): Map<String, Any?> {
    val expected = asMap(http.getValue("metadataPayload")).mapValues { (_, value) ->
        val item = asMap(value)
        mapOf("size" to (item.getValue("size") as Number).toLong(), "sha256" to item.getValue("sha256"))
    }
    check(expected.isNotEmpty())
    val candidates = compiler.libraries.files.associateWith(::payload)
    val matches = candidates.filterValues { it == expected }.keys
    evidence("consumer-metadata-trace.json", mapOf("rootHttpArtifacts" to http.getValue("metadataArtifacts"),
        "expectedPayload" to expected, "matchingLibraries" to matches.map { it.absolutePath },
        "candidates" to candidates.map { (file, entries) -> mapOf("path" to file.absolutePath, "entries" to entries.size,
            "matchingEntries" to entries.count { (name, value) -> expected[name] == value }) }))
    check(matches.size == 1) { "Calendar transformed metadata cannot be traced to the Pages root" }
    return mapOf("rootHttpArtifacts" to http.getValue("metadataArtifacts"), "compilerLibrary" to matches.single().absolutePath,
        "payload" to expected, "payloadFileCount" to expected.size)
}
fun nativeTrace(compiler: KotlinNativeCompile, target: String): Map<String, Any> {
    val declared = (asMap(http.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
    check(declared.size == 2 && declared.map { it.getValue("artifactKind").toString() }.toSet() == setOf("main", "cinterop"))
    val candidates = compiler.libraries.files.associateWith(::payload)
    val traces = declared.map { item ->
        val expected = payload(file(item.getValue("path")!!))
        check(expected.isNotEmpty())
        val matches = candidates.filterValues { it == expected }.keys
        check(matches.size == 1) { "Native compiler library cannot be traced to the Pages leaf: $target" }
        mapOf("artifactKind" to item.getValue("artifactKind").toString(), "httpArtifact" to item,
              "compilerLibrary" to matches.single().absolutePath)
    }
    check(traces.map { it.getValue("compilerLibrary") }.toSet().size == 2)
    return mapOf("target" to target, "artifacts" to traces)
}
val checkTools = tasks.register("verifyConsumerTools") {
    outputs.upToDateWhen { false }
    doLast { evidence("consumer-tools.json", toolRecords()) }
}
tasks.withType<KotlinNativeCompile>().configureEach { if (name in compileTasks) dependsOn(checkTools) }
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0" && System.getProperty("java.specification.version") == "17")
        evidence("consumer-resolution.json", mapOf("calendarVersion" to calendarVersion, "gradleVersion" to gradle.gradleVersion,
            "javaVersion" to System.getProperty("java.version"), "javaHome" to System.getProperty("java.home"),
            "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
    }
}
fun recordCompilation(name: String, taskName: String, target: String?) {
    tasks.register(name) {
        dependsOn(taskName)
        outputs.upToDateWhen { false }
        doLast {
            val compiler = tasks.getByName(taskName) as KotlinNativeCompile
            check(compiler.sources.files.filter { it.isFile && it.extension == "kt" }.map { it.canonicalFile }.toSet() == setOf(probe) && sha(probe) == probeSha)
            check(compiler.enabled && compiler.state.executed && !compiler.state.noSource && compiler.state.skipMessage in listOf(null, "UP-TO-DATE", "FROM-CACHE"))
            val plugins = compiler.compilerPluginClasspath?.files.orEmpty()
            val pluginIds = listOf("org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable", "org.jetbrains.kotlin:kotlin-serialization-compiler-plugin-embeddable")
            val expectedPlugins = pluginIds.map { id ->
                check(compilerPluginPins[id] == "2.4.20-0.1.0-08")
                val item = asMap(compilerPluginArtifacts.getValue(id))
                (item.getValue("size") as Number).toLong() to item.getValue("sha256").toString()
            }.toSet()
            check(expectedPlugins.size == 2 && plugins.size == 2 && plugins.map { it.length() to sha(it) }.toSet() == expectedPlugins) {
                "Consumer Compose and serialization compiler plugins differ"
            }
            val outputs = compiler.outputs.files.files.flatMap(::leaves).distinct()
            check(outputs.isNotEmpty() && outputs.any { it.length() > 0 })
            var metadata = false
            var ir = false
            val targets = mutableSetOf<String>()
            outputs.forEach { file ->
                if (file.extension in listOf("klib", "jar")) ZipFile(file).use { zip ->
                    val entries = zip.entries().asSequence().toList()
                    metadata = metadata || entries.any { it.name.contains("/linkdata/") && it.size > 0 }
                    ir = ir || entries.any { it.name.contains("/ir/") && it.size > 0 }
                    zip.getEntry("default/manifest")?.let { entry ->
                        val text = zip.getInputStream(entry).use { it.readBytes().toString(Charsets.UTF_8) }
                        text.lineSequence().firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
                    }
                }
                if (file.invariantSeparatorsPath.contains("/linkdata/") && file.length() > 0) metadata = true
                if (file.invariantSeparatorsPath.contains("/ir/") && file.length() > 0) ir = true
                if (file.invariantSeparatorsPath.endsWith("/default/manifest")) file.readLines().firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
            }
            check(metadata) { "Consumer compilation produced no metadata payload" }
            if (target != null) check(ir && targets == setOf(target)) { "Consumer Native target/IR differs" }
            evidence("consumer-compilation-$name.json", mapOf("task" to compiler.path, "target" to target, "sources" to records(listOf(probe)),
                "outputs" to records(outputs), "libraries" to compiler.libraries.files.sortedBy { it.path }.map { mapOf("path" to it.absolutePath, "files" to records(listOf(it))) },
                "pluginOptions" to compiler.compilerPluginCommandLine, "plugins" to records(compiler.compilerPluginClasspath?.files.orEmpty()),
                "metadataTrace" to if (target == null) metadataTrace(compiler) else null,
                "nativeTrace" to if (target == null) null else nativeTrace(compiler, target),
                "metadataPayload" to metadata, "irPayload" to ir, "nativeTargets" to targets, "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
'''
PROBE = r'''package acceptance

import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import com.kizitonwose.calendar.compose.HorizontalCalendar
import com.kizitonwose.calendar.compose.WeekCalendar
import com.kizitonwose.calendar.compose.rememberCalendarState
import com.kizitonwose.calendar.compose.weekcalendar.rememberWeekCalendarState
import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.LocalDate
import kotlinx.datetime.YearMonth

@Composable
fun CalendarProbe() {
    val month = rememberCalendarState(
        startMonth = YearMonth(2024, 1), endMonth = YearMonth(2024, 12),
        firstVisibleMonth = YearMonth(2024, 6), firstDayOfWeek = DayOfWeek.MONDAY,
    )
    val week = rememberWeekCalendarState(
        startDate = LocalDate(2024, 1, 1), endDate = LocalDate(2024, 12, 31),
        firstVisibleWeekDate = LocalDate(2024, 6, 3), firstDayOfWeek = DayOfWeek.MONDAY,
    )
    HorizontalCalendar(state = month, dayContent = { day -> BasicText(day.date.toString()) })
    WeekCalendar(state = week, dayContent = { day -> BasicText(day.date.toString()) })
}
'''

STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}


def source_manifest_sha256(rows):
    if not isinstance(rows, list) or len(rows) != 51:
        raise RuntimeError("Calendar source archive inventory differs")
    try:
        members = [{key: row[key] for key in ("member", "size", "sha256", "compile")} for row in rows]
    except (KeyError, TypeError) as error:
        raise RuntimeError("Calendar source archive inventory is malformed") from error
    if len({row["member"] for row in members}) != 51 or sum(row["compile"] is True for row in members) != 41:
        raise RuntimeError("Calendar handwritten source inventory differs")
    return digest(json.dumps(members, sort_keys=True, separators=(",", ":")).encode())


def verify_provenance(data, version, source_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not re.fullmatch(
            r"2\.10\.1-cpf11-preview-" + re.escape(source_sha[:12]) + r"-[1-9][0-9]*-[1-9][0-9]*", version):
        raise RuntimeError("Calendar source SHA or version differs")
    value = json.loads(data)
    expected = {"sourceCommit": source_sha, "group": GROUP, "module": MODULE, "version": version,
                "toolingCommit": TOOL_REVISION, "upstreamCommit": "0e94f40b5849d92a6f1390b9e39a0d316c7d5408",
                "licenseSha256": "942b3872c6621a2ff8a2730044ec02093d350aff5e5db13fe8811ca67aa0aae9"}
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise RuntimeError("Calendar published provenance identity differs")
    fingerprint = value.get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise RuntimeError("Calendar published provenance fingerprint differs")
    if source_manifest_sha256(value.get("sourceMembers")) != SOURCE_MANIFEST_SHA256 or value.get("platformInputs") != PLATFORM_INPUTS:
        raise RuntimeError("Calendar published source or platform inventory differs")
    sysroot = value.get("sysroot")
    if not isinstance(sysroot, dict) or sysroot.get("kind") not in ("cpf", "deveco"):
        raise RuntimeError("Calendar published external sysroot identity differs")
    files = sysroot.get("files")
    expected_files = [{"relativePath": item["path"], "size": item["size"], "sha256": item["sha256"]} for item in SYSROOT_CANDIDATE["files"]]
    if sysroot["kind"] == "cpf":
        archive = {key: SYSROOT_CANDIDATE[key] for key in ("url", "size", "sha256")}
        if (files != expected_files or sysroot.get("candidateArchive") != archive or
                sysroot.get("candidateArchiveVerification") != "LOCK_ONLY_NOT_READ_BY_PORT"):
            raise RuntimeError("Calendar approved CPF sysroot identity differs")
    else:
        if (not isinstance(files, list) or len(files) != len(expected_files) or
                {item.get("relativePath") for item in files} != {item["relativePath"] for item in expected_files} or
                any(not isinstance(item.get("size"), int) or item["size"] <= 0 or
                    not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) for item in files) or
                sysroot.get("candidateArchive") is not None or
                sysroot.get("devecoVersion") != "CALLER_SELECTED_26.0.0.105_NOT_INDEPENDENTLY_VERIFIED"):
            raise RuntimeError("Calendar caller-selected DevEco sysroot identity differs")
    return {**expected, "fingerprint": fingerprint, "sourceManifestSha256": SOURCE_MANIFEST_SHA256,
            "platformInputs": PLATFORM_INPUTS, "sysroot": value.get("sysroot")}


def verify_metadata_source_manifest(metadata_bytes, provenance_identity):
    member_name = "META-INF/upstream/source-manifest.json"
    with zipfile.ZipFile(io.BytesIO(metadata_bytes)) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename == member_name and not entry.is_dir()]
        if len(entries) != 1:
            raise RuntimeError("Calendar metadata source manifest is missing or duplicated")
        raw = archive.read(entries[0])
    manifest = json.loads(raw)
    if manifest.get("fingerprint") != provenance_identity["fingerprint"] or source_manifest_sha256(manifest.get("members")) != provenance_identity["sourceManifestSha256"]:
        raise RuntimeError("Calendar metadata source manifest differs from provenance")
    actuals = [{key: row[key] for key in ("relativePath", "size", "sha256")} for row in manifest.get("actuals", [])]
    definition = manifest.get("definition", {})
    binding = {key: definition.get(key) for key in ("relativePath", "size", "sha256")}
    if actuals + [binding] != PLATFORM_INPUTS:
        raise RuntimeError("Calendar metadata platform inputs differ")
    old_generated = [row for row in manifest["members"] if "/generated/resources/" in row["member"]]
    expected_names = {"commonMain/calendar/compose_multiplatform/library/generated/resources/Res.kt",
                      "commonMain/calendar/compose_multiplatform/library/generated/resources/ExpectResourceCollectors.kt"}
    if (len(old_generated) != 2 or {row["member"] for row in old_generated} != expected_names or
            any(row["compile"] is not False for row in old_generated) or manifest.get("oldGeneratedMembers") != old_generated):
        raise RuntimeError("Calendar old generated source policy differs")
    resources = manifest.get("resources")
    if resources != {"package": "calendar.compose_multiplatform.library.generated.resources", "visibility": "internal",
                     "producer": "CPF_COMPOSE_RESOURCES_PLUGIN", "upstreamAssetCount": 0}:
        raise RuntimeError("Calendar resource generation policy differs")
    return raw, {"entry": member_name, "size": len(raw), "sha256": digest(raw),
                 "fingerprint": manifest["fingerprint"], "sourceManifestSha256": provenance_identity["sourceManifestSha256"],
                 "sourceCount": 41, "oldGeneratedMembers": old_generated, "resources": resources}


def platform_source_member(relative):
    prefix = "compose-multiplatform/library/src/ohosMain/kotlin/"
    definition = "compose-multiplatform/library/src/nativeInterop/cinterop/calendar_icu.def"
    if relative.startswith(prefix) and relative.endswith(".kt"):
        return "ohosMain/" + relative.removeprefix(prefix)
    if relative == definition:
        return "nativeInterop/cinterop/calendar_icu.def"
    raise RuntimeError("Unexpected Calendar platform source: " + relative)


def verify_public_sources(data, manifest):
    expected = {item["member"]: (item["size"], item["sha256"]) for item in manifest["members"] if item["compile"]}
    for item in PLATFORM_INPUTS:
        expected[platform_source_member(item["relativePath"])] = (item["size"], item["sha256"])
    if len(expected) != 44:
        raise RuntimeError("Calendar published source set expectation differs")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if any(PurePosixPath(item.filename).name == "libicu.so" for item in entries):
            raise RuntimeError("Calendar sources archive contains libicu.so")
        for name, identity in expected.items():
            matches = [item for item in entries if item.filename == name and not item.is_dir()]
            if len(matches) != 1:
                raise RuntimeError("Calendar published source entry absent or duplicated: " + name)
            content = archive.read(matches[0])
            if (len(content), digest(content)) != identity:
                raise RuntimeError("Calendar published source bytes differ: " + name)
        license_name = "META-INF/licenses/calendar/LICENSE.md"
        licenses = [item for item in entries if item.filename == license_name and not item.is_dir()]
        if len(licenses) != 1 or digest(archive.read(licenses[0])) != "942b3872c6621a2ff8a2730044ec02093d350aff5e5db13fe8811ca67aa0aae9":
            raise RuntimeError("Calendar published sources license differs")
        generated = [{"member": item.filename, "size": item.file_size, "sha256": digest(archive.read(item))}
                     for item in entries if not item.is_dir() and "/generated/resources/" in item.filename and item.filename.endswith(".kt")]
    return {"commonSourceCount": 41, "actualCount": 2, "definitionCount": 1,
            "generatedSourceEntries": generated, "upstreamResourceAssetCount": 0,
            "generationEvidence": "POLICY_AND_PUBLIC_ARTIFACTS; PRODUCER_TASK_EVIDENCE_SEPARATE"}


def verify_upstream_sources(data, manifest):
    if len(data) != 56351 or digest(data) != "e13bcd699c499d3a58bc21cb61bba35b159dcac00518fb8279d346793b10e84a":
        raise RuntimeError("Calendar upstream sources archive differs")
    expected = {item["member"]: item for item in manifest["members"]}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        if (len(entries) != 51 or {item.filename for item in entries} != set(expected) or
                any(PurePosixPath(item.filename).name == "libicu.so" for item in entries)):
            raise RuntimeError("Calendar upstream archive inventory differs")
        for item in entries:
            content = archive.read(item)
            row = expected[item.filename]
            if (len(content), digest(content)) != (row["size"], row["sha256"]):
                raise RuntimeError("Calendar upstream archive member differs: " + item.filename)
    return {"members": 51, "oldGeneratedMembers": manifest["oldGeneratedMembers"],
            "oldGeneratedCompiled": False, "artifactRole": "UPSTREAM_SOURCE_EVIDENCE_ONLY"}


def resource_payload(entries):
    prefix = "default/linkdata/package_calendar.compose_multiplatform.library.generated.resources/"
    found = {name: item for name, item in entries.items() if name.startswith(prefix) and item["size"] > 0}
    if not found:
        raise RuntimeError("Calendar generated resource package is absent from Klib metadata")
    return found


def fetch_graph(version, source_sha, output):
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    root_url = PAGES + GROUP.replace(".", "/") + "/" + MODULE + "/" + version + "/" + MODULE + "-" + version + ".module"
    requests = []
    provenance_artifacts = []

    def provenance(module_url, module):
        url = public_url(module_url.removesuffix(".module") + "-provenance.json", module_url.rsplit("/", 1)[0] + "/")
        data, row = read_http(url, PAGES)
        path = evidence / "remote-provenance" / (module + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        row.update(role="provenance", module=module, path=str(path))
        requests.append(row)
        write_json(path.with_suffix(".http.json"), row)
        identity = verify_provenance(data, version, source_sha)
        if provenance_artifacts and (row["sha256"] != provenance_artifacts[0]["sha256"] or identity != provenance_artifacts[0]["identity"]):
            raise RuntimeError("Calendar root and Native published provenance differ")
        provenance_artifacts.append({**row, "identity": identity})

    def gmm(url, label):
        data, row = read_http(url, PAGES)
        requests.append(row)
        value = json.loads(data)
        write_json(evidence / "remote-gmm" / (label + ".json"), value)
        owner = value["component"]
        if any(owner.get(key) != expected for key, expected in (("group", GROUP), ("module", MODULE), ("version", version))):
            raise RuntimeError("Calendar GMM owner differs: " + label)
        for variant in value.get("variants", []):
            for dep in variant.get("dependencies", []):
                ga = dep["group"] + ":" + dep["module"]
                if PINS.get(ga) != dep.get("version", {}).get("requires"):
                    raise RuntimeError("Calendar GMM dependency version differs: " + ga)
            attrs = variant.get("attributes", {})
            metadata = attrs.get("org.gradle.usage") == "kotlin-metadata" and attrs.get("org.jetbrains.kotlin.platform.type") == "common"
            native = attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.jetbrains.kotlin.native.target") in ("ohos_x64", "ohos_arm64") and "available-at" not in variant
            if metadata or native:
                if not DIRECT_DEPENDENCIES.issubset({dep["group"] + ":" + dep["module"] for dep in variant.get("dependencies", [])}):
                    raise RuntimeError("Calendar GMM API dependencies differ")
        return value

    def artifact(module_url, declaration, role, target=None):
        directory = module_url.rsplit("/", 1)[0] + "/"
        url = public_url(urljoin(module_url, declaration["url"]), directory)
        data, row = read_http(url, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Calendar GMM artifact size/SHA256 differs: " + role)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(data)
        row.update(role=role, expectedTarget=target, path=str(path), declaredName=declaration["name"])
        entries, props = klib_payload(data)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if any(PurePosixPath(item.filename).name == "libicu.so" for item in archive.infolist()):
                raise RuntimeError("Calendar Klib contains libicu.so")
        if target is not None:
            if set(props.get("native_targets", "").split()) != {target}:
                raise RuntimeError("Calendar HTTP Native target differs: " + target)
            if props.get("interop") == "true":
                if ("-licu" not in props.get("linkerOpts", "").split() or
                        not props.get("unique_name", "").endswith("compose-multiplatform-cinterop-calendarIcu")):
                    raise RuntimeError("Calendar ICU cinterop manifest differs: " + target)
                row["artifactKind"] = "cinterop"
            else:
                if (not any("/ir/" in name and item["size"] > 0 for name, item in entries.items()) or
                        "compose-multiplatform-cinterop-calendarIcu" not in props.get("depends", "")):
                    raise RuntimeError("Calendar Native main IR or cinterop dependency differs: " + target)
                row["artifactKind"] = "main"
                row["generatedResourcePayload"] = resource_payload(entries)
        else:
            row["generatedResourcePayload"] = resource_payload(entries)
        requests.append(row)
        return row, entries, data

    def pom(module_url, module, target):
        url = module_url.removesuffix(".module") + ".pom"
        data, row = read_http(url, PAGES)
        requests.append(row)
        xml = ET.fromstring(data)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + key, namespaces=ns) != expected for key, expected in (("groupId", GROUP), ("artifactId", module), ("version", version))):
            raise RuntimeError("Calendar Pages POM coordinates differ")
        developers = [(item.findtext("m:id", namespaces=ns), item.findtext("m:name", namespaces=ns), item.findtext("m:url", namespaces=ns))
                      for item in xml.findall("m:developers/m:developer", ns)]
        licenses = [(item.findtext("m:name", namespaces=ns), item.findtext("m:url", namespaces=ns))
                    for item in xml.findall("m:licenses/m:license", ns)]
        if developers != [("kizitonwose", "Kizito Nwose", "https://github.com/kizitonwose")] or licenses != [("MIT License", "https://opensource.org/license/mit/")]:
            raise RuntimeError("Calendar Pages POM author or license differs")
        deps = xml.findall("m:dependencies/m:dependency", ns)
        found, canonical = set(), set()
        for dep in deps:
            ga = dep.findtext("m:groupId", namespaces=ns) + ":" + dep.findtext("m:artifactId", namespaces=ns)
            if ga in found or PINS.get(ga) != dep.findtext("m:version", namespaces=ns) or dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
                raise RuntimeError("Calendar Pages POM dependency or scope differs: " + ga)
            found.add(ga)
            suffix = "-ohosx64" if target == "ohos_x64" else "-ohosarm64" if target else ""
            canonical.add(ga[:-len(suffix)] if suffix and ga.lower().endswith(suffix) else ga)
        if not DIRECT_DEPENDENCIES.issubset(canonical):
            raise RuntimeError("Calendar Pages POM direct dependency set differs")

    root = gmm(root_url, MODULE)
    pom(root_url, MODULE, None)
    provenance(root_url, MODULE)
    common = [v for v in root["variants"] if v.get("attributes", {}).get("org.gradle.usage") == "kotlin-metadata" and v.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == "common" and v.get("attributes", {}).get("org.gradle.category") == "library"]
    metadata, payload, metadata_bytes = [], None, None
    for variant in common:
        for declaration in variant.get("files", []):
            row, entries, metadata_bytes = artifact(root_url, declaration, "metadata")
            metadata.append(row)
            if payload is not None and payload != entries:
                raise RuntimeError("Multiple incompatible Calendar common payloads")
            payload = entries
    if len(metadata) != 1:
        raise RuntimeError("Expected one Calendar common metadata artifact")
    raw_manifest, source_manifest = verify_metadata_source_manifest(metadata_bytes, provenance_artifacts[0]["identity"])
    manifest_path = evidence / "remote-metadata-source-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(raw_manifest)
    source_manifest.update(path=str(manifest_path), artifactUrl=metadata[0]["url"],
                           artifactSize=metadata[0]["size"], artifactSha256=metadata[0]["sha256"])
    write_json(evidence / "remote-metadata-source-manifest-receipt.json", source_manifest)
    manifest_data = json.loads(raw_manifest)
    source_variants = [v for v in root["variants"] if v.get("attributes", {}).get("org.gradle.category") == "documentation"
                       and v.get("attributes", {}).get("org.gradle.docstype") == "sources"
                       and v.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == "common"]
    declarations = [item for variant in source_variants for item in variant.get("files", [])]
    if len(declarations) != 1:
        raise RuntimeError("Expected one Calendar common sources artifact")
    declaration = declarations[0]
    source_url = public_url(urljoin(root_url, declaration["url"]), root_url.rsplit("/", 1)[0] + "/")
    source_data, source_row = read_http(source_url, PAGES)
    if source_row["size"] != declaration["size"] or source_row["sha256"] != declaration["sha256"]:
        raise RuntimeError("Calendar GMM sources artifact differs")
    source_inventory = verify_public_sources(source_data, manifest_data)
    source_path = evidence / "remote-sources.jar"
    source_path.write_bytes(source_data)
    source_row.update(role="sources", path=str(source_path), declaredName=declaration["name"])
    requests.append(source_row)
    upstream_url = public_url(root_url.removesuffix(".module") + "-upstream-sources.jar", root_url.rsplit("/", 1)[0] + "/")
    upstream_data, upstream_row = read_http(upstream_url, PAGES)
    upstream_inventory = verify_upstream_sources(upstream_data, manifest_data)
    upstream_path = evidence / "upstream-sources.jar"
    upstream_path.write_bytes(upstream_data)
    upstream_row.update(role="upstream-source-evidence", path=str(upstream_path))
    requests.append(upstream_row)
    write_json(evidence / "remote-sources-inventory.json", {"publishedArtifact": source_row, "publishedSources": source_inventory,
               "upstreamArtifact": upstream_row, "upstreamSources": upstream_inventory})
    native, owners, resource_archives = {}, [], {}
    for target, module in (("ohos_x64", MODULE + "-ohosx64"), ("ohos_arm64", MODULE + "-ohosarm64")):
        links = [v["available-at"] for v in root["variants"] if v.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and v.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and v.get("attributes", {}).get("org.gradle.category") == "library" and "available-at" in v]
        expected_url = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/" + module + "-" + version + ".module"
        if not links or any(link["group"] != GROUP or link["module"] != module or link["version"] != version or urljoin(root_url, link["url"]) != expected_url for link in links):
            raise RuntimeError("Calendar root available-at differs: " + target)
        leaf = gmm(expected_url, module)
        pom(expected_url, module, target)
        provenance(expected_url, module)
        if urljoin(expected_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Calendar Native leaf owner differs")
        owners.append({"target": target, "leafModule": module, "leafUrl": expected_url, "ownerUrl": root_url})
        native[target] = []
        for variant in leaf["variants"]:
            attrs = variant.get("attributes", {})
            if attrs.get("org.jetbrains.kotlin.native.target") == target and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.gradle.category") == "library":
                for declaration in variant.get("files", []):
                    row, _, _ = artifact(expected_url, declaration, "native", target)
                    native[target].append(row)
        if len(native[target]) != 2 or {item.get("artifactKind") for item in native[target]} != {"main", "cinterop"}:
            raise RuntimeError("Expected Calendar main and ICU cinterop Native Klibs: " + target)
        resource_archives[target] = []
        for variant in leaf["variants"]:
            attrs = variant.get("attributes", {})
            if attrs.get("org.jetbrains.kotlin.native.target") == target and attrs.get("org.gradle.usage") == "kotlin-multiplatformresources":
                for declaration in variant.get("files", []):
                    directory = expected_url.rsplit("/", 1)[0] + "/"
                    url = public_url(urljoin(expected_url, declaration["url"]), directory)
                    data, row = read_http(url, PAGES)
                    if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
                        raise RuntimeError("Calendar Native resource archive bytes differ: " + target)
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        entries = archive.infolist()
                        if any(PurePosixPath(item.filename).name == "libicu.so" for item in entries):
                            raise RuntimeError("Calendar resource archive contains libicu.so")
                        recorded = [{"member": item.filename, "size": item.file_size, "sha256": digest(archive.read(item))}
                                    for item in entries if not item.is_dir()]
                    row.update(role="resource-archive", expectedTarget=target, members=recorded)
                    requests.append(row)
                    resource_archives[target].append(row)
    manifest = {"status": "ANONYMOUS_PAGES_GRAPH_AND_BYTES_VERIFIED", "baseUrl": PAGES, "group": GROUP, "module": MODULE,
                "version": version, "sourceCommit": source_sha, "rootUrl": root_url, "owners": owners, "requests": requests,
                "provenanceArtifacts": provenance_artifacts, "metadataArtifacts": metadata,
                "metadataSourceManifest": source_manifest, "metadataPayload": payload,
                "nativeArtifacts": native, "resourceArchives": resource_archives,
                "sourceArchive": source_row, "sourceInventory": source_inventory,
                "upstreamSourceArchive": upstream_row, "upstreamSourceInventory": upstream_inventory,
                "librarySourcesDownloaded": True, "librarySourceCheckout": False, "sourcesUsedForCompilation": False,
                "upstreamResourceAssetCount": 0, "abiOrRuntimeEquivalence": "NOT_ESTABLISHED"}
    write_json(evidence / "remote-http-manifest.json", manifest)
    return manifest


def fetch_tools(output, mode):
    lock = TOOL_LOCK
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
    wrapper = WRAPPER_INPUTS
    if wrapper["sourceCommit"] != WRAPPER_COMMIT or {item["path"] for item in wrapper["files"]} != {"gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties", "gradle.properties"}:
        raise RuntimeError("Fixed Gradle wrapper input set differs")
    prefix = "https://raw.githubusercontent.com/qsxs/Calendar/" + WRAPPER_COMMIT + "/ohos/"
    wrapper_root = output / "wrapper"
    for item in wrapper["files"]:
        if item["url"] != prefix + item["path"]:
            raise RuntimeError("Gradle wrapper URL differs")
        data, http = read_http(item["url"], prefix)
        if len(data) != item["size"] or digest(data) != item["sha256"]:
            raise RuntimeError("Gradle wrapper bytes differ")
        target = wrapper_root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({"path": item["path"], **http})
    tool_directory = tools / TOOL_DIR
    write_json(tool_directory / "dependency-pins.json", PINS)
    write_json(tool_directory / "metadata-pins.json", METADATA_PINS)
    write_json(tool_directory / "compiler-plugin-toolchain.json", COMPOSE_TOOL)
    write_json(output / "evidence/toolchain-inputs.json", {"runtimeToolingCommit": TOOL_REVISION, "wrapperSourceCommit": WRAPPER_COMMIT,
        "wrapperSourceRepository": "qsxs/Calendar", "gradleVersion": "9.5.0",
        "files": rows, "librarySourceCheckout": False})
    return tools, wrapper_root


def verify_records(output, native_home, env, mode):
    evidence = output / "evidence"
    resolution = json.loads((evidence / "consumer-resolution.json").read_text())
    if {item.get("configuration") for item in resolution["configurations"]} != {
            "commonMainResolvableDependenciesMetadata", "ohosX64CompileKlibraries", "ohosArm64CompileKlibraries"}:
        raise RuntimeError("Consumer resolution evidence is incomplete")
    compilations = []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
        data = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text())
        if data["target"] != target or len(data["sources"]) != 1 or not data["metadataPayload"] or not data["outputs"]:
            raise RuntimeError("Consumer compilation proof is incomplete: " + name)
        if target is not None and (not data["irPayload"] or set(data["nativeTargets"]) != {target}):
            raise RuntimeError("Consumer Native IR or target differs: " + name)
        if target is None and not data["metadataTrace"]:
            raise RuntimeError("Consumer common metadata transform has no Pages trace")
        plugin_ids = ("org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable", "org.jetbrains.kotlin:kotlin-serialization-compiler-plugin-embeddable")
        expected_plugins = {(COMPOSE_TOOL["artifacts"][key]["size"], COMPOSE_TOOL["artifacts"][key]["sha256"]) for key in plugin_ids}
        if (len(data["plugins"]) != 2 or len(expected_plugins) != 2 or
                {(item["size"], item["sha256"]) for item in data["plugins"]} != expected_plugins or
                (target is not None and not data.get("nativeTrace"))):
            raise RuntimeError("Consumer compiler plugin set or Native Pages trace differs")
        if target is not None:
            trace = data["nativeTrace"]
            artifacts = trace.get("artifacts", [])
            if (trace.get("target") != target or len(artifacts) != 2 or
                    {item.get("artifactKind") for item in artifacts} != {"main", "cinterop"} or
                    len({item.get("compilerLibrary") for item in artifacts}) != 2):
                raise RuntimeError("Calendar main/cinterop compiler traces differ: " + name)
        for item in [*data["sources"], *data["outputs"], *data["plugins"]]:
            if record(Path(item["path"])) != item:
                raise RuntimeError("Consumer compiler input/output bytes changed")
        compilations.append(data)
    write_json(evidence / "consumer-compilation.json", {"status": "METADATA_AND_DUAL_ABI_CONSUMER_COMPILED", "gradleVersion": "9.5.0",
        "compilations": compilations, "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN",
        "androidRegression": "NOT_RUN", "iosRegression": "NOT_RUN", "gradle8Consumer": "NOT_RUN",
        "consumerSysroot": "STANDARD_KONAN_ON_DEMAND_NO_MANUAL_PREFILL", "abiOrRuntimeEquivalence": "NOT_ESTABLISHED"})


def read_log_head(path):
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        data = stream.read(16 * 1024)
    text = data.decode("utf-8", errors="replace")
    return text.encode("utf-8")[:16 * 1024].decode("utf-8", errors="ignore")


def main():
    output = Path(os.environ["CALENDAR_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    if (evidence / "run.json").exists():
        raise RuntimeError("Existing Calendar consumer evidence; use a fresh run")
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN",
             "device": "NOT_RUN", "androidRegression": "NOT_RUN", "iosRegression": "NOT_RUN", "gradle8Consumer": "NOT_RUN",
             "consumerSysroot": "STANDARD_KONAN_ON_DEMAND_NO_MANUAL_PREFILL", "abiOrRuntimeEquivalence": "NOT_ESTABLISHED"}
    code = 1
    try:
        version, source = os.environ["CALENDAR_VERSION"], os.environ["CALENDAR_SOURCE_SHA"]
        mode = "gradle9"
        workflow = os.environ["CI_TOOLING_SHA"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"2\.10\.1-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete Calendar version must match the full producer source SHA")
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
        fetch_graph(version, source, output)
        state["stage"] = "PinnedBuildTools"
        tools, wrapper = fetch_tools(output, mode)
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running Calendar consumer " + label, flush=True)
            with stdout.open("xb") as out, stderr.open("xb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError("Consumer " + label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        probe_name = "src/commonMain/kotlin/CalendarConsumer.kt"
        for name, contents in (("settings.gradle.kts", SETTINGS), ("build.gradle.kts", BUILD), (probe_name, PROBE)):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
        shutil.copyfile(wrapper / "gradle.properties", project / "gradle.properties")
        probe = project / probe_name
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "remote-http-manifest.json"), "-PcalendarVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Consumer tasks absent from actual discovery")
                write_json(evidence / "task-discovery.json", {"required": sorted(REQUIRED), "stdout": record(logs / "Tasks.stdout.log")})
        state["stage"] = "VerifyPublicConsumption"
        verify_records(output, native, env, mode)
        state["status"] = "PUBLIC_CONSUMER_COMPILED"
        code = 0
    except Exception as error:
        state.update(status="FAILED", error=str(error))
    finally:
        for stage in ("BootstrapNative", *STAGES):
            for stream in ("stdout", "stderr"):
                log_path = output / "logs" / (stage + "." + stream + ".log")
                text = tail(log_path)
                if text:
                    (evidence / (stage + "." + stream + "-tail.log")).write_text(text, encoding="utf-8")
                    if state["status"] == "FAILED" and state.get("stage") == stage:
                        print(text, file=sys.stderr)
                if state["status"] == "FAILED" and state.get("stage") == stage:
                    try:
                        prefix = read_log_head(log_path)
                        if prefix:
                            (evidence / (stage + "." + stream + "-head.log")).write_text(prefix, encoding="utf-8")
                    except OSError as error:
                        state.setdefault("logCaptureWarnings", []).append(
                            {"stage": stage, "stream": stream, "errorType": type(error).__name__}
                        )
        for path in evidence.rglob("*"):
            if path.is_file() and path.stat().st_size > 8 * 1024 * 1024:
                message = "Consumer structured evidence exceeds 8 MiB: " + path.name
                state.setdefault("evidenceErrors", []).append(message)
                if state["status"] != "FAILED":
                    state.update(status="FAILED", error=message)
                code = 1
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
