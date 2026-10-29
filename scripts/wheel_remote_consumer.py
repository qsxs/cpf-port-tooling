"""公开 Pages Wheel 与 Lyricist 公开制品消费者；仅下载公开制品和锁定构建工具。"""
from __future__ import annotations
import io
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
import zipfile
from grid_remote_consumer import digest, klib_payload, public_url, read_http, record, tail, write_json

ROOT = Path(__file__).resolve().parents[1]
PAGES = 'https://qsxs.github.io/cpf-maven/'
GROUP = 'io.github.qsxs.cpf.lyricist'
WHEEL_GROUP = 'io.github.qsxs.cpf.wheel'
WHEEL_MODULE = 'datetime-wheel-picker'
MODULES = ('datetime-wheel-picker', 'lyricist', 'lyricist-core')
LYRICIST_MODULES = ('lyricist', 'lyricist-core')
LYRICIST_COMMIT = 'fad3d9091c75927320da3511350202e681269b2a'
LYRICIST_VERSION = '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1'
TOOL_REVISION = 'd0cff88fd1ea2e4f08bb4409f1c802cca0c7f285'
TOOL_DIR = 'toolchains/kotlin-native/2.4.20-0.1.0-08'
WRAPPER_COMMIT = 'e73ecdbb9a38897c7e5cc47467bf1197a076191a'

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
 'sourceRepository': 'qsxs/compose-datetime-wheel-picker',
 'sourceCommit': 'e73ecdbb9a38897c7e5cc47467bf1197a076191a',
 'files': [{'path': 'gradlew',
            'size': 363,
            'sha256': '0e96228f9589965a5e171190f69f6e820f128bdae180f7e2acc6e4d65f788ed5',
            'url': 'https://raw.githubusercontent.com/qsxs/compose-datetime-wheel-picker/e73ecdbb9a38897c7e5cc47467bf1197a076191a/ohos/gradlew'},
           {'path': 'gradle/wrapper/gradle-wrapper.jar',
            'size': 43764,
            'sha256': '7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172',
            'url': 'https://raw.githubusercontent.com/qsxs/compose-datetime-wheel-picker/e73ecdbb9a38897c7e5cc47467bf1197a076191a/ohos/gradle/wrapper/gradle-wrapper.jar'},
           {'path': 'gradle/wrapper/gradle-wrapper.properties',
            'size': 339,
            'sha256': '93b4f2c5ddcfc9e6f630fc7e004b31b389695cd0228be6da42e196e5d4af7acb',
            'url': 'https://raw.githubusercontent.com/qsxs/compose-datetime-wheel-picker/e73ecdbb9a38897c7e5cc47467bf1197a076191a/ohos/gradle/wrapper/gradle-wrapper.properties'},
           {'path': 'gradle.properties',
            'size': 314,
            'sha256': '993600cfde45bf43788143c6eb2ebab1949c733ef38cc4abc3437c6e2112ed40',
            'url': 'https://raw.githubusercontent.com/qsxs/compose-datetime-wheel-picker/e73ecdbb9a38897c7e5cc47467bf1197a076191a/ohos/gradle.properties'}]}

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
 'org.jetbrains.compose.components:components-ui-tooling-preview-ohosArm64': '1.12.0-0.1.0-11',
 'io.github.qsxs.cpf.lyricist:lyricist': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'io.github.qsxs.cpf.lyricist:lyricist-ohosx64': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'io.github.qsxs.cpf.lyricist:lyricist-ohosarm64': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'io.github.qsxs.cpf.lyricist:lyricist-core': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'io.github.qsxs.cpf.lyricist:lyricist-core-ohosx64': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'io.github.qsxs.cpf.lyricist:lyricist-core-ohosarm64': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1'}

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
 'scope': 'HOST_COMPOSE_COMPILER_PLUGIN_ONLY',
 'compilerTasks': ['compileCommonMainKotlinMetadata', 'compileKotlinOhosX64', 'compileKotlinOhosArm64'],
 'pins': {'org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable': '2.4.20-0.1.0-08'},
 'artifacts': {'org.jetbrains.kotlin:kotlin-compose-compiler-plugin-embeddable': {'size': 870498,
                                                                                  'sha256': '4ffe7f38089fa4acdda5d67fa3a858b9fc2fe7ed1f2e58bedbf8d3447c15df39',
                                                                                  'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-compose-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.jar'}},
 'sourcePom': {'path': 'vendor/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom',
               'size': 1257,
               'sha256': 'd38ccafd8914713808fb9d66a5deb11b742dcd05d6420e8b0351ca146795540b',
               'url': 'https://maven.eazytec-cloud.com/nexus/repository/maven-develop/org/jetbrains/kotlin/kotlin-compose-compiler-plugin-embeddable/2.4.20-0.1.0-08/kotlin-compose-compiler-plugin-embeddable-2.4.20-0.1.0-08.pom'},
 'directRuntimeDependencies': []}

SOURCE_LOCK = {'lyricist': {'sources': {'path': 'vendor/lyricist-1.8.0-sources.jar',
                          'size': 1287,
                          'sha256': '7ace8ee1feb973684e4ec4f45867617d3377601706f835ed8da09eb1e61646fa'},
              'pom': {'path': 'vendor/lyricist-1.8.0.pom',
                      'size': 2165,
                      'sha256': '1a2784b43542b74576139dbdcb5aa09d5be52199a90f7a8b58fe82d10f44906c'},
              'gmm': {'path': 'vendor/lyricist-1.8.0.module',
                      'size': 23875,
                      'sha256': '0c7aedd9dfde5ff8dc138e62a92d352338d436e21555526a105516be175683a8'},
              'upstreamBuild': {'path': 'vendor/lyricist-upstream-build.gradle.kts',
                                'size': 564,
                                'sha256': '4a530c856f27b992f6d27227c330ace79b431519ac3f28e262e6652b61d11e1b'},
              'license': {'path': 'legal/LYRICIST-LICENSE.md',
                          'size': 1080,
                          'sha256': 'b55f5b44f477d275044af430d3d8d1c0eb644bf586459c89226b216e1c225929'},
              'sourceMembers': [{'member': 'commonMain/cafe/adriel/lyricist/LyricistCompose.kt',
                                 'size': 1081,
                                 'sha256': 'd2a05223d74fb92311dfcd31f5358bba40688cfe925c79d5df8b1d901ebf38e1'}],
              'sourceSetSha256': '1d19633d4a69cb3760212b1c056de8955f0c55775056e24b3e906b3e06e7377d',
              'sourceDependencies': {'api': ['io.github.qsxs.cpf.lyricist:lyricist-core'],
                                     'implementation': ['org.jetbrains.kotlinx:kotlinx-coroutines-core'],
                                     'compileOnly': ['org.jetbrains.compose.runtime:runtime',
                                                     'org.jetbrains.compose.ui:ui']},
              'publicApi': {'declarations': [{'owner': 'cafe.adriel.lyricist.rememberStrings',
                                              'kind': 'function',
                                              'name': 'rememberStrings',
                                              'visibility': 'public',
                                              'visibilityOrigin': 'explicit',
                                              'member': 'commonMain/cafe/adriel/lyricist/LyricistCompose.kt',
                                              'sourceLine': 13,
                                              'sourceSignature': 'public fun <T> rememberStrings(\n'
                                                                 '    translations: Map<LanguageTag, T>,\n'
                                                                 '    defaultLanguageTag: LanguageTag = "en",\n'
                                                                 '    currentLanguageTag: LanguageTag = '
                                                                 'Locale.current.toLanguageTag()\n'
                                                                 '): Lyricist<T>',
                                              'metadataPattern': '^cafe\\.adriel\\.lyricist/rememberStrings\\|rememberStrings\\(kotlin\\.collections\\.Map<kotlin\\.String,[^;]+>;kotlin\\.String;kotlin\\.String\\)',
                                              'evidenceChannel': 'metadata',
                                              'typeParameters': ['T'],
                                              'parameterTypes': ['Map<LanguageTag,T>', 'LanguageTag', 'LanguageTag']},
                                             {'owner': 'cafe.adriel.lyricist.ProvideStrings',
                                              'kind': 'function',
                                              'name': 'ProvideStrings',
                                              'visibility': 'public',
                                              'visibilityOrigin': 'explicit',
                                              'member': 'commonMain/cafe/adriel/lyricist/LyricistCompose.kt',
                                              'sourceLine': 25,
                                              'sourceSignature': 'public fun <T> ProvideStrings(\n'
                                                                 '    lyricist: Lyricist<T>,\n'
                                                                 '    provider: ProvidableCompositionLocal<T>,\n'
                                                                 '    content: @Composable () -> Unit\n'
                                                                 ')',
                                              'metadataPattern': '^cafe\\.adriel\\.lyricist/ProvideStrings\\|ProvideStrings\\(cafe\\.adriel\\.lyricist\\.Lyricist<[^;]+>;androidx\\.compose\\.runtime\\.ProvidableCompositionLocal<[^;]+>;kotlin\\.Function0<kotlin\\.Unit>\\)',
                                              'evidenceChannel': 'metadata',
                                              'typeParameters': ['T'],
                                              'parameterTypes': ['Lyricist<T>',
                                                                 'ProvidableCompositionLocal<T>',
                                                                 '@Composable () -> Unit']}],
                            'languageGeneratedMembers': [],
                            'excluded': [],
                            'expectActual': []},
              'gitSources': {'commonMain/cafe/adriel/lyricist/LyricistCompose.kt': 'lyricist-compose/src/commonMain/kotlin/cafe/adriel/lyricist/LyricistCompose.kt'},
              'gitBlob': 'd5159a08f0bc6a488c1b5760fa45c92540c65306'},
 'lyricist-core': {'sources': {'path': 'vendor/lyricist-core-1.8.0-sources.jar',
                               'size': 1238,
                               'sha256': '0ca9071f050457c8e3c164c6824168fc2d8827121879786681e9450035a368d6'},
                   'pom': {'path': 'vendor/lyricist-core-1.8.0.pom',
                           'size': 1989,
                           'sha256': 'ce8232349214f698f2fed343c475be7da6366363bf53341914c75680514d7135'},
                   'gmm': {'path': 'vendor/lyricist-core-1.8.0.module',
                           'size': 19178,
                           'sha256': 'ad80662c94abedd168f242140fa47be64edebcfdead61530ae14a67eacd76b38'},
                   'upstreamBuild': {'path': 'vendor/lyricist-core-upstream-build.gradle.kts',
                                     'size': 359,
                                     'sha256': '947f6436adf854e07f379d72263d80b9547623822742190b6ff10b80ccbb4449'},
                   'license': {'path': 'legal/LYRICIST-LICENSE.md',
                               'size': 1080,
                               'sha256': 'b55f5b44f477d275044af430d3d8d1c0eb644bf586459c89226b216e1c225929'},
                   'sourceMembers': [{'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                      'size': 1734,
                                      'sha256': 'b0a3cff0ddc964a978193c79f5c7ce65208c4abf8f13754943ec30185aec9d69'}],
                   'sourceSetSha256': 'b16f0be3c10541911d0a1a658c5314034a2210f41f05660a43fe17a163185403',
                   'sourceDependencies': {'api': [],
                                          'implementation': ['org.jetbrains.kotlinx:kotlinx-coroutines-core'],
                                          'compileOnly': []},
                   'publicApi': {'declarations': [{'owner': 'cafe.adriel.lyricist.LanguageTag',
                                                   'kind': 'typealias',
                                                   'name': 'LanguageTag',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 7,
                                                   'sourceSignature': 'public typealias LanguageTag = String',
                                                   'metadataPattern': None,
                                                   'evidenceChannel': 'metadata-dump',
                                                   'metadataDumpPattern': '(?i)typealias\\s+LanguageTag\\b',
                                                   'runtimeType': False},
                                                  {'owner': 'cafe.adriel.lyricist.Lyricist',
                                                   'kind': 'class',
                                                   'name': 'Lyricist',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 9,
                                                   'sourceSignature': 'public class Lyricist<T>(\n'
                                                                      '    private val defaultLanguageTag: '
                                                                      'LanguageTag,\n'
                                                                      '    private val translations: Map<LanguageTag, '
                                                                      'T>\n'
                                                                      ')',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/Lyricist\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistState',
                                                   'kind': 'data class',
                                                   'name': 'LyricistState',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 43,
                                                   'sourceSignature': 'public data class LyricistState<T> internal '
                                                                      'constructor(\n'
                                                                      '    val languageTag: LanguageTag,\n'
                                                                      '    val strings: T,\n'
                                                                      ')',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistState\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistException',
                                                   'kind': 'class',
                                                   'name': 'LyricistException',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 48,
                                                   'sourceSignature': 'public class LyricistException internal '
                                                                      'constructor(\n'
                                                                      '    override val message: String\n'
                                                                      ') : RuntimeException()',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistException\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistStrings',
                                                   'kind': 'annotation class',
                                                   'name': 'LyricistStrings',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 54,
                                                   'sourceSignature': 'public annotation class LyricistStrings(\n'
                                                                      '    val languageTag: LanguageTag,\n'
                                                                      '    val default: Boolean = false\n'
                                                                      ')',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistStrings\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.Lyricist.state',
                                                   'kind': 'property',
                                                   'name': 'state',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 16,
                                                   'sourceSignature': '',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/Lyricist\\.state\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.Lyricist.languageTag',
                                                   'kind': 'property',
                                                   'name': 'languageTag',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 19,
                                                   'sourceSignature': '',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/Lyricist\\.languageTag\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.Lyricist.strings',
                                                   'kind': 'property',
                                                   'name': 'strings',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 25,
                                                   'sourceSignature': '',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/Lyricist\\.strings\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistState.languageTag',
                                                   'kind': 'property',
                                                   'name': 'languageTag',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 44,
                                                   'sourceSignature': 'val languageTag: LanguageTag,',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.languageTag\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistState.strings',
                                                   'kind': 'property',
                                                   'name': 'strings',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 45,
                                                   'sourceSignature': 'val strings: T,',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.strings\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistException.message',
                                                   'kind': 'property',
                                                   'name': 'message',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 49,
                                                   'sourceSignature': 'override val message: String',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistException\\.message\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistStrings.languageTag',
                                                   'kind': 'property',
                                                   'name': 'languageTag',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 55,
                                                   'sourceSignature': 'val languageTag: LanguageTag,',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistStrings\\.languageTag\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistStrings.default',
                                                   'kind': 'property',
                                                   'name': 'default',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 56,
                                                   'sourceSignature': 'val default: Boolean = false',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistStrings\\.default\\|',
                                                   'evidenceChannel': 'metadata'},
                                                  {'owner': 'cafe.adriel.lyricist.Lyricist.<init>',
                                                   'kind': 'constructor',
                                                   'name': '<init>',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 9,
                                                   'sourceSignature': 'public class Lyricist<T>(\n'
                                                                      '    private val defaultLanguageTag: '
                                                                      'LanguageTag,\n'
                                                                      '    private val translations: Map<LanguageTag, '
                                                                      'T>\n'
                                                                      ')',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/Lyricist\\.<init>\\|<init>\\(kotlin\\.String;kotlin\\.collections\\.Map<kotlin\\.String,[^;]+>\\)',
                                                   'evidenceChannel': 'metadata',
                                                   'parameterTypes': ['kotlin.String',
                                                                      'kotlin.collections.Map<kotlin.String,T>']},
                                                  {'owner': 'cafe.adriel.lyricist.LyricistStrings.<init>',
                                                   'kind': 'constructor',
                                                   'name': '<init>',
                                                   'visibility': 'public',
                                                   'visibilityOrigin': 'explicit',
                                                   'member': 'commonMain/cafe.adriel.lyricist/Lyricist.kt',
                                                   'sourceLine': 54,
                                                   'sourceSignature': 'public annotation class LyricistStrings(\n'
                                                                      '    val languageTag: LanguageTag,\n'
                                                                      '    val default: Boolean = false\n'
                                                                      ')',
                                                   'metadataPattern': '^cafe\\.adriel\\.lyricist/LyricistStrings\\.<init>\\|<init>\\(kotlin\\.String;kotlin\\.Boolean\\)',
                                                   'evidenceChannel': 'metadata',
                                                   'parameterTypes': ['kotlin.String', 'kotlin.Boolean']}],
                                 'languageGeneratedMembers': [{'owner': 'cafe.adriel.lyricist.LyricistState.component1',
                                                               'kind': 'data generated',
                                                               'name': 'component1',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.component1\\|',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'public'},
                                                              {'owner': 'cafe.adriel.lyricist.LyricistState.component2',
                                                               'kind': 'data generated',
                                                               'name': 'component2',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.component2\\|',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'public'},
                                                              {'owner': 'cafe.adriel.lyricist.LyricistState.equals',
                                                               'kind': 'data generated',
                                                               'name': 'equals',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.equals\\|',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'public'},
                                                              {'owner': 'cafe.adriel.lyricist.LyricistState.hashCode',
                                                               'kind': 'data generated',
                                                               'name': 'hashCode',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.hashCode\\|',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'public'},
                                                              {'owner': 'cafe.adriel.lyricist.LyricistState.toString',
                                                               'kind': 'data generated',
                                                               'name': 'toString',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.toString\\|',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'public'},
                                                              {'owner': 'cafe.adriel.lyricist.LyricistState.copy',
                                                               'kind': 'data generated',
                                                               'name': 'copy',
                                                               'signaturePattern': '^cafe\\.adriel\\.lyricist/LyricistState\\.copy\\|copy\\(',
                                                               'evidenceChannel': 'metadata-or-declaredIr',
                                                               'effectiveVisibility': 'CONSTRUCTOR_DERIVED_VERIFY_ACTUAL_METADATA_DUMP',
                                                               'note': 'Not an explicitly public source declaration; '
                                                                       'preserve generated implementation and inspect '
                                                                       'configured compiler visibility rather than '
                                                                       'assuming historical public copy.'}],
                                 'excluded': [{'owner': 'cafe.adriel.lyricist.LyricistState.<init>',
                                               'reason': 'internal constructor'},
                                              {'owner': 'cafe.adriel.lyricist.LyricistException.<init>',
                                               'reason': 'internal constructor'},
                                              {'reason': 'private backing state/helper/companion excluded'}],
                                 'expectActual': []},
                   'gitSources': {'commonMain/cafe.adriel.lyricist/Lyricist.kt': 'lyricist-core/src/commonMain/kotlin/cafe.adriel.lyricist/Lyricist.kt'},
                   'gitBlob': '5b07f4899df8350ea6fbe87237713cce59fcb16f'}}

WHEEL_LOCK = {'sources': [{'member': 'commonMain/dev/darkokoa/datetimewheelpicker/Strings.kt',
              'size': 3921,
              'sha256': '5f858835a582c183988a8063a132ca377b46cf963f6712ce7e2b856a7ac276a9',
              'origin': 'OFFICIAL_SOURCES_JAR_GENERATED_BY_KSP'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/WheelDatePicker.kt',
              'size': 5370,
              'sha256': '203bdfd054194d0b96c2eaafdf8ab223740093aa1991ce238de9e446266f2de5',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/WheelDatePicker.kt',
              'gitBlob': '2a8b63a7eb095a4c04887dd3d7dbc4bbc431a9b3'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/WheelDateTimePicker.kt',
              'size': 5975,
              'sha256': '6daedc769116bb71e4a5f659fd19080b04c9c417b8fdbc94e21868fe8303e596',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/WheelDateTimePicker.kt',
              'gitBlob': '0d68dc0e8ec5a8daf095daf051ebba2bcc9694f7'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/WheelTimePicker.kt',
              'size': 4786,
              'sha256': '6df54137047457c9ee6dcd9ec72a404c1147e7cbe980677acdb31041a505b452',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/WheelTimePicker.kt',
              'gitBlob': '5d1278d5e1f5e1850be1eb891000db2dbf102326'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/AdaptiveWheelDatePicker.kt',
              'size': 2388,
              'sha256': '9383bec1474fc627c1a09baecf4ce80be85d7d3410775174d571f26470e527b7',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/AdaptiveWheelDatePicker.kt',
              'gitBlob': '78062bff10e356757f22116d6b9f5fe7aae90e1f'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/AdaptiveWheelDateTimePicker.kt',
              'size': 7849,
              'sha256': '67060a7faf1c5c5de82cd7bcdff84ee9894ffe00b49bdbaa900da9c645d473c7',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/AdaptiveWheelDateTimePicker.kt',
              'gitBlob': '6612a04c3fc9ae423e57a1ab4cf4323e58742daf'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/CJKWheelDatePicker.kt',
              'size': 10171,
              'sha256': '33cc8ce8f4439caf8701fd28b00ddad247987d9728c1f989be023ccfae6e7078',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/CJKWheelDatePicker.kt',
              'gitBlob': '24f49056f9ae4b3e5a9d31b5600f81dd515a566e'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/ChronoUnit.kt',
              'size': 124,
              'sha256': '3f34e223b21ff93333f03281716629ec28d39ec43e8178d3a35b946da695336b',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/ChronoUnit.kt',
              'gitBlob': '5ba8275871336d859d7a1d3f131e7fe81afbba0d'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/DateComponents.kt',
              'size': 2004,
              'sha256': '9bf1233523e3565310bbc5eaa6739a7b18de47941e518a5358c8e20b29806d40',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/DateComponents.kt',
              'gitBlob': 'a01d13c4a77bf59f162e3a9ce3f3a1bf7e956247'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/KLocalDateExt.kt',
              'size': 1837,
              'sha256': 'be4b32167c13249e7bdce4fbd8b65dd8c5d402fc9d6d51eb8dd07f55bfb04940',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/KLocalDateExt.kt',
              'gitBlob': '1b6acf4169761da00819dfefe8b7b6d920dfa877'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/KLocalDateTimeExt.kt',
              'size': 2451,
              'sha256': 'ff986be34d39d3ec6a0b998631c4c2d6bf6f00dca8d1531317a8f4f781db3417',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/KLocalDateTimeExt.kt',
              'gitBlob': 'cc7fd891f68b3373d6137a450bb9d8ee2bb41c35'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/KLocalTimeExt.kt',
              'size': 1039,
              'sha256': '07bbcc360486322f7a373a68304b165cce3c024c5a9f1608d9858d3c2b70faad',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/KLocalTimeExt.kt',
              'gitBlob': '4a1c14895b86e59fcab4fe5502d5c63c15553659'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/LocaleExtensions.kt',
              'size': 1387,
              'sha256': '6435701396510bc0ede3ca70f53bf8e410cb47d1e6dd72dc1434a726da1c5e89',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/LocaleExtensions.kt',
              'gitBlob': '5544724f0eff8166910a52044ac23d634eea5583'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/PickerSize.kt',
              'size': 1561,
              'sha256': 'dd339c555d55025b131b194211c6a90f546e9fdb9d3233b01e8228798473f6d5',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/PickerSize.kt',
              'gitBlob': 'b08d90a752ffd97c64a9c22d88521795330a3149'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/SnappedDateTime.kt',
              'size': 1468,
              'sha256': 'b81080697de8214b71f160ef7c74faac0ccdd7d56dc2d1793938cf6847356623',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/SnappedDateTime.kt',
              'gitBlob': 'ca3f35a0bc12b5f3246b41208546594070ef8cb5'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/StandardWheelDatePicker.kt',
              'size': 9233,
              'sha256': 'b647c05581cbd3793b81397ad1e80ff13d1e0b221d8f49174208764310335ff5',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/StandardWheelDatePicker.kt',
              'gitBlob': '0b5df0636c45373a1a2ae9be9f2abf928a55e2c7'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/StandardWheelTimePicker.kt',
              'size': 15821,
              'sha256': 'c1571b3e0cb6a0e1df4e04c3cd1b1cd7428789b202517b5893145228eb9f70d3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/StandardWheelTimePicker.kt',
              'gitBlob': 'ec6e82d17fc4160921f76c366ef0ab48d5d14a82'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/WheelPicker.kt',
              'size': 6361,
              'sha256': 'd01372e44dcbdf5a18bb9cdb42ce93533f7b938702c43634257e0f6a10deda33',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/WheelPicker.kt',
              'gitBlob': '4bdd529cbfeef976320c1856a473824114ff3b99'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/WheelTextPicker.kt',
              'size': 8912,
              'sha256': '4d6c5be8301cdbfa23ad73e3030d4b4eacbcd73942be42f63c10624a87709688',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/WheelTextPicker.kt',
              'gitBlob': '52bbdf82c27b77cea73e6a77faaec5f8daf483ae'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/CjkSuffixConfig.kt',
              'size': 2824,
              'sha256': 'c9404618d68aeffea5bef44d5f2d0f1c90f0e95de298ebb42b45feb26b61542e',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/CjkSuffixConfig.kt',
              'gitBlob': '3e5a2cb4ce895c7216c506fdc6bea78ec324336e'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/DateField.kt',
              'size': 102,
              'sha256': '6341ed9cfc15fde3b86a0e0c0f6683447a968dbe4b203fd91b78ce882bd0aa55',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/DateField.kt',
              'gitBlob': 'da9c79acde185519c3c41222ac59e313b656dbcb'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/DateFormatter.kt',
              'size': 4624,
              'sha256': 'edc0458d9e24faa0a17cc2fe97b9a7c019870ab1b8951ed04332863d8d52510c',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/DateFormatter.kt',
              'gitBlob': 'e813324ce4d01826b9930a3a9c86318e31ff48a1'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/DateOrder.kt',
              'size': 693,
              'sha256': '4bf006db774ee5ef64ea191c8b37d78b314abaf6f9b181fa059cbbac5d7395d3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/DateOrder.kt',
              'gitBlob': '3afece665e800057a2d2843ea578809f2f438d64'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/LocalizedNumeralsExt.kt',
              'size': 1596,
              'sha256': '469fa064f25d461b5154bfb2b82f5f74bcc6c463dfb08d662181112c694424c3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/LocalizedNumeralsExt.kt',
              'gitBlob': '46f87e8abe3f52000c39c19e0d04b82643eab53c'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/MonthDisplayStyle.kt',
              'size': 191,
              'sha256': 'f4773671ca61df696a2ef221822ae6144dcc2d410818ebfb3d9c92a176c2d557',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/MonthDisplayStyle.kt',
              'gitBlob': '87067d614614603da6762ce5745eccbc6e81c768'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/TimeFormat.kt',
              'size': 152,
              'sha256': 'a696ba351d5c21a240bb5ba8bb54b182d580e08a5125772e8ee88c9942035fa9',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/TimeFormat.kt',
              'gitBlob': '167954295a51d422ff29adb1304198f8d74e3046'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/core/format/TimeFormatter.kt',
              'size': 2657,
              'sha256': '9fe0482deecf7cd1796b0a8b39eeff66f411831c1630d36f752a26f944a8bbe5',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/core/format/TimeFormatter.kt',
              'gitBlob': '0b4d4ccc957dc84e1e75041591f81e918bb59cbc'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ArStrings.kt',
              'size': 1217,
              'sha256': 'bdc174e46590ccc1d369416ff7445a263c16d0040082559a48db5749aeeca509',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ArStrings.kt',
              'gitBlob': 'c8a2f2600ae3e009ffdd784132a9925cb3e49e4b'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/BnStrings.kt',
              'size': 1121,
              'sha256': 'aaf42c332cb8262a9cce8916f198c5c4e5c257ef5b11acd13eaa89cb4e7246b3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/BnStrings.kt',
              'gitBlob': '706f58708336e19de3c1a3a068a322b7c1ae06ea'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/CsStrings.kt',
              'size': 888,
              'sha256': 'fe134bf7e0cc2a3790182789132454cac20a21d0fc503494ac04f3c251987c1b',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/CsStrings.kt',
              'gitBlob': 'ce9d489ec51ba26f738113d43b98b98972820427'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/DaStrings.kt',
              'size': 880,
              'sha256': '2ec12e2057a6cf38b71b2bf23c35c26ac20ed5cea92c567425df2a0ee509c613',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/DaStrings.kt',
              'gitBlob': '52a194ed2c48e929eb894fe3bdeeb15c3bc5f26d'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/DeStrings.kt',
              'size': 881,
              'sha256': '27a16db054cecb46e57006ddfcea659c7a6afd07c4beda55c460f1a80507d099',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/DeStrings.kt',
              'gitBlob': '30d94a433ffd980589a27219a1262304d4f6c4bf'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ElStrings.kt',
              'size': 1043,
              'sha256': 'dbdc7c24ddf4dd51ba236eeec26ffd5116856a80ac275a28f1dc2ff640076fc5',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ElStrings.kt',
              'gitBlob': '706c546ee430e030aec7839b75108c6315839407'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/EnStrings.kt',
              'size': 182,
              'sha256': '4bfb1a4ccc477500fa94c31165a7e5410165d4fb17f8a01a1d0996c1ab1161bb',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/EnStrings.kt',
              'gitBlob': 'db4764911d6cba3f66f855ddec96479cd39699e7'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/EsStrings.kt',
              'size': 914,
              'sha256': '59705879366a5d01dcbfa273c07c1595f1c6113c86515b0d88ea5795907c40ba',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/EsStrings.kt',
              'gitBlob': 'a13349b59ee6d2e29404d227b5360925a6e5b86d'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/FaStrings.kt',
              'size': 1159,
              'sha256': '2f28c0d84d29b4dab97a46c485ef39d50252ce85521686ecf84d4af116a3a026',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/FaStrings.kt',
              'gitBlob': '6e3590c49ea6c00a9a638fb16ca985f2b713fec3'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/FiStrings.kt',
              'size': 963,
              'sha256': '2c0d16062252db3f8041082aff30ff943ba9e172688fa780281853efcee99889',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/FiStrings.kt',
              'gitBlob': 'c83c3ac028417f79fe515d2545df8773825487c8'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/FrStrings.kt',
              'size': 890,
              'sha256': '5f4c947ee433534057263c1a1fc3862452d07a690e5c312fb9b5562ebc718e70',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/FrStrings.kt',
              'gitBlob': '941c110f39694dc6fd8309e9317c97214c3306af'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/HeStrings.kt',
              'size': 1063,
              'sha256': '5f057a29e205e42c93954ab9fc0299c8849394a40b310f33dd99cf65040684d9',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/HeStrings.kt',
              'gitBlob': '21cc29e168113af29c054410145575a176b7ff29'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/HiStrings.kt',
              'size': 1120,
              'sha256': '0768a6f4b61071bcf8a28331eeba47e97b6ef9e6db18975035cd9e085e00fe6e',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/HiStrings.kt',
              'gitBlob': 'f777b2454867c0abe7972feba20b04e6895b7849'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/IdStrings.kt',
              'size': 872,
              'sha256': '0707cc5b3a85acd79b8a249e005d305d2512bb621c44de77f90dd724cdf67ef3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/IdStrings.kt',
              'gitBlob': '950b27a3cea3154769691ba58183661154a0717f'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ItStrings.kt',
              'size': 878,
              'sha256': 'f540d436a057f17c76f13e113c5cd63f05c03144bf56b56fec3731a019234357',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ItStrings.kt',
              'gitBlob': '06864b938d199522d30839b87f94f667684e29eb'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/JaStrings.kt',
              'size': 900,
              'sha256': 'eda6addfd28a172cb2f87ab0582c8806e62600c6acc7651880e20bd417da3aed',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/JaStrings.kt',
              'gitBlob': '443eefe4ed31f7ebfa30801f8f14a31f41468c7e'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/KoStrings.kt',
              'size': 900,
              'sha256': '655db3223f0da80bd1938a096955d4cc5bb45231478d7477e1cc18cdcfb08fba',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/KoStrings.kt',
              'gitBlob': '1cddecdafc29bc97c9e34969cdc0185aae0cdc89'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/NbStrings.kt',
              'size': 879,
              'sha256': '27ceb4951e82f533242a8e3a21608b079a0788a5e1530248101267f5e1f44aad',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/NbStrings.kt',
              'gitBlob': 'd6ab88405d7a006764c06f3f5484f647cd7df7e3'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/NlStrings.kt',
              'size': 917,
              'sha256': 'a6b50218c99afc451208a2450e49e5249c6aa3b47aa9b8d1c571f51eb3993da3',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/NlStrings.kt',
              'gitBlob': '3bbf9b40469968fc574c4da6fb98ba6723eaf6ba'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/NoStrings.kt',
              'size': 167,
              'sha256': 'eba9200973ff758689d4fb1fea8e1692b51802770c8a0f11a81f662bf9fa3c6b',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/NoStrings.kt',
              'gitBlob': '98175bafdabe37ffced8f29df96aea0af4e44407'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/PlStrings.kt',
              'size': 886,
              'sha256': '8c4e9aeb2616ec8b84a90e2b5c0048cd78c81d0b687c29d66ad1909e7273768d',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/PlStrings.kt',
              'gitBlob': 'e2df3da80e56e4165324b262d2b6963334975de6'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/PtStrings.kt',
              'size': 886,
              'sha256': '38e8ad81d165a10b975adcffd97fa265ab84fa4de2466a040ffcbff878ec7bcc',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/PtStrings.kt',
              'gitBlob': '93fca8a4115fb62c656e8934b9ff4e1d1805968b'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/RoStrings.kt',
              'size': 895,
              'sha256': 'd36bb717556b17a913482c25dd0c64bfbe5b4582d985a589821d77824fbddf4f',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/RoStrings.kt',
              'gitBlob': '30fea0f3dcd818f5786e3facfe43f750bb4ccd4a'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/RuStrings.kt',
              'size': 989,
              'sha256': '4dfbdbed022f33e46d95ef5268337ad6652271bc754f5c6f14350a4a973cbc8b',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/RuStrings.kt',
              'gitBlob': 'b40943b96cce6ed55e8cabc4e3f9c33147cfbeed'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/Strings.kt',
              'size': 1485,
              'sha256': 'b62d5855f05f3992be39e52f9b68b1ec371213ff52edb9d6df57e6c2cf26c357',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/Strings.kt',
              'gitBlob': '5555c7657efcfd56cf5725cfae896d6a133157a1'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/SvStrings.kt',
              'size': 882,
              'sha256': '3bc5cd41762186ffac25b39af3733bb61757beff5b620ec749651120fd8cd3b9',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/SvStrings.kt',
              'gitBlob': '791caead2da45a85fdf698491844cfe93de90eae'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ThStrings.kt',
              'size': 1177,
              'sha256': '0e87946b8a6f6910f98dda6747126cba554361f505471b1d8e3ff8c00e78aa16',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ThStrings.kt',
              'gitBlob': '7917b155b12f52c6baddc1b8765d54c5940db33a'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/TrStrings.kt',
              'size': 904,
              'sha256': 'ae450409eb233bda72ff51dd78aa32a257444a011ff02b882ec1beb21e91fe61',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/TrStrings.kt',
              'gitBlob': 'de5236198499ac9f3ab1ebe2bf50bdbe9a709f0a'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/UkStrings.kt',
              'size': 1046,
              'sha256': '929e9b167f229485432b3ea1704652dd91d828b72f379cd41590c5c38a35831a',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/UkStrings.kt',
              'gitBlob': 'aaddc072a790e629ae90a82cb2a6b52d45957067'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/UzArabStrings.kt',
              'size': 1157,
              'sha256': 'ac408990a202b9ab026beabbfeb032edd437d21c5474f9868e13942f7d05f65d',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/UzArabStrings.kt',
              'gitBlob': 'a2df32a8e6f213af72afd53db11f7c7990e45d18'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/UzCyrlStrings.kt',
              'size': 1016,
              'sha256': '6a2a2fbc688bccacc21d5a5686a3903b9adca04333f52df80e969bfaf14d29ca',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/UzCyrlStrings.kt',
              'gitBlob': 'fdba5fbe35de4ee02580d30f0aa1290aca0c0d04'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/UzStrings.kt',
              'size': 894,
              'sha256': '89cae80448eca3bce186e731cac48f53639655bcc0ee75962bc3b62c1a149953',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/UzStrings.kt',
              'gitBlob': 'c820e3d2c5b781bbb60945df55317cca2f0518a5'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ViStrings.kt',
              'size': 958,
              'sha256': '8ceee755775c731b25518ff2755c576deb2376c09989e1f64cf5920864a2fe2b',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ViStrings.kt',
              'gitBlob': 'b655b644346529dca7d0fc421a02fe525f3fc101'},
             {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/strings/ZhStrings.kt',
              'size': 900,
              'sha256': 'd1c5d6ee3806036cc9cd8f1dacda12c6d3a49fa0c4005dcb087a7219a222cbf4',
              'origin': 'UPSTREAM_GIT_BLOB',
              'gitPath': 'datetime-wheel-picker/src/commonMain/kotlin/dev/darkokoa/datetimewheelpicker/strings/ZhStrings.kt',
              'gitBlob': '70a4e3d78e01b9526a716edad25dd2c2e405b7f2'}],
 'sourceSetSha256': '6dabb50939110cddbc36a2c45ac183b3fa2909e31991bae8a9d030eca6fa5930',
 'generatedSource': {'member': 'commonMain/dev/darkokoa/datetimewheelpicker/Strings.kt',
                     'size': 3921,
                     'sha256': '5f858835a582c183988a8063a132ca377b46cf963f6712ce7e2b856a7ac276a9',
                     'origin': 'OFFICIAL_SOURCES_JAR_GENERATED_BY_KSP'},
 'upstreamFiles': [{'path': 'vendor/datetime-wheel-picker-1.4.0-sources.jar',
                    'size': 50168,
                    'sha256': 'cd8c95516665c5ecbd0d5f7e13e1703a8a18ebd65f219d8d3ec803eaa82ed307'},
                   {'path': 'vendor/datetime-wheel-picker-1.4.0.pom',
                    'size': 2662,
                    'sha256': '17afcaf3cb293a253ba99a9c02290717d68df4d40f5f27491f6e7245a4acdbf6'},
                   {'path': 'vendor/datetime-wheel-picker-1.4.0.module',
                    'size': 17102,
                    'sha256': '46963627919a42f08f01907e4586a0b97043d58b44ac9dcf3f673d5ad611a2d0'},
                   {'path': 'vendor/upstream-build.gradle.kts',
                    'size': 2931,
                    'sha256': '319c281d814162e49013a1a678c916ec53b141f3313fd860c260963bfa372733'},
                   {'path': 'legal/LICENSE',
                    'size': 11357,
                    'sha256': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'},
                   {'path': 'vendor/datetime-wheel-picker-iosarm64-1.4.0.pom',
                    'size': 2735,
                    'sha256': 'bb2023dcbb3de05fc794fded99edc8e0466bb36cb8d1f9c1362bbee8f157f0de'},
                   {'path': 'vendor/datetime-wheel-picker-iosarm64-1.4.0.module',
                    'size': 6895,
                    'sha256': 'f668693581abfafa95c690dfa177bf2c2efe103a961b382bfb4ead868ec7452e'}],
 'privateLicense': {'name': 'The Apache Software License, Version 2.0',
                    'url': 'http://www.apache.org/licenses/LICENSE-2.0.txt'},
 'license': {'path': 'legal/LICENSE',
             'size': 11357,
             'sha256': 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'},
 'sourcesJar': {'path': 'vendor/datetime-wheel-picker-1.4.0-sources.jar',
                'size': 50168,
                'sha256': 'cd8c95516665c5ecbd0d5f7e13e1703a8a18ebd65f219d8d3ec803eaa82ed307'},
 'pom': {'path': 'vendor/datetime-wheel-picker-1.4.0.pom',
         'size': 2662,
         'sha256': '17afcaf3cb293a253ba99a9c02290717d68df4d40f5f27491f6e7245a4acdbf6'},
 'gmm': {'path': 'vendor/datetime-wheel-picker-1.4.0.module',
         'size': 17102,
         'sha256': '46963627919a42f08f01907e4586a0b97043d58b44ac9dcf3f673d5ad611a2d0'},
 'upstreamBuild': {'path': 'vendor/upstream-build.gradle.kts',
                   'size': 2931,
                   'sha256': '319c281d814162e49013a1a678c916ec53b141f3313fd860c260963bfa372733'},
 'publicApiSha256': 'c06ecc019647854d3efa41b909bbbe0b3d58645cfa6f56ca4d9f2d1e63f05af3'}

LYRICIST_INPUT = {'schemaVersion': 1,
 'repository': 'https://qsxs.github.io/cpf-maven/',
 'group': 'io.github.qsxs.cpf.lyricist',
 'version': '1.8.0-cpf11-preview-fad3d9091c75-40827525373-1',
 'sourceCommit': 'fad3d9091c75927320da3511350202e681269b2a',
 'fingerprint': '3fca02e7dea92db2eb7e7066f7d35898fbc44490ca7003fdfca3c2bf82b8ca9d',
 'modules': {'lyricist': {'metadataArtifact': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.jar',
                                               'size': 6486,
                                               'sha256': '26925da689ef45c5c59cb118fb11ea75d6ef235c12fe998f72cfb4385690e0c1'},
                          'metadataPayload': {'default/manifest': {'size': 305,
                                                                   'sha256': '80a36bbd8fc58a20763376448410daa9074884c37596184b36f9d717513f13e2'},
                                              'default/linkdata/module': {'size': 73,
                                                                          'sha256': '6e892f46365976c6850e0da2fad4137f37d15a5fff931e87551c71ec64f284c9'},
                                              'default/linkdata/package_cafe.adriel.lyricist/0_lyricist.knm': {'size': 584,
                                                                                                               'sha256': '4a3333f7984ee2c81389d9e4f0a95957dcdc19afd89252418c57dda13c6196a9'}},
                          'nativeArtifacts': {'ohos_x64': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-ohosx64/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-ohosx64-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.klib',
                                                           'size': 10393,
                                                           'sha256': 'c9a4ec6cec181ade813c2170f8750bfd75e740a3e6abf1ed6f199dbbbdc0164e'},
                                              'ohos_arm64': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-ohosarm64/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-ohosarm64-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.klib',
                                                             'size': 10406,
                                                             'sha256': '0365ffbfc39c77d62a4bd0bd97b5dc1b4755568445d34f712461a2acf581a7d5'}},
                          'provenanceSha256': '0386c5767f60a93df79fa503939a7236ffd3dd3f582a326544d3ae845d97bac4'},
             'lyricist-core': {'metadataArtifact': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-core/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-core-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.jar',
                                                    'size': 6983,
                                                    'sha256': 'ad271fde372f62f345820e43c8ef268976370942a2aa1f55c4e07380e1a96890'},
                               'metadataPayload': {'default/manifest': {'size': 315,
                                                                        'sha256': 'bbc627d429e93e1eca0b679a23547f04f8dfe2b24f27899081e366aef9982f25'},
                                                   'default/linkdata/module': {'size': 78,
                                                                               'sha256': '3f9ac680fd67908b79da5ba96c36ce2f20e9081b69f6e7547bb459da53cd6a2b'},
                                                   'default/linkdata/package_cafe.adriel.lyricist/0_lyricist.knm': {'size': 1465,
                                                                                                                    'sha256': 'e0e30dd78c00527703ae1add62e9fd8bd7c45f03eb315209cff0bfaf0d69ced4'}},
                               'nativeArtifacts': {'ohos_x64': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-core-ohosx64/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-core-ohosx64-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.klib',
                                                                'size': 10979,
                                                                'sha256': '580dc14c78575b1e6dfd2e219b7040eacc0bddd3a8035ff0e89f9eff192f28d9'},
                                                   'ohos_arm64': {'url': 'https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-core-ohosarm64/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-core-ohosarm64-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.klib',
                                                                  'size': 10992,
                                                                  'sha256': '784f3f05ed958bbf5aa5b22e1f25e8a8becae1e54ce39e6f8aaa278266f8f63f'}},
                               'provenanceSha256': '0386c5767f60a93df79fa503939a7236ffd3dd3f582a326544d3ae845d97bac4'}}}

SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.lyricist"); excludeGroup("io.github.qsxs.cpf.wheel") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.lyricist"); excludeGroup("io.github.qsxs.cpf.wheel") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.lyricist"); excludeGroup("io.github.qsxs.cpf.wheel") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.lyricist"); excludeGroup("io.github.qsxs.cpf.wheel") } }
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.compose") version "2.4.20-0.1.0-08"
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
            forRepository { maven { name = "WheelPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.lyricist"); includeGroup("io.github.qsxs.cpf.wheel") }
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
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.lyricist"); excludeGroup("io.github.qsxs.cpf.wheel") } }
    }
}
rootProject.name = "wheel-pages-consumer"
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
val lyricistGroup = "io.github.qsxs.cpf.lyricist"
val lyricistVersion = "1.8.0-cpf11-preview-fad3d9091c75-40827525373-1"
val wheelGroup = "io.github.qsxs.cpf.wheel"
val wheelVersion = providers.gradleProperty("wheelVersion").get()
val probe = file("src/commonMain/kotlin/WheelConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val publicVersions = mapOf(wheelGroup to wheelVersion, lyricistGroup to lyricistVersion)
val pins = readMap(tools.resolve("dependency-pins.json"))
val metadataPins = readMap(tools.resolve("metadata-pins.json"))
val metadataTools = readMap(tools.resolve("metadata-toolchain.json"))
val launcherPins = asMap(metadataTools.getValue("launcherPins"))
val launcherArtifacts = asMap(metadataTools.getValue("launcherArtifacts"))
val commonizer = readMap(tools.resolve("commonizer-toolchain.json"))
val commonizerPins = launcherPins + asMap(commonizer.getValue("pins"))
val commonizerArtifacts = launcherArtifacts + asMap(commonizer.getValue("artifacts"))
val host = readMap(tools.resolve("native-compiler-toolchain.json"))
val hostPins = asMap(host.getValue("pins"))
val hostArtifacts = asMap(host.getValue("artifacts"))
val plugin = readMap(tools.resolve("compiler-plugin-toolchain.json"))
val pluginPins = asMap(plugin.getValue("pins"))
val pluginArtifacts = asMap(plugin.getValue("artifacts"))
val compileTasks = listOf("compileCommonMainKotlinMetadata", "compileKotlinOhosX64", "compileKotlinOhosArm64")
layout.buildDirectory.set(output.resolve("build"))
kotlin {
    ohosX64()
    ohosArm64()
    sourceSets {
        val commonMain by getting {
            kotlin.setSrcDirs(listOf(file("src/commonMain/kotlin")))
            dependencies { implementation("$wheelGroup:datetime-wheel-picker:$wheelVersion") }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
fun directDependencies(): List<String> {
    val actual = configurations.getByName("commonMainImplementation").dependencies.map { "${it.group}:${it.name}:${it.version}" }.sorted()
    val direct = actual.filterNot { it.startsWith("org.jetbrains.kotlin:kotlin-stdlib:") }.toSet()
    check(direct == setOf("$wheelGroup:datetime-wheel-picker:$wheelVersion")) { "Only the Wheel root may be direct" }
    return actual
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
        val selected = publicVersions[requested.group]
        if (selected != null) {
            check(requested.version == selected) { "Public dependency version differs: ${requested}" }
        } else {
            check(requested.group !in setOf("cafe.adriel.lyricist", "io.github.darkokoa")) { "Upstream coordinates cannot satisfy OHOS public consumption" }
            val ga = "${requested.group}:${requested.name}"
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
        check(fixed[ga] == id.version) { "Consumer tool version differs: $id" }
        val item = asMap(expected.getValue(ga))
        check(sha(artifact.file) == item["sha256"] && artifact.file.length() == (item.getValue("size") as Number).toLong()) { "Consumer tool bytes differ: $id" }
        mapOf("gav" to id.toString(), "files" to records(listOf(artifact.file)))
    }
    check(actual.size == fixed.size && actual.map { it.getValue("gav") }.toSet() == fixed.map { "${it.key}:${it.value}" }.toSet())
    return mapOf("configuration" to name, "edges" to edges(configuration), "artifacts" to actual)
}
fun pluginRecords() = compileTasks.map { name ->
    val compiler = tasks.getByName(name) as KotlinNativeCompile
    val actual = compiler.compilerPluginClasspath?.files.orEmpty().map { file ->
        val matched = pluginArtifacts.entries.singleOrNull { (_, value) ->
            val expected = asMap(value)
            sha(file) == expected["sha256"] && file.length() == (expected.getValue("size") as Number).toLong()
        } ?: error("Consumer compiler plugin bytes differ: $file")
        mapOf("gav" to "${matched.key}:${pluginPins.getValue(matched.key)}", "files" to records(listOf(file)))
    }
    check(actual.size == pluginPins.size)
    mapOf("task" to compiler.path, "artifacts" to actual)
}
fun toolRecords() = mapOf("nativeCompiler" to checkedTools(host.getValue("configuration").toString(), hostPins, hostArtifacts),
    "commonizer" to checkedTools(commonizer.getValue("configuration").toString(), commonizerPins, commonizerArtifacts), "plugins" to pluginRecords())
val publicModules = mapOf("datetime-wheel-picker" to wheelGroup, "lyricist" to lyricistGroup, "lyricist-core" to lyricistGroup)
fun resolution() = listOf("commonMainResolvableDependenciesMetadata", "ohosX64CompileKlibraries", "ohosArm64CompileKlibraries").map { name ->
    val configuration = configurations.getByName(name)
    val target = when (name) { "ohosX64CompileKlibraries" -> "ohos_x64"; "ohosArm64CompileKlibraries" -> "ohos_arm64"; else -> null }
    val manifests = asMap(http.getValue("modules"))
    val found = mutableMapOf<String, Int>()
    val artifacts = configuration.incoming.artifacts.artifacts.map { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier)
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        val module = publicModules.entries.singleOrNull { (base, group) ->
            id.group == group && id.module in listOf(base, "$base-ohosx64", "$base-ohosarm64")
        }?.key
        if (id.group in publicVersions.keys) {
            check(module != null) { "Unexpected public component: $id" }
            val info = asMap(manifests.getValue(module))
            check(id.version == publicVersions.getValue(id.group))
            val declared = if (target == null) (info.getValue("metadataArtifacts") as List<*>).map(::asMap)
                else (asMap(info.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
            if (target == null) check(id.module == module && attrs["org.jetbrains.kotlin.platform.type"] == "common" && attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf(module, module + if (target == "ohos_x64") "-ohosx64" else "-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            check(declared.any { it["sha256"] == sha(artifact.file) && (it.getValue("size") as Number).toLong() == artifact.file.length() }) {
                "Public artifact differs from anonymous HTTP: $id"
            }
            found[module] = (found[module] ?: 0) + 1
        } else {
            val ga = "${id.group}:${id.module}"
            val metadata = target == null
            check((if (metadata) metadataPins[ga] ?: pins[ga] else pins[ga]) == id.version) { "Unpinned resolved consumer dependency: $id" }
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
    check(publicModules.keys.all { found[it] == 1 }) { "Incomplete public graph for $name: $found" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$wheelGroup:datetime-wheel-picker:$wheelVersion" })
    check(graph.any { edge ->
        val from = edge.getValue("from").toString()
        from in listOf("$wheelGroup:datetime-wheel-picker:$wheelVersion", "$wheelGroup:datetime-wheel-picker-ohosx64:$wheelVersion", "$wheelGroup:datetime-wheel-picker-ohosarm64:$wheelVersion") &&
            edge.getValue("requested") == "$lyricistGroup:lyricist:$lyricistVersion"
    }) { "Wheel implementation dependency on Lyricist is absent: $name" }
    check(graph.any { edge ->
        val from = edge.getValue("from").toString()
        val requested = edge.getValue("requested").toString()
        from in listOf("$lyricistGroup:lyricist:$lyricistVersion", "$lyricistGroup:lyricist-ohosx64:$lyricistVersion", "$lyricistGroup:lyricist-ohosarm64:$lyricistVersion") &&
            requested == "$lyricistGroup:lyricist-core:$lyricistVersion"
    }) { "Lyricist api dependency on lyricist-core is absent: $name" }
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
fun publicTrace(compiler: KotlinNativeCompile, target: String?): Map<String, Any> {
    val manifests = asMap(http.getValue("modules"))
    val candidates = compiler.libraries.files.associateWith(::payload)
    return publicModules.keys.associateWith { module ->
        val info = asMap(manifests.getValue(module))
        val expected: Map<String, Map<String, Any>> = if (target == null) {
            asMap(info.getValue("metadataPayload")).mapValues { (_, value) ->
                val row = asMap(value)
                mapOf("size" to (row.getValue("size") as Number).toLong(), "sha256" to row.getValue("sha256")!!)
            }
        } else {
            val artifacts = (asMap(info.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
            check(artifacts.size == 1)
            payload(file(artifacts.single().getValue("path")!!))
        }
        check(expected.isNotEmpty())
        val matches = candidates.filterValues { it == expected }.keys
        check(matches.size == 1) { "Compiler library cannot be traced to public $module for $target" }
        mapOf("compilerLibrary" to matches.single().absolutePath, "payloadFileCount" to expected.size)
    }
}
val checkTools = tasks.register("verifyConsumerTools") {
    outputs.upToDateWhen { false }
    doLast { evidence("consumer-tools.json", toolRecords()) }
}
tasks.withType<KotlinNativeCompile>().configureEach { if (name in compileTasks) dependsOn(checkTools) }
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0" && System.getProperty("java.specification.version") == "17")
        evidence("consumer-resolution.json", mapOf("javaVersion" to System.getProperty("java.version"), "wheelVersion" to wheelVersion, "lyricistVersion" to lyricistVersion, "consumerDirectDependencies" to directDependencies(), "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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
                "plugins" to records(compiler.compilerPluginClasspath?.files.orEmpty()),
                "metadataTrace" to if (target == null) publicTrace(compiler, null) else null,
                "nativeTrace" to if (target == null) null else publicTrace(compiler, target),
                "metadataPayload" to metadata, "irPayload" to ir, "nativeTargets" to targets, "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
'''

PROBE = r'''package acceptance

import androidx.compose.runtime.Composable
import dev.darkokoa.datetimewheelpicker.WheelDatePicker
import dev.darkokoa.datetimewheelpicker.WheelDateTimePicker
import dev.darkokoa.datetimewheelpicker.core.format.TimeFormat
import dev.darkokoa.datetimewheelpicker.core.format.timeFormatter
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime

@Composable
fun wheelProbe(onDate: (LocalDate) -> Unit, onDateTime: (LocalDateTime) -> Unit) {
    WheelDatePicker(
        startDate = LocalDate(2024, 1, 1),
        minDate = LocalDate(1990, 1, 1),
        maxDate = LocalDate(2099, 12, 31),
        onSnappedDateChanged = onDate,
        onSnappedDate = onDate,
    )
    WheelDateTimePicker(
        startDateTime = LocalDateTime(2024, 1, 1, 12, 0),
        minDateTime = LocalDateTime(1990, 1, 1, 0, 0),
        maxDateTime = LocalDateTime(2099, 12, 31, 23, 59),
        timeFormatter = timeFormatter(timeFormat = TimeFormat.HOUR_24),
        onSnappedDateTimeChanged = onDateTime,
        onSnappedDateTime = onDateTime,
    )
}
'''

STAGES = ('Tasks', 'Resolve', 'Metadata', 'NativeX64', 'NativeArm64')
TASKS = {'Tasks': ['tasks', '--all'],
 'Resolve': ['resolveConsumer'],
 'Metadata': ['recordConsumerMetadata'],
 'NativeX64': ['recordConsumerX64'],
 'NativeArm64': ['recordConsumerArm64']}
REQUIRED = {'resolveConsumer', 'compileKotlinOhosX64', 'verifyConsumerTools', 'compileCommonMainKotlinMetadata', 'recordConsumerArm64', 'compileKotlinOhosArm64', 'recordConsumerMetadata', 'recordConsumerX64'}


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
    prefix = "https://raw.githubusercontent.com/qsxs/compose-datetime-wheel-picker/" + WRAPPER_COMMIT + "/ohos/"
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
    host_commit = None
    write_json(output / "evidence/toolchain-inputs.json", {"runtimeToolingCommit": TOOL_REVISION, "wrapperSourceCommit": WRAPPER_COMMIT,
        "wrapperSourceApplicationCommit": host_commit, "gradleVersion": "9.5.0",
        "files": rows, "librarySourceCheckout": False})
    return tools, wrapper_root


def verify_records(output, native_home, env, mode):
    evidence = output / "evidence"
    resolution = json.loads((evidence / "consumer-resolution.json").read_text())
    if len(resolution["configurations"]) != 3:
        raise RuntimeError("Consumer resolution evidence is incomplete")
    compilations = []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
        data = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text())
        if data["target"] != target or len(data["sources"]) != 1 or not data["metadataPayload"] or not data["outputs"]:
            raise RuntimeError("Consumer compilation proof is incomplete: " + name)
        if target is not None and (not data["irPayload"] or set(data["nativeTargets"]) != {target}):
            raise RuntimeError("Consumer Native IR or target differs: " + name)
        if target is None and set(data.get("metadataTrace", {})) != set(MODULES):
            raise RuntimeError("Consumer common metadata transform has no Pages trace")
        if (len(data["plugins"]) != 1 or data["plugins"][0]["size"] != 870498 or
                data["plugins"][0]["sha256"] != "4ffe7f38089fa4acdda5d67fa3a858b9fc2fe7ed1f2e58bedbf8d3447c15df39" or
                (target is not None and set(data.get("nativeTrace", {})) != set(MODULES))):
            raise RuntimeError("Consumer compiler plugin set or Native Pages trace differs")
        for item in [*data["sources"], *data["outputs"], *data["plugins"]]:
            if record(Path(item["path"])) != item:
                raise RuntimeError("Consumer compiler input/output bytes changed")
        compilations.append(data)
    write_json(evidence / "consumer-compilation.json", {"status": "METADATA_AND_DUAL_ABI_CONSUMER_COMPILED", "gradleVersion": "9.5.0",
        "compilations": compilations, "link": "NOT_RUN", "runtime": "NOT_RUN"})


def read_log_head(path):
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        data = stream.read(16 * 1024)
    text = data.decode("utf-8", errors="replace")
    return text.encode("utf-8")[:16 * 1024].decode("utf-8", errors="ignore")


def verify_provenance(data, version, source):
    value = json.loads(data)
    expected = {"group": GROUP, "version": version, "sourceCommit": source, "toolingCommit": TOOL_REVISION}
    if any(value.get(key) != item for key, item in expected.items()) or value.get("modules") != list(LYRICIST_MODULES):
        raise RuntimeError("Lyricist provenance identity differs")
    if value.get("upstream") != {"repository": "https://github.com/adrielcafe/lyricist", "version": "1.8.0", "commit": "89b8b6821b288164f71e5196f33d8f706c758fae", "license": "MIT"}:
        raise RuntimeError("Lyricist upstream identity differs")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("fingerprint", "")):
        raise RuntimeError("Lyricist provenance fingerprint differs")
    rows = value.get("sources", [])
    if len(rows) != 2 or {row.get("module") for row in rows} != set(LYRICIST_MODULES):
        raise RuntimeError("Lyricist source inventory differs")
    for module in LYRICIST_MODULES:
        locked = SOURCE_LOCK[module]
        original = value.get("sourceInputs", {}).get(module, {})
        for key in ("sources", "pom", "gmm", "upstreamBuild", "license", "sourceMembers", "sourceSetSha256", "sourceDependencies", "publicApi", "gitSources"):
            if original.get(key) != locked[key]:
                raise RuntimeError("Lyricist original input differs: " + module + ":" + key)
        row = next(item for item in rows if item["module"] == module)
        expected_source = locked["sourceMembers"][0]
        path = locked["gitSources"][expected_source["member"]]
        if any(row.get(key) != val for key, val in {**expected_source, "gitPath": path, "gitBlob": locked["gitBlob"]}.items()):
            raise RuntimeError("Lyricist Git source identity differs: " + module)
    return value


def verify_metadata_manifest(data, provenance):
    entry = "META-INF/upstream/source-manifest.json"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        matches = [item for item in archive.infolist() if item.filename == entry and not item.is_dir()]
        if len(matches) != 1:
            raise RuntimeError("Lyricist metadata source manifest missing or duplicated")
        raw = archive.read(matches[0])
    manifest = json.loads(raw)
    expected = {(module, row["member"]): (row["size"], row["sha256"]) for module in LYRICIST_MODULES for row in SOURCE_LOCK[module]["sourceMembers"]}
    rows = manifest.get("members", [])
    actual = {(row.get("module"), row.get("member")): (row.get("size"), row.get("sha256")) for row in rows}
    if (manifest.get("fingerprint") != provenance["fingerprint"] or manifest.get("sourceCount") != 2 or len(rows) != 2 or actual != expected or
            manifest.get("moduleSourceCounts") != {module: 1 for module in LYRICIST_MODULES} or
            manifest.get("sourceSetSha256") != {module: SOURCE_LOCK[module]["sourceSetSha256"] for module in LYRICIST_MODULES} or
            manifest.get("publicApi") != {module: SOURCE_LOCK[module]["publicApi"] for module in LYRICIST_MODULES}):
        raise RuntimeError("Lyricist metadata source manifest differs")
    return raw, {"entry": entry, "size": len(raw), "sha256": digest(raw), "fingerprint": manifest["fingerprint"], "sourceCount": 2}


def expected_dependencies(module, version):
    dependencies = [("org.jetbrains.kotlin", "kotlin-stdlib"), ("org.jetbrains.kotlinx", "kotlinx-coroutines-core")]
    if module == "lyricist":
        dependencies.append((GROUP, "lyricist-core"))
    elif module != "lyricist-core":
        raise RuntimeError("Unexpected Lyricist module")
    return {key: version if key[0] == GROUP else PINS[key[0] + ":" + key[1]] for key in dependencies}


def verify_source_archive(data, module):
    locked = SOURCE_LOCK[module]
    expected = {row["member"]: (row["size"], row["sha256"]) for row in locked["sourceMembers"]}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        sources = [item for item in entries if item.filename.endswith(".kt")]
        if len(sources) != len(expected) or {item.filename for item in sources} != set(expected):
            raise RuntimeError("Lyricist published source inventory differs: " + module)
        for item in sources:
            raw = archive.read(item)
            if (len(raw), digest(raw)) != expected[item.filename]:
                raise RuntimeError("Lyricist published source bytes differ: " + module)
        license_name = "META-INF/licenses/" + module + "/LYRICIST-LICENSE.md"
        licenses = [item for item in entries if item.filename == license_name]
        if len(licenses) != 1 or digest(archive.read(licenses[0])) != locked["license"]["sha256"]:
            raise RuntimeError("Lyricist published source license differs: " + module)
    return {"sourceCount": len(expected), "licenseSha256": locked["license"]["sha256"]}


def fetch_module(module, version, source, output):
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    base = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/"
    root_url = base + module + "-" + version + ".module"
    requests, identities = [], []
    expected = expected_dependencies(module, version)

    def provenance(url, artifact):
        location = public_url(url.removesuffix(".module") + "-provenance.json", url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        path = evidence / "provenance" / (artifact + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="provenance", artifact=artifact, path=str(path))
        write_json(path.with_suffix(".http.json"), row)
        value = verify_provenance(raw, version, source)
        if identities and row["sha256"] != identities[0]["sha256"]:
            raise RuntimeError("Lyricist root/leaf provenance bytes differ")
        identities.append({**row, "fingerprint": value["fingerprint"]})
        requests.append(row)
        return value

    def gmm(url, label):
        raw, row = read_http(url, PAGES)
        path = evidence / "remote-gmm" / (label + ".module")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="gmm", artifact=label, path=str(path))
        requests.append(row)
        value = json.loads(raw)
        if any(value["component"].get(k) != v for k, v in (("group", GROUP), ("module", module), ("version", version))):
            raise RuntimeError("Lyricist GMM owner differs: " + label)
        return value

    def pom(url, artifact, target):
        raw, row = read_http(url.removesuffix(".module") + ".pom", PAGES)
        path = evidence / "remote-pom" / (artifact + ".pom")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="pom", artifact=artifact, path=str(path))
        requests.append(row)
        xml = ET.fromstring(raw)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + k, namespaces=ns) != v for k, v in (("groupId", GROUP), ("artifactId", artifact), ("version", version))):
            raise RuntimeError("Lyricist POM identity differs: " + artifact)
        if (xml.findtext("m:licenses/m:license/m:name", namespaces=ns) != "MIT License" or
                xml.findtext("m:licenses/m:license/m:url", namespaces=ns) != "https://opensource.org/licenses/MIT" or
                xml.findtext("m:scm/m:url", namespaces=ns) != "https://github.com/adrielcafe/lyricist"):
            raise RuntimeError("Lyricist POM license or SCM differs: " + artifact)
        developers = [(d.findtext("m:id", namespaces=ns), d.findtext("m:name", namespaces=ns), d.findtext("m:url", namespaces=ns)) for d in xml.findall("m:developers/m:developer", ns)]
        if developers != [("adrielcafe", "Adriel Cafe", "https://github.com/adrielcafe/")]:
            raise RuntimeError("Lyricist POM author differs: " + artifact)
        found = {}
        suffix = "-ohosx64" if target == "ohos_x64" else "-ohosarm64" if target else ""
        for dep in xml.findall("m:dependencies/m:dependency", ns):
            group = dep.findtext("m:groupId", namespaces=ns)
            name = dep.findtext("m:artifactId", namespaces=ns)
            base_name = name.removesuffix(suffix) if suffix else name
            key = (group, base_name)
            if key in found or key not in expected or dep.findtext("m:version", namespaces=ns) != expected[key] or dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
                raise RuntimeError("Lyricist POM dependency or scope differs: " + artifact)
            if target and group == GROUP and name != base_name + suffix:
                raise RuntimeError("Lyricist POM project dependency target differs")
            found[key] = expected[key]
        if found != expected:
            raise RuntimeError("Lyricist POM dependency set differs: " + artifact)

    def select(value, url, target):
        selected = []
        for variant in value["variants"]:
            attrs = variant.get("attributes", {})
            api = (target is None and attrs.get("org.gradle.usage") == "kotlin-metadata" and attrs.get("org.jetbrains.kotlin.platform.type") == "common") or (target is not None and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.jetbrains.kotlin.native.target") == target)
            for dep in variant.get("dependencies", []):
                key = (dep["group"], dep["module"])
                if key not in expected or dep.get("version", {}).get("requires") != expected[key]:
                    raise RuntimeError("Lyricist GMM dependency differs: " + module)
            if api:
                found = {(dep["group"], dep["module"]): dep["version"]["requires"] for dep in variant.get("dependencies", [])}
                if found != expected:
                    raise RuntimeError("Lyricist GMM API dependency set differs: " + module)
                selected.extend(variant.get("files", []))
        if len(selected) != 1:
            raise RuntimeError("Lyricist public API artifact is absent or ambiguous: " + module)
        declaration = selected[0]
        location = public_url(urljoin(url, declaration["url"]), url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Lyricist public artifact bytes differ: " + module)
        entries, props = klib_payload(raw)
        if target is not None and (set(props.get("native_targets", "").split()) != {target} or not any("/ir/" in name and item["size"] > 0 for name, item in entries.items())):
            raise RuntimeError("Lyricist public Native target or IR differs: " + module)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(raw)
        row.update(role="metadata" if target is None else "native", expectedTarget=target, path=str(path))
        requests.append(row)
        return row, entries, raw

    def original(url, artifact, suffix, role, expected_identity=None):
        location = public_url(url.removesuffix(".module") + suffix, url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        if expected_identity is not None and (len(raw), digest(raw)) != (expected_identity["size"], expected_identity["sha256"]):
            raise RuntimeError("Lyricist original bytes differ: " + artifact + suffix)
        path = evidence / "public-originals" / (artifact + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role=role, artifact=artifact, path=str(path))
        requests.append(row)
        return raw

    def sources_and_license(url, artifact):
        source_bytes = original(url, artifact, "-sources.jar", "published-sources")
        verify_source_archive(source_bytes, module)
        original(url, artifact, "-license.txt", "license", SOURCE_LOCK[module]["license"])

    root = gmm(root_url, module)
    pom(root_url, module, None)
    source_provenance = provenance(root_url, module)
    sources_and_license(root_url, module)
    upstream = original(root_url, module, "-upstream-sources.jar", "upstream-sources", SOURCE_LOCK[module]["sources"])
    with zipfile.ZipFile(io.BytesIO(upstream)) as archive:
        expected_source = SOURCE_LOCK[module]["sourceMembers"][0]
        raw_source = archive.read(expected_source["member"])
        if (len(raw_source), digest(raw_source)) != (expected_source["size"], expected_source["sha256"]):
            raise RuntimeError("Lyricist upstream source member differs: " + module)
    for suffix, key in (("-upstream-pom.xml", "pom"), ("-upstream-module.json", "gmm"), ("-upstream-build.gradle.kts", "upstreamBuild")):
        original(root_url, module, suffix, "upstream-" + key, SOURCE_LOCK[module][key])
    metadata, payload, metadata_bytes = select(root, root_url, None)
    manifest_bytes, manifest = verify_metadata_manifest(metadata_bytes, source_provenance)
    manifest_path = evidence / "metadata-source-manifest" / (module + ".json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)
    manifest.update(path=str(manifest_path), artifactSha256=metadata["sha256"], artifactUrl=metadata["url"])
    write_json(manifest_path.with_suffix(".receipt.json"), manifest)
    native, owners = {}, []
    for target, suffix in (("ohos_x64", "-ohosx64"), ("ohos_arm64", "-ohosarm64")):
        leaf_module = module + suffix
        leaf_url = PAGES + GROUP.replace(".", "/") + "/" + leaf_module + "/" + version + "/" + leaf_module + "-" + version + ".module"
        links = [variant["available-at"] for variant in root["variants"] if variant.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and variant.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and "available-at" in variant]
        if len(links) != 1 or any(links[0].get(k) != v for k, v in (("group", GROUP), ("module", leaf_module), ("version", version))) or urljoin(root_url, links[0]["url"]) != leaf_url:
            raise RuntimeError("Lyricist root/leaf publication link differs: " + module)
        leaf = gmm(leaf_url, leaf_module)
        pom(leaf_url, leaf_module, target)
        provenance(leaf_url, leaf_module)
        sources_and_license(leaf_url, leaf_module)
        if urljoin(leaf_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Lyricist leaf owner differs: " + module)
        artifact, _, _ = select(leaf, leaf_url, target)
        native[target] = [artifact]
        owners.append({"target": target, "leafUrl": leaf_url, "ownerUrl": root_url})
    return {"module": module, "rootUrl": root_url, "fingerprint": source_provenance["fingerprint"],
            "provenanceSha256": identities[0]["sha256"], "provenanceArtifacts": identities,
            "metadataArtifacts": [metadata], "metadataPayload": payload, "metadataSourceManifest": manifest,
            "nativeArtifacts": native, "owners": owners, "requests": requests}


def canonical_sha(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def verify_wheel_provenance(data, version, source):
    value = json.loads(data)
    expected = {"group": WHEEL_GROUP, "module": WHEEL_MODULE, "version": version, "sourceCommit": source, "toolingCommit": TOOL_REVISION}
    if any(value.get(key) != item for key, item in expected.items()) or not re.fullmatch(r"[0-9a-f]{64}", value.get("fingerprint", "")):
        raise RuntimeError("Wheel provenance identity differs")
    if value.get("upstream") != {"repository": "https://github.com/darkokoa/compose-datetime-wheel-picker", "version": "1.4.0", "commit": "56a15ca7c47fd6b23d155ba73027d29d9693664d", "license": "Apache-2.0"}:
        raise RuntimeError("Wheel upstream identity differs")
    if (value.get("sourceMembers") != WHEEL_LOCK["sources"] or value.get("generatedSource") != WHEEL_LOCK["generatedSource"] or
            value.get("upstreamFiles") != WHEEL_LOCK["upstreamFiles"] or value.get("licenseDecision") != WHEEL_LOCK["privateLicense"] or
            value.get("lyricistInput") != LYRICIST_INPUT or canonical_sha(value.get("publicApi")) != WHEEL_LOCK["publicApiSha256"]):
        raise RuntimeError("Wheel source origins, API or Lyricist lock differ")
    return value


def verify_wheel_metadata_manifest(data, provenance):
    entry = "META-INF/upstream/source-manifest.json"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        matches = [item for item in archive.infolist() if item.filename == entry and not item.is_dir()]
        if len(matches) != 1:
            raise RuntimeError("Wheel metadata source manifest missing or duplicated")
        raw = archive.read(matches[0])
    value = json.loads(raw)
    expected = {x["member"]: (x["size"], x["sha256"], x["origin"]) for x in WHEEL_LOCK["sources"]}
    rows = value.get("members", [])
    actual = {x.get("member"): (x.get("size"), x.get("sha256"), x.get("origin")) for x in rows}
    if (value.get("fingerprint") != provenance["fingerprint"] or len(rows) != 61 or actual != expected or
            value.get("sourceCount") != 61 or value.get("gitSourceCount") != 60 or value.get("jarGeneratedSourceCount") != 1 or
            value.get("localeCount") != 33 or value.get("sourceSetSha256") != WHEEL_LOCK["sourceSetSha256"] or
            canonical_sha(value.get("publicApi")) != WHEEL_LOCK["publicApiSha256"]):
        raise RuntimeError("Wheel metadata source manifest differs")
    return raw, {"entry": entry, "size": len(raw), "sha256": digest(raw), "fingerprint": value["fingerprint"],
                 "sourceCount": 61, "gitSourceCount": 60, "jarGeneratedSourceCount": 1, "localeCount": 33}


def verify_wheel_source_archive(data, module):
    expected = {row["member"]: (row["size"], row["sha256"]) for row in WHEEL_LOCK["sources"]}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        sources = [item for item in entries if item.filename.endswith(".kt")]
        if len(sources) != 61 or {item.filename for item in sources} != set(expected):
            raise RuntimeError("Wheel published source inventory differs")
        locales = 0
        for item in sources:
            raw = archive.read(item)
            if (len(raw), digest(raw)) != expected[item.filename]:
                raise RuntimeError("Wheel published source bytes differ: " + item.filename)
            locales += b"@LyricistStrings(" in raw
        licenses = [item for item in entries if item.filename == "META-INF/licenses/datetime-wheel-picker/LICENSE"]
        if len(licenses) != 1 or digest(archive.read(licenses[0])) != WHEEL_LOCK["license"]["sha256"] or locales != 33:
            raise RuntimeError("Wheel source license or locale count differs")
    return {"sourceCount": 61, "gitSourceCount": 60, "jarGeneratedSourceCount": 1, "localeCount": 33}


def expected_wheel_dependencies(module, version):
    names = ["org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains.compose.runtime:runtime", "org.jetbrains.compose.material3:material3",
             "org.jetbrains.kotlinx:kotlinx-datetime", "io.github.qsxs.cpf.lyricist:lyricist"]
    return {tuple(name.split(":")): PINS[name] for name in names}


def fetch_wheel(version, source, output):
    module = WHEEL_MODULE
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    base = PAGES + WHEEL_GROUP.replace(".", "/") + "/" + module + "/" + version + "/"
    root_url = base + module + "-" + version + ".module"
    requests, identities = [], []
    expected = expected_wheel_dependencies(module, version)

    def provenance(url, artifact):
        location = public_url(url.removesuffix(".module") + "-provenance.json", url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        path = evidence / "provenance" / (artifact + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="provenance", artifact=artifact, path=str(path))
        write_json(path.with_suffix(".http.json"), row)
        value = verify_wheel_provenance(raw, version, source)
        if identities and row["sha256"] != identities[0]["sha256"]:
            raise RuntimeError("Wheel root/leaf provenance bytes differ")
        identities.append({**row, "fingerprint": value["fingerprint"]})
        requests.append(row)
        return value

    def gmm(url, label):
        raw, row = read_http(url, PAGES)
        path = evidence / "remote-gmm" / (label + ".module")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="gmm", artifact=label, path=str(path))
        requests.append(row)
        value = json.loads(raw)
        if any(value["component"].get(k) != v for k, v in (("group", WHEEL_GROUP), ("module", module), ("version", version))):
            raise RuntimeError("Wheel GMM owner differs: " + label)
        return value

    def pom(url, artifact, target):
        raw, row = read_http(url.removesuffix(".module") + ".pom", PAGES)
        path = evidence / "remote-pom" / (artifact + ".pom")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role="pom", artifact=artifact, path=str(path))
        requests.append(row)
        xml = ET.fromstring(raw)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + k, namespaces=ns) != v for k, v in (("groupId", WHEEL_GROUP), ("artifactId", artifact), ("version", version))):
            raise RuntimeError("Wheel POM identity differs: " + artifact)
        if (xml.findtext("m:licenses/m:license/m:name", namespaces=ns) != "The Apache Software License, Version 2.0" or
                xml.findtext("m:licenses/m:license/m:url", namespaces=ns) != "http://www.apache.org/licenses/LICENSE-2.0.txt" or
                xml.findtext("m:scm/m:url", namespaces=ns) != "https://github.com/darkokoa/compose-datetime-wheel-picker"):
            raise RuntimeError("Wheel POM license or SCM differs: " + artifact)
        developers = [(d.findtext("m:id", namespaces=ns), d.findtext("m:name", namespaces=ns), d.findtext("m:url", namespaces=ns)) for d in xml.findall("m:developers/m:developer", ns)]
        if developers != [("darkokoa", "darkokoa", "https://github.com/darkokoa/")]:
            raise RuntimeError("Wheel POM author differs: " + artifact)
        found = {}
        suffix = "-ohosx64" if target == "ohos_x64" else "-ohosarm64" if target else ""
        for dep in xml.findall("m:dependencies/m:dependency", ns):
            group = dep.findtext("m:groupId", namespaces=ns)
            name = dep.findtext("m:artifactId", namespaces=ns)
            base_name = name.removesuffix(suffix) if suffix else name
            key = (group, base_name)
            if key in found or key not in expected or dep.findtext("m:version", namespaces=ns) != expected[key] or dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
                raise RuntimeError("Wheel POM dependency or scope differs: " + artifact)
            if target and group != "org.jetbrains.kotlin" and name != base_name + suffix:
                raise RuntimeError("Wheel POM project dependency target differs")
            found[key] = expected[key]
        if found != expected:
            raise RuntimeError("Wheel POM dependency set differs: " + artifact)

    def select(value, url, target):
        selected = []
        for variant in value["variants"]:
            attrs = variant.get("attributes", {})
            api = (target is None and attrs.get("org.gradle.usage") == "kotlin-metadata" and attrs.get("org.jetbrains.kotlin.platform.type") == "common") or (target is not None and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.jetbrains.kotlin.native.target") == target)
            for dep in variant.get("dependencies", []):
                key = (dep["group"], dep["module"])
                if key not in expected or dep.get("version", {}).get("requires") != expected[key]:
                    raise RuntimeError("Wheel GMM dependency differs: " + module)
            if api:
                found = {(dep["group"], dep["module"]): dep["version"]["requires"] for dep in variant.get("dependencies", [])}
                if found != expected:
                    raise RuntimeError("Wheel GMM API dependency set differs: " + module)
                selected.extend(variant.get("files", []))
        if len(selected) != 1:
            raise RuntimeError("Wheel public API artifact is absent or ambiguous: " + module)
        declaration = selected[0]
        location = public_url(urljoin(url, declaration["url"]), url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Wheel public artifact bytes differ: " + module)
        entries, props = klib_payload(raw)
        if target is not None and (set(props.get("native_targets", "").split()) != {target} or not any("/ir/" in name and item["size"] > 0 for name, item in entries.items())):
            raise RuntimeError("Wheel public Native target or IR differs: " + module)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(raw)
        row.update(role="metadata" if target is None else "native", expectedTarget=target, path=str(path))
        requests.append(row)
        return row, entries, raw

    def original(url, artifact, suffix, role, expected_identity=None):
        location = public_url(url.removesuffix(".module") + suffix, url.rsplit("/", 1)[0] + "/")
        raw, row = read_http(location, PAGES)
        if expected_identity is not None and (len(raw), digest(raw)) != (expected_identity["size"], expected_identity["sha256"]):
            raise RuntimeError("Wheel original bytes differ: " + artifact + suffix)
        path = evidence / "public-originals" / (artifact + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        row.update(role=role, artifact=artifact, path=str(path))
        requests.append(row)
        return raw

    def sources_and_license(url, artifact, descriptor):
        source_bytes = original(url, artifact, "-sources.jar", "published-sources")
        verify_wheel_source_archive(source_bytes, module)
        expected_url = url.removesuffix(".module") + "-sources.jar"
        declarations = [entry for variant in descriptor["variants"] if variant.get("attributes", {}).get("org.gradle.docstype") == "sources"
                        for entry in variant.get("files", []) if urljoin(url, entry["url"]) == expected_url]
        if len(declarations) != 1 or (declarations[0]["size"], declarations[0]["sha256"]) != (len(source_bytes), digest(source_bytes)):
            raise RuntimeError("Wheel GMM sources artifact differs: " + artifact)
        original(url, artifact, "-license.txt", "license", WHEEL_LOCK["license"])

    root = gmm(root_url, module)
    pom(root_url, module, None)
    source_provenance = provenance(root_url, module)
    sources_and_license(root_url, module, root)
    upstream = original(root_url, module, "-upstream-sources.jar", "upstream-sources", WHEEL_LOCK["sourcesJar"])
    with zipfile.ZipFile(io.BytesIO(upstream)) as archive:
        expected_sources = {item["member"]: (item["size"], item["sha256"]) for item in WHEEL_LOCK["sources"]}
        entries = [item for item in archive.infolist() if not item.is_dir() and item.filename.endswith(".kt")]
        if len(archive.infolist()) != 70 or len(entries) != 61 or {item.filename for item in entries} != set(expected_sources):
            raise RuntimeError("Wheel upstream sources JAR inventory differs")
        locales = 0
        for item in entries:
            raw_source = archive.read(item)
            if (len(raw_source), digest(raw_source)) != expected_sources[item.filename]:
                raise RuntimeError("Wheel upstream source member differs: " + item.filename)
            locales += b"@LyricistStrings(" in raw_source
        if locales != 33:
            raise RuntimeError("Wheel upstream locale inventory differs")
    for suffix, key in (("-upstream-pom.xml", "pom"), ("-upstream-module.json", "gmm"), ("-upstream-build.gradle.kts", "upstreamBuild")):
        original(root_url, module, suffix, "upstream-" + key, WHEEL_LOCK[key])
    metadata, payload, metadata_bytes = select(root, root_url, None)
    manifest_bytes, manifest = verify_wheel_metadata_manifest(metadata_bytes, source_provenance)
    manifest_path = evidence / "metadata-source-manifest" / (module + ".json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)
    manifest.update(path=str(manifest_path), artifactSha256=metadata["sha256"], artifactUrl=metadata["url"])
    write_json(manifest_path.with_suffix(".receipt.json"), manifest)
    native, owners = {}, []
    for target, suffix in (("ohos_x64", "-ohosx64"), ("ohos_arm64", "-ohosarm64")):
        leaf_module = module + suffix
        leaf_url = PAGES + WHEEL_GROUP.replace(".", "/") + "/" + leaf_module + "/" + version + "/" + leaf_module + "-" + version + ".module"
        links = [variant["available-at"] for variant in root["variants"] if variant.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and variant.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and "available-at" in variant]
        if len(links) != 1 or any(links[0].get(k) != v for k, v in (("group", WHEEL_GROUP), ("module", leaf_module), ("version", version))) or urljoin(root_url, links[0]["url"]) != leaf_url:
            raise RuntimeError("Wheel root/leaf publication link differs: " + module)
        leaf = gmm(leaf_url, leaf_module)
        pom(leaf_url, leaf_module, target)
        provenance(leaf_url, leaf_module)
        sources_and_license(leaf_url, leaf_module, leaf)
        if urljoin(leaf_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Wheel leaf owner differs: " + module)
        artifact, _, _ = select(leaf, leaf_url, target)
        native[target] = [artifact]
        owners.append({"target": target, "leafUrl": leaf_url, "ownerUrl": root_url})
    return {"module": module, "rootUrl": root_url, "fingerprint": source_provenance["fingerprint"],
            "provenanceSha256": identities[0]["sha256"], "provenanceArtifacts": identities,
            "metadataArtifacts": [metadata], "metadataPayload": payload, "metadataSourceManifest": manifest,
            "nativeArtifacts": native, "owners": owners, "requests": requests}


def main():
    output = Path(os.environ["WHEEL_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": WHEEL_GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN", "androidRegression": "NOT_RUN", "iosRegression": "NOT_RUN", "gradle8Consumer": "NOT_RUN"}
    code = 1
    try:
        version, source, workflow = os.environ["WHEEL_VERSION"], os.environ["WHEEL_SOURCE_SHA"], os.environ["CI_TOOLING_SHA"]
        if source != WRAPPER_COMMIT or not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"1\.4\.0-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete Wheel version must match its full source SHA")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, folder in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / folder
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        actual = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env).stdout.strip()
        if actual != workflow:
            raise RuntimeError("Consumer workflow checkout differs")
        state.update(version=version, sourceCommit=source, workflowToolingCommit=workflow, runtimeToolingCommit=TOOL_REVISION,
                     runId=os.environ.get("CI_RUN_ID"), runAttempt=os.environ.get("CI_RUN_ATTEMPT"))
        state["stage"] = "AnonymousHTTP"
        wheel = fetch_wheel(version, source, output)
        lyricist = {module: fetch_module(module, LYRICIST_VERSION, LYRICIST_COMMIT, output) for module in LYRICIST_MODULES}
        fingerprints = {value["fingerprint"] for value in lyricist.values()}
        provenance_hashes = {value["provenanceSha256"] for value in lyricist.values()}
        if fingerprints != {LYRICIST_INPUT["fingerprint"]} or len(provenance_hashes) != 1:
            raise RuntimeError("Published Lyricist module provenance differs")
        for module, item in lyricist.items():
            locked = LYRICIST_INPUT["modules"][module]
            metadata = item["metadataArtifacts"][0]
            if ((metadata["size"], metadata["sha256"]) != (locked["metadataArtifact"]["size"], locked["metadataArtifact"]["sha256"]) or
                    item["metadataPayload"] != locked["metadataPayload"] or item["provenanceSha256"] != locked["provenanceSha256"]):
                raise RuntimeError("Published Lyricist metadata identity differs: " + module)
            for target, rows in item["nativeArtifacts"].items():
                expected = locked["nativeArtifacts"][target]
                if len(rows) != 1 or (rows[0]["size"], rows[0]["sha256"]) != (expected["size"], expected["sha256"]):
                    raise RuntimeError("Published Lyricist Native identity differs: " + module + ":" + target)
        modules = {WHEEL_MODULE: wheel, **lyricist}
        public = {"status": "ANONYMOUS_PUBLIC_GRAPH_VERIFIED", "version": version, "sourceCommit": source,
                  "fingerprint": wheel["fingerprint"], "modules": modules, "librarySourcesUsedAsCompilationInput": False,
                  "consumerDirectDependencies": [WHEEL_GROUP + ":" + WHEEL_MODULE + ":" + version],
                  "lyricistVersion": LYRICIST_VERSION, "wheelSourceOrigins": "60_GIT_BLOBS_PLUS_1_OFFICIAL_JAR_GENERATED"}
        write_json(evidence / "public-manifest.json", public)
        state["stage"] = "PinnedBuildTools"
        tools, wrapper = fetch_tools(output, "gradle9")
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running Wheel consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        probe_name = "src/commonMain/kotlin/WheelConsumer.kt"
        for name, contents in (("settings.gradle.kts", SETTINGS), ("build.gradle.kts", BUILD), (probe_name, PROBE)):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
        shutil.copyfile(wrapper / "gradle.properties", project / "gradle.properties")
        probe = project / probe_name
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "public-manifest.json"), "-PwheelVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Wheel consumer tasks absent from actual discovery")
                write_json(evidence / "task-discovery.json", {"required": sorted(REQUIRED), "stdout": record(logs / "Tasks.stdout.log")})
        state["stage"] = "VerifyPublicConsumption"
        verify_records(output, native, env, "gradle9")
        state["status"] = "PUBLIC_CONSUMER_COMPILED"
        code = 0
    except Exception as error:
        state.update(status="FAILED", error=str(error))
    finally:
        for stage in ("BootstrapNative", *STAGES):
            for stream in ("stdout", "stderr"):
                path = output / "logs" / (stage + "." + stream + ".log")
                content = tail(path)
                if content:
                    (evidence / (stage + "." + stream + "-tail.log")).write_text(content, encoding="utf-8")
                    if state["status"] == "FAILED" and state.get("stage") == stage:
                        print(content, file=sys.stderr)
                if stream == "stderr" and state["status"] == "FAILED" and state.get("stage") == stage:
                    try:
                        prefix = read_log_head(path)
                        if prefix:
                            (evidence / (stage + ".stderr-head.log")).write_text(prefix, encoding="utf-8")
                    except OSError as error:
                        state.setdefault("logCaptureWarnings", []).append(
                            {"stage": stage, "stream": stream, "errorType": type(error).__name__}
                        )
        for path in evidence.rglob("*"):
            if path.is_file() and path.stat().st_size > 8 * 1024 * 1024:
                if code == 0:
                    state.update(status="FAILED", error="Consumer structured evidence exceeds 8 MiB")
                else:
                    state["evidenceError"] = "Consumer structured evidence exceeds 8 MiB"
                code = 1
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
