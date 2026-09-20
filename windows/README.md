# OpenDisplay USB — Windows Client

This directory contains the Windows host implementation of **OpenDisplay USB**.

The Windows client turns an Android tablet or phone into a genuine secondary display by acquiring desktop/virtual display frames, hardware-encoding them to low-latency H.264, and transmitting them over USB via the OpenDisplay Protocol.

---

## Architecture Overview

```text
c:\usbcaster2.0\windows\
├── driver\                         # Windows IDD (Indirect Display Driver) UMDF v2 / IddCx
│   ├── OpenDisplayIdd.inf          # Driver installation directive
│   ├── Driver.h / Driver.cpp       # DriverEntry, WDF device callbacks
│   ├── Device.h / Device.cpp       # IddCxDeviceInit, monitor arrival
│   ├── Monitor.h / Monitor.cpp     # Virtual monitor EDID, mode lists (1080p, 2K, 60/120Hz)
│   ├── Swapchain.h / Swapchain.cpp # Buffer acquisition and frame presentation
│   └── install.ps1                 # Driver installation helper
├── src\
│   └── opendisplay\
│       ├── protocol\               # 11-byte ODSP framing, JsonCodec, and message models
│       ├── transport\              # ITransport, AdbTransport, TcpTransport, MockTransport
│       ├── display\                # Virtual monitor modes & Desktop Duplication frame capture
│       ├── video\                  # Hardware H.264/HEVC encoder & SPS/PPS CSD extraction
│       ├── audio\                  # WASAPI loopback audio capture & packetizer
│       ├── input\                  # Normalization reversal & Windows SendInput injection
│       ├── timing\                 # MonotonicClock and ClockSync RTT tracker
│       ├── diagnostics\            # Real-time FPS, bitrate, and latency metrics
│       ├── session\                # 7-stage protocol handshake & auto-reconnect backoff
│       └── ui\                     # Modern PyQt6 desktop application UI
├── tests\                          # Test suite (test vectors, framing, end-to-end mock stream)
└── requirements.txt
```

---

## Features

1. **IddCx Virtual Monitor Driver**: Complete UMDF v2 driver implementing indirect display swapchain and monitor EDID.
2. **Ultra Low-Latency H.264 Encoding**: Hardware encoding using NVENC, Intel QuickSync, or AMD AMF with `libx264` fallback (`zerolatency`, CBR rate control).
3. **Automated ADB Port Forwarding**: Discovers connected devices and auto-provisions `adb forward tcp:7320 tcp:7320`.
4. **Touch & Stylus Input**: Converts normalized 0.0..1.0 coordinates into Windows screen coordinates and dispatches via `SendInput`.
5. **Modern Desktop UI**: Dark-themed PyQt6 dashboard displaying live FPS, bitrate, round-trip latency, resolution selector, and connection controls.
6. **Self-Healing Reconnection**: Automatically retries dropped USB connections using exponential backoff (2s → 4s → 8s → 16s → 30s max, up to 5 attempts).

---

## Running the Windows Client

### Prerequisites
```bash
pip install -r requirements.txt
```

### Launch GUI Dashboard
```bash
set PYTHONPATH=src
python -m opendisplay.main
```

### Launch in Headless / Mock Test Mode
```bash
set PYTHONPATH=src
python -m opendisplay.main --cli --mock
```

---

## Running Automated Verification Tests

To verify 100% interoperability against the protocol test vectors and mock stream:
```bash
set PYTHONPATH=src
python -m pytest tests -v
```
