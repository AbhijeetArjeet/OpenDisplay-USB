package com.opendisplay.usb.display

import com.opendisplay.usb.protocol.DisplayConfigMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Thrown when a [DisplayConfigMessage] is incompatible with the device.
 *
 * Android MUST return DISPLAY_CONFIG_ACK with accepted=false when this is thrown.
 * It MUST NOT silently apply an incompatible configuration.
 */
class DisplayConfigException(message: String) : Exception(message)

/**
 * Validates and applies [DisplayConfigMessage] from the Windows host.
 *
 * Rules:
 * - Configuration is validated before being applied.
 * - Incompatible configurations return [Result.failure] — never silently ignored.
 * - Resolution changes notify observers via [activeConfig] [StateFlow].
 * - The video decoder MUST be reset after a resolution change (handled by SessionManager).
 *
 * Thread safety: thread-safe. [apply] may be called from any coroutine.
 */
class DisplayConfigurator {

    private val _activeConfig = MutableStateFlow<DisplayInfo?>(null)
    val activeConfig: StateFlow<DisplayInfo?> = _activeConfig.asStateFlow()

    // Device physical limits (set by the CapabilityDetector in a real session;
    // defaults are conservative)
    private var deviceMaxWidthPx: Int = 4096
    private var deviceMaxHeightPx: Int = 4096
    private var deviceMaxFps: Float = 120f

    /**
     * Updates the device physical limits. Call this after [CapabilityDetector] runs.
     */
    fun setDeviceLimits(maxWidthPx: Int, maxHeightPx: Int, maxFps: Float) {
        deviceMaxWidthPx = maxWidthPx
        deviceMaxHeightPx = maxHeightPx
        deviceMaxFps = maxFps
    }

    /**
     * Validates and applies a [DisplayConfigMessage].
     *
     * @return [Result.success] with the new [DisplayInfo] on success.
     * @return [Result.failure] with [DisplayConfigException] if the config is incompatible.
     */
    fun apply(config: DisplayConfigMessage): Result<DisplayInfo> {
        // Validate dimensions
        if (config.widthPx <= 0 || config.heightPx <= 0) {
            return Result.failure(
                DisplayConfigException("Invalid dimensions: ${config.widthPx}x${config.heightPx}")
            )
        }
        if (config.widthPx > deviceMaxWidthPx || config.heightPx > deviceMaxHeightPx) {
            return Result.failure(
                DisplayConfigException(
                    "Resolution ${config.widthPx}x${config.heightPx} exceeds device maximum " +
                    "${deviceMaxWidthPx}x${deviceMaxHeightPx}"
                )
            )
        }

        // Validate frame rate
        if (config.frameRateHz <= 0f || config.frameRateHz > deviceMaxFps) {
            return Result.failure(
                DisplayConfigException(
                    "Frame rate ${config.frameRateHz}fps is out of range (max: ${deviceMaxFps}fps)"
                )
            )
        }

        // Validate orientation
        if (config.orientation !in 0..3) {
            return Result.failure(
                DisplayConfigException("Invalid orientation: ${config.orientation}")
            )
        }

        // Validate scaling mode
        val scalingMode = when (config.scaling.uppercase()) {
            "FIT"     -> ScalingMode.FIT
            "CROP"    -> ScalingMode.CROP
            "STRETCH" -> ScalingMode.STRETCH
            else      -> return Result.failure(
                DisplayConfigException("Unknown scaling mode: '${config.scaling}'")
            )
        }

        val displayInfo = DisplayInfo(
            widthPx = config.widthPx,
            heightPx = config.heightPx,
            frameRateHz = config.frameRateHz,
            orientation = config.orientation,
            pixelFormat = config.pixelFormat,
            scalingMode = scalingMode
        )

        val previousConfig = _activeConfig.value
        _activeConfig.value = displayInfo

        if (previousConfig != null &&
            (previousConfig.widthPx != displayInfo.widthPx ||
             previousConfig.heightPx != displayInfo.heightPx)) {
            // Resolution changed — SessionManager observes activeConfig and resets the decoder
        }

        return Result.success(displayInfo)
    }
}
