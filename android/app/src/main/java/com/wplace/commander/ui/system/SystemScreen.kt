package com.wplace.commander.ui.system

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.theme.ThemeMode
import com.wplace.commander.util.downloadZipToCache
import com.wplace.commander.util.downloadZipToUri
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SystemScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val serverIp by vm.serverIp.collectAsState()
    var ip by remember { mutableStateOf(serverIp) }
    var themeResult by remember { mutableStateOf<String?>(null) }
    var backupResult by remember { mutableStateOf<String?>(null) }
    var backupBusy by remember { mutableStateOf(false) }
    var cachedZip by remember { mutableStateOf<File?>(null) }

    val backupLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { uri: Uri? ->
        if (uri != null) {
            backupBusy = true; backupResult = null
            vm.runApi({
                // Guarda una copia local (cache) para poder abrirla y además copia al destino elegido.
                val local = downloadZipToCache(context, taskId = null)
                cachedZip = local
                downloadZipToUri(context, uri, taskId = null)
                backupResult = "Copia de seguridad generada"
            }, onDone = { backupBusy = false })
        }
    }

    fun openZip() {
        val file = cachedZip ?: return
        try {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/zip")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(intent)
        } catch (_: Exception) {
            backupResult = "No hay app para abrir el ZIP en el dispositivo"
        }
    }

    Column(
        modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Sistema", style = MaterialTheme.typography.titleLarge)

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Servidor", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = ip, onValueChange = { ip = it },
                    label = { Text("Dirección del servidor") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                Button(onClick = { vm.setServer(ip) }, modifier = Modifier.fillMaxWidth()) {
                    Text("Conectar")
                }
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Tema", style = MaterialTheme.typography.titleMedium)
                val current by vm.themeMode.collectAsState()
                val options = listOf(
                    Triple("auto", "Auto", ThemeMode.AUTO),
                    Triple("light", "Claro", ThemeMode.LIGHT),
                    Triple("dark", "Oscuro", ThemeMode.DARK),
                    Triple("high_contrast", "Alto contraste", ThemeMode.HIGH_CONTRAST),
                )
                options.forEach { (name, label, mode) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(
                            selected = current == mode,
                            onClick = { vm.setTheme(mode); themeResult = null },
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(label)
                    }
                }
                themeResult?.let { Text(it) }
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Respaldo", style = MaterialTheme.typography.titleMedium)
                Button(
                    onClick = { backupLauncher.launch("wplace_backup.zip") },
                    enabled = !backupBusy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (backupBusy) "Descargando…" else "Exportar copia de seguridad (ZIP)")
                }
                backupResult?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
                if (cachedZip != null) {
                    OutlinedButton(onClick = { openZip() }, modifier = Modifier.fillMaxWidth()) {
                        Text("Abrir ZIP")
                    }
                }
            }
        }

        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Zona de peligro", style = MaterialTheme.typography.titleMedium)
                OutlinedButton(onClick = { vm.runApi({
                    ApiClient.api().stopAll()
                    ApiClient.api().deleteTasks()
                }) { vm.refreshStatus() } }, modifier = Modifier.fillMaxWidth()) {
                    Text("Detener y eliminar todas las tareas")
                }
                OutlinedButton(onClick = { vm.runApi({
                    ApiClient.api().stopAll()
                    ApiClient.api().deletePhotos()
                }) { vm.refreshStatus() } }, modifier = Modifier.fillMaxWidth()) {
                    Text("Eliminar todas las fotos")
                }
            }
        }
    }
}
