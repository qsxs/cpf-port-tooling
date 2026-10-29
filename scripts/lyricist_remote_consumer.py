"""公开 Pages Lyricist 双模块消费者；仅下载公开制品和锁定构建工具。"""
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
MODULES = ('lyricist', 'lyricist-core')
TOOL_REVISION = 'd0cff88fd1ea2e4f08bb4409f1c802cca0c7f285'
TOOL_DIR = 'toolchains/kotlin-native/2.4.20-0.1.0-08'
WRAPPER_COMMIT = 'fad3d9091c75927320da3511350202e681269b2a'

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
 'sourceRepository': 'qsxs/lyricist',
 'sourceCommit': 'fad3d9091c75927320da3511350202e681269b2a',
 'files': [{'path': 'gradlew',
            'size': 363,
            'sha256': '0e96228f9589965a5e171190f69f6e820f128bdae180f7e2acc6e4d65f788ed5',
            'url': 'https://raw.githubusercontent.com/qsxs/lyricist/fad3d9091c75927320da3511350202e681269b2a/ohos/gradlew'},
           {'path': 'gradle/wrapper/gradle-wrapper.jar',
            'size': 43764,
            'sha256': '7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172',
            'url': 'https://raw.githubusercontent.com/qsxs/lyricist/fad3d9091c75927320da3511350202e681269b2a/ohos/gradle/wrapper/gradle-wrapper.jar'},
           {'path': 'gradle/wrapper/gradle-wrapper.properties',
            'size': 339,
            'sha256': '93b4f2c5ddcfc9e6f630fc7e004b31b389695cd0228be6da42e196e5d4af7acb',
            'url': 'https://raw.githubusercontent.com/qsxs/lyricist/fad3d9091c75927320da3511350202e681269b2a/ohos/gradle/wrapper/gradle-wrapper.properties'},
           {'path': 'gradle.properties',
            'size': 314,
            'sha256': '993600cfde45bf43788143c6eb2ebab1949c733ef38cc4abc3437c6e2112ed40',
            'url': 'https://raw.githubusercontent.com/qsxs/lyricist/fad3d9091c75927320da3511350202e681269b2a/ohos/gradle.properties'}]}

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

SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.lyricist") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.lyricist") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.lyricist") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.lyricist") } }
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
            forRepository { maven { name = "LyricistPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.lyricist") }
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
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.lyricist") } }
    }
}
rootProject.name = "lyricist-pages-consumer"
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
val lyricistVersion = providers.gradleProperty("lyricistVersion").get()
val probe = file("src/commonMain/kotlin/LyricistConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val publicVersions = mapOf(lyricistGroup to lyricistVersion)
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
            dependencies {
                implementation("$lyricistGroup:lyricist:$lyricistVersion")
                implementation("org.jetbrains.compose.runtime:runtime:1.12.0-0.1.0-11")
                implementation("org.jetbrains.compose.ui:ui:1.12.0-0.1.0-11")
            }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
fun directDependencies(): List<String> {
    val actual = configurations.getByName("commonMainImplementation").dependencies.map { "${it.group}:${it.name}:${it.version}" }.sorted()
    val required = setOf("$lyricistGroup:lyricist:$lyricistVersion", "org.jetbrains.compose.runtime:runtime:1.12.0-0.1.0-11", "org.jetbrains.compose.ui:ui:1.12.0-0.1.0-11")
    check(actual.containsAll(required)) { "Consumer environment dependencies differ" }
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
            check(requested.group != "cafe.adriel.lyricist") { "Upstream Lyricist cannot satisfy OHOS public consumption" }
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
val publicModules = listOf("lyricist", "lyricist-core").associateWith { lyricistGroup }
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
    check(graph.any { it.getValue("requested") == "$lyricistGroup:lyricist:$lyricistVersion" })
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
        check(gradle.gradleVersion == "9.5.0")
        evidence("consumer-resolution.json", mapOf("lyricistVersion" to lyricistVersion, "consumerDirectDependencies" to directDependencies(), "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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
import cafe.adriel.lyricist.LanguageTag
import cafe.adriel.lyricist.LyricistStrings
import cafe.adriel.lyricist.rememberStrings

data class ProbeStrings(val greeting: String)

@LyricistStrings(languageTag = "en", default = true)
val english = ProbeStrings("Hello")

@Composable
fun lyricistProbe(currentLanguageTag: LanguageTag): String {
    val lyricist = rememberStrings(
        translations = mapOf("en" to english),
        defaultLanguageTag = "en",
        currentLanguageTag = currentLanguageTag,
    )
    val selected: LanguageTag = lyricist.languageTag
    return selected + ":" + lyricist.strings.greeting
}
'''

STAGES = ('Tasks', 'Resolve', 'Metadata', 'NativeX64', 'NativeArm64')
TASKS = {'Tasks': ['tasks', '--all'],
 'Resolve': ['resolveConsumer'],
 'Metadata': ['recordConsumerMetadata'],
 'NativeX64': ['recordConsumerX64'],
 'NativeArm64': ['recordConsumerArm64']}
REQUIRED = {'resolveConsumer', 'compileKotlinOhosX64', 'recordConsumerX64', 'recordConsumerMetadata', 'compileKotlinOhosArm64', 'verifyConsumerTools', 'compileCommonMainKotlinMetadata', 'recordConsumerArm64'}


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
    prefix = "https://raw.githubusercontent.com/qsxs/lyricist/" + WRAPPER_COMMIT + "/ohos/"
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
    if any(value.get(key) != item for key, item in expected.items()) or value.get("modules") != list(MODULES):
        raise RuntimeError("Lyricist provenance identity differs")
    if value.get("upstream") != {"repository": "https://github.com/adrielcafe/lyricist", "version": "1.8.0", "commit": "89b8b6821b288164f71e5196f33d8f706c758fae", "license": "MIT"}:
        raise RuntimeError("Lyricist upstream identity differs")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("fingerprint", "")):
        raise RuntimeError("Lyricist provenance fingerprint differs")
    rows = value.get("sources", [])
    if len(rows) != 2 or {row.get("module") for row in rows} != set(MODULES):
        raise RuntimeError("Lyricist source inventory differs")
    for module in MODULES:
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
    expected = {(module, row["member"]): (row["size"], row["sha256"]) for module in MODULES for row in SOURCE_LOCK[module]["sourceMembers"]}
    rows = manifest.get("members", [])
    actual = {(row.get("module"), row.get("member")): (row.get("size"), row.get("sha256")) for row in rows}
    if (manifest.get("fingerprint") != provenance["fingerprint"] or manifest.get("sourceCount") != 2 or len(rows) != 2 or actual != expected or
            manifest.get("moduleSourceCounts") != {module: 1 for module in MODULES} or
            manifest.get("sourceSetSha256") != {module: SOURCE_LOCK[module]["sourceSetSha256"] for module in MODULES} or
            manifest.get("publicApi") != {module: SOURCE_LOCK[module]["publicApi"] for module in MODULES}):
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


def main():
    output = Path(os.environ["LYRICIST_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN", "androidRegression": "NOT_RUN", "iosRegression": "NOT_RUN", "gradle8Consumer": "NOT_RUN"}
    code = 1
    try:
        version, source, workflow = os.environ["LYRICIST_VERSION"], os.environ["LYRICIST_SOURCE_SHA"], os.environ["CI_TOOLING_SHA"]
        if source != WRAPPER_COMMIT or not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"1\.8\.0-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete Lyricist version must match its full source SHA")
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
        modules = {module: fetch_module(module, version, source, output) for module in MODULES}
        fingerprints = {value["fingerprint"] for value in modules.values()}
        provenance_hashes = {value["provenanceSha256"] for value in modules.values()}
        if len(fingerprints) != 1 or len(provenance_hashes) != 1:
            raise RuntimeError("Lyricist module provenance differs")
        public = {"status": "ANONYMOUS_PUBLIC_GRAPH_VERIFIED", "version": version, "sourceCommit": source,
                  "fingerprint": fingerprints.pop(), "modules": modules, "librarySourcesUsedAsCompilationInput": False,
                  "consumerEnvironmentDependencies": ["org.jetbrains.compose.runtime:runtime:1.12.0-0.1.0-11", "org.jetbrains.compose.ui:ui:1.12.0-0.1.0-11"],
                  "libraryComposeScope": "COMPILE_ONLY_NOT_PUBLISHED"}
        write_json(evidence / "public-manifest.json", public)
        state["stage"] = "PinnedBuildTools"
        tools, wrapper = fetch_tools(output, "gradle9")
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running Lyricist consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        probe_name = "src/commonMain/kotlin/LyricistConsumer.kt"
        for name, contents in (("settings.gradle.kts", SETTINGS), ("build.gradle.kts", BUILD), (probe_name, PROBE)):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
        shutil.copyfile(wrapper / "gradle.properties", project / "gradle.properties")
        probe = project / probe_name
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "public-manifest.json"), "-PlyricistVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Lyricist consumer tasks absent from actual discovery")
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
