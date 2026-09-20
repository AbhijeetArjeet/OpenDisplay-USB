# OpenDisplay USB — Android Integration Guide

> **Audience**: This document is written for the **Windows-side development agent**.
> It provides everything needed to implement the Windows host without reading any Android source code.
> The Android app is the server; the Windows host is the client.

---

## 1. Overview

The Android app opens a TCP `ServerSocket` on port **7320** and waits for the Windows host to connect.

Connection setup:

```
Windows host
    │
    │  (1) USB cable attached
    │
    ▼
adb forward tcp:7320 tcp:7320
    │
    │  (2) TCP connection to 127.0.0.1:7320
    │
    ▼
Android app (listening on :7320)
```

Once connected, the protocol proceeds through a defined handshake, then enters the streaming phase.

> **Transport note**: In Phase 1 the Android app uses a `FakeTransport` internally for development.
> When the real ADB/USB transport is implemented, the app will listen on port 7320 and the framing
> described here is exactly what flows over that socket.

---

## 2. Binary Frame Format

**Every message** is wrapped in an 11-byte header followed by a payload:

```
Offset  Len  Endian  Field           Description
──────  ───  ──────  ──────          ───────────────────────────────────────────
  0      4   n/a     MAGIC           ASCII "ODSP" = 0x4F 0x44 0x53 0x50
  4      1   n/a     VERSION         Protocol version byte = 0x01
  5      2   LE      MSG_TYPE        Message type ID (uint16). See §3.
  7      4   LE      PAYLOAD_LEN     Payload length in bytes (uint32). 0 .. 16,777,216.
 11      N   n/a     PAYLOAD         UTF-8 JSON, or binary for VIDEO_FRAME / AUDIO_FRAME.
```

Rules:
- All multi-byte integers (MSG_TYPE, PAYLOAD_LEN) are **little-endian**.
- MAGIC is four raw bytes — do not interpret as a multi-byte integer.
- Maximum PAYLOAD_LEN: **16,777,216** bytes (16 MiB). Larger frames MUST be rejected.
- Unknown MSG_TYPE values MUST be silently discarded — do not disconnect.

### 2.1 Annotated hex dump — HELLO_ACK example

```
4F 44 53 50  │  Magic "ODSP"
01           │  Protocol version 1
02 00        │  MSG_TYPE = 0x0002 (HELLO_ACK), little-endian
2E 00 00 00  │  PAYLOAD_LEN = 46 bytes, little-endian
7B 22 74 79 70 65 22 3A 22 48 45 4C 4C 4F 5F 41
43 4B 22 2C 22 70 72 6F 74 6F 63 6F 6C 22 3A 31
2C 22 61 63 63 65 70 74 65 64 22 3A 74 72 75 65
2C 22 72 65 6A 65 63 74 69 6F 6E 52 65 61 73 6F
6E 22 3A 6E 75 6C 6C 7D
```

UTF-8 payload decoded:
```json
{"type":"HELLO_ACK","protocol":1,"accepted":true,"rejectionReason":null}
```

---

## 3. Message Type IDs

| ID (hex) | ID (dec) | Name               | Direction      |
|----------|----------|--------------------|----------------|
| 0x0001   | 1        | HELLO              | Android→Windows |
| 0x0002   | 2        | HELLO_ACK          | Windows→Android |
| 0x0003   | 3        | CAPABILITIES       | Android→Windows |
| 0x0004   | 4        | CAPABILITIES_ACK   | Windows→Android |
| 0x0005   | 5        | DISPLAY_CONFIG     | Windows→Android |
| 0x0006   | 6        | DISPLAY_CONFIG_ACK | Android→Windows |
| 0x0007   | 7        | VIDEO_CONFIG       | Windows→Android |
| 0x0008   | 8        | VIDEO_CONFIG_ACK   | Android→Windows |
| 0x0009   | 9        | VIDEO_FRAME        | Windows→Android |
| 0x000A   | 10       | AUDIO_CONFIG       | Windows→Android |
| 0x000B   | 11       | AUDIO_FRAME        | Windows→Android |
| 0x000C   | 12       | INPUT_EVENT        | Android→Windows |
| 0x000D   | 13       | CLIPBOARD_EVENT    | Bidirectional  |
| 0x000E   | 14       | FILE_TRANSFER      | Bidirectional  |
| 0x000F   | 15       | PING               | Bidirectional  |
| 0x0010   | 16       | PONG               | Bidirectional  |
| 0x0011   | 17       | STREAM_RESET       | Windows→Android |
| 0x0012   | 18       | ERROR              | Bidirectional  |
| 0x0013   | 19       | DISCONNECT         | Bidirectional  |

---

## 4. Full Connection Handshake

```
Android                                  Windows
   │                                        │
   │───── TCP connection established ───────│
   │                                        │
   │──── HELLO ────────────────────────────►│
   │                                        │
   │◄─── HELLO_ACK ─────────────────────────│
   │        accepted: true                  │
   │                                        │
   │──── CAPABILITIES ─────────────────────►│
   │        display, video, audio, input    │
   │                                        │
   │◄─── CAPABILITIES_ACK ──────────────────│
   │                                        │
   │◄─── DISPLAY_CONFIG ────────────────────│
   │        width, height, fps, scaling     │
   │                                        │
   │──── DISPLAY_CONFIG_ACK ───────────────►│
   │        accepted: true                  │
   │                                        │
   │◄─── VIDEO_CONFIG ──────────────────────│
   │        codec, dims, SPS, PPS           │
   │                                        │
   │──── VIDEO_CONFIG_ACK ─────────────────►│
   │        accepted: true                  │
   │                                        │
   │◄═══ VIDEO_FRAME ════════════════════════│ (stream begins)
   │◄═══ VIDEO_FRAME ════════════════════════│
   │──── INPUT_EVENT ──────────────────────►│ (touch events)
   │◄─── PING ───────────────────────────────│ (every 5s)
   │──── PONG ─────────────────────────────►│
```

---

## 5. Message Payloads

All payloads are UTF-8 JSON unless noted as BINARY.

### 5.1 HELLO (Android → Windows)

```json
{
  "type": "HELLO",
  "protocol": 1,
  "platform": "android",
  "manufacturer": "Samsung",
  "model": "SM-T505",
  "androidVersion": "10",
  "sdk": 29,
  "deviceId": "a3f2b1c0"
}
```

- `protocol`: MUST be `1`. If the Windows agent requires a different version, reject in HELLO_ACK.
- `deviceId`: Stable opaque string. NOT a hardware serial number. Used for session continuity.

### 5.2 HELLO_ACK (Windows → Android)

Accept:
```json
{"type":"HELLO_ACK","protocol":1,"accepted":true,"rejectionReason":null}
```

Reject:
```json
{"type":"HELLO_ACK","protocol":1,"accepted":false,"rejectionReason":"Protocol version mismatch"}
```

If `accepted` is `false`, Android will disconnect. The Windows agent MUST include a human-readable `rejectionReason`.

### 5.3 CAPABILITIES (Android → Windows)

```json
{
  "type": "CAPABILITIES",
  "display": {
    "widthPx": 2000, "heightPx": 1200, "densityDpi": 240,
    "refreshRateHz": 60.0, "orientation": 0
  },
  "video": [
    {
      "codec": "H264", "supported": true, "hardwareAccelerated": true,
      "maxWidth": 3840, "maxHeight": 2160, "maxFrameRateHz": 120.0,
      "lowLatencySupported": true
    },
    {
      "codec": "HEVC", "supported": true, "hardwareAccelerated": true,
      "maxWidth": 3840, "maxHeight": 2160, "maxFrameRateHz": 60.0,
      "lowLatencySupported": false
    },
    {
      "codec": "AV1", "supported": false, "hardwareAccelerated": false,
      "maxWidth": 0, "maxHeight": 0, "maxFrameRateHz": 0.0,
      "lowLatencySupported": false
    }
  ],
  "audio": {
    "opusSupported": true, "aacSupported": true, "pcmSupported": true,
    "supportedSampleRates": [44100, 48000],
    "supportedChannelCounts": [1, 2],
    "lowLatencyOutput": false
  },
  "input": {
    "touchSupported": true, "maxTouchPoints": 10,
    "stylusSupported": false, "pressureSupported": true, "tiltSupported": false
  },
  "device": {
    "hasMicrophone": true, "hasCamera": true, "hasSpeaker": true,
    "batteryLevel": 85, "batteryCharging": false
  }
}
```

**Codec selection rule**: H.264 is mandatory — if `video[codec="H264"].supported` is `false`, the session MUST NOT proceed. HEVC/AV1 are optional and must only be selected if `supported` is `true`.

### 5.4 CAPABILITIES_ACK (Windows → Android)

```json
{"type":"CAPABILITIES_ACK","accepted":true}
```

### 5.5 DISPLAY_CONFIG (Windows → Android)

```json
{
  "type": "DISPLAY_CONFIG",
  "widthPx": 1920,
  "heightPx": 1080,
  "frameRateHz": 60.0,
  "orientation": 0,
  "pixelFormat": "RGBA_8888",
  "scaling": "FIT"
}
```

- `orientation`: 0=portrait, 1=landscape, 2=reverse-portrait, 3=reverse-landscape
- `scaling`: "FIT" (letterbox), "CROP" (fill+crop), "STRETCH" (ignore aspect ratio)
- Android will reject configs where `widthPx` > `CAPABILITIES.display.widthPx * 1.5` etc.

### 5.6 DISPLAY_CONFIG_ACK (Android → Windows)

Success:
```json
{"type":"DISPLAY_CONFIG_ACK","accepted":true,"errorCode":0,"errorMessage":null}
```

Failure:
```json
{"type":"DISPLAY_CONFIG_ACK","accepted":false,"errorCode":3,"errorMessage":"Resolution 4096x2160 exceeds device maximum 3840x2160"}
```

### 5.7 VIDEO_CONFIG (Windows → Android)

```json
{
  "type": "VIDEO_CONFIG",
  "codec": "H264",
  "widthPx": 1920,
  "heightPx": 1080,
  "frameRateHz": 60.0,
  "bitrateBps": 10000000,
  "keyframeIntervalS": 2.0,
  "lowLatencyMode": true,
  "csd0Base64": "Z0IAKeKQFAe2AAADAAIAAAMAfCA=",
  "csd1Base64": "aM48gA=="
}
```

- `csd0Base64`: Base64-encoded SPS NAL unit for H.264 (standard Base64, RFC 4648).
- `csd1Base64`: Base64-encoded PPS NAL unit for H.264.
- For HEVC: `csd0Base64` = VPS+SPS+PPS combined, `csd1Base64` = null.
- The first VIDEO_FRAME after VIDEO_CONFIG MUST be a keyframe (IDR).

### 5.8 VIDEO_FRAME (Windows → Android) — BINARY PAYLOAD

The VIDEO_FRAME payload is binary, not JSON.

```
Offset  Len  Endian  Field           Description
──────  ───  ──────  ──────          ───────────────────────────────────────────
  0      8   LE      TIMESTAMP_NS    int64. Stream-relative monotonic nanoseconds.
  8      4   LE      FLAGS           uint32. Bit 0 = 1 for keyframe, 0 for inter.
 12      N   n/a     NAL_DATA        Raw H.264/HEVC/AV1 NAL units (Annex B format).
```

TIMESTAMP_NS rules:
- Must start at 0 for the first frame and increment monotonically.
- Represents the frame's intended presentation time from the stream start.
- Android feeds this directly to `MediaCodec.queueInputBuffer(presentationTimeUs = TIMESTAMP_NS / 1000)`.
- Do NOT use wall-clock time (absolute epoch). Use encoder output timestamps or a frame counter multiplied by 1,000,000,000 / frameRateHz.

FLAGS:
- Bit 0 = 1: This frame is a keyframe (IDR for H.264). Android may use this to implement seek.
- Bits 1–31: Reserved. Set to 0.

Keyframe rules:
- The first frame after VIDEO_CONFIG_ACK MUST have bit 0 = 1.
- The first frame after STREAM_RESET + new VIDEO_CONFIG MUST have bit 0 = 1.
- If bit 0 = 0 is received before the first keyframe, Android will discard it.

Example VIDEO_FRAME binary construction (pseudo-code):
```
frame = bytearray()
frame += struct.pack('<q', timestamp_ns)     # 8 bytes LE int64
frame += struct.pack('<I', 1 if keyframe else 0)  # 4 bytes LE uint32 flags
frame += nal_units                           # raw compressed data
```

Total frame packet:
```
header (11 bytes) + binary_payload (12 + len(nal_units))
```

### 5.9 AUDIO_FRAME (Windows → Android) — BINARY PAYLOAD

```
Offset  Len  Endian  Field           Description
──────  ───  ──────  ──────          ───────────────────────────────────────────
  0      8   LE      TIMESTAMP_NS    int64. Presentation timestamp in nanoseconds.
  8      4   LE      SEQUENCE        uint32. Monotonically increasing sequence number.
 12      N   n/a     AUDIO_DATA      Encoded audio bytes (Opus / AAC / PCM).
```

### 5.10 INPUT_EVENT (Android → Windows) — JSON

Touch event:
```json
{
  "type": "INPUT_EVENT",
  "eventType": "TOUCH",
  "timestampNs": 1234567890123456789,
  "pointers": [
    {
      "id": 0,
      "action": "DOWN",
      "x": 0.523,
      "y": 0.341,
      "pressure": 0.75,
      "toolType": "FINGER"
    }
  ]
}
```

Stylus event:
```json
{
  "type": "INPUT_EVENT",
  "eventType": "STYLUS",
  "timestampNs": 1234567890123456789,
  "pointers": [
    {
      "id": 0,
      "action": "MOVE",
      "x": 0.4,
      "y": 0.6,
      "pressure": 0.9,
      "tiltX": 0.1,
      "tiltY": -0.05,
      "toolType": "STYLUS",
      "buttons": 0
    }
  ]
}
```

Coordinate rules:
- `x` and `y` are normalized: 0.0 = left/top edge, 1.0 = right/bottom edge of the display surface.
- Windows must scale: `absolute_x = x * virtual_display_width_px`
- `action` values: "DOWN", "MOVE", "UP", "CANCEL"
- `pressure`: 0.0 (none) to 1.0 (maximum). May be 0 on devices without pressure sensors.
- `timestampNs`: Android monotonic time from `MotionEvent.getEventTime()` converted to nanoseconds.

### 5.11 PING / PONG

PING (sender records send time as `timestampNs`):
```json
{"type":"PING","timestampNs":1000000000}
```

PONG (responder echoes `timestampNs`; adds its own time as `serverTimestampNs`):
```json
{"type":"PONG","timestampNs":1000000000,"serverTimestampNs":1001500000}
```

Round-trip latency = `now_ns - ping.timestampNs` at the time PONG is received.

### 5.12 STREAM_RESET (Windows → Android)

```json
{
  "type": "STREAM_RESET",
  "reason": "RESOLUTION_CHANGE",
  "newWidthPx": 1200,
  "newHeightPx": 2000
}
```

After sending STREAM_RESET, Windows MUST:
1. Wait for `STREAM_RESET` to be sent (no acknowledgement required).
2. Send a new `VIDEO_CONFIG`.
3. Ensure the next `VIDEO_FRAME` is a keyframe.

Android will:
1. Flush the MediaCodec decoder.
2. Clear the frame queue.
3. Wait for the new `VIDEO_CONFIG`.
4. Re-configure the decoder.

### 5.13 ERROR (Bidirectional)

```json
{"type":"ERROR","code":6,"message":"Invalid packet: magic bytes mismatch","fatal":false}
```

Non-fatal errors do not require disconnection. Fatal errors (`"fatal":true`) imply the sender will disconnect.

### 5.14 DISCONNECT (Bidirectional)

```json
{"type":"DISCONNECT","reason":"USER_REQUESTED"}
```

After sending DISCONNECT, the sender MUST close the TCP connection within 500ms.

---

## 6. Error Codes

| Code | Hex    | Name                        | Meaning                                    |
|------|--------|-----------------------------|--------------------------------------------|
| 0    | 0x0000 | ERR_NONE                    | No error                                   |
| 1    | 0x0001 | ERR_PROTOCOL_VERSION        | Incompatible protocol version              |
| 2    | 0x0002 | ERR_UNSUPPORTED_CODEC       | Requested codec not supported              |
| 3    | 0x0003 | ERR_UNSUPPORTED_RESOLUTION  | Requested resolution not supported         |
| 4    | 0x0004 | ERR_UNSUPPORTED_FRAMERATE   | Requested frame rate not supported         |
| 5    | 0x0005 | ERR_DECODER_FAILED          | MediaCodec decoder failure                 |
| 6    | 0x0006 | ERR_INVALID_PACKET          | Malformed or truncated packet              |
| 7    | 0x0007 | ERR_STREAM_RESET            | Stream reset requested                     |
| 8    | 0x0008 | ERR_AUTH_FAILED             | Reserved for future authentication         |
| 255  | 0x00FF | ERR_INTERNAL                | Unspecified internal Android error         |

---

## 7. Stream Reset Procedure

Use STREAM_RESET when:
- The virtual display resolution changes.
- The codec changes.
- The encoder resets internally.
- Bitrate changes significantly.

Sequence:
```
Windows                             Android
   │                                   │
   │──── STREAM_RESET ────────────────►│
   │       reason: "RESOLUTION_CHANGE" │  Android: flush decoder, clear queue
   │                                   │
   │──── VIDEO_CONFIG ────────────────►│  New width/height/codec
   │                                   │
   │◄─── VIDEO_CONFIG_ACK ─────────────│
   │                                   │
   │══── VIDEO_FRAME (keyframe) ══════►│  Bit 0 of FLAGS MUST be 1
   │══── VIDEO_FRAME ═════════════════►│
```

---

## 8. Reconnect Procedure

If the TCP connection drops:

```
Windows                                  Android
   │                                        │
   │  [connection lost]                     │  [transport failure detected]
   │                                        │  [decoder stops, queue cleared]
   │                                        │  [waits for reconnect]
   │                                        │
   │  adb forward tcp:7320 tcp:7320         │
   │  [reconnect TCP to 127.0.0.1:7320]     │
   │                                        │
   │  [repeat full handshake]               │
   │──── HELLO ────────────────────────────►│
   │◄─── HELLO_ACK ─────────────────────────│
   │  ...                                   │
```

Android implements automatic reconnect with exponential backoff (2s → 4s → 8s → … → 30s max, 5 attempts).
Windows should also retry TCP connections.

---

## 9. How to Send a Minimal Test H.264 Stream

To test the Android receiver without a real IDD driver, generate a synthetic H.264 stream using FFmpeg:

```bash
# Generate 10 seconds of test pattern at 1920x1080 60fps, H.264 baseline, ~8 Mbps
ffmpeg -f lavfi -i testsrc2=size=1920x1080:rate=60 \
       -c:v libx264 -preset ultrafast -profile:v baseline \
       -b:v 8M -keyint_min 120 -g 120 \
       -f h264 test_stream.h264
```

To send this over the protocol:
1. Parse NAL units from the Annex B stream (split on start codes `00 00 00 01`).
2. Extract SPS NAL → base64 encode → `csd0Base64` in VIDEO_CONFIG.
3. Extract PPS NAL → base64 encode → `csd1Base64` in VIDEO_CONFIG.
4. Send remaining NAL units as VIDEO_FRAME packets.
5. First frame must be an IDR (check NAL type == 5 for H.264).
6. Set TIMESTAMP_NS = frame_index * 1_000_000_000 / 60 (for 60 fps).

---

## 10. Expected Android Behavior Per Message

| Message received        | Android action                                                              |
|-------------------------|-----------------------------------------------------------------------------|
| TCP connection          | Accepts, sends HELLO immediately                                            |
| HELLO_ACK (accepted)    | Sends CAPABILITIES                                                          |
| HELLO_ACK (rejected)    | Logs reason, disconnects cleanly                                            |
| CAPABILITIES_ACK        | Waits for DISPLAY_CONFIG                                                    |
| DISPLAY_CONFIG          | Validates, applies, sends DISPLAY_CONFIG_ACK                                |
| VIDEO_CONFIG            | Creates/configures MediaCodec decoder, sends VIDEO_CONFIG_ACK               |
| VIDEO_FRAME             | Enqueues to VideoFrameQueue; decoder feeds to MediaCodec → Surface          |
| AUDIO_CONFIG            | Configures AudioTrack (Phase 2)                                             |
| AUDIO_FRAME             | Decodes and plays audio (Phase 2)                                           |
| PING                    | Immediately responds with PONG                                              |
| STREAM_RESET            | Flushes decoder, clears queue, waits for new VIDEO_CONFIG                   |
| ERROR (non-fatal)       | Logs warning, continues                                                     |
| ERROR (fatal)           | Logs error, stops session                                                   |
| DISCONNECT              | Sends nothing, closes connection, transitions to idle                       |
| Unknown MSG_TYPE        | Logs warning, discards packet, **does NOT disconnect**                      |

---

## 11. Test Vectors

Reference JSON payloads are in `protocol/test-vectors/`:

```
protocol/test-vectors/
├── hello.json               HELLO payload
├── hello_ack.json           HELLO_ACK (accepted)
├── hello_ack_rejected.json  HELLO_ACK (rejected)
├── capabilities.json        CAPABILITIES for a mid-range tablet
├── capabilities_ack.json    CAPABILITIES_ACK
├── video_config.json        VIDEO_CONFIG with H.264 CSD
├── display_config.json      DISPLAY_CONFIG
├── ping.json                PING
├── pong.json                PONG
├── stream_reset.json        STREAM_RESET
├── error.json               ERROR
├── disconnect.json          DISCONNECT
└── malformed/
    ├── bad_magic.txt         Invalid magic bytes — must be rejected
    ├── overflow_length.txt   PAYLOAD_LEN > 16MB — must be rejected
    └── unknown_type.json     Unknown MSG_TYPE — must be discarded, not disconnected
```

To construct a complete framed packet from a test vector JSON file for your unit tests:

```python
import struct, json

def make_frame(msg_type_id: int, payload: bytes) -> bytes:
    magic = b'ODSP'
    version = b'\x01'
    type_bytes = struct.pack('<H', msg_type_id)
    length_bytes = struct.pack('<I', len(payload))
    return magic + version + type_bytes + length_bytes + payload

hello_ack_json = json.dumps({
    "type": "HELLO_ACK",
    "protocol": 1,
    "accepted": True,
    "rejectionReason": None
}).encode('utf-8')

frame = make_frame(0x0002, hello_ack_json)
# Send frame over TCP socket
```

---

## 12. Forward Compatibility Rules

1. **Unknown message types**: Receivers MUST silently discard unknown MSG_TYPE values.
2. **Unknown JSON fields**: Android uses `ignoreUnknownKeys = true` — new fields from future
   Windows versions are safely ignored.
3. **Version negotiation**: If `HELLO_ACK.protocol != 1`, Android will disconnect.
   Future protocol versions will define their own negotiation mechanism.
4. **Capability evolution**: New capability fields added in future versions will be
   ignored by older Android clients (ignoreUnknownKeys). New required features
   must be gated on capability negotiation, not assumed.
