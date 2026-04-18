#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

#include "flutter_window.h"
#include "utils.h"

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  // Always create console for logging (even in release mode)
  // This allows Launcher to capture stdout/stderr for log file storage
  if (!::AttachConsole(ATTACH_PARENT_PROCESS)) {
    // Try to attach to parent console first (if launched from Launcher)
    // If that fails, create a new console (for standalone debugging)
    if (::IsDebuggerPresent()) {
      CreateAndAttachConsole();
    } else {
      // In release mode, still create console but hide it
      // This allows stdout/stderr redirection to work
      CreateAndAttachConsole();
      // Hide the console window (logs will still be captured by Launcher)
      ::ShowWindow(::GetConsoleWindow(), SW_HIDE);
    }
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  std::vector<std::string> command_line_arguments =
      GetCommandLineArguments();

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));

  FlutterWindow window(project);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(1280, 720);
  if (!window.Create(L"Owlangs", origin, size)) {
    return EXIT_FAILURE;
  }
  window.SetQuitOnClose(true);
  
  // Maximize window to fullscreen on startup
  // Note: Window will be shown after Flutter first frame is ready
  // Maximize will be called when window is actually shown

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  // Force process exit in case Flutter engine or other threads are still running
  ::ExitProcess(0);
  return EXIT_SUCCESS;
}
