package com.wplace.commander.ui.mission

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.Coords
import com.wplace.commander.data.CreateTaskRequest
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    var name by remember { mutableStateOf("") }
    var xs by remember { mutableStateOf("") }
    var ys by remember { mutableStateOf("") }
    var xe by remember { mutableStateOf("") }
    var ye by remember { mutableStateOf("") }
    var saveTl by remember { mutableStateOf(true) }
    var sentry by remember { mutableStateOf(false) }
    var interval by remember { mutableStateOf("60") }
    var duration by remember { mutableStateOf("0") }
    var limitMb by remember { mutableStateOf("500") }
    var alertPct by remember { mutableStateOf("90") }
    var tgToken by remember { mutableStateOf("") }
    var tgChat by remember { mutableStateOf("") }
    var preview by remember { mutableStateOf(true) }
    var result by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    val coords = runCatching {
        Region(xs.toLong(), ys.toLong(), xe.toLong(), ye.toLong())
    }.getOrNull()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Nueva misión", style = MaterialTheme.typography.titleLarge)

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it },
                    label = { Text("Nombre de la misión") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = xs, onValueChange = { xs = it },
                        label = { Text("X inicio") }, singleLine = true,
                        modifier = Modifier.weight(1f))
                    OutlinedTextField(value = ys, onValueChange = { ys = it },
                        label = { Text("Y inicio") }, singleLine = true,
                        modifier = Modifier.weight(1f))
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(value = xe, onValueChange = { xe = it },
                        label = { Text("X fin") }, singleLine = true,
                        modifier = Modifier.weight(1f))
                    OutlinedTextField(value = ye, onValueChange = { ye = it },
                        label = { Text("Y fin") }, singleLine = true,
                        modifier = Modifier.weight(1f))
                }

                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Switch(checked = saveTl, onCheckedChange = { saveTl = it })
                    Spacer(Modifier.width(8.dp))
                    Text("Guardar timelapse")
                }
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Switch(checked = sentry, onCheckedChange = { sentry = it })
                    Spacer(Modifier.width(8.dp))
                    Text("Modo centinela (detección de cambios)")
                }

                OutlinedTextField(value = interval, onValueChange = { interval = it },
                    label = { Text("Intervalo (minutos)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = duration, onValueChange = { duration = it },
                    label = { Text("Duración (horas, 0 = infinita)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = limitMb, onValueChange = { limitMb = it },
                    label = { Text("Límite de capturas (MB)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = alertPct, onValueChange = { alertPct = it },
                    label = { Text("Alerta de cuota (%)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = tgToken, onValueChange = { tgToken = it },
                    label = { Text("Token de Telegram (opcional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = tgChat, onValueChange = { tgChat = it },
                    label = { Text("Chat ID de Telegram (opcional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())

                Button(
                    onClick = {
                        val xS = xs.toLong(); val yS = ys.toLong()
                        val xE = xe.toLong(); val yE = ye.toLong()
                        val req = CreateTaskRequest(
                            name = name,
                            coords = Coords(xS, yS, xE, yE),
                            source = "WPlace",
                            save_timelapse = saveTl,
                            sentry = sentry,
                            interval = interval.toIntOrNull() ?: 60,
                            duration_hours = duration.toDoubleOrNull() ?: 0.0,
                            limit_mb = limitMb.toIntOrNull() ?: 500,
                            alert_pct = alertPct.toDoubleOrNull() ?: 90.0,
                            tg_token = tgToken.trim(),
                            tg_chat = tgChat.trim(),
                        )
                        busy = true; result = null
                        vm.runApi({
                            val resp = ApiClient.api().createTask(req)
                            result = "Misión creada: ${resp.task_id} (${resp.status})"
                        }, onDone = { busy = false })
                    },
                    enabled = coords != null && name.isNotBlank() && !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (busy) "Creando…" else "Crear misión")
                }
                result?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            }
        }

        Text("Vista previa", style = MaterialTheme.typography.titleLarge)
        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Switch(checked = preview, onCheckedChange = { preview = it })
            Spacer(Modifier.width(8.dp))
            Text("Mostrar tiles de la región")
        }
        if (preview && coords != null) {
            Card(modifier = Modifier.fillMaxWidth().height(380.dp)) {
                TileViewer(coords = coords, modifier = Modifier.fillMaxSize())
            }
        } else if (coords == null) {
            Text("Introduce coordenadas válidas para ver la región.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
