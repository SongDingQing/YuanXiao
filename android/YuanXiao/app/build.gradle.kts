import org.gradle.api.tasks.Copy
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
}

val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")
if (localPropertiesFile.isFile) {
    localPropertiesFile.inputStream().use(localProperties::load)
}

fun localProperty(name: String, defaultValue: String): String {
    return providers.gradleProperty(name).orNull
        ?: localProperties.getProperty(name)
        ?: defaultValue
}

fun quotedBuildConfigValue(value: String): String {
    return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
}

val yuanxiaoRelayBaseUrl = localProperty("yuanxiao.relay.baseUrl", "https://a.example.com").trimEnd('/')
val yuanxiaoApkOutputDir = localProperty(
    "yuanxiao.apk.outputDir",
    layout.buildDirectory.dir("yuanxiao-apk").get().asFile.absolutePath
)

android {
    namespace = "com.example.yuanxiao"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.example.yuanxiao"
        minSdk = 24
        targetSdk = 36
        versionCode = 50
        versionName = "0.50"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "YUANXIAO_RELAY_BASE_URL", quotedBuildConfigValue(yuanxiaoRelayBaseUrl))
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
}

val yuanxiaoVersionName = android.defaultConfig.versionName ?: "dev"
val copyYuanXiaoDebugApk by tasks.registering(Copy::class) {
    from(layout.buildDirectory.file("outputs/apk/debug/app-debug.apk"))
    into(yuanxiaoApkOutputDir)
    rename { "yuanxiao-$yuanxiaoVersionName.apk" }
    mustRunAfter("assembleDebug")
}

afterEvaluate {
    tasks.named("assembleDebug") {
        finalizedBy(copyYuanXiaoDebugApk)
    }
}
