set(LR2021_DIR "../../../../../tracker/firmware/components/lr2021_transport")

idf_component_register(
    SRCS "main.cpp"
         "${LR2021_DIR}/src/lr2021_spi.cpp"
         "${LR2021_DIR}/src/esp_idf_lr2021_radio.cpp"
    INCLUDE_DIRS "."
                 "${LR2021_DIR}/include"
                 "../../rp2040-bridge/src"
    REQUIRES driver esp_timer)

# Match the E80-900MBL-02 sub-GHz FLRC implementation in the vendored Semtech
# driver and the already-flashed E80/RP2040 bridges. Keep the ordinary shared
# driver defaults for the unrelated 2.4 GHz NiceRF carrier.
target_compile_options(${COMPONENT_LIB} PRIVATE
    -DLR2021_E80_COMPAT=1
    -DLR2021_PKT_BYTE0=0x1E
    -DLR2021_PKT_BYTE1=0x7D)
