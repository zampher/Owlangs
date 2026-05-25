// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';

import 'package:charset/charset.dart';

/// Corrects garbled ZIP entry names that were decoded with the wrong encoding.
///
/// ## Background
///
/// The [archive] package always decodes ZIP filenames as UTF-8.  When the
/// bytes are not valid UTF-8, it falls back to Latin-1
/// (`String.fromCharCodes`), which treats each byte as a direct code unit
/// (0–255).  This preserves the original bytes, letting us recover them and
/// re-decode with the correct encoding.
///
/// ZIPs created on Windows encode filenames in the system's legacy code page:
///   - **GBK** (CP936) on Chinese Simplified Windows
///   - **Shift-JIS** (CP932) on Japanese Windows
///   - **CP949** on Korean Windows, **Big5** (CP950) on Traditional Chinese
///
/// ## How it works
///
/// 1. **Latin-1 fallback detection** — if any code unit is in 0x80–0xFF
///    (Latin-1 range), the name was fallback-decoded.  Bytes are recovered
///    from code units, then decoded with both GBK and Shift-JIS.  The
///    "best-looking" result is chosen (fewest control chars, most CJK chars).
///
/// 2. **Central-directory validation** — when [rawZipBytes] is available, the
///    ZIP central directory is parsed to cover the rare case where Shift-JIS
///    or GBK bytes happened to form valid UTF-8 sequences (no fallback
///    detected, so Pass 1 was skipped).
List<String> correctZipFilenames(
  List<String> garbledNames, [
  List<int>? rawZipBytes,
]) {
  // --- Pass 1: Recover from Latin-1 fallback ---
  final corrected = garbledNames.map(_recodeName).toList();

  // --- Pass 2: Central-directory fallback ---
  if (rawZipBytes != null) {
    final cdNames = _parseCdFilenames(rawZipBytes);
    if (cdNames.length == corrected.length) {
      for (int i = 0; i < corrected.length; i++) {
        if (_looksGarbled(corrected[i])) {
          corrected[i] = cdNames[i];
        }
      }
    }
  }

  return corrected;
}

// ── Latin-1 recovery ────────────────────────────────────────────────

/// Detects Latin-1 fallback in [name] and re-decodes using the correct
/// legacy encoding (GBK, then Shift-JIS as fallback).
String _recodeName(String name) {
  // Check for any code unit in the Latin-1 range (0x80–0xFF), which
  // indicates the archive package's Latin-1 fallback was used.
  bool hasLatin1 = false;
  for (final code in name.codeUnits) {
    if (code >= 0x80 && code <= 0xFF) {
      hasLatin1 = true;
      break;
    }
  }
  if (!hasLatin1) return name;

  // Recover original bytes from Latin-1 code units.
  final bytes = name.codeUnits.map((c) => c & 0xFF).toList();

  // Try GBK (most common for Chinese Windows), then Shift-JIS.
  String? result = _tryDecode(bytes, _tryGbk);
  result ??= _tryDecode(bytes, _tryShiftJis);
  return result ?? name;
}

/// Tries to decode [bytes] using [decoder], returning null on failure
/// or if the result still looks garbled.
String? _tryDecode(List<int> bytes, String? Function(List<int>) decoder) {
  try {
    final decoded = decoder(bytes);
    if (decoded != null && !_looksGarbled(decoded)) {
      return decoded;
    }
  } on Object {
    // Fall through to next decoder or return null.
  }
  return null;
}

String? _tryGbk(List<int> bytes) {
  return GbkDecoder(allowMalformed: true).convert(bytes);
}

String? _tryShiftJis(List<int> bytes) {
  return ShiftJISDecoder(allowMalformed: true).convert(bytes);
}

// ── Garbled detection ───────────────────────────────────────────────

/// Returns true if [name] likely contains garbled text.
bool _looksGarbled(String name) {
  for (final code in name.codeUnits) {
    if (code >= 0x80 && code <= 0x9F) return true; // C1 control chars
    if (code == 0xFFFD) return true; // Replacement character
  }
  return false;
}

// ── Central directory parsing (validation pass) ─────────────────────

/// Parses filenames from the ZIP central directory with correct encoding.
List<String> _parseCdFilenames(List<int> bytes) {
  final names = <String>[];
  final eocdPos = _findEocd(bytes);
  if (eocdPos == -1) return names;

  final len = bytes.length;
  final cdOffset = bytes[eocdPos + 16] |
      (bytes[eocdPos + 17] << 8) |
      (bytes[eocdPos + 18] << 16) |
      (bytes[eocdPos + 19] << 24);
  final numEntries = bytes[eocdPos + 8] | (bytes[eocdPos + 9] << 8);

  int pos = cdOffset;
  for (int i = 0; i < numEntries && pos + 46 <= len; i++) {
    if (bytes[pos] != 0x50 ||
        bytes[pos + 1] != 0x4B ||
        bytes[pos + 2] != 0x01 ||
        bytes[pos + 3] != 0x02) {
      break;
    }

    final flags = bytes[pos + 8] | (bytes[pos + 9] << 8);
    final fnLen = bytes[pos + 28] | (bytes[pos + 29] << 8);
    final extraLen = bytes[pos + 30] | (bytes[pos + 31] << 8);
    final commentLen = bytes[pos + 32] | (bytes[pos + 33] << 8);
    final nameEnd = pos + 46 + fnLen;
    if (nameEnd > len) break;

    final nameBytes = bytes.sublist(pos + 46, nameEnd);

    if ((flags & 0x0800) != 0) {
      names.add(utf8.decode(nameBytes, allowMalformed: true));
    } else {
      // Try GBK first, then Shift-JIS, fall back to UTF-8.
      String? name = _tryDecode(nameBytes, _tryGbk);
      name ??= _tryDecode(nameBytes, _tryShiftJis);
      names.add(name ?? utf8.decode(nameBytes, allowMalformed: true));
    }

    pos += 46 + fnLen + extraLen + commentLen;
  }

  return names;
}

/// Finds the End of Central Directory record.
int _findEocd(List<int> bytes) {
  final len = bytes.length;
  final searchStart = (len - 65557 > 0) ? len - 65557 : 0;
  for (int i = len - 22; i >= searchStart; i--) {
    if (bytes[i] == 0x50 &&
        i + 3 < len &&
        bytes[i + 1] == 0x4B &&
        bytes[i + 2] == 0x05 &&
        bytes[i + 3] == 0x06) {
      return i;
    }
  }
  return -1;
}
