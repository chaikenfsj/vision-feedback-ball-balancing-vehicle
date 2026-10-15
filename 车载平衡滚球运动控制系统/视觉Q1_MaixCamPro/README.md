# 视觉 Q1 — MaixCam Pro 钢球检测

这是使用 MaixCam Vision 编写、部署到 MaixCam Pro 的视觉工程。它通过 YOLOv5 检测钢球，按标定表把像素横坐标换算为摆杆坐标，并将平滑后的钢球状态通过 UART 发给 MSPM0 主控。

## 工程文件

- `main.py`：相机采集、YOLO 检测、坐标标定、卡尔曼滤波、稳定性判定、图传和串口协议。
- `model_314316.mud`、`model_314316.cvimodel`：检测模型。
- `app.yaml`：MaixCam Vision 工程配置。
- `report.json`：模型训练/评估记录。

使用 MaixCam Vision 打开本目录，连接 MaixCam Pro 后部署或运行工程。模型默认检测标签为 `steel`；标定点对应 25 cm 摆杆的约 -12.5 cm 至 +12.5 cm 范围。

## 串口

视觉端使用 MaixCam Pro 的 `UART1`：`A19` 为 TX，`A18` 为 RX，115200 baud、8N1。它向 MSPM0G3507 的 `UART3` 发送帧：

```text
AA 55 | version | type | sequence | payload_length | payload | CRC16-LE
```

检测帧（`type = 0x02`）的 payload 为 12 字节小端序：

```text
int16 position_cm_x10 | int16 velocity_cm_x10 | uint16 timestamp_ms |
uint8 stable | uint8 confidence_pct | uint16 pixel_cx | uint16 pixel_cy
```

接线时将 `A19 (TX)` 接到主控 `PA25 (UART3_RX)`；如需预留双向通信，可将 `A18 (RX)` 接到 `PA26 (UART3_TX)`；两端共地并保持 3.3 V TTL 电平。

## Wi-Fi 图传

程序支持可选的 MJPEG 图传。公开版本没有保存任何 Wi-Fi 凭据，因此默认跳过联网；如需使用图传，只在已部署到自己设备的本地 `main.py` 中填写 `WIFI_SSID` 和 `WIFI_PASSWORD`，不要提交这些内容。

## 调参

- `CALIB_POINTS`：像素横坐标到物理厘米的分段线性标定表。
- `CONF_TH`：YOLO 检测阈值。主控会接受置信度不低于 50% 的样本，实际使用时建议将视觉阈值与此限制一起调整。
- `SEND_INTERVAL_MS`：串口发送周期，当前为 20 ms。
- `STABLE_WINDOW`、`STABLE_THRESHOLD_CM`：静止判定窗口和阈值。
