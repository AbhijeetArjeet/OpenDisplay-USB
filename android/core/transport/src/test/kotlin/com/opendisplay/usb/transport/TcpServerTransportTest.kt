package com.opendisplay.usb.transport

import com.opendisplay.usb.protocol.MessageType
import com.opendisplay.usb.protocol.PacketCodec
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.net.Socket

class TcpServerTransportTest {

    private val testPort = 17320

    @Test
    fun testTcpServerConnectionAndPacketExchange() = runBlocking(Dispatchers.IO) {
        val server = TcpServerTransport(port = testPort)

        // Launch server connect asynchronously
        val serverJob = async {
            server.connect()
        }

        // Connect client
        var clientSocket: Socket? = null
        for (i in 1..10) {
            try {
                clientSocket = Socket("127.0.0.1", testPort)
                break
            } catch (_: Exception) {
                Thread.sleep(100)
            }
        }
        val client = clientSocket ?: throw IllegalStateException("Could not connect to test server")

        val connectResult = withTimeout(5000) { serverJob.await() }
        assertTrue("Server connect should succeed", connectResult.isSuccess)
        assertTrue("Server state should be CONNECTED", server.isConnected())

        val clientOut = BufferedOutputStream(client.getOutputStream())
        val clientIn = BufferedInputStream(client.getInputStream())

        // 1. Client -> Server packet
        val testPayload = "{\"type\":\"HELLO_ACK\",\"protocol\":1,\"accepted\":true}".toByteArray(Charsets.UTF_8)
        val sentFrame = PacketCodec.encode(MessageType.HELLO_ACK, testPayload)

        clientOut.write(sentFrame)
        clientOut.flush()

        val receivedFrame = withTimeout(5000) {
            server.receiveFlow().first()
        }
        assertArrayEquals("Server should receive exact framed bytes", sentFrame, receivedFrame)

        val decodedResult = PacketCodec.decode(receivedFrame)
        assertTrue(decodedResult.isSuccess)
        val decodedPacket = decodedResult.getOrThrow()
        assertEquals(MessageType.HELLO_ACK, decodedPacket.type)

        // 2. Server -> Client packet
        val helloPayload = "{\"type\":\"HELLO\",\"protocol\":1,\"platform\":\"android\"}".toByteArray(Charsets.UTF_8)
        val serverFrame = PacketCodec.encode(MessageType.HELLO, helloPayload)

        val sendResult = server.send(serverFrame)
        assertTrue("Server send should succeed", sendResult.isSuccess)

        val clientReceivedPacket = PacketCodec.decodeFromStream(clientIn).getOrThrow()
        assertEquals(MessageType.HELLO, clientReceivedPacket.type)
        assertEquals(String(helloPayload, Charsets.UTF_8), String(clientReceivedPacket.payload, Charsets.UTF_8))

        // Clean up
        server.disconnect()
        client.close()
    }
}
