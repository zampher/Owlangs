#include "utils.h"

#include <flutter_windows.h>
#include <io.h>
#include <stdio.h>
#include <wchar.h>
#include <windows.h>

#include <iostream>

// Maximum length for UTF-16 string when converting to UTF-8 (CJK path safety, avoid buffer over-read)
#ifndef UNICODE_STRING_MAX_CHARS
#define UNICODE_STRING_MAX_CHARS 32767
#endif

void CreateAndAttachConsole() {
  if (::AllocConsole()) {
    FILE *unused;
    if (freopen_s(&unused, "CONOUT$", "w", stdout)) {
      _dup2(_fileno(stdout), 1);
    }
    if (freopen_s(&unused, "CONOUT$", "w", stderr)) {
      _dup2(_fileno(stdout), 2);
    }
    std::ios::sync_with_stdio();
    FlutterDesktopResyncOutputStreams();
  }
}

std::vector<std::string> GetCommandLineArguments() {
  // Convert the UTF-16 command line arguments to UTF-8 for the Engine to use.
  int argc;
  wchar_t** argv = ::CommandLineToArgvW(::GetCommandLineW(), &argc);
  if (argv == nullptr) {
    return std::vector<std::string>();
  }

  std::vector<std::string> command_line_arguments;

  // Skip the first argument as it's the binary name.
  for (int i = 1; i < argc; i++) {
    command_line_arguments.push_back(Utf8FromUtf16(argv[i]));
  }

  ::LocalFree(argv);

  return command_line_arguments;
}

// Bounded length for UTF-16 string (avoids buffer over-read with CJK paths, CWE-126)
static size_t BoundedWcslen(const wchar_t* str, size_t max_chars) {
  if (str == nullptr) return 0;
  size_t n = 0;
  while (n < max_chars && str[n] != L'\0') n++;
  return n;
}

std::string Utf8FromUtf16(const wchar_t* utf16_string) {
  if (utf16_string == nullptr) {
    return std::string();
  }
  const size_t input_len = BoundedWcslen(utf16_string, UNICODE_STRING_MAX_CHARS);
  if (input_len == 0) {
    return std::string();
  }
  const int input_length = static_cast<int>(input_len);
  const int target_length = ::WideCharToMultiByte(
      CP_UTF8, WC_ERR_INVALID_CHARS, utf16_string, input_length,
      nullptr, 0, nullptr, nullptr);
  std::string utf8_string;
  if (target_length <= 0 || static_cast<size_t>(target_length) > utf8_string.max_size()) {
    return utf8_string;
  }
  utf8_string.resize(static_cast<size_t>(target_length));
  const int converted_length = ::WideCharToMultiByte(
      CP_UTF8, WC_ERR_INVALID_CHARS, utf16_string, input_length,
      utf8_string.data(), target_length, nullptr, nullptr);
  if (converted_length <= 0) {
    return std::string();
  }
  return utf8_string;
}
