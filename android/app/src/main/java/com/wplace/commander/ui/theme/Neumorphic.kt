package com.wplace.commander.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.minimumInteractiveComponentSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Anuncia el cambio de un texto de estado a los lectores de pantalla. */
fun Modifier.liveRegion(): Modifier = semantics { liveRegion = LiveRegionMode.Polite }

/** Paleta neumórfica: base neutra, brillo (arriba-izquierda) y sombra (abajo-derecha). */
data class NeumorphicColors(
    val base: Color,
    val highlight: Color,
    val shadow: Color,
    val accent: Color,
    val onAccent: Color,
    val text: Color,
)

private fun Color.blend(factor: Float, with: Color): Color = Color(
    red = red + (with.red - red) * factor,
    green = green + (with.green - green) * factor,
    blue = blue + (with.blue - blue) * factor,
    alpha = alpha + (with.alpha - alpha) * factor,
)

/** Colores neumórficos derivados del fondo del tema (claro/oscuro/alto contraste). */
@Composable
fun neumorphicColors(): NeumorphicColors {
    val scheme = MaterialTheme.colorScheme
    val base = scheme.background
    val dark = base.luminance() < 0.35f
    val highlight = if (dark) base.blend(0.35f, Color.White) else base.blend(0.85f, Color.White)
    val shadow = if (dark) base.blend(0.35f, Color.Black) else base.blend(0.55f, Color.Black)
    return NeumorphicColors(base, highlight, shadow, scheme.primary, scheme.onPrimary, scheme.onBackground)
}

/** Superficie neumórfica: caja con doble sombra (luz/sombra) y relieve suave. */
@Composable
fun NeumorphicSurface(
    modifier: Modifier = Modifier,
    shape: Shape = RoundedCornerShape(16.dp),
    colors: NeumorphicColors = neumorphicColors(),
    elevation: Dp = 8.dp,
    containerColor: Color? = null,
    onClick: (() -> Unit)? = null,
    contentDescription: String? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val base = containerColor ?: if (pressed) colors.base.blend(0.06f, colors.shadow) else colors.base
    val effElevation = if (pressed) elevation * 0.4f else elevation
    val hi = if (pressed) colors.shadow else colors.highlight
    val sh = if (pressed) colors.highlight else colors.shadow
    val enabled = onClick != null
    Box(
        modifier = modifier
            .shadow(effElevation, shape, clip = false, ambientColor = sh, spotColor = sh)
            .shadow(effElevation, shape, clip = false, ambientColor = hi, spotColor = hi)
            .background(base, shape)
            .then(if (focused) Modifier.border(2.dp, colors.accent, shape) else Modifier)
            .let { m ->
                if (enabled) m
                    .minimumInteractiveComponentSize()
                    .semantics {
                        role = Role.Button
                        contentDescription?.let { this.contentDescription = it }
                    }
                    .clickable(interactionSource = interaction, indication = null, onClick = onClick!!)
                else m
            },
    ) { content() }
}

/** Botón neumórfico principal (relieve, marca el color de acento). */
@Composable
fun NeumorphicButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: NeumorphicColors = neumorphicColors(),
    contentDescription: String? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    val shape = RoundedCornerShape(14.dp)
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val accent = if (enabled) colors.accent else colors.base.blend(0.25f, colors.shadow)
    val contentColor = if (enabled) colors.onAccent else colors.text.copy(alpha = 0.4f)
    val hi = if (pressed) colors.shadow else colors.highlight
    val sh = if (pressed) colors.highlight else colors.shadow
    val elevation = if (pressed) 3.dp else 7.dp
    Box(
        modifier = modifier
            .shadow(elevation, shape, clip = false, ambientColor = sh, spotColor = sh)
            .shadow(elevation, shape, clip = false, ambientColor = hi, spotColor = hi)
            .background(accent, shape)
            .then(if (focused && enabled) Modifier.border(2.dp, colors.onAccent, shape) else Modifier)
            .minimumInteractiveComponentSize()
            .semantics {
                role = Role.Button
                contentDescription?.let { this.contentDescription = it }
            }
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        CompositionLocalProvider(
            LocalContentColor provides contentColor,
            LocalTextStyle provides MaterialTheme.typography.labelLarge,
        ) {
            Box(Modifier.defaultMinSize(minWidth = 88.dp).padding(horizontal = 20.dp, vertical = 12.dp)) { content() }
        }
    }
}

/** Botón neumórfico secundario (plano/ligeramente hundido según interacción). */
@Composable
fun NeumorphicTextButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: NeumorphicColors = neumorphicColors(),
    inset: Boolean = false,
    contentDescription: String? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    val shape = RoundedCornerShape(12.dp)
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val textColor = if (enabled) colors.accent else colors.text.copy(alpha = 0.4f)
    val hi = if (pressed || inset) colors.shadow else colors.highlight
    val sh = if (pressed || inset) colors.highlight else colors.shadow
    val elevation = if (pressed || inset) 1.dp else 4.dp
    Box(
        modifier = modifier
            .shadow(elevation, shape, clip = false, ambientColor = sh, spotColor = sh)
            .shadow(elevation, shape, clip = false, ambientColor = hi, spotColor = hi)
            .background(colors.base, shape)
            .then(if (focused && enabled) Modifier.border(2.dp, colors.accent, shape) else Modifier)
            .minimumInteractiveComponentSize()
            .semantics {
                role = Role.Button
                contentDescription?.let { this.contentDescription = it }
            }
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        CompositionLocalProvider(
            LocalContentColor provides textColor,
            LocalTextStyle provides MaterialTheme.typography.labelMedium,
        ) {
            Box(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) { content() }
        }
    }
}

/** Campo de texto neumórfico (hundido sutil, sin borde duro). */
@Composable
fun NeumorphicTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    singleLine: Boolean = true,
    colors: NeumorphicColors = neumorphicColors(),
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = label?.let { lbl -> @Composable { Text(lbl) } },
        singleLine = singleLine,
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = colors.base,
            unfocusedContainerColor = colors.base,
            disabledContainerColor = colors.base,
            focusedBorderColor = colors.shadow.copy(alpha = 0.12f),
            unfocusedBorderColor = colors.shadow.copy(alpha = 0.12f),
            disabledBorderColor = colors.shadow.copy(alpha = 0.08f),
            cursorColor = colors.accent,
            focusedLabelColor = colors.accent,
        ),
    )
}

/** Control segmentado neumórfico (reemplaza TabRow). */
@Composable
fun NeumorphicSegmented(
    options: List<String>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = neumorphicColors()
    val shape = RoundedCornerShape(14.dp)
    Row(
        modifier = modifier
            .shadow(6.dp, shape, clip = false, ambientColor = colors.shadow, spotColor = colors.shadow)
            .shadow(6.dp, shape, clip = false, ambientColor = colors.highlight, spotColor = colors.highlight)
            .background(colors.base, shape)
            .padding(4.dp)
            .fillMaxWidth()
            .selectableGroup(),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEachIndexed { i, label ->
            val selected = i == selectedIndex
            Box(
                modifier = Modifier
                    .weight(1f)
                    .clip(shape)
                    .background(if (selected) colors.accent else Color.Transparent)
                    .selectable(
                        selected = selected,
                        role = Role.Tab,
                        onClick = { onSelect(i) },
                    )
                    .defaultMinSize(minHeight = 48.dp)
                    .padding(vertical = 10.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = label,
                    color = if (selected) colors.onAccent else colors.text,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
    }
}

/** Barra de progreso neumórfica (canal hundido + relleno de acento). */
@Composable
fun NeumorphicProgress(
    progress: Float,
    modifier: Modifier = Modifier,
    height: Dp = 12.dp,
    contentDescription: String? = null,
) {
    val colors = neumorphicColors()
    val shape = RoundedCornerShape(height / 2.dp)
    val p = progress.coerceIn(0f, 1f)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(height)
            .background(colors.base, shape)
            .semantics {
                contentDescription?.let { this.contentDescription = it }
                stateDescription = "${(p * 100).toInt()} %"
            },
    ) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth(p)
                .background(colors.accent, shape),
        )
    }
}

/** Conveniencia: tarjeta neumórfica estándar. */
@Composable
fun NeumorphicCard(
    modifier: Modifier = Modifier,
    colors: NeumorphicColors = neumorphicColors(),
    containerColor: Color? = null,
    onClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    NeumorphicSurface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = colors,
        containerColor = containerColor,
        onClick = onClick,
        content = content,
    )
}