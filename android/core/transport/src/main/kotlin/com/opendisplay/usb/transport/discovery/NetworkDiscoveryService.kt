package com.opendisplay.usb.transport.discovery

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress

private const val TAG = "NetworkDiscovery"
private const val UDP_DISCOVERY_PORT = 7321
private const val DEFAULT_STREAM_PORT = 7320
private const val SERVICE_TYPE = "_opendisplay._tcp"

/**
 * Dual-stack network discovery service for OpenDisplay USB over Wi-Fi.
 *
 * 1. mDNS / DNS-SD via Android [NsdManager]: announces "_opendisplay._tcp" on port 7320.
 * 2. High-speed UDP broadcast responder on port 7321: replies immediately to Windows
 *    subnetwork probe queries with device metadata and model name.
 */
class NetworkDiscoveryService(private val context: Context) {

    private val scope = CoroutineScope(Dispatchers.IO + Job())
    private var udpJob: Job? = null
    private var udpSocket: DatagramSocket? = null

    private var nsdManager: NsdManager? = null
    private var registrationListener: NsdManager.RegistrationListener? = null
    private var isRegistered = false

    fun start(streamPort: Int = DEFAULT_STREAM_PORT) {
        startUdpResponder(streamPort)
        startNsdRegistration(streamPort)
    }

    fun stop() {
        stopUdpResponder()
        stopNsdRegistration()
    }

    private fun startUdpResponder(streamPort: Int) {
        if (udpJob?.isActive == true) return

        udpJob = scope.launch {
            try {
                val socket = DatagramSocket(null).apply {
                    reuseAddress = true
                    bind(InetSocketAddress(UDP_DISCOVERY_PORT))
                }
                udpSocket = socket
                val rxBuffer = ByteArray(1024)

                Log.i(TAG, "UDP discovery beacon listening on port $UDP_DISCOVERY_PORT...")

                while (isActive && !socket.isClosed) {
                    val rxPacket = DatagramPacket(rxBuffer, rxBuffer.size)
                    socket.receive(rxPacket)

                    val query = String(rxPacket.data, 0, rxPacket.length, Charsets.UTF_8).trim()
                    if (query.startsWith("OPENDISPLAY_DISCOVER")) {
                        Log.i(TAG, "Received discovery query from ${rxPacket.address.hostAddress}")

                        val responseJson = JSONObject().apply {
                            put("service", "opendisplay")
                            put("device", Build.MODEL)
                            put("manufacturer", Build.MANUFACTURER)
                            put("port", streamPort)
                            put("version", 1)
                        }

                        val txData = responseJson.toString().toByteArray(Charsets.UTF_8)
                        val txPacket = DatagramPacket(
                            txData,
                            txData.size,
                            rxPacket.address,
                            rxPacket.port
                        )
                        socket.send(txPacket)
                    }
                }
            } catch (e: Exception) {
                if (isActive) {
                    Log.w(TAG, "UDP discovery responder exception: ${e.message}")
                }
            } finally {
                udpSocket?.close()
                udpSocket = null
            }
        }
    }

    private fun stopUdpResponder() {
        udpJob?.cancel()
        udpJob = null
        try {
            udpSocket?.close()
        } catch (_: Exception) {}
        udpSocket = null
    }

    private fun startNsdRegistration(streamPort: Int) {
        try {
            nsdManager = context.getSystemService(Context.NSD_SERVICE) as? NsdManager ?: return

            val serviceInfo = NsdServiceInfo().apply {
                serviceName = "OpenDisplay-${Build.MODEL.replace(" ", "_")}"
                serviceType = SERVICE_TYPE
                port = streamPort
            }

            registrationListener = object : NsdManager.RegistrationListener {
                override fun onServiceRegistered(info: NsdServiceInfo) {
                    isRegistered = true
                    Log.i(TAG, "mDNS NSD Service registered: ${info.serviceName}")
                }

                override fun onRegistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                    Log.w(TAG, "mDNS NSD Service registration failed: error code $errorCode")
                    isRegistered = false
                }

                override fun onServiceUnregistered(info: NsdServiceInfo) {
                    isRegistered = false
                    Log.i(TAG, "mDNS NSD Service unregistered")
                }

                override fun onUnregistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                    Log.w(TAG, "mDNS NSD Service unregistration failed: error code $errorCode")
                }
            }

            nsdManager?.registerService(serviceInfo, NsdManager.PROTOCOL_DNS_SD, registrationListener)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to start NSD registration: ${e.message}")
        }
    }

    private fun stopNsdRegistration() {
        if (isRegistered && registrationListener != null) {
            try {
                nsdManager?.unregisterService(registrationListener)
            } catch (e: Exception) {
                Log.w(TAG, "Error unregistering NSD service: ${e.message}")
            }
        }
        isRegistered = false
        registrationListener = null
    }
}
