/// Shared bidirectional language code-to-name mapper.
///
/// Frontend UI uses language CODES (e.g. 'en', 'zh').
/// Backend stores language NAMES (e.g. 'English', 'Chinese').
/// This mapper bridges the two.

import '../../l10n/app_localizations.dart';

/// Code -> English name (matching _convertLangCodeToName in translation_screen.dart).
const Map<String, String> codeToNameMap = <String, String>{
  'ar': 'Arabic',
  'bn': 'Bengali',
  'ca': 'Catalan',
  'zh': 'Chinese',
  'cs': 'Czech',
  'hr': 'Croatian',
  'da': 'Danish',
  'nl': 'Dutch',
  'en': 'English',
  'fil': 'Filipino',
  'fi': 'Finnish',
  'fr': 'French',
  'de': 'German',
  'el': 'Greek',
  'he': 'Hebrew',
  'hi': 'Hindi',
  'it': 'Italian',
  'ja': 'Japanese',
  'ko': 'Korean',
  'km': 'Khmer',
  'lt': 'Lithuanian',
  'mk': 'Macedonian',
  'ms': 'Malay',
  'nb': 'Norwegian',
  'pl': 'Polish',
  'pt': 'Portuguese',
  'ro': 'Romanian',
  'ru': 'Russian',
  'sl': 'Slovenian',
  'es': 'Spanish',
  'sv': 'Swedish',
  'th': 'Thai',
  'tr': 'Turkish',
  'uk': 'Ukrainian',
  'ur': 'Urdu',
  'vi': 'Vietnamese',
};

/// Code -> native script name (for display).
const Map<String, String> nativeScriptNames = <String, String>{
  'ar': '\u0627\u0644\u0639\u0631\u0628\u064A\u0629',
  'bn': '\u09AC\u09BE\u0982\u09B2\u09BE',
  'ca': 'Catal\u00E0',
  'zh': '\u4E2D\u6587',
  'zh-TW': '\u7E41\u9AD4\u4E2D\u6587',
  'cs': '\u010Ce\u0161tina',
  'hr': 'Hrvatski',
  'da': 'Dansk',
  'nl': 'Nederlands',
  'en': 'English',
  'fil': 'Filipino',
  'fi': 'Suomi',
  'fr': 'Fran\u00E7ais',
  'de': 'Deutsch',
  'el': '\u0395\u03BB\u03BB\u03B7\u03BD\u03B9\u03BA\u03AC',
  'he': '\u05E2\u05D1\u05E8\u05D9\u05EA',
  'hi': '\u0939\u093F\u0928\u094D\u0926\u0940',
  'it': 'Italiano',
  'ja': '\u65E5\u672C\u8A9E',
  'ko': '\uD55C\uAD6D\uC5B4',
  'km': '\u1797\u17B6\u179F\u17B6\u1781\u17D2\u1798\u17C2\u179A',
  'lt': 'Lietuvi\u0173',
  'mk': '\u041C\u0430\u043A\u0435\u0434\u043E\u043D\u0441\u043A\u0438',
  'ms': 'Bahasa Melayu',
  'nb': 'Norwegian Bokm\u00E5l',
  'pl': 'Polski',
  'pt': 'Portugu\u00EAs',
  'ro': 'Rom\u00E2n\u0103',
  'ru': '\u0420\u0443\u0441\u0441\u043A\u0438\u0439',
  'sl': 'Sloven\u0161\u010Dina',
  'es': 'Espa\u00F1ol',
  'sv': 'Svenska',
  'th': '\u0E44\u0E17\u0E22',
  'tr': 'T\u00FCrk\u00E7e',
  'uk': '\u0423\u043A\u0440\u0430\u0457\u043D\u0441\u044C\u043A\u0430',
  'ur': '\u0627\u0631\u062F\u0648',
  'vi': 'Ti\u1EBFng Vi\u1EC7t',
};

/// Reverse: name -> code (computed lazily).
Map<String, String>? _nameToCodeCache;
Map<String, String> get nameToCodeMap {
  _nameToCodeCache ??= <String, String>{
    for (final MapEntry<String, String> e in codeToNameMap.entries)
      e.value: e.key,
  };
  return _nameToCodeCache!;
}

/// Convert a language code (e.g. 'ja') to a backend name (e.g. 'Japanese').
String? codeToName(String code) => codeToNameMap[code];

/// Convert a backend name (e.g. 'Japanese') to a language code (e.g. 'ja').
String? nameToCode(String name) => nameToCodeMap[name];

/// Localized display name for a language code: "English (English)", "中文 (中文)".
String languageDisplayName(AppLocalizations l10n, String code) {
  final String label = switch (code) {
    'ar' => l10n.translationLangArabic,
    'bn' => l10n.translationLangBengali,
    'ca' => l10n.translationLangCatalan,
    'zh' => l10n.translationLangChinese,
    'zh-TW' => l10n.translationLangChineseTraditional,
    'cs' => l10n.translationLangCzech,
    'hr' => l10n.translationLangCroatian,
    'da' => l10n.translationLangDanish,
    'nl' => l10n.translationLangDutch,
    'en' => l10n.translationLangEnglish,
    'fil' => l10n.translationLangFilipino,
    'fi' => l10n.translationLangFinnish,
    'fr' => l10n.translationLangFrench,
    'de' => l10n.translationLangGerman,
    'el' => l10n.translationLangGreek,
    'he' => l10n.translationLangHebrew,
    'hi' => l10n.translationLangHindi,
    'it' => l10n.translationLangItalian,
    'ja' => l10n.translationLangJapanese,
    'ko' => l10n.translationLangKorean,
    'km' => l10n.translationLangKhmer,
    'lt' => l10n.translationLangLithuanian,
    'mk' => l10n.translationLangMacedonian,
    'ms' => l10n.translationLangMalay,
    'nb' => l10n.translationLangNorwegian,
    'pl' => l10n.translationLangPolish,
    'pt' => l10n.translationLangPortuguese,
    'ro' => l10n.translationLangRomanian,
    'ru' => l10n.translationLangRussian,
    'sl' => l10n.translationLangSlovenian,
    'es' => l10n.translationLangSpanish,
    'sv' => l10n.translationLangSwedish,
    'th' => l10n.translationLangThai,
    'tr' => l10n.translationLangTurkish,
    'uk' => l10n.translationLangUkrainian,
    'ur' => l10n.translationLangUrdu,
    'vi' => l10n.translationLangVietnamese,
    _ => code,
  };
  final String native = nativeScriptNames[code] ?? code;
  return '$label ($native)';
}

/// Dropdown entries for language selectors: code + display name (English).
List<Map<String, String>> get languageDropdownEntries => codeToNameMap.entries
    .map((e) => <String, String>{'code': e.key, 'name': e.value})
    .toList();
