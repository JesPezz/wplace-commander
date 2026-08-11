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
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.TaskInfo
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel

@Composable
fun RadarScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val status by vm.status.collectAsState()

    LaunchedEffect(Unit) { vm.refreshStatus() }

    val tasks = status?.tasks ?: emptyList()

    Column(modifier = modifier.fillMaxSize()) {
        // encabezado del sistema
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
                    TaskCard(task, vm)
                }
            }
        }
    }
}

@Composable
private fun TaskCard(task: TaskInfo, vm: WPlaceViewModel) {
    val running = task.status.equals("running", ignoreCase = true) || task.status.equals("active", ignoreCase = true)
    val color = when {
        running -> Color(0xFF2E7D32)
        task.status.equals("done", ignoreCase = true) || task.status.equals("stopped", ignoreCase = true) -> Color(0xFF616161)
        else -> MaterialTheme.colorScheme.primary
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
        }
    }
}
