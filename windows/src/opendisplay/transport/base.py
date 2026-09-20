"""Transport abstraction interface for OpenDisplay USB."""

import abc
from enum import Enum
from typing import AsyncIterator, Optional, Callable, List


class ConnectionState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class ITransport(abc.ABC):
    """Abstract interface for all OpenDisplay USB transport implementations.
    
    The video decoder, audio system, and protocol state machine are completely
    transport-independent and interact solely through this interface.
    """

    def __init__(self):
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._state_callbacks: List[Callable[[ConnectionState], None]] = []

    @property
    def state(self) -> ConnectionState:
        return self._state

    def set_state(self, new_state: ConnectionState) -> None:
        if self._state != new_state:
            self._state = new_state
            for cb in self._state_callbacks:
                try:
                    cb(new_state)
                except Exception:
                    pass

    def add_state_listener(self, callback: Callable[[ConnectionState], None]) -> None:
        self._state_callbacks.append(callback)

    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    @abc.abstractmethod
    async def connect(self) -> bool:
        """Establishes connection to the Android receiver."""
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Closes the connection cleanly."""
        pass

    @abc.abstractmethod
    async def send(self, packet: bytes) -> bool:
        """Sends a complete framed packet."""
        pass

    @abc.abstractmethod
    async def receive_flow(self) -> AsyncIterator[bytes]:
        """Yields complete framed packets as they arrive."""
        pass
