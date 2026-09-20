package com.opendisplay.usb.protocol

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class PacketCodecTest {

    // ── encode ────────────────────────────────────────────────────────────────

    @Test
    fun `encode produces correct magic bytes at offset 0`() {
        val frame = PacketCodec.encode(MessageType.PING, ByteArray(0))
        assertEquals(0x4F.toByte(), frame[0])  // 'O'
        assertEquals(0x44.toByte(), frame[1])  // 'D'
        assertEquals(0x53.toByte(), frame[2])  // 'S'
        assertEquals(0x50.toByte(), frame[3])  // 'P'
    }

    @Test
    fun `encode produces correct version byte at offset 4`() {
        val frame = PacketCodec.encode(MessageType.PING, ByteArray(0))
        assertEquals(ProtocolVersion.CURRENT.toByte(), frame[4])
    }

    @Test
    fun `encode produces correct type ID little-endian at offset 5`() {
        val frame = PacketCodec.encode(MessageType.HELLO, ByteArray(0))
        val typeId = ByteBuffer.wrap(frame, 5, 2).order(ByteOrder.LITTLE_ENDIAN).short.toUShort()
        assertEquals(MessageType.HELLO.id, typeId)
    }

    @Test
    fun `encode produces correct payload length little-endian at offset 7`() {
        val payload = ByteArray(100) { 0xAB.toByte() }
        val frame = PacketCodec.encode(MessageType.HELLO, payload)
        val length = ByteBuffer.wrap(frame, 7, 4).order(ByteOrder.LITTLE_ENDIAN).int
        assertEquals(100, length)
    }

    @Test
    fun `encode with empty payload produces header-only frame`() {
        val frame = PacketCodec.encode(MessageType.PING)
        assertEquals(ProtocolVersion.HEADER_SIZE, frame.size)
    }

    @Test
    fun `encode with payload embeds payload bytes starting at offset 11`() {
        val payload = byteArrayOf(0x01, 0x02, 0x03)
        val frame = PacketCodec.encode(MessageType.PING, payload)
        assertEquals(0x01.toByte(), frame[11])
        assertEquals(0x02.toByte(), frame[12])
        assertEquals(0x03.toByte(), frame[13])
    }

    // ── encode/decode round-trip ───────────────────────────────────────────────

    @Test
    fun `encodeDecodeRoundTrip HELLO with JSON payload`() {
        val originalPayload = """{"type":"HELLO","protocol":1}""".toByteArray(Charsets.UTF_8)
        val frame = PacketCodec.encode(MessageType.HELLO, originalPayload)
        val result = PacketCodec.decode(frame)
        assertTrue(result.isSuccess)
        val packet = result.getOrThrow()
        assertEquals(MessageType.HELLO, packet.type)
        assertEquals(ProtocolVersion.CURRENT.toByte(), packet.version)
        assertArrayEquals(originalPayload, packet.payload)
    }

    @Test
    fun `encodeDecodeRoundTrip VIDEO_FRAME with binary payload`() {
        val binaryPayload = ByteArray(1024) { it.toByte() }
        val frame = PacketCodec.encode(MessageType.VIDEO_FRAME, binaryPayload)
        val result = PacketCodec.decode(frame)
        assertTrue(result.isSuccess)
        val packet = result.getOrThrow()
        assertEquals(MessageType.VIDEO_FRAME, packet.type)
        assertArrayEquals(binaryPayload, packet.payload)
    }

    @Test
    fun `encodeDecodeRoundTrip all 19 message types`() {
        for (type in MessageType.entries) {
            val payload = byteArrayOf(0xDE.toByte(), 0xAD.toByte())
            val frame = PacketCodec.encode(type, payload)
            val result = PacketCodec.decode(frame)
            assertTrue("Round-trip failed for $type", result.isSuccess)
            assertEquals(type, result.getOrThrow().type)
        }
    }

    // ── decode — valid edge cases ──────────────────────────────────────────────

    @Test
    fun `decode empty payload succeeds`() {
        val frame = PacketCodec.encode(MessageType.PING)  // no payload
        val result = PacketCodec.decode(frame)
        assertTrue(result.isSuccess)
        assertEquals(0, result.getOrThrow().payload.size)
    }

    // ── decode — malformed inputs ──────────────────────────────────────────────

    @Test
    fun `decode returns failure for frame shorter than header`() {
        val shortFrame = ByteArray(5) { 0x00 }
        val result = PacketCodec.decode(shortFrame)
        assertTrue(result.isFailure)
        assertIs<PacketDecodeException>(result.exceptionOrNull())
    }

    @Test
    fun `decode returns failure for bad magic bytes`() {
        val frame = PacketCodec.encode(MessageType.HELLO, byteArrayOf(0x7B, 0x7D))
        // Corrupt the magic
        frame[0] = 0x58  // 'X' instead of 'O'
        val result = PacketCodec.decode(frame)
        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertIs<PacketDecodeException>(ex)
        assertTrue(ex?.message?.contains("magic", ignoreCase = true) == true)
    }

    @Test
    fun `decode returns failure for payload length exceeding 16MB`() {
        // Construct a frame with PAYLOAD_LEN = 0xFFFFFFFF (4294967295)
        val fakeFrame = ByteArray(ProtocolVersion.HEADER_SIZE + 2)
        fakeFrame[0] = 0x4F; fakeFrame[1] = 0x44; fakeFrame[2] = 0x53; fakeFrame[3] = 0x50
        fakeFrame[4] = 0x01  // version
        ByteBuffer.wrap(fakeFrame, 5, 2).order(ByteOrder.LITTLE_ENDIAN)
            .putShort(MessageType.HELLO.id.toShort())
        ByteBuffer.wrap(fakeFrame, 7, 4).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(ProtocolVersion.MAX_PAYLOAD_BYTES + 1)  // overflow
        val result = PacketCodec.decode(fakeFrame)
        assertTrue(result.isFailure)
        assertIs<PacketDecodeException>(result.exceptionOrNull())
    }

    @Test
    fun `decode returns failure for truncated payload`() {
        val payload = ByteArray(100) { 0xAB.toByte() }
        val fullFrame = PacketCodec.encode(MessageType.HELLO, payload)
        // Give only partial frame (header + 50 bytes of 100)
        val truncated = fullFrame.copyOf(ProtocolVersion.HEADER_SIZE + 50)
        val result = PacketCodec.decode(truncated)
        assertTrue(result.isFailure)
        assertIs<PacketDecodeException>(result.exceptionOrNull())
    }

    @Test
    fun `decode returns failure for unknown message type`() {
        val fakeFrame = ByteArray(ProtocolVersion.HEADER_SIZE + 2)
        fakeFrame[0] = 0x4F; fakeFrame[1] = 0x44; fakeFrame[2] = 0x53; fakeFrame[3] = 0x50
        fakeFrame[4] = 0x01
        ByteBuffer.wrap(fakeFrame, 5, 2).order(ByteOrder.LITTLE_ENDIAN)
            .putShort(0xFFFF.toShort())  // Unknown type
        ByteBuffer.wrap(fakeFrame, 7, 4).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(2)  // 2 byte payload
        fakeFrame[11] = 0x7B; fakeFrame[12] = 0x7D  // "{}"
        val result = PacketCodec.decode(fakeFrame)
        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertIs<PacketDecodeException>(ex)
        assertTrue(ex?.message?.contains("Unknown", ignoreCase = true) == true)
    }

    // ── VIDEO_FRAME binary payload helpers ────────────────────────────────────

    @Test
    fun `encodeVideoFramePayload roundTrip preserves all fields`() {
        val ts = 1_000_000_000L
        val nalData = byteArrayOf(0x00, 0x00, 0x00, 0x01, 0x65)  // IDR start code
        val payload = PacketCodec.encodeVideoFramePayload(ts, isKeyframe = true, nalData = nalData)
        val (decodedTs, isKeyframe, dataOffset) = PacketCodec.decodeVideoFramePayload(payload)
        assertEquals(ts, decodedTs)
        assertTrue(isKeyframe)
        assertArrayEquals(nalData, payload.copyOfRange(dataOffset, payload.size))
    }

    @Test
    fun `decodeVideoFramePayload returns failure for payload shorter than 12 bytes`() {
        assertThrows(PacketDecodeException::class.java) {
            PacketCodec.decodeVideoFramePayload(ByteArray(8))
        }
    }

    // ── Helper ────────────────────────────────────────────────────────────────

    private inline fun <reified T : Throwable> assertThrows(
        clazz: Class<T>,
        block: () -> Unit
    ) {
        try {
            block()
            fail("Expected ${clazz.simpleName} to be thrown")
        } catch (e: Throwable) {
            if (!clazz.isInstance(e)) throw e
        }
    }

    private inline fun <reified T> assertIs(value: Any?) {
        assertTrue(
            "Expected ${T::class.simpleName} but got ${value?.javaClass?.simpleName}",
            value is T
        )
    }
}
