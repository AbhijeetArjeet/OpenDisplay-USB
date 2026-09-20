"""Session Manager orchestrating transport, protocol controller, and auto-reconnection."""

import asyncio
import logging
from typing import Optional, Callable
from ..transport.base import ITransport, ConnectionState
from ..diagnostics.collector import DiagnosticsCollector, DiagnosticsSnapshot
from ..input.injector import InputInjector
from .controller import ProtocolController, SessionState
from .adaptive import PerformanceProfile
from ..protocol import PacketCodec, MessageType, DisconnectMessage, JsonCodec

logger = logging.getLogger(__name__)

RECONNECT_DELAYS = [2.0, 4.0, 8.0, 16.0, 30.0]
MAX_RECONNECT_ATTEMPTS = 5


class SessionManager:
    """Manages an OpenDisplay USB session with automatic reconnection."""

    def __init__(
        self,
        transport: ITransport,
        diagnostics: Optional[DiagnosticsCollector] = None,
        input_injector: Optional[InputInjector] = None,
        on_state_change: Optional[Callable[[SessionState], None]] = None,
        use_synthetic_video: bool = True,
        enable_audio: bool = True,
        enable_clipboard: bool = True,
        performance_profile: PerformanceProfile = PerformanceProfile.BALANCED,
        preferred_codec: str = "H264",
        monitor_index: int = 0,
        capture_backend: str = "dxgi",
        auto_extend: bool = False,
        enable_wifi_failover: bool = True
    ):
        self.transport = transport
        self.diagnostics = diagnostics or DiagnosticsCollector()
        self.input_injector = input_injector or InputInjector()
        self.on_state_change = on_state_change
        self.use_synthetic_video = use_synthetic_video
        self.enable_audio = enable_audio
        self.enable_clipboard = enable_clipboard
        self.performance_profile = performance_profile
        self.preferred_codec = preferred_codec
        self.monitor_index = monitor_index
        self.capture_backend = capture_backend
        self.auto_extend = auto_extend or (monitor_index > 0)
        self.enable_wifi_failover = enable_wifi_failover

        from ..display.virtual_display import VirtualDisplayManager
        self.virtual_display_manager: Optional[VirtualDisplayManager] = VirtualDisplayManager() if self.auto_extend else None

        from ..transport.discovery import NetworkDiscoveryManager
        self.discovery_manager = NetworkDiscoveryManager() if self.enable_wifi_failover else None

        self.controller: Optional[ProtocolController] = None
        self._main_task: Optional[asyncio.Task] = None
        self._stopped = False

    async def start(self) -> None:
        """Starts the session manager loop."""
        self._stopped = False
        if self.virtual_display_manager and self.auto_extend:
            self.virtual_display_manager.enable_extend_mode()
        self._main_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stops the session and disconnects cleanly."""
        self._stopped = True
        if self.virtual_display_manager:
            self.virtual_display_manager.teardown()
        if self.controller:
            try:
                # Send clean DISCONNECT to Android receiver
                disc = DisconnectMessage(reason="USER_REQUESTED")
                packet = PacketCodec.encode(MessageType.DISCONNECT, JsonCodec.encode(disc))
                await self.transport.send(packet)
            except Exception:
                pass
            await self.controller.stop()

        await self.transport.disconnect()
        if self._main_task:
            self._main_task.cancel()

    async def _run_loop(self) -> None:
        reconnect_idx = 0

        while not self._stopped:
            connected = await self.transport.connect()
            if not connected:
                if reconnect_idx >= MAX_RECONNECT_ATTEMPTS:
                    logger.error("Exceeded maximum reconnect attempts (%d)", MAX_RECONNECT_ATTEMPTS)
                    break

                delay = RECONNECT_DELAYS[min(reconnect_idx, len(RECONNECT_DELAYS) - 1)]
                logger.info("Reconnect failed. Retrying in %.1f seconds...", delay)
                self.diagnostics.record_reconnect()
                reconnect_idx += 1
                await asyncio.sleep(delay)
                continue

            # Connected successfully, reset reconnect backoff
            reconnect_idx = 0
            self.controller = ProtocolController(
                send_packet_func=self.transport.send,
                diagnostics=self.diagnostics,
                input_injector=self.input_injector,
                use_synthetic_video=self.use_synthetic_video,
                enable_audio=self.enable_audio,
                enable_clipboard=self.enable_clipboard,
                performance_profile=self.performance_profile,
                preferred_codec=self.preferred_codec,
                monitor_index=self.monitor_index,
                capture_backend=self.capture_backend
            )
            await self.controller.start_handshake()

            try:
                async for packet_bytes in self.transport.receive_flow():
                    if self._stopped:
                        break
                    await self.controller.handle_packet(packet_bytes)

                    if self.on_state_change:
                        self.on_state_change(self.controller.state)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Session stream loop error: %s", e)
            finally:
                if self.controller:
                    await self.controller.stop()

            if not self._stopped:
                logger.warning("Transport connection lost. Checking for Wi-Fi failover...")
                if self.enable_wifi_failover and self.discovery_manager:
                    try:
                        devices = await self.discovery_manager.discover_devices(timeout=0.6)
                        if devices:
                            best_dev = devices[0]
                            logger.info("Auto-migrating session to discovered wireless device: %s (%s)", best_dev.name, best_dev.endpoint)
                            from ..transport.wifi_transport import WifiTransport
                            self.transport = WifiTransport(host=best_dev.ip, port=best_dev.port)
                            continue
                    except Exception as e:
                        logger.debug("Wi-Fi failover discovery exception: %s", e)

                self.transport.set_state(ConnectionState.RECONNECTING)
                self.diagnostics.record_reconnect()
                await asyncio.sleep(2.0)
