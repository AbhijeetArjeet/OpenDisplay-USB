package com.opendisplay.usb.transport

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

/**
 * Transport abstraction for OpenDisplay USB.
 *
 * The video decoder, audio system, input encoder, and protocol controller MUST only
 * depend on this interface. They MUST NOT import or reference any concrete transport
 * implementation (ADB, USB, Wi-Fi, Fake).
 *
 * Packet framing: every ByteArray passed to [send] or emitted by [receiveFlow] is a
 * COMPLETE framed packet (11-byte header + payload) as produced by PacketCodec.encode().
 * The transport layer is responsible for reliable, in-order, framed delivery.
 *
 * Thread safety: all implementations MUST be thread-safe.
 * Coroutine safety: [connect], [disconnect], [send] are suspend functions callable
 * from any dispatcher. [receiveFlow] delivers packets on the collector's dispatcher.
 */
interface Transport {

    /**
     * Current connection state as a hot [StateFlow].
     * Updated before any suspend function returns.
     */
    val connectionState: StateFlow<ConnectionState>

    /**
     * Establish the connection.
     *
     * Returns [Result.success] when connected and ready to send/receive.
     * Returns [Result.failure] if connection fails (e.g., device not found, port refused).
     *
     * Must be idempotent: calling connect() when already [ConnectionState.CONNECTED]
     * MUST return [Result.success] immediately.
     */
    suspend fun connect(): Result<Unit>

    /**
     * Disconnect gracefully.
     *
     * Safe to call from any state. No-op if already disconnected.
     * After this returns, [connectionState] MUST be [ConnectionState.DISCONNECTED].
     * The [receiveFlow] completes (no exception) after disconnect.
     */
    suspend fun disconnect()

    /**
     * Send a complete framed packet.
     *
     * [packet] must be a complete frame as returned by PacketCodec.encode().
     * Returns [Result.failure] if the send fails (connection lost, buffer full, etc.).
     */
    suspend fun send(packet: ByteArray): Result<Unit>

    /**
     * A cold [Flow] of received raw packet bytes.
     *
     * Each emission is a complete framed packet (header + payload).
     * The flow completes normally when the transport disconnects cleanly.
     * The flow throws an exception on unexpected transport failure.
     *
     * Implementations MUST begin receiving as soon as this flow is collected.
     * Implementations MUST NOT buffer more than a reasonable number of frames before
     * applying backpressure or dropping (transport-specific policy).
     */
    fun receiveFlow(): Flow<ByteArray>

    /**
     * Returns true if [connectionState] is currently [ConnectionState.CONNECTED].
     */
    fun isConnected(): Boolean = connectionState.value == ConnectionState.CONNECTED

    /**
     * Returns metadata about this transport (type, bandwidth estimate, latency estimate).
     */
    fun getInfo(): TransportInfo
}
