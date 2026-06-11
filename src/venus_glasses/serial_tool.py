"""Venus serial communication tool."""

import json
import logging
import os
import queue
import threading
import time
import uuid
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import Callable, Deque, Optional
import serial
import re

from venus_glasses.enums import (
    ButtonEvent,
    LightBrightnessEvent,
    OtsEvent,
    RecorderEvent,
    TempleEvent,
    TranslatorStartType,
    TranslatorStopReason,
)

# Constants
SET_AP_PERF_MODE = "sysfreq set 24 19"
REBOOT_COMMAND = "reboot"


class FileLogger:
    """File logger with rotation support."""

    def __init__(
        self,
        logger_name: str,
        log_path: str,
        formatter: str = "[%(asctime)s] %(message)s",
        max_bytes: int = 50 * 1024 * 1024,
    ):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if self.logger.handlers:
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)

        fh = RotatingFileHandler(
            filename=log_path, maxBytes=max_bytes, backupCount=100, encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(formatter))
        self.logger.addHandler(fh)

    def get_logger(self):
        return self.logger


class VenusSerialTool:
    """Venus smart glasses serial communication tool."""

    def __init__(
        self,
        com_name: str,
        baudrate: int = 921600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 0.1,
        write_timeout: float = 1.0,
        command_terminator: str = "\r\n",
        serial_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        self.com_name = com_name
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.command_terminator = command_terminator
        self._serial_factory = serial_factory or serial.Serial

        self.log_path: Optional[str] = None
        self.is_logging = False
        self.is_serial_connected = False

        self._serial = None
        self._serial_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._command_condition = threading.Condition()
        self._stop_event = threading.Event()
        self._serial_io_enabled = threading.Event()
        self._watchers: dict[str, Callable[[str], None]] = {}
        self._line_buffer = bytearray()

        self._business_queue: Deque[str] = deque(maxlen=10000)
        self._command_lines: Deque[str] = deque(maxlen=10000)
        self._watcher_queue: "queue.Queue[str]" = queue.Queue()
        self._writer_queue: "queue.Queue[str]" = queue.Queue()

        self._reader_thread: Optional[threading.Thread] = None
        self._watcher_thread: Optional[threading.Thread] = None
        self._writer_thread: Optional[threading.Thread] = None

        self._nuttx_logger = None
        self._crash_logger = None
        self._disconnection_logger = None

        self._read_chunk_size = 4096
        self._reconnect_interval = 1.0
        self._serial_io_enabled.set()

    def _build_serial(self):
        return self._serial_factory(
            port=self.com_name,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
        )

    def _create_loggers(self) -> None:
        assert self.log_path is not None

        logger_suffix = f"{self.com_name}-{id(self)}"
        nuttx_log_file = os.path.join(self.log_path, "nuttx.log")
        crash_log_file = os.path.join(self.log_path, "crash.log")
        disconnection_log_file = os.path.join(self.log_path, "disconnection.log")

        self._nuttx_logger = FileLogger(
            f"venus-nuttx-{logger_suffix}", nuttx_log_file
        ).get_logger()
        self._crash_logger = FileLogger(
            f"venus-crash-{logger_suffix}", crash_log_file
        ).get_logger()
        self._disconnection_logger = FileLogger(
            f"venus-disconnection-{logger_suffix}", disconnection_log_file
        ).get_logger()

    def _open_serial(self) -> bool:
        with self._serial_lock:
            if self._serial is not None and getattr(self._serial, "is_open", False):
                self.is_serial_connected = True
                return True

            try:
                self._serial = self._build_serial()
                self.is_serial_connected = True
                logging.info(
                    "connected Venus serial port %s at %s baud",
                    self.com_name,
                    self.baudrate,
                )
                return True
            except (serial.SerialException, OSError) as exc:
                self._serial = None
                self.is_serial_connected = False
                logging.warning(
                    "failed to open Venus serial port %s: %s", self.com_name, exc
                )
                return False

    def _close_serial(self) -> None:
        with self._serial_lock:
            serial_port = self._serial
            self._serial = None

        self.is_serial_connected = False

        if serial_port is None:
            return

        try:
            if getattr(serial_port, "is_open", False):
                serial_port.close()
        except Exception as exc:
            logging.warning(
                "failed to close Venus serial port %s: %s", self.com_name, exc
            )

    def _flush_line_buffer(self) -> None:
        if not self._line_buffer:
            return

        line = self._decode_line(bytes(self._line_buffer))
        self._line_buffer.clear()
        if line:
            self._publish_line(line)

    @staticmethod
    def _decode_line(raw: bytes) -> str:
        return raw.decode("utf-8", errors="replace").strip()

    def _publish_line(self, line: str) -> None:
        if not line:
            return

        self._business_queue.append(line)
        self._writer_queue.put_nowait(line)
        self._watcher_queue.put_nowait(line)

        with self._command_condition:
            self._command_lines.append(line)
            self._command_condition.notify_all()

    def _process_chunk(self, chunk: bytes) -> None:
        self._line_buffer.extend(chunk)
        parts = self._line_buffer.splitlines(keepends=True)

        if parts and not parts[-1].endswith((b"\r", b"\n")):
            self._line_buffer = bytearray(parts.pop())
        else:
            self._line_buffer.clear()

        for raw_line in parts:
            line = self._decode_line(raw_line.rstrip(b"\r\n"))
            if line:
                self._publish_line(line)

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self._serial_io_enabled.is_set():
                self._stop_event.wait(0.1)
                continue

            if not self._open_serial():
                self._stop_event.wait(self._reconnect_interval)
                continue

            with self._serial_lock:
                serial_port = self._serial

            if serial_port is None:
                self._stop_event.wait(self._reconnect_interval)
                continue

            try:
                chunk = serial_port.read(self._read_chunk_size)
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                if chunk:
                    self._process_chunk(chunk)
            except (serial.SerialException, OSError):
                self._flush_line_buffer()
                self._close_serial()
                self._stop_event.wait(self._reconnect_interval)

        self._flush_line_buffer()
        self._close_serial()

    def _writer_loop(self) -> None:
        while not self._stop_event.is_set() or not self._writer_queue.empty():
            try:
                line = self._writer_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self._nuttx_logger:
                self._nuttx_logger.info(line)

    def _watcher_loop(self) -> None:
        crash_keywords = [
            "STACK bthost_crash",
            "host rx acl overflow",
            "Got panic msg",
            "do_spp_write write to stack failed",
            "malloc buf fail",
            "dump_assert_info",
        ]

        while not self._stop_event.is_set() or not self._watcher_queue.empty():
            try:
                line = self._watcher_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if any(keyword in line for keyword in crash_keywords):
                if self._crash_logger:
                    self._crash_logger.info("venus crashed: %s", line)

            if "boot_reason" in line:
                if self._crash_logger:
                    self._crash_logger.info("venus rebooted: %s\r\n\r\n", line)

            if "CONNECTION_STATE_DISCONNECTED" in line:
                if self._disconnection_logger:
                    self._disconnection_logger.info("venus disconnected: %s", line)

            if self._watchers:
                for keyword, watcher in list(self._watchers.items()):
                    if keyword in line:
                        threading.Thread(
                            target=watcher, args=(line,), daemon=True
                        ).start()

    # ==================== Public API ====================

    def start_log(self, log_path: str) -> None:
        """Start logging serial output."""
        if self.is_logging:
            logging.info("Venus serial logging already started on %s", self.com_name)
            return

        self.log_path = log_path
        os.makedirs(log_path, exist_ok=True)
        self._create_loggers()

        self._stop_event = threading.Event()
        self._line_buffer.clear()
        self.is_logging = True
        self._serial_io_enabled.set()

        self._reader_thread = threading.Thread(
            target=self._reader_loop, name=f"venus-reader-{self.com_name}", daemon=True
        )
        self._writer_thread = threading.Thread(
            target=self._writer_loop, name=f"venus-writer-{self.com_name}", daemon=True
        )
        self._watcher_thread = threading.Thread(
            target=self._watcher_loop,
            name=f"venus-watcher-{self.com_name}",
            daemon=True,
        )

        self._reader_thread.start()
        self._writer_thread.start()
        self._watcher_thread.start()

    def stop_log(self) -> None:
        """Stop logging and close serial connection."""
        if not self.is_logging:
            return

        self.is_logging = False
        self._stop_event.set()
        self._serial_io_enabled.set()
        self._close_serial()

        for thread in (self._reader_thread, self._writer_thread, self._watcher_thread):
            if thread and thread.is_alive():
                thread.join(timeout=5)

    def read_log(self, duration: float = 0.0) -> str:
        """Read logged output."""
        if not isinstance(duration, (int, float)):
            raise TypeError("duration must be an int or float")

        duration = max(float(duration), 0.0)
        if duration > 0:
            self._business_queue.clear()
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                self._stop_event.wait(min(0.05, max(0.0, deadline - time.monotonic())))

        log_lines = []
        while self._business_queue:
            log_lines.append(self._business_queue.popleft())
        return "\r\n".join(log_lines)

    def clear_log_cache(self) -> None:
        """Clear cached log data."""
        self._business_queue.clear()

    def register_watcher(
        self, keyword: str | list, watcher: Callable[[str], None]
    ) -> None:
        """Register a keyword watcher."""
        if isinstance(keyword, str):
            keyword = [keyword]

        for item in keyword:
            if item in self._watchers:
                logging.info("%s watcher already exists and will be replaced", item)
            self._watchers[item] = watcher
            logging.info("registered Venus watcher keyword=%s", item)

    def unregister_watcher(self, keyword: str) -> None:
        """Unregister a keyword watcher."""
        if keyword in self._watchers:
            del self._watchers[keyword]
        else:
            logging.warning("Venus watcher keyword=%s is not registered", keyword)

    def clear_watcher(self) -> None:
        """Clear all watchers."""
        self._watchers.clear()

    def parse_notification_line(self, line: str) -> Optional[dict]:
        """Parse phone notification from a serial log line.

        Log marker: ``NotificationMessageProcessor::handleNotificationReceived:``

        Returns ``None`` if the line is not a notification log. Otherwise a dict with
        ``is_incoming_call``, ``is_missed_call``, ``is_message``, ``phone_number``,
        ``title``, ``content``, ``app_id``, ``app_name``, ``uid``.
        """
        marker = "NotificationMessageProcessor::handleNotificationReceived:"
        idx = line.find(marker)
        if idx < 0:
            return None

        payload = line[idx + len(marker) :].strip()
        if not payload.startswith("{"):
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        app_id = str(data.get("appId") or "")
        title = str(data.get("title") or "")
        content = str(data.get("content") or "")
        app_name = str(data.get("appName") or "")

        is_incoming_call = (
            "incallui" in app_id
            and (
                content == "来电"
                or (content == "" and title and title not in ("未接来电",))
            )
        )
        is_missed_call = "未接来电" in title or (
            "dialer" in app_id and int(data.get("category") or 0) == 1
        )
        is_message = any(x in app_id for x in ("messaging", ".mms", "message"))

        phone_number = ""
        for text in (title, content):
            digits = re.sub(r"\D", "", text)
            if len(digits) >= 7:
                phone_number = digits
                break

        return {
            "is_incoming_call": is_incoming_call,
            "is_missed_call": is_missed_call,
            "is_message": is_message,
            "phone_number": phone_number,
            "title": title,
            "content": content,
            "app_id": app_id,
            "app_name": app_name,
            "uid": str(data.get("notificationUID") or ""),
        }

    def send_command(self, command: str) -> bool:
        """Send a raw serial command."""
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command cannot be empty")

        with self._command_lock:
            empty_cmd = "\r\n\r\n\r\n\r\n"
            self._send_commands_locked([empty_cmd])
            time.sleep(0.01)
            return self._send_commands_locked([command])

    def _send_commands_locked(self, commands) -> bool:
        if self.is_logging and not self._serial_io_enabled.is_set():
            logging.warning(
                "Venus serial commands are blocked because serial I/O is paused on %s",
                self.com_name,
            )
            return False

        if not self._open_serial():
            return False

        payload = "".join(
            f"{command.rstrip(chr(13) + chr(10))}{self.command_terminator}"
            for command in commands
        )
        data = payload.encode("utf-8")

        with self._serial_lock:
            serial_port = self._serial

        if serial_port is None:
            self.is_serial_connected = False
            return False

        try:
            serial_port.write(data)
            flush = getattr(serial_port, "flush", None)
            if callable(flush):
                flush()
            return True
        except (serial.SerialException, OSError):
            self._close_serial()
            return False

    def send_command_and_wait_response(
        self,
        command: str,
        timeout: float = 5.0,
        idle_timeout: float = 0.3,
        strip_echo: bool = True,
    ) -> str:
        """Send command and wait for response."""
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command cannot be empty")

        command = command.strip()
        token = uuid.uuid4().hex[:12]
        begin_marker = f"__VENUS_CMD_BEGIN_{token}__"
        end_marker = f"__VENUS_CMD_END_{token}__"
        collected: list[str] = []
        saw_begin = False
        saw_end = False
        cursor = 0
        deadline = time.monotonic() + timeout
        idle_deadline: Optional[float] = None

        with self._command_lock:
            self._command_lines.clear()
            if not self._send_commands_locked(
                [f"echo {begin_marker}", command, f"echo {end_marker}"]
            ):
                return ""

            while time.monotonic() < deadline:
                with self._command_condition:
                    snapshot = list(self._command_lines)
                    if cursor >= len(snapshot):
                        wait_timeout = min(0.1, max(0.0, deadline - time.monotonic()))
                        self._command_condition.wait(timeout=wait_timeout)
                        snapshot = list(self._command_lines)

                    new_lines = snapshot[cursor:]
                    cursor = len(snapshot)

                if new_lines:
                    idle_deadline = time.monotonic() + idle_timeout

                for line in new_lines:
                    if begin_marker in line:
                        saw_begin = True
                        continue
                    if end_marker in line:
                        saw_end = True
                        break
                    if saw_begin:
                        collected.append(line)

                if saw_end:
                    break

                if saw_begin and idle_deadline is not None and time.monotonic() >= idle_deadline:
                    break

        filtered_lines = []
        for line in collected:
            stripped = line.strip()
            if not stripped:
                continue
            if begin_marker in stripped or end_marker in stripped:
                continue
            if strip_echo and stripped == command:
                continue
            filtered_lines.append(stripped)

        return "\n".join(filtered_lines).strip()

    # ==================== Event Commands ====================

    def send_btn_event(self, btn_event: ButtonEvent) -> bool:
        """Send button event. Command: lvgl btn_send {value}"""
        command = f"lvgl btn_send {btn_event.value}"
        return self.send_command(command)

    def send_ots_event(self, ots_event: OtsEvent) -> bool:
        """Send OTS rotation event. Command: uorb_injector ots {value}"""
        command = f"uorb_injector ots {ots_event.value}"
        return self.send_command(command)

    def send_recorder_event(self, recorder_event: RecorderEvent) -> bool:
        """Send recorder event. Command: uorb_injector recorder {value}"""
        command = f"uorb_injector recorder {recorder_event.value}"
        return self.send_command(command)

    def send_temple_event(self, temple_event: TempleEvent) -> bool:
        """Send temple fold/unfold event. Command: uorb_injector hall {value}"""
        command = f"uorb_injector hall {temple_event.value}"
        return self.send_command(command)

    def send_light_brightness_event(
        self, light_brightness_event: LightBrightnessEvent
    ) -> bool:
        """Send light brightness event. Command: aw21104 --level {value}"""
        command = f"aw21104 --level {light_brightness_event.value}"
        return self.send_command(command)

    def send_translator_start_type(
        self, translator_start_type: TranslatorStartType
    ) -> bool:
        """Send translator start type. Command: translator start {value}"""
        command = f"translator start {translator_start_type.value}"
        return self.send_command(command)

    def send_translator_stop_reason(
        self, translator_stop_reason: TranslatorStopReason
    ) -> bool:
        """Send translator stop reason. Command: translator stop {value}"""
        command = f"translator stop {translator_stop_reason.value}"
        return self.send_command(command)

    def send_display_always_on(
        self, display_always_on: bool, source: str = "system"
    ) -> bool:
        """Send display always on command. Command: display always_on {0|1} {source}"""
        command = f"display always_on {1 if display_always_on else 0} {source}"
        return self.send_command(command)

    def set_ap_perf_mode(self) -> bool:
        """Set AP performance mode. Command: sysfreq set 24 19"""
        return self.send_command(SET_AP_PERF_MODE)

    def reboot(self) -> bool:
        """Reboot the glasses. Command: reboot"""
        return self.send_command(REBOOT_COMMAND)

    # ==================== Bluetooth Commands ====================

    def remove_bond(self) -> bool:
        """Remove Bluetooth bond. Command: rnl rmbond 1"""
        command = "rnl rmbond 1"
        return self.send_command(command)

    def set_bt_name(self, name: str) -> bool:
        """Set Bluetooth name. Command: rnl setname {name}"""
        command = f"rnl setname {name}"
        return self.send_command(command)

    def get_bt_name(self, timeout: float = 5.0) -> str:
        """Get Bluetooth name. Command: rnl getname

        Args:
            timeout: Response timeout in seconds

        Returns:
            Bluetooth name string, empty string if failed
        """
        command = "rnl getname"
        response = self.send_command_and_wait_response(command, timeout=timeout)

        # 解析蓝牙名称，匹配格式: "local bluetooth device name: Venus-413"
        match = re.search(r"local bluetooth device name:\s*(\S+)", response)
        if match:
            return match.group(1)
        return ""

    def start_advertising(self) -> bool:
        """Start Bluetooth advertising. Command: rnl startadv"""
        command = "rnl startadv"
        return self.send_command(command)

    # ==================== Log Switch Commands ====================

    def set_log_all(self, enable: bool) -> bool:
        """Enable/disable all logs. Command: rntests log {0|1}"""
        command = f"rntests log {1 if enable else 0}"
        return self.send_command(command)

    def set_log_ap(self, enable: bool) -> bool:
        """Enable/disable AP logs. Command: rntests log ap {0|1}"""
        command = f"rntests log ap {1 if enable else 0}"
        return self.send_command(command)

    def set_log_hifi(self, enable: bool) -> bool:
        """Enable/disable hifi logs. Command: rntests log hifi {0|1}"""
        command = f"rntests log hifi {1 if enable else 0}"
        return self.send_command(command)

    def set_log_apc1(self, enable: bool) -> bool:
        """Enable/disable apc1 logs. Command: rntests log apc1 {0|1}"""
        command = f"rntests log apc1 {1 if enable else 0}"
        return self.send_command(command)

    def set_log_bth(self, enable: bool) -> bool:
        """Enable/disable bth logs. Command: rntests log bth {0|1}"""
        command = f"rntests log bth {1 if enable else 0}"
        return self.send_command(command)
