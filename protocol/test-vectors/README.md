# Protocol Test Vectors

This directory contains canonical JSON payloads and binary descriptions for every OpenDisplay Protocol message type.

These vectors are used by:
- Android unit tests (`core:protocol` module)
- Future Windows-side unit tests

## Files

| File | Direction | Description |
|---|---|---|
| `hello.json` | Android→Windows | Initial handshake |
| `hello_ack.json` | Windows→Android | Accepted |
| `hello_ack_rejected.json` | Windows→Android | Rejected (version mismatch) |
| `capabilities.json` | Android→Windows | Device capabilities |
| `capabilities_ack.json` | Windows→Android | Acknowledgement |
| `video_config.json` | Windows→Android | Video stream parameters |
| `display_config.json` | Windows→Android | Display configuration |
| `ping.json` | Either | Latency probe |
| `pong.json` | Either | Latency response |
| `stream_reset.json` | Windows→Android | Reset stream |
| `error.json` | Either | Error notification |
| `disconnect.json` | Either | Clean disconnect |
| `malformed/` | — | Invalid packets; must be rejected |

## Usage in Android Tests

Test vectors are loaded from `src/test/resources/test-vectors/` in the `core:protocol` module.
The Gradle build copies them from `protocol/test-vectors/` during the test resource phase.
