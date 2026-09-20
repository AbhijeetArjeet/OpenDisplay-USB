# OpenDisplay USB Architecture

## Project Vision and Goals
OpenDisplay USB aims to turn Android phones and tablets into genuine, high-performance secondary displays for Windows PCs over USB. The goal is to provide a seamless, low-latency, and cross-platform compatible experience without relying on proprietary network protocols.

## System Overview Diagram
```text
+---------------------+                            +-------------------------+
|     Windows PC      |                            |     Android Device      |
|                     |                            |                         |
| +-----------------+ |                            | +---------------------+ |
| | Virtual Display | |    +------------------+    | | OpenDisplay USB App | |
| | Driver          | |    |                  |    | |                     | |
| +-------+---------+ |    |   ADB Forward    |    | | +-----------------+ | |
|         |           |    |   Port 7320      |    | | |   Protocol      | | |
| +-------v---------+ |    |                  |    | | |   Handler       | | |
| |  H.264 Encoder  | |    |                  |    | | +-------+---------+ | |
| +-------+---------+ |    |                  |    | |         |           | |
|         |           |    |                  |    | | +-------v---------+ | |
| +-------v---------+ |======> USB Cable ========> | | |   MediaCodec    | | |
| |   Transport     | |    |                  |    | | |   Decoder       | | |
| |   Manager       | |    |                  |    | | +-------+---------+ | |
| +-----------------+ |    +------------------+    | |         |           | |
|                     |                            | | +-------v---------+ | |
|                     |                            | | |    Surface      | | |
|                     |                            | | +-----------------+ | |
+---------------------+                            +-------------------------+
```

## Module Dependency Graph
```text
          +---------------+
          |     app       |
          +-------+-------+
                  |
    +-------------+-------------+
    |             |             |
+---v---+     +---v---+     +---v---+
|  ui   |     | video |     | audio |
+---+---+     +---+---+     +---+---+
    |             |             |
    +-------------+-------------+
                  |
            +-----v-----+
            |   core    |
            | (protocol,|
            | transport,|
            | timing,   |
            | caps)     |
            +-----------+
```

## Data Flow: Video Pipeline
PC Virtual Display -> H.264 Encoder -> USB Transport -> Android Protocol Handler -> MediaCodec -> Surface

## Data Flow: Audio Pipeline
PC Audio Capture -> Opus Encoder -> USB Transport -> Android Protocol Handler -> AudioTrack

## Data Flow: Input
Android Touch/Stylus Event -> Input Protocol Handler -> USB Transport -> PC Virtual Input Device

## Transport Independence Diagram
```text
+-----------------------+
|   Protocol Layer      |
+---+-------+-------+---+
    |       |       |
+---v---+ +-v-----+ +v------+
|  ADB  | | Native| | Wi-Fi |
|       | |  USB  | |       |
+-------+ +-------+ +-------+
```

## Capability Negotiation Philosophy
The protocol employs graceful degradation. The Android device sends a `CAPABILITIES` message detailing its max supported codecs, resolutions, audio features, and input mechanisms. The Windows host responds with a `VIDEO_CONFIG` and `DISPLAY_CONFIG` that fit within those limits. If unsupported settings are requested, the Android device responds with an explicit error code and cleanly disconnects or waits for a new configuration.

## Android Version Compatibility Table
| API Level | Features Available |
|-----------|--------------------|
| 26+       | Base display, touch, H.264 decode |
| 28+       | HEVC low-latency hints |
| 29+       | MediaCodec low-latency mode flag |
| 31+       | AudioTrack improved timestamp accuracy |
| 34+       | AV1 hardware decode more common |

## Module Descriptions
- **app**: The main application entry point, dependency injection setup, and lifecycle management.
- **core/protocol**: Implements the OpenDisplay Protocol (parsing, serializing, state machine).
- **core/transport**: Abstract transport layer and concrete implementations (currently ADB forward mock).
- **core/capabilities**: Discovers and reports device hardware capabilities (codecs, resolutions).
- **core/timing**: Manages clock synchronization and latency calculations.
- **video**: Handles H.264/HEVC decoding via MediaCodec and rendering to Surface.
- **audio**: Handles audio decoding and playback via AudioTrack.
- **input**: Captures touch, stylus, and keyboard events and translates them to protocol messages.
- **display**: Manages window parameters, wakelocks, and screen rotation.
- **diagnostics**: Collects performance metrics, dropped frames, and latency stats.
- **ui**: Compose-based user interface for settings, status, and instructions.

## Thread Model
- **UI Thread**: Minimal workload, Compose UI updates.
- **Transport Rx Thread**: Dedicated thread reading from the socket and parsing protocol headers.
- **Transport Tx Thread**: Dedicated thread serializing and writing messages to the socket.
- **Video Decode Thread**: Managed by MediaCodec async callbacks.
- **Audio Playback Thread**: Thread continuously feeding AudioTrack.
- **Protocol State Machine**: Synchronized or single-threaded coroutine context.

## Security Boundaries
- Only listens on localhost (127.0.0.1) when using ADB forward.
- Malformed packets are discarded; buffer limits enforced to prevent OOM.

## Reconnect State Machine
```text
[DISCONNECTED] <---+
      |            | (Error/Timeout)
      v            |
 [LISTENING]       |
      |            |
      v            |
[HANDSHAKING] -----+
      |
      v
 [CONNECTED]
```
