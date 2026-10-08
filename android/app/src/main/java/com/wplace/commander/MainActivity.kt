package com.wplace.commander

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.wplace.commander.network.AppContextProvider
import com.wplace.commander.ui.WPlaceViewModel
import com.wplace.commander.ui.mission.MissionScreen
import com.wplace.commander.ui.planner.PlannerScreen
import com.wplace.commander.ui.radar.RadarScreen
import com.wplace.commander.ui.system.SystemScreen
import com.wplace.commander.ui.telegram.TelegramProxyScreen
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

    LaunchedEffect(Unit) { vm.startPolling() }

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
}
