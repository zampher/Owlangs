// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import '../../app/app_config.dart';
import '../services/config_service.dart';

/// Resolve a backend-relative path (e.g. `/service/task-image/...`) to a
/// loadable URL for [Image.network] / HTML `<img src>`.
String resolveBackendResourceUrl(String pathOrUrl) {
  if (pathOrUrl.isEmpty) {
    return pathOrUrl;
  }
  if (pathOrUrl.startsWith('http://') ||
      pathOrUrl.startsWith('https://') ||
      pathOrUrl.startsWith('data:') ||
      pathOrUrl.startsWith('blob:')) {
    return pathOrUrl;
  }
  final String base = AppConfig.baseUrl;
  if (base.isEmpty) {
    return pathOrUrl.startsWith('/') ? pathOrUrl : '/$pathOrUrl';
  }
  if (pathOrUrl.startsWith('/')) {
    return '$base$pathOrUrl';
  }
  return '$base/$pathOrUrl';
}

/// Auth / desktop headers for [Image.network] when loading task images.
Map<String, String> backendImageRequestHeaders() {
  final String? auth = ConfigService().authorizationHeader;
  return <String, String>{
    if (auth != null && auth.isNotEmpty) 'Authorization': auth,
    ...ConfigService.desktopBackendHeaders,
  };
}

/// Prefer URL ref; fall back to legacy base64 data URI.
String? imageSrcFromEntry(Map<String, String> imageData) {
  final String url = (imageData['url'] ?? '').trim();
  if (url.isNotEmpty) {
    return resolveBackendResourceUrl(url);
  }
  final String data = (imageData['data'] ?? '').trim();
  if (data.startsWith('data:image/')) {
    return data;
  }
  return null;
}
