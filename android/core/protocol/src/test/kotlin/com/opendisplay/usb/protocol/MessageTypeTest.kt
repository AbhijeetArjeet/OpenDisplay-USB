package com.opendisplay.usb.protocol

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class MessageTypeTest {

    @Test
    fun testAllMessageTypesHaveUniqueIds() {
        val ids = MessageType.entries.map { it.id }
        assertEquals("All message type IDs must be unique", ids.size, ids.toSet().size)
    }

    @Test
    fun testFromIdValid() {
        assertEquals(MessageType.HELLO, MessageType.fromId(0x0001u))
        assertEquals(MessageType.HELLO_ACK, MessageType.fromId(0x0002u))
        assertEquals(MessageType.VIDEO_FRAME, MessageType.fromId(0x0009u))
        assertEquals(MessageType.DISCONNECT, MessageType.fromId(0x0013u))
    }

    @Test
    fun testFromIdUnknownReturnsNull() {
        assertNull(MessageType.fromId(0x0000u))
        assertNull(MessageType.fromId(0x0099u))
        assertNull(MessageType.fromId(0xFFFFu))
    }

    @Test
    fun testEveryEntryResolvesViaFromId() {
        for (entry in MessageType.entries) {
            val resolved = MessageType.fromId(entry.id)
            assertNotNull("MessageType.fromId failed for ${entry.name}", resolved)
            assertEquals(entry, resolved)
        }
    }
}
