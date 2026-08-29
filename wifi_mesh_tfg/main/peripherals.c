#include "peripherals.h"
#include "driver/gpio.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "PERIPHERALS";
#define BUTTON_PIN          GPIO_NUM_16


static void button_ps_task(void *arg) {
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = (1ULL << BUTTON_PIN),
        .pull_down_en = 0,
        .pull_up_en = 1
    };
    gpio_config(&io_conf);
    
    int current_ps_mode = 0; 
    bool last_state = true;
    
    while (true) {
        bool state = gpio_get_level(BUTTON_PIN);
        if (state == 0 && last_state == 1) {
            vTaskDelay(pdMS_TO_TICKS(50)); // Debounce
            if (gpio_get_level(BUTTON_PIN) == 0) {
                 current_ps_mode = (current_ps_mode + 1) % 3;
                 wifi_ps_type_t ps_type = WIFI_PS_NONE;
                const char* mode_str = "";
                switch(current_ps_mode) {
                    case 0:
                         ps_type = WIFI_PS_NONE;
                         mode_str = "NONE (Máximo consumo, mínima latencia)";
                        break;
                    case 1:
                         ps_type = WIFI_PS_MIN_MODEM;
                         mode_str = "MIN_MODEM (Equilibrio)";
                        break;
                    case 2:
                         ps_type = WIFI_PS_MAX_MODEM;
                         mode_str = "MAX_MODEM (Mínimo consumo, máxima latencia)";
                        break;
                }
                esp_wifi_set_ps(ps_type);
                ESP_LOGW(TAG, "================================================");
                ESP_LOGW(TAG, " BOTÓN PULSADO: Power Save cambiado a: %s", mode_str);
                ESP_LOGW(TAG, "================================================");
                while(gpio_get_level(BUTTON_PIN) == 0) {
                    vTaskDelay(pdMS_TO_TICKS(10));
                }
            }
        }
        last_state = state;
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

uint8_t peripherals_get_ps_mode(void) {
    wifi_ps_type_t ps_type = WIFI_PS_NONE;
    if (esp_wifi_get_ps(&ps_type) == ESP_OK) {
        return (uint8_t)ps_type;
    }
    return 0;
}



void peripherals_start_button_task(void) {
    xTaskCreate(button_ps_task, "button_ps", 4096, NULL, 3, NULL);
    ESP_LOGI(TAG, "Tarea de gestión de botón Power Save iniciada en nodo hijo.");
}
