set(LR2021_DIR "../../../../../tracker/firmware/components/lr2021_transport")

idf_component_register(
    SRCS "main.cpp"
         "${LR2021_DIR}/src/lr2021_spi.cpp"
         "${LR2021_DIR}/src/esp_idf_lr2021_radio.cpp"
    INCLUDE_DIRS "."
                 "${LR2021_DIR}/include"
                 "../../rp2040-bridge/src"
    REQUIRES driver esp_timer)

# Keep the validated E80 air-format bytes for both carriers, but select their
# electrical RF/IRQ implementation from the MCU/board target. Do not use the
# ESP32-C3 NiceRF carrier as an E80-900MBL-02 radio.
target_compile_options(${COMPONENT_LIB} PRIVATE
    -DLR2021_E80_COMPAT=1
    -DLR2021_PKT_BYTE0=0x1E
    -DLR2021_PKT_BYTE1=0x7D)

if(IDF_TARGET STREQUAL "esp32c3")
    target_compile_options(${COMPONENT_LIB} PRIVATE -DLR2021_NICERF_C3=1)
endif()
