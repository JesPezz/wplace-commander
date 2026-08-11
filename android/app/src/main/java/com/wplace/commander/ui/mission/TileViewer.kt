package com.wplace.commander.ui.mission

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.wplace.commander.network.ApiClient

data class Region(
    val xStart: Long,
    val yStart: Long,
    val xEnd: Long,
    val yEnd: Long,
)

/**
 * Visor de tiles WPlace con zoom (pinza) y paneo.
 * Cada tile son 1000x1000 px servidos por la fuente WPlace.
 * Solo se compone la subcuadrícula de tiles que solapa la región.
 *
 * @param refreshKey si cambia, se fuerza la recarga de las tiles
 *        (bustea la caché de Coil añadiendo un parámetro a la URL).
 */
@Composable
fun TileViewer(
    coords: Region,
    modifier: Modifier = Modifier,
    refreshKey: Int = 0,
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }

    val tileSize = ApiClient.TILE_SIZE

    val txStart = (coords.xStart / tileSize).toInt()
    val txEnd = ((coords.xEnd - 1) / tileSize).toInt()
    val tyStart = (coords.yStart / tileSize).toInt()
    val tyEnd = ((coords.yEnd - 1) / tileSize).toInt()
    val cacheBuster = if (refreshKey > 0) "?t=$refreshKey" else ""

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF9E9E9E))
            .pointerInput(coords) {
                detectTransformGestures { _, pan, zoom, _ ->
                    scale = (scale * zoom).coerceIn(0.2f, 12f)
                    offset += pan
                }
            }
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
                translationX = offset.x
                translationY = offset.y
            }
    ) {
        for (tx in txStart..txEnd) {
            for (ty in tyStart..tyEnd) {
                val px = tx * tileSize - coords.xStart.toInt()
                val py = ty * tileSize - coords.yStart.toInt()
                AsyncImage(
                    model = "${ApiClient.TILE_SOURCE}/$tx/$ty.png$cacheBuster",
                    contentDescription = "Tile $tx,$ty",
                    contentScale = ContentScale.FillBounds,
                    modifier = Modifier
                        .offset { IntOffset(px, py) }
                        .size(tileSize.dp, tileSize.dp),
                )
            }
        }
    }
}
