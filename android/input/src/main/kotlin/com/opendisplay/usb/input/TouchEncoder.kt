package com.opendisplay.usb.input

import android.view.MotionEvent
import com.opendisplay.usb.protocol.InputEventMessage
import com.opendisplay.usb.protocol.PointerInfo

/**
 * Encodes Android [MotionEvent] objects into [InputEventMessage] protocol messages.
 *
 * Features:
 * - Up to 240Hz batch event extraction via [encodeBatch] and historical samples.
 * - Full S-Pen and active stylus support: toolType, pressure (0.0..1.0), tiltX, tiltY, buttons.
 * - Stylus hover tracking (ACTION_HOVER_MOVE) for Windows cursor preview.
 * - Multitouch pointer tracking and normalized coordinates (0.0..1.0).
 */
class TouchEncoder {

    /**
     * Encodes a single [MotionEvent] into an [InputEventMessage].
     */
    fun encode(event: MotionEvent, viewWidth: Int, viewHeight: Int): InputEventMessage? {
        val batch = encodeBatch(event, viewWidth, viewHeight)
        return batch.lastOrNull()
    }

    /**
     * Encodes a [MotionEvent] including all intermediate historical samples into a list of
     * [InputEventMessage] messages, delivering full 120-240Hz sampling accuracy.
     */
    fun encodeBatch(event: MotionEvent, viewWidth: Int, viewHeight: Int): List<InputEventMessage> {
        if (viewWidth <= 0 || viewHeight <= 0) return emptyList()

        val actionMasked = event.actionMasked
        val actionPointerIndex = event.actionIndex

        val primaryAction = when (actionMasked) {
            MotionEvent.ACTION_DOWN,
            MotionEvent.ACTION_POINTER_DOWN -> "DOWN"
            MotionEvent.ACTION_MOVE         -> "MOVE"
            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_POINTER_UP   -> "UP"
            MotionEvent.ACTION_CANCEL       -> "CANCEL"
            MotionEvent.ACTION_HOVER_MOVE   -> "HOVER"
            MotionEvent.ACTION_HOVER_ENTER  -> "HOVER_ENTER"
            MotionEvent.ACTION_HOVER_EXIT   -> "HOVER_EXIT"
            else                            -> return emptyList()
        }

        val messages = mutableListOf<InputEventMessage>()

        // 1. Process historical samples first if this is a MOVE event
        val historySize = event.historySize
        if (historySize > 0 && actionMasked == MotionEvent.ACTION_MOVE) {
            for (h in 0 until historySize) {
                val histTimeNs = event.getHistoricalEventTime(h) * 1_000_000L
                val histPointers = (0 until event.pointerCount).map { i ->
                    val normX = (event.getHistoricalX(i, h) / viewWidth).coerceIn(0f, 1f)
                    val normY = (event.getHistoricalY(i, h) / viewHeight).coerceIn(0f, 1f)
                    val pressure = event.getHistoricalPressure(i, h).coerceIn(0f, 1f)
                    val toolType = toolTypeString(event.getToolType(i))
                    val tiltRad = event.getHistoricalAxisValue(MotionEvent.AXIS_TILT, i, h)

                    PointerInfo(
                        id = event.getPointerId(i),
                        action = "MOVE",
                        x = normX,
                        y = normY,
                        pressure = pressure,
                        tiltX = tiltRad,
                        tiltY = tiltRad,
                        toolType = toolType,
                        buttons = event.buttonState
                    )
                }

                val eventType = if (histPointers.any { it.toolType == "STYLUS" || it.toolType == "ERASER" }) "STYLUS" else "TOUCH"
                messages.add(
                    InputEventMessage(
                        eventType = eventType,
                        timestampNs = histTimeNs,
                        pointers = histPointers
                    )
                )
            }
        }

        // 2. Process current motion sample
        val pointers = (0 until event.pointerCount).map { i ->
            val action = when {
                actionMasked == MotionEvent.ACTION_MOVE -> "MOVE"
                actionMasked == MotionEvent.ACTION_HOVER_MOVE -> "HOVER"
                i == actionPointerIndex                 -> primaryAction
                else                                    -> "MOVE"
            }

            val normX = (event.getX(i) / viewWidth).coerceIn(0f, 1f)
            val normY = (event.getY(i) / viewHeight).coerceIn(0f, 1f)
            val pressure = event.getPressure(i).coerceIn(0f, 1f)
            val toolType = toolTypeString(event.getToolType(i))
            val tiltRad = event.getAxisValue(MotionEvent.AXIS_TILT, i)

            PointerInfo(
                id = event.getPointerId(i),
                action = action,
                x = normX,
                y = normY,
                pressure = pressure,
                tiltX = tiltRad,
                tiltY = tiltRad,
                toolType = toolType,
                buttons = event.buttonState
            )
        }

        val timestampNs = event.eventTime * 1_000_000L
        val eventType = if (pointers.any { it.toolType == "STYLUS" || it.toolType == "ERASER" }) "STYLUS" else "TOUCH"

        messages.add(
            InputEventMessage(
                eventType = eventType,
                timestampNs = timestampNs,
                pointers = pointers
            )
        )

        return messages
    }

    private fun toolTypeString(toolType: Int): String = when (toolType) {
        MotionEvent.TOOL_TYPE_FINGER -> "FINGER"
        MotionEvent.TOOL_TYPE_STYLUS -> "STYLUS"
        MotionEvent.TOOL_TYPE_MOUSE  -> "MOUSE"
        MotionEvent.TOOL_TYPE_ERASER -> "ERASER"
        else                          -> "UNKNOWN"
    }

    companion object {
        fun normalizeCoordinate(value: Float, dimension: Int): Float {
            if (dimension <= 0) return 0f
            return (value / dimension).coerceIn(0f, 1f)
        }
    }
}
