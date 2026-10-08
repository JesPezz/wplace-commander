package com.wplace.commander.ui.telegram

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.ProxySetRequest
import com.wplace.commander.data.TelegramSetRequest
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.theme.NeumorphicButton
import com.wplace.commander.ui.theme.NeumorphicSegmented
import com.wplace.commander.ui.theme.NeumorphicTextField
import com.wplace.commander.ui.theme.NeumorphicTextButton
import com.wplace.commander.ui.theme.liveRegion

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TelegramProxyScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val api = ApiClient.api()
    var tab by remember { mutableStateOf(0) }

    Column(modifier = modifier.fillMaxSize()) {
        NeumorphicSegmented(
            options = listOf("Telegram", "Proxy"),
            selectedIndex = tab,
            onSelect = { tab = it },
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
        )

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
        try {
            val s = api.telegramStatus()
            if (s.token.isNotBlank() || s.chat_id.isNotBlank()) {
                token = s.token
                chat = s.chat_id
                ApiClient.saveTgCreds(context, s.token, s.chat_id)
            }
        } catch (_: Exception) {}
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Telegram", style = MaterialTheme.typography.titleLarge)
        Text("Credenciales globales: valen para todas las tareas, misiones y el planificador.",
            style = MaterialTheme.typography.bodyMedium)
        NeumorphicTextField(value = token, onValueChange = { token = it },
            label = "Bot token", modifier = Modifier.fillMaxWidth())
        NeumorphicTextField(value = chat, onValueChange = { chat = it },
            label = "Chat ID", modifier = Modifier.fillMaxWidth())
        NeumorphicButton(onClick = {
            ApiClient.saveTgCreds(context, token, chat)
            status = "Guardando…"
            vm.runApi({
                val r = api.telegramSet(TelegramSetRequest(token.trim(), chat.trim()))
                status = r.message.ifBlank { "Credenciales globales guardadas" }
            }, {
                if (status == "Guardando…") status = "Credenciales globales guardadas (servidor no accesible)"
            })
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Guardar credenciales globales")
        }
        status?.let { Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.liveRegion()) }
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
            Switch(checked = enabled, onCheckedChange = { enabled = it },
                modifier = Modifier.semantics { contentDescription = "Usar proxy" })
            Spacer(Modifier.width(8.dp))
            Text(if (enabled) "Proxy activo" else "Proxy desactivado")
        }
        NeumorphicTextField(value = host, onValueChange = { host = it },
            label = "Host", modifier = Modifier.fillMaxWidth())
        NeumorphicTextField(value = port, onValueChange = { port = it },
            label = "Puerto", modifier = Modifier.fillMaxWidth())
        NeumorphicTextField(value = user, onValueChange = { user = it },
            label = "Usuario", modifier = Modifier.fillMaxWidth())
        NeumorphicButton(onClick = {
            result = null
            val req = ProxySetRequest(enabled, host.trim(), port.trim(), user.trim())
            vm.runApi({
                val r = api.proxySet(req)
                result = r.message.ifBlank { "Proxy actualizado" }
            }) { vm.refreshStatus() }
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Guardar proxy")
        }
        NeumorphicTextButton(onClick = {
            result = null
            vm.runApi({
                val r = api.proxyCheckIp()
                result = r.message.ifBlank { r.sanitized }
            })
        }, modifier = Modifier.fillMaxWidth()) {
            Text("Comprobar IP del proxy")
        }
        result?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.liveRegion()) }
    }
}
