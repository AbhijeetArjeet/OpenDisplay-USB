# OpenDisplay Protocol Specification

## Version and Compatibility
Protocol Version: **1**
Changes to the major version indicate breaking changes. Client and server MUST negotiate matching major versions during the HELLO handshake.

## Binary Frame Format
All messages share a common 11-byte header:
```
[MAGIC: 4 bytes  "ODSP" 0x4F445350]
[VERSION: 1 byte  currently 0x01]
[MSG_TYPE: 2 bytes little-endian]
[PAYLOAD_LEN: 4 bytes little-endian]
[PAYLOAD: PAYLOAD_LEN bytes of UTF-8 JSON or binary]
```
- Max payload size is 16 MB (`0x01000000`).
- JSON payloads are UTF-8 without BOM.

## Connection Handshake Sequence
```text
Windows (Client)                        Android (Server)
      |                                       |
      | ------------- TCP Connect ----------> |
      |                                       |
      | <------------ HELLO ----------------- |
      |                                       |
      | ------------- HELLO_ACK ------------> |
      |                                       |
      | <------------ CAPABILITIES ---------- |
      |                                       |
      | ------------- CAPABILITIES_ACK -----> |
      |                                       |
      | ------------- DISPLAY_CONFIG -------> |
      | <------------ DISPLAY_CONFIG_ACK ---- |
      |                                       |
      | ------------- VIDEO_CONFIG ---------> |
      | <------------ VIDEO_CONFIG_ACK ------ |
      |                                       |
      | ============= VIDEO_FRAME ==========> |
```

## Message Types

### HELLO (0x0001)
- **Direction:** Android -> Windows
- **Format:** JSON
- **Fields:**
  - `type` (string): "HELLO"
  - `protocol` (int): 1
  - `platform` (string): "android"
  - `manufacturer` (string)
  - `model` (string)
  - `androidVersion` (string)
  - `sdk` (int)
  - `deviceId` (string)
- **Example:**
```json
{
  "type": "HELLO",
  "protocol": 1,
  "platform": "android",
  "manufacturer": "<from Build.MANUFACTURER>",
  "model": "<from Build.MODEL>",
  "androidVersion": "<from Build.VERSION.RELEASE>",
  "sdk": 35,
  "deviceId": "<stable opaque ID, NOT the Android device ID>"
}
```

### HELLO_ACK (0x0002)
- **Direction:** Windows -> Android
- **Format:** JSON
- **Fields:**
  - `type` (string): "HELLO_ACK"
  - `protocol` (int): 1
  - `accepted` (bool)
  - `rejectionReason` (string|null)
- **Example:**
```json
{
  "type": "HELLO_ACK",
  "protocol": 1,
  "accepted": true,
  "rejectionReason": null
}
```

### CAPABILITIES (0x0003)
- **Direction:** Android -> Windows
- **Format:** JSON
- **Example:**
```json
{
  "type": "CAPABILITIES",
  "display": {
    "widthPx": 2000,
    "heightPx": 1200,
    "densityDpi": 240,
    "refreshRateHz": 60.0,
    "orientation": 0
  },
  "video": [
    {
      "codec": "H264",
      "supported": true,
      "hardwareAccelerated": true,
      "maxWidth": 3840,
      "maxHeight": 2160,
      "maxFrameRateHz": 120.0,
      "lowLatencySupported": true
    },
    {
      "codec": "HEVC",
      "supported": true,
      "hardwareAccelerated": true,
      "maxWidth": 3840,
      "maxHeight": 2160,
      "maxFrameRateHz": 60.0,
      "lowLatencySupported": false
    },
    {
      "codec": "AV1",
      "supported": false,
      "hardwareAccelerated": false,
      "maxWidth": 0,
      "maxHeight": 0,
      "maxFrameRateHz": 0.0,
      "lowLatencySupported": false
    }
  ],
  "audio": {
    "opusSupported": true,
    "aacSupported": true,
    "pcmSupported": true,
    "supportedSampleRates": [44100, 48000],
    "supportedChannelCounts": [1, 2],
    "lowLatencyOutput": true
  },
  "input": {
    "touchSupported": true,
    "maxTouchPoints": 10,
    "stylusSupported": true,
    "pressureSupported": true,
    "tiltSupported": true
  },
  "device": {
    "hasMicrophone": true,
    "hasCamera": true,
    "hasSpeaker": true,
    "batteryLevel": 85,
    "batteryCharging": false
  }
}
```

### CAPABILITIES_ACK (0x0004)
- **Direction:** Windows -> Android
- **Format:** JSON
- **Example:**
```json
{
  "type": "CAPABILITIES_ACK",
  "accepted": true
}
```

### DISPLAY_CONFIG (0x0005)
- **Direction:** Windows -> Android
- **Format:** JSON
- **Example:**
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

### VIDEO_CONFIG (0x0007)
- **Direction:** Windows -> Android
- **Format:** JSON
- **Example:**
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
  "csd0Base64": "<base64-encoded SPS NAL>",
  "csd1Base64": "<base64-encoded PPS NAL>"
}
```

### VIDEO_FRAME (0x0009)
- **Direction:** Windows -> Android
- **Format:** BINARY
- **Payload:**
  ```
  [TIMESTAMP_NS: 8 bytes little-endian int64]  — monotonic nanoseconds
  [FLAGS: 4 bytes little-endian uint32]         — bit 0 = keyframe, bits 1-31 reserved
  [DATA: remaining bytes]                       — raw H.264/HEVC/AV1 NAL units
  ```

### AUDIO_FRAME (0x000B)
- **Direction:** Windows -> Android
- **Format:** BINARY
- **Payload:**
  ```
  [TIMESTAMP_NS: 8 bytes little-endian int64]  — presentation timestamp
  [SEQUENCE: 4 bytes little-endian uint32]     — packet sequence number
  [DATA: remaining bytes]                      — encoded audio (Opus/AAC/PCM)
  ```

### INPUT_EVENT (0x000C)
- **Direction:** Android -> Windows
- **Format:** JSON
- **Examples:**
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

### PING (0x000F) / PONG (0x0010)
- **Direction:** Bidirectional
- **Format:** JSON

### STREAM_RESET (0x0011)
- **Direction:** Windows -> Android
- **Format:** JSON

### ERROR (0x0012)
- **Direction:** Bidirectional
- **Format:** JSON

### DISCONNECT (0x0013)
- **Direction:** Bidirectional
- **Format:** JSON

## Unknown Message Types
If a peer receives a `MSG_TYPE` it does not recognize, it MUST discard the payload up to `PAYLOAD_LEN` and continue processing. It MUST NOT disconnect.

## Stream Reset Procedure
A `STREAM_RESET` message implies that the stream context (like decoder state) needs to be completely reinitialized. Following this, the next `VIDEO_FRAME` MUST be a keyframe.

## Reconnect Procedure
If a socket disconnection occurs, the Android side returns to the LISTENING state and awaits a new TCP connection, restarting the handshake from HELLO.
