package com.opendisplay.usb.display

enum class Orientation {
    PORTRAIT, LANDSCAPE
}

class OrientationManager {
    var currentOrientation: Orientation = Orientation.PORTRAIT
        private set

    fun setOrientation(orientation: Orientation) {
        currentOrientation = orientation
    }
}
