package com.opendisplay.usb.input

import android.view.MotionEvent
import com.opendisplay.usb.protocol.InputEventMessage
import com.opendisplay.usb.protocol.PointerInfo

/**
 * Encodes Android [MotionEvent] objects into [InputEventMessage] protocol messages.
 *
 * Coordinate normalization:
 *   normalized_x = raw_x / view_width_px   (clamped to 0.0..1.0)
 *   normalized_y = raw_y / view_height_px  (clamped to 0.0..1.0)
 *
 * The Windows side must scale back:
 *   absolute_x = normalized_x * virtual_display_width_px
 *
 * Multi-touch: all pointers in the event are encoded in the same message.
 *
 * Thread safety: stateless. Safe to call from any thread.
 */
class TouchEncoder {

    /**
     * Encodes a [MotionEvent] into an [InputEventMessage].
     *
     * @param event      the raw Android motion event
     * @param viewWidth  width of the rendering surface in pixels
     * @param viewHeight height of the rendering surface in pixels
     * @return the protocol message, or null if the event should be ignored
     *         (e.g., unknown tool type with no useful data)
     */
    fun encode(event: MotionEvent, viewWidth: Int, viewHeight: Int): InputEventMessage? {
        if (viewWidth <= 0 || viewHeight <= 0) return null

        val actionMasked = event.actionMasked
        val actionPointerIndex = event.actionIndex

        // Determine the action string for the active pointer
        val primaryAction = when (actionMasked) {
            MotionEvent.ACTION_DOWN,
            MotionEvent.ACTION_POINTER_DOWN      -> "DOWN"
            MotionEvent.ACTION_MOVE              -> "MOVE"
            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_POINTER_UP        -> "UP"
            MotionEvent.ACTION_CANCEL            -> "CANCEL"
            else                                 -> return null  // unhandled action
        }

        val pointers = (0 until event.pointerCount).map { i ->
            val action = when {
                actionMasked == MotionEvent.ACTION_MOVE -> "MOVE"
                i == actionPointerIndex                 -> primaryAction
                else                                    -> "MOVE"  // other pointers are implicitly MOVE
            }

            val normX = (event.getX(i) / viewWidth).coerceIn(0f, 1f)
            val normY = (event.getY(i) / viewHeight).coerceIn(0f, 1f)
            val pressure = event.getPressure(i).coerceIn(0f, 1f)
            val toolType = toolTypeString(event.getToolType(i))

            PointerInfo(
                id = event.getPointerId(i),
                action = action,
                x = normX,
                y = normY,
                pressure = pressure,
                toolType = toolType
            )
        }

        // timestampNs: MotionEvent.eventTime is in milliseconds since boot; convert to ns
        val timestampNs = event.eventTime * 1_000_000L

        val eventType = if (pointers.any { it.toolType == "STYLUS" }) "STYLUS" else "TOUCH"

        return InputEventMessage(
            eventType = eventType,
            timestampNs = timestampNs,
            pointers = pointers
        )
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun toolTypeString(toolType: Int): String = when (toolType) {
        MotionEvent.TOOL_TYPE_FINGER -> "FINGER"
        MotionEvent.TOOL_TYPE_STYLUS -> "STYLUS"
        MotionEvent.TOOL_TYPE_MOUSE  -> "MOUSE"
        MotionEvent.TOOL_TYPE_ERASER -> "ERASER"
        else                          -> "UNKNOWN"
    }

    companion object {
        /**
         * Standalone utility for normalizing a single coordinate.
         * Exposed for unit testing without requiring a MotionEvent.
         */
        fun normalizeCoordinate(value: Float, dimension: Int): Float {
            if (dimension <= 0) return 0f
            return (value / dimension).coerceIn(0f, 1f)
        }
    }
}
