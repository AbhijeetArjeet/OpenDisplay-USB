pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "OpenDisplayUSB"

include(":app")
include(":core:protocol")
include(":core:timing")
include(":core:transport")
include(":core:capabilities")
include(":video")
include(":audio")
include(":input")
include(":display")
include(":diagnostics")
include(":ui")
