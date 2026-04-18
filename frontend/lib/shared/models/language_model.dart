// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

class Language {
  const Language({
    required this.code,
    required this.name,
    required this.nativeName,
    required this.flag,
  });
  final String code;
  final String name;
  final String nativeName;
  final String flag;

  @override
  String toString() => '$name ($nativeName)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Language &&
          runtimeType == other.runtimeType &&
          code == other.code;

  @override
  int get hashCode => code.hashCode;
}

class LanguageService {
  static const List<Language> supportedLanguages = <Language>[
    Language(code: 'zh', name: 'Chinese', nativeName: '中文', flag: '🇨🇳'),
    Language(code: 'en', name: 'English', nativeName: 'English', flag: '🇺🇸'),
    Language(code: 'ja', name: 'Japanese', nativeName: '日本語', flag: '🇯🇵'),
    Language(code: 'ko', name: 'Korean', nativeName: '한국어', flag: '🇰🇷'),
    Language(code: 'fr', name: 'French', nativeName: 'Français', flag: '🇫🇷'),
    Language(code: 'de', name: 'German', nativeName: 'Deutsch', flag: '🇩🇪'),
    Language(code: 'es', name: 'Spanish', nativeName: 'Español', flag: '🇪🇸'),
    Language(code: 'ru', name: 'Russian', nativeName: 'Русский', flag: '🇷🇺'),
    Language(code: 'ar', name: 'Arabic', nativeName: 'العربية', flag: '🇸🇦'),
    Language(
      code: 'pt',
      name: 'Portuguese',
      nativeName: 'Português',
      flag: '🇵🇹',
    ),
  ];

  static Language? getLanguageByCode(String code) {
    try {
      return supportedLanguages
          .firstWhere((Language lang) => lang.code == code);
    } catch (e) {
      return null;
    }
  }

  static Language getDefaultSourceLanguage() =>
      supportedLanguages.first; // Chinese
  static Language getDefaultTargetLanguage() =>
      supportedLanguages[1]; // English
}
