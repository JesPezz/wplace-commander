package com.wplace.commander.ui.theme

import android.content.res.Configuration
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration

private val LightColors = lightColorScheme(
    primary = Color(0xFF0078D4),
    onPrimary = Color.White,
    secondary = Color(0xFF71C5F1),
    background = Color(0xFFF3F3F3),
    surface = Color.White,
    onBackground = Color(0xFF1B1B1B),
    onSurface = Color(0xFF1B1B1B),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF60CDFF),
    onPrimary = Color(0xFF001019),
    secondary = Color(0xFF001019),
    background = Color(0xFF202020),
    surface = Color(0xFF2B2B2B),
    onBackground = Color.White,
    onSurface = Color.White,
)

/** Alto contraste: colores siguiendo el estándar de Windows (fondo negro, texto blanco, acento amarillo). */
private val HighContrastColors = darkColorScheme(
    primary = Color(0xFFFFFF00),
    onPrimary = Color.Black,
    background = Color.Black,
    surface = Color.Black,
    onBackground = Color.White,
    onSurface = Color.White,
    outline = Color.White,
)

enum class ThemeMode { AUTO, LIGHT, DARK, HIGH_CONTRAST }

@Composable
fun isHighContrastEnabled(): Boolean {
    val configuration = LocalConfiguration.current
    val nightMask = configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK
    return nightMask == Configuration.UI_MODE_NIGHT_YES
}

@Composable
fun WPlaceTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
        ThemeMode.HIGH_CONTRAST -> true
        ThemeMode.AUTO -> isSystemInDarkTheme()
    }
    val highContrast = mode == ThemeMode.HIGH_CONTRAST
    val colors = when {
        highContrast -> HighContrastColors
        dark -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = colors, content = content)
}
