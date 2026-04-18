// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Check if a string is likely a base64-encoded image data URI
bool isBase64Image(String text) {
  if (text.isEmpty) return false;
  // Check for data URI pattern: data:image/...;base64,...
  if (text.startsWith('data:image/') && text.contains(';base64,')) {
    return true;
  }
  // Check if it's a long base64 string (likely image data)
  // Base64 strings are typically long and contain only base64 characters
  if (text.length > 100) {
    final base64Pattern = RegExp(r'^[A-Za-z0-9+/=\s]+$');
    if (base64Pattern.hasMatch(text.trim())) {
      // Additional check: base64 strings usually don't contain spaces in the middle
      // and have a high ratio of base64 characters
      final cleanText = text.replaceAll(RegExp(r'\s+'), '');
      if (cleanText.length > 100 && base64Pattern.hasMatch(cleanText)) {
        return true;
      }
    }
  }
  return false;
}

/// Check if a string is a placeholder (e.g., <ph-xxxxx>)
bool isPlaceholder(String text) {
  if (text.isEmpty) return false;
  // Check for placeholder pattern: <ph-xxxxx> or similar
  final trimmed = text.trim();
  return RegExp(r'^<ph-[^>]+>$').hasMatch(trimmed);
}

/// Replace base64 content with placeholder for logging
String sanitizeForLog(String text, {int maxLength = 50}) {
  if (text.isEmpty) return text;

  // Check if it's base64
  if (isBase64Image(text)) {
    // Extract image type if it's a data URI
    if (text.startsWith('data:image/')) {
      final match = RegExp('data:image/([^;]+)').firstMatch(text);
      final imageType = match?.group(1) ?? 'image';
      return '<base64_image_data_uri: $imageType, length=${text.length}>';
    } else {
      return '<base64_string, length=${text.length}>';
    }
  }

  // Check if it's a placeholder
  if (isPlaceholder(text)) {
    return '<placeholder: ${text.trim()}>';
  }

  // For non-base64, just truncate if too long
  if (text.length > maxLength) {
    return '${text.substring(0, maxLength)}...';
  }
  return text;
}

/// Extract text from HTML by removing tags
/// Simple HTML tag removal - for better extraction, consider using html package
String extractTextFromHtml(String html) => html
    .replaceAll(
      RegExp(r'<script[^>]*>[\s\S]*?</script>', caseSensitive: false),
      '',
    )
    .replaceAll(
      RegExp(r'<style[^>]*>[\s\S]*?</style>', caseSensitive: false),
      '',
    )
    .replaceAll(RegExp('<[^>]+>'), '\n')
    .replaceAll(RegExp(r'\n\s*\n'), '\n')
    .trim();
