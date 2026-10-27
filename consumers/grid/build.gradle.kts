import groovy.json.JsonOutput
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
fun readMap(file: File) = (JsonSlurper().parse(file) as Map<*, *>).entries.associate { it.key.toString() to it.value }
fun asMap(value: Any?) = (value as Map<*, *>).entries.associate { it.key.toString() to requireNotNull(it.value) }
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
val gridGroup = "com.github.qsxs.gridlayout-compose"
val gridVersion = providers.gradleProperty("gridVersion").get()
val probe = file("src/commonMain/kotlin/GridConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
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
            dependencies { implementation("$gridGroup:grid:$gridVersion") }
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
        if (requested.group == gridGroup) {
            check(requested.version == gridVersion) { "Grid version escaped explicit Pages coordinate" }
        } else {
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
fun checkedTools(name: String, fixed: Map<String, Any>, expected: Map<String, Any>): Map<String, Any> {
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
fun resolution() = listOf("commonMainResolvableDependenciesMetadata", "ohosX64CompileKlibraries", "ohosArm64CompileKlibraries").map { name ->
    val configuration = configurations.getByName(name)
    val target = when (name) { "ohosX64CompileKlibraries" -> "ohos_x64"; "ohosArm64CompileKlibraries" -> "ohos_arm64"; else -> null }
    val expected = if (target == null) (http.getValue("metadataArtifacts") as List<*>).map(::asMap) else
        (asMap(http.getValue("nativeArtifacts")).getValue(target) as List<*>).map(::asMap)
    var gridCount = 0
    val artifacts = configuration.incoming.artifacts.artifacts.map { artifact ->
        val id = artifact.id.componentIdentifier
        check(id is ModuleComponentIdentifier)
        val attrs = artifact.variant.attributes.keySet().associate { it.name to artifact.variant.attributes.getAttribute(it).toString() }
        val files = records(listOf(artifact.file))
        if (id.group == gridGroup) {
            gridCount++
            check(id.version == gridVersion)
            if (target == null) check(id.module == "grid" && attrs["org.jetbrains.kotlin.platform.type"] == "common" && attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf("grid", if (target == "ohos_x64") "grid-ohosx64" else "grid-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            check(expected.any { it["sha256"] == sha(artifact.file) && (it.getValue("size") as Number).toLong() == artifact.file.length() }) { "Gradle Grid artifact differs from anonymous HTTP: $id" }
        }
        mapOf("component" to id.displayName, "attributes" to attrs, "files" to files)
    }
    check(gridCount == expected.size && gridCount > 0) { "Consumer Grid artifact set is incomplete: $name" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$gridGroup:grid:$gridVersion" }) { "Root Grid GAV was not consumed" }
    mapOf("configuration" to name, "target" to target, "edges" to graph, "artifacts" to artifacts)
}
fun payload(file: File): Map<String, Map<String, Any>> {
    val found = mutableMapOf<String, Map<String, Any>>()
    fun add(name: String, bytes: ByteArray) {
        val normalized = name.removePrefix("commonMain/")
        if (normalized.startsWith("default/")) found[normalized] = mapOf("size" to bytes.size.toLong(), "sha256" to digest(bytes))
    }
    if (file.isDirectory) leaves(file).forEach { add(it.relativeTo(file).invariantSeparatorsPath, it.readBytes()) }
    else if (file.isFile && file.extension in listOf("jar", "klib")) ZipFile(file).use { zip ->
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
    check(matches.size == 1) { "Grid transformed common metadata cannot be traced to HTTP root archive" }
    return mapOf("rootHttpArtifacts" to http.getValue("metadataArtifacts"), "compilerLibrary" to matches.single().absolutePath,
        "payload" to expected, "payloadFileCount" to expected.size)
}
val checkTools = tasks.register("verifyConsumerTools") {
    outputs.upToDateWhen { false }
    doLast { evidence("consumer-tools.json", toolRecords()) }
}
tasks.withType<KotlinNativeCompile>().configureEach { if (name in compileTasks) dependsOn(checkTools) }
tasks.register("resolveConsumer") {
    doLast {
        check(gradle.gradleVersion == "9.5.0")
        evidence("consumer-resolution.json", mapOf("gridVersion" to gridVersion, "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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
                "metadataTrace" to if (target == null) metadataTrace(compiler) else null,
                "metadataPayload" to metadata, "irPayload" to ir, "nativeTargets" to targets, "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
