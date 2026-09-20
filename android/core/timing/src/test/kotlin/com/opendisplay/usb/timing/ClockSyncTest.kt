package com.opendisplay.usb.timing

import org.junit.Assert.assertEquals
import org.junit.Test

class ClockSyncTest {

    private class TestClock(var timeNanos: Long = 0L) : MonotonicClock {
        override fun nowNanos(): Long = timeNanos
    }

    @Test
    fun testManualOffset() {
        val sync = ClockSync()
        sync.updateOffset(1000L, 2000L)
        assertEquals(1000L, sync.offsetNanos)
        assertEquals(2500L, sync.hostToDevice(1500L))
        assertEquals(1500L, sync.deviceToHost(2500L))
    }

    @Test
    fun testPingPongMeasurement() {
        val clock = TestClock(timeNanos = 10_000_000L)
        val sync = ClockSync(clock)

        val pingTs = sync.onPingSent()
        assertEquals(10_000_000L, pingTs)

        // Advance clock by 20ms (20,000,000ns)
        clock.timeNanos = 30_000_000L
        sync.onPongReceived(pingTs)

        assertEquals(20f, sync.roundTripLatencyMs, 0.001f)
        assertEquals(10f, sync.estimatedLatencyMs, 0.001f)
    }
}
