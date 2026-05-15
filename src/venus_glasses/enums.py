"""Enumeration types for Venus glasses events."""

from enum import Enum


class ButtonEvent(Enum):
    """Button event types."""

    INVALID = 0
    PRESS = 1
    CLICK = 2
    DOUBLE_CLICK = 3
    TRIPLE_CLICK = 4
    FIVE_CLICK = 5
    HOLD_1S = 6
    HOLD_3S = 7
    HOLD_5S = 8
    HOLD_8S = 9
    FAC_RESET = 10
    RELEASED = 11


class OtsEvent(Enum):
    """OTS rotation event."""

    CLOCKWISE = 45
    COUNTER_CLOCKWISE = -45


class RecorderEvent(Enum):
    """Recorder event types."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    INFO = "info"


class TempleEvent(Enum):
    """Glasses temple fold/unfold event."""

    FOLD = 1
    UNFOLD = 0


class LightBrightnessEvent(Enum):
    """Light brightness levels."""

    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2


class TranslatorStartType(Enum):
    """Translator start types."""

    CLASSIC = "classic"
    TITLE = "title"


class TranslatorStopReason(Enum):
    """Translator stop reasons."""

    GESTURE = 1
    APP = 2
    BT = 3
    TIMEOUT = 4
