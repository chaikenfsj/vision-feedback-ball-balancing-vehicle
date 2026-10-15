# Q2–Q6 主控固件 — MSPM0G3507

本目录是车载平衡滚球运动控制系统的 MSPM0G3507 主控工程，覆盖 Q2 至 Q6 的控制路径。它接收视觉 Q1 的 UART 数据，驱动底盘和摆杆执行机构，并完成循迹、钢球位置闭环、静态/动态车球控制和任意位置目标保持。

## 代码结构

- `user/app/q3/`：钢球状态估计、位置控制和 Q3 流程。
- `user/app/q4/`：Q4 静态路线和 Q5 动态车球控制。
- `user/app/q6/`：任意初始位置的目标捕获与闭环控制。
- `user/bsp/`：底盘、传感器、显示与板级服务。
- `user/code/vision_link.*`：视觉帧解析、CRC 校验和样本有效性管理。
- `empty.syscfg`：SysConfig 外设配置；生成的 `ti_msp_dl_config.c/.h` 已随工程保存，不应手改。

## 视觉串口

主控将 `UART3` 分配给视觉模块：`PA25` 为 RX、`PA26` 为 TX，参数为 115200 baud、8N1。接收端支持 `AA 55 01` 帧头、Modbus CRC-16 和 12 字节视觉检测 payload；协议定义在 `user/code/vision_link.h`。对应 MaixCam Pro 工程位于同级的 `../视觉Q1_MaixCamPro/`。

## 构建

在本目录安装 CMake 3.22 或更高版本、Ninja 和 Arm GNU Toolchain。按本机工具链路径设置环境变量后运行：

```powershell
$env:ARM_GCC_ROOT = "C:\Toolchains\arm-gnu-toolchain"
$env:NINJA_ROOT = "C:\Tools\ninja"
cmake --preset debug-armgcc
cmake --build --preset build-debug
```

如需使用 VS Code 的 SysConfig 辅助任务，请将 `.env.example` 复制为未提交的 `.env`，并填写 `MSPM0_SDK_ROOT`、`SYSCONFIG_ROOT` 等本机路径。测试说明、硬件连接和控制路径请查看 `docs/`。

## 安全提示

固件接到实物后可能立即驱动电机。调试时应支撑好小车、清空摆杆和车轮附近区域，并准备实体断电开关。软件检查不等同于实车验证。
