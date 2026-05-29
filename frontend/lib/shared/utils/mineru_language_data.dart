// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import '../../l10n/app_localizations.dart';

/// MinerU native language codes and their descriptions.
///
/// Each code groups one or more written languages that MinerU can OCR.
/// Descriptions come from mineru-3.0.9/mineru/cli/fast_api.py lines 748-765.
class MineruLanguageEntry {
  final String code;
  final String label;
  final String nativeName;
  final String description;

  const MineruLanguageEntry({
    required this.code,
    required this.label,
    required this.nativeName,
    required this.description,
  });

  String get displayName => '$label ($nativeName)';
}

/// All MinerU language codes with their metadata.
const List<MineruLanguageEntry> mineruLanguageEntries = <MineruLanguageEntry>[
  MineruLanguageEntry(
    code: 'auto',
    label: 'Auto Detect',
    nativeName: 'Auto',
    description: 'Automatically detect document language',
  ),
  MineruLanguageEntry(
    code: 'ch',
    label: 'Chinese',
    nativeName: '中文',
    description: 'Chinese, English, Chinese Traditional',
  ),
  MineruLanguageEntry(
    code: 'ch_server',
    label: 'Chinese (Server)',
    nativeName: '中文',
    description: 'Chinese, English, Chinese Traditional, Japanese',
  ),
  MineruLanguageEntry(
    code: 'ch_lite',
    label: 'Chinese (Lite)',
    nativeName: '中文',
    description: 'Chinese, English, Chinese Traditional, Japanese',
  ),
  MineruLanguageEntry(
    code: 'chinese_cht',
    label: 'Chinese Traditional',
    nativeName: '繁體中文',
    description: 'Chinese, English, Chinese Traditional, Japanese',
  ),
  MineruLanguageEntry(
    code: 'en',
    label: 'English',
    nativeName: 'English',
    description: 'English',
  ),
  MineruLanguageEntry(
    code: 'korean',
    label: 'Korean',
    nativeName: '한국어',
    description: 'Korean, English',
  ),
  MineruLanguageEntry(
    code: 'japan',
    label: 'Japanese',
    nativeName: '日本語',
    description: 'Chinese, English, Chinese Traditional, Japanese',
  ),
  MineruLanguageEntry(
    code: 'ta',
    label: 'Tamil',
    nativeName: 'தமிழ்',
    description: 'Tamil, English',
  ),
  MineruLanguageEntry(
    code: 'te',
    label: 'Telugu',
    nativeName: 'తెలుగు',
    description: 'Telugu, English',
  ),
  MineruLanguageEntry(
    code: 'ka',
    label: 'Kannada',
    nativeName: 'ಕನ್ನಡ',
    description: 'Kannada',
  ),
  MineruLanguageEntry(
    code: 'th',
    label: 'Thai',
    nativeName: 'ไทย',
    description: 'Thai, English',
  ),
  MineruLanguageEntry(
    code: 'el',
    label: 'Greek',
    nativeName: 'Ελληνικά',
    description: 'Greek, English',
  ),
  MineruLanguageEntry(
    code: 'latin',
    label: 'Latin Script',
    nativeName: 'Latin',
    description:
        'French, German, Afrikaans, Italian, Spanish, Portuguese, Dutch, and more Latin-script languages',
  ),
  MineruLanguageEntry(
    code: 'arabic',
    label: 'Arabic Script',
    nativeName: 'العربية',
    description: 'Arabic, Persian, Uyghur, Urdu, Pashto, Sindhi, Balochi, English',
  ),
  MineruLanguageEntry(
    code: 'east_slavic',
    label: 'East Slavic',
    nativeName: 'East Slavic',
    description: 'Russian, Belarusian, Ukrainian, English',
  ),
  MineruLanguageEntry(
    code: 'cyrillic',
    label: 'Cyrillic Script',
    nativeName: 'Cyrillic',
    description:
        'Russian, Belarusian, Ukrainian, Serbian, Bulgarian, Kazakh, and more Cyrillic-script languages',
  ),
  MineruLanguageEntry(
    code: 'devanagari',
    label: 'Devanagari Script',
    nativeName: 'देवनागरी',
    description: 'Hindi, Marathi, Nepali, Bihari, Maithili, Sanskrit, and more Devanagari-script languages',
  ),
];

/// Look up a [MineruLanguageEntry] by its [code].
/// Returns `null` if the code is not found.
MineruLanguageEntry? findMineruLanguage(String code) {
  for (final MineruLanguageEntry entry in mineruLanguageEntries) {
    if (entry.code == code) return entry;
  }
  return null;
}

/// Returns a localized display name for a [MineruLanguageEntry].
/// Uses [mineruLang*] l10n keys for MinerU-specific codes and existing
/// [translationLang*] keys for common languages.
/// The native name in parentheses is kept as-is.
String mineruLocalizedDisplayName(AppLocalizations l10n, MineruLanguageEntry entry) {
  final String localizedLabel = _mineruLocalizedLabel(l10n, entry.code);
  return '$localizedLabel (${entry.nativeName})';
}

String _mineruLocalizedLabel(AppLocalizations l10n, String code) {
  switch (code) {
    case 'auto':
      return l10n.mineruLangAuto;
    case 'ch':
      return l10n.translationLangChinese;
    case 'ch_server':
      return l10n.mineruLangChServer;
    case 'ch_lite':
      return l10n.mineruLangChLite;
    case 'chinese_cht':
      return l10n.translationLangChineseTraditional;
    case 'en':
      return l10n.translationLangEnglish;
    case 'korean':
      return l10n.translationLangKorean;
    case 'japan':
      return l10n.translationLangJapanese;
    case 'ta':
      return l10n.mineruLangTamil;
    case 'te':
      return l10n.mineruLangTelugu;
    case 'ka':
      return l10n.mineruLangKannada;
    case 'th':
      return l10n.translationLangThai;
    case 'el':
      return l10n.translationLangGreek;
    case 'latin':
      return l10n.mineruLangLatinScript;
    case 'arabic':
      return l10n.mineruLangArabicScript;
    case 'east_slavic':
      return l10n.mineruLangEastSlavic;
    case 'cyrillic':
      return l10n.mineruLangCyrillicScript;
    case 'devanagari':
      return l10n.mineruLangDevanagariScript;
    default:
      return findMineruLanguage(code)?.label ?? code;
  }
}
