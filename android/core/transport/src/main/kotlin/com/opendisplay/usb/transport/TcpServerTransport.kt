package com.opendisplay.usb.transport

import android.util.Log
import com.opendisplay.usb.protocol.ProtocolVersion
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder

private const val TAG = "TcpServerTransport"

/**
 * TCP server transport that listens for incoming host connections on port [port]
 * (typically 7320, forwarded via `adb forward tcp:7320 tcp:7320`).
 *
 * Implements [Transport] framing contract where every emitted [ByteArray] in [receiveFlow]
 * and accepted by [send] is a complete 11-byte header + payload packet.
 */
class TcpServerTransport(
    private val port: Int = 7320,
    private val customInfo: TransportInfo = TransportInfo(
        type = TransportType.USB,
        bandwidthBps = 480_000_000L,
        latencyMs = 2L,
        description = "TCP Server Transport over ADB (Port $port)",
        id = "tcp_server_$port",
        name = "ADB TCP Transport"
    )
) : Transport {

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    override val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private var serverSocket: ServerSocket? = null
    private var clientSocket: Socket? = null
    private var inputStream: InputStream? = null
    private var outputStream: OutputStream? = null

    private val sendLock = Any()

    override suspend fun connect(): Result<Unit> = withContext(Dispatchers.IO) {
        if (_connectionState.value == ConnectionState.CONNECTED) {
            return@withContext Result.success(Unit)
        }

        _connectionState.value = ConnectionState.CONNECTING
        Log.i(TAG, "Opening ServerSocket on port $port...")

        runCatching {
            val server = if (serverSocket != null && !serverSocket!!.isClosed && serverSocket!!.isBound) {
                serverSocket!!
            } else {
                try {
                    serverSocket?.close()
                } catch (_: Exception) {}
                ServerSocket().apply {
                    reuseAddress = true
                    bind(InetSocketAddress(port))
                }.also { serverSocket = it }
            }

            Log.i(TAG, "Listening on port $port. Awaiting Windows host connection...")
            val client = server.accept()

            client.tcpNoDelay = true
            client.soTimeout = 0
            client.receiveBufferSize = 4 * 1024 * 1024
            client.sendBufferSize = 1024 * 1024

            clientSocket = client
            inputStream = BufferedInputStream(client.getInputStream(), 1024 * 1024)
            outputStream = BufferedOutputStream(client.getOutputStream(), 64 * 1024)

            _connectionState.value = ConnectionState.CONNECTED
            Log.i(TAG, "Connected to host: ${client.inetAddress.hostAddress}:${client.port}")
            Unit
        }.onFailure { e ->
            Log.e(TAG, "Failed to establish TCP server connection: ${e.message}", e)
            _connectionState.value = ConnectionState.DISCONNECTED
            cleanupClient()
        }
    }

    override suspend fun disconnect() = withContext(Dispatchers.IO) {
        Log.i(TAG, "Disconnecting TCP client connection")
        _connectionState.value = ConnectionState.DISCONNECTED
        cleanupClient()
        // Note: We intentionally keep serverSocket bound and listening so host reconnects succeed instantly
    }

    /** Closes the server socket completely. Call on app shutdown. */
    fun closeServer() {
        try {
            serverSocket?.close()
        } catch (e: Exception) {
            Log.w(TAG, "Error closing ServerSocket: ${e.message}")
        }
        serverSocket = null
    }

    override suspend fun send(packet: ByteArray): Result<Unit> = withContext(Dispatchers.IO) {
        if (!isConnected()) {
            return@withContext Result.failure(IllegalStateException("TcpServerTransport: send() called while disconnected"))
        }

        val out = outputStream ?: return@withContext Result.failure(IllegalStateException("No output stream"))

        runCatching {
            synchronized(sendLock) {
                out.write(packet)
                out.flush()
            }
        }.onFailure { e ->
            Log.e(TAG, "Failed to send packet: ${e.message}")
            _connectionState.value = ConnectionState.DISCONNECTED
            cleanupClient()
        }
    }

    override fun receiveFlow(): Flow<ByteArray> = flow {
        val input = inputStream ?: throw IllegalStateException("Not connected: no input stream")
        val headerBuffer = ByteArray(ProtocolVersion.HEADER_SIZE)

        try {
            while (isConnected()) {
                // Read 11-byte header
                input.readFully(headerBuffer, 0, ProtocolVersion.HEADER_SIZE)

                // Validate magic
                val m0 = headerBuffer[0].toInt() and 0xFF
                val m1 = headerBuffer[1].toInt() and 0xFF
                val m2 = headerBuffer[2].toInt() and 0xFF
                val m3 = headerBuffer[3].toInt() and 0xFF
                if (m0 != 0x4F || m1 != 0x44 || m2 != 0x53 || m3 != 0x50) {
                    throw IOException("Invalid magic bytes: 0x%02X 0x%02X 0x%02X 0x%02X".format(m0, m1, m2, m3))
                }

                // Parse payload length (little-endian uint32 at offset 7)
                val payloadLen = ByteBuffer.wrap(headerBuffer, 7, 4)
                    .order(ByteOrder.LITTLE_ENDIAN)
                    .getInt()

                if (payloadLen < 0 || payloadLen > ProtocolVersion.MAX_PAYLOAD_BYTES) {
                    throw IOException("Invalid payload length: $payloadLen (max=${ProtocolVersion.MAX_PAYLOAD_BYTES})")
                }

                // Read payload directly into complete frame
                val totalFrameSize = ProtocolVersion.HEADER_SIZE + payloadLen
                val completeFrame = ByteArray(totalFrameSize)
                System.arraycopy(headerBuffer, 0, completeFrame, 0, ProtocolVersion.HEADER_SIZE)

                if (payloadLen > 0) {
                    input.readFully(completeFrame, ProtocolVersion.HEADER_SIZE, payloadLen)
                }

                emit(completeFrame)
            }
        } catch (e: EOFException) {
            Log.i(TAG, "Host closed connection (EOF)")
            _connectionState.value = ConnectionState.DISCONNECTED
            cleanupClient()
        } catch (e: IOException) {
            if (isConnected()) {
                Log.w(TAG, "Connection read error: ${e.message}")
                _connectionState.value = ConnectionState.DISCONNECTED
                cleanupClient()
            }
        } catch (e: kotlinx.coroutines.CancellationException) {
            // Normal collector cancellation (e.g. first()), do not drop transport connection
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Unexpected error in receiveFlow: ${e.message}")
            _connectionState.value = ConnectionState.DISCONNECTED
            cleanupClient()
        }
    }.flowOn(Dispatchers.IO)

    override fun getInfo(): TransportInfo = customInfo

    private fun cleanupClient() {
        try {
            inputStream?.close()
        } catch (_: Exception) {}
        try {
            outputStream?.close()
        } catch (_: Exception) {}
        try {
            clientSocket?.close()
        } catch (_: Exception) {}
        inputStream = null
        outputStream = null
        clientSocket = null
    }

    private fun InputStream.readFully(b: ByteArray, off: Int, len: Int) {
        var n = 0
        while (n < len) {
            val count = read(b, off + n, len - n)
            if (count < 0) {
                throw EOFException("Stream ended before reading $len bytes (read $n bytes)")
            }
            n += count
        }
    }
}
