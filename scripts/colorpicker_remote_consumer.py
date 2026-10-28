"""匿名 Pages ColorPicker 消费者；只取公开制品与固定工具，不取库源码。"""
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

# 复用 Grid 已验的匿名 HTTP、Klib payload 和有界日志读取；不修改 Grid 行为。
from grid_remote_consumer import digest, klib_payload, public_url, read_http, record, tail, write_json

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.colorpicker"
MODULE = "colorpicker-compose"
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
GRID_COMMIT = "ed3472803fdb637d601391f62f43aba1bfea551f"

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
 'sourceRepository': 'qsxs/gridlayout-compose',
 'sourceCommit': 'ed3472803fdb637d601391f62f43aba1bfea551f',
 'files': [{'path': 'gradlew',
            'size': 363,
            'sha256': '0e96228f9589965a5e171190f69f6e820f128bdae180f7e2acc6e4d65f788ed5',
            'url': 'https://raw.githubusercontent.com/qsxs/gridlayout-compose/ed3472803fdb637d601391f62f43aba1bfea551f/ohos/gradlew'},
           {'path': 'gradle/wrapper/gradle-wrapper.jar',
            'size': 43764,
            'sha256': '7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172',
            'url': 'https://raw.githubusercontent.com/qsxs/gridlayout-compose/ed3472803fdb637d601391f62f43aba1bfea551f/ohos/gradle/wrapper/gradle-wrapper.jar'},
           {'path': 'gradle/wrapper/gradle-wrapper.properties',
            'size': 339,
            'sha256': '93b4f2c5ddcfc9e6f630fc7e004b31b389695cd0228be6da42e196e5d4af7acb',
            'url': 'https://raw.githubusercontent.com/qsxs/gridlayout-compose/ed3472803fdb637d601391f62f43aba1bfea551f/ohos/gradle/wrapper/gradle-wrapper.properties'},
           {'path': 'gradle.properties',
            'size': 314,
            'sha256': '993600cfde45bf43788143c6eb2ebab1949c733ef38cc4abc3437c6e2112ed40',
            'url': 'https://raw.githubusercontent.com/qsxs/gridlayout-compose/ed3472803fdb637d601391f62f43aba1bfea551f/ohos/gradle.properties'}]}
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
 'org.jetbrains.compose.foundation:foundation': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-layout-ohosx64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-ohosarm64': '1.12.0-0.1.0-11',
 'org.jetbrains.compose.foundation:foundation-ohosx64': '1.12.0-0.1.0-11',
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
 'org.jetbrains.skiko:skiko': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64-api': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosarm64-fusionrenderer': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64-api': '0.150.1-0.1.0-10',
 'org.jetbrains.skiko:skiko-ohosx64-fusionrenderer': '0.150.1-0.1.0-10',
 'org.jetbrains.kotlinx:kotlinx-datetime': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-datetime-ohosx64': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core-ohosx64': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-datetime-ohosarm64': '0.8.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-core-ohosarm64': '1.11.0-0.1.0-07',
 'org.jetbrains.kotlinx:kotlinx-serialization-bom': '1.11.0-0.1.0-07'}
METADATA_PINS = {'androidx.annotation:annotation': '1.9.1',
 'androidx.arch.core:core-common': '2.2.0',
 'androidx.collection:collection': '1.5.0',
 'androidx.compose.runtime:runtime': '1.12.0',
 'androidx.compose.runtime:runtime-annotation': '1.12.0',
 'androidx.compose.runtime:runtime-saveable': '1.12.0',
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

SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.colorpicker") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.colorpicker") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.colorpicker") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.colorpicker") } }
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.compose") version "2.4.20-0.1.0-08"
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
            forRepository { maven { name = "ColorPickerPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.colorpicker") }
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
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.colorpicker") } }
    }
}
rootProject.name = "colorpicker-pages-consumer"
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
val colorpickerGroup = "io.github.qsxs.cpf.colorpicker"
val colorpickerVersion = providers.gradleProperty("colorpickerVersion").get()
val probe = file("src/commonMain/kotlin/ColorPickerConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val metadataTools = readMap(tools.resolve("metadata-toolchain.json"))
val commonizer = readMap(tools.resolve("commonizer-toolchain.json"))
val commonizerPins = asMap(metadataTools.getValue("launcherPins")) + asMap(commonizer.getValue("pins"))
val commonizerArtifacts = asMap(metadataTools.getValue("launcherArtifacts")) + asMap(commonizer.getValue("artifacts"))
val host = readMap(tools.resolve("native-compiler-toolchain.json"))
val pins = readMap(tools.resolve("dependency-pins.json"))
val metadataPins = readMap(tools.resolve("metadata-pins.json"))
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
            dependencies { implementation("$colorpickerGroup:colorpicker-compose:$colorpickerVersion") }
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
        if (requested.group == colorpickerGroup) {
            check(requested.version == colorpickerVersion) { "ColorPicker version escaped explicit Pages coordinate" }
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
    val artifacts = configuration.incoming.artifacts.artifacts.map { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier)
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        if (id.group == colorpickerGroup) {
            count++
            check(id.version == colorpickerVersion)
            if (target == null) check(id.module == "colorpicker-compose" && attrs["org.jetbrains.kotlin.platform.type"] == "common" && attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf("colorpicker-compose", if (target == "ohos_x64") "colorpicker-compose-ohosx64" else "colorpicker-compose-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            check(expected.any { it["sha256"] == sha(artifact.file) && (it.getValue("size") as Number).toLong() == artifact.file.length() }) { "ColorPicker artifact differs from anonymous HTTP: $id" }
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
    check(count == expected.size && count > 0) { "ColorPicker selected artifact set differs: $name" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$colorpickerGroup:colorpicker-compose:$colorpickerVersion" })
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
    check(matches.size == 1) { "ColorPicker transformed metadata cannot be traced to the Pages root" }
    return mapOf("rootHttpArtifacts" to http.getValue("metadataArtifacts"), "compilerLibrary" to matches.single().absolutePath,
        "payload" to expected, "payloadFileCount" to expected.size)
}
fun nativeTrace(compiler: KotlinNativeCompile, target: String): Map<String, Any> {
    val declared = (asMap(http.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
    check(declared.size == 1)
    val expected = payload(file(declared.single().getValue("path")!!))
    check(expected.isNotEmpty())
    val matches = compiler.libraries.files.filter { payload(it) == expected }
    check(matches.size == 1) { "Native compiler library cannot be traced to the Pages leaf: $target" }
    return mapOf("target" to target, "httpArtifact" to declared.single(), "compilerLibrary" to matches.single().absolutePath)
}
val checkTools = tasks.register("verifyConsumerTools") {
    outputs.upToDateWhen { false }
    doLast { evidence("consumer-tools.json", toolRecords()) }
}
tasks.withType<KotlinNativeCompile>().configureEach { if (name in compileTasks) dependsOn(checkTools) }
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0")
        evidence("consumer-resolution.json", mapOf("colorpickerVersion" to colorpickerVersion, "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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
            check(plugins.size == 1 && plugins.single().length() == 870498L &&
                sha(plugins.single()) == "4ffe7f38089fa4acdda5d67fa3a858b9fc2fe7ed1f2e58bedbf8d3447c15df39") {
                "Consumer Compose compiler plugin differs"
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

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.github.skydoves.colorpicker.compose.BrightnessSlider
import com.github.skydoves.colorpicker.compose.ColorEnvelope
import com.github.skydoves.colorpicker.compose.HsvColorPicker
import com.github.skydoves.colorpicker.compose.rememberColorPickerController

@Composable
fun ColorPickerProbe(initialColor: Color, color: Color, onColorChanged: (Color) -> Unit) {
    val controller = rememberColorPickerController()
    HsvColorPicker(
        modifier = Modifier,
        controller = controller,
        initialColor = initialColor,
        onColorChanged = { envelope: ColorEnvelope -> onColorChanged(envelope.color) },
    )
    BrightnessSlider(modifier = Modifier, controller = controller, borderRadius = 24.dp)
    Box(modifier = Modifier.clickable { controller.selectByColor(color, true) }) {}
}
'''

STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}


def source_set_sha256(rows):
    if not isinstance(rows, list) or len(rows) != 21:
        raise RuntimeError("ColorPicker source inventory differs")
    try:
        members = [{key: row[key] for key in ("member", "size", "sha256")} for row in rows]
        members.sort(key=lambda row: row["member"])
        if len({row["member"] for row in members}) != 21:
            raise RuntimeError("ColorPicker source inventory has duplicates")
        return digest(json.dumps(members, sort_keys=True, separators=(",", ":")).encode())
    except (KeyError, TypeError) as error:
        raise RuntimeError("ColorPicker source inventory is malformed") from error


def verify_provenance(data, version, source_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not re.fullmatch(
            r"1\.2\.0-cpf11-preview-" + re.escape(source_sha[:12]) + r"-[1-9][0-9]*-[1-9][0-9]*", version):
        raise RuntimeError("ColorPicker source SHA or preview version differs")
    value = json.loads(data)
    expected = {"sourceCommit": source_sha, "group": GROUP, "module": MODULE,
                "version": version, "toolingCommit": TOOL_REVISION}
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise RuntimeError("ColorPicker published provenance identity differs")
    fingerprint = value.get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise RuntimeError("ColorPicker published provenance fingerprint differs")
    upstream = value.get("upstream")
    if not isinstance(upstream, dict) or upstream.get("commit") != "85f81afbccaf5c0837e402686b8db9d67cc74c59":
        raise RuntimeError("ColorPicker published upstream commit differs")
    source_set = source_set_sha256(value.get("sourceMembers"))
    if source_set != "f57dbc4d60c3b247580ebfe8f9ea1a0cf5350406935d029ddbafa4c63a431d67":
        raise RuntimeError("ColorPicker published source set differs")
    return {**expected, "fingerprint": fingerprint, "upstreamCommit": upstream["commit"], "sourceSetSha256": source_set}


def verify_metadata_source_manifest(metadata_bytes, provenance_identity):
    member_name = "META-INF/upstream/source-manifest.json"
    with zipfile.ZipFile(io.BytesIO(metadata_bytes)) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename == member_name and not entry.is_dir()]
        if len(entries) != 1:
            raise RuntimeError("ColorPicker metadata source manifest is missing or duplicated")
        raw = archive.read(entries[0])
    manifest = json.loads(raw)
    source_set = source_set_sha256(manifest.get("members"))
    if (manifest.get("fingerprint") != provenance_identity["fingerprint"] or
            manifest.get("sourceCount") != 21 or manifest.get("sourceSetSha256") != source_set or
            source_set != provenance_identity["sourceSetSha256"]):
        raise RuntimeError("ColorPicker metadata source manifest does not match published provenance")
    return raw, {"entry": member_name, "size": len(raw), "sha256": digest(raw),
                 "fingerprint": manifest["fingerprint"], "sourceSetSha256": source_set, "sourceCount": 21}


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
            raise RuntimeError("ColorPicker root and Native published provenance differ")
        provenance_artifacts.append({**row, "identity": identity})

    def gmm(url, label):
        data, row = read_http(url, PAGES)
        requests.append(row)
        value = json.loads(data)
        write_json(evidence / "remote-gmm" / (label + ".json"), value)
        owner = value["component"]
        if any(owner.get(key) != expected for key, expected in (("group", GROUP), ("module", MODULE), ("version", version))):
            raise RuntimeError("ColorPicker GMM owner differs: " + label)
        roots = {"org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains.compose.runtime:runtime", "org.jetbrains.compose.foundation:foundation", "org.jetbrains.compose.ui:ui"}
        for variant in value.get("variants", []):
            for dep in variant.get("dependencies", []):
                ga = dep["group"] + ":" + dep["module"]
                if PINS.get(ga) != dep.get("version", {}).get("requires"):
                    raise RuntimeError("ColorPicker GMM dependency version differs")
            attrs = variant.get("attributes", {})
            if (attrs.get("org.gradle.usage") == "kotlin-metadata" and attrs.get("org.jetbrains.kotlin.platform.type") == "common") or (attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.jetbrains.kotlin.native.target") in ("ohos_x64", "ohos_arm64") and "available-at" not in variant):
                if {dep["group"] + ":" + dep["module"] for dep in variant.get("dependencies", [])} != roots:
                    raise RuntimeError("ColorPicker GMM API dependency set differs")
        return value

    def artifact(module_url, declaration, role, target=None):
        directory = module_url.rsplit("/", 1)[0] + "/"
        url = public_url(urljoin(module_url, declaration["url"]), directory)
        data, row = read_http(url, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("ColorPicker GMM artifact size/SHA256 differs: " + role)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(data)
        row.update(role=role, expectedTarget=target, path=str(path), declaredName=declaration["name"])
        entries, props = klib_payload(data)
        if target is not None and (set(props.get("native_targets", "").split()) != {target} or not any("/ir/" in name and item["size"] > 0 for name, item in entries.items())):
            raise RuntimeError("ColorPicker HTTP Native target or IR differs: " + target)
        requests.append(row)
        return row, entries, data

    def pom(module_url, module, target):
        url = module_url.removesuffix(".module") + ".pom"
        data, row = read_http(url, PAGES)
        requests.append(row)
        xml = ET.fromstring(data)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + key, namespaces=ns) != expected for key, expected in (("groupId", GROUP), ("artifactId", module), ("version", version))):
            raise RuntimeError("ColorPicker Pages POM coordinates differ")
        deps = xml.findall("m:dependencies/m:dependency", ns)
        roots = {"org.jetbrains.kotlin:kotlin-stdlib", "org.jetbrains.compose.runtime:runtime", "org.jetbrains.compose.foundation:foundation", "org.jetbrains.compose.ui:ui"}
        suffix = "-ohosx64" if target == "ohos_x64" else "-ohosarm64" if target else ""
        expected = {ga + (suffix if not ga.startswith("org.jetbrains.kotlin:") else "") for ga in roots}
        actual = set()
        for dep in deps:
            ga = dep.findtext("m:groupId", namespaces=ns) + ":" + dep.findtext("m:artifactId", namespaces=ns)
            actual.add(ga)
            if PINS.get(ga) != dep.findtext("m:version", namespaces=ns) or dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
                raise RuntimeError("ColorPicker Pages POM dependency version or scope differs")
        if actual != expected or len(deps) != len(expected):
            raise RuntimeError("ColorPicker Pages POM dependency set differs")

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
                raise RuntimeError("Multiple incompatible ColorPicker common payloads")
            payload = entries
    if len(metadata) != 1:
        raise RuntimeError("Expected one ColorPicker common metadata artifact")
    raw_manifest, source_manifest = verify_metadata_source_manifest(metadata_bytes, provenance_artifacts[0]["identity"])
    manifest_path = evidence / "remote-metadata-source-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(raw_manifest)
    source_manifest.update(path=str(manifest_path), artifactUrl=metadata[0]["url"],
                           artifactSize=metadata[0]["size"], artifactSha256=metadata[0]["sha256"])
    write_json(evidence / "remote-metadata-source-manifest-receipt.json", source_manifest)
    native, owners = {}, []
    for target, module in (("ohos_x64", MODULE + "-ohosx64"), ("ohos_arm64", MODULE + "-ohosarm64")):
        links = [v["available-at"] for v in root["variants"] if v.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and v.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and v.get("attributes", {}).get("org.gradle.category") == "library" and "available-at" in v]
        expected_url = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/" + module + "-" + version + ".module"
        if not links or any(link["group"] != GROUP or link["module"] != module or link["version"] != version or urljoin(root_url, link["url"]) != expected_url for link in links):
            raise RuntimeError("ColorPicker root available-at differs: " + target)
        leaf = gmm(expected_url, module)
        pom(expected_url, module, target)
        provenance(expected_url, module)
        if urljoin(expected_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("ColorPicker Native leaf owner differs")
        owners.append({"target": target, "leafModule": module, "leafUrl": expected_url, "ownerUrl": root_url})
        native[target] = []
        for variant in leaf["variants"]:
            attrs = variant.get("attributes", {})
            if attrs.get("org.jetbrains.kotlin.native.target") == target and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.gradle.category") == "library":
                for declaration in variant.get("files", []):
                    row, _, _ = artifact(expected_url, declaration, "native", target)
                    native[target].append(row)
        if len(native[target]) != 1:
            raise RuntimeError("Expected one ColorPicker Native API Klib: " + target)
    manifest = {"status": "ANONYMOUS_PAGES_GRAPH_AND_BYTES_VERIFIED", "baseUrl": PAGES, "group": GROUP, "module": MODULE,
                "version": version, "sourceCommit": source_sha, "rootUrl": root_url, "owners": owners, "requests": requests,
                "provenanceArtifacts": provenance_artifacts, "metadataArtifacts": metadata,
                "metadataSourceManifest": source_manifest, "metadataPayload": payload,
                "nativeArtifacts": native, "librarySourcesDownloaded": False}
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
    if wrapper["sourceCommit"] != GRID_COMMIT or {item["path"] for item in wrapper["files"]} != {"gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties", "gradle.properties"}:
        raise RuntimeError("Fixed Gradle wrapper input set differs")
    prefix = "https://raw.githubusercontent.com/qsxs/gridlayout-compose/" + GRID_COMMIT + "/ohos/"
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
    write_json(output / "evidence/toolchain-inputs.json", {"runtimeToolingCommit": TOOL_REVISION, "wrapperSourceCommit": GRID_COMMIT,
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
        if target is None and not data["metadataTrace"]:
            raise RuntimeError("Consumer common metadata transform has no Pages trace")
        if (len(data["plugins"]) != 1 or data["plugins"][0]["size"] != 870498 or
                data["plugins"][0]["sha256"] != "4ffe7f38089fa4acdda5d67fa3a858b9fc2fe7ed1f2e58bedbf8d3447c15df39" or
                (target is not None and not data.get("nativeTrace"))):
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


def main():
    output = Path(os.environ["COLORPICKER_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP, "link": "NOT_RUN", "runtime": "NOT_RUN"}
    code = 1
    try:
        version, source = os.environ["COLORPICKER_VERSION"], os.environ["COLORPICKER_SOURCE_SHA"]
        mode = "gradle9"
        workflow = os.environ["CI_TOOLING_SHA"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"1\.2\.0-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete ColorPicker version must match the full producer source SHA")
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
            print("Running ColorPicker consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError("Consumer " + label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"), "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        probe_name = "src/commonMain/kotlin/ColorPickerConsumer.kt"
        for name, contents in (("settings.gradle.kts", SETTINGS), ("build.gradle.kts", BUILD), (probe_name, PROBE)):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
        shutil.copyfile(wrapper / "gradle.properties", project / "gradle.properties")
        probe = project / probe_name
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "remote-http-manifest.json"), "-PcolorpickerVersion=" + version,
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
                state.update(status="FAILED", error="Consumer structured evidence exceeds 8 MiB")
                code = 1
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
