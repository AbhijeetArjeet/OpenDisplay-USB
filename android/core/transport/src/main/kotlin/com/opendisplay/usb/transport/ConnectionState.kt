package com.opendisplay.usb.transport

/**
 * Transport connection lifecycle states.
 */
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    ERROR
}
