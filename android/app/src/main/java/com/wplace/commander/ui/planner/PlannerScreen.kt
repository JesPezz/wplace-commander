package com.wplace.commander.ui.planner

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.PlanSetRequest
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlannerScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val api = ApiClient.api()
    var segundos by remember { mutableStateOf("") }
    var pxObjetivo by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var chatId by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Planificador", style = MaterialTheme.typography.titleLarge)
        Text("Configura la cuota y el control de descarga del servidor.",
            style = MaterialTheme.typography.bodyMedium)

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(value = segundos, onValueChange = { segundos = it },
                    label = { Text("Segundos de espera") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = pxObjetivo, onValueChange = { pxObjetivo = it },
                    label = { Text("Píxeles objetivo") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = token, onValueChange = { token = it },
                    label = { Text("Token de Telegram") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = chatId, onValueChange = { chatId = it },
                    label = { Text("Chat ID") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Button(onClick = {
                    result = null
                    val req = PlanSetRequest(
                        segundos_espera = segundos.toLongOrNull() ?: 0,
                        px_objetivo = pxObjetivo.toIntOrNull() ?: 0,
                        token = token.trim(),
                        chat_id = chatId.trim(),
                    )
                    vm.runApi({ api.planSet(req) }) { result = "Planificación guardada" }
                }, modifier = Modifier.fillMaxWidth()) {
                    Text("Guardar planificación")
                }
                result?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            }
        }
    }
}
