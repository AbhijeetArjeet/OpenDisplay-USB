package com.opendisplay.usb.transport

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow

/**
 * In-memory loopback transport for development and testing.
 *
 * How to use in mock mode:
 * 1. Create a [FakeTransport].
 * 2. Call [connect].
 * 3. Inject packets with [injectPacket] — they appear in [receiveFlow] as if sent by Windows.
 * 4. Packets sent via [send] can be read back with [consumeSentPacket] in tests.
 * 5. Call [simulateDisconnect] to simulate a cable unplug.
 * 6. Call [simulateReconnect] to reconnect after a simulated disconnect.
 *
 * Thread safety: all public methods are thread-safe.
 */
class FakeTransport(
    private val customInfo: TransportInfo = TransportInfo(
        type = TransportType.FAKE,
        bandwidthBps = 480_000_000L,
        latencyMs = 0L,
        description = "Fake in-memory transport (mock mode)"
    )
) : Transport {

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    override val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    /**
     * Channel simulating the "wire from Windows to Android" (incoming to Android).
     * [injectPacket] writes here; [receiveFlow] reads here.
     */
    private var incomingChannel: Channel<ByteArray> = Channel(capacity = 256)

    /**
     * Channel capturing packets that Android sends (outgoing from Android).
     * [send] writes here; tests read via [consumeSentPacket].
     */
    private var sentChannel: Channel<ByteArray> = Channel(capacity = 256)

    // ── Transport interface ───────────────────────────────────────────────────

    override suspend fun connect(): Result<Unit> {
        if (_connectionState.value == ConnectionState.CONNECTED) return Result.success(Unit)
        _connectionState.value = ConnectionState.CONNECTING
        // Ensure channels are open (re-create if previously closed by simulateDisconnect)
        if (incomingChannel.isClosedForSend) {
            incomingChannel = Channel(capacity = 256)
        }
        if (sentChannel.isClosedForSend) {
            sentChannel = Channel(capacity = 256)
        }
        _connectionState.value = ConnectionState.CONNECTED
        return Result.success(Unit)
    }

    override suspend fun disconnect() {
        if (_connectionState.value == ConnectionState.DISCONNECTED) return
        _connectionState.value = ConnectionState.DISCONNECTED
        incomingChannel.close()
        sentChannel.close()
    }

    override suspend fun send(packet: ByteArray): Result<Unit> {
        if (!isConnected()) {
            return Result.failure(IllegalStateException("FakeTransport: send() called while disconnected"))
        }
        return runCatching { sentChannel.send(packet) }
    }

    override fun receiveFlow(): Flow<ByteArray> = flow {
        val channel = incomingChannel
        try {
            for (packet in channel) {
                emit(packet)
            }
        } catch (_: ClosedReceiveChannelException) {
            // Channel closed cleanly — flow completes
        }
    }

    override fun getInfo(): TransportInfo = customInfo

    // ── Test / mock helpers ────────────────────────────────────────────────────

    /**
     * Injects a packet as if it arrived from the Windows side.
     * The packet will appear in [receiveFlow] on the next collection.
     *
     * Suspends if the incoming channel buffer is full (backpressure).
     *
     * @throws [IllegalStateException] if the transport is not connected.
     */
    suspend fun injectPacket(packet: ByteArray) {
        check(isConnected()) { "FakeTransport: injectPacket() called while disconnected" }
        incomingChannel.send(packet)
    }

    /**
     * Injects a packet without suspending.
     * Drops the packet if the incoming channel buffer is full.
     * Use this from non-suspend contexts in tests.
     */
    fun injectPacketBlocking(packet: ByteArray): Boolean {
        if (!isConnected()) return false
        return incomingChannel.trySend(packet).isSuccess
    }

    /**
     * Returns the next packet that Android sent via [send], or null if none is queued.
     * Does NOT suspend. Useful for test assertions.
     */
    fun consumeSentPacket(): ByteArray? = sentChannel.tryReceive().getOrNull()

    /**
     * Simulates a sudden transport failure (e.g., USB cable unplugged).
     *
     * - [connectionState] transitions to [ConnectionState.DISCONNECTED].
     * - Any current [receiveFlow] collector will see the flow complete.
     * - Any pending [send] will fail.
     */
    suspend fun simulateDisconnect() {
        _connectionState.value = ConnectionState.DISCONNECTED
        incomingChannel.close()
        sentChannel.close()
    }

    /**
     * Simulates reconnection after [simulateDisconnect].
     * Equivalent to calling [connect] on fresh channels.
     */
    suspend fun simulateReconnect(): Result<Unit> {
        // Force re-creation of channels regardless of close state
        incomingChannel = Channel(capacity = 256)
        sentChannel = Channel(capacity = 256)
        return connect()
    }

    /** Number of packets currently queued in the incoming buffer. */
    val incomingQueueSize: Int get() = incomingChannel.isEmpty.let {
        // Channel.isEmpty only tells us if it's empty, not the count.
        // For diagnostics, this is sufficient.
        if (it) 0 else -1  // -1 = "at least one, exact count not available from Channel API"
    }
}
