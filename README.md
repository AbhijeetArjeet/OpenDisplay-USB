# OpenDisplay USB

OpenDisplay USB turns Android phones and tablets into genuine, high-performance secondary displays for Windows PCs over a USB connection.

## Current Status
Currently in **Phase 1**: Android receiver + mock transport implementation.

## Feature Roadmap
| Feature | Status |
|---|---|
| Core Protocol Definitions | ✅ Phase 1 |
| Mock Transport (TCP) | ✅ Phase 1 |
| Android H.264 Decoding | 🔄 In Progress |
| Windows Virtual Display Driver | 📋 Planned |
| Native USB Transport | 📋 Planned |
| Touch Input Forwarding | 📋 Planned |

## Repository Structure
```text
usbcaster2.0/
├── app/                  # Main Android Application
├── core/
│   ├── protocol/         # Protocol parsing and serialization
│   ├── transport/        # Transport abstraction
│   ├── timing/           # Clock sync & latency
│   └── capabilities/     # Device feature discovery
├── video/                # MediaCodec H.264/HEVC decoding
├── audio/                # AudioTrack playback
├── input/                # Touch and event capture
├── display/              # Window management
├── ui/                   # Jetpack Compose UI
├── diagnostics/          # Metrics and monitoring
├── protocol/
│   └── test-vectors/     # Protocol JSON/binary examples
└── README.md
```

## Quick Start
1. Ensure you have Android Studio and JDK 17+ installed.
2. Clone this repository and open it in Android Studio.
3. Build the debug APK: `cd android && ./gradlew assembleDebug` (or via IDE).
4. Install on your device: `adb install app/build/outputs/apk/debug/app-debug.apk`
5. Enable mock mode in the app Settings -> Connection -> Use Mock Transport.

To run tests: `./gradlew test`

## Documentation
- [Protocol Specification](PROTOCOL.md)
- [Android Integration Guide](ANDROID_INTEGRATION.md)
- [Architecture](ARCHITECTURE.md)

## License
Apache License, Version 2.0. See LICENSE for more information.

> This repository contains the Android client only.
> The Windows virtual display driver and transport manager
> will be implemented separately. See ANDROID_INTEGRATION.md
> for the interface contract.
