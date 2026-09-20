package com.opendisplay.usb.display

/**
 * Display orientation and scaling modes supported by the Android client.
 */
enum class ScalingMode {
    /** Letterbox to preserve aspect ratio without cropping. */
    FIT,
    /** Crop edges to fill screen while preserving aspect ratio. */
    CROP,
    /** Alias for CROP. */
    FILL,
    /** Stretch to fill screen ignoring aspect ratio. */
    STRETCH
}
