import 'dart:io' if (dart.library.html) '../utils/io_stub.dart' as io;
import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import 'package:path_provider/path_provider.dart';

class BackendManager {
  factory BackendManager() => _instance;

  BackendManager._internal();
  static final BackendManager _instance = BackendManager._internal();

  io.Process? _backendProcess;
  bool _isRunning = false;
  Completer<bool>? _startupCompleter;

  Future<bool> startBackend() async {
    if (kIsWeb) {
      // Web platform: no backend needed
      return true;
    }

    if (_isRunning) return true;
    if (_startupCompleter != null) return _startupCompleter!.future;

    _startupCompleter = Completer<bool>();

    try {
      String backendPath = 'backend/main.py';
      String? workingDirectory;
      bool usePython = true;

      // 尝试使用应用包内的后端（打包后的桌面版）
      if (!kDebugMode && io.Platform.isMacOS) {
        try {
          final appDir = await getApplicationSupportDirectory();
          final appBundlePath = appDir.path.split('/Library/Application Support/')[0];
          final backendDir = '$appBundlePath/Contents/Resources/backend';

          // 检查后端目录是否存在
          final backendDirExists = await io.Directory(backendDir).exists();
          if (!backendDirExists) {
            if (kDebugMode) {
              print('⚠️ [BACKEND] Backend directory not found: $backendDir');
            }
          } else {
            // 查找后端可执行文件
            final backendFiles = await io.Directory(backendDir).list().toList();
            String? bundledBackendPath;

            for (final file in backendFiles) {
              if (file is io.File && file.path.endsWith('-mac')) {
                bundledBackendPath = file.path;
                break;
              }
            }

            if (bundledBackendPath != null) {
              // 检查文件是否有执行权限
              final fileStat = await io.File(bundledBackendPath).stat();
              if (fileStat.mode & 0x100 != 0) {
                // 检查执行权限
                backendPath = bundledBackendPath;
                workingDirectory = backendDir;
                usePython = false; // 直接运行可执行文件，不需要 Python 解释器
                if (kDebugMode) {
                  print('🚀 [BACKEND] Using bundled backend: $bundledBackendPath');
                }
              } else {
                if (kDebugMode) {
                  print('⚠️ [BACKEND] Backend executable has no execute permission: $bundledBackendPath');
                }
              }
            } else {
              if (kDebugMode) {
                print('⚠️ [BACKEND] No bundled backend executable found in: $backendDir');
              }
            }
          }
        } catch (e) {
          if (kDebugMode) {
            print('⚠️ [BACKEND] Failed to get bundled backend: $e');
          }
        }
      }

      // 如果没有打包的后端，使用项目根目录的后端
      if (workingDirectory == null) {
        workingDirectory = io.Platform.script.toFilePath().split('frontend')[0];
        // 检查后端目录是否存在
        final backendDir = '${workingDirectory}backend';
        final backendDirExists = await io.Directory(backendDir).exists();
        if (!backendDirExists) {
          print('❌ [BACKEND] Backend directory not found: $backendDir');
          _startupCompleter?.complete(false);
          return false;
        }
      }

      if (kDebugMode) {
        if (usePython) {
          final String pythonExecutable = io.Platform.isWindows ? 'python.exe' : 'python3';
          print('🚀 [BACKEND] Starting backend with: $pythonExecutable $backendPath');
        } else {
          print('🚀 [BACKEND] Starting backend with: $backendPath');
        }
        print('🚀 [BACKEND] Working directory: $workingDirectory');
      }

      // 启动后端进程
      if (usePython) {
        final String pythonExecutable = io.Platform.isWindows ? 'python.exe' : 'python3';
        // 检查 Python 解释器是否存在
        try {
          final result = await io.Process.run(
            pythonExecutable,
            <String>['--version'],
            workingDirectory: workingDirectory,
          );
          if (result.exitCode != 0) {
            print('❌ [BACKEND] Python interpreter not found or not working');
            _startupCompleter?.complete(false);
            return false;
          }
        } catch (e) {
          print('❌ [BACKEND] Failed to check Python interpreter: $e');
          _startupCompleter?.complete(false);
          return false;
        }

        _backendProcess = await io.Process.start(
          pythonExecutable,
          <String>[backendPath],
          workingDirectory: workingDirectory,
          runInShell: true,
        );
      } else {
        // 直接运行可执行文件
        // 再次检查文件是否存在
        final backendFileExists = await io.File(backendPath).exists();
        if (!backendFileExists) {
          print('❌ [BACKEND] Backend executable not found: $backendPath');
          _startupCompleter?.complete(false);
          return false;
        }

        _backendProcess = await io.Process.start(
          backendPath,
          <String>[],
          workingDirectory: workingDirectory,
          runInShell: true,
        );
      }

      _isRunning = true;

      // 监听后端输出
      _backendProcess?.stdout.transform(utf8.decoder).listen((output) {
        if (kDebugMode) {
          print('📡 [BACKEND] $output');
        }
        // 检查后端是否启动成功
        if (output.contains('Uvicorn running on') && !_startupCompleter!.isCompleted) {
          _startupCompleter!.complete(true);
        }
      });

      // 监听后端错误
      _backendProcess?.stderr.transform(utf8.decoder).listen((error) {
        print('❌ [BACKEND] $error');
        if (!_startupCompleter!.isCompleted) {
          _startupCompleter!.complete(false);
        }
      });

      // 处理后端退出
      _backendProcess?.exitCode.then((code) {
        _isRunning = false;
        if (kDebugMode) {
          print('🚪 [BACKEND] Exited with code: $code');
        }
      });

      // 设置启动超时
      Future.delayed(const Duration(seconds: 10), () {
        if (!_startupCompleter!.isCompleted) {
          print('❌ [BACKEND] Startup timeout after 10 seconds');
          _startupCompleter!.complete(false);
        }
      });

      return _startupCompleter!.future;
    } catch (e) {
      print('❌ [BACKEND] Failed to start: $e');
      _startupCompleter?.complete(false);
      return false;
    }
  }

  Future<void> stopBackend() async {
    if (kIsWeb) {
      // Web platform: no backend to stop
      return;
    }

    if (!_isRunning || _backendProcess == null) return;

    try {
      if (kDebugMode) {
        print('🚪 [BACKEND] Stopping backend process');
      }

      // 尝试优雅停止
      _backendProcess?.kill();
      await _backendProcess?.exitCode.timeout(
        const Duration(seconds: 5),
        onTimeout: () {
          // 超时后强制终止
          _backendProcess?.kill(io.ProcessSignal.sigkill);
          return -1;
        },
      );

      _isRunning = false;
      if (kDebugMode) {
        print('✅ [BACKEND] Stopped successfully');
      }
    } catch (e) {
      print('❌ [BACKEND] Error stopping: $e');
    }
  }

  bool get isRunning => _isRunning;
}
