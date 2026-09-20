# OpenDisplay USB

OpenDisplay USB turns Android phones and tablets into genuine, high-performance secondary displays for Windows PCs over a USB connection.

## Highlights
- **Universal Hardware Support**: Probes GPU encoders dynamically (NVIDIA NVENC, AMD AMF, Intel QSV, Software x264/x265) and supports all Android SoCs (Qualcomm, MediaTek, Exynos, Tensor, Unisoc).
- **Multi-Codec Handshake**: Runtime discovery and negotiation between H.264 and HEVC.
- **Ultra-Low Latency Video**: MediaCodec direct-to-surface decoding with high-precision monotonic frame pacing ($24 \dots 120\,\text{FPS}$).
- **Multi-Touch & Stylus Return**: Injects physical Android touch and pen events into Windows via `SendInput`.
- **WASAPI Audio Streaming**: Low-latency PCM loopback streaming directly to Android `AudioTrack`.
- **Bidirectional Clipboard**: Instant clipboard synchronization between Windows and Android.
- **$T_0 \dots T_{10}$ Latency Pipeline**: Full pipeline latency measurement with zero synthetic fabrication (strictly reporting unmeasurable metrics as N/A).
- **Automated Benchmark Suite**: Reproducible JSON benchmark generation (`run_benchmark.py`).

## Feature Roadmap
| Feature | Status |
|---|---|
| Core Protocol Definitions (V1) | ✅ Complete |
| ADB TCP Transport (`:7320`) | ✅ Complete |
| Android MediaCodec H.264/HEVC Decoding | ✅ Complete |
| Windows Host Video Capture & Multi-GPU Encoding | ✅ Complete |
| Multi-Touch Event Injection (`SendInput`) | ✅ Complete |
| WASAPI Audio Streaming | ✅ Complete |
| Bidirectional Clipboard Synchronization | ✅ Complete |
| Precision Clock Synchronization ($ppm$ drift) | ✅ Complete |
| Adaptive Performance Controller (5 Modes) | ✅ Complete |
| Physical Hardware Validation (Samsung Galaxy Tab A7) | ✅ Complete |
| IddCx Virtual Monitor Driver Source | ✅ Included |
| Native AOA/WinUSB Transport | 📋 Planned |

## Repository Structure
```text
OpenDisplay-USB/
├── android/              # Native Android Client (Kotlin / Compose)
│   ├── app/              # Main receiver application & UI
│   ├── core/             # Protocol, transport, capabilities & timing
│   ├── video/            # MediaCodec decoder & smart-drop frame queue
│   ├── audio/            # AudioTrack playback
│   ├── input/            # Touch & stylus event capture
│   ├── display/          # SurfaceView display management
│   └── ui/               # Jetpack Compose interface & diagnostics
├── windows/              # Windows Host Application (Python 3.10+)
│   ├── driver/           # IddCx Virtual Display Driver (C++)
│   ├── src/opendisplay/  # Video capture, encoder, audio, input, session
│   ├── tests/            # Automated test suite (pytest)
│   └── run_benchmark.py  # Automated performance & latency benchmark runner
├── protocol/             # Protocol specification & test vectors
├── ARCHITECTURE.md       # Architecture & system design
├── PROTOCOL.md           # Byte-level protocol specification
└── ANDROID_INTEGRATION.md# Cross-platform integration guide
```

## Quick Start

### 1. Android Receiver
1. Open the `android/` directory in Android Studio (JDK 17+).
2. Build and install:
   ```bash
   cd android
   ./gradlew installDebug
   ```
3. Launch the app on your Android tablet/phone.

### 2. Connect via USB (ADB)
```bash
adb forward tcp:7320 tcp:7320
```

### 3. Windows Host Streaming
1. Install Python dependencies:
   ```bash
   cd windows
   pip install -r requirements.txt
   ```
2. Start streaming:
   ```bash
   python -m opendisplay.main
   ```
3. Run automated latency benchmark:
   ```bash
   python run_benchmark.py --duration 15 --mode low_latency
   ```

## Documentation
- [Protocol Specification](PROTOCOL.md)
- [Architecture](ARCHITECTURE.md)
- [Android Integration Guide](ANDROID_INTEGRATION.md)

## License
Apache License 2.0.
