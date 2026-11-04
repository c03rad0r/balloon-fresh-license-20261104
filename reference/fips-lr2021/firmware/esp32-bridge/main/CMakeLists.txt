idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
                 "../../../../../firmware/e80-bypass/common"
                 "../../rp2040-bridge/src"
    REQUIRES driver esp_timer)

# e80_pinmap.h declares pins as plain ints; ESP-IDF GPIO APIs take gpio_num_t.
target_compile_options(${COMPONENT_LIB} PRIVATE -fpermissive)

# Per-carrier radio settings. The NiceRF carriers need the alternate init
# sequence, DIO9 and FRF encoding; the E80 modules use the demo sequence, DIO8
# and plain 4-byte Hz.
if(IDF_TARGET STREQUAL "esp32c3")
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -DE80_BRIDGE_CARRIER_INIT=1 -DE80_RADIO_IRQ_DIO=9 -DE80_RFREQ_FRF=1 -DE80_SPI_HZ=20000000)
else()
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -DE80_BRIDGE_CARRIER_INIT=0 -DE80_RADIO_IRQ_DIO=8 -DE80_RFREQ_FRF=0 -DE80_SPI_HZ=4000000)
endif()
