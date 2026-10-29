"""匿名消费 Pages 的 FileKit；只编译探针并保留制品与编译输入证据。"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import zipfile

from filekit_producer import collect_file, publish_run_evidence, stream_digest, write_json_new, write_new
from grid_remote_consumer import digest, klib_payload, public_url, read_http
from lyricist_remote_consumer import TOOL_LOCK

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.filekit"
MODULES = ("filekit-core", "filekit-dialogs")
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
KOTLIN_VERSION = "2.4.20-0.1.0-08"
SOURCE_MODEL_SHA = "f1c121f45309aff7a72a81144d41fa5132137f299fcde979cdc577c1b3085746"
SOURCE_INPUTS_SHA = "813cc732df4fa538e6131071952fc06781e78ab0f2d3388730c9769658a9ab97"
SOURCE_PATCH_SHA = "eabb5e7f1b37bf7e6ad42f6c67caaed3a9bb114baba04978bffbc4b011736440"
ARKTS_SHA = "73d6c5432666cc432c40cd5cc26549db28c8b2b9d56bd142dbffdf3de76ab681"
LICENSES = {
    "upstream": (1075, "5ceb0f372844932c328a4d34bfb6b1903b157d4b3467c5de484bfec8e5aea7ca"),
    "community": (1075, "a41675c6f02403d7845edd2488c5eafbe1dc5f20daac608e09f71c42fe9ff22b"),
}
WRAPPER = {
    "gradlew": (363, "0e96228f9589965a5e171190f69f6e820f128bdae180f7e2acc6e4d65f788ed5"),
    "gradle/wrapper/gradle-wrapper.jar": (43764, "7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172"),
    "gradle/wrapper/gradle-wrapper.properties": (340, "1b9cd6961ee86eea17b2f912bddb22030492db23fc6dff07da6c30eccaaab0c4"),
}
BASE_PINS = {
    "androidx.annotation:annotation": "1.10.0",
    "org.jetbrains.kotlin:kotlin-stdlib": KOTLIN_VERSION,
}
for module, version in (
    ("atomicfu", "0.33.0-0.1.0-07"),
    ("kotlinx-coroutines-core", "1.11.0-0.1.0-07"),
    ("kotlinx-io-core", "0.9.1-0.1.0-07"),
    ("kotlinx-io-bytestring", "0.9.1-0.1.0-07"),
    ("kotlinx-serialization-core", "1.11.0-0.1.0-07"),
    ("kotlinx-serialization-json", "1.11.0-0.1.0-07"),
):
    for suffix in ("", "-ohosx64", "-ohosarm64"):
        BASE_PINS["org.jetbrains.kotlinx:" + module + suffix] = version
for suffix in ("", "-ohosx64", "-ohosarm64"):
    BASE_PINS["org.jetbrains.compose.annotation-internal:annotation" + suffix] = "1.9.1-0.1.0-11"

# 消费者显式提供项目和探针所需的公开 Flow、RawSource/RawSink 类型依赖；core 仍须由 dialogs 的 api 传递。
ENVIRONMENT_DEPENDENCY_PURPOSE = ("项目和编译探针显式提供 coroutines 与 kotlinx-io，"
                                  "用于公开 Flow 与 RawSource/RawSink 类型；FileKit core 必须由 dialogs 的 api 传递。")
ENVIRONMENT_DEPS = (
    "org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0-0.1.0-07",
    "org.jetbrains.kotlinx:kotlinx-io-core:0.9.1-0.1.0-07",
)
REQUIRED_COMMON = {
    "filekit-core": {"org.jetbrains.kotlinx:kotlinx-io-core", "org.jetbrains.kotlinx:kotlinx-coroutines-core",
                     "org.jetbrains.kotlinx:kotlinx-serialization-core"},
    "filekit-dialogs": {GROUP + ":filekit-core", "org.jetbrains.kotlinx:kotlinx-coroutines-core"},
}
REQUIRED_NATIVE = {
    "filekit-core": {"org.jetbrains.compose.annotation-internal:annotation"},
    "filekit-dialogs": {"org.jetbrains.kotlinx:kotlinx-serialization-json"},
}
STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"], "Metadata": ["recordConsumerMetadata"],
         "NativeX64": ["recordConsumerX64"], "NativeArm64": ["recordConsumerArm64"]}
REQUIRED_TASKS = {"resolveConsumer", "verifyConsumerTools", "compileCommonMainKotlinMetadata",
                  "compileKotlinOhosX64", "compileKotlinOhosArm64", "recordConsumerMetadata",
                  "recordConsumerX64", "recordConsumerArm64"}

COMMON_PROBE = r'''package acceptance

import io.github.vinceglb.filekit.FileKit
import io.github.vinceglb.filekit.dialogs.FileKitType
import io.github.vinceglb.filekit.dialogs.openFilePicker
import io.github.vinceglb.filekit.readBytes

suspend fun pickImageBytes(): ByteArray? =
    FileKit.openFilePicker(type = FileKitType.Image)?.readBytes()
'''

OHOS_PROBE = r'''@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package acceptance

import io.github.vinceglb.filekit.FileKit
import io.github.vinceglb.filekit.ImageFormat
import io.github.vinceglb.filekit.PlatformFile
import io.github.vinceglb.filekit.compressImage
import io.github.vinceglb.filekit.dialogs.FileKitShareSettings
import io.github.vinceglb.filekit.dialogs.init
import io.github.vinceglb.filekit.dialogs.openFileSaver
import io.github.vinceglb.filekit.dialogs.shareFile
import io.github.vinceglb.filekit.readBytes
import io.github.vinceglb.filekit.sink
import io.github.vinceglb.filekit.source
import io.github.vinceglb.filekit.write
import platform.ArkTS.ArkTS_Napi_NativeModule.napi_env
import platform.ArkTS.ArkTS_Napi_NativeModule.napi_value

suspend fun saveImage(env: napi_env, context: napi_value, shareFactory: napi_value, file: PlatformFile) {
    val session = FileKit.init(env, context, shareFactory)
    val input = file.source()
    input.close()
    val destination = FileKit.openFileSaver(
        suggestedName = "image",
        defaultExtension = "jpg",
        allowedExtensions = setOf("jpg"),
    )
    if (destination != null) {
        val output = destination.sink()
        output.close()
        val bytes = FileKit.compressImage(file.readBytes(), imageFormat = ImageFormat.JPEG)
        val fileBytes = FileKit.compressImage(file = file, imageFormat = ImageFormat.JPEG)
        destination.write(bytes + fileBytes)
        FileKit.shareFile(file = destination, shareSettings = FileKitShareSettings.createDefault())
        destination.close()
    }
    file.close()
    session.dispose()
}
'''

SETTINGS = r'''pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven { name = "FileKitPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.filekit") }
        }
        google { content { includeModule("androidx.annotation", "annotation") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.filekit") } }
    }
}
rootProject.name = "filekit-pages-consumer"
'''

PROPERTIES = r'''org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8
org.gradle.workers.max=4
org.gradle.parallel=false
kotlin.mpp.applyDefaultHierarchyTemplate=false
kotlin.native.ignoreDisabledTargets=false
kotlin.native.cacheKind.ohos_x64=none
kotlin.native.cacheKind.ohos_arm64=none
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

plugins { kotlin("multiplatform") }
fun readMap(file: File): Map<String, Any?> =
    (JsonSlurper().parse(file) as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun asMap(value: Any?): Map<String, Any?> =
    (value as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
fun sha(file: File) = digest(file.readBytes())
fun leaves(file: File): List<File> = if (file.isDirectory) file.walkTopDown().filter(File::isFile).toList()
    else if (file.isFile) listOf(file) else emptyList()
fun records(files: Iterable<File>) = files.flatMap(::leaves).distinct().sortedBy { it.path }.map {
    mapOf("path" to it.absolutePath, "size" to it.length(), "sha256" to sha(it))
}

val groupName = "io.github.qsxs.cpf.filekit"
val libraryVersion = providers.gradleProperty("filekitVersion").get()
val consumerStage = providers.gradleProperty("consumerStage").get()
val output = file(providers.gradleProperty("consumerOutput").get())
val evidenceDir = file(providers.gradleProperty("consumerEvidence").get())
val toolDir = file(providers.gradleProperty("consumerTools").get())
val http = readMap(file(providers.gradleProperty("consumerHttp").get()))
val pins = readMap(file(providers.gradleProperty("consumerPins").get()))
val commonProbe = file("src/commonMain/kotlin/FileKitCommonProbe.kt").canonicalFile
val ohosProbe = file("src/ohosMain/kotlin/FileKitOhosProbe.kt").canonicalFile
val commonSha = providers.gradleProperty("commonProbeSha").get()
val ohosSha = providers.gradleProperty("ohosProbeSha").get()
val metadataTools = readMap(toolDir.resolve("metadata-toolchain.json"))
val launcherPins = asMap(metadataTools.getValue("launcherPins"))
val launcherArtifacts = asMap(metadataTools.getValue("launcherArtifacts"))
val commonizer = readMap(toolDir.resolve("commonizer-toolchain.json"))
val commonizerPins = launcherPins + asMap(commonizer.getValue("pins"))
val commonizerArtifacts = launcherArtifacts + asMap(commonizer.getValue("artifacts"))
val host = readMap(toolDir.resolve("native-compiler-toolchain.json"))
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
            dependencies {
                implementation("$groupName:filekit-dialogs:$libraryVersion")
                implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0-0.1.0-07")
                implementation("org.jetbrains.kotlinx:kotlinx-io-core:0.9.1-0.1.0-07")
            }
        }
        val ohosMain by creating {
            dependsOn(commonMain)
            kotlin.setSrcDirs(listOf(file("src/ohosMain/kotlin")))
        }
        val ohosX64Main by getting { dependsOn(ohosMain) }
        val ohosArm64Main by getting { dependsOn(ohosMain) }
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
    val library = name.endsWith("ResolvableDependenciesMetadata") || name == "allSourceSetsCompileDependenciesMetadata" ||
        name.endsWith("CompileKlibraries") || name.endsWith("CompilationDependenciesMetadata")
    if (library && !name.contains("Test", ignoreCase = true)) resolutionStrategy.eachDependency {
        val ga = "${requested.group}:${requested.name}"
        val fixed = pins[ga]?.toString() ?: error("Unpinned consumer dependency: $ga")
        if (requested.group == groupName) {
            check(requested.version == libraryVersion && fixed == libraryVersion) { "FileKit version differs: $requested" }
        } else if (requested.version != fixed) useVersion(fixed)
    }
}

fun evidence(name: String, data: Any) {
    val destination = evidenceDir.resolve(name)
    check(!destination.exists()) { "Consumer evidence already exists: $name" }
    destination.writeText(JsonOutput.prettyPrint(JsonOutput.toJson(data)) + "\n")
}
fun edges(configuration: Configuration) = configuration.incoming.resolutionResult.allDependencies.map { edge ->
    if (edge !is ResolvedDependencyResult)
        throw GradleException("Unresolved consumer dependency: $edge", (edge as? UnresolvedDependencyResult)?.failure)
    mapOf("from" to edge.from.id.displayName, "requested" to edge.requested.displayName, "selected" to edge.selected.id.displayName)
}
fun checkedTools(name: String, fixed: Map<String, Any?>, expected: Map<String, Any?>): Map<String, Any> {
    val configuration = configurations.getByName(name)
    val actual = configuration.resolvedConfiguration.resolvedArtifacts.map { artifact ->
        val id = artifact.moduleVersion.id
        val ga = "${id.group}:${id.name}"
        check(fixed[ga] == id.version) { "Consumer tool version differs: $id" }
        val item = asMap(expected.getValue(ga))
        check(sha(artifact.file) == item["sha256"] && artifact.file.length() == (item.getValue("size") as Number).toLong()) {
            "Consumer tool bytes differ: $id"
        }
        mapOf("gav" to id.toString(), "files" to records(listOf(artifact.file)))
    }
    check(actual.size == fixed.size && actual.map { it.getValue("gav") }.toSet() ==
        fixed.map { "${it.key}:${it.value}" }.toSet())
    return mapOf("configuration" to name, "edges" to edges(configuration), "artifacts" to actual)
}
fun toolRecords() = mapOf(
    "nativeCompiler" to checkedTools(host.getValue("configuration").toString(), hostPins, hostArtifacts),
    "commonizer" to checkedTools(commonizer.getValue("configuration").toString(), commonizerPins, commonizerArtifacts),
)
fun directDependencies(): List<String> {
    val actual = configurations.getByName("commonMainImplementation").dependencies.map {
        "${it.group}:${it.name}:${it.version}"
    }.sorted()
    check(actual.containsAll(setOf(
        "$groupName:filekit-dialogs:$libraryVersion",
        "org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0-0.1.0-07",
        "org.jetbrains.kotlinx:kotlinx-io-core:0.9.1-0.1.0-07",
    )))
    check(actual.none { it.startsWith("$groupName:filekit-core:") }) { "Core must arrive transitively" }
    return actual
}
fun resolution() = listOf("commonMainResolvableDependenciesMetadata", "ohosX64CompileKlibraries", "ohosArm64CompileKlibraries").map { name ->
    val configuration = configurations.getByName(name)
    val target = when (name) { "ohosX64CompileKlibraries" -> "ohos_x64"; "ohosArm64CompileKlibraries" -> "ohos_arm64"; else -> null }
    val manifests = asMap(http.getValue("modules"))
    val found = mutableMapOf<String, Int>()
    val artifacts = configuration.incoming.artifacts.artifacts.map { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier)
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        val module = listOf("filekit-core", "filekit-dialogs").singleOrNull { base ->
            id.group == groupName && id.module in listOf(base, "$base-ohosx64", "$base-ohosarm64")
        }
        if (id.group == groupName) {
            check(module != null && id.version == libraryVersion) { "Unexpected FileKit component: $id" }
            val info = asMap(manifests.getValue(module))
            val declared = if (target == null) (info.getValue("metadataArtifacts") as List<*>).map(::asMap)
                else (asMap(info.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
            if (target == null) check(id.module == module && attrs["org.jetbrains.kotlin.platform.type"] == "common" &&
                attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf(module, module + if (target == "ohos_x64") "-ohosx64" else "-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            check(declared.any { it["sha256"] == sha(artifact.file) && (it.getValue("size") as Number).toLong() == artifact.file.length() }) {
                "Resolved FileKit artifact differs from anonymous Pages: $id"
            }
            found[module] = (found[module] ?: 0) + 1
        } else {
            val ga = "${id.group}:${id.module}"
            check(pins[ga] == id.version) { "Unpinned resolved consumer dependency: $id" }
        }
        mapOf("component" to id.displayName, "attributes" to attrs, "files" to records(listOf(artifact.file)))
    }
    check(listOf("filekit-core", "filekit-dialogs").all { found[it] == 1 }) { "Incomplete FileKit graph: $name $found" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$groupName:filekit-dialogs:$libraryVersion" })
    check(graph.any { edge ->
        val from = edge.getValue("from").toString()
        from in listOf("$groupName:filekit-dialogs:$libraryVersion", "$groupName:filekit-dialogs-ohosx64:$libraryVersion",
            "$groupName:filekit-dialogs-ohosarm64:$libraryVersion") &&
            edge.getValue("requested") == "$groupName:filekit-core:$libraryVersion"
    }) { "FileKit dialogs api edge to core is absent: $name" }
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
    return listOf("filekit-core", "filekit-dialogs").associateWith { module ->
        val info = asMap(manifests.getValue(module))
        val expected: Map<String, Map<String, Any>> = if (target == null)
            asMap(info.getValue("metadataPayload")).mapValues { (_, value) ->
                val row = asMap(value)
                mapOf("size" to (row.getValue("size") as Number).toLong(), "sha256" to row.getValue("sha256")!!)
            }
        else {
            val artifacts = (asMap(info.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
            check(artifacts.size == 1)
            payload(file(artifacts.single().getValue("path")!!))
        }
        check(expected.isNotEmpty())
        val matches = candidates.filterValues { it == expected }.keys
        check(matches.size == 1) { "Compiler library cannot be traced to anonymous Pages $module for $target" }
        mapOf("compilerLibrary" to matches.single().absolutePath, "payloadFileCount" to expected.size)
    }
}
val checkTools = tasks.register("verifyConsumerTools") {
    outputs.upToDateWhen { false }
    doLast { evidence("consumer-tools-$consumerStage.json", toolRecords()) }
}
tasks.withType<KotlinNativeCompile>().configureEach { if (name in compileTasks) dependsOn(checkTools) }
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "8.11.1" && System.getProperty("java.specification.version") == "17")
        evidence("consumer-resolution.json", mapOf("filekitVersion" to libraryVersion,
            "consumerDirectDependencies" to directDependencies(),
            "consumerEnvironmentDependencies" to listOf("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0-0.1.0-07",
                "org.jetbrains.kotlinx:kotlinx-io-core:0.9.1-0.1.0-07"),
            "consumerEnvironmentDependencyPurpose" to "项目和探针所需的公开 Flow 与 RawSource/RawSink 类型",
            "filekitCoreResolution" to "DIALOGS_API_TRANSITIVE_REQUIRED",
            "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(commonProbe, ohosProbe))))
    }
}
fun recordCompilation(name: String, taskName: String, target: String?) {
    tasks.register(name) {
        dependsOn(taskName)
        outputs.upToDateWhen { false }
        doLast {
            val compiler = tasks.getByName(taskName) as KotlinNativeCompile
            val expectedSources = if (target == null) setOf(commonProbe) else setOf(commonProbe, ohosProbe)
            val actualSources = compiler.sources.files.filter { it.isFile && it.extension == "kt" }.map { it.canonicalFile }.toSet()
            check(actualSources == expectedSources && sha(commonProbe) == commonSha && sha(ohosProbe) == ohosSha)
            check(compiler.enabled && compiler.state.executed && !compiler.state.noSource &&
                compiler.state.skipMessage in listOf(null, "UP-TO-DATE", "FROM-CACHE"))
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
                        text.lineSequence().firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")
                            ?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
                    }
                }
                if (file.invariantSeparatorsPath.contains("/linkdata/") && file.length() > 0) metadata = true
                if (file.invariantSeparatorsPath.contains("/ir/") && file.length() > 0) ir = true
                if (file.invariantSeparatorsPath.endsWith("/default/manifest"))
                    file.readLines().firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")
                        ?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
            }
            check(metadata) { "Consumer compilation produced no metadata payload" }
            if (target != null) check(ir && targets == setOf(target)) { "Consumer Native target/IR differs" }
            evidence("consumer-compilation-$name.json", mapOf("task" to compiler.path, "target" to target,
                "sources" to records(expectedSources), "inputs" to records(compiler.inputs.files.files), "outputs" to records(outputs),
                "libraries" to compiler.libraries.files.sortedBy { it.path }.map { mapOf("path" to it.absolutePath, "files" to records(listOf(it))) },
                "plugins" to records(compiler.compilerPluginClasspath?.files.orEmpty()),
                "publicTrace" to publicTrace(compiler, target), "metadataPayload" to metadata, "irPayload" to ir,
                "nativeTargets" to targets, "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
'''

def canonical_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def expected_compiled_sources(model, inputs, patches):
    # 仅使用固定摘要的来源清单和补丁清单重建编译映射，不能从待验证结果反推期望值。
    if (canonical_digest(model) != SOURCE_MODEL_SHA or canonical_digest(inputs) != SOURCE_INPUTS_SHA or
            canonical_digest(patches) != SOURCE_PATCH_SHA):
        raise RuntimeError("Trusted FileKit source mapping fingerprints differ")
    rows = model["files"]
    if len(rows) != 67 or len({row["forkPath"] for row in rows}) != 67:
        raise RuntimeError("Trusted source map has duplicate or missing fork paths")
    by_original = {}
    for row in rows:
        by_original.setdefault(row["originalPath"], []).append(row)
    mappings = inputs["unmodifiedMappings"]
    overlays = patches["overlays"]
    if (len(mappings) != 35 or len(overlays) != 8 or
            patches["metadataWaiver"] != "NONE_STANDARD_KGP_FIRST"):
        raise RuntimeError("Trusted compiled source mapping counts or policy differ")
    sources, targets, forks = [], set(), set()

    def add(row, destination, kind):
        relative = PurePosixPath(destination)
        if (not destination or relative.is_absolute() or "\\" in destination or
                any(part in ("", ".", "..") for part in relative.parts)):
            raise RuntimeError("Unsafe compiled source path: " + destination)
        value = relative.as_posix()
        parts = relative.parts
        if (value in targets or row["forkPath"] in forks or len(parts) < 3 or
                parts[0] not in MODULES or parts[1] not in (
                    "commonMain", "nonWebMain", "mobileMain", "ohosMain", "ohosX64Main", "ohosArm64Main"
                ) or not value.endswith(".kt")):
            raise RuntimeError("Duplicate or invalid compiled source destination: " + value)
        targets.add(value)
        forks.add(row["forkPath"])
        sources.append({"module": parts[0], "sourceSet": parts[1], "member": "/".join(parts[1:]),
                        "path": "sources/" + value, "forkPath": row["forkPath"],
                        "originalPath": row["originalPath"], "kind": kind,
                        "size": row["bytes"], "sha256": row["sha256"]})

    for item in mappings:
        kind = "abi-handler" if item["rawPath"].startswith("vendor/community/") else "upstream-input"
        matches = [row for row in by_original.get(item["rawPath"], []) if row["category"] == kind]
        if len(matches) != 1:
            raise RuntimeError("Trusted unmodified source mapping differs: " + item["rawPath"])
        add(matches[0], item["compiledPath"], kind)

    for item in overlays:
        matches = [row for row in by_original.get(item["path"], []) if row["category"] == "overlay"]
        patch_rows = [row for row in by_original.get(item["patch"]["path"], []) if row["category"] == "review-patch"]
        if (not item["path"].startswith("overlay/") or len(matches) != 1 or len(patch_rows) != 1 or
                (matches[0]["bytes"], matches[0]["sha256"]) != (item["bytes"], item["sha256"]) or
                patch_rows[0]["sha256"] != item["patch"]["sha256"]):
            raise RuntimeError("Trusted overlay or review patch differs: " + item["path"])
        for base in item["basedOn"]:
            if not any(row["sha256"] == base["sha256"] for row in by_original.get(base["path"], [])):
                raise RuntimeError("Trusted overlay base differs: " + base["path"])
        add(matches[0], item["path"].removeprefix("overlay/"), "overlay")

    abi_expected = {(item["rawPath"], "sources/" + item["compiledPath"])
                    for item in patches["unmodifiedAbiHandlers"]}
    abi_actual = {(row["originalPath"], row["path"]) for row in sources if row["kind"] == "abi-handler"}
    if len(abi_expected) != 2 or abi_actual != abi_expected:
        raise RuntimeError("Trusted ABI handler mappings differ")
    expected_counts = {
        "filekit-core": {"commonMain": 9, "nonWebMain": 8, "ohosMain": 5},
        "filekit-dialogs": {"commonMain": 10, "nonWebMain": 2, "mobileMain": 4,
                            "ohosMain": 3, "ohosX64Main": 1, "ohosArm64Main": 1},
    }
    counts = {module: {name: sum(row["module"] == module and row["sourceSet"] == name for row in sources)
                       for name in expected_counts[module]} for module in MODULES}
    kinds = {kind: sum(row["kind"] == kind for row in sources)
             for kind in ("upstream-input", "abi-handler", "overlay")}
    if len(sources) != 43 or counts != expected_counts or kinds != {
            "upstream-input": 33, "abi-handler": 2, "overlay": 8}:
        raise RuntimeError("Trusted compiled source topology differs")
    return sorted(sources, key=lambda row: row["path"])


def source_jar_declaration(gmm, gmm_url, expected_url, target):
    # root 只引用公共 sources；各 ABI 的 documentation 变体必须引用自己的 sources。
    expected_platform = "common" if target is None else "native"
    variants = [variant for variant in gmm["variants"]
                if variant.get("attributes", {}).get("org.gradle.category") == "documentation" and
                variant.get("attributes", {}).get("org.gradle.docstype") == "sources" and
                variant.get("attributes", {}).get("org.gradle.usage") == "kotlin-runtime" and
                variant.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == expected_platform and
                variant.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target]
    if len(variants) != 1 or len(variants[0].get("files", [])) != 1 or "available-at" in variants[0]:
        raise RuntimeError("FileKit sources documentation variant differs: " + expected_url)
    entry = variants[0]["files"][0]
    if (entry.get("url") != expected_url.rsplit("/", 1)[-1] or
            urljoin(gmm_url, entry["url"]) != expected_url or
            not isinstance(entry.get("size"), int) or entry["size"] <= 0 or
            not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
        raise RuntimeError("FileKit sources GMM path or hash differs: " + expected_url)
    return entry


def expected_source_jar_members(compiled_sources, module, target):
    if module not in MODULES or target not in (None, "ohos_x64", "ohos_arm64"):
        raise RuntimeError("Invalid FileKit sources publication identity")
    source_sets = {"commonMain", "nonWebMain", "mobileMain", "ohosMain"}
    if target == "ohos_x64":
        source_sets.add("ohosX64Main")
    elif target == "ohos_arm64":
        source_sets.add("ohosArm64Main")
    selected = [row for row in compiled_sources if row["module"] == module and row["sourceSet"] in source_sets]
    expected = {row["member"]: (row["size"], row["sha256"]) for row in selected}
    if len(expected) != len(selected) or not expected:
        raise RuntimeError("FileKit sources publication has duplicate or empty members")
    return expected


def verify_source_jar(raw, module, target, manifest_data, provenance):
    # provenance 的完整 43 条映射已由可信输入重建并校验；此处按 KGP publication 选取源集。
    expected = expected_source_jar_members(provenance["compiledSources"], module, target)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [item for item in archive.infolist() if item.filename.endswith(".kt")]
        if len(entries) != len(expected) or len({item.filename for item in entries}) != len(entries):
            raise RuntimeError("FileKit source JAR member count differs: " + module)
        for item in entries:
            identity = expected.get(item.filename)
            if identity is None or item.file_size != identity[0] or digest(archive.read(item)) != identity[1]:
                raise RuntimeError("FileKit source JAR source mapping differs: " + item.filename)
        for kind, identity in LICENSES.items():
            license_data = archive.read("META-INF/licenses/" + kind + "-LICENSE")
            if (len(license_data), digest(license_data)) != identity:
                raise RuntimeError("FileKit source JAR license differs: " + module)
        if archive.read("META-INF/upstream/source-manifest.json") != manifest_data:
            raise RuntimeError("FileKit source JAR source manifest differs")
        compiled = json.loads(archive.read("META-INF/upstream/compiled-source-manifest.json"))
        if compiled != {"schemaVersion": 1, "fingerprint": provenance["fingerprint"],
                        "files": provenance["compiledSources"]}:
            raise RuntimeError("FileKit source JAR compiled source manifest differs")
    return len(expected)


def checked_head(repo, expected, env):
    actual = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
                            check=True, capture_output=True, text=True, env=env).stdout.strip()
    if actual != expected:
        raise RuntimeError("Checkout HEAD differs: " + str(repo))


def check_locked_tools(tools):
    if TOOL_LOCK["revision"] != TOOL_REVISION or len(TOOL_LOCK["files"]) != 20:
        raise RuntimeError("Locked tooling identity differs")
    for row in TOOL_LOCK["files"]:
        path = (tools / row["path"]).resolve()
        if not path.is_relative_to(tools):
            raise RuntimeError("Tooling lock path escapes checkout")
        with path.open("rb") as stream:
            actual = stream_digest(stream)
        if (actual["size"], actual["sha256"]) != (row["size"], row["sha256"]):
            raise RuntimeError("Locked tooling bytes differ: " + row["path"])


def fetch_wrapper(source, output):
    wrapper = output / "wrapper"
    wrapper.mkdir()
    prefix = "https://raw.githubusercontent.com/qsxs/FileKit/" + source + "/ohos/"
    receipts = []
    for relative, expected in WRAPPER.items():
        data, row = read_http(prefix + relative, prefix)
        if (len(data), digest(data)) != expected:
            raise RuntimeError("FileKit wrapper bytes differ: " + relative)
        path = wrapper / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write_new(path, data)
        receipts.append({**row, "path": str(path), "role": "fixed-wrapper"})
    return wrapper, receipts


def fetch_graph(version, source, output):
    evidence = output / "evidence"
    public = evidence / "public"
    public.mkdir()
    downloads = output / "http-data"
    downloads.mkdir()
    pins = dict(BASE_PINS)
    pins.update({GROUP + ":" + module + suffix: version
                 for module in MODULES for suffix in ("", "-ohosx64", "-ohosarm64")})
    requests, cache, metadata = [], {}, {}
    identities = {"sourceManifest": None, "provenance": None, "fingerprint": None}
    native_ids = set()

    def fetch(url, role, label=None, artifact=False):
        public_url(url, PAGES)
        if url not in cache:
            raw, receipt = read_http(url, PAGES)
            cache[url] = (raw, receipt)
            requests.append({**receipt, "role": role})
        raw, receipt = cache[url]
        result = {**receipt, "role": role}
        if label:
            path = public / label
            write_new(path, raw)
            result["evidencePath"] = str(path)
        if artifact:
            path = downloads / (receipt["sha256"] + ".bin")
            if path.exists():
                if path.read_bytes() != raw:
                    raise RuntimeError("Conflicting anonymous artifact hash")
            else:
                write_new(path, raw)
            result["path"] = str(path)
        return raw, result

    def validate_provenance(manifest_data, provenance_data):
        manifest, provenance = json.loads(manifest_data), json.loads(provenance_data)
        fingerprint = manifest.get("fingerprint")
        model = manifest.get("sourceMap")
        if (not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint) or
                manifest.get("sourceCommit") != source or provenance.get("sourceCommit") != source or
                provenance.get("fingerprint") != fingerprint or canonical_digest(model) != SOURCE_MODEL_SHA or
                canonical_digest(provenance.get("sourceInputs")) != SOURCE_INPUTS_SHA or
                canonical_digest(provenance.get("sourcePatch")) != SOURCE_PATCH_SHA):
            raise RuntimeError("Public FileKit source provenance identity differs")
        if any(provenance.get(key) != model.get(key) for key in ("upstream", "community", "originalPort")):
            raise RuntimeError("Public FileKit original source identity differs")
        if (manifest.get("arktsSources") != [{"path": "arkts/FileKitShareFactory.ets", "size": 457, "sha256": ARKTS_SHA}] or
                manifest.get("licenses") != {"upstream": "LICENSE", "community": "ohos/provenance/vendor/community/LICENSE"}):
            raise RuntimeError("Public FileKit sidecar or license source mapping differs")
        expected = expected_compiled_sources(model, provenance["sourceInputs"], provenance["sourcePatch"])
        if provenance.get("compiledSources") != expected:
            raise RuntimeError("Compiled sources differ from the complete trusted FileKit source mapping")
        return manifest, provenance

    def common_companions(base, artifact):
        manifest_data, _ = fetch(base + "-source-manifest.json", "source-manifest", artifact + "-source-manifest.json")
        provenance_data, _ = fetch(base + "-provenance.json", "provenance", artifact + "-provenance.json")
        manifest, provenance = validate_provenance(manifest_data, provenance_data)
        for key, data in (("sourceManifest", manifest_data), ("provenance", provenance_data)):
            if identities[key] is None:
                identities[key] = digest(data)
            elif identities[key] != digest(data):
                raise RuntimeError("Root and leaf public provenance bytes differ")
        if identities["fingerprint"] is None:
            identities["fingerprint"] = manifest["fingerprint"]
        elif identities["fingerprint"] != manifest["fingerprint"]:
            raise RuntimeError("Root and leaf fingerprints differ")
        for kind, expected in LICENSES.items():
            raw, _ = fetch(base + "-" + kind + "-license.txt", "license", artifact + "-" + kind + "-license.txt")
            if (len(raw), digest(raw)) != expected:
                raise RuntimeError("Public FileKit license bytes differ: " + artifact + " " + kind)
        return manifest_data, provenance

    def gmm(url, base_module, artifact):
        raw, _ = fetch(url, "gmm", artifact + ".module")
        value = json.loads(raw)
        if (not isinstance(value, dict) or not value or next(iter(value)) != "formatVersion" or
                not isinstance(value["formatVersion"], str)):
            raise RuntimeError("FileKit GMM formatVersion differs: " + artifact)
        owner = value["component"]
        if (owner.get("group"), owner.get("module"), owner.get("version")) != (GROUP, base_module, version):
            raise RuntimeError("FileKit GMM owner differs: " + artifact)
        return value

    def pom(url, module, artifact, target):
        raw, _ = fetch(url, "pom", artifact + ".pom")
        xml = ET.fromstring(raw)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if any(xml.findtext("m:" + key, namespaces=ns) != expected for key, expected in
               (("groupId", GROUP), ("artifactId", artifact), ("version", version))):
            raise RuntimeError("FileKit POM identity differs: " + artifact)
        if (xml.findtext("m:licenses/m:license/m:name", namespaces=ns) != "MIT License" or
                xml.findtext("m:licenses/m:license/m:url", namespaces=ns) != "https://opensource.org/license/mit/"):
            raise RuntimeError("FileKit POM license differs: " + artifact)
        core_edges = []
        for dependency in xml.findall("m:dependencies/m:dependency", ns):
            group = dependency.findtext("m:groupId", namespaces=ns)
            name = dependency.findtext("m:artifactId", namespaces=ns)
            value = dependency.findtext("m:version", namespaces=ns)
            scope = dependency.findtext("m:scope", namespaces=ns)
            ga = str(group) + ":" + str(name)
            if pins.get(ga) != value or scope not in ("compile", "runtime"):
                raise RuntimeError("FileKit POM dependency differs: " + ga)
            if group == GROUP and name in ("filekit-core", "filekit-core-ohosx64", "filekit-core-ohosarm64"):
                core_edges.append((ga, value, scope))
        if module == "filekit-dialogs":
            suffix = "" if target is None else "-ohosx64" if target == "ohos_x64" else "-ohosarm64"
            expected = (GROUP + ":filekit-core" + suffix, version, "compile" if target else "runtime")
            if core_edges != [expected]:
                raise RuntimeError("FileKit dialogs POM core dependency differs: " + artifact)

    def validate_variants(value, module, target, gmm_url, expected_file):
        matching, artifacts = [], []
        for variant in value["variants"]:
            deps = set()
            for dep in variant.get("dependencies", []):
                ga = dep["group"] + ":" + dep["module"]
                if dep.get("version", {}).get("requires") != pins.get(ga) or ga not in pins:
                    raise RuntimeError("Unpinned FileKit GMM dependency: " + ga)
                deps.add(ga)
            attrs = variant.get("attributes", {})
            selected = ((target is None and attrs.get("org.gradle.usage") == "kotlin-metadata" and
                         attrs.get("org.jetbrains.kotlin.platform.type") == "common") or
                        (target is not None and attrs.get("org.gradle.usage") == "kotlin-api" and
                         attrs.get("org.jetbrains.kotlin.native.target") == target))
            if selected:
                required = REQUIRED_COMMON[module] | (REQUIRED_NATIVE[module] if target else set())
                if not required.issubset(deps):
                    raise RuntimeError("FileKit GMM API dependencies are incomplete: " + module)
            selected_files = []
            for entry in variant.get("files", []):
                base = gmm_url.rsplit("/", 1)[0] + "/"
                url = public_url(urljoin(gmm_url, entry["url"]), base)
                raw, row = fetch(url, "gmm-artifact", artifact=True)
                if (row["size"], row["sha256"]) != (entry.get("size"), entry.get("sha256")) or not row["size"]:
                    raise RuntimeError("FileKit GMM artifact differs: " + url)
                artifacts.append(row)
                if url == base + expected_file:
                    selected_files.append((raw, row))
            if selected:
                if len(selected_files) != 1:
                    raise RuntimeError("FileKit GMM API artifact is missing or ambiguous: " + expected_file)
                matching.extend(selected_files)
        distinct = {row["sha256"]: (raw, row) for raw, row in matching}
        if len(distinct) != 1 or not artifacts:
            raise RuntimeError("FileKit API variant artifact differs: " + expected_file)
        raw, row = next(iter(distinct.values()))
        payload, props = klib_payload(raw)
        if target and (props.get("native_targets", "").split() != [target] or not props.get("unique_name") or
                       not any("/ir/" in name and value["size"] > 0 for name, value in payload.items())):
            raise RuntimeError("FileKit Native target or payload differs")
        if target:
            key = (target, props["unique_name"])
            if key in native_ids:
                raise RuntimeError("Duplicated FileKit Native unique_name")
            native_ids.add(key)
        return row, payload

    def source_jar(gmm, gmm_url, url, module, target, manifest_data, provenance):
        entry = source_jar_declaration(gmm, gmm_url, url, target)
        raw, receipt = fetch(url, "source-jar", artifact=True)
        if (receipt["size"], receipt["sha256"]) != (entry["size"], entry["sha256"]):
            raise RuntimeError("FileKit sources JAR differs from its GMM declaration: " + url)
        count = verify_source_jar(raw, module, target, manifest_data, provenance)
        return {**receipt, "memberCount": count, "target": target, "gmmUrl": gmm_url}

    for module in MODULES:
        root_dir = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/"
        root_base = root_dir + module + "-" + version
        root_url = root_base + ".module"
        root = gmm(root_url, module, module)
        pom(root_base + ".pom", module, module, None)
        manifest_data, provenance = common_companions(root_base, module)
        metadata_artifact, payload = validate_variants(root, module, None, root_url, module + "-" + version + ".jar")
        source_record = source_jar(root, root_url, root_base + "-sources.jar", module, None, manifest_data, provenance)
        native, native_sources, owners = {}, {}, []
        for target, suffix in (("ohos_x64", "-ohosx64"), ("ohos_arm64", "-ohosarm64")):
            artifact = module + suffix
            leaf_dir = PAGES + GROUP.replace(".", "/") + "/" + artifact + "/" + version + "/"
            leaf_base = leaf_dir + artifact + "-" + version
            leaf_url = leaf_base + ".module"
            links = [item["available-at"] for item in root["variants"] if
                     item.get("attributes", {}).get("org.gradle.usage") == "kotlin-api" and
                     item.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and "available-at" in item]
            if not links or any((link.get("group"), link.get("module"), link.get("version")) != (GROUP, artifact, version) or
                                urljoin(root_url, link["url"]) != leaf_url for link in links):
                raise RuntimeError("FileKit root to leaf redirect differs: " + artifact)
            source_links = [item["available-at"] for item in root["variants"] if
                            item.get("attributes", {}).get("org.gradle.category") == "documentation" and
                            item.get("attributes", {}).get("org.gradle.docstype") == "sources" and
                            item.get("attributes", {}).get("org.gradle.usage") == "kotlin-runtime" and
                            item.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and
                            "available-at" in item]
            if (len(source_links) != 1 or
                    (source_links[0].get("group"), source_links[0].get("module"), source_links[0].get("version")) !=
                    (GROUP, artifact, version) or urljoin(root_url, source_links[0]["url"]) != leaf_url):
                raise RuntimeError("FileKit root sources to leaf redirect differs: " + artifact)
            leaf = gmm(leaf_url, module, artifact)
            if urljoin(leaf_url, leaf["component"].get("url", "")) != root_url:
                raise RuntimeError("FileKit leaf owner URL differs: " + artifact)
            pom(leaf_base + ".pom", module, artifact, target)
            common_companions(leaf_base, artifact)
            record, _ = validate_variants(leaf, module, target, leaf_url, artifact + "-" + version + ".klib")
            native[target] = [record]
            native_sources[target] = source_jar(leaf, leaf_url, leaf_base + "-sources.jar", module, target,
                                                manifest_data, provenance)
            owners.append({"target": target, "rootUrl": root_url, "leafUrl": leaf_url})
        metadata[module] = {"rootUrl": root_url, "metadataArtifacts": [metadata_artifact], "metadataPayload": payload,
                            "nativeArtifacts": native, "owners": owners, "sourceJar": source_record,
                            "nativeSourceJars": native_sources}

    arkts_url = (PAGES + GROUP.replace(".", "/") + "/filekit-dialogs/" + version +
                 "/filekit-dialogs-" + version + "-arkts-sources.zip")
    raw, arkts_receipt = fetch(arkts_url, "arkts-source-zip", artifact=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if (len(entries) != 1 or entries[0].filename != "FileKitShareFactory.ets" or entries[0].is_dir() or
                entries[0].file_size != 457 or ((entries[0].external_attr >> 16) & 0o170000) not in (0, 0o100000)):
            raise RuntimeError("ArkTS source archive must contain exactly one regular member")
        data = archive.read(entries[0])
    source_text = data.decode("utf-8")
    if (digest(data) != ARKTS_SHA or "import { systemShare } from '@kit.ShareKit';" not in source_text or
            "createSharedData(record: systemShare.SharedRecord): systemShare.SharedData" not in source_text or
            "createShareController(data: systemShare.SharedData): systemShare.ShareController" not in source_text):
        raise RuntimeError("ArkTS factory source identity or methods differ")
    return {
        "status": "ANONYMOUS_PUBLIC_GRAPH_VERIFIED",
        "sourceCommit": source, "version": version, "fingerprint": identities["fingerprint"],
        "provenanceSha256": identities["provenance"], "sourceManifestSha256": identities["sourceManifest"],
        "modules": metadata, "requests": requests, "arkts": {**arkts_receipt, "memberSha256": digest(data),
            "type": "SOURCE_NOT_COMPILED", "requiredMethods": ["createSharedData", "createShareController"]},
        "licenseSha256": {key: value[1] for key, value in LICENSES.items()},
        "librarySourcesUsedAsCompilationInput": False, "consumerEnvironmentDependencies": list(ENVIRONMENT_DEPS),
        "consumerEnvironmentDependencyPurpose": ENVIRONMENT_DEPENDENCY_PURPOSE,
        "filekitCoreResolution": "DIALOGS_API_TRANSITIVE_REQUIRED",
    }

def verify_compilations(output):
    evidence = output / "evidence"
    resolution = json.loads((evidence / "consumer-resolution.json").read_text(encoding="utf-8"))
    if len(resolution.get("configurations", [])) != 3:
        raise RuntimeError("Consumer resolution evidence is incomplete")
    results = []
    for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"),
                         ("recordConsumerArm64", "ohos_arm64")):
        path = evidence / ("consumer-compilation-" + name + ".json")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("target") != target or len(value.get("sources", [])) != (1 if target is None else 2) or
                not value.get("metadataPayload") or not value.get("outputs") or
                set(value.get("publicTrace", {})) != set(MODULES)):
            raise RuntimeError("Consumer compile proof is incomplete: " + name)
        if target and (not value.get("irPayload") or set(value.get("nativeTargets", [])) != {target}):
            raise RuntimeError("Consumer Native target or IR proof differs: " + name)
        for item in [*value["sources"], *value["outputs"]]:
            file = Path(item["path"])
            with file.open("rb") as stream:
                actual = stream_digest(stream)
            if (actual["size"], actual["sha256"]) != (item["size"], item["sha256"]):
                raise RuntimeError("Consumer compile source or output changed: " + item["path"])
        results.append({"stage": name, "target": target, "evidencePath": str(path), "sha256": digest(path.read_bytes())})
    write_json_new(evidence / "consumer-compilation.json", {
        "status": "METADATA_AND_DUAL_ABI_CONSUMER_COMPILED",
        "gradleVersion": "8.11.1", "compilations": results,
        "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN", "arktsCompilation": "NOT_RUN",
    })


def main():
    output = Path(os.environ["FILEKIT_CONSUMER_OUTPUT"]).resolve()
    tools = Path(os.environ["FILEKIT_LOCKED_TOOLS"]).resolve()
    evidence = output / "evidence"
    state = {
        "status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP,
        "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN",
        "armDevice": "NOT_RUN", "arktsCompilation": "NOT_RUN", "stages": [],
    }
    failed = None
    index = []
    try:
        source = os.environ["FILEKIT_SOURCE_SHA"]
        version = os.environ["FILEKIT_VERSION"]
        workflow = os.environ["CI_TOOLING_SHA"]
        run_id = os.environ["CI_RUN_ID"]
        attempt = os.environ["CI_RUN_ATTEMPT"]
        if (not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or
                not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt) or
                not re.fullmatch(r"0\.16\.0-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version)):
            raise RuntimeError("FileKit version must match the full source SHA and producer run identity")
        if (output.parent != Path(os.environ["RUNNER_TEMP"]).resolve() or
                output.name != "filekit-consumer-" + run_id + "-" + attempt or
                not evidence.is_dir() or not (evidence / "workflow-context.txt").is_file()):
            raise RuntimeError("Fresh isolated runner output is required")
        if any((output / name).exists() for name in ("project", "wrapper", "http-data", "logs", "native-bootstrap", "scratch")):
            raise RuntimeError("Consumer output already exists")
        if any((evidence / name).exists() for name in ("run.json", "public-manifest.json", "evidence-index.json")):
            raise RuntimeError("Consumer evidence already exists")
        if sys.version_info[:2] != (3, 13):
            raise RuntimeError("Python 3.13 is required")
        if any(repo == output or repo.is_relative_to(output) or output.is_relative_to(repo) for repo in (ROOT, tools)):
            raise RuntimeError("Consumer checkouts and runner output must be separate")
        state.update(sourceCommit=source, version=version, workflowToolingCommit=workflow,
                     runtimeToolingCommit=TOOL_REVISION, runId=run_id, runAttempt=attempt,
                     pythonVersion=sys.version, kotlinVersion=KOTLIN_VERSION, gradleVersion="8.11.1",
                     librarySourcesUsedAsCompilationInput=False, consumerEnvironmentDependencies=list(ENVIRONMENT_DEPS),
                     consumerEnvironmentDependencyPurpose=ENVIRONMENT_DEPENDENCY_PURPOSE,
                     filekitCoreResolution="DIALOGS_API_TRANSITIVE_REQUIRED")
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
        checked_head(ROOT, workflow, env)
        checked_head(tools, TOOL_REVISION, env)
        check_locked_tools(tools)
        logs = output / "logs"
        logs.mkdir()

        def run(stage, argv):
            state["stage"] = stage
            entry = {"stage": stage, "started": time.time()}
            state["stages"].append(entry)
            stdout, stderr = logs / (stage + ".stdout.log"), logs / (stage + ".stderr.log")
            print("Running FileKit consumer " + stage, flush=True)
            try:
                with stdout.open("xb") as out, stderr.open("xb") as err:
                    result = subprocess.run(argv, env=env, cwd=output, stdout=out, stderr=err, check=False)
                entry["exitCode"] = result.returncode
                if result.returncode:
                    raise RuntimeError(stage + " failed with exit " + str(result.returncode))
                return stdout.read_text(encoding="utf-8").strip()
            except Exception as error:
                entry["error"] = str(error)
                raise
            finally:
                entry["finished"] = time.time()

        run("JavaVersion", [str(Path(env["JAVA_HOME"]) / "bin/java"), "-version"])
        if not re.search(r'version "17(?:[.+"]|$)', (logs / "JavaVersion.stderr.log").read_text(encoding="utf-8")):
            raise RuntimeError("JDK 17 is required")
        state["stage"] = "AnonymousHTTP"
        public = fetch_graph(version, source, output)
        write_json_new(evidence / "public-manifest.json", public)
        state["fingerprint"] = public["fingerprint"]
        state["stage"] = "FixedWrapper"
        wrapper, wrapper_receipts = fetch_wrapper(source, output)
        write_json_new(evidence / "wrapper-downloads.json", {"sourceCommit": source, "files": wrapper_receipts})
        native_output = run("BootstrapNative", [
            sys.executable, "-B", str(tools / TOOL_DIR / "bootstrap-native.py"),
            "--destination", str(output / "native-bootstrap"), "--kotlin-version", KOTLIN_VERSION,
        ])
        native = Path(native_output).resolve()
        bootstrap = output / "native-bootstrap"
        receipt_path = bootstrap / "bootstrap-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        bundle = json.loads((tools / TOOL_DIR / "bootstrap-linux.json").read_text(encoding="utf-8"))["nativeBundle"]
        archive = bootstrap / (bundle["directory"] + ".tar.gz")
        with archive.open("rb") as stream:
            bundle_identity = stream_digest(stream)
        if (native.parent != bootstrap or native.name != bundle["directory"] or not native.is_dir() or
                Path(receipt["nativeHome"]).resolve() != native or receipt["compilerVersion"] != KOTLIN_VERSION or
                (bundle_identity["size"], bundle_identity["sha256"]) != (bundle["bytes"], bundle["sha256"]) or
                (receipt["bytes"], receipt["sha256"]) != (bundle["bytes"], bundle["sha256"])):
            raise RuntimeError("Native bootstrap bundle or receipt differs")
        write_new(evidence / "bootstrap-receipt.json", receipt_path.read_bytes())
        project = output / "project"
        project.mkdir()
        source_files = {
            "settings.gradle.kts": SETTINGS,
            "build.gradle.kts": BUILD,
            "gradle.properties": PROPERTIES,
            "src/commonMain/kotlin/FileKitCommonProbe.kt": COMMON_PROBE,
            "src/ohosMain/kotlin/FileKitOhosProbe.kt": OHOS_PROBE,
        }
        for name, contents in source_files.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_new(path, contents.encode("utf-8"))
        pins = dict(BASE_PINS)
        pins.update({GROUP + ":" + module + suffix: version
                     for module in MODULES for suffix in ("", "-ohosx64", "-ohosarm64")})
        pins_path = project / "pins.json"
        write_json_new(pins_path, pins)
        write_json_new(evidence / "consumer-inputs.json", {
            "files": [{"path": str(project / name), "sha256": digest(contents.encode("utf-8")),
                       "size": len(contents.encode("utf-8"))} for name, contents in source_files.items()],
            "pins": pins, "wrapper": wrapper_receipts, "toolRevision": TOOL_REVISION,
            "librarySourcesUsedAsCompilationInput": False,
            "consumerEnvironmentDependencies": list(ENVIRONMENT_DEPS),
            "consumerEnvironmentDependencyPurpose": ENVIRONMENT_DEPENDENCY_PURPOSE,
            "filekitCoreResolution": "DIALOGS_API_TRANSITIVE_REQUIRED",
        })
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace",
                "--project-cache-dir", str(output / "project-cache"),
                "-PconsumerOutput=" + str(output), "-PconsumerEvidence=" + str(evidence),
                "-PconsumerTools=" + str(tools / TOOL_DIR), "-PconsumerHttp=" + str(evidence / "public-manifest.json"),
                "-PconsumerPins=" + str(pins_path), "-PfilekitVersion=" + version,
                "-PcommonProbeSha=" + digest(COMMON_PROBE.encode("utf-8")),
                "-PohosProbeSha=" + digest(OHOS_PROBE.encode("utf-8")),
                "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, "-PconsumerStage=" + stage, *TASKS[stage]])
            if stage == "Tasks":
                discovered = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED_TASKS.issubset(discovered):
                    raise RuntimeError("Consumer tasks are absent from actual discovery")
                write_json_new(evidence / "task-discovery.json", {"required": sorted(REQUIRED_TASKS),
                                                                    "stdoutSha256": digest((logs / "Tasks.stdout.log").read_bytes())})
        state["stage"] = "VerifyCompilations"
        verify_compilations(output)
        state["status"] = "ANONYMOUS_PUBLIC_CONSUMER_COMPILED"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        try:
            files = [path for path in evidence.rglob("*") if path.is_file()]
            log_files = [path for stage in ("JavaVersion", "BootstrapNative", *STAGES)
                         for stream in ("stdout", "stderr")
                         for path in (output / "logs" / (stage + "." + stream + ".log"),) if path.is_file()]
            if len(files) + len(log_files) + 2 > 96 or any(path.stat().st_size > 8 * 1024 * 1024 for path in files):
                raise RuntimeError("Consumer structured evidence exceeds file-count or size limit")
            total = sum(path.stat().st_size for path in files)
            if total > 128 * 1024 * 1024:
                raise RuntimeError("Consumer structured evidence exceeds total limit")
            for path in log_files:
                total = collect_file(path, evidence, path.name, index, total)
            write_json_new(evidence / "evidence-index.json", {"schemaVersion": 1, "files": index})
        except Exception as error:
            state["evidenceError"] = str(error)
            if failed is None:
                failed = error
                state["status"] = "FAILED_EVIDENCE_COLLECTION"
        state["finished"] = time.time()
        try:
            publish_run_evidence(output, evidence, state)
        except Exception as error:
            state["status"] = "FAILED_EVIDENCE_COLLECTION"
            state["finalEvidenceError"] = str(error)
            if failed is None:
                failed = error
            print("Final consumer evidence write failed: " + str(error), file=sys.stderr)
    if failed is not None:
        print("Consumer failure: " + str(failed), file=sys.stderr)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
