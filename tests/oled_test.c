#include <string.h>
#include "code/oled.h"

extern u8 OLED_GRAM[144][8];
unsigned checks, failures, first_failure_line;
unsigned failure_lines[32], failure_lines_count;
static uint8_t last_command;
static u8 snapshot[144][8];

#define CHECK(x)                                                                                   \
    do                                                                                             \
    {                                                                                              \
        ++checks;                                                                                  \
        if (!(x))                                                                                  \
        {                                                                                          \
            ++failures;                                                                            \
            if (!first_failure_line)                                                               \
                first_failure_line = __LINE__;                                                     \
            if (failure_lines_count < 32U)                                                         \
                failure_lines[failure_lines_count++] = __LINE__;                                   \
        }                                                                                          \
    } while (0)

uint32_t DL_I2C_getControllerStatus(int instance)
{
    (void)instance;
    return DL_I2C_CONTROLLER_STATUS_IDLE;
}
void DL_I2C_resetControllerTransfer(int instance)
{
    (void)instance;
}
void DL_I2C_fillControllerTXFIFO(int instance, const uint8_t *data, uint32_t length)
{
    (void)instance;
    if (length == 2U && data[0] == 0U)
        last_command = data[1];
}
void DL_I2C_startControllerTransfer(int instance,
                                    uint32_t address,
                                    uint32_t direction,
                                    uint32_t length)
{
    (void)instance;
    (void)address;
    (void)direction;
    (void)length;
}

int main(void)
{
    unsigned x, y;
    /* Exhaustively reject every out-of-display uint8_t coordinate. A y=64
     * write used to corrupt the next column; x>=144 could leave the buffer. */
    memset(OLED_GRAM, 0xA5, sizeof(OLED_GRAM));
    memcpy(snapshot, OLED_GRAM, sizeof(snapshot));
    for (x = 0; x < 256U; ++x)
        for (y = 0; y < 256U; ++y)
            if (x >= 128U || y >= 64U)
            {
                OLED_DrawPoint((u8)x, (u8)y);
                OLED_ClearPoint((u8)x, (u8)y);
            }
    CHECK(memcmp(snapshot, OLED_GRAM, sizeof(snapshot)) == 0);

    memset(OLED_GRAM, 0, sizeof(OLED_GRAM));
    OLED_DrawPoint(127U, 63U);
    CHECK(OLED_GRAM[127][7] == 0x80U);
    OLED_ClearPoint(127U, 63U);
    CHECK(OLED_GRAM[127][7] == 0U);
    memcpy(snapshot, OLED_GRAM, sizeof(snapshot));
    OLED_DrawLine(0U, 64U, 10U, 64U);
    OLED_DrawLine(128U, 0U, 128U, 10U);
    OLED_ShowChar(0U, 0U, 0U, 12U);
    OLED_ShowChar(0U, 0U, 255U, 12U);
    OLED_ShowString(0U, 64U, (u8 *)"OFF SCREEN", 12U);
    OLED_ShowString(0U, 0U, NULL, 12U);
    CHECK(memcmp(snapshot, OLED_GRAM, sizeof(snapshot)) == 0);

    /* Rendering beyond the last line must stop instead of wrapping y. */
    OLED_ShowString(120U, 60U, (u8 *)"ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZ", 12U);
    for (x = 0U; x < 144U; ++x)
        for (y = 0U; y < 8U; ++y)
            if (x < 120U || x >= 128U || y < 7U)
                CHECK(OLED_GRAM[x][y] == 0U);

    OLED_DisPlay_Off();
    CHECK(last_command == 0xAEU);
    OLED_DisPlay_On();
    CHECK(last_command == 0xAFU);
    return failures ? 1 : 0;
}
