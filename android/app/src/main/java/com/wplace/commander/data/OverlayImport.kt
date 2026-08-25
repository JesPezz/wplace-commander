package com.wplace.commander.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.math.PI
import kotlin.math.asinh
import kotlin.math.roundToLong
import kotlin.math.tan

/** Importa overlays exportados por WPlace (.wplace.json) convirtiendo sus bounds
 *  geográficos (north/south/west/east) a píxeles absolutos del lienzo.
 *
 *  Proyección Web Mercator sobre un mundo de 2048000px (misma que usa WPlace).
 */
object OverlayImporter {

    const val MAP_SIZE = 2_048_000.0

    data class ImportedRegion(
        val name: String,
        val xStart: Long,
        val yStart: Long,
        val xEnd: Long,
        val yEnd: Long,
    )

    private fun latLngToPixel(lat: Double, lng: Double): Pair<Long, Long> {
        val gx = (lng + 180.0) / 360.0 * MAP_SIZE
        val n = asinh(tan(Math.toRadians(lat)))
        val gy = (MAP_SIZE / 2.0) * (1.0 - n / PI)
        return gx.roundToLong() to gy.roundToLong()
    }

    fun parseOverlay(content: String): ImportedRegion {
        val root = Json.parseToJsonElement(content).jsonObject
        val bounds = root["bounds"]?.jsonObject
            ?: throw IllegalArgumentException("El archivo no tiene un campo 'bounds' válido")
        val north = bounds["north"]?.jsonPrimitive?.double ?: throw IllegalArgumentException("Falta 'bounds.north'")
        val south = bounds["south"]?.jsonPrimitive?.double ?: throw IllegalArgumentException("Falta 'bounds.south'")
        val west = bounds["west"]?.jsonPrimitive?.double ?: throw IllegalArgumentException("Falta 'bounds.west'")
        val east = bounds["east"]?.jsonPrimitive?.double ?: throw IllegalArgumentException("Falta 'bounds.east'")

        val (x1, y1) = latLngToPixel(north, west)
        val (x2, y2) = latLngToPixel(south, east)

        val rawName = root["name"]?.jsonPrimitive?.contentOrNull
        val name = rawName?.removeSuffix(".png")?.ifBlank { null } ?: "Overlay"

        return ImportedRegion(
            name = name,
            xStart = minOf(x1, x2),
            yStart = minOf(y1, y2),
            xEnd = maxOf(x1, x2),
            yEnd = maxOf(y1, y2),
        )
    }
}