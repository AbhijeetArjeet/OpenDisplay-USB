# Malformed Test Vectors

This directory contains descriptions of invalid packets that the Android `PacketCodec` must reject gracefully.

Each `.txt` file describes the raw bytes and the expected error behaviour.
Since these vectors are binary (or describe binary), they are documented as hex dumps with explanations.

## Contract

- `bad_magic`: Magic bytes are not `ODSP`. Must return `Result.failure`.
- `overflow_length`: `PAYLOAD_LEN > 16_777_216`. Must return `Result.failure`.
- `unknown_type`: Unknown `MSG_TYPE`. Must NOT disconnect. Must log and discard.
