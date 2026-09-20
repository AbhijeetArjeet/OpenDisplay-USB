package com.opendisplay.usb.protocol

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class JsonCodecTest {

    @Test
    fun testHelloMessageRoundTrip() {
        val msg = HelloMessage(
            type = "HELLO",
            protocol = 1,
            platform = "android",
            manufacturer = "Samsung",
            model = "SM-T505",
            androidVersion = "10",
            sdk = 29,
            deviceId = "test-device-123"
        )
        val bytes = JsonCodec.encode(msg)
        val decodedResult = JsonCodec.decodeHello(bytes)
        assertTrue(decodedResult.isSuccess)
        assertEquals(msg, decodedResult.getOrThrow())
    }

    @Test
    fun testDisplayConfigRoundTrip() {
        val msg = DisplayConfigMessage(
            widthPx = 1920,
            heightPx = 1080,
            frameRateHz = 60f,
            orientation = 1,
            pixelFormat = "RGBA_8888",
            scaling = "FIT"
        )
        val bytes = JsonCodec.encode(msg)
        val decodedResult = JsonCodec.decodeDisplayConfig(bytes)
        assertTrue(decodedResult.isSuccess)
        assertEquals(msg, decodedResult.getOrThrow())
    }

    @Test
    fun testVideoConfigRoundTrip() {
        val msg = VideoConfigMessage(
            codec = "H264",
            widthPx = 1920,
            heightPx = 1080,
            frameRateHz = 60f,
            bitrateBps = 10_000_000,
            keyframeIntervalS = 2f,
            lowLatencyMode = true,
            csd0Base64 = "AAAA",
            csd1Base64 = "BBBB"
        )
        val bytes = JsonCodec.encode(msg)
        val decodedResult = JsonCodec.decodeVideoConfig(bytes)
        assertTrue(decodedResult.isSuccess)
        assertEquals(msg, decodedResult.getOrThrow())
    }

    @Test
    fun testPeekType() {
        val json = """{"type":"HELLO","protocol":1}""".toByteArray(Charsets.UTF_8)
        assertEquals("HELLO", JsonCodec.peekType(json))
    }

    @Test
    fun testDecodeIncomingDispatch() {
        val ping = PingMessage(type = "PING", timestampNs = 123456L)
        val bytes = JsonCodec.encode(ping)
        val result = JsonCodec.decodeIncoming(bytes, MessageType.PING)
        assertTrue(result.isSuccess)
        assertEquals(ping, result.getOrThrow())
    }
}
