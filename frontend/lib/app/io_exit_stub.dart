// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// Stub for dart:io exit on web. Not called on web (close interceptor is desktop-only).
library;

void exit(int code) {
  throw UnsupportedError('exit() not available on web');
}
