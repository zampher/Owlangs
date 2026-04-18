import 'dart:async';
import 'dart:io' if (dart.library.html) '../utils/io_stub.dart' as io;

import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;

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
      // 暂时跳过后端启动，测试应用是否能正常启动
      print('🚀 [BACKEND] Skipping backend startup for testing');
      
      // 模拟后端启动成功
      Future.delayed(const Duration(seconds: 1), () {
        _startupCompleter!.complete(true);
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