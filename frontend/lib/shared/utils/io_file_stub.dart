// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert' show Encoding, utf8;

/// Stubbed File implementation for platforms where dart:io is unavailable (e.g. Web).
/// All operations throw UnsupportedError since file operations are not available on web.
/// Accepts path so that call sites can use File(path) on both web and desktop.
class File {
  File([this.path = '']);

  final String path;

  Future<bool> exists() async => false;

  Future<List<int>> readAsBytes() async => <int>[];

  Future<String> readAsString({Encoding encoding = utf8}) async {
    throw UnsupportedError('File.readAsString is not supported on web');
  }

  Future<void> writeAsString(
    String contents, {
    Encoding encoding = utf8,
    FileMode mode = FileMode.write,
    bool flush = false,
  }) async {
    throw UnsupportedError('File.writeAsString is not supported on web');
  }

  Directory get parent {
    throw UnsupportedError('File.parent is not supported on web');
  }
}

/// Stub for Directory class
class Directory {
  Directory();

  Future<Directory> create({bool recursive = false}) async {
    throw UnsupportedError('Directory.create is not supported on web');
  }
}

/// Stub for FileMode enum
enum FileMode {
  read,
  write,
  append,
  writeOnly,
  writeOnlyAppend,
}
