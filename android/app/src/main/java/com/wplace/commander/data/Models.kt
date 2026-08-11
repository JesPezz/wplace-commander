package com.wplace.commander.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

@Serializable
data class Coords(
    val x_start: Long = 0,
    val y_start: Long = 0,
    val x_end: Long = 0,
    val y_end: Long = 0,
)

@Serializable
data class CreateTaskRequest(
    val name: String,
    val coords: Coords,
    val source: String = "WPlace",
    val save_timelapse: Boolean,
    val sentry: Boolean,
    val interval: Int,
    val duration_hours: Double,
    val limit_mb: Int,
    val alert_pct: Double,
    val tg_token: String = "",
    val tg_chat: String = "",
)

@Serializable
data class CreateTaskResponse(
    val status: String,
    val task_id: String = "",
)

@Serializable
data class SimpleResponse(
    val status: String? = null,
    val msg: String? = null,
    val message: String? = null,
)

@Serializable
data class StatusResponse(
    val status: String = "",
    val system: SystemInfo? = null,
    val tasks: List<TaskInfo> = emptyList(),
)

@Serializable
data class SystemInfo(
    val cpu: Double = 0.0,
    val ram: Double = 0.0,
)

@Serializable
data class TaskInfo(
    val id: String,
    val name: String,
    val source: String = "WPlace",
    val mode: String = "",
    val status: String = "",
    val captures: Int = 0,
    val restante: String = "",
    val diff_actual: String = "",
    val diff_px: Int = 0,
    val start_str: String = "",
    val config: JsonObject? = null,
)

@Serializable
data class UpdateTaskRequest(
    val id: Int,
    val config: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class PlanStatusResponse(
    val active: Boolean = false,
    val expired: Boolean = false,
    val restante: Double = 0.0,
    val px_objetivo: Int = 0,
    val config_txt: String = "",
)

@Serializable
data class ProxyStatusResponse(
    val status: String = "",
    val config: ProxyConfig? = null,
    val has_pass: Boolean = false,
    val sanitized: String = "",
)

@Serializable
data class ProxyConfig(
    val enabled: Boolean = false,
    val host: String = "",
    val port: String = "",
    val user: String = "",
)

@Serializable
data class ProxySetRequest(
    val enabled: Boolean,
    val host: String,
    val port: String,
    val user: String,
)

@Serializable
data class ProxyMessageResponse(
    val status: String = "",
    val message: String = "",
    val sanitized: String = "",
)

@Serializable
data class PlanSetRequest(
    val segundos_espera: Long,
    val px_objetivo: Int,
    val token: String,
    val chat_id: String,
    val config_txt: String = "",
)

@Serializable
data class FavoriteMission(
    val name: String = "",
    val x_start: Long = 0,
    val y_start: Long = 0,
    val x_end: Long = 0,
    val y_end: Long = 0,
    val save_timelapse: Boolean = true,
    val sentry: Boolean = false,
    val interval: Int = 60,
    val duration_hours: Double = 0.0,
    val limit_mb: Int = 500,
    val alert_pct: Double = 90.0,
)

/** Convierte un mapa simple de valores en un mapa de JsonElement para /tasks/update. */
fun buildConfigJson(map: Map<String, Any>): Map<String, JsonElement> =
    map.mapValues { (_, v) ->
        when (v) {
            is String -> JsonPrimitive(v)
            is Int -> JsonPrimitive(v)
            is Long -> JsonPrimitive(v)
            is Double -> JsonPrimitive(v)
            is Boolean -> JsonPrimitive(v)
            else -> JsonPrimitive(v.toString())
        }
    }
