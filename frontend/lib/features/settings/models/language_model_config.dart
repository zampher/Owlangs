// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

class LanguageModelConfig {
  // Allow fallback (lg→md→sm)

  const LanguageModelConfig({
    required this.preferred,
    this.modelsDir,
    this.fallback = true,
  });

  factory LanguageModelConfig.fromJson(Map<String, dynamic> json) =>
      LanguageModelConfig(
        preferred: json['preferred'] ?? '',
        modelsDir: json['models_dir'],
        fallback: json['fallback'] ?? true,
      );
  final String preferred; // e.g., "zh_core_web_sm"
  final String? modelsDir;
  final bool fallback;

  LanguageModelConfig copyWith({
    String? preferred,
    String? modelsDir,
    bool? fallback,
  }) =>
      LanguageModelConfig(
        preferred: preferred ?? this.preferred,
        modelsDir: modelsDir ?? this.modelsDir,
        fallback: fallback ?? this.fallback,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'preferred': preferred,
        'models_dir': modelsDir,
        'fallback': fallback,
      };
}
