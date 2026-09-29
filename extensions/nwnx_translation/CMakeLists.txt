cmake_minimum_required(VERSION 3.16)
project(RoleWeaverTranslation LANGUAGES CXX)

# Build against the SAME unified source and Core binary used by the server.
# No NWNX source tree or existing plugin is modified by this build.
set(NWNX_SOURCE "" CACHE PATH "Matching nwnxee/unified checkout")
set(NWNX_CORE "" CACHE FILEPATH "Installed NWNX_Core.so")
option(RW_TRANSLATION_TESTS "Include isolated-server test entry points" OFF)
if(NOT EXISTS "${NWNX_SOURCE}/NWNXLib/nwnx.hpp" OR NOT EXISTS "${NWNX_CORE}")
  message(FATAL_ERROR "Set NWNX_SOURCE and NWNX_CORE to your matching NWNX installation")
endif()
add_library(RWTranslation MODULE Translation.cpp)
target_compile_features(RWTranslation PRIVATE cxx_std_17)
target_compile_options(RWTranslation PRIVATE -Wall -Wextra -Wno-pmf-conversions -fno-strict-aliasing)
target_include_directories(RWTranslation PRIVATE "${NWNX_SOURCE}/NWNXLib" "${NWNX_SOURCE}/NWNXLib/API")
target_compile_definitions(RWTranslation PRIVATE PLUGIN_NAME="NWNX_RWTranslation" CMAKE_SOURCE_DIR_LENGTH=0
  NWNX_TARGET_NWN_BUILD=8193 NWNX_TARGET_NWN_BUILD_REVISION=37 NWNX_TARGET_NWN_BUILD_POSTFIX=17)
target_link_libraries(RWTranslation PRIVATE "${NWNX_CORE}")
set_target_properties(RWTranslation PROPERTIES PREFIX "NWNX_" BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "$ORIGIN")
if(RW_TRANSLATION_TESTS)
  target_compile_definitions(RWTranslation PRIVATE RW_TRANSLATION_TESTS=1)
endif()
