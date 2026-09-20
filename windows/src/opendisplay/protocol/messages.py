"""Typed data classes and JSON codec for OpenDisplay Protocol v1 messages."""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict


@dataclass
class HelloMessage:
    type: str = "HELLO"
    protocol: int = 1
    platform: str = "android"
    manufacturer: str = ""
    model: str = ""
    androidVersion: str = ""
    sdk: int = 0
    deviceId: str = ""


@dataclass
class HelloAckMessage:
    type: str = "HELLO_ACK"
    protocol: int = 1
    accepted: bool = True
    rejectionReason: Optional[str] = None


@dataclass
class DisplayCapabilityInfo:
    widthPx: int = 1920
    heightPx: int = 1080
    densityDpi: int = 240
    refreshRateHz: float = 60.0
    orientation: int = 0


@dataclass
class VideoCapabilityInfo:
    codec: str = "H264"
    supported: bool = True
    hardwareAccelerated: bool = True
    maxWidth: int = 3840
    maxHeight: int = 2160
    maxFrameRateHz: float = 60.0
    lowLatencySupported: bool = True


@dataclass
class AudioCapabilityInfo:
    opusSupported: bool = True
    aacSupported: bool = True
    pcmSupported: bool = True
    supportedSampleRates: List[int] = field(default_factory=lambda: [44100, 48000])
    supportedChannelCounts: List[int] = field(default_factory=lambda: [1, 2])
    lowLatencyOutput: bool = False


@dataclass
class InputCapabilityInfo:
    touchSupported: bool = True
    maxTouchPoints: int = 10
    stylusSupported: bool = False
    pressureSupported: bool = True
    tiltSupported: bool = False


@dataclass
class DeviceCapabilityInfo:
    hasMicrophone: bool = True
    hasCamera: bool = True
    hasSpeaker: bool = True
    batteryLevel: Optional[int] = None
    batteryCharging: Optional[bool] = None


@dataclass
class CapabilitiesMessage:
    type: str = "CAPABILITIES"
    display: DisplayCapabilityInfo = field(default_factory=DisplayCapabilityInfo)
    video: List[VideoCapabilityInfo] = field(default_factory=list)
    audio: AudioCapabilityInfo = field(default_factory=AudioCapabilityInfo)
    input: InputCapabilityInfo = field(default_factory=InputCapabilityInfo)
    device: DeviceCapabilityInfo = field(default_factory=DeviceCapabilityInfo)


@dataclass
class CapabilitiesAckMessage:
    type: str = "CAPABILITIES_ACK"
    accepted: bool = True


@dataclass
class DisplayConfigMessage:
    type: str = "DISPLAY_CONFIG"
    widthPx: int = 1920
    heightPx: int = 1080
    frameRateHz: float = 60.0
    orientation: int = 0
    pixelFormat: str = "RGBA_8888"
    scaling: str = "FIT"


@dataclass
class DisplayConfigAckMessage:
    type: str = "DISPLAY_CONFIG_ACK"
    accepted: bool = True
    errorCode: int = 0
    errorMessage: Optional[str] = None


@dataclass
class VideoConfigMessage:
    type: str = "VIDEO_CONFIG"
    codec: str = "H264"
    widthPx: int = 1920
    heightPx: int = 1080
    frameRateHz: float = 60.0
    bitrateBps: int = 10000000
    keyframeIntervalS: float = 2.0
    lowLatencyMode: bool = True
    csd0Base64: Optional[str] = None
    csd1Base64: Optional[str] = None


@dataclass
class VideoConfigAckMessage:
    type: str = "VIDEO_CONFIG_ACK"
    accepted: bool = True
    errorCode: int = 0
    errorMessage: Optional[str] = None


@dataclass
class AudioConfigMessage:
    type: str = "AUDIO_CONFIG"
    codec: str = "OPUS"
    sampleRate: int = 48000
    channelCount: int = 2
    bitrateBps: int = 128000


@dataclass
class PointerInfo:
    id: int
    action: str
    x: float
    y: float
    pressure: float = 1.0
    toolType: str = "FINGER"
    tiltX: float = 0.0
    tiltY: float = 0.0
    buttons: int = 0


@dataclass
class InputEventMessage:
    type: str = "INPUT_EVENT"
    eventType: str = "TOUCH"
    timestampNs: int = 0
    pointers: List[PointerInfo] = field(default_factory=list)


@dataclass
class ClipboardEventMessage:
    type: str = "CLIPBOARD_EVENT"
    content: str = ""
    mimeType: str = "text/plain"


@dataclass
class PingMessage:
    type: str = "PING"
    timestampNs: int = 0


@dataclass
class PongMessage:
    type: str = "PONG"
    timestampNs: int = 0
    serverTimestampNs: int = 0


@dataclass
class StreamResetMessage:
    type: str = "STREAM_RESET"
    reason: str = "RESOLUTION_CHANGE"
    newWidthPx: Optional[int] = None
    newHeightPx: Optional[int] = None


@dataclass
class ErrorMessage:
    type: str = "ERROR"
    code: int = 0
    message: str = ""
    fatal: bool = False


@dataclass
class DisconnectMessage:
    type: str = "DISCONNECT"
    reason: str = "USER_REQUESTED"


class JsonCodec:
    """Helper for encoding and decoding protocol JSON messages."""

    @staticmethod
    def encode(obj: Any) -> bytes:
        """Serializes a dataclass or dictionary to UTF-8 encoded JSON bytes without BOM."""
        if hasattr(obj, "__dataclass_fields__"):
            data = asdict(obj)
        elif isinstance(obj, dict):
            data = obj
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @staticmethod
    def decode(payload: bytes) -> Dict[str, Any]:
        """Decodes UTF-8 JSON bytes to a Python dictionary."""
        return json.loads(payload.decode("utf-8"))

    @classmethod
    def decode_hello(cls, payload: bytes) -> HelloMessage:
        d = cls.decode(payload)
        return HelloMessage(
            type=d.get("type", "HELLO"),
            protocol=d.get("protocol", 1),
            platform=d.get("platform", "android"),
            manufacturer=d.get("manufacturer", ""),
            model=d.get("model", ""),
            androidVersion=d.get("androidVersion", ""),
            sdk=d.get("sdk", 0),
            deviceId=d.get("deviceId", ""),
        )

    @classmethod
    def decode_capabilities(cls, payload: bytes) -> CapabilitiesMessage:
        d = cls.decode(payload)
        disp = d.get("display", {})
        display_cap = DisplayCapabilityInfo(
            widthPx=disp.get("widthPx", 1920),
            heightPx=disp.get("heightPx", 1080),
            densityDpi=disp.get("densityDpi", 240),
            refreshRateHz=float(disp.get("refreshRateHz", 60.0)),
            orientation=disp.get("orientation", 0),
        )

        videos: List[VideoCapabilityInfo] = []
        for v in d.get("video", []):
            videos.append(
                VideoCapabilityInfo(
                    codec=v.get("codec", "H264"),
                    supported=v.get("supported", True),
                    hardwareAccelerated=v.get("hardwareAccelerated", True),
                    maxWidth=v.get("maxWidth", 3840),
                    maxHeight=v.get("maxHeight", 2160),
                    maxFrameRateHz=float(v.get("maxFrameRateHz", 60.0)),
                    lowLatencySupported=v.get("lowLatencySupported", True),
                )
            )

        aud = d.get("audio", {})
        audio_cap = AudioCapabilityInfo(
            opusSupported=aud.get("opusSupported", True),
            aacSupported=aud.get("aacSupported", True),
            pcmSupported=aud.get("pcmSupported", True),
            supportedSampleRates=aud.get("supportedSampleRates", [44100, 48000]),
            supportedChannelCounts=aud.get("supportedChannelCounts", [1, 2]),
            lowLatencyOutput=aud.get("lowLatencyOutput", False),
        )

        inp = d.get("input", {})
        input_cap = InputCapabilityInfo(
            touchSupported=inp.get("touchSupported", True),
            maxTouchPoints=inp.get("maxTouchPoints", 10),
            stylusSupported=inp.get("stylusSupported", False),
            pressureSupported=inp.get("pressureSupported", True),
            tiltSupported=inp.get("tiltSupported", False),
        )

        dev = d.get("device", {})
        device_cap = DeviceCapabilityInfo(
            hasMicrophone=dev.get("hasMicrophone", True),
            hasCamera=dev.get("hasCamera", True),
            hasSpeaker=dev.get("hasSpeaker", True),
            batteryLevel=dev.get("batteryLevel"),
            batteryCharging=dev.get("batteryCharging"),
        )

        return CapabilitiesMessage(
            type=d.get("type", "CAPABILITIES"),
            display=display_cap,
            video=videos,
            audio=audio_cap,
            input=input_cap,
            device=device_cap,
        )

    @classmethod
    def decode_display_config_ack(cls, payload: bytes) -> DisplayConfigAckMessage:
        d = cls.decode(payload)
        return DisplayConfigAckMessage(
            type=d.get("type", "DISPLAY_CONFIG_ACK"),
            accepted=d.get("accepted", True),
            errorCode=d.get("errorCode", 0),
            errorMessage=d.get("errorMessage"),
        )

    @classmethod
    def decode_video_config_ack(cls, payload: bytes) -> VideoConfigAckMessage:
        d = cls.decode(payload)
        return VideoConfigAckMessage(
            type=d.get("type", "VIDEO_CONFIG_ACK"),
            accepted=d.get("accepted", True),
            errorCode=d.get("errorCode", 0),
            errorMessage=d.get("errorMessage"),
        )

    @classmethod
    def decode_input_event(cls, payload: bytes) -> InputEventMessage:
        d = cls.decode(payload)
        pointers = [
            PointerInfo(
                id=p.get("id", 0),
                action=p.get("action", "MOVE"),
                x=float(p.get("x", 0.0)),
                y=float(p.get("y", 0.0)),
                pressure=float(p["pressure"]) if p.get("pressure") is not None else 1.0,
                toolType=p.get("toolType", "FINGER"),
                tiltX=float(p["tiltX"]) if p.get("tiltX") is not None else 0.0,
                tiltY=float(p["tiltY"]) if p.get("tiltY") is not None else 0.0,
                buttons=p.get("buttons", 0),
            )
            for p in d.get("pointers", [])
        ]
        return InputEventMessage(
            type=d.get("type", "INPUT_EVENT"),
            eventType=d.get("eventType", "TOUCH"),
            timestampNs=d.get("timestampNs", 0),
            pointers=pointers,
        )

    @classmethod
    def decode_pong(cls, payload: bytes) -> PongMessage:
        d = cls.decode(payload)
        return PongMessage(
            type=d.get("type", "PONG"),
            timestampNs=d.get("timestampNs", 0),
            serverTimestampNs=d.get("serverTimestampNs", 0),
        )

    @classmethod
    def decode_error(cls, payload: bytes) -> ErrorMessage:
        d = cls.decode(payload)
        return ErrorMessage(
            type=d.get("type", "ERROR"),
            code=d.get("code", 0),
            message=d.get("message", ""),
            fatal=d.get("fatal", False),
        )

    @classmethod
    def decode_clipboard_event(cls, payload: bytes) -> ClipboardEventMessage:
        d = cls.decode(payload)
        return ClipboardEventMessage(
            type=d.get("type", "CLIPBOARD_EVENT"),
            content=d.get("content", ""),
            mimeType=d.get("mimeType", "text/plain"),
        )
