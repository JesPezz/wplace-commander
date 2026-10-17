package com.wplace.commander

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.wplace.commander.network.ApiClient
import com.wplace.commander.network.AppContextProvider
import com.wplace.commander.network.UpdateChecker
import com.wplace.commander.network.UpdateInfo
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.mission.MissionScreen
import com.wplace.commander.ui.planner.PlannerScreen
import com.wplace.commander.ui.radar.RadarScreen
import com.wplace.commander.ui.system.SystemScreen
import com.wplace.commander.ui.telegram.TelegramProxyScreen
import com.wplace.commander.ui.theme.NeumorphicButton
import com.wplace.commander.ui.theme.WPlaceTheme
import com.wplace.commander.ui.theme.neumorphicColors
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.runtime.collectAsState
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppContextProvider.init(applicationContext)
        setContent {
            val vm: WPlaceViewModel = viewModel(
                factory = viewModelFactory {
                    initializer { WPlaceViewModel(AppContextProvider.context) }
                }
            )
            val themeMode by vm.themeMode.collectAsState()
            WPlaceTheme(themeMode) {
                AppRoot(vm)
            }
        }
    }
}

data class NavItem(val label: String, val icon: ImageVector, val screen: Int)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot(vm: WPlaceViewModel) {
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val selected by vm.selectedTab.collectAsState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    // Actualización automática al abrir la app.
    var autoUpdate by remember { mutableStateOf<UpdateInfo?>(null) }
    var autoBusy by remember { mutableStateOf(false) }
    var autoProgress by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) {
        vm.startPolling()
        val info = runCatching { UpdateChecker.check() }.getOrNull()
        if (info?.hasUpdate == true) {
            val skipped = ApiClient.prefs(context).getString("skipped_version", null)
            if (skipped != info.latestVersion) autoUpdate = info
        }
    }

    val items = listOf(
        NavItem("Misión", Icons.Filled.Place, 0),
        NavItem("Radar", Icons.Filled.List, 1),
        NavItem("Planificador", Icons.Filled.CalendarMonth, 2),
        NavItem("Telegram", Icons.Filled.Email, 3),
        NavItem("Sistema", Icons.Filled.Settings, 4),
    )

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            val neo = neumorphicColors()
            ModalDrawerSheet(
                drawerContainerColor = MaterialTheme.colorScheme.background,
                drawerContentColor = neo.text,
            ) {
                Text("WPlace Commander", style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(16.dp))
                HorizontalDivider(color = neo.shadow.copy(alpha = 0.2f))
                items.forEach { item ->
                    NavigationDrawerItem(
                        label = { Text(item.label) },
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        selected = selected == item.screen,
                        onClick = {
                            vm.setTab(item.screen)
                            scope.launch { drawerState.close() }
                        },
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        colors = NavigationDrawerItemDefaults.colors(
                            selectedContainerColor = neo.accent,
                            selectedTextColor = neo.onAccent,
                            selectedIconColor = neo.onAccent,
                            unselectedContainerColor = Color.Transparent,
                            unselectedTextColor = neo.text,
                            unselectedIconColor = neo.text,
                        ),
                    )
                }
            }
        },
    ) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                TopAppBar(
                    title = { Text(items.firstOrNull { it.screen == selected }?.label ?: "") },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Filled.Menu, contentDescription = "Abrir menú")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background,
                        titleContentColor = MaterialTheme.colorScheme.onBackground,
                        navigationIconContentColor = MaterialTheme.colorScheme.onBackground,
                    ),
                )
            },
        ) { padding ->
            when (selected) {
                0 -> MissionScreen(vm, Modifier.padding(padding))
                1 -> RadarScreen(vm, Modifier.padding(padding))
                2 -> PlannerScreen(vm, Modifier.padding(padding))
                3 -> TelegramProxyScreen(vm, Modifier.padding(padding))
                4 -> SystemScreen(vm, Modifier.padding(padding))
            }
        }
    }

    autoUpdate?.let { info ->
        AlertDialog(
            onDismissRequest = { if (!autoBusy) autoUpdate = null },
            title = { Text("Actualización disponible") },
            text = {
                Column {
                    Text("Nueva versión v${info.latestVersion}. ¿Actualizar ahora?")
                    if (autoBusy) {
                        Spacer(Modifier.height(12.dp))
                        LinearProgressIndicator(
                            progress = { autoProgress / 100f },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text("Descargando… $autoProgress%", style = MaterialTheme.typography.bodySmall)
                    } else if (info.body.isNotBlank()) {
                        Spacer(Modifier.height(8.dp))
                        Text(info.body.trim(), style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = {
                NeumorphicButton(enabled = !autoBusy, onClick = {
                    scope.launch {
                        autoBusy = true; autoProgress = 0
                        try {
                            val ok = UpdateChecker.downloadAndInstall(context, info.downloadUrl) { autoProgress = it }
                            if (ok) {
                                autoUpdate = null
                            } else {
                                Toast.makeText(context, "Concede «instalar apps desconocidas» y pulsa Actualizar de nuevo", Toast.LENGTH_LONG).show()
                            }
                        } catch (e: Exception) {
                            Toast.makeText(context, "Error al descargar: ${e.message}", Toast.LENGTH_LONG).show()
                        } finally {
                            autoBusy = false
                        }
                    }
                }) { Text(if (autoBusy) "Descargando…" else "Actualizar") }
            },
            dismissButton = {
                TextButton(enabled = !autoBusy, onClick = {
                    ApiClient.prefs(context).edit().putString("skipped_version", info.latestVersion).apply()
                    autoUpdate = null
                }) { Text("Omitir versión") }
            },
        )
    }
}
