package com.wplace.commander.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.wplace.commander.data.StatusResponse
import com.wplace.commander.network.ApiClient
import com.wplace.commander.ui.theme.ThemeMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class WPlaceViewModel(private val appContext: Context) : ViewModel() {

    private val _serverIp = MutableStateFlow(ApiClient.getServerIp(appContext))
    val serverIp: StateFlow<String> = _serverIp.asStateFlow()

    private val _status = MutableStateFlow<StatusResponse?>(null)
    val status: StateFlow<StatusResponse?> = _status.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _themeMode = MutableStateFlow(
        ThemeMode.valueOf(ApiClient.prefs(appContext).getString("theme", "AUTO") ?: "AUTO")
    )
    val themeMode: StateFlow<ThemeMode> = _themeMode.asStateFlow()

    private val _selectedTab = MutableStateFlow(0)
    val selectedTab: StateFlow<Int> = _selectedTab.asStateFlow()

    // Acceso al contexto compartido (para prefs locales).
    private val _appContext = appContext
    fun appCtx(): Context = _appContext

    private var polling = false

    fun setServer(ip: String) {
        ApiClient.saveServerIp(appContext, ip)
        _serverIp.value = ApiClient.getServerIp(appContext)
        refreshStatus()
    }

    fun setTab(index: Int) { _selectedTab.value = index }

    fun setTheme(mode: ThemeMode) {
        _themeMode.value = mode
        ApiClient.prefs(appContext).edit().putString("theme", mode.name).apply()
    }

    fun clearError() { _error.value = null }

    fun startPolling() {
        if (polling) return
        polling = true
        viewModelScope.launch {
            while (true) {
                refreshStatus()
                delay(3000)
            }
        }
    }

    fun refreshStatus() {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                _status.value = ApiClient.api().status()
            } catch (e: Exception) {
                _error.value = e.message
            }
        }
    }

    fun runApi(block: suspend () -> Unit, onDone: (() -> Unit)? = null) {
        viewModelScope.launch(Dispatchers.IO) {
            _loading.value = true
            try {
                block()
            } catch (e: Exception) {
                _error.value = e.message
            } finally {
                _loading.value = false
                onDone?.let { viewModelScope.launch(Dispatchers.Main) { it() } }
            }
        }
    }
}
