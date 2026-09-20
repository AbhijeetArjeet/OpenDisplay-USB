package com.opendisplay.usb.transport

/**
 * Metadata describing a transport link.
 */
data class TransportInfo(
    val type: TransportType,
    val bandwidthBps: Long = 480_000_000L,
    val latencyMs: Long = 0L,
    val description: String = "Transport",
    val id: String = type.name.lowercase(),
    val name: String = type.name
)
