package com.wplace.commander.ui.mission

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import com.wplace.commander.data.Coords
import com.wplace.commander.data.CreateTaskRequest
import com.wplace.commander.data.FavoriteMission
import com.wplace.commander.data.FavoritesStore
import com.wplace.commander.data.OverlayImporter
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val context = LocalContext.current
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
    var showPreview by remember { mutableStateOf(false) }
    var previewRefresh by remember { mutableIntStateOf(0) }
    var result by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    // Favoritos
    var favorites by remember { mutableStateOf(FavoritesStore.load(context)) }
    var selectedFav by remember { mutableStateOf<String?>(null) }
    var favMenuOpen by remember { mutableStateOf(false) }
    var favDialog by remember { mutableStateOf(false) }
    var favName by remember { mutableStateOf("") }
    var favFeedback by remember { mutableStateOf<String?>(null) }

    val coords = runCatching {
        Region(xs.toLong(), ys.toLong(), xe.toLong(), ye.toLong())
    }.getOrNull()

    fun persistFavorites() { FavoritesStore.save(context, favorites) }

    val overlayLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            try {
                val content = context.contentResolver.openInputStream(uri)
                    ?.bufferedReader()?.use { it.readText() }
                    ?: throw IllegalArgumentException("No se pudo leer el archivo")
                val reg = OverlayImporter.parseOverlay(content)
                name = reg.name
                xs = reg.xStart.toString()
                ys = reg.yStart.toString()
                xe = reg.xEnd.toString()
                ye = reg.yEnd.toString()
                val fav = FavoriteMission(
                    name = reg.name,
                    x_start = reg.xStart,
                    y_start = reg.yStart,
                    x_end = reg.xEnd,
                    y_end = reg.yEnd,
                    save_timelapse = saveTl,
                    sentry = sentry,
                    interval = interval.toIntOrNull() ?: 60,
                    duration_hours = duration.toDoubleOrNull() ?: 0.0,
                    limit_mb = limitMb.toIntOrNull() ?: 500,
                    alert_pct = alertPct.toDoubleOrNull() ?: 90.0,
                )
                favorites = favorites + (reg.name to fav)
                selectedFav = reg.name
                persistFavorites()
                favFeedback = "Overlay importado y guardado en favoritos"
            } catch (e: Exception) {
                favFeedback = "Error al importar: ${e.message}"
            }
        }
    }

    fun loadFavorite(f: FavoriteMission) {
        name = f.name
        xs = f.x_start.toString()
        ys = f.y_start.toString()
        xe = f.x_end.toString()
        ye = f.y_end.toString()
        saveTl = f.save_timelapse
        sentry = f.sentry
        interval = f.interval.toString()
        duration = f.duration_hours.toString()
        limitMb = f.limit_mb.toString()
        alertPct = f.alert_pct.toString()
        showPreview = false
        result = null
    }

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

                // Favoritos
                Text("Favoritos", style = MaterialTheme.typography.titleMedium)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.weight(1f)) {
                        OutlinedButton(
                            onClick = { favMenuOpen = true },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(selectedFav ?: "Seleccionar favorito…")
                        }
                        DropdownMenu(expanded = favMenuOpen, onDismissRequest = { favMenuOpen = false }) {
                            if (favorites.isEmpty()) {
                                DropdownMenuItem(text = { Text("Sin favoritos guardados") }, onClick = { favMenuOpen = false })
                            }
                            favorites.forEach { (key, f) ->
                                DropdownMenuItem(
                                    text = { Text(key) },
                                    onClick = {
                                        selectedFav = key
                                        loadFavorite(f)
                                        favMenuOpen = false
                                    },
                                )
                            }
                        }
                    }
                    OutlinedButton(onClick = { favName = name.ifBlank { "Zona" }; favDialog = true }) {
                        Text("💾 Guardar")
                    }
                    OutlinedButton(
                        onClick = {
                            val key = selectedFav ?: return@OutlinedButton
                            favorites = favorites - key
                            selectedFav = null
                            persistFavorites()
                            favFeedback = "Favorito borrado"
                        },
                        enabled = selectedFav != null,
                    ) {
                        Text("🗑")
                    }
                }
                favFeedback?.let { Text(it, color = MaterialTheme.colorScheme.primary) }

                OutlinedButton(
                    onClick = { overlayLauncher.launch(arrayOf("*/*")) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("📥 Importar overlay (.wplace)")
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(checked = saveTl, onCheckedChange = { saveTl = it })
                    Spacer(Modifier.width(8.dp))
                    Text("Guardar timelapse")
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
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

                Text("Las alertas de Telegram usan las credenciales globales de la pestaña Telegram.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)

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
                            tg_token = ApiClient.getTgToken(context),
                            tg_chat = ApiClient.getTgChat(context),
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

        // Vista previa bajo demanda (se refresca cada vez que se abre)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(onClick = {
                showPreview = !showPreview
                if (showPreview) previewRefresh += 1
            }) {
                Text(if (showPreview) "Ocultar vista previa" else "📷 Vista previa")
            }
            if (showPreview && coords != null) {
                TextButton(onClick = { previewRefresh += 1 }) {
                    Text("🔄 Recargar")
                }
            }
        }
        if (showPreview && coords != null) {
            Card(modifier = Modifier.fillMaxWidth().height(380.dp)) {
                TileViewer(
                    coords = coords,
                    modifier = Modifier.fillMaxSize(),
                    refreshKey = previewRefresh,
                )
            }
        } else if (coords == null) {
            Text("Introduce coordenadas válidas para ver la región.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

    if (favDialog) {
        AlertDialog(
            onDismissRequest = { favDialog = false },
            title = { Text("Guardar favorito") },
            text = {
                OutlinedTextField(value = favName, onValueChange = { favName = it },
                    label = { Text("Nombre de la zona") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
            },
            confirmButton = {
                Button(onClick = {
                    val f = FavoriteMission(
                        name = name,
                        x_start = xs.toLongOrNull() ?: 0,
                        y_start = ys.toLongOrNull() ?: 0,
                        x_end = xe.toLongOrNull() ?: 0,
                        y_end = ye.toLongOrNull() ?: 0,
                        save_timelapse = saveTl,
                        sentry = sentry,
                        interval = interval.toIntOrNull() ?: 60,
                        duration_hours = duration.toDoubleOrNull() ?: 0.0,
                        limit_mb = limitMb.toIntOrNull() ?: 500,
                        alert_pct = alertPct.toDoubleOrNull() ?: 90.0,
                    )
                    val key = favName.trim().ifBlank { name.ifBlank { "Zona" } }
                    favorites = favorites + (key to f)
                    selectedFav = key
                    persistFavorites()
                    favDialog = false
                    favFeedback = "Favorito guardado"
                }) { Text("Guardar") }
            },
            dismissButton = {
                TextButton(onClick = { favDialog = false }) { Text("Cancelar") }
            },
        )
    }
}
