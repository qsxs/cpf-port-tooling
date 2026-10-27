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
val pokoGroup = "io.github.qsxs.cpf.poko"
val pokoVersion = providers.gradleProperty("pokoVersion").get()
val probe = file("src/commonMain/kotlin/PokoHostConsumer.kt").canonicalFile
val probeSha = providers.gradleProperty("probeSha256").get()
val metadataTools = readMap(tools.resolve("metadata-toolchain.json"))
val commonizer = readMap(tools.resolve("commonizer-toolchain.json"))
val host = readMap(tools.resolve("native-compiler-toolchain.json"))
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
            dependencies { implementation("$pokoGroup:poko-annotations:$pokoVersion") }
        }
        matching { it.name.endsWith("Test") }.configureEach { kotlin.setSrcDirs(emptyList<File>()) }
    }
}
configurations.configureEach {
    val metadata = name.endsWith("ResolvableDependenciesMetadata") || name == "allSourceSetsCompileDependenciesMetadata"
    val library = metadata || name.endsWith("CompileKlibraries") || name.endsWith("CompilationDependenciesMetadata")
    if (library && !name.contains("Test", ignoreCase = true)) resolutionStrategy.eachDependency {
        val ga = "${requested.group}:${requested.name}"
        check(ga != "dev.drewhamilton.poko:poko-annotations") { "Original plugin annotations escaped exclusion" }
        if (requested.group == pokoGroup) {
            check(requested.version == pokoVersion) { "Poko version escaped explicit Pages coordinate" }
        } else {
            check(ga == "org.jetbrains.kotlin:kotlin-stdlib") { "Unexpected consumer library dependency: $ga" }
            if (requested.version != "2.4.20-0.1.0-08") useVersion("2.4.20-0.1.0-08")
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
// Gradle 8 的宿主闭包按实际配置记录，不施加 Gradle 9 的 14 项集合或版本选择。
fun observedTools(): List<Map<String, Any>> {
    val known = listOf(hostPins to hostArtifacts,
        asMap(metadataTools.getValue("launcherPins")) to asMap(metadataTools.getValue("launcherArtifacts")),
        asMap(commonizer.getValue("pins")) to asMap(commonizer.getValue("artifacts")))
    val names = listOf(host.getValue("configuration").toString(), commonizer.getValue("configuration").toString())
    return names.mapNotNull { name ->
        val configuration = configurations.findByName(name) ?: return@mapNotNull null
        if (!configuration.isCanBeResolved) return@mapNotNull null
        val artifacts = configuration.resolvedConfiguration.resolvedArtifacts.map { artifact ->
            val id = artifact.moduleVersion.id
            val ga = "${id.group}:${id.name}"
            if (id.group == "org.jetbrains.kotlin" && listOf("kotlin-compiler", "kotlin-native-", "kotlin-build-tools-",
                    "kotlin-daemon-", "kotlin-tooling-", "kotlin-klib-commonizer", "kotlin-script-runtime").any { id.name.startsWith(it) }) {
                check(id.version == "2.4.20-0.1.0-08") { "Observed compiler host version differs: $id" }
            }
            val matches = known.mapNotNull { (pins, values) -> if (pins[ga] == id.version) values[ga] else null }
            matches.forEach { item ->
                val expected = asMap(item)
                check(sha(artifact.file) == expected["sha256"] && artifact.file.length() == (expected.getValue("size") as Number).toLong()) {
                    "Observed compiler host bytes differ: $id"
                }
            }
            mapOf("gav" to id.toString(), "matchedKnownIdentity" to matches.isNotEmpty(), "files" to records(listOf(artifact.file)))
        }
        mapOf("configuration" to name, "edges" to edges(configuration), "artifacts" to artifacts)
    }
}
fun pluginRecords() = compileTasks.map { name ->
    val compiler = tasks.getByName(name) as KotlinNativeCompile
    check(!plugins.hasPlugin("dev.drewhamilton.poko")) { "Poko Gradle plugin must not be applied to Gradle 8 host" }
    val files = compiler.compilerPluginClasspath?.files.orEmpty()
    check(files.none { it.name.startsWith("poko-compiler-plugin-") || sha(it) == "7bdd55014b8e0d8115e99c49d1167c8d85bf1367fdec59ef4af28d0788a114c6" })
    check(compiler.compilerPluginCommandLine.none { it.startsWith("plugin:dev.drewhamilton.poko:") })
    mapOf("task" to compiler.path, "pokoPluginApplied" to false, "artifacts" to records(files), "options" to compiler.compilerPluginCommandLine)
}
fun toolRecords(): Map<String, Any> {
    val observed = observedTools()
    check(observed.any { (it.getValue("artifacts") as List<*>).isNotEmpty() }) { "No Gradle 8 compiler host artifacts were observed" }
    return mapOf("observedCompilerAndCommonizer" to observed, "plugins" to pluginRecords(),
        "policy" to "OBSERVE_GRADLE8_HOST_NO_GRADLE9_CLOSURE_FORCE")
}
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
        if (id.group == pokoGroup) {
            count++
            check(id.version == pokoVersion)
            if (target == null) check(id.module == "poko-annotations" && attrs["org.jetbrains.kotlin.platform.type"] == "common" && attrs["org.gradle.usage"] == "kotlin-metadata")
            else check(id.module in listOf("poko-annotations", if (target == "ohos_x64") "poko-annotations-ohosx64" else "poko-annotations-ohosarm64") &&
                attrs["org.jetbrains.kotlin.native.target"] == target && attrs["org.gradle.usage"] == "kotlin-api")
            check(expected.any { it["sha256"] == sha(artifact.file) && (it.getValue("size") as Number).toLong() == artifact.file.length() }) { "Poko artifact differs from anonymous HTTP: $id" }
        }
        check(!(id.group == "dev.drewhamilton.poko" && id.module == "poko-annotations"))
        mapOf("component" to id.displayName, "attributes" to attrs, "files" to records(listOf(artifact.file)))
    }
    check(count == expected.size && count > 0) { "Poko selected artifact set differs: $name" }
    val graph = edges(configuration)
    check(graph.any { it.getValue("requested") == "$pokoGroup:poko-annotations:$pokoVersion" })
    check(graph.none { it.getValue("selected").contains("dev.drewhamilton.poko:poko-annotations") })
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
    check(matches.size == 1) { "Poko transformed metadata cannot be traced to the Pages root" }
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
        check(gradle.gradleVersion == "8.11.1")
        check(!plugins.hasPlugin("dev.drewhamilton.poko"))
        evidence("consumer-resolution.json", mapOf("gradleVersion" to gradle.gradleVersion, "pokoPluginApplied" to false,
            "pokoVersion" to pokoVersion, "tools" to toolRecords(), "configurations" to resolution(), "sources" to records(listOf(probe))))
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
            check(gradle.gradleVersion == "8.11.1" && !plugins.hasPlugin("dev.drewhamilton.poko"))
            check(compiler.compilerPluginCommandLine.none { it.startsWith("plugin:dev.drewhamilton.poko:") })
            evidence("consumer-compilation-$name.json", mapOf("gradleVersion" to gradle.gradleVersion, "pokoPluginApplied" to false,
                "task" to compiler.path, "target" to target, "sources" to records(listOf(probe)),
                "outputs" to records(outputs), "libraries" to compiler.libraries.files.sortedBy { it.path }.map { mapOf("path" to it.absolutePath, "files" to records(listOf(it))) },
                "pluginOptions" to compiler.compilerPluginCommandLine, "plugins" to records(compiler.compilerPluginClasspath?.files.orEmpty()),
                "metadataTrace" to if (target == null) metadataTrace(compiler) else null,
                "metadataPayload" to metadata, "irPayload" to ir, "nativeTargets" to targets, "link" to "NOT_RUN", "runtime" to "NOT_RUN"))
        }
    }
}
recordCompilation("recordConsumerMetadata", "compileCommonMainKotlinMetadata", null)
recordCompilation("recordConsumerX64", "compileKotlinOhosX64", "ohos_x64")
recordCompilation("recordConsumerArm64", "compileKotlinOhosArm64", "ohos_arm64")
