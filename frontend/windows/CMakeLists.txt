# Project-level configuration.
# Use min...max to satisfy CMake deprecation (compatibility with CMake < 3.10 removed)
cmake_minimum_required(VERSION 3.14...3.30)
project(owlangs LANGUAGES CXX)

# Pdfium for pdfx plugin: prefer local 3rdParty tarball (tools/download_pdfium.ps1).
# Pre-extract so the plugin skips its download step (avoids ExternalProject/file:///tar issues on Windows).
# On Windows prefer 7z for extraction (more reliable than cmake -E tar).
set(PDFIUM_VERSION "7651" CACHE STRING "pdfium for pdfx (bblanchon/pdfium-binaries)" FORCE)
set(PDFIUM_LOCAL "${CMAKE_CURRENT_SOURCE_DIR}/../../3rdParty/windows/pdfium-win-x64-${PDFIUM_VERSION}.tgz")
set(PDFIUM_EXTRACT_TO "${CMAKE_BINARY_DIR}/pdfium-extract")
if(EXISTS "${PDFIUM_LOCAL}")
  set(_pdfium_done "${PDFIUM_EXTRACT_TO}/.done")
  if(NOT EXISTS "${_pdfium_done}")
    file(MAKE_DIRECTORY "${PDFIUM_EXTRACT_TO}")
    set(_pdfium_extract_ok 0)
    if(WIN32)
      # 7-Zip typical path: C:\Program Files\7-Zip. ProgramFiles(x86) breaks CMake parsing so not used.
set(_pdfium_7z_paths "C:/Program Files/7-Zip" "$ENV{ProgramFiles}/7-Zip")
find_program(PDFIUM_7Z NAMES 7z 7z.exe PATHS ${_pdfium_7z_paths} ENV PATH)
      if(PDFIUM_7Z)
        execute_process(COMMAND "${PDFIUM_7Z}" x "${PDFIUM_LOCAL}" "-o${PDFIUM_EXTRACT_TO}" -y
          RESULT_VARIABLE _pdfium_7z OUTPUT_QUIET ERROR_QUIET)
        if(_pdfium_7z EQUAL 0)
          # .tgz may extract to a single .tar; extract that too
          file(GLOB _pdfium_after_first "${PDFIUM_EXTRACT_TO}/*")
          list(LENGTH _pdfium_after_first _naf)
          if(_naf EQUAL 1)
            list(GET _pdfium_after_first 0 _first_file)
            if(_first_file MATCHES "\\.tar$")
              execute_process(COMMAND "${PDFIUM_7Z}" x "${_first_file}" "-o${PDFIUM_EXTRACT_TO}" -y
                RESULT_VARIABLE _pdfium_7z2 OUTPUT_QUIET ERROR_QUIET)
              if(_pdfium_7z2 EQUAL 0)
                file(REMOVE "${_first_file}")
              endif()
            endif()
          endif()
          set(_pdfium_extract_ok 1)
          message(STATUS "Pdfium: extracted with 7z")
        endif()
      endif()
    endif()
    if(NOT _pdfium_extract_ok)
      execute_process(COMMAND ${CMAKE_COMMAND} -E tar xfz "${PDFIUM_LOCAL}" WORKING_DIRECTORY "${PDFIUM_EXTRACT_TO}" RESULT_VARIABLE _pdfium_tar)
      if(_pdfium_tar EQUAL 0)
        set(_pdfium_extract_ok 1)
      endif()
    endif()
    if(_pdfium_extract_ok)
      file(WRITE "${_pdfium_done}" "")
    endif()
  endif()
  file(GLOB _pdfium_dirs "${PDFIUM_EXTRACT_TO}/*")
  list(LENGTH _pdfium_dirs _n)
  if(_n EQUAL 1)
    list(GET _pdfium_dirs 0 _one)
    if(IS_DIRECTORY "${_one}" AND EXISTS "${_one}/PDFiumConfig.cmake")
      file(REAL_PATH "${_one}" PDFIUM_SOURCE_DIR_ABS)
      set(PDFIUM_SOURCE_DIR "${PDFIUM_SOURCE_DIR_ABS}" CACHE PATH "Pre-extracted pdfium for pdfx" FORCE)
      message(STATUS "Pdfium: local (pre-extracted)")
    endif()
  endif()
  if(NOT DEFINED PDFIUM_SOURCE_DIR AND EXISTS "${PDFIUM_EXTRACT_TO}/PDFiumConfig.cmake")
    file(REAL_PATH "${PDFIUM_EXTRACT_TO}" PDFIUM_SOURCE_DIR_ABS)
    set(PDFIUM_SOURCE_DIR "${PDFIUM_SOURCE_DIR_ABS}" CACHE PATH "Pre-extracted pdfium for pdfx" FORCE)
    message(STATUS "Pdfium: local (pre-extracted)")
  endif()
  if(NOT DEFINED PDFIUM_SOURCE_DIR)
    set(PDFIUM_URL "https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/${PDFIUM_VERSION}/pdfium-win-x64.tgz" CACHE STRING "" FORCE)
  endif()
else()
  set(PDFIUM_URL "https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/${PDFIUM_VERSION}/pdfium-win-x64.tgz" CACHE STRING "" FORCE)
endif()

# The name of the executable created for the application. Change this to change
# the on-disk name of your application.
set(BINARY_NAME "owlangs")

# Explicitly opt in to modern CMake behaviors to avoid warnings with recent
# versions of CMake.
cmake_policy(VERSION 3.14...3.25)

# Define build configuration option.
get_property(IS_MULTICONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
if(IS_MULTICONFIG)
  set(CMAKE_CONFIGURATION_TYPES "Debug;Profile;Release"
    CACHE STRING "" FORCE)
else()
  if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE "Debug" CACHE
      STRING "Flutter build mode" FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS
      "Debug" "Profile" "Release")
  endif()
endif()
# Define settings for the Profile build mode.
set(CMAKE_EXE_LINKER_FLAGS_PROFILE "${CMAKE_EXE_LINKER_FLAGS_RELEASE}")
set(CMAKE_SHARED_LINKER_FLAGS_PROFILE "${CMAKE_SHARED_LINKER_FLAGS_RELEASE}")
set(CMAKE_C_FLAGS_PROFILE "${CMAKE_C_FLAGS_RELEASE}")
set(CMAKE_CXX_FLAGS_PROFILE "${CMAKE_CXX_FLAGS_RELEASE}")

# Use Unicode for all projects.
add_definitions(-DUNICODE -D_UNICODE)

# Compilation settings that should be applied to most targets.
#
# Be cautious about adding new options here, as plugins use this function by
# default. In most cases, you should add new options to specific targets instead
# of modifying this function.
function(APPLY_STANDARD_SETTINGS TARGET)
  target_compile_features(${TARGET} PUBLIC cxx_std_17)
  target_compile_options(${TARGET} PRIVATE /W4 /WX /wd"4100")
  target_compile_options(${TARGET} PRIVATE /EHsc)
  target_compile_definitions(${TARGET} PRIVATE "_HAS_EXCEPTIONS=0")
  target_compile_definitions(${TARGET} PRIVATE "$<$<CONFIG:Debug>:_DEBUG>")
endfunction()

# Flutter library and tool build rules.
set(FLUTTER_MANAGED_DIR "${CMAKE_CURRENT_SOURCE_DIR}/flutter")
add_subdirectory(${FLUTTER_MANAGED_DIR})

# Application build; see runner/CMakeLists.txt.
add_subdirectory("runner")


# Generated plugin build rules, which manage building the plugins and adding
# them to the application.
include(flutter/generated_plugins.cmake)


# === Installation ===
# Support files are copied into place next to the executable, so that it can
# run in place. This is done instead of making a separate bundle (as on Linux)
# so that building and running from within Visual Studio will work.
set(BUILD_BUNDLE_DIR "$<TARGET_FILE_DIR:${BINARY_NAME}>")
# Always install to build output dir (next to exe). Avoids "Permission denied"
# when INSTALL runs with default prefix (e.g. C:/Program Files/owlangs).
set(CMAKE_INSTALL_PREFIX "${BUILD_BUNDLE_DIR}" CACHE PATH "Install next to executable" FORCE)
set(CMAKE_VS_INCLUDE_INSTALL_TO_DEFAULT_BUILD 1)

set(INSTALL_BUNDLE_DATA_DIR "${CMAKE_INSTALL_PREFIX}/data")
set(INSTALL_BUNDLE_LIB_DIR "${CMAKE_INSTALL_PREFIX}")

install(TARGETS ${BINARY_NAME} RUNTIME DESTINATION "${CMAKE_INSTALL_PREFIX}"
  COMPONENT Runtime)

install(FILES "${FLUTTER_ICU_DATA_FILE}" DESTINATION "${INSTALL_BUNDLE_DATA_DIR}"
  COMPONENT Runtime)

install(FILES "${FLUTTER_LIBRARY}" DESTINATION "${INSTALL_BUNDLE_LIB_DIR}"
  COMPONENT Runtime)

if(PLUGIN_BUNDLED_LIBRARIES)
  install(FILES "${PLUGIN_BUNDLED_LIBRARIES}"
    DESTINATION "${INSTALL_BUNDLE_LIB_DIR}"
    COMPONENT Runtime)
endif()

# Copy the native assets provided by the build.dart from all packages.
# Install only if the directory exists at install time (avoids INSTALL step failure when absent).
set(NATIVE_ASSETS_DIR "${PROJECT_BUILD_DIR}native_assets/windows/")
install(CODE "
  if(EXISTS \"${NATIVE_ASSETS_DIR}\")
    file(GLOB _native_entries \"${NATIVE_ASSETS_DIR}*\")
    foreach(_e \${_native_entries})
      file(COPY \"\${_e}\" DESTINATION \"${INSTALL_BUNDLE_LIB_DIR}\")
    endforeach()
  endif()
  " COMPONENT Runtime)

# Fully re-copy the assets directory on each build to avoid having stale files
# from a previous install. Use CODE so missing source dir does not fail INSTALL.
set(FLUTTER_ASSET_DIR_NAME "flutter_assets")
set(FLUTTER_ASSET_SOURCE "${PROJECT_BUILD_DIR}/${FLUTTER_ASSET_DIR_NAME}")
set(FLUTTER_ASSET_DEST "${INSTALL_BUNDLE_DATA_DIR}/${FLUTTER_ASSET_DIR_NAME}")
install(CODE "
  if(EXISTS \"${FLUTTER_ASSET_DEST}\")
    file(REMOVE_RECURSE \"${FLUTTER_ASSET_DEST}\")
  endif()
  if(EXISTS \"${FLUTTER_ASSET_SOURCE}\")
    file(COPY \"${FLUTTER_ASSET_SOURCE}\" DESTINATION \"${INSTALL_BUNDLE_DATA_DIR}\")
  endif()
  " COMPONENT Runtime)

# Install the AOT library on non-Debug builds only.
install(FILES "${AOT_LIBRARY}" DESTINATION "${INSTALL_BUNDLE_DATA_DIR}"
  CONFIGURATIONS Profile;Release
  COMPONENT Runtime)
