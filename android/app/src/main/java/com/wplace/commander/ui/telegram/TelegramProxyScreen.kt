package com.wplace.commander.ui.telegram

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.ProxySetRequest
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TelegramProxyScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val api = ApiClient.api()
    var tab by remember { mutableStateOf(0) }

    Column(modifier = modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = tab) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Telegram") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Proxy") })
        }

        when (tab) {
            0 -> TelegramTab(api, vm)
            1 -> ProxyTab(api, vm)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TelegramTab(api: com.wplace.commander.network.WPlaceApi, vm: WPlaceViewModel) {
    var token by remember { mutableStateOf("") }
    var chat by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("") }

    val context = androidx.compose.ui.platform.LocalContext.current

    LaunchedEffect(Unit) {
        token = ApiClient.getTgToken(context)
        chat = ApiClient.getTgChat(context)
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Telegram", style = MaterialTheme.typography.titleLarge)
        Text("Credenciales globales: valen para todas las tareas, misiones y el planificador.",
            style = MaterialTheme.typography.bodyMedium)
        OutlinedTextField(value = token, onValueChange = { token = it },
            label = { Text("Bot token") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = chat, onValueChange = { chat = it },
            label = { Text("Chat ID") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Button(onClick = {
            ApiClient.saveTgCreds(context, token, chat)
            status = "Credenciales globales guardadas"
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Guardar credenciales globales")
        }
        status?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        Text("Estas credenciales se usarán automáticamente al crear misiones y activar el planificador.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProxyTab(api: com.wplace.commander.network.WPlaceApi, vm: WPlaceViewModel) {
    var enabled by remember { mutableStateOf(false) }
    var host by remember { mutableStateOf("") }
    var port by remember { mutableStateOf("") }
    var user by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            val s = api.proxyStatus()
            enabled = s.config?.enabled ?: false
            host = s.config?.host ?: ""
            port = s.config?.port ?: ""
            user = s.config?.user ?: ""
        } catch (_: Exception) {}
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Proxy", style = MaterialTheme.typography.titleLarge)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = enabled, onCheckedChange = { enabled = it })
            Spacer(Modifier.width(8.dp))
            Text(if (enabled) "Proxy activo" else "Proxy desactivado")
        }
        OutlinedTextField(value = host, onValueChange = { host = it },
            label = { Text("Host") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = port, onValueChange = { port = it },
            label = { Text("Puerto") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(value = user, onValueChange = { user = it },
            label = { Text("Usuario") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Button(onClick = {
            result = null
            val req = ProxySetRequest(enabled, host.trim(), port.trim(), user.trim())
            vm.runApi({
                val r = api.proxySet(req)
                result = r.message.ifBlank { "Proxy actualizado" }
            }) { vm.refreshStatus() }
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Guardar proxy")
        }
        OutlinedButton(onClick = {
            result = null
            vm.runApi({
                val r = api.proxyCheckIp()
                result = r.message.ifBlank { r.sanitized }
            })
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Comprobar IP del proxy")
        }
        result?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
}
