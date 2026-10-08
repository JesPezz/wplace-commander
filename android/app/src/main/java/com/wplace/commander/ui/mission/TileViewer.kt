package com.wplace.commander.ui.mission

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
    var fitted by remember(coords) { mutableStateOf(false) }

    val tileSize = ApiClient.TILE_SIZE

    // Tamaño de la región en px (mismo sistema que las tiles).
    val regionW = (coords.xEnd - coords.xStart).toInt()
    val regionH = (coords.yEnd - coords.yStart).toInt()

    val txStart = (coords.xStart / tileSize).toInt()
    val txEnd = ((coords.xEnd - 1) / tileSize).toInt()
    val tyStart = (coords.yStart / tileSize).toInt()
    val tyEnd = ((coords.yEnd - 1) / tileSize).toInt()
    val cacheBuster = if (refreshKey > 0) "?t=$refreshKey" else ""

    BoxWithConstraints(
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
            .semantics {
                contentDescription = "Visor de la región seleccionada. Usa pinza para ampliar y arrastra para mover."
            },
        contentAlignment = Alignment.Center,
    ) {
        // Ajusta la vista para que la región del overlay se vea completa,
        // ampliando incluso regiones más pequeñas que el visor (como el escritorio).
        // El hijo va centrado, así que el pivote del graphicsLayer (centro del visor)
        // coincide con el centro de la región y no hay que compensarlo con un offset.
        LaunchedEffect(regionW, regionH, maxWidth, maxHeight, fitted) {
            if (!fitted && regionW > 0 && regionH > 0 && maxWidth > 0.dp && maxHeight > 0.dp) {
                scale = minOf(maxWidth.value / regionW, maxHeight.value / regionH, 8f)
                fitted = true
            }
        }

        Box(
            modifier = Modifier
                .size(regionW.dp, regionH.dp)
                // unbounded: los tiles (1000 dp) son mayores que la caja de la
                // región; sin esto se coaccionan a su tamaño y quedan recortados.
                .wrapContentSize(align = Alignment.TopStart, unbounded = true)
                .clipToBounds()
        ) {
            for (tx in txStart..txEnd) {
                for (ty in tyStart..tyEnd) {
                    // dp = px del lienzo: región y tiles comparten sistema de unidades
                    // (si el offset fuera px crudos, se mezclaría con los tamaños en dp).
                    val ox = (tx * tileSize - coords.xStart).toInt().dp
                    val oy = (ty * tileSize - coords.yStart).toInt().dp
                    AsyncImage(
                        model = "${ApiClient.TILE_SOURCE}/$tx/$ty.png$cacheBuster",
                        contentDescription = null,
                        contentScale = ContentScale.FillBounds,
                        modifier = Modifier
                            .offset(x = ox, y = oy)
                            // requiredSize: un tile (1000 dp) es mayor que la caja de la
                            // región, y `size` se coaccionaría a esos 167 dp y quedaría
                            // fuera de la caja recortada. requiredSize ignora el padre.
                            .requiredSize(tileSize.dp, tileSize.dp),
                    )
                }
            }
        }
    }
}
