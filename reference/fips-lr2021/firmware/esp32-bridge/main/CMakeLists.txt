set(LR2021_DIR "../../../../../tracker/firmware/components/lr2021_transport")

idf_component_register(
    SRCS "main.cpp"
         "${LR2021_DIR}/src/lr2021_spi.cpp"
         "${LR2021_DIR}/src/esp_idf_lr2021_radio.cpp"
    INCLUDE_DIRS "."
                 "${LR2021_DIR}/include"
                 "../../rp2040-bridge/src"
    REQUIRES driver esp_timer)

# Match the E80/RP2040 family's FLRC framing so the two can interoperate.
target_compile_options(${COMPONENT_LIB} PRIVATE -DLR2021_PKT_BYTE0=0x0C -DLR2021_FORCE_CRC_OFF=1)
