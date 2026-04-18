// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

// Stub file for Web platform
// This file provides empty stubs for dart:io classes that are not available on Web

import 'dart:async';

/// Stub class for HttpClient (not available on Web)
class HttpClient {
  Future<HttpClientRequest> getUrl(Uri url) {
    throw UnimplementedError('HttpClient is not available on Web platform');
  }

  void close({bool force = false}) {
    // Stub implementation
  }
}

/// Stub class for HttpClientRequest (not available on Web)
class HttpClientRequest {
  Future<HttpClientResponse> close() {
    throw UnimplementedError(
      'HttpClientRequest is not available on Web platform',
    );
  }
}

/// Stub class for HttpClientResponse (not available on Web)
class HttpClientResponse {
  int get statusCode => 0;
}
