pluginManagement {
    repositories {
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.poko") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.poko") } }
        gradlePluginPortal { content { excludeGroup("io.github.qsxs.cpf.poko") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.poko") } }
    }
    plugins { id("org.jetbrains.kotlin.multiplatform") version "2.4.20-0.1.0-08" }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        exclusiveContent {
            forRepository { maven { name = "PokoPages"; url = uri("https://qsxs.github.io/cpf-maven/") } }
            filter { includeGroup("io.github.qsxs.cpf.poko") }
        }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-develop/") { content { excludeGroup("io.github.qsxs.cpf.poko") } }
        maven("https://maven.eazytec-cloud.com/nexus/repository/maven-public/") { content { excludeGroup("io.github.qsxs.cpf.poko") } }
        mavenCentral { content { excludeGroup("io.github.qsxs.cpf.poko") } }
    }
}
rootProject.name = "poko-pages-gradle8-consumer"
