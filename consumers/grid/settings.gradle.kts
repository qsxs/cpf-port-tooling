import groovy.json.JsonSlurper

pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("com.github.qsxs.gridlayout-compose") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("com.github.qsxs.gridlayout-compose") } }
        gradlePluginPortal { content { excludeGroup("com.github.qsxs.gridlayout-compose") } }
        mavenCentral { content { excludeGroup("com.github.qsxs.gridlayout-compose") } }
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
            forRepository { maven { name = "GridPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("com.github.qsxs.gridlayout-compose") }
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
        mavenCentral { content { excludeGroup("com.github.qsxs.gridlayout-compose") } }
    }
}
rootProject.name = "grid-pages-consumer"
