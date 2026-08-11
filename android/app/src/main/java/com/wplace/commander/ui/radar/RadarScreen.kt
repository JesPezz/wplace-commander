package com.wplace.commander.ui.radar

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import com.wplace.commander.data.FavoriteMission
import com.wplace.commander.data.FavoritesStore
import com.wplace.commander.data.TaskInfo
import com.wplace.commander.data.UpdateTaskRequest
import com.wplace.commander.data.buildConfigJson
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.util.downloadZipToUri
import kotlinx.serialization.json.JsonObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RadarScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val status by vm.status.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(Unit) { vm.refreshStatus() }

    val tasks = status?.tasks ?: emptyList()

    Column(modifier = modifier.fillMaxSize()) {
        val sys = status?.system
        if (sys != null) {
            Text("CPU ${"%.0f".format(sys.cpu)}%  •  RAM ${"%.0f".format(sys.ram)}%",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
        }

        if (tasks.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Sin tareas. Crea una desde Misión.")
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(tasks, key = { it.id }) { task ->
                    TaskCard(task, vm, context)
                }
            }
        }
    }
}

@Composable
private fun TaskCard(task: TaskInfo, vm: WPlaceViewModel, context: android.content.Context) {
    val running = task.status.equals("running", ignoreCase = true) || task.status.equals("active", ignoreCase = true)
    val color = when {
        running -> Color(0xFF2E7D32)
        task.status.equals("done", ignoreCase = true) || task.status.equals("stopped", ignoreCase = true) -> Color(0xFF616161)
        else -> MaterialTheme.colorScheme.primary
    }

    var feedback by remember { mutableStateOf<String?>(null) }
    var showEdit by remember { mutableStateOf(false) }
    var editBusy by remember { mutableStateOf(false) }

    // Estados del diálogo de edición
    var eName by remember { mutableStateOf(task.config?.string("name") ?: task.name) }
    var eInterval by remember { mutableStateOf((task.config?.number("interval") ?: 1.0).toString()) }
    var eAlert by remember { mutableStateOf((task.config?.number("alert_pct") ?: 5.0).toString()) }
    var eMb by remember { mutableStateOf((task.config?.number("limit_mb") ?: 1000.0).toString()) }
    var eDur by remember { mutableStateOf((task.config?.number("duration_hours") ?: 0.0).toString()) }
    var eTl by remember { mutableStateOf(task.config?.boolean("save_timelapse") ?: true) }
    var eSent by remember { mutableStateOf(task.config?.boolean("sentry") ?: false) }

    val zipLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { uri: Uri? ->
        if (uri != null) {
            vm.runApi({ downloadZipToUri(context, uri, task.id) }) {
                feedback = "ZIP descargado"
            }
        }
    }

    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(color, androidx.compose.foundation.shape.CircleShape))
                Spacer(Modifier.width(8.dp))
                Text(task.name, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            }
            Text("ID ${task.id}  •  capturas: ${task.captures}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (task.diff_actual.isNotBlank()) {
                Text("Cambio: ${task.diff_actual} (${task.diff_px} px)",
                    style = MaterialTheme.typography.bodySmall)
            }
            if (task.restante.isNotBlank()) {
                Text("Restante: ${task.restante}", style = MaterialTheme.typography.bodySmall)
            }
            if (task.start_str.isNotBlank()) {
                Text("Inicio: ${task.start_str}", style = MaterialTheme.typography.bodySmall)
            }
            feedback?.let { Text(it, color = MaterialTheme.colorScheme.primary) }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (running) {
                    Button(onClick = { vm.runApi({ ApiClient.api().stopTask(task.id) }) { vm.refreshStatus() } }) {
                        Text("Detener")
                    }
                } else {
                    Button(onClick = { vm.runApi({ ApiClient.api().startTask(task.id) }) { vm.refreshStatus() } }) {
                        Text("Iniciar")
                    }
                }
                OutlinedButton(onClick = {
                    vm.runApi({ ApiClient.api().deleteTask(task.id) }) { vm.refreshStatus() }
                }) {
                    Text("Eliminar")
                }
            }

            // Acciones: favorito, editar y ZIP
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    val cfg = task.config
                    val xs = cfg?.long("x_start")
                    val ys = cfg?.long("y_start")
                    val xe = cfg?.long("x_end")
                    val ye = cfg?.long("y_end")
                    if (xs == null || ys == null || xe == null || ye == null) {
                        feedback = "La tarea no tiene coordenadas para guardar"
                    } else {
                        val favs = FavoritesStore.load(context).toMutableMap()
                        val key = task.name
                        favs[key] = FavoriteMission(
                            name = task.name,
                            x_start = xs, y_start = ys, x_end = xe, y_end = ye,
                            save_timelapse = cfg.boolean("save_timelapse") ?: true,
                            sentry = cfg.boolean("sentry") ?: false,
                            interval = cfg.number("interval")?.toInt() ?: 60,
                            duration_hours = cfg.number("duration_hours") ?: 0.0,
                            limit_mb = cfg.number("limit_mb")?.toInt() ?: 500,
                            alert_pct = cfg.number("alert_pct") ?: 90.0,
                        )
                        FavoritesStore.save(context, favs)
                        feedback = "⭐ Guardada como favorita"
                    }
                }) {
                    Text("⭐")
                }
                OutlinedButton(onClick = {
                    eName = task.config?.string("name") ?: task.name
                    eInterval = (task.config?.number("interval") ?: 1.0).toString()
                    eAlert = (task.config?.number("alert_pct") ?: 5.0).toString()
                    eMb = (task.config?.number("limit_mb") ?: 1000.0).toString()
                    eDur = (task.config?.number("duration_hours") ?: 0.0).toString()
                    eTl = task.config?.boolean("save_timelapse") ?: true
                    eSent = task.config?.boolean("sentry") ?: false
                    showEdit = true
                }) {
                    Text("✏️")
                }
                OutlinedButton(onClick = {
                    feedback = null
                    zipLauncher.launch("wplace_task_${task.id}.zip")
                }) {
                    Text("📥 ZIP")
                }
            }
        }
    }

    if (showEdit) {
        AlertDialog(
            onDismissRequest = { showEdit = false },
            title = { Text("Editar tarea #${task.id}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = eName, onValueChange = { eName = it },
                        label = { Text("Nombre") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = eInterval, onValueChange = { eInterval = it },
                        label = { Text("Intervalo (min)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = eAlert, onValueChange = { eAlert = it },
                        label = { Text("Alerta de cuota (%)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = eMb, onValueChange = { eMb = it },
                        label = { Text("Límite (MB)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = eDur, onValueChange = { eDur = it },
                        label = { Text("Duración (horas, 0 = inf)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Switch(checked = eTl, onCheckedChange = { eTl = it })
                        Spacer(Modifier.width(8.dp))
                        Text("Guardar timelapse")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Switch(checked = eSent, onCheckedChange = { eSent = it })
                        Spacer(Modifier.width(8.dp))
                        Text("Modo centinela")
                    }
                }
            },
            confirmButton = {
                Button(enabled = !editBusy, onClick = {
                    editBusy = true
                    val config = buildConfigJson(mapOf(
                        "name" to eName,
                        "interval" to (eInterval.toFloatOrNull() ?: 1f),
                        "alert_pct" to (eAlert.toFloatOrNull() ?: 5f),
                        "limit_mb" to (eMb.toFloatOrNull() ?: 1000f),
                        "duration_hours" to (eDur.toFloatOrNull() ?: 0f),
                        "save_timelapse" to eTl,
                        "sentry" to eSent,
                    ))
                    vm.runApi({
                        ApiClient.api().updateTask(UpdateTaskRequest(task.id.toInt(), config))
                    }, onDone = {
                        editBusy = false
                        showEdit = false
                        vm.refreshStatus()
                    })
                }) { Text("Guardar") }
            },
            dismissButton = {
                TextButton(onClick = { showEdit = false }) { Text("Cancelar") }
            },
        )
    }
}

// Accesos auxiliares a JsonObject
private fun JsonObject.string(key: String): String? = this[key]?.let {
    when (it) {
        is kotlinx.serialization.json.JsonPrimitive -> it.content
        else -> it.toString().removeSurrounding("\"")
    }
}
private fun JsonObject.number(key: String): Double? = this[key]?.let {
    when (it) {
        is kotlinx.serialization.json.JsonPrimitive -> it.content.toDoubleOrNull()
        else -> null
    }
}
private fun JsonObject.boolean(key: String): Boolean? = this[key]?.let {
    when (it) {
        is kotlinx.serialization.json.JsonPrimitive -> it.content.toBooleanStrictOrNull()
        else -> null
    }
}
private fun JsonObject.long(key: String): Long? = this[key]?.let {
    when (it) {
        is kotlinx.serialization.json.JsonPrimitive -> it.content.toLongOrNull()
        else -> null
    }
}
