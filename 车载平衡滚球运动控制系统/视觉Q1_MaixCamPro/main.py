# 电赛H题 - 视觉模块（model-314316 高精度钢珠检测版）
# 功能: YOLO检测 + 坐标换算 + 稳定性判断 + 串口回传
# 模型: model_314316.mud（高精度钢珠检测）

from maix import camera, display, image, nn, app, uart, pinmap, time, network, err, http
from struct import pack
import os

# ================= 1. UART1 初始化 =================
pinmap.set_pin_function("A19", "UART1_TX")
pinmap.set_pin_function("A18", "UART1_RX")
serial = uart.UART("/dev/ttyS1", 115200)

# ================= 2. 通信协议 =================
FRAME_VERSION = 0x01
TYPE_HEARTBEAT = 0x01
TYPE_DETECT_RESULT = 0x02
TYPE_VISION_STATUS = 0x03

seq_counter = 0

def crc16_modbus(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def send_frame(frame_type, payload):
    global seq_counter
    header = pack("<BBBBB", 0xAA, 0x55, FRAME_VERSION, frame_type, seq_counter & 0xFF)
    length = pack("B", len(payload))
    frame_no_crc = header + length + payload
    crc = crc16_modbus(frame_no_crc)
    frame = frame_no_crc + pack("<H", crc)
    serial.write(frame)
    seq_counter += 1

def send_heartbeat():
    send_frame(TYPE_HEARTBEAT, pack("B", 0))

def send_detect_result(position_cm_x10, velocity_cm_x10, timestamp_ms, stable_flag, confidence, cx, cy):
    """
    payload (12 bytes):
      position_cm_x10: int16  (钢珠位置x10，如+53表示+5.3cm，范围-125~+126)
      velocity_cm_x10: int16  (钢珠速度x10，单位cm/s，如+35表示+3.5cm/s)
      timestamp_ms:    uint16 (时间戳低16位，ms，用于主控判断数据新鲜度)
      stable_flag:     uint8  (0=不稳定, 1=稳定)
      confidence:      uint8  (置信度 0-100)
      cx:              uint16 (像素中心x，调试用)
      cy:              uint16 (像素中心y，调试用)
    """
    payload = pack("<hhHBBHH", position_cm_x10, velocity_cm_x10, timestamp_ms, stable_flag, confidence, cx, cy)
    send_frame(TYPE_DETECT_RESULT, payload)

def send_vision_status(code, detail):
    send_frame(TYPE_VISION_STATUS, pack("BB", code, detail))

# 启动心跳
send_heartbeat()
print("[UART] Boot heartbeat sent.")

# ================= 3. 模型加载 =================
model_path = "model_314316.mud"
if not os.path.exists(model_path):
    model_path = "/root/0731/model_314316.mud"

detector = nn.YOLOv5(model=model_path)
print(f"[Model] Loaded: {model_path}")
print(f"[Model] Labels: {detector.labels}")

# ================= 4. 相机与显示 =================
cam = camera.Camera(detector.input_width(), detector.input_height(), detector.input_format())
dis = display.Display()
cam.skip_frames(10)

# ================= 5. WiFi 连接 =================
WIFI_SSID = ""
WIFI_PASSWORD = ""

if WIFI_SSID and WIFI_PASSWORD:
    print(f"[WiFi] Connecting to {WIFI_SSID} ...")
    w = network.wifi.Wifi()
    e = w.connect(WIFI_SSID, WIFI_PASSWORD, wait=True, timeout=30)
    if e != err.Err.ERR_NONE:
        print(f"[WiFi] Connect failed: {e}")
        wifi_ok = False
    else:
        ip = w.get_ip()
        print(f"[WiFi] Connected! IP: {ip}")
        wifi_ok = True
else:
    print("[WiFi] Skipped: configure credentials locally to enable MJPEG streaming.")
    wifi_ok = False

# ================= 6. MJPEG 图传 =================
stream = None
stream_interval_ms = 100  # ~10fps

if wifi_ok:
    try:
        stream = http.JpegStreamer()
        stream.start()
        print(f"[Stream] MJPEG started: http://{stream.host()}:{stream.port()}")
    except Exception as ex:
        print(f"[Stream] Failed: {ex}")
        stream = None
else:
    print("[Stream] Skipped (WiFi not connected).")

# ================= 7. 标定参数（正对拍摄 - 分段线性标定） =================
# 标定方法：开启 CALIBRATION_MODE=True，将钢球依次放到 -12.5, -5, 0, +5, +12.5 cm 位置，
#          记录屏幕显示的 cx 值，然后更新 CALIB_POINTS 并关闭标定模式。
CALIBRATION_MODE = False  # 标定完成

# 分段标定点 (cx, cm) — model_314316 实际标定数据
CALIB_POINTS = [(4, -12.5), (67, -5.0), (110, 0.0), (154, 5.0), (210, 12.5)]

def pixel_to_cm(cx):
    """像素x坐标转换为实际cm位置（分段线性插值）"""
    if cx <= CALIB_POINTS[0][0]:
        return -12.5
    if cx >= CALIB_POINTS[-1][0]:
        return 12.5
    for i in range(len(CALIB_POINTS) - 1):
        cx0, cm0 = CALIB_POINTS[i]
        cx1, cm1 = CALIB_POINTS[i + 1]
        if cx0 <= cx <= cx1:
            return cm0 + (cx - cx0) * (cm1 - cm0) / (cx1 - cx0)
    return 0.0

# ================= 6. 检测与稳定性参数 =================
CONF_TH = 0.1
IOU_TH = 0.45
SEND_INTERVAL_MS = 20       # 串口发送间隔(ms)

STABLE_WINDOW = 5            # 滑动窗口大小（帧数）
STABLE_THRESHOLD_CM = 0.8   # 窗口内位置变化小于此值(cm)判定为稳定

# ================= 7. 卡尔曼滤波器（位置+速度） =================
class KalmanTracker:
    """
    一维卡尔曼滤波器，状态向量 [位置, 速度]
    同时输出平滑后的位置和速度，供主控 PID 使用
    """
    def __init__(self, process_noise=0.25, measurement_noise=0.5, dt=0.02):
        # 状态: [位置(cm), 速度(cm/s)]
        self.x = [0.0, 0.0]
        # 协方差矩阵 2x2: [[P00, P01], [P10, P22]]
        self.P = [[1.0, 0.0], [0.0, 1.0]]
        # 过程噪声
        self.q = process_noise
        # 测量噪声
        self.r = measurement_noise
        # 时间间隔(s)
        self.dt = dt
        # 滑动窗口（用于稳定性判断）
        self.window = []
        self.window_size = 5
        self.threshold_cm = 0.8

    def update(self, measurement_cm):
        """卡尔曼更新：预测 + 校正"""
        dt = self.dt

        # === 预测步骤 ===
        # 状态预测: x_new = F * x
        # F = [[1, dt], [0, 1]]  (匀速运动模型)
        x_pred = [
            self.x[0] + self.x[1] * dt,  # 位置预测
            self.x[1]                     # 速度预测（假设匀速）
        ]

        # 协方差预测: P_new = F * P * F^T + Q
        # Q = [[q, 0], [0, q]]
        P_pred = [
            [self.P[0][0] + 2 * dt * self.P[0][1] + dt * dt * self.P[1][1] + self.q,
             self.P[0][1] + dt * self.P[1][1]],
            [self.P[1][0] + dt * self.P[1][1],
             self.P[1][1] + self.q]
        ]

        # === 校正步骤 ===
        # 测量矩阵 H = [1, 0] (只测量位置)
        # 创新: y = z - H * x_pred
        y = measurement_cm - x_pred[0]

        # 创新协方差: S = H * P_pred * H^T + R
        S = P_pred[0][0] + self.r

        # 卡尔曼增益: K = P_pred * H^T / S
        K = [P_pred[0][0] / S, P_pred[1][0] / S]

        # 状态更新: x = x_pred + K * y
        self.x = [
            x_pred[0] + K[0] * y,
            x_pred[1] + K[1] * y
        ]

        # 协方差更新: P = (I - K*H) * P_pred
        self.P = [
            [(1 - K[0]) * P_pred[0][0], (1 - K[0]) * P_pred[0][1]],
            [-K[1] * P_pred[0][0], P_pred[1][1] - K[1] * P_pred[0][1]]
        ]

        # 更新滑动窗口（用于稳定性判断）
        self.window.append(self.x[0])
        if len(self.window) > self.window_size:
            self.window.pop(0)

    def get_position(self):
        """返回平滑后的位置(cm)"""
        return self.x[0]

    def get_velocity(self):
        """返回平滑后的速度(cm/s)"""
        return self.x[1]

    def is_stable(self):
        """滑动窗口内位置变化小于阈值则判定为稳定"""
        if len(self.window) < 3:
            return False
        max_val = max(self.window)
        min_val = min(self.window)
        return (max_val - min_val) < self.threshold_cm

tracker = KalmanTracker(process_noise=0.1, measurement_noise=0.5, dt=0.05)

# ================= 9. 主循环 =================
last_send_ms = 0
last_stream_ms = 0

if CALIBRATION_MODE:
    print("[Calibration] Mode ON - 屏幕大字显示cx/cm，串口暂停发送")
    print("[Calibration] 请将钢球依次放到 -12.5, -5, 0, +5, +12.5 cm 位置，记录屏幕cx值")
else:
    print("[Normal] Mode - 正常工作")

while not app.need_exit():
    now_ms = time.ticks_ms()
    img = cam.read()

    objs = detector.detect(img, conf_th=CONF_TH, iou_th=IOU_TH)

    if len(objs) > 0:
        best = max(objs, key=lambda o: o.score)
        cx = best.x + best.w // 2
        cy = best.y + best.h // 2
        conf_pct = int(best.score * 100)

        raw_cm = pixel_to_cm(cx)
        tracker.update(raw_cm)
        smooth_cm = tracker.get_position()
        velocity_cm = tracker.get_velocity()
        stable = tracker.is_stable()
        pos_cm_x10 = int(round(smooth_cm * 10))
        vel_cm_x10 = int(round(velocity_cm * 10))

        # 画检测框（稳定=绿，运动=红）
        color = image.COLOR_GREEN if stable else image.COLOR_RED
        img.draw_rect(best.x, best.y, best.w, best.h, color=color)
        label = f'{detector.labels[best.class_id]}: {best.score:.2f}'
        img.draw_string(best.x, best.y - 10, label, color=color, scale=1)

        if CALIBRATION_MODE:
            # 标定模式：大字显示cx和cm，暂停串口发送
            img.draw_string(4, 4, 'CALIB MODE', color=image.COLOR_YELLOW, scale=2)
            img.draw_string(4, 36, f'cx={cx}', color=image.COLOR_WHITE, scale=2)
            img.draw_string(4, 68, f'cm={raw_cm:+.2f}', color=image.COLOR_WHITE, scale=2)
            img.draw_string(4, 100, f'smooth={smooth_cm:+.1f}', color=image.COLOR_BLUE, scale=1)
            img.draw_string(4, 126, f'vel={velocity_cm:+.1f}cm/s', color=image.COLOR_BLUE, scale=1)
            print(f"[Calib] cx={cx} raw_cm={raw_cm:+.2f} smooth={smooth_cm:+.2f} vel={velocity_cm:+.2f}cm/s")
        else:
            # 正常模式：串口发送 + 屏幕显示
            if now_ms - last_send_ms >= SEND_INTERVAL_MS:
                ts = now_ms & 0xFFFF
                send_detect_result(pos_cm_x10, vel_cm_x10, ts, 1 if stable else 0, conf_pct, cx, cy)
                last_send_ms = now_ms
                print(f"[Send] pos={smooth_cm:+.1f}cm vel={velocity_cm:+.1f}cm/s stable={stable} conf={conf_pct}%")

            status = "STABLE" if stable else "MOVING"
            info = f'{smooth_cm:+.1f}cm {status} {conf_pct}%'
            vel_info = f'v={velocity_cm:+.1f}cm/s'
            img.draw_string(4, 4, info, color=color, scale=1)
            img.draw_string(4, 20, vel_info, color=image.COLOR_BLUE, scale=1)

            # 画中心参考线
            center_y = img.height() // 2
            img.draw_line(0, center_y, img.width(), center_y, color=image.COLOR_BLUE, thickness=1)

    else:
        if not CALIBRATION_MODE:
            if now_ms - last_send_ms >= 500:
                send_vision_status(0, 0)
                last_send_ms = now_ms
        img.draw_string(4, 4, 'NO DETECT', color=image.COLOR_YELLOW, scale=2)

    # 图传：发送带检测框的画面
    if stream is not None and (now_ms - last_stream_ms >= stream_interval_ms):
        stream.write(img)
        last_stream_ms = now_ms

    dis.show(img)

print("[App] Exiting.")
