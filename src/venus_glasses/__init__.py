"""Venus smart glasses serial communication library."""

from venus_glasses.serial_tool import VenusSerialTool
from venus_glasses.enums import (
    ButtonEvent,
    OtsEvent,
    RecorderEvent,
    TempleEvent,
    LightBrightnessEvent,
    TranslatorStartType,
    TranslatorStopReason,
)

__version__ = "0.1.0"
__all__ = [
    "VenusSerialTool",
    "ButtonEvent",
    "OtsEvent",
    "RecorderEvent",
    "TempleEvent",
    "LightBrightnessEvent",
    "TranslatorStartType",
    "TranslatorStopReason",
]