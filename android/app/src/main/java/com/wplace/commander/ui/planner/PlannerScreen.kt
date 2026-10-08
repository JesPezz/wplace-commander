package com.wplace.commander.ui.planner

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.wplace.commander.data.PlanSetRequest
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.theme.NeumorphicButton
import com.wplace.commander.ui.theme.NeumorphicCard
import com.wplace.commander.ui.theme.NeumorphicProgress
import com.wplace.commander.ui.theme.NeumorphicTextField
import com.wplace.commander.ui.theme.liveRegion
import kotlinx.coroutines.delay
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlannerScreen(vm: WPlaceViewModel, modifier: Modifier = Modifier) {
    val api = ApiClient.api()
    val context = LocalContext.current
    val prefs = ApiClient.prefs(context)

    var actuales by remember { mutableStateOf("") }
    var maximos by remember { mutableStateOf(prefs.getString("pl_max", "7404") ?: "7404") }
    var objPct by remember { mutableStateOf(prefs.getString("pl_obj", "85") ?: "85") }
    var resPct by remember { mutableStateOf(prefs.getString("pl_res", "25") ?: "25") }
    var result by remember { mutableStateOf<String?>(null) }
    var warning by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    // Estado del plan activo en el servidor (progreso + cuenta regresiva)
    var planActive by remember { mutableStateOf(false) }
    var planExpired by remember { mutableStateOf(false) }
    var planRestante by remember { mutableStateOf(0L) }
    var planPxObjetivo by remember { mutableStateOf(0) }
    var planConfigTxt by remember { mutableStateOf("") }
    var planToken by remember { mutableStateOf("") }
    var planChatId by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        var lastActive = false
        while (true) {
            try {
                val p = api.planStatus()
                planActive = p.active
                planExpired = p.expired
                planRestante = p.restante.toLong()
                planPxObjetivo = p.px_objetivo
                planConfigTxt = p.config_txt
                planToken = p.token
                planChatId = p.chat_id
                if (p.active && !p.expired) {
                    if (p.token.isNotBlank()) {
                        ApiClient.saveTgCreds(context, p.token, p.chat_id)
                    }
                    if (!lastActive) {
                        val pxActuales = maxOf(0, p.px_objetivo - (p.restante.toLong() / 30).toInt())
                        if (actuales.isBlank()) actuales = pxActuales.toString()
                    }
                }
                lastActive = p.active && !p.expired
            } catch (_: Exception) {}
            delay(3000)
        }
    }

    val maxPx = maximos.toDoubleOrNull() ?: 0.0
    val pxActualesCalc = if (planActive && !planExpired)
        maxOf(0, planPxObjetivo - (planRestante / 30).toInt())
    else 0
    val progress = if (maxPx > 0) (pxActualesCalc / maxPx).toFloat().coerceIn(0f, 1f) else 0f

    Column(
        modifier = modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Planificador", style = MaterialTheme.typography.titleLarge)
        Text("Calcula la alerta táctica de la reserva y su cronograma.",
            style = MaterialTheme.typography.bodyMedium)

        NeumorphicCard {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                NeumorphicTextField(value = actuales, onValueChange = { actuales = it },
                    label = "Píxeles Actuales (Reserva)", modifier = Modifier.fillMaxWidth())
                NeumorphicTextField(value = maximos, onValueChange = { maximos = it },
                    label = "Capacidad Máxima", modifier = Modifier.fillMaxWidth())
                NeumorphicTextField(value = objPct, onValueChange = { objPct = it },
                    label = "Objetivo de Disparo (%)", modifier = Modifier.fillMaxWidth())
                NeumorphicTextField(value = resPct, onValueChange = { resPct = it },
                    label = "Reserva de Defensa (%)", modifier = Modifier.fillMaxWidth())

                NeumorphicButton(
                    onClick = {
                        result = null; warning = null; busy = true
                        val actualesV = actuales.toIntOrNull()
                        val maximosV = maximos.toIntOrNull()
                        val objV = objPct.toFloatOrNull()
                        val resV = resPct.toFloatOrNull()
                        if (actualesV == null || maximosV == null || maximosV <= 0 || objV == null || resV == null) {
                            warning = "Revisa los valores: deben ser numéricos y válidos."
                            busy = false
                            return@NeumorphicButton
                        }
                        // Persistencia de la configuración de la UI
                        prefs.edit().putString("pl_max", maximos.toString())
                            .putString("pl_obj", objPct.toString())
                            .putString("pl_res", resPct.toString()).apply()

                        val pxObjetivo = (maximosV * (objV / 100f)).toInt()
                        val pxReserva = (maximosV * (resV / 100f)).toInt()
                        val pxGastar = pxObjetivo - pxReserva
                        val pxFaltantes = maxOf(0, pxObjetivo - actualesV)
                        val segundosEspera = pxFaltantes * 30L
                        val cal = Calendar.getInstance().apply { timeInMillis = System.currentTimeMillis() + segundosEspera * 1000 }
                        val fecha = "%02d/%02d/%04d a las %02d:%02d:%02d".format(
                            cal.get(Calendar.DAY_OF_MONTH), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.YEAR),
                            cal.get(Calendar.HOUR_OF_DAY), cal.get(Calendar.MINUTE), cal.get(Calendar.SECOND))
                        val horasMargen = ((maximosV - pxObjetivo) * 30) / 3600.0

                        val txt = buildString {
                            append("🎯 Objetivo a alcanzar: $pxObjetivo px (${objV.toInt()}%)\n")
                            append("🛡️ Reserva a dejar: $pxReserva px (${resV.toInt()}%)\n")
                            append("🖌️ Píxeles a pintar por sesión: $pxGastar px\n\n")
                            append("⏱️ Tiempo de recarga estimado: ${"%.2f".format(segundosEspera / 3600.0)} horas\n")
                            append("⏰ Hora de notificación: $fecha\n")
                            append("🔋 Margen de inactividad antes de perder píxeles: ${"%.2f".format(horasMargen)} horas")
                        }
                        result = txt

                        val token = ApiClient.getTgToken(context).ifBlank { planToken }
                        val chatId = ApiClient.getTgChat(context).ifBlank { planChatId }
                        if (token.isBlank() || chatId.isBlank()) {
                            warning = "Configura las credenciales globales en la pestaña Telegram para recibir la alerta."
                            busy = false
                            return@NeumorphicButton
                        }
                        if (pxFaltantes > 0) {
                            vm.runApi({
                                val req = PlanSetRequest(
                                    segundos_espera = segundosEspera,
                                    px_objetivo = pxObjetivo,
                                    token = token,
                                    chat_id = chatId,
                                    config_txt = txt,
                                )
                                api.planSet(req)
                                result = "$txt\n\n✅ Alerta activada en el servidor."
                            }, onDone = { busy = false })
                        } else {
                            warning = "Ya tienes suficientes píxeles: el objetivo ya está alcanzado."
                            busy = false
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (busy) "Calculando…" else "CALCULAR Y ACTIVAR ALERTA")
                }
                warning?.let { Text("⚠️ $it", color = MaterialTheme.colorScheme.error, modifier = Modifier.liveRegion()) }
                result?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.liveRegion()) }
            }
        }

        // Barra de progreso y cuenta regresiva
        if (planActive) {
            NeumorphicCard {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Progreso de generación", style = MaterialTheme.typography.titleMedium)
                    NeumorphicProgress(
                        progress = progress,
                        modifier = Modifier.fillMaxWidth(),
                        contentDescription = "Progreso de generación de píxeles",
                    )
                    val pct = if (maxPx > 0) (pxActualesCalc / maxPx * 100.0) else 0.0
                    Text("Generación: $pxActualesCalc / ${maxPx.toInt()} px (${"%.1f".format(pct)}%)",
                        style = MaterialTheme.typography.bodyMedium)
                    if (planExpired) {
                        Text("✅ ¡TIEMPO CUMPLIDO - LISTO PARA PINTAR!",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary)
                    } else {
                        val hrs = planRestante / 3600
                        val mins = (planRestante % 3600) / 60
                        Text("⏳ Cuenta regresiva: faltan ${hrs}h ${mins}m",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }

        // Resultados y cronograma (sincronizado con el servidor)
        NeumorphicCard {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Resultados y Cronograma", style = MaterialTheme.typography.titleMedium)
                val txt = if (planActive && planConfigTxt.isNotBlank()) planConfigTxt else result
                Text(
                    txt ?: "Ingresa tus datos para generar el plan…",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (planActive) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.liveRegion(),
                )
            }
        }
    }
}
