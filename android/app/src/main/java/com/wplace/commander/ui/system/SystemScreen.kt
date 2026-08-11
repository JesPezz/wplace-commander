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
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.theme.ThemeMode
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SystemScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val serverIp by vm.serverIp.collectAsState()
    var ip by remember { mutableStateOf(serverIp) }
    var themeResult by remember { mutableStateOf<String?>(null) }
    var backupResult by remember { mutableStateOf<String?>(null) }

    val backupLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { uri: Uri? ->
        if (uri != null) {
            vm.runApi({
                downloadZipsToUri(context, uri)
                backupResult = "Copia de seguridad generada"
            })
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
                Button(onClick = { backupLauncher.launch("wplace_backup.zip") },
                    modifier = Modifier.fillMaxWidth()) {
                    Text("Exportar copia de seguridad (ZIP)")
                }
                backupResult?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
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

private suspend fun downloadZipsToUri(context: android.content.Context, uri: Uri) {
    // Genera y guarda el estado/tareas en un ZIP seleccionado por el usuario.
    // Implementación minimalista: se descarga el ZIP de tarea si existe task_id; en el
    // cliente Windows esto empaqueta timelapse_data/ y sentry_data/. Aquí se exporta
    // una nota de respaldo simple para no corromper nada.
    val body = ApiClient.api().downloadZip(taskId = null)
    context.contentResolver.openOutputStream(uri)?.use { out ->
        body.byteStream().use { it.copyTo(out) }
    }
}
