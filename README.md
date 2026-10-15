# 2026 NUEDC H — 车载平衡滚球运动控制系统

本仓库整理了 2026 年全国大学生电子设计竞赛 H 题的两个实现部分：MaixCam Pro 视觉定位（Q1）和 MSPM0G3507 主控闭环控制（Q2–Q6）。系统使用摄像头检测摆杆凹槽中的钢球位置，经 UART 传给主控，再由主控完成小车循迹、摆杆调节和车球协同控制。

赛题要求小车沿环形黑色路线行驶，并让钢球保持在凹槽内指定位置。摆杆长度为 25 cm，视觉模块覆盖整个凹槽，用于显示和记录钢球运动。

## 目录

```text
车载平衡滚球运动控制系统/
├── 视觉Q1_MaixCamPro/       # MaixCam Vision 工程：钢球检测、标定、图传和 UART 回传
└── Q2-Q6_MSPM0主控/         # MSPM0G3507 固件：Q2 至 Q6 的控制和硬件接口
```

| 部分 | 硬件/环境 | 作用 |
|---|---|---|
| [视觉 Q1](车载平衡滚球运动控制系统/视觉Q1_MaixCamPro/) | MaixCam Pro、MaixCam Vision | YOLO 钢球检测、像素到厘米标定、卡尔曼滤波、稳定性判断、MJPEG 图传和串口发送。 |
| [Q2–Q6 主控](车载平衡滚球运动控制系统/Q2-Q6_MSPM0主控/) | TI MSPM0G3507 | 循迹、钢球位置闭环、静态/动态车球控制、任意起点目标保持。 |

## 视觉与主控通信

视觉端使用 `UART1`，主控使用 `UART3`；两端配置均为 115200 baud、8N1。通信帧为 `AA 55 01 type sequence length payload CRC16`，CRC 使用 Modbus CRC-16，低字节在前。视觉端以约 20 ms 的间隔发送 12 字节检测结果：位置、速度、时间戳、稳定标志、置信度和像素中心。主控端已按相同协议解析并校验该帧。

接线：MaixCam Pro `A19 (UART1_TX)` 接 MSPM0 `PA25 (UART3_RX)`；MaixCam Pro `A18 (UART1_RX)` 可接 MSPM0 `PA26 (UART3_TX)`；两端必须共地，且均使用 3.3 V TTL 电平。

## 演示视频

四段整机演示视频位于 [media/demos](media/demos/)：

- [Demo 01](media/demos/demo-01.mp4)
- [Demo 02](media/demos/demo-02.mp4)
- [Demo 03](media/demos/demo-03.mp4)
- [Demo 04](media/demos/demo-04.mp4)

## 使用说明

请分别阅读两个子目录中的 README：视觉工程需要通过 MaixCam Vision 打开；主控工程的构建、烧录、按键映射和硬件说明均在 Q2–Q6 目录中。视觉工程中的 Wi-Fi 配置已留空，若需要 MJPEG 图传，请仅在自己设备上的 `main.py` 中填写网络信息，切勿将凭据提交到公开仓库。

## 赛题来源

本仓库说明依据《2026 年全国大学生电子设计竞赛区赛（TI 杯）暨模拟电子系统设计专题赛选拔赛：车载平衡滚球运动控制系统（H 题）》整理。
