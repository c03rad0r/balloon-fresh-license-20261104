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
    -DLR2021_PKT_BYTE1=0x7D
    # Fixed-slot turn-taking is retained as an experiment. It has not beaten
    # the CSMA-only path in delivery tests, so it stays disabled by default.
    -DLR2021_ENABLE_TDMA=0)

if(IDF_TARGET STREQUAL "esp32c3")
    target_compile_options(${COMPONENT_LIB} PRIVATE -DLR2021_NICERF_C3=1)
endif()

# Opt-in throughput experiment only. The default remains the validated CR 3/4
# profile. Enable with: idf.py -DLR2021_FLRC_CR_NONE=ON build
option(LR2021_FLRC_CR_NONE
       "Use uncoded FLRC (CR_NONE/BT_1); experimental, not yet gate-qualified"
       OFF)
if(LR2021_FLRC_CR_NONE)
    target_compile_options(${COMPONENT_LIB} PRIVATE -DLR2021_CR_SHAPE=0x27)
endif()
