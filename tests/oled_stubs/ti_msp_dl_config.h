#ifndef OLED_TEST_TI_CONFIG_H
#define OLED_TEST_TI_CONFIG_H
#include <stdint.h>
#define OLED_INST 0
#define DL_I2C_CONTROLLER_STATUS_IDLE 1U
#define DL_I2C_CONTROLLER_DIRECTION_TX 0U
uint32_t DL_I2C_getControllerStatus(int instance);
void DL_I2C_resetControllerTransfer(int instance);
void DL_I2C_fillControllerTXFIFO(int instance, const uint8_t *data, uint32_t length);
void DL_I2C_startControllerTransfer(int instance,
                                    uint32_t address,
                                    uint32_t direction,
                                    uint32_t length);
#endif
