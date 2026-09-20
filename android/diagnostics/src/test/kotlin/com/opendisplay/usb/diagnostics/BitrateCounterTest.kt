package com.opendisplay.usb.diagnostics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BitrateCounterTest {

    @Test
    fun testZeroBytes() {
        val counter = BitrateCounter()
        assertEquals(0f, counter.getKbps(1000L), 0.001f)
    }

    @Test
    fun testBitrateCalculation() {
        val counter = BitrateCounter(windowMs = 1000L)
        val startNs = 1_000_000_000L
        // 125,000 bytes per second = 1,000,000 bits per second = 1,000 Kbps = 1 Mbps
        counter.recordBytes(125_000, startNs)

        val kbps = counter.getKbps(startNs + 1_000_000_000L)
        assertTrue("Bitrate should be approximately 1000 Kbps, got $kbps", kbps in 900f..1100f)
    }

    @Test
    fun testReset() {
        val counter = BitrateCounter()
        counter.recordBytes(5000, 100L)
        counter.reset()
        assertEquals(0f, counter.getKbps(200L), 0.001f)
    }
}
