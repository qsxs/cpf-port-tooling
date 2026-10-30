"""只从匿名 Pages 解析并编译 Coil 三入口、七模块消费图。"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urljoin
import urllib.error
import urllib.request

PAGES = "https://qsxs.github.io/cpf-maven/"
GROUP = "io.github.qsxs.cpf.coil"
MODULES = ("coil", "coil-core", "coil-compose", "coil-compose-core", "coil-network-core", "coil-network-ktor3", "coil-svg")
DIRECT = ("coil-compose", "coil-network-ktor3", "coil-svg")
PROBE = r'''package acceptance

import androidx.compose.runtime.Composable
import coil3.Extras
import coil3.compose.AsyncImage
import coil3.network.ktor3.KtorNetworkFetcherFactory
import coil3.svg.Svg
import coil3.svg.SvgDecoder
import io.ktor.client.HttpClient

@Composable
fun CoilPicture(model: Any?) {
    AsyncImage(model = model, contentDescription = null)
}

fun networkFactory(client: HttpClient) = KtorNetworkFetcherFactory(client)
fun svgFactory() = SvgDecoder.Factory(parser = Svg.Parser.DEFAULT)
fun extras(): Extras = Extras.Builder().build()
'''

SETTINGS = r'''import groovy.json.JsonSlurper
pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/")
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/")
        gradlePluginPortal()
        mavenCentral()
    }
    plugins {
        id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08"
        id("org.jetbrains.kotlin.plugin.compose") version "2.4.20-0.1.0-08"
        id("org.jetbrains.compose") version "1.12.0-0.1.0-11"
    }
}
val metadataPins = JsonSlurper().parse(file("metadata-pins.json")) as Map<*, *>
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven("https://qsxs.github.io/cpf-maven/") }
            filter { includeGroup("io.github.qsxs.cpf.coil") }
        }
        exclusiveContent {
            forRepository { maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") }
            filter { includeGroup("io.ktor") }
        }
        exclusiveContent {
            forRepository { maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") }
            filter {
                includeModule("org.jetbrains.kotlinx", "kotlinx-io-okio")
                includeModule("org.jetbrains.kotlinx", "kotlinx-io-okio-ohosx64")
                includeModule("org.jetbrains.kotlinx", "kotlinx-io-okio-ohosarm64")
            }
        }
        google { content { metadataPins.forEach { (ga, version) ->
            val parts = ga.toString().split(":")
            if (parts[0].startsWith("androidx.")) includeVersion(parts[0], parts[1], version.toString())
        } } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/")
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/")
        mavenCentral()
    }
}
rootProject.name = "coil-pages-consumer"
'''

BUILD = r'''import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.security.MessageDigest
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.jetbrains.kotlin.gradle.tasks.KotlinNativeCompile

plugins {
    kotlin("multiplatform")
    kotlin("plugin.compose")
    id("org.jetbrains.compose")
}
fun asMap(value: Any?) = (value as Map<*, *>).entries.associate { it.key.toString() to requireNotNull(it.value) }
fun readMap(file: File) = asMap(JsonSlurper().parse(file))
fun sha(file: File) = MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }
fun leaves(file: File): List<File> = if (file.isDirectory) file.walkTopDown().filter(File::isFile).toList() else if (file.isFile) listOf(file) else emptyList()
val groupName = "io.github.qsxs.cpf.coil"
val versionName = providers.gradleProperty("coilVersion").get()
val attempt = providers.gradleProperty("consumerAttempt").get()
val output = file(providers.gradleProperty("consumerOutput").get())
val graph = readMap(file("http-graph.json"))
val pins = readMap(file("pins.json"))
val metadataPins = readMap(file("metadata-pins.json"))
val modules = listOf("coil", "coil-core", "coil-compose", "coil-compose-core", "coil-network-core", "coil-network-ktor3", "coil-svg")
val directModules = listOf("coil-compose", "coil-network-ktor3", "coil-svg")
layout.buildDirectory.set(output.resolve("build"))

kotlin {
    ohosX64()
    ohosArm64()
    sourceSets {
        val commonMain by getting {
            dependencies { directModules.forEach { implementation("$groupName:$it:$versionName") } }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
configurations.configureEach {
    val metadata = name.endsWith("ResolvableDependenciesMetadata") || name == "allSourceSetsCompileDependenciesMetadata"
    val library = metadata || name.endsWith("CompileKlibraries") || name.endsWith("CompilationDependenciesMetadata")
    if (library && !name.contains("Test", ignoreCase = true)) resolutionStrategy.eachDependency {
        val ga = "${requested.group}:${requested.name}"
        if (requested.group == groupName) {
            check(requested.version == versionName && requested.name in modules.flatMap { listOf(it, "$it-ohosx64", "$it-ohosarm64") })
        } else {
            val expected = (if (metadata) metadataPins[ga] ?: pins[ga] else pins[ga])?.toString()
                ?: error("Unpinned Coil consumer dependency: $ga")
            if (requested.version != expected) useVersion(expected)
        }
    }
}
fun writeEvidence(name: String, value: Any) {
    val file = output.resolve("evidence/$name-attempt-$attempt.json")
    file.parentFile.mkdirs()
    check(!file.exists())
    file.writeText(JsonOutput.prettyPrint(JsonOutput.toJson(value)) + "\n")
}
fun selected(configurationName: String, target: String): List<Map<String, Any>> {
    val configuration = configurations.getByName(configurationName)
    val found = mutableMapOf<String, Map<String, Any>>()
    configuration.incoming.artifacts.artifacts.forEach { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier) { "Unexpected project artifact: $id" }
        check(id.group != "io.coil-kt.coil3") { "Unexpected original Coil artifact: $id" }
        if (id.group == groupName) {
            val module = modules.singleOrNull { id.module in listOf(it, "$it-ohosx64", "$it-ohosarm64") }
                ?: error("Unexpected Coil module: $id")
            check(module !in found && id.version == versionName)
            val expected = asMap(asMap(graph.getValue(module)).getValue(target))
            check(artifact.file.isFile && artifact.file.length() == (expected["size"] as Number).toLong() && sha(artifact.file) == expected["sha256"])
            val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
            if (target == "common") check(attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(attrs["org.gradle.usage"] == "kotlin-api" && attrs["org.jetbrains.kotlin.native.target"] == target)
            found[module] = mapOf("component" to id.displayName, "path" to artifact.file.absolutePath,
                "size" to artifact.file.length(), "sha256" to sha(artifact.file), "attributes" to attrs)
        }
    }
    check(found.keys == modules.toSet()) { "Incomplete Coil module graph: $configurationName ${found.keys}" }
    val edges = configuration.incoming.resolutionResult.allDependencies.map { edge ->
        check(edge is ResolvedDependencyResult) { "Unresolved Coil consumer dependency: $edge" }
        mapOf("from" to edge.from.id.displayName, "requested" to edge.requested.displayName, "selected" to edge.selected.id.displayName)
    }
    writeEvidence("resolution-$configurationName", mapOf("target" to target, "artifacts" to found, "edges" to edges))
    return found.values.toList()
}
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0" && System.getProperty("java.specification.version") == "17")
        check(providers.gradleProperty("rendererBackend").get() == "skia")
        val direct = configurations.getByName("commonMainImplementation").dependencies.filter { it.group == groupName }
        check(direct.map { it.name }.toSet() == directModules.toSet() && direct.all { it.version == versionName })
        selected("commonMainResolvableDependenciesMetadata", "common")
        selected("ohosX64CompileKlibraries", "ohos_x64")
        selected("ohosArm64CompileKlibraries", "ohos_arm64")
        writeEvidence("consumer-resolution", mapOf("directModules" to directModules,
            "rendererBackend" to providers.gradleProperty("rendererBackend").get(), "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
    }
}
fun record(name: String, taskName: String, target: String) {
    tasks.register(name) {
        dependsOn(taskName)
        outputs.upToDateWhen { false }
        doLast {
            val task = tasks.getByName(taskName) as KotlinNativeCompile
            val sources = task.sources.files.filter { it.isFile && it.extension == "kt" }
            val outputs = task.outputs.files.files.flatMap(::leaves).filter { it.length() > 0 }
            check(task.enabled && task.state.executed && !task.state.noSource && task.state.failure == null && sources.size == 1 && outputs.isNotEmpty())
            val nativeTrace = if (target == "common") emptyList() else {
                val configurationName = if (target == "ohos_x64") "ohosX64CompileKlibraries" else "ohosArm64CompileKlibraries"
                val published = configurations.getByName(configurationName).incoming.artifacts.artifacts.filter {
                    val id = it.id.componentIdentifier
                    id is ModuleComponentIdentifier && id.group == groupName
                }
                val compilerFiles = task.libraries.files.filter { it.isFile }
                check(published.size == modules.size)
                published.map { artifact ->
                    val hash = sha(artifact.file)
                    val matches = compilerFiles.filter { it.length() == artifact.file.length() && sha(it) == hash }
                    check(matches.size == 1) { "Compiler input does not uniquely match published Coil artifact: ${artifact.id}" }
                    mapOf("artifact" to artifact.id.componentIdentifier.displayName, "sha256" to hash,
                        "compilerPath" to matches.single().absolutePath)
                }
            }
            writeEvidence(name, mapOf("task" to task.path, "target" to target,
                "sources" to sources.map { mapOf("path" to it.absolutePath, "sha256" to sha(it)) },
                "outputs" to outputs.map { mapOf("path" to it.absolutePath, "sha256" to sha(it), "size" to it.length()) },
                "nativeCompilerTrace" to nativeTrace, "metadataCompilerTrace" to "NOT_INSPECTED",
                "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
record("recordConsumerMetadata", "compileCommonMainKotlinMetadata", "common")
record("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
record("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
'''


def get(url):
    attempt = 1
    while True:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "cpf-coil-public-consumer"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
                if response.status != 200 or len(data) > 2_000_000:
                    raise RuntimeError("Public metadata response invalid")
                return data
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        print("公开元数据请求暂时失败，重试次数：" + str(attempt), flush=True)
        time.sleep(min(attempt * 2, 30))
        attempt += 1


def transient_network_failure(text):
    retryable = ("connect timed out", "read timed out", "connection reset", "connection refused",
                 "temporary failure in name resolution", "remote host terminated the handshake",
                 "status code 429", "status code 500", "status code 502", "status code 503", "status code 504")
    if "* What went wrong:" not in text:
        return False
    failure = text.rsplit("* What went wrong:", 1)[-1].split("* Try:", 1)[0].lower()
    nonretryable = ("compilation error", "compilation failed", "unresolved reference", "could not find", "checksum mismatch")
    return not any(reason in failure for reason in nonretryable) and any(reason in failure for reason in retryable)


def graph(version, cfg):
    jobs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for module in MODULES:
            for suffix, target in (("", "common"), ("-ohosx64", "ohos_x64"), ("-ohosarm64", "ohos_arm64")):
                artifact = module + suffix
                url = PAGES + GROUP.replace(".", "/") + "/" + artifact + "/" + version + "/" + artifact + "-" + version + ".module"
                jobs[(module, target)] = (url, pool.submit(get, url))
        documents = {key: (url, future.result()) for key, (url, future) in jobs.items()}
    result, receipts = {}, []
    for module in MODULES:
        result[module] = {}
        for target in ("common", "ohos_x64", "ohos_arm64"):
            url, data = documents[(module, target)]
            doc = json.loads(data)
            require = doc["component"]
            if (require["group"], require["module"], require["version"]) != (GROUP, module, version):
                raise RuntimeError("Public GMM owner differs: " + module)
            if target == "common":
                variant = next(x for x in doc["variants"] if x["name"] == "metadataApiElements")
                edges = {d["module"] for d in variant.get("dependencies", []) if d["group"] == GROUP}
                if edges != set(cfg["modules"][module]["projectApiDependencies"]):
                    raise RuntimeError("Public module API edges differ: " + module)
                for abi, suffix in (("ohos_x64", "-ohosx64"), ("ohos_arm64", "-ohosarm64")):
                    expected_url = documents[(module, abi)][0]
                    if not any(v.get("available-at", {}).get("module") == module + suffix and
                               v["available-at"].get("group") == GROUP and
                               v["available-at"].get("version") == version and
                               urljoin(url, v["available-at"]["url"]) == expected_url for v in doc["variants"]):
                        raise RuntimeError("Public root target mapping missing: " + module + suffix)
            else:
                variant = next(x for x in doc["variants"] if x.get("attributes", {}).get("org.jetbrains.kotlin.native.target") == target
                               and x.get("attributes", {}).get("org.gradle.usage") == "kotlin-api")
            files = variant["files"]
            if len(files) != 1 or not re.fullmatch(r"[0-9a-f]{64}", files[0].get("sha256", "")):
                raise RuntimeError("Public GMM file declaration differs: " + module + " " + target)
            result[module][target] = {"sha256": files[0]["sha256"], "size": files[0]["size"]}
            receipts.append({"url": url, "status": 200, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    return result, receipts


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data)


def main():
    source_sha = os.environ["COIL_SOURCE_SHA"]
    version = os.environ["COIL_VERSION"]
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not re.fullmatch(
        r"3\.3\.0-cpf11-preview-" + source_sha[:12] + r"-[1-9][0-9]*-[1-9][0-9]*", version):
        raise RuntimeError("Source/version identity differs")
    checkout = Path(os.environ["COIL_CHECKOUT"]).resolve()
    output = Path(os.environ["COIL_CONSUMER_OUTPUT"]).resolve()
    native = Path(os.environ["COIL_NATIVE_HOME"]).resolve()
    head = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if head != source_sha or not native.is_dir():
        raise RuntimeError("Source or native tool identity differs")
    recipe = checkout / "ohos"
    cfg = json.loads((recipe / "port-config.json").read_text(encoding="utf-8"))
    public_graph, receipts = graph(version, cfg)
    output.mkdir(parents=True, exist_ok=False)
    project = output / "consumer"
    write(output / "evidence/public-http.json", json.dumps({"requests": receipts}, ensure_ascii=False, indent=2) + "\n")
    write(project / "http-graph.json", json.dumps(public_graph, indent=2) + "\n")
    write(project / "settings.gradle.kts", SETTINGS)
    write(project / "build.gradle.kts", BUILD)
    properties = (recipe / "gradle.properties").read_text(encoding="utf-8").rstrip() + "\nrendererBackend=skia\n"
    write(project / "gradle.properties", properties)
    write(project / "src/commonMain/kotlin/CoilConsumer.kt", PROBE)
    shutil.copyfile(recipe / "dependency-pins.json", project / "pins.json")
    shutil.copyfile(recipe / "metadata-pins.json", project / "metadata-pins.json")
    shutil.copytree(recipe / "gradle", project / "gradle")
    shutil.copy2(recipe / "gradlew", project / "gradlew")
    env = os.environ.copy()
    env["GRADLE_USER_HOME"] = str(output / "gradle-home")
    env["KONAN_DATA_DIR"] = str(output / "konan")
    for task in ("resolveConsumer", "recordConsumerMetadata", "recordConsumerX64", "recordConsumerArm64"):
        attempt = 1
        while True:
            print("执行 " + task + "，第 " + str(attempt) + " 次", flush=True)
            cmd = [str(project / "gradlew"), "-PcoilVersion=" + version, "-PconsumerOutput=" + str(output),
                   "-PconsumerAttempt=" + str(attempt), "-Pkotlin.native.home=" + str(native),
                   "--project-cache-dir", str(output / "project-cache"), "--console=plain", task]
            log_path = output / "evidence" / (task + ".attempt-" + str(attempt) + ".log")
            with log_path.open("x", encoding="utf-8") as log:
                process = subprocess.run(cmd, cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
            print(task + " exit=" + str(process.returncode), flush=True)
            if process.returncode == 0:
                break
            if not transient_network_failure(log_path.read_text(encoding="utf-8", errors="replace")):
                raise RuntimeError("Consumer stage failed: " + task)
            print("消费依赖传输暂时失败，保留本轮缓存与日志后重试：" + task, flush=True)
            time.sleep(min(attempt * 2, 30))
            attempt += 1
    write(output / "evidence/result.json", json.dumps({"sourceSha": source_sha, "version": version,
          "metadata": "PASS", "ohosX64": "PASS", "ohosArm64": "PASS", "link": "NOT_RUN", "runtime": "NOT_RUN"}, indent=2) + "\n")


if __name__ == "__main__":
    main()
