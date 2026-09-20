package com.opendisplay.usb.input

import android.view.MotionEvent

data class StylusEventMessage(
    val x: Float,
    val y: Float,
    val pressure: Float,
    val tiltX: Float,
    val tiltY: Float,
    val action: Int
)

class StylusEncoder(private val width: Float, private val height: Float) {
    fun encode(event: MotionEvent): StylusEventMessage {
        val normX = event.x / width
        val normY = event.y / height
        val pressure = event.pressure
        val tiltX = event.getAxisValue(MotionEvent.AXIS_TILT)
        val tiltY = event.getAxisValue(MotionEvent.AXIS_TILT) // Simple mock
        return StylusEventMessage(normX, normY, pressure, tiltX, tiltY, event.actionMasked)
    }
}
