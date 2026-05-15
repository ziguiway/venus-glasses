"""Real device test for venus_glasses library."""

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


def test_real_device():
    """Test with real Venus device."""

    # 连接设备
    device = VenusSerialTool("/dev/tty.usbserial-A9VQ8KI5")

    # 开始记录日志
    print("Starting log...")
    device.start_log("./test_logs")

    # 等待连接
    import time
    time.sleep(2)

    print(f"Connected: {device.is_serial_connected}")

    # 测试发送命令
    print("\n--- Testing commands ---")

    # 1. 设置 AP 性能模式
    print("1. Setting AP performance mode...")
    result = device.set_ap_perf_mode()
    print(f"   set_ap_perf_mode: {result}")
    time.sleep(0.5)

    # 2. 发送按钮单击事件
    print("2. Sending button click event...")
    result = device.send_btn_event(ButtonEvent.CLICK)
    print(f"   send_btn_event(CLICK): {result}")
    time.sleep(0.5)

    # 3. 发送 OTS 旋钮事件
    print("3. Sending OTS clockwise event...")
    result = device.send_ots_event(OtsEvent.CLOCKWISE)
    print(f"   send_ots_event(CLOCKWISE): {result}")
    time.sleep(0.5)

    # 4. 发送显示常亮
    print("4. Setting display always on...")
    result = device.send_display_always_on(True)
    print(f"   send_display_always_on(True): {result}")
    time.sleep(0.5)

    # 5. 获取蓝牙名称
    print("5. Getting Bluetooth name...")
    bt_name = device.get_bt_name(timeout=3.0)
    print(f"   get_bt_name: '{bt_name}'")
    time.sleep(0.5)

    # 6. 测试日志开关
    print("6. Testing log commands...")
    result = device.set_log_all(True)
    print(f"   set_log_all(True): {result}")
    time.sleep(0.5)

    # 7. 发送 help 命令并获取响应
    print("7. Sending help command...")
    response = device.send_command_and_wait_response("help", timeout=3.0)
    print(f"   help response:\n{response[:500] if response else '<empty>'}...")

    # 读取日志
    print("\n--- Reading log ---")
    log = device.read_log(duration=1.0)
    print(f"Log length: {len(log)} chars")

    # 停止记录
    print("\n--- Stopping log ---")
    device.stop_log()
    print("Done!")

    print(f"\nLogs saved to: {device.log_path}")


if __name__ == "__main__":
    test_real_device()