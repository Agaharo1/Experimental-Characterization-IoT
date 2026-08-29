#pragma once
#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

esp_err_t peripherals_init(void);
void peripherals_start_button_task(void);
uint8_t peripherals_get_ps_mode(void);