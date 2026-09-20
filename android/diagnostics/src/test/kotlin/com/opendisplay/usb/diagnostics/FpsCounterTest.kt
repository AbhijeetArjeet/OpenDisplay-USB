package com.opendisplay.usb.diagnostics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FpsCounterTest {

    @Test
    fun testZeroFrames() {
        val counter = FpsCounter()
        assertEquals(0f, counter.getFps(1000L), 0.001f)
    }

    @Test
    fun testSingleFrame() {
        val counter = FpsCounter()
        counter.recordFrame(1_000_000_000L)
        assertEquals(0f, counter.getFps(1_000_000_000L), 0.001f)
    }

    @Test
    fun testFpsCalculationRollingWindow() {
        val counter = FpsCounter(windowMs = 1000L) // 1 second window
        val startNs = 1_000_000_000L

        // Record 61 frames across 1 second (every 16.666ms) -> 60 fps
        val intervalNs = 1_000_000_000L / 60
        for (i in 0..60) {
            counter.recordFrame(startNs + i * intervalNs)
        }

        val fps = counter.getFps(startNs + 60 * intervalNs)
        assertTrue("FPS should be around 60: $fps", fps in 59.0f..61.0f)
    }

    @Test
    fun testReset() {
        val counter = FpsCounter()
        counter.recordFrame(100L)
        counter.reset()
        assertEquals(0f, counter.getFps(200L), 0.001f)
    }
}
