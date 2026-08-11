package com.wplace.commander.network

import android.content.Context
import android.content.SharedPreferences
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object ApiClient {

    private const val PREFS = "wplace_prefs"
    private const val KEY_SERVER = "server_ip"
    private const val DEFAULT_SERVER = "http://192.168.1.107:5000"

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    @Volatile
    private var api: WPlaceApi? = null

    private val okHttp: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    // Coordenadas de la fuente de tiles WPlace (coincide con el servidor)
    const val TILE_SOURCE = "https://backend.wplace.live/files/s0/tiles"
    const val TILE_SIZE = 1000

    fun getServerIp(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getString(KEY_SERVER, DEFAULT_SERVER) ?: DEFAULT_SERVER
    }

    fun saveServerIp(context: Context, ip: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_SERVER, ip.trim()).apply()
        synchronized(this) { api = null }  // invalidar para reconstruir con la nueva IP
    }

    private fun build(): Retrofit {
        val context = AppContextProvider.context
        val base = getServerIp(context).trim().trimEnd('/') + "/"
        return Retrofit.Builder()
            .baseUrl(base)
            .client(okHttp)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    fun api(): WPlaceApi {
        return api ?: synchronized(this) {
            api ?: build().create(WPlaceApi::class.java).also { api = it }
        }
    }

    /** Prefs compartidas para credenciales y configuración simple. */
    fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}

/** Provee un Context global (se inicializa en MainActivity/Application). */
object AppContextProvider {
    lateinit var context: Context
        private set
    fun init(c: Context) { context = c.applicationContext }
}
