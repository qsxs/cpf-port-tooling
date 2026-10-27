"""仅从公开 Pages 根 GAV 解析 MaterialKolor 的独立消费者。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from grid_remote_consumer import digest, klib_payload, public_url, read_http, record, tail, write_json
from colormath_remote_consumer import fetch_graph as fetch_colormath_graph, fetch_tools
from poko_remote_consumer import fetch_graph as fetch_poko_graph
from materialkolor_producer import collect_evidence_file, mark_evidence_failure

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.materialkolor"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
POKO_CLASSES = ("com.materialkolor.hct.Hct", "com.materialkolor.palettes.TonalPalette",
                "com.materialkolor.temperature.TemperatureCache", "com.materialkolor.dynamiccolor.ContrastCurve",
                "com.materialkolor.dynamiccolor.ToneDeltaPair", "com.materialkolor.dynamiccolor.DynamicColor")
STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}

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
 'org.jetbrains.skiko:skiko-ohosx64-fusionrenderer': '0.150.1-0.1.0-10'}
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
SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.materialkolor"); excludeGroup("io.github.qsxs.cpf.poko"); excludeGroup("io.github.qsxs.cpf.colormath") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.materialkolor"); excludeGroup("io.github.qsxs.cpf.poko"); excludeGroup("io.github.qsxs.cpf.colormath") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.materialkolor"); excludeGroup("io.github.qsxs.cpf.poko"); excludeGroup("io.github.qsxs.cpf.colormath") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.materialkolor"); excludeGroup("io.github.qsxs.cpf.poko"); excludeGroup("io.github.qsxs.cpf.colormath") } }
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.compose") version "2.4.20-0.1.0-08"
    }
}
val tools = file(providers.gradleProperty("consumerTools").get())
fun json(name: String) = JsonSlurper().parse(tools.resolve(name)) as Map<*, *>
val runtimePins = json("dependency-pins.json")
val metadataPins = json("metadata-pins.json")
val launcherPins = json("metadata-toolchain.json")["launcherPins"] as Map<*, *>
val commonizerPins = json("commonizer-toolchain.json")["pins"] as Map<*, *>
val composePins = json("compiler-plugin-toolchain.json")["pins"] as Map<*, *>
val hostPins = json("native-compiler-toolchain.json")["pins"] as Map<*, *>
val allowed = runtimePins.entries + metadataPins.entries + launcherPins.entries + commonizerPins.entries + composePins.entries + hostPins.entries

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven { name = "CpfPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.materialkolor"); includeGroup("io.github.qsxs.cpf.poko"); includeGroup("io.github.qsxs.cpf.colormath") }
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
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.materialkolor"); excludeGroup("io.github.qsxs.cpf.poko"); excludeGroup("io.github.qsxs.cpf.colormath") } }
    }
}
rootProject.name = "materialkolor-pages-consumer"
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
val materialGroup = "io.github.qsxs.cpf.materialkolor"
val materialVersion = providers.gradleProperty("materialVersion").get()
val probe = file("src/commonMain/kotlin/MaterialKolorConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val dependencyVersions = asMap(http.getValue("dependencies"))
val publicVersions = mapOf(materialGroup to materialVersion,
    "io.github.qsxs.cpf.poko" to asMap(dependencyVersions.getValue("poko")).getValue("version").toString(),
    "io.github.qsxs.cpf.colormath" to asMap(dependencyVersions.getValue("colormath")).getValue("version").toString())
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
            dependencies { implementation("$materialGroup:material-kolor:$materialVersion") }
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
        val selected = publicVersions[requested.group]
        if (selected != null) {
            check(requested.version == selected) { "Public dependency version differs: ${requested}" }
        } else {
            check(requested.group != "com.materialkolor" && requested.group != "com.github.ajalt.colormath" &&
                !(requested.group == "dev.drewhamilton.poko" && requested.name.startsWith("poko-annotations")))
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
val publicModules = mapOf("material-kolor" to materialGroup, "material-color-utilities" to materialGroup,
    "poko-annotations" to "io.github.qsxs.cpf.poko", "colormath" to "io.github.qsxs.cpf.colormath")
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
        }
        mapOf("component" to id.displayName, "attributes" to attrs, "files" to records(listOf(artifact.file)))
    }
    check(publicModules.keys.all { found[it] == 1 }) { "Incomplete public graph for $name: $found" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$materialGroup:material-kolor:$materialVersion" })
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
        evidence("consumer-resolution.json", mapOf("materialVersion" to materialVersion, "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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

import androidx.compose.material3.ColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.materialkolor.PaletteStyle
import com.materialkolor.dynamiccolor.ColorSpec
import com.materialkolor.rememberDynamicColorScheme

@Composable
fun applicationThemeProbe(primary: Color, tertiary: Color, dark: Boolean): ColorScheme =
    rememberDynamicColorScheme(
        primary = primary,
        tertiary = tertiary,
        isDark = dark,
        specVersion = ColorSpec.SpecVersion.SPEC_2025,
        style = PaletteStyle.Content,
        modifyColorScheme = { it },
    )
'''



def expected_dependencies(module, version, dependencies):
    result = {("org.jetbrains.kotlin", "kotlin-stdlib"): "2.4.20-0.1.0-08"}
    if module == "material-color-utilities":
        item = dependencies["poko"]
        result[(item["group"], item["module"])] = item["version"]
    else:
        item = dependencies["colormath"]
        result[(item["group"], item["module"])] = item["version"]
        result[(GROUP, "material-color-utilities")] = version
        for ga in (("org.jetbrains.compose.runtime", "runtime"), ("org.jetbrains.compose.foundation", "foundation"),
                   ("org.jetbrains.compose.ui", "ui"), ("org.jetbrains.compose.material3", "material3")):
            result[ga] = "1.12.0-0.1.0-11"
    return result


def validate_dependencies(lock):
    if lock.get("repository") != PAGES or set(lock.get("dependencies", {})) != {"poko", "colormath"}:
        raise RuntimeError("Published provenance has an incomplete public dependency lock")
    specs = {"poko": ("io.github.qsxs.cpf.poko", "poko-annotations", "0.23.1"),
             "colormath": ("io.github.qsxs.cpf.colormath", "colormath", "3.6.1")}
    for name, (group, module, base) in specs.items():
        item = lock["dependencies"][name]
        source, version = item.get("sourceCommit", ""), item.get("version", "")
        if item.get("group") != group or item.get("module") != module or not re.fullmatch(r"[0-9a-f]{40}", source):
            raise RuntimeError("Published public dependency identity differs: " + name)
        pattern = re.escape(base) + r"-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*"
        if not re.fullmatch(pattern, version) or not re.fullmatch(r"[0-9a-f]{64}", item.get("rootGmmSha256", "")):
            raise RuntimeError("Published public dependency version or GMM hash differs: " + name)
        if set(item.get("artifacts", {})) != {"metadata", "ohos_x64", "ohos_arm64"}:
            raise RuntimeError("Published public dependency artifact lock differs: " + name)
        for artifact in item["artifacts"].values():
            if not isinstance(artifact.get("size"), int) or artifact["size"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")) or not artifact.get("payload"):
                raise RuntimeError("Published public dependency artifact digest differs: " + name)
    return lock["dependencies"]


def fetch_module(module, version, source_commit, dependencies, output):
    evidence = output / "evidence"
    downloads = output / "http-data"
    downloads.mkdir(parents=True, exist_ok=True)
    base = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/"
    root_url = base + module + "-" + version + ".module"
    expected = expected_dependencies(module, version, dependencies)
    requests = []
    provenance_data, provenance_http = read_http(base + module + "-" + version + "-provenance.json", PAGES)
    provenance = json.loads(provenance_data)
    if any(provenance.get(key) != value for key, value in (("group", GROUP), ("module", module), ("version", version), ("sourceCommit", source_commit))):
        raise RuntimeError("MaterialKolor provenance differs: " + module)
    if validate_dependencies(provenance["dependencies"]) != dependencies:
        raise RuntimeError("MaterialKolor module dependency locks differ")
    requests.append(provenance_http)

    def fetch_gmm(url, label):
        data, row = read_http(url, PAGES)
        requests.append(row)
        model = json.loads(data)
        owner = model["component"]
        if any(owner.get(k) != v for k, v in (("group", GROUP), ("module", module), ("version", version))):
            raise RuntimeError("MaterialKolor GMM owner differs: " + label)
        write_json(evidence / "remote-gmm" / (label + ".json"), model)
        return model

    def check_pom(module_url, artifact, target):
        data, row = read_http(module_url.removesuffix(".module") + ".pom", PAGES)
        requests.append(row)
        xml = ET.fromstring(data)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + key, namespaces=ns) != val for key, val in (("groupId", GROUP), ("artifactId", artifact), ("version", version))):
            raise RuntimeError("MaterialKolor POM coordinates differ: " + artifact)
        suffix = "-ohosx64" if target == "ohos_x64" else "-ohosarm64" if target else ""
        expected_pom = {(group, name + (suffix if target and group != "org.jetbrains.kotlin" else "")): ver
                        for (group, name), ver in expected.items()}
        actual = {}
        for dep in xml.findall("m:dependencies/m:dependency", ns):
            key = (dep.findtext("m:groupId", namespaces=ns), dep.findtext("m:artifactId", namespaces=ns))
            if dep.findtext("m:scope", namespaces=ns) != ("compile" if target else "runtime"):
                raise RuntimeError("MaterialKolor POM scope differs: " + artifact)
            actual[key] = dep.findtext("m:version", namespaces=ns)
        if actual != expected_pom:
            raise RuntimeError("MaterialKolor POM dependencies differ: " + artifact)

    def select(model, url, target):
        selected = []
        for variant in model["variants"]:
            attrs = variant.get("attributes", {})
            api = (not target and attrs.get("org.gradle.usage") == "kotlin-metadata" and attrs.get("org.jetbrains.kotlin.platform.type") == "common") or (
                target and attrs.get("org.gradle.usage") == "kotlin-api" and attrs.get("org.jetbrains.kotlin.native.target") == target)
            for dep in variant.get("dependencies", []):
                key = (dep["group"], dep["module"])
                if key not in expected or dep.get("version", {}).get("requires") != expected[key]:
                    raise RuntimeError("Unexpected published dependency: " + str(key))
            if not api:
                continue
            actual = {(dep["group"], dep["module"]): dep["version"]["requires"] for dep in variant.get("dependencies", [])}
            if actual != expected:
                raise RuntimeError("Published API dependency set differs: " + module)
            selected.extend(variant.get("files", []))
        if len(selected) != 1:
            raise RuntimeError("Expected exactly one public API artifact: " + module)
        declaration = selected[0]
        location = public_url(urljoin(url, declaration["url"]), url.rsplit("/", 1)[0] + "/")
        data, row = read_http(location, PAGES)
        if row["size"] != declaration["size"] or row["sha256"] != declaration["sha256"]:
            raise RuntimeError("Public GMM artifact bytes differ: " + module)
        path = downloads / (row["sha256"] + ".bin")
        path.write_bytes(data)
        row.update(path=str(path), declaredName=declaration["name"], expectedTarget=target)
        entries, properties = klib_payload(data)
        if target and (set(properties.get("native_targets", "").split()) != {target} or
                       not any("/ir/" in name and item["size"] > 0 for name, item in entries.items())):
            raise RuntimeError("Public native target or IR differs: " + module)
        requests.append(row)
        return row, entries

    root = fetch_gmm(root_url, module)
    check_pom(root_url, module, None)
    meta, payload = select(root, root_url, None)
    native = {}
    for target, suffix in (("ohos_x64", "-ohosx64"), ("ohos_arm64", "-ohosarm64")):
        leaf_name = module + suffix
        leaf_url = PAGES + GROUP.replace(".", "/") + "/" + leaf_name + "/" + version + "/" + leaf_name + "-" + version + ".module"
        links = [v["available-at"] for v in root["variants"] if v.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and
                 v.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and "available-at" in v]
        if not links or any(link["group"] != GROUP or link["module"] != leaf_name or link["version"] != version or urljoin(root_url, link["url"]) != leaf_url for link in links):
            raise RuntimeError("Public available-at differs: " + leaf_name)
        leaf = fetch_gmm(leaf_url, leaf_name)
        if urljoin(leaf_url, leaf["component"]["url"]) != root_url:
            raise RuntimeError("Public Native owner differs: " + leaf_name)
        check_pom(leaf_url, leaf_name, target)
        row, _ = select(leaf, leaf_url, target)
        native[target] = [row]
    return {"group": GROUP, "module": module, "version": version, "rootUrl": root_url, "requests": requests,
            "metadataArtifacts": [meta], "metadataPayload": payload, "nativeArtifacts": native}



def inspect_generated(output, native_home, env):
    evidence = output / "evidence"
    paths = []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
        row = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text(encoding="utf-8"))
        trace = row["metadataTrace"] if target is None else row["nativeTrace"]
        paths.append((name, target, Path(trace["material-color-utilities"]["compilerLibrary"])))
    checks = []
    for name, target, klib in paths:
        operations = ("dump-metadata", "dump-metadata-signatures") + (("dump-ir-signatures",) if target else ())
        output_text = {}
        for operation in operations:
            result = subprocess.run([str(native_home / "bin/klib"), operation, str(klib)], env=env, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError("Public MCI Klib " + operation + " failed: " + result.stderr[-4000:])
            output_text[operation] = result.stdout
            (evidence / (name + "-" + operation + ".txt")).write_text(result.stdout, encoding="utf-8")
        declared = ""
        if target:
            ir = output_text["dump-ir-signatures"]
            if "// Declared signatures:" not in ir or "// Imported signatures:" not in ir:
                raise RuntimeError("Native IR signature sections differ")
            declared = ir.split("// Declared signatures:", 1)[1].split("// Imported signatures:", 1)[0]
        metadata = output_text["dump-metadata"].splitlines()
        signatures = output_text["dump-metadata-signatures"].splitlines()
        for fqn in POKO_CLASSES:
            package, cls = fqn.rsplit(".", 1)
            headers = [i for i, line in enumerate(metadata) if re.search(r"\bclass\s+" + re.escape(fqn.replace(".", "/")) + r"\s*:\s*kotlin/Any\s*\{", line)]
            if len(headers) != 1:
                raise RuntimeError("MCI class metadata missing: " + fqn)
            block = []
            for line in metadata[headers[0] + 1:]:
                if re.fullmatch(r"\s*}\s*", line):
                    break
                block.append(line)
            for method in ("equals", "hashCode", "toString"):
                signature = package + "/" + cls + "." + method + "|" + method + "("
                declarations = [line.strip() for line in block if re.search(r"\bfun\s+" + method + r"\s*\(", line)]
                matched = [line.strip() for line in signatures if signature in line]
                ir = [line.strip() for line in declared.splitlines() if signature in line]
                if len(declarations) != 1 or len(matched) != 1 or (target and len(ir) != 1):
                    raise RuntimeError("MCI own Poko declaration missing: " + fqn + "." + method + " in " + name)
                checks.append({"stage": name, "class": fqn, "method": method, "metadata": declarations[0],
                               "metadataSignature": matched[0], "irSignature": ir[0] if target else None})
    write_json(evidence / "poko-generated.json", {"checks": checks, "link": "NOT_RUN", "runtime": "NOT_RUN"})



def main():
    output = Path(os.environ["MATERIALKOLOR_CONSUMER_OUTPUT"]).resolve()
    evidence, upload = output / "evidence", output / "upload"
    evidence.mkdir(parents=True, exist_ok=True)
    state = {"status": "STARTED", "started": time.time(), "link": "NOT_RUN", "runtime": "NOT_RUN"}
    failed = None
    try:
        version, source, workflow = os.environ["MATERIALKOLOR_VERSION"], os.environ["MATERIALKOLOR_SOURCE_SHA"], os.environ["CI_TOOLING_SHA"]
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or not re.fullmatch(r"5\.0\.0-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
            raise RuntimeError("Concrete MaterialKolor version must match its producer source commit")
        env = {key: os.environ[key] for key in ("PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "LD_LIBRARY_PATH") if key in os.environ}
        for key, name in (("GRADLE_USER_HOME", "gradle-home"), ("KONAN_DATA_DIR", "konan"), ("TMPDIR", "temp"), ("TEMP", "temp"), ("TMP", "temp")):
            path = output / name
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        actual = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], env=env, check=True, capture_output=True, text=True).stdout.strip()
        if actual != workflow:
            raise RuntimeError("Consumer tooling checkout differs")
        state.update(version=version, sourceCommit=source, workflowToolingCommit=workflow)
        state["stage"] = "PublicGraph"
        write_json(evidence / "run.json", state)
        base = PAGES + GROUP.replace(".", "/") + "/material-kolor/" + version + "/material-kolor-" + version
        data, provenance_http = read_http(base + "-provenance.json", PAGES)
        provenance = json.loads(data)
        if any(provenance.get(k) != v for k, v in (("sourceCommit", source), ("version", version), ("group", GROUP), ("module", "material-kolor"))):
            raise RuntimeError("Published MaterialKolor provenance differs")
        dependencies = validate_dependencies(provenance["dependencies"])
        modules = {}
        modules["material-kolor"] = fetch_module("material-kolor", version, source, dependencies, output)
        modules["material-color-utilities"] = fetch_module("material-color-utilities", version, source, dependencies, output)
        for name, fetch in (("poko", fetch_poko_graph), ("colormath", fetch_colormath_graph)):
            item = dependencies[name]
            result = fetch(item["version"], output / "dependencies" / name)
            if result["requests"][0]["sha256"] != item["rootGmmSha256"] or result["group"] != item["group"] or result["module"] != item["module"]:
                raise RuntimeError("Published transitive dependency differs: " + name)
            meta = result["metadataArtifacts"][0]
            expected = item["artifacts"]["metadata"]
            if (meta["size"], meta["sha256"], result["metadataPayload"]) != (expected["size"], expected["sha256"], expected["payload"]):
                raise RuntimeError("Published dependency metadata bytes differ: " + name)
            for target in ("ohos_x64", "ohos_arm64"):
                artifact = result["nativeArtifacts"][target][0]
                payload, _ = klib_payload(Path(artifact["path"]).read_bytes())
                expected = item["artifacts"][target]
                if (artifact["size"], artifact["sha256"], payload) != (expected["size"], expected["sha256"], expected["payload"]):
                    raise RuntimeError("Published dependency Native bytes differ: " + name + ":" + target)
            modules[item["module"]] = result
        public = {"status": "ANONYMOUS_PUBLIC_GRAPH_VERIFIED", "version": version, "sourceCommit": source,
                  "provenanceHttp": provenance_http, "dependencies": dependencies, "modules": modules, "librarySourcesDownloaded": False}
        write_json(evidence / "public-manifest.json", public)
        state["stage"] = "PinnedBuildTools"
        tools, wrapper = fetch_tools(output, "gradle9")
        tool_root = tools / TOOL_DIR
        for name, value in (("dependency-pins.json", PINS), ("metadata-pins.json", METADATA_PINS), ("compiler-plugin-toolchain.json", COMPOSE_TOOL)):
            write_json(tool_root / name, value)
        logs = output / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        def run(label, argv):
            state["stage"] = label
            write_json(evidence / "run.json", state)
            stdout, stderr = logs / (label + ".stdout.log"), logs / (label + ".stderr.log")
            print("Running MaterialKolor consumer " + label, flush=True)
            with stdout.open("wb") as out, stderr.open("wb") as err:
                result = subprocess.run(argv, cwd=output, env=env, stdout=out, stderr=err)
            if result.returncode:
                raise RuntimeError(label + " failed with exit " + str(result.returncode))
            return stdout.read_text(encoding="utf-8").strip()
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tool_root / "bootstrap-native.py"),
                    "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"]))
        project = output / "project"
        for name, content in (("settings.gradle.kts", SETTINGS), ("build.gradle.kts", BUILD), ("src/commonMain/kotlin/MaterialKolorConsumer.kt", PROBE)):
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (project / "gradle.properties").write_bytes((wrapper / "gradle.properties").read_bytes())
        probe = project / "src/commonMain/kotlin/MaterialKolorConsumer.kt"
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace", "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerTools=" + str(tool_root), "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerHttp=" + str(evidence / "public-manifest.json"), "-PmaterialVersion=" + version,
                "-PprobeSha256=" + digest(probe.read_bytes()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                names = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(names):
                    raise RuntimeError("Consumer tasks absent from actual discovery")
                write_json(evidence / "task-discovery.json", {"required": sorted(REQUIRED), "stdout": record(logs / "Tasks.stdout.log")})
        for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
            result = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text())
            if result["target"] != target or len(result["sources"]) != 1 or not result["metadataPayload"] or not result["outputs"]:
                raise RuntimeError("Consumer compilation evidence differs: " + name)
            if target and (not result["irPayload"] or set(result["nativeTargets"]) != {target} or not result["nativeTrace"]):
                raise RuntimeError("Consumer native target, IR or trace differs: " + name)
            if target is None and not result["metadataTrace"]:
                raise RuntimeError("Consumer metadata trace is missing")
            for item in result["sources"] + result["outputs"]:
                if record(Path(item["path"])) != item:
                    raise RuntimeError("Consumer compiler input/output bytes changed")
        state["stage"] = "InspectPublicMciGeneratedMembers"
        inspect_generated(output, native, env)
        state["status"] = "PUBLIC_ROOT_METADATA_AND_DUAL_ABI_COMPILED"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        for stage in ("BootstrapNative", *STAGES):
            for stream in ("stdout", "stderr"):
                content = tail(output / "logs" / (stage + "." + stream + ".log"))
                if content:
                    (evidence / (stage + "." + stream + "-tail.log")).write_text(content, encoding="utf-8")
                    if failed is not None and state.get("stage") == stage:
                        print(content, file=sys.stderr)
        state["finished"] = time.time()
        write_json(evidence / "run.json", state)
        try:
            compressed = []
            for item in sorted(evidence.rglob("*")):
                if item.is_file():
                    destination = upload / item.relative_to(evidence).parent
                    destination.mkdir(parents=True, exist_ok=True)
                    before = len(compressed)
                    collect_evidence_file(item, destination, compressed)
                    if len(compressed) != before:
                        compressed[-1]["directory"] = destination.relative_to(upload).as_posix()
            for dep in ("poko", "colormath"):
                source = output / "dependencies" / dep / "evidence"
                if source.is_dir():
                    for item in sorted(source.rglob("*.json")):
                        destination = upload / "dependencies" / dep / item.relative_to(source).parent
                        destination.mkdir(parents=True, exist_ok=True)
                        before = len(compressed)
                        collect_evidence_file(item, destination, compressed)
                        if len(compressed) != before:
                            compressed[-1]["directory"] = destination.relative_to(upload).as_posix()
            if compressed:
                write_json(upload / "evidence-index.json", {"schemaVersion": 1, "compressedFiles": compressed})
        except Exception as error:
            failed = mark_evidence_failure(state, failed, error)
            upload.mkdir(parents=True, exist_ok=True)
            write_json(upload / "run.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
