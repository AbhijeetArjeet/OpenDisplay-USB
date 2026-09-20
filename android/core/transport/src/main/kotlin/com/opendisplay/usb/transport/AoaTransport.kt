package com.opendisplay.usb.transport

import android.os.ParcelFileDescriptor
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
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

private const val TAG = "AoaTransport"

/**
 * Native Android Open Accessory (AOA) Transport over direct USB cable.
 *
 * Provides zero-ADB plug-and-play streaming by reading/writing directly to the
 * Linux kernel USB accessory character device (/dev/usb_accessory) via [ParcelFileDescriptor].
 */
class AoaTransport(
    private val fileDescriptor: ParcelFileDescriptor,
    private val customInfo: TransportInfo = TransportInfo(
        type = TransportType.USB,
        bandwidthBps = 480_000_000L,
        latencyMs = 1L,
        description = "Native Android Open Accessory (AOA) USB 2.0/3.0",
        id = "aoa_usb",
        name = "Native USB AOA Transport"
    )
) : Transport {

    private val _connectionState = MutableStateFlow(ConnectionState.CONNECTED)
    override val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val inputStream: InputStream = BufferedInputStream(
        FileInputStream(fileDescriptor.fileDescriptor),
        1024 * 1024
    )
    private val outputStream: OutputStream = BufferedOutputStream(
        FileOutputStream(fileDescriptor.fileDescriptor),
        64 * 1024
    )

    private val sendLock = Any()

    override suspend fun connect(): Result<Unit> {
        _connectionState.value = ConnectionState.CONNECTED
        return Result.success(Unit)
    }

    override suspend fun disconnect() = withContext(Dispatchers.IO) {
        Log.i(TAG, "Closing AOA USB transport")
        _connectionState.value = ConnectionState.DISCONNECTED
        try {
            inputStream.close()
        } catch (_: Exception) {}
        try {
            outputStream.close()
        } catch (_: Exception) {}
        try {
            fileDescriptor.close()
        } catch (_: Exception) {}
    }

    override suspend fun send(packet: ByteArray): Result<Unit> = withContext(Dispatchers.IO) {
        if (!isConnected()) {
            return@withContext Result.failure(IllegalStateException("AoaTransport: send() called while disconnected"))
        }

        runCatching {
            synchronized(sendLock) {
                outputStream.write(packet)
                outputStream.flush()
            }
        }.onFailure { e ->
            Log.e(TAG, "AOA USB send failed: ${e.message}")
            disconnect()
        }
    }

    override fun receiveFlow(): Flow<ByteArray> = flow {
        val headerBuffer = ByteArray(ProtocolVersion.HEADER_SIZE)

        try {
            while (isConnected()) {
                readFully(inputStream, headerBuffer, ProtocolVersion.HEADER_SIZE)

                val byteBuf = ByteBuffer.wrap(headerBuffer).order(ByteOrder.LITTLE_ENDIAN)
                val magic = byteBuf.int
                if (magic != ProtocolVersion.MAGIC) {
                    Log.e(TAG, "Malformed packet magic in AOA stream: 0x${Integer.toHexString(magic)}")
                    disconnect()
                    break
                }

                val payloadLength = byteBuf.getInt(7)
                if (payloadLength < 0 || payloadLength > 16 * 1024 * 1024) {
                    Log.e(TAG, "Invalid payload length in AOA packet: $payloadLength")
                    disconnect()
                    break
                }

                val packet = ByteArray(ProtocolVersion.HEADER_SIZE + payloadLength)
                System.arraycopy(headerBuffer, 0, packet, 0, ProtocolVersion.HEADER_SIZE)

                if (payloadLength > 0) {
                    readFully(inputStream, packet, payloadLength, offset = ProtocolVersion.HEADER_SIZE)
                }

                emit(packet)
            }
        } catch (e: EOFException) {
            Log.i(TAG, "AOA USB stream reached EOF")
        } catch (e: IOException) {
            if (isConnected()) {
                Log.w(TAG, "AOA USB read error: ${e.message}")
            }
        } finally {
            disconnect()
        }
    }.flowOn(Dispatchers.IO)

    private fun readFully(stream: InputStream, buffer: ByteArray, length: Int, offset: Int = 0) {
        var totalBytesRead = 0
        while (totalBytesRead < length) {
            val bytesRead = stream.read(buffer, offset + totalBytesRead, length - totalBytesRead)
            if (bytesRead < 0) {
                throw EOFException("End of stream reached before reading required $length bytes (read $totalBytesRead)")
            }
            totalBytesRead += bytesRead
        }
    }

    override fun getInfo(): TransportInfo = customInfo
}
