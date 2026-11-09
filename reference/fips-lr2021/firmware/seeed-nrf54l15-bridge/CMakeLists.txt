cmake_minimum_required(VERSION 3.20.0)

set(KCONFIG_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/Kconfig)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(seeed_nrf54l15_bridge)

target_sources(app PRIVATE
  src/main.cpp
  src/bridge_core.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/../rp2040-bridge/src/bridge_protocol.h
)
target_include_directories(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src
  ${CMAKE_CURRENT_SOURCE_DIR}/../rp2040-bridge/src
)
