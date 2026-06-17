// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

const Set<String> kMineruLayoutImageExtensions = <String>{
  'png',
  'jpg',
  'jpeg',
  'webp',
  'bmp',
  'gif',
  'tif',
  'tiff',
};

bool isMineruLayoutImageFileName(String? fileName) {
  if (fileName == null || fileName.isEmpty || !fileName.contains('.')) {
    return false;
  }
  final String ext = fileName.toLowerCase().split('.').last;
  return kMineruLayoutImageExtensions.contains(ext);
}

String? originalImageDownloadExtension(String? fileName) {
  if (!isMineruLayoutImageFileName(fileName)) {
    return null;
  }
  return fileName!.toLowerCase().split('.').last;
}

bool isOriginalImageDownloadFormat(String formatKey) {
  return kMineruLayoutImageExtensions.contains(formatKey.toLowerCase());
}
