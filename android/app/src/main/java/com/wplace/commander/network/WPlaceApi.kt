package com.wplace.commander.network

import com.wplace.commander.data.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming
import okhttp3.ResponseBody

interface WPlaceApi {

    @POST("tasks/create")
    suspend fun createTask(@Body body: CreateTaskRequest): CreateTaskResponse

    @POST("tasks/{id}/start")
    suspend fun startTask(@Path("id") id: String): SimpleResponse

    @POST("tasks/{id}/stop")
    suspend fun stopTask(@Path("id") id: String): SimpleResponse

    @POST("tasks/{id}/delete")
    suspend fun deleteTask(@Path("id") id: String): SimpleResponse

    @GET("status")
    suspend fun status(): StatusResponse

    @POST("tasks/update")
    suspend fun updateTask(@Body body: UpdateTaskRequest): SimpleResponse

    @Streaming
    @GET("download_zip")
    suspend fun downloadZip(@Query("task_id") taskId: String?): ResponseBody

    @POST("stop_all")
    suspend fun stopAll(): SimpleResponse

    @POST("delete_tasks")
    suspend fun deleteTasks(): SimpleResponse

    @POST("delete_photos")
    suspend fun deletePhotos(): SimpleResponse

    @GET("plan/status")
    suspend fun planStatus(): PlanStatusResponse

    @POST("plan/set")
    suspend fun planSet(@Body body: PlanSetRequest): SimpleResponse

    @GET("proxy/status")
    suspend fun proxyStatus(): ProxyStatusResponse

    @POST("proxy/set")
    suspend fun proxySet(@Body body: ProxySetRequest): ProxyMessageResponse

    @GET("proxy/check_ip")
    suspend fun proxyCheckIp(): ProxyMessageResponse
}
