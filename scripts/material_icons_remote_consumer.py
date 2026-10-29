"""匿名 Pages Material Icons 消费者；不访问 producer、本地 Maven 或库源码。"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from colormath_remote_consumer import fetch_tools
from filekit_producer import check_head, collect_file, publish_run_evidence, write_json_new
from grid_remote_consumer import digest, public_url, read_http
from materialkolor_remote_consumer import PINS, METADATA_PINS

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.materialicons"
MODULES = ("material-icons-core", "material-icons-extended")
TARGETS = (("-ohosx64", "ohos_x64"), ("-ohosarm64", "ohos_arm64"))
TOOL_REVISION = "d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285"
TOOL_DIR = "toolchains/kotlin-native/2.4.20-0.1.0-08"
STAGES = ("Tasks", "Resolve", "Metadata", "NativeX64", "NativeArm64")
TASKS = {"Tasks": ["tasks", "--all"], "Resolve": ["resolveConsumer"],
         "Metadata": ["recordConsumerMetadata"], "NativeX64": ["recordConsumerX64"],
         "NativeArm64": ["recordConsumerArm64"]}
REQUIRED = {"resolveConsumer", "compileCommonMainKotlinMetadata", "compileKotlinOhosX64",
            "compileKotlinOhosArm64", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"}

PROBE = r'''package acceptance

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.ui.graphics.vector.ImageVector

fun icons(): List<ImageVector> = listOf(
    Icons.Filled.ArrowBack, Icons.Filled.ArrowForward,
    Icons.Filled.CalendarMonth, Icons.Filled.AccountBalanceWallet,
)
'''

SETTINGS = r'''import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/")
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/")
        gradlePluginPortal()
        mavenCentral()
    }
    plugins { id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08" }
}
val metadataPins = JsonSlurper().parse(file("metadata-pins.json")) as Map<*, *>
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven { name = "MaterialIconsPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.materialicons") }
        }
        google { content { metadataPins.forEach { (ga, version) ->
            val parts = ga.toString().split(":")
            if (parts[0].startsWith("androidx.")) includeVersion(parts[0], parts[1], version.toString())
        } } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.materialicons") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.materialicons") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.materialicons") } }
    }
}
rootProject.name = "material-icons-pages-consumer"
'''

PROPERTIES = r'''org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8
org.gradle.workers.max=2
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
fun readMap(file: File) = (JsonSlurper().parse(file) as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun asMap(value: Any?) = (value as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun digest(input: java.io.InputStream): String {
    val hash = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(65536)
    while (true) { val count = input.read(buffer); if (count < 0) break; hash.update(buffer, 0, count) }
    return hash.digest().joinToString("") { "%02x".format(it) }
}
fun sha(file: File) = file.inputStream().use(::digest)
fun leaves(file: File): List<File> = if (file.isDirectory) file.walkTopDown().filter(File::isFile).toList()
    else if (file.isFile) listOf(file) else emptyList()
fun records(files: Iterable<File>) = files.flatMap(::leaves).distinct().sortedBy { it.path }.map {
    mapOf("path" to it.absolutePath, "size" to it.length(), "sha256" to sha(it))
}
val groupName = "io.github.qsxs.cpf.materialicons"
val versionName = providers.gradleProperty("iconsVersion").get()
val output = file(providers.gradleProperty("consumerOutput").get())
val evidenceDir = file(providers.gradleProperty("consumerEvidence").get())
val publicGraph = readMap(file(providers.gradleProperty("consumerHttp").get()))
val pins = readMap(file("pins.json"))
val metadataPins = readMap(file("metadata-pins.json"))
val toolDir = file(providers.gradleProperty("consumerTools").get())
val metadataTools = readMap(toolDir.resolve("metadata-toolchain.json"))
val commonizer = readMap(toolDir.resolve("commonizer-toolchain.json"))
val host = readMap(toolDir.resolve("native-compiler-toolchain.json"))
val hostPins = asMap(host.getValue("pins"))
val commonizerPins = asMap(metadataTools.getValue("launcherPins")) + asMap(commonizer.getValue("pins"))
val probe = file("src/commonMain/kotlin/IconsConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val modules = listOf("material-icons-core", "material-icons-extended")
layout.buildDirectory.set(output.resolve("build"))

kotlin {
    ohosX64()
    ohosArm64()
    sourceSets {
        val commonMain by getting {
            kotlin.setSrcDirs(listOf(file("src/commonMain/kotlin")))
            dependencies { implementation("$groupName:material-icons-extended:$versionName") }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
configurations.configureEach {
    if (name == host["configuration"] || name == commonizer["configuration"]) {
        val fixed = if (name == host["configuration"]) hostPins else commonizerPins
        resolutionStrategy.eachDependency {
            val ga = "${requested.group}:${requested.name}"
            val expected = fixed[ga]?.toString() ?: error("Unpinned compiler tool: $ga")
            if (requested.version != expected) useVersion(expected)
        }
    }
    val metadata = name.endsWith("ResolvableDependenciesMetadata") || name == "allSourceSetsCompileDependenciesMetadata"
    val library = metadata || name.endsWith("CompileKlibraries") || name.endsWith("CompilationDependenciesMetadata")
    if (library && !name.contains("Test", ignoreCase = true)) resolutionStrategy.eachDependency {
        val ga = "${requested.group}:${requested.name}"
        if (requested.group == groupName) {
            check(requested.version == versionName && requested.name in modules.flatMap { listOf(it, "$it-ohosx64", "$it-ohosarm64") })
        } else {
            val expected = (if (metadata) metadataPins[ga] ?: pins[ga] else pins[ga])?.toString()
                ?: error("Unpinned consumer dependency: $ga")
            if (requested.version != expected) useVersion(expected)
        }
    }
}
fun evidence(name: String, value: Any) {
    val path = evidenceDir.resolve(name)
    check(!path.exists()) { "Consumer evidence already exists: $name" }
    path.writeText(JsonOutput.prettyPrint(JsonOutput.toJson(value)) + "\n")
}
fun edges(configuration: Configuration) = configuration.incoming.resolutionResult.allDependencies.map { edge ->
    if (edge !is ResolvedDependencyResult) throw GradleException("Unresolved dependency: $edge", (edge as? UnresolvedDependencyResult)?.failure)
    mapOf("from" to edge.from.id.displayName, "requested" to edge.requested.displayName, "selected" to edge.selected.id.displayName)
}
fun payload(file: File): Map<String, Map<String, Any>> {
    val result = mutableMapOf<String, Map<String, Any>>()
    fun add(name: String, size: Long, hash: String) {
        val normalized = name.removePrefix("commonMain/")
        if (normalized.startsWith("default/")) result[normalized] = mapOf("size" to size, "sha256" to hash)
    }
    if (file.isDirectory) leaves(file).forEach { add(it.relativeTo(file).invariantSeparatorsPath, it.length(), sha(it)) }
    else if (file.isFile && file.extension in listOf("klib", "jar", "bin")) ZipFile(file).use { zip ->
        zip.entries().asSequence().filter { !it.isDirectory }.forEach { item ->
            val name = item.name.removePrefix("commonMain/")
            if (name.startsWith("default/")) zip.getInputStream(item).use { add(item.name, item.size, digest(it)) }
        }
    }
    return result
}
fun nativeTarget(file: File): Set<String> {
    val text = if (file.isDirectory) file.resolve("default/manifest").readText()
        else ZipFile(file).use { zip -> zip.getInputStream(zip.getEntry("default/manifest") ?: error("KLIB manifest absent"))
            .bufferedReader().use { it.readText() } }
    return text.lineSequence().firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")
        ?.split(" ")?.filter(String::isNotBlank)?.toSet() ?: emptySet()
}
fun selected(configurationName: String, target: String?): Map<String, File> {
    val configuration = configurations.getByName(configurationName)
    val declared = asMap(publicGraph.getValue("artifacts"))
    val found = mutableMapOf<String, File>()
    val artifactRows = mutableListOf<Map<String, Any?>>()
    configuration.incoming.artifacts.artifacts.forEach { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier) { "Consumer selected non-module artifact: $id" }
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        if (id.group == groupName) {
            val module = modules.singleOrNull { id.module in listOf(it, "$it-ohosx64", "$it-ohosarm64") }
                ?: error("Unexpected Material Icons component: $id")
            check(id.version == versionName && module !in found)
            val item = asMap(asMap(declared.getValue(module)).getValue(target ?: "common"))
            val expectedModule = if (target == null) module else module + if (target == "ohos_x64") "-ohosx64" else "-ohosarm64"
            check(id.module in listOf(module, expectedModule) && artifact.file.length() == (item.getValue("size") as Number).toLong() &&
                sha(artifact.file) == item["sha256"]) { "Gradle selected bytes unlike public GMM: $id" }
            if (target == null) check(attrs["org.gradle.usage"] == "kotlin-metadata" && attrs["org.jetbrains.kotlin.platform.type"] == "common")
            else check(attrs["org.gradle.usage"] == "kotlin-api" && attrs["org.jetbrains.kotlin.native.target"] == target &&
                nativeTarget(artifact.file) == setOf(target)) { "Gradle selected the wrong KLIB target: $id" }
            found[module] = artifact.file
            artifactRows.add(mapOf("component" to id.displayName, "attributes" to attrs,
                "file" to records(listOf(artifact.file)).single(), "nativeTarget" to target))
        }
    }
    check(found.keys == modules.toSet()) { "Incomplete Material Icons graph: $configurationName $found" }
    val graph = edges(configuration)
    val extended = "$groupName:material-icons-extended:$versionName"
    check(graph.any { it["requested"] == extended }) { "Extended root dependency absent" }
    check(graph.any {
        it["from"].toString().startsWith("$groupName:material-icons-extended") &&
            it["requested"].toString() in listOf("$groupName:material-icons-core:$versionName",
                "$groupName:material-icons-core-ohosx64:$versionName", "$groupName:material-icons-core-ohosarm64:$versionName")
    }) { "Extended API edge to same-version core absent" }
    evidence("resolution-$configurationName.json", mapOf("configuration" to configurationName,
        "target" to target, "edges" to graph, "artifacts" to artifactRows))
    return found
}
fun trace(compiler: KotlinNativeCompile, configurationName: String, target: String?): Map<String, Any> {
    val configuration = configurations.getByName(configurationName)
    val selected = configuration.incoming.artifacts.artifacts.filter {
        val id = it.id.componentIdentifier
        id is ModuleComponentIdentifier && id.group == groupName
    }
    val libraries = compiler.libraries.files
    return modules.associateWith { module ->
        val artifact = selected.single {
            val id = it.id.componentIdentifier as ModuleComponentIdentifier
            id.module in listOf(module, "$module-ohosx64", "$module-ohosarm64")
        }.file
        val expected = payload(artifact)
        check(expected.isNotEmpty() && expected.keys.any { it.contains("/linkdata/") }) { "Selected artifact lacks metadata: $module" }
        if (target != null) check(expected.keys.any { it.contains("/ir/") } && nativeTarget(artifact) == setOf(target))
        val direct = libraries.filter { it.canonicalFile == artifact.canonicalFile }
        val matches = if (direct.isNotEmpty()) direct else libraries.filter { payload(it) == expected }
        check(matches.size == 1) { "Compiler libraries do not trace uniquely to selected public $module: $target" }
        mapOf("selected" to records(listOf(artifact)).single(), "compilerLibrary" to matches.single().absolutePath,
            "payloadFiles" to expected.size, "target" to target)
    }
}
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0" && System.getProperty("java.specification.version") == "17")
        val direct = configurations.getByName("commonMainImplementation").dependencies.filter { it.group == groupName }
        check(direct.size == 1 && direct.single().name == "material-icons-extended" && direct.single().version == versionName)
        selected("commonMainResolvableDependenciesMetadata", null)
        selected("ohosX64CompileKlibraries", "ohos_x64")
        selected("ohosArm64CompileKlibraries", "ohos_arm64")
        evidence("consumer-resolution.json", mapOf("direct" to "$groupName:material-icons-extended:$versionName",
            "core" to "EXTENDED_API_TRANSITIVE_REQUIRED", "source" to records(listOf(probe)),
            "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
    }
}
fun recordCompilation(name: String, taskName: String, configurationName: String, target: String?) {
    tasks.register(name) {
        dependsOn(taskName)
        outputs.upToDateWhen { false }
        doLast {
            val compiler = tasks.getByName(taskName) as KotlinNativeCompile
            val sources = compiler.sources.files.filter { it.isFile && it.extension == "kt" }.map { it.canonicalFile }.toSet()
            check(sources == setOf(probe) && sha(probe) == probeSha)
            check(compiler.enabled && compiler.state.executed && !compiler.state.noSource && compiler.state.failure == null &&
                compiler.state.skipMessage in listOf(null, "UP-TO-DATE", "FROM-CACHE"))
            val outputs = compiler.outputs.files.files.flatMap(::leaves).distinct()
            check(outputs.any { it.length() > 0 })
            var metadata = false
            var ir = false
            val targets = mutableSetOf<String>()
            outputs.forEach { path ->
                if (path.extension in listOf("klib", "jar")) ZipFile(path).use { zip ->
                    val entries = zip.entries().asSequence().toList()
                    metadata = metadata || entries.any { it.name.contains("/linkdata/") && it.size > 0 }
                    ir = ir || entries.any { it.name.contains("/ir/") && it.size > 0 }
                    zip.getEntry("default/manifest")?.let { entry ->
                        zip.getInputStream(entry).bufferedReader().useLines { lines ->
                            lines.firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")
                                ?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
                        }
                    }
                }
                if (path.invariantSeparatorsPath.contains("/linkdata/") && path.length() > 0) metadata = true
                if (path.invariantSeparatorsPath.contains("/ir/") && path.length() > 0) ir = true
                if (path.invariantSeparatorsPath.endsWith("/default/manifest")) path.readLines()
                    .firstOrNull { it.startsWith("native_targets=") }?.substringAfter("=")
                    ?.split(" ")?.filter(String::isNotBlank)?.let(targets::addAll)
            }
            check(metadata && (target == null || (ir && targets == setOf(target))))
            evidence("consumer-compilation-$name.json", mapOf("task" to compiler.path, "target" to target,
                "sources" to records(sources), "outputs" to records(outputs), "publicTrace" to trace(compiler, configurationName, target),
                "metadataPayload" to metadata, "irPayload" to ir, "nativeTargets" to targets,
                "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", "commonMainResolvableDependenciesMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohosX64CompileKlibraries", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohosArm64CompileKlibraries", "ohos_arm64")
'''


def anonymous(url):
    data, receipt = read_http(public_url(url, PAGES), PAGES)
    if len(data) > 4 * 1024 * 1024:
        raise RuntimeError("Public metadata exceeds the small-file limit")
    return data, receipt


def fetch_graph(version, source, evidence=None):
    requests = []

    def get(url):
        data, receipt = anonymous(url)
        requests.append(receipt)
        if evidence is not None:
            (evidence / "public-http-progress.json").write_text(
                json.dumps({"requests": requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data

    artifacts = {}
    fingerprint = None
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    for module in MODULES:
        artifacts[module] = {}
        directory = PAGES + GROUP.replace(".", "/") + "/" + module + "/" + version + "/"
        prefix = module + "-" + version
        raw = get(directory + prefix + "-build-provenance.json")
        provenance = json.loads(raw)
        if (provenance.get("sourceCommit") != source or provenance.get("version") != version or
                provenance.get("group") != GROUP or provenance.get("toolingCommit") != TOOL_REVISION or
                not re.fullmatch(r"[0-9a-f]{64}", provenance.get("fingerprint", ""))):
            raise RuntimeError("Published full source or build provenance differs: " + module)
        counts = provenance.get("sources", {})
        if any(counts.get(name, {}).get("count") != count for name, count in
               (("material-icons-core", 281), ("material-icons-extended", 11105))):
            raise RuntimeError("Published source inventory differs")
        if fingerprint is None:
            fingerprint = provenance["fingerprint"]
        elif fingerprint != provenance["fingerprint"]:
            raise RuntimeError("Published module fingerprints differ")
        raw = get(directory + prefix + ".module")
        root = json.loads(raw)
        for suffix, target in (("", None), *TARGETS):
            name = module + suffix
            leaf_dir = PAGES + GROUP.replace(".", "/") + "/" + name + "/" + version + "/"
            gmm_url = leaf_dir + name + "-" + version + ".module"
            if target is None:
                gmm = root
            else:
                raw = get(gmm_url)
                gmm = json.loads(raw)
                links = [row["available-at"] for row in root["variants"] if
                         row.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target and "available-at" in row]
                if not links or any(link.get("group") != GROUP or link.get("module") != name or
                        link.get("version") != version or urljoin(directory, link["url"]) != gmm_url for link in links):
                    raise RuntimeError("Public root target link differs: " + name)
                if urljoin(leaf_dir, gmm["component"].get("url", "")) != directory + prefix + ".module":
                    raise RuntimeError("Public leaf owner URL differs: " + name)
            if any(gmm["component"].get(key) != value for key, value in
                   (("group", GROUP), ("module", module), ("version", version))):
                raise RuntimeError("Public GMM component differs: " + name)
            variants = [row for row in gmm["variants"] if
                (row.get("attributes", {}).get("org.gradle.usage") == ("kotlin-api" if target else "kotlin-metadata") and
                 row.get("attributes", {}).get("org.jetbrains.kotlin.platform.type") == ("native" if target else "common") and
                 row.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target)]
            if not variants:
                raise RuntimeError("Public API variant missing: " + name)
            extension = ".klib" if target else ".jar"
            classifier = {None: "metadata", "ohos_x64": "ohosX64Main", "ohos_arm64": "ohosArm64Main"}[target]
            expected_name = module + "-" + classifier + "-" + version + extension
            expected_file = name + "-" + version + extension
            if any(not isinstance(row.get("files"), list) or len(row["files"]) != 1 for row in variants):
                raise RuntimeError("Public API variant must declare exactly one artifact: " + name)
            files = [row["files"][0] for row in variants]
            if (any(not isinstance(item, dict) or item.get("name") != expected_name for item in files) or
                    any(item != files[0] for item in files) or
                    not re.fullmatch(r"[0-9a-f]{64}", files[0].get("sha256", "")) or
                    not isinstance(files[0].get("size"), int) or files[0]["size"] <= 0 or
                    files[0].get("url") != expected_file):
                raise RuntimeError("Public API artifact declaration differs: " + name)
            if module == "material-icons-extended" and not all(any(
                    dep.get("group") == GROUP and dep.get("module") in ("material-icons-core", "material-icons-core" + suffix) and
                    dep.get("version", {}).get("requires") == version for dep in row.get("dependencies", [])) for row in variants):
                raise RuntimeError("Public extended API edge to same-version core missing: " + name)
            artifacts[module][target or "common"] = {"url": leaf_dir + expected_file,
                "size": files[0]["size"], "sha256": files[0]["sha256"]}
            raw = get(leaf_dir + name + "-" + version + ".pom")
            pom = ET.fromstring(raw)
            if any(pom.findtext("m:" + key, namespaces=ns) != value for key, value in
                   (("groupId", GROUP), ("artifactId", name), ("version", version))):
                raise RuntimeError("Public POM identity differs: " + name)
            if module == "material-icons-extended":
                dependencies = pom.findall("m:dependencies/m:dependency", ns)
                if not any(dep.findtext("m:groupId", namespaces=ns) == GROUP and
                           dep.findtext("m:artifactId", namespaces=ns) == "material-icons-core" + suffix and
                           dep.findtext("m:version", namespaces=ns) == version and
                           dep.findtext("m:scope", namespaces=ns) == ("compile" if target else "runtime") for dep in dependencies):
                    raise RuntimeError("Public POM core edge differs: " + name)
    return {"status": "ANONYMOUS_SMALL_METADATA_VERIFIED", "sourceCommit": source, "version": version,
            "fingerprint": fingerprint, "group": GROUP, "artifacts": artifacts, "requests": requests,
            "klibsPrefetched": False, "librarySourcesDownloaded": False}


def main():
    output = Path(os.environ["ICONS_CONSUMER_OUTPUT"]).resolve()
    evidence = output / "evidence"
    state = {"status": "STARTED", "started": time.time(), "pages": PAGES, "group": GROUP,
             "link": "NOT_RUN", "runtime": "NOT_RUN", "device": "NOT_RUN", "androidIosRegression": "NOT_RUN", "stages": []}
    failed, index = None, []
    try:
        source, version, workflow = os.environ["ICONS_SOURCE_SHA"], os.environ["ICONS_VERSION"], os.environ["CI_TOOLING_SHA"]
        run_id, attempt = os.environ["CI_RUN_ID"], os.environ["CI_RUN_ATTEMPT"]
        if (not re.fullmatch(r"[0-9a-f]{40}", source) or not re.fullmatch(r"[0-9a-f]{40}", workflow) or
                not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt) or
                not re.fullmatch(r"1\.7\.3-cpf11-preview-" + source[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version)):
            raise RuntimeError("Full source SHA and matching published version are required")
        if (output.parent != Path(os.environ["RUNNER_TEMP"]).resolve() or
                output.name != "material-icons-consumer-" + run_id + "-" + attempt or
                not evidence.is_dir() or not (evidence / "workflow-context.txt").is_file() or
                any((output / name).exists() for name in ("project", "wrapper", "shared-tools", "logs", "native-bootstrap", "scratch"))):
            raise RuntimeError("Fresh isolated runner output is required")
        if sys.version_info[:2] != (3, 13):
            raise RuntimeError("Python 3.13 is required")
        if ROOT == output or ROOT.is_relative_to(output) or output.is_relative_to(ROOT):
            raise RuntimeError("Tooling and consumer output must be separate")
        state.update(sourceCommit=source, version=version, workflowToolingCommit=workflow,
                     runtimeToolingCommit=TOOL_REVISION, runId=run_id, runAttempt=attempt,
                     pythonVersion=sys.version, kotlinVersion="2.4.20-0.1.0-08", gradleVersion="9.5.0",
                     librarySourcesUsedAsCompilationInput=False, klibsPrefetched=False)
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
        check_head(ROOT, workflow, env)
        logs = output / "logs"
        logs.mkdir()

        def run(stage, argv):
            state["stage"] = stage
            item = {"stage": stage, "argv": argv, "started": time.time(), "exitCode": None}
            state["stages"].append(item)
            print("Running Material Icons consumer " + stage, flush=True)
            try:
                with (logs / (stage + ".stdout.log")).open("xb") as out, (logs / (stage + ".stderr.log")).open("xb") as err:
                    result = subprocess.run(argv, cwd=output, env=env, stdout=out, stderr=err, check=False)
                item["exitCode"] = result.returncode
                if result.returncode:
                    raise RuntimeError(stage + " failed with exit " + str(result.returncode))
                return (logs / (stage + ".stdout.log")).read_text(encoding="utf-8").strip()
            except Exception as error:
                item["error"] = str(error)
                raise
            finally:
                item["finished"] = time.time()

        run("JavaVersion", [str(Path(env["JAVA_HOME"]) / "bin/java"), "-version"])
        if not re.search(r'version "17(?:[.+"]|$)', (logs / "JavaVersion.stderr.log").read_text(encoding="utf-8")):
            raise RuntimeError("JDK 17 is required")
        state["stage"] = "AnonymousPublicGraph"
        public = fetch_graph(version, source, evidence)
        state["fingerprint"] = public["fingerprint"]
        write_json_new(evidence / "public-manifest.json", public)
        state["stage"] = "PinnedTools"
        tools, wrapper = fetch_tools(output, "gradle9")
        tool_root = tools / TOOL_DIR
        native = Path(run("BootstrapNative", [sys.executable, "-B", str(tool_root / "bootstrap-native.py"),
            "--destination", str(output / "native-bootstrap"), "--kotlin-version", "2.4.20-0.1.0-08"])).resolve()
        receipt = json.loads((output / "native-bootstrap/bootstrap-receipt.json").read_text(encoding="utf-8"))
        if (native.parent != output / "native-bootstrap" or not native.is_dir() or
                Path(receipt["nativeHome"]).resolve() != native or receipt["compilerVersion"] != "2.4.20-0.1.0-08"):
            raise RuntimeError("Native bootstrap output differs")
        write_json_new(evidence / "bootstrap-receipt.json", receipt)
        project = output / "project"
        project.mkdir()
        files = {"settings.gradle.kts": SETTINGS, "build.gradle.kts": BUILD, "gradle.properties": PROPERTIES,
                 "src/commonMain/kotlin/IconsConsumer.kt": PROBE}
        for name, content in files.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        pins = dict(PINS)
        for name in ("components-ui-tooling-preview", "components-ui-tooling-preview-ohosX64", "components-ui-tooling-preview-ohosArm64"):
            pins["org.jetbrains.compose.components:" + name] = "1.12.0-0.1.0-11"
        write_json_new(project / "pins.json", pins)
        write_json_new(project / "metadata-pins.json", METADATA_PINS)
        write_json_new(evidence / "consumer-inputs.json", {"files": [{"path": name, "size": len(text.encode()),
            "sha256": digest(text.encode())} for name, text in files.items()], "direct": GROUP + ":material-icons-extended:" + version,
            "coreResolution": "EXTENDED_API_TRANSITIVE_REQUIRED", "librarySourcesUsedAsCompilationInput": False,
            "dependencyPins": pins, "metadataPins": METADATA_PINS})
        args = ["sh", str(wrapper / "gradlew"), "-p", str(project), "--console=plain", "--stacktrace",
                "--project-cache-dir", str(output / "project-cache"), "-PconsumerOutput=" + str(output),
                "-PconsumerEvidence=" + str(evidence), "-PconsumerTools=" + str(tool_root),
                "-PconsumerHttp=" + str(evidence / "public-manifest.json"), "-PiconsVersion=" + version,
                "-PprobeSha256=" + digest(PROBE.encode()), "-Pkotlin.native.home=" + str(native),
                "-Pkotlin.project.persistent.dir=" + str(output / "kotlin-cache")]
        for stage in STAGES:
            text = run(stage, [*args, *TASKS[stage]])
            if stage == "Tasks":
                found = {name.lstrip(":") for name in re.findall(r"^\s*([\w:-]+)(?:\s+-|\s*$)", text, re.MULTILINE)}
                if not REQUIRED.issubset(found):
                    raise RuntimeError("Consumer tasks are absent from actual discovery")
                write_json_new(evidence / "task-discovery.json", {"required": sorted(REQUIRED),
                    "stdoutSha256": digest((logs / "Tasks.stdout.log").read_bytes())})
        for name, target in (("recordConsumerMetadata", None), ("recordConsumerX64", "ohos_x64"), ("recordConsumerArm64", "ohos_arm64")):
            row = json.loads((evidence / ("consumer-compilation-" + name + ".json")).read_text(encoding="utf-8"))
            if (row.get("target") != target or not row.get("metadataPayload") or not row.get("outputs") or
                    set(row.get("publicTrace", {})) != set(MODULES) or
                    (target and (not row.get("irPayload") or set(row.get("nativeTargets", [])) != {target}))):
                raise RuntimeError("Consumer compilation evidence differs: " + name)
        state["status"] = "ANONYMOUS_PUBLIC_METADATA_AND_DUAL_OHOS_COMPILED"
    except Exception as error:
        failed = error
        state.update(status="FAILED", error=str(error))
    finally:
        try:
            files = [path for path in evidence.rglob("*") if path.is_file()]
            if len(files) > 80 or any(path.stat().st_size > 8 * 1024 * 1024 for path in files):
                raise RuntimeError("Consumer structured evidence exceeds limits")
            total = sum(path.stat().st_size for path in files)
            if total > 128 * 1024 * 1024:
                raise RuntimeError("Consumer structured evidence exceeds total limit")
            errors = []
            for stage in ("JavaVersion", "BootstrapNative", *STAGES):
                for stream in ("stdout", "stderr"):
                    path = output / "logs" / (stage + "." + stream + ".log")
                    if path.is_file():
                        try:
                            total = collect_file(path, evidence, path.name, index, total)
                        except Exception as error:
                            errors.append(path.name + ": " + str(error))
                            with path.open(encoding="utf-8", errors="replace") as source:
                                tail = "".join(deque(source, maxlen=120)).encode()[-32768:]
                            (evidence / (path.name + ".tail")).write_bytes(tail)
            write_json_new(evidence / "evidence-index.json", {"schemaVersion": 1, "files": index})
            if errors:
                raise RuntimeError("Evidence collection failed: " + "; ".join(errors))
        except Exception as error:
            state["evidenceError"] = str(error)
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
        print("Consumer failure: " + str(failed), file=sys.stderr)
        label = state.get("stage")
        if label and (output / "logs" / (label + ".stderr.log")).is_file():
            with (output / "logs" / (label + ".stderr.log")).open(encoding="utf-8", errors="replace") as stream:
                print("".join(deque(stream, maxlen=80)).encode()[-16384:].decode(errors="replace"), file=sys.stderr)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
