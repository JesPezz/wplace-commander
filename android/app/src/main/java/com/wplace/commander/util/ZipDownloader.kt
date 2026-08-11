package com.wplace.commander.util

import android.content.Context
import android.net.Uri
import com.wplace.commander.network.ApiClient
import java.io.File

/** Descarga el ZIP del servidor y lo guarda en el URI seleccionado por el usuario. */
suspend fun downloadZipToUri(context: Context, uri: Uri, taskId: String?) {
    val body = ApiClient.api().downloadZip(taskId = taskId)
    context.contentResolver.openOutputStream(uri)?.use { out ->
        body.byteStream().use { it.copyTo(out) }
    }
}

/** Descarga el ZIP a un archivo temporal en cacheDir (para abrirlo con FileProvider). */
suspend fun downloadZipToCache(context: Context, taskId: String?): File {
    val body = ApiClient.api().downloadZip(taskId = taskId)
    val file = File(context.cacheDir, "wplace_backup.zip")
    body.byteStream().use { input -> file.outputStream().use { input.copyTo(it) } }
    return file
}
