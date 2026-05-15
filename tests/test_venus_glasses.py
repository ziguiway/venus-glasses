"""Tests for venus_glasses library."""

import pytest
from unittest.mock import MagicMock, patch
from venus_glasses import (
    VenusSerialTool,
    ButtonEvent,
    OtsEvent,
    RecorderEvent,
    TempleEvent,
    LightBrightnessEvent,
    TranslatorStartType,
    TranslatorStopReason,
)


class TestEnums:
    """Test enum values."""

    def test_button_event_values(self):
        assert ButtonEvent.INVALID.value == 0
        assert ButtonEvent.PRESS.value == 1
        assert ButtonEvent.CLICK.value == 2
        assert ButtonEvent.DOUBLE_CLICK.value == 3
        assert ButtonEvent.TRIPLE_CLICK.value == 4
        assert ButtonEvent.FIVE_CLICK.value == 5
        assert ButtonEvent.HOLD_1S.value == 6
        assert ButtonEvent.HOLD_3S.value == 7
        assert ButtonEvent.HOLD_5S.value == 8
        assert ButtonEvent.HOLD_8S.value == 9
        assert ButtonEvent.FAC_RESET.value == 10
        assert ButtonEvent.RELEASED.value == 11

    def test_ots_event_values(self):
        assert OtsEvent.CLOCKWISE.value == 45
        assert OtsEvent.COUNTER_CLOCKWISE.value == -45

    def test_recorder_event_values(self):
        assert RecorderEvent.START.value == "start"
        assert RecorderEvent.PAUSE.value == "pause"
        assert RecorderEvent.RESUME.value == "resume"
        assert RecorderEvent.STOP.value == "stop"
        assert RecorderEvent.INFO.value == "info"

    def test_temple_event_values(self):
        assert TempleEvent.FOLD.value == 1
        assert TempleEvent.UNFOLD.value == 0

    def test_light_brightness_event_values(self):
        assert LightBrightnessEvent.LEVEL_0.value == 0
        assert LightBrightnessEvent.LEVEL_1.value == 1
        assert LightBrightnessEvent.LEVEL_2.value == 2

    def test_translator_start_type_values(self):
        assert TranslatorStartType.CLASSIC.value == "classic"
        assert TranslatorStartType.TITLE.value == "title"

    def test_translator_stop_reason_values(self):
        assert TranslatorStopReason.GESTURE.value == 1
        assert TranslatorStopReason.APP.value == 2
        assert TranslatorStopReason.BT.value == 3
        assert TranslatorStopReason.TIMEOUT.value == 4


class TestVenusSerialToolCommands:
    """Test command generation."""

    def setup_method(self):
        self.mock_serial = MagicMock()
        self.mock_serial.is_open = True
        self.mock_serial.write = MagicMock(return_value=None)
        self.mock_serial.flush = MagicMock()

        with patch("venus_glasses.serial_tool.serial.Serial", return_value=self.mock_serial):
            self.tool = VenusSerialTool("COM18")
            self.tool._serial = self.mock_serial

    def test_send_btn_event_click(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_btn_event(ButtonEvent.CLICK)
            mock_send.assert_called_once_with("lvgl btn_send 2")
            assert result == True

    def test_send_btn_event_hold_3s(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_btn_event(ButtonEvent.HOLD_3S)
            mock_send.assert_called_once_with("lvgl btn_send 7")
            assert result == True

    def test_send_ots_event_clockwise(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_ots_event(OtsEvent.CLOCKWISE)
            mock_send.assert_called_once_with("uorb_injector ots 45")
            assert result == True

    def test_send_ots_event_counter_clockwise(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_ots_event(OtsEvent.COUNTER_CLOCKWISE)
            mock_send.assert_called_once_with("uorb_injector ots -45")
            assert result == True

    def test_send_recorder_event_start(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_recorder_event(RecorderEvent.START)
            mock_send.assert_called_once_with("uorb_injector recorder start")
            assert result == True

    def test_send_temple_event_fold(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_temple_event(TempleEvent.FOLD)
            mock_send.assert_called_once_with("uorb_injector hall 1")
            assert result == True

    def test_send_light_brightness_event(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_light_brightness_event(LightBrightnessEvent.LEVEL_1)
            mock_send.assert_called_once_with("aw21104 --level 1")
            assert result == True

    def test_send_translator_start_type(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_translator_start_type(TranslatorStartType.CLASSIC)
            mock_send.assert_called_once_with("translator start classic")
            assert result == True

    def test_send_translator_stop_reason(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_translator_stop_reason(TranslatorStopReason.GESTURE)
            mock_send.assert_called_once_with("translator stop 1")
            assert result == True

    def test_send_display_always_on_true(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_display_always_on(True)
            mock_send.assert_called_once_with("display always_on 1 system")
            assert result == True

    def test_send_display_always_on_false(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_display_always_on(False)
            mock_send.assert_called_once_with("display always_on 0 system")
            assert result == True

    def test_send_display_always_on_custom_source(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.send_display_always_on(True, source="mtbf")
            mock_send.assert_called_once_with("display always_on 1 mtbf")
            assert result == True

    def test_set_ap_perf_mode(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_ap_perf_mode()
            mock_send.assert_called_once_with("sysfreq set 24 19")
            assert result == True

    def test_reboot(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.reboot()
            mock_send.assert_called_once_with("reboot")
            assert result == True


class TestBluetoothCommands:
    """Test Bluetooth commands."""

    def setup_method(self):
        self.mock_serial = MagicMock()
        self.mock_serial.is_open = True

        with patch("venus_glasses.serial_tool.serial.Serial", return_value=self.mock_serial):
            self.tool = VenusSerialTool("COM18")
            self.tool._serial = self.mock_serial

    def test_remove_bond(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.remove_bond()
            mock_send.assert_called_once_with("rnl rmbond 1")
            assert result == True

    def test_set_bt_name(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_bt_name("MyVenus")
            mock_send.assert_called_once_with("rnl setname MyVenus")
            assert result == True

    def test_get_bt_name_returns_string(self):
        with patch.object(
            self.tool, "send_command_and_wait_response", return_value="venus_device"
        ) as mock_send:
            result = self.tool.get_bt_name()
            mock_send.assert_called_once_with("rnl getname", timeout=5.0)
            assert result == "venus_device"
            assert isinstance(result, str)

    def test_get_bt_name_empty_on_failure(self):
        with patch.object(
            self.tool, "send_command_and_wait_response", return_value=""
        ) as mock_send:
            result = self.tool.get_bt_name()
            assert result == ""

    def test_get_bt_name_custom_timeout(self):
        with patch.object(
            self.tool, "send_command_and_wait_response", return_value="test_name"
        ) as mock_send:
            result = self.tool.get_bt_name(timeout=10.0)
            mock_send.assert_called_once_with("rnl getname", timeout=10.0)
            assert result == "test_name"

    def test_start_advertising(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.start_advertising()
            mock_send.assert_called_once_with("rnl startadv")
            assert result == True


class TestLogCommands:
    """Test log switch commands."""

    def setup_method(self):
        self.mock_serial = MagicMock()
        self.mock_serial.is_open = True

        with patch("venus_glasses.serial_tool.serial.Serial", return_value=self.mock_serial):
            self.tool = VenusSerialTool("COM18")
            self.tool._serial = self.mock_serial

    def test_set_log_all_enable(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_all(True)
            mock_send.assert_called_once_with("rntests log 1")
            assert result == True

    def test_set_log_all_disable(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_all(False)
            mock_send.assert_called_once_with("rntests log 0")
            assert result == True

    def test_set_log_ap(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_ap(True)
            mock_send.assert_called_once_with("rntests log ap 1")
            assert result == True

    def test_set_log_hifi(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_hifi(False)
            mock_send.assert_called_once_with("rntests log hifi 0")
            assert result == True

    def test_set_log_apc1(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_apc1(True)
            mock_send.assert_called_once_with("rntests log apc1 1")
            assert result == True

    def test_set_log_bth(self):
        with patch.object(self.tool, "send_command", return_value=True) as mock_send:
            result = self.tool.set_log_bth(False)
            mock_send.assert_called_once_with("rntests log bth 0")
            assert result == True


class TestSendCommand:
    """Test send_command method."""

    def setup_method(self):
        self.mock_serial = MagicMock()
        self.mock_serial.is_open = True
        self.mock_serial.write = MagicMock()
        self.mock_serial.flush = MagicMock()

        with patch("venus_glasses.serial_tool.serial.Serial", return_value=self.mock_serial):
            self.tool = VenusSerialTool("COM18")

    def test_send_command_empty_raises_error(self):
        with pytest.raises(ValueError, match="command cannot be empty"):
            self.tool.send_command("")

        with pytest.raises(ValueError, match="command cannot be empty"):
            self.tool.send_command("   ")

    def test_send_command_success(self):
        self.tool._serial = self.mock_serial
        self.tool.is_logging = False

        result = self.tool.send_command("help")
        assert result == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])