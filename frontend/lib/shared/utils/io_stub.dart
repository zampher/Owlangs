// Stub file for dart:io on web platform
// This file is used when dart:io is not available (web platform)
// It provides empty implementations to avoid compilation errors

// This file should only be imported on web platform
// On non-web platforms, dart:io will be used instead

/// Stub for File class on web
class File {
  File([this.path = '']);
  final String path;
  Future<void> writeAsBytes(List<int> bytes, {bool flush = false}) {
    throw UnsupportedError('File.writeAsBytes is not supported on web');
  }

  Future<bool> exists() async => false;
  Future<List<int>> readAsBytes() async => <int>[];
  FileStat statSync() {
    throw UnsupportedError('File.statSync is not supported on web');
  }
  Future<FileStat> stat() async {
    throw UnsupportedError('File.stat is not supported on web');
  }
}

/// Stub for FileStat class on web
class FileStat {
  
  FileStat({
    required this.mode,
    required this.size,
    required this.modified,
    required this.accessed,
    required this.changed,
  });
  final int mode;
  final int size;
  final DateTime modified;
  final DateTime accessed;
  final DateTime changed;
}

/// Stub for Directory class on web
class Directory {
  Directory([this.path = '']);
  final String path;
  Stream<dynamic> list({bool recursive = false}) async* {
    throw UnsupportedError('Directory.list is not supported on web');
  }
  List<dynamic> listSync({bool recursive = false}) {
    throw UnsupportedError('Directory.listSync is not supported on web');
  }
  Future<bool> exists() async => false;
}

/// Stub for Process class on web
class Process {
  static Future<Process> start(String executable, List<String> arguments, {
    String? workingDirectory,
    bool runInShell = false,
  }) async {
    throw UnsupportedError('Process.start is not supported on web');
  }
  
  static Future<ProcessResult> run(String executable, List<String> arguments, {
    String? workingDirectory,
    bool runInShell = false,
  }) async {
    throw UnsupportedError('Process.run is not supported on web');
  }
  
  Future<int> get exitCode async => 0;
  void kill([ProcessSignal? signal]) {
    throw UnsupportedError('Process.kill is not supported on web');
  }
  Stream<List<int>> get stdout => throw UnsupportedError('Process.stdout is not supported on web');
  Stream<List<int>> get stderr => throw UnsupportedError('Process.stderr is not supported on web');
}

/// Stub for ProcessResult class on web
class ProcessResult {
  
  ProcessResult({
    required this.exitCode,
    required this.stdout,
    required this.stderr,
  });
  final int exitCode;
  final String stdout;
  final String stderr;
}

/// Stub for Platform class on web
class Platform {
  static bool get isWindows => false;
  static bool get isLinux => false;
  static bool get isMacOS => false;
  static Uri get script => Uri();
}

/// Stub for ProcessSignal class on web
class ProcessSignal {
  static ProcessSignal get sigint =>
      throw UnsupportedError('ProcessSignal is not supported on web');
  static ProcessSignal get sigterm =>
      throw UnsupportedError('ProcessSignal is not supported on web');
  static ProcessSignal get sigkill =>
      throw UnsupportedError('ProcessSignal is not supported on web');
  Stream<ProcessSignal> watch() {
    throw UnsupportedError('ProcessSignal.watch is not supported on web');
  }
}

/// Stub for exit function on web
Never exit(int code) {
  throw UnsupportedError('exit is not supported on web');
}

/// Stub for stdout and stderr on web
class Stdout {
  Stream<List<int>> get stdout => throw UnsupportedError('stdout is not supported on web');
  Stream<List<int>> get stderr => throw UnsupportedError('stderr is not supported on web');
}

/// Stub for utf8 on web
class Utf8 {
  static const Utf8Decoder decoder = Utf8Decoder();
}

class Utf8Decoder {
  const Utf8Decoder();
  String convert(List<int> bytes) => String.fromCharCodes(bytes);
  Stream<String> bind(Stream<List<int>> stream) => stream.map(convert);
}
