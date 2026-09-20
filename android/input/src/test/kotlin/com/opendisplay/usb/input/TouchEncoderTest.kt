package com.opendisplay.usb.input

import org.junit.Assert.assertEquals
import org.junit.Test

class TouchEncoderTest {

    @Test
    fun `normalizeCoordinate returns zero when dimension is non-positive`() {
        assertEquals(0f, TouchEncoder.normalizeCoordinate(100f, 0), 0.0001f)
        assertEquals(0f, TouchEncoder.normalizeCoordinate(100f, -50), 0.0001f)
    }

    @Test
    fun `normalizeCoordinate centers properly`() {
        assertEquals(0.5f, TouchEncoder.normalizeCoordinate(500f, 1000), 0.0001f)
        assertEquals(0.5f, TouchEncoder.normalizeCoordinate(1000f, 2000), 0.0001f)
    }

    @Test
    fun `normalizeCoordinate clamps out-of-bounds coordinates`() {
        assertEquals(0.0f, TouchEncoder.normalizeCoordinate(-50f, 1000), 0.0001f)
        assertEquals(1.0f, TouchEncoder.normalizeCoordinate(1500f, 1000), 0.0001f)
    }

    @Test
    fun `normalizeCoordinate exact bounds`() {
        assertEquals(0.0f, TouchEncoder.normalizeCoordinate(0f, 1920), 0.0001f)
        assertEquals(1.0f, TouchEncoder.normalizeCoordinate(1920f, 1920), 0.0001f)
    }
}
