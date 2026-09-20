package com.opendisplay.usb.capabilities

data class InputCapabilities(
    val hasTouch: Boolean,
    val hasKeyboard: Boolean,
    val hasMouse: Boolean,
    val hasStylus: Boolean = false
)
