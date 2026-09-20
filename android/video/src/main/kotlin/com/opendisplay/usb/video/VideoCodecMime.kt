package com.opendisplay.usb.video

object VideoCodecMime {
    const val H264 = "video/avc"
    const val HEVC = "video/hevc"
    const val AV1 = "video/av01"
    const val VP8 = "video/x-vnd.on2.vp8"
    const val VP9 = "video/x-vnd.on2.vp9"

    fun fromProtocolName(name: String): String = when (name.uppercase()) {
        "H264", "AVC" -> H264
        "HEVC", "H265" -> HEVC
        "AV1" -> AV1
        "VP8" -> VP8
        "VP9" -> VP9
        else -> name
    }
}
