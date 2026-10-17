package com.wplace.commander.network

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import com.wplace.commander.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException

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
                .url("https://api.github.com/repos/JesPezz/wplace-commander/releases/latest")
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

    /** ¿La app puede instalar APKs? (Android 8+: permiso "instalar apps desconocidas" por app). */
    fun canInstall(context: Context): Boolean =
        context.packageManager.canRequestPackageInstalls()

    /** Intent a los ajustes para conceder "instalar apps desconocidas" a esta app. */
    fun unknownSourcesIntent(context: Context): Intent =
        Intent(
            android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:${context.packageName}")
        )

    /** Descarga el APK a cacheDir informando el progreso (0-100) en el hilo principal. */
    suspend fun downloadApk(context: Context, url: String, onProgress: (Int) -> Unit = {}): File =
        withContext(Dispatchers.IO) {
            val req = Request.Builder().url(url).addHeader("Accept", "application/octet-stream").build()
            client.newCall(req).execute().use { res ->
                if (!res.isSuccessful) throw IOException("HTTP ${res.code}")
                val body = res.body ?: throw IOException("respuesta vacía")
                val total = body.contentLength()
                val file = File(context.cacheDir, "update.apk")
                body.byteStream().use { input ->
                    file.outputStream().use { out ->
                        val buf = ByteArray(8192)
                        var read = input.read(buf)
                        var done = 0L
                        var last = -1
                        while (read != -1) {
                            out.write(buf, 0, read); done += read
                            if (total > 0) {
                                val pct = (done * 100 / total).toInt()
                                if (pct != last) { last = pct; withContext(Dispatchers.Main) { onProgress(pct) } }
                            }
                            read = input.read(buf)
                        }
                    }
                }
                file
            }
        }

    private fun installApk(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    /**
     * Descarga el APK e intenta instalar. Devuelve true si se lanzó el instalador;
     * false si falta el permiso (en cuyo caso abre los ajustes para concederlo).
     */
    suspend fun downloadAndInstall(context: Context, url: String, onProgress: (Int) -> Unit = {}): Boolean {
        val file = downloadApk(context, url, onProgress)
        if (!canInstall(context)) {
            context.startActivity(unknownSourcesIntent(context))
            return false
        }
        installApk(context, file)
        return true
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
