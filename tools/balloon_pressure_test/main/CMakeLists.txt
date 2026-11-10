idf_component_register(
    SRCS "main.c" "interlock.c" "ms5611.c"
    INCLUDE_DIRS "."
    REQUIRES esp_driver_i2c esp_timer
)
