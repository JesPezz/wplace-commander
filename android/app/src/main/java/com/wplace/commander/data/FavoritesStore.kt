package com.wplace.commander.data

import android.content.Context
import com.wplace.commander.network.ApiClient
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json

object FavoritesStore {

    private val json = Json { ignoreUnknownKeys = true }
    private val mapSerializer = MapSerializer(String.serializer(), FavoriteMission.serializer())

    fun load(context: Context): Map<String, FavoriteMission> {
        val raw = ApiClient.prefs(context).getString("favorites", "{}") ?: "{}"
        return try {
            json.decodeFromString(mapSerializer, raw)
        } catch (_: Exception) {
            emptyMap()
        }
    }

    fun save(context: Context, favorites: Map<String, FavoriteMission>) {
        ApiClient.prefs(context).edit()
            .putString("favorites", json.encodeToString(mapSerializer, favorites))
            .apply()
    }
}
