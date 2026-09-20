package com.opendisplay.usb.transport

object TransportFactory {
    fun createTcpServerTransport(port: Int = 7320): Transport {
        return TcpServerTransport(port = port)
    }

    fun createAoaTransport(fileDescriptor: android.os.ParcelFileDescriptor): Transport {
        return AoaTransport(fileDescriptor = fileDescriptor)
    }

    fun createFakeTransport(id: String = "fake-1", name: String = "Fake Transport"): Transport {
        return FakeTransport(
            TransportInfo(
                id = id,
                type = TransportType.FAKE,
                name = name
            )
        )
    }
}
