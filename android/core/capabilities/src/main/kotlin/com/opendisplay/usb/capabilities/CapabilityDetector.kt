package com.opendisplay.usb.capabilities

import android.content.Context
import android.hardware.input.InputManager
import android.media.AudioManager
import android.media.MediaCodecList
import android.os.Build
import android.view.InputDevice
import android.view.WindowManager

class CapabilityDetector(private val context: Context) {

    fun detectCapabilities(): DeviceCapabilities {
        return DeviceCapabilities(
            deviceInfo = detectDeviceInfo(),
            display = detectDisplayCapabilities(),
            video = detectVideoCapabilities(),
            audio = detectAudioCapabilities(),
            input = detectInputCapabilities()
        )
    }

    private fun detectDeviceInfo(): DeviceInfo {
        return DeviceInfo(
            manufacturer = Build.MANUFACTURER,
            model = Build.MODEL,
            osVersion = Build.VERSION.RELEASE
        )
    }

    private fun detectDisplayCapabilities(): DisplayCapabilities {
        val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val display = windowManager.defaultDisplay
        val metrics = android.util.DisplayMetrics()
        display.getRealMetrics(metrics)

        val supportedRates = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                display.supportedModes.map { it.refreshRate }.distinct().sorted()
            } catch (e: Exception) {
                listOf(display.refreshRate)
            }
        } else {
            listOf(display.refreshRate)
        }

        return DisplayCapabilities(
            physicalWidth = metrics.widthPixels,
            physicalHeight = metrics.heightPixels,
            refreshRate = display.refreshRate,
            densityDpi = metrics.densityDpi,
            supportedRefreshRates = if (supportedRates.isNotEmpty()) supportedRates else listOf(display.refreshRate)
        )
    }

    private fun detectVideoCapabilities(): VideoCapabilities {
        val codecList = MediaCodecList(MediaCodecList.ALL_CODECS)
        val supportedCodecs = mutableListOf<VideoCodec>()
        var maxWidth = 1920
        var maxHeight = 1080
        var maxFps = 60

        for (info in codecList.codecInfos) {
            if (info.isEncoder) continue
            if (DeviceCompatibilityProvider.isDecoderExcluded(info.name)) continue

            val types = info.supportedTypes
            for (type in types) {
                when (type) {
                    "video/avc" -> supportedCodecs.add(VideoCodec.H264)
                    "video/hevc" -> supportedCodecs.add(VideoCodec.H265)
                    "video/x-vnd.on2.vp8" -> supportedCodecs.add(VideoCodec.VP8)
                    "video/x-vnd.on2.vp9" -> supportedCodecs.add(VideoCodec.VP9)
                    "video/av01" -> supportedCodecs.add(VideoCodec.AV1)
                }

                try {
                    val caps = info.getCapabilitiesForType(type)
                    caps.videoCapabilities?.let { vCaps ->
                        maxWidth = maxOf(maxWidth, vCaps.supportedWidths.upper)
                        maxHeight = maxOf(maxHeight, vCaps.supportedHeights.upper)
                        maxFps = maxOf(maxFps, vCaps.supportedFrameRates.upper.toInt())
                    }
                } catch (e: Exception) {
                    // Ignore capability query failure on legacy codecs
                }
            }
        }

        return VideoCapabilities(
            supportedCodecs = supportedCodecs.distinct(),
            maxResolutionWidth = maxWidth,
            maxResolutionHeight = maxHeight,
            maxFps = maxFps
        )
    }

    private fun detectAudioCapabilities(): AudioCapabilities {
        return AudioCapabilities(
            supportedCodecs = listOf(AudioCodec.AAC, AudioCodec.OPUS),
            maxChannels = 2,
            maxSampleRate = 48000
        )
    }

    private fun detectInputCapabilities(): InputCapabilities {
        var hasTouch = false
        var hasKeyboard = false
        var hasMouse = false
        var hasStylus = false

        val inputManager = context.getSystemService(Context.INPUT_SERVICE) as InputManager
        for (deviceId in inputManager.inputDeviceIds) {
            val device = inputManager.getInputDevice(deviceId) ?: continue
            val sources = device.sources

            if (sources and InputDevice.SOURCE_TOUCHSCREEN == InputDevice.SOURCE_TOUCHSCREEN) {
                hasTouch = true
            }
            if (sources and InputDevice.SOURCE_STYLUS == InputDevice.SOURCE_STYLUS) {
                hasStylus = true
            }
            if (sources and InputDevice.SOURCE_KEYBOARD == InputDevice.SOURCE_KEYBOARD) {
                hasKeyboard = true
            }
            if (sources and InputDevice.SOURCE_MOUSE == InputDevice.SOURCE_MOUSE) {
                hasMouse = true
            }
        }

        return InputCapabilities(
            hasTouch = hasTouch,
            hasKeyboard = hasKeyboard,
            hasMouse = hasMouse,
            hasStylus = hasStylus
        )
    }
}
