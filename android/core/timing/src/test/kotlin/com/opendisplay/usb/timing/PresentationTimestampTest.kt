package com.opendisplay.usb.timing

import org.junit.Assert.assertEquals
import org.junit.Test

class PresentationTimestampTest {

    @Test
    fun testPtsConversions() {
        val pts = PresentationTimestamp(1_500_000_000L) // 1.5 seconds
        assertEquals(1_500_000_000L, pts.ptsNanos)
        assertEquals(1_500_000L, pts.us)
        assertEquals(1_500L, pts.ms)
        assertEquals(1.5, pts.seconds, 0.0001)
    }

    @Test
    fun testArithmetic() {
        val t1 = PresentationTimestamp(1_000_000_000L)
        val t2 = PresentationTimestamp(500_000_000L)
        val sum = t1 + t2
        val diff = t1 - t2
        assertEquals(1_500_000_000L, sum.ptsNanos)
        assertEquals(500_000_000L, diff.ptsNanos)
    }

    @Test
    fun testBuilders() {
        assertEquals(1_000_000L, PresentationTimestamp.fromMillis(1).ptsNanos)
        assertEquals(1_000L, PresentationTimestamp.fromMicros(1).ptsNanos)
        assertEquals(0L, PresentationTimestamp.ZERO.ptsNanos)
    }
}
