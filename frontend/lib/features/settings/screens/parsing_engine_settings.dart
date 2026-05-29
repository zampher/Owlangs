import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/utils/mineru_language_data.dart';

// 解析引擎设置状态管理
final StateNotifierProvider<ParsingEngineSettingsNotifier,
        ParsingEngineSettings> parsingEngineSettingsProvider =
    StateNotifierProvider<ParsingEngineSettingsNotifier, ParsingEngineSettings>(
  (
    StateNotifierProviderRef<ParsingEngineSettingsNotifier, ParsingEngineSettings> ref,
  ) =>
      ParsingEngineSettingsNotifier(),
);

class ParsingEngineSettings {
  const ParsingEngineSettings({
    this.parsingEngine = 'mineru',
    this.ocrLanguage = 'eng',
    this.chunkSize = 1000,
    this.concurrent = 3,
    this.timeout = 300,
    this.isTestingEngine = false,
  });
  final String parsingEngine;
  final String ocrLanguage;
  final int chunkSize;
  final int concurrent;
  final int timeout;
  final bool isTestingEngine;

  ParsingEngineSettings copyWith({
    String? parsingEngine,
    String? ocrLanguage,
    int? chunkSize,
    int? concurrent,
    int? timeout,
    bool? isTestingEngine,
  }) =>
      ParsingEngineSettings(
        parsingEngine: parsingEngine ?? this.parsingEngine,
        ocrLanguage: ocrLanguage ?? this.ocrLanguage,
        chunkSize: chunkSize ?? this.chunkSize,
        concurrent: concurrent ?? this.concurrent,
        timeout: timeout ?? this.timeout,
        isTestingEngine: isTestingEngine ?? this.isTestingEngine,
      );
}

class ParsingEngineSettingsNotifier
    extends StateNotifier<ParsingEngineSettings> {
  ParsingEngineSettingsNotifier() : super(const ParsingEngineSettings());

  void updateParsingEngine(String parsingEngine) {
    state = state.copyWith(parsingEngine: parsingEngine);
  }

  void updateOcrLanguage(String ocrLanguage) {
    state = state.copyWith(ocrLanguage: ocrLanguage);
  }

  void updateChunkSize(int chunkSize) {
    state = state.copyWith(chunkSize: chunkSize);
  }

  void updateConcurrent(int concurrent) {
    state = state.copyWith(concurrent: concurrent);
  }

  void updateTimeout(int timeout) {
    state = state.copyWith(timeout: timeout);
  }

  Future<void> testEngine() async {
    state = state.copyWith(isTestingEngine: true);

    // Simulate engine test
    await Future.delayed(const Duration(seconds: 2));

    state = state.copyWith(isTestingEngine: false);
  }

  void reset() {
    state = const ParsingEngineSettings();
  }
}

class ParsingEngineSettingsScreen extends ConsumerWidget {
  const ParsingEngineSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final GlobalSettings globalSettings = ref.watch(globalSettingsProvider);
    final GlobalSettingsNotifier globalNotifier =
        ref.read(globalSettingsProvider.notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Parsing Engine Selection
          _buildParsingEngineSection(context, globalSettings, globalNotifier, ref),
          const SizedBox(height: 24),

          // OCR Language Settings
          _buildOcrLanguageSection(context, globalSettings, globalNotifier),
        ],
      ),
    );
  }

  Widget _buildParsingEngineSection(
    BuildContext context,
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
    WidgetRef ref,
  ) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    // Hardcoded parser engine codes
    final List<String> engineCodes = <String>['mineru', 'mineru_local'];

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(Icons.build, color: Colors.blue.shade700),
                const SizedBox(width: 8),
                Text(
                  l10n.settingsParsingEngineTitle,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.blue.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              l10n.settingsParsingEngineSubtitle,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: engineCodes.contains(settings.parsingEngine)
                  ? settings.parsingEngine
                  : engineCodes.first,
              decoration: InputDecoration(
                labelText: l10n.settingsParsingEngineLabel,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              items: engineCodes
                  .map(
                    (String code) => DropdownMenuItem<String>(
                      value: code,
                      child: Text(
                        _getParserPlatformDisplayName(l10n, code),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (String? value) =>
                  notifier.updateParsingEngineSettings(parsingEngine: value),
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 8),
            // Formula OCR Toggle
            SwitchListTile(
              title: Text(l10n.settingsFormulaOcr),
              subtitle: Text(l10n.settingsFormulaOcrSubtitle),
              value: settings.formulaOcr,
              onChanged: (bool value) =>
                  notifier.updateParsingEngineSettings(formulaOcr: value),
              contentPadding: EdgeInsets.zero,
            ),
            // Table OCR Toggle
            SwitchListTile(
              title: Text(l10n.settingsTableOcr),
              subtitle: Text(l10n.settingsTableOcrSubtitle),
              value: settings.tableOcr,
              onChanged: (bool value) =>
                  notifier.updateParsingEngineSettings(tableOcr: value),
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 8),
            Text(
              l10n.settingsParsingEngineNewTaskNotice,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
            const SizedBox(height: 12),
            // PDF Split Max Pages
            TextFormField(
              decoration: InputDecoration(
                labelText: l10n.settingsPdfSplitMaxPages,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              keyboardType: TextInputType.number,
              initialValue: settings.pdfSplitMaxPages.toString(),
              onChanged: (String value) {
                final int? parsed = int.tryParse(value);
                if (parsed != null && parsed > 0) {
                  notifier.updateParsingEngineSettings(pdfSplitMaxPages: parsed);
                }
              },
            ),
            const SizedBox(height: 12),
            // PDF Split Max Workers
            TextFormField(
              decoration: InputDecoration(
                labelText: l10n.settingsPdfSplitMaxWorkers,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              keyboardType: TextInputType.number,
              initialValue: settings.pdfSplitMaxWorkers.toString(),
              onChanged: (String value) {
                final int? parsed = int.tryParse(value);
                if (parsed != null && parsed > 0) {
                  notifier.updateParsingEngineSettings(pdfSplitMaxWorkers: parsed);
                }
              },
            ),
            const SizedBox(height: 12),
            // Request Retry Count
            TextFormField(
              decoration: InputDecoration(
                labelText: l10n.settingsRequestRetryCount,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              keyboardType: TextInputType.number,
              initialValue: settings.requestRetryCount.toString(),
              onChanged: (String value) {
                final int? parsed = int.tryParse(value);
                if (parsed != null && parsed >= 0) {
                  notifier.updateParsingEngineSettings(requestRetryCount: parsed);
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  /// Get parser platform display names
  String _getParserPlatformDisplayName(AppLocalizations l10n, String code) {
    // Try to get from config first, fallback to localized names
    switch (code) {
      case 'mineru':
        return l10n.settingsParsingEngineMineru;
      case 'mineru_local':
        return l10n.settingsParsingEngineMineruLocal;
      default:
        return code;
    }
  }

  Widget _buildOcrLanguageSection(
    BuildContext context,
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final String effectiveLang =
        _coerceLegacyOcrLang(settings.ocrLanguage);

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(Icons.language, color: Colors.green.shade700),
                const SizedBox(width: 8),
                Text(
                  l10n.settingsOcrLanguageTitle,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.green.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              l10n.settingsOcrLanguageSubtitle,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: effectiveLang,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: l10n.settingsOcrLanguageLabel,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              selectedItemBuilder: (BuildContext context) {
                return mineruLanguageEntries.map((MineruLanguageEntry lang) {
                  return Text(mineruLocalizedDisplayName(l10n, lang));
                }).toList();
              },
              items: mineruLanguageEntries
                  .map(
                    (MineruLanguageEntry lang) => DropdownMenuItem<String>(
                      value: lang.code,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(mineruLocalizedDisplayName(l10n, lang)),
                          if (lang.code != 'auto')
                            Text(
                              lang.description,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade600,
                              ),
                            ),
                        ],
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (String? value) {
                if (value != null) {
                  notifier.updateParsingEngineSettings(ocrLanguage: value);
                }
              },
            ),
            // Show description for selected language below the dropdown
            if (effectiveLang != 'auto') ...<Widget>[
              const SizedBox(height: 8),
              _buildSelectedLangInfo(effectiveLang),
            ],
          ],
        ),
      ),
    );
  }

  /// Map old Tesseract-style codes to MinerU native codes for backward compatibility.
  String _coerceLegacyOcrLang(String code) {
    switch (code) {
      case 'eng':
        return 'en';
      case 'chi_sim':
      case 'chs':
        return 'ch';
      case 'chi_tra':
      case 'cht':
        return 'chinese_cht';
      case 'jpn':
        return 'japan';
      case 'kor':
        return 'korean';
      case 'fra':
      case 'deu':
      case 'spa':
        return 'latin';
      case 'rus':
        return 'east_slavic';
      case 'ara':
        return 'arabic';
      default:
        // Check if code is already a valid MinerU code
        if (findMineruLanguage(code) != null) return code;
        return 'auto';
    }
  }

  Widget _buildSelectedLangInfo(String effectiveLang) {
    final MineruLanguageEntry? current = findMineruLanguage(effectiveLang);
    if (current == null) return const SizedBox.shrink();
    return Tooltip(
      message: current.description,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          '${current.displayName}\n${current.description}',
          style: TextStyle(
            fontSize: 13,
            color: Colors.grey.shade700,
            height: 1.5,
          ),
        ),
      ),
    );
  }
}
