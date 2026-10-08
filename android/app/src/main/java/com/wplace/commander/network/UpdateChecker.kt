package com.wplace.commander.network

import com.wplace.commander.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

@Serializable
data class GitHubRelease(
    val tag_name: String = "",
    val name: String = "",
    val body: String = "",
    val html_url: String = "",
    val assets: List<GitHubAsset> = emptyList()
)

@Serializable
data class GitHubAsset(
    val name: String = "",
    val browser_download_url: String = "",
    val size: Long = 0
)

data class UpdateInfo(
    val hasUpdate: Boolean,
    val latestVersion: String,
    val url: String,
    val body: String,
    val downloadUrl: String
)

object UpdateChecker {
    private val client = OkHttpClient.Builder().build()
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun check(): UpdateInfo = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("https://api.github.com/repos/JesPezz/WPlace-Automation-System/releases/latest")
                .addHeader("Accept", "application/vnd.github+json")
                .build()
            client.newCall(req).execute().use { res ->
                if (!res.isSuccessful) return@withContext UpdateInfo(false, BuildConfig.VERSION_NAME, "", "", "")
                val bodyStr = res.body?.string() ?: return@withContext UpdateInfo(false, BuildConfig.VERSION_NAME, "", "", "")
                val rel = json.decodeFromString<GitHubRelease>(bodyStr)
                val latest = rel.tag_name.trimStart('v')
                val cur = BuildConfig.VERSION_NAME.trimStart('v')
                val has = isNewer(latest, cur)
                val apkUrl = rel.assets.firstOrNull { it.name.endsWith(".apk") }?.browser_download_url ?: rel.html_url
                UpdateInfo(has, latest, rel.html_url, rel.body, apkUrl)
            }
        } catch (_: Exception) {
            UpdateInfo(false, BuildConfig.VERSION_NAME, "", "", "")
        }
    }

    private fun isNewer(latest: String, current: String): Boolean {
        fun toList(s: String) = s.split('.').mapNotNull { it.trim().toIntOrNull() }
        val l = toList(latest)
        val c = toList(current)
        val max = maxOf(l.size, c.size)
        for (i in 0 until max) {
            val lv = l.getOrNull(i) ?: 0
            val cv = c.getOrNull(i) ?: 0
            if (lv != cv) return lv > cv
        }
        return false
    }
}
