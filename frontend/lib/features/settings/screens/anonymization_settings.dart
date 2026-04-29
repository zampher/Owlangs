// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io' show Platform;
import '../providers/anonymization_settings_provider.dart';
import '../models/language_model_config.dart';
import '../models/anonymization_settings_state.dart';
import '../widgets/anonymization_status_bar.dart';
import '../../../shared/utils/message_service.dart';
import '../../../l10n/app_localizations.dart';

// Language names mapping (English Name (Local Name))
const Map<String, String> LANGUAGES = <String, String>{
  'zh': 'Chinese (中文)',
  'en': 'English (English)',
  'de': 'German (Deutsch)',
  'fr': 'French (Français)',
  'es': 'Spanish (Español)',
  'it': 'Italian (Italiano)',
  'nl': 'Dutch (Nederlands)',
  'pt': 'Portuguese (Português)',
  'ru': 'Russian (Русский)',
  'ja': 'Japanese (日本語)',
  'ko': 'Korean (한국어)',
  'pl': 'Polish (Polski)',
  'da': 'Danish (Dansk)',
  'nb': 'Norwegian (Norsk)',
  'sv': 'Swedish (Svenska)',
  'fi': 'Finnish (Suomi)',
  'el': 'Greek (Ελληνικά)',
  'lt': 'Lithuanian (Lietuvių)',
  'ro': 'Romanian (Română)',
  'uk': 'Ukrainian (Українська)',
  'ar': 'Arabic (العربية)',
  'hi': 'Hindi (हिन्दी)',
  'th': 'Thai (ไทย)',
  'vi': 'Vietnamese (Tiếng Việt)',
};

// Default test texts by language
const Map<String, String> DEFAULT_TEST_TEXTS = <String, String>{
  'zh': '今天天气不错，张三的邮箱是 zhangsan@example.com',
  'en': "Hello, John Smith's email is john@example.com",
  'de': 'Hallo, Max Mustermanns E-Mail ist max@example.com',
  'fr': "Bonjour, l'email de Jean Dupont est jean@example.com",
  'es': 'Hola, el email de Juan Pérez es juan@example.com',
  'it': "Ciao, l'email di Mario Rossi è mario@example.com",
  'nl': "Hallo, Jan Jansen's email is jan@example.com",
  'pt': 'Olá, o email de João Silva é joao@example.com',
  'ru': 'Привет, email Ивана Петрова это ivan@example.com',
  'ja': 'こんにちは、田中太郎のメールは tanaka@example.com です',
  'ko': '안녕하세요, 김철수의 이메일은 kim@example.com 입니다',
  'pl': 'Cześć, email Jana Kowalskiego to jan@example.com',
  'da': 'Hej, Jan Hansens email er jan@example.com',
  'nb': 'Hei, Jan Hansens e-post er jan@example.com',
  'sv': 'Hej, Jan Hanssons e-post är jan@example.com',
  'fi': 'Hei, Jan Hanssonin sähköposti on jan@example.com',
  'el': 'Γεια σας, το email του Γιάννη Παπαδόπουλου είναι giannis@example.com',
  'lt': 'Labas, Jono Jonaitis el. paštas yra jonas@example.com',
  'ro': 'Salut, email-ul lui Ion Popescu este ion@example.com',
  'uk': 'Привіт, email Івана Петренка це ivan@example.com',
  'ar': 'مرحبا، بريد أحمد محمد الإلكتروني هو ahmed@example.com',
  'hi': 'नमस्ते, अमित शर्मा का ईमेल amit@example.com है',
  'th': 'สวัสดี อีเมลของสมชาย ใจดี คือ somchai@example.com',
  'vi': 'Xin chào, email của Nguyễn Văn A là nguyen@example.com',
};

class AnonymizationSettingsScreen extends ConsumerStatefulWidget {
  const AnonymizationSettingsScreen({super.key});

  @override
  ConsumerState<AnonymizationSettingsScreen> createState() =>
      _AnonymizationSettingsScreenState();
}

class _AnonymizationSettingsScreenState
    extends ConsumerState<AnonymizationSettingsScreen> {
  String _selectedLanguage = 'zh';
  String _languageSearch = '';
  final TextEditingController _testTextController = TextEditingController();
  final Map<String, TextEditingController> _modelsDirControllers =
      <String, TextEditingController>{};

  @override
  void initState() {
    super.initState();
    // Set default test text based on selected language
    _updateTestText();
  }

  @override
  void dispose() {
    _testTextController.dispose();
    for (final TextEditingController controller
        in _modelsDirControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  TextEditingController _getModelsDirController(
    String language,
    LanguageModelConfig config,
  ) {
    if (!_modelsDirControllers.containsKey(language)) {
      _modelsDirControllers[language] = TextEditingController(
        text: config.modelsDir ?? '',
      );
    } else {
      // Update controller text if config changed
      final String currentText = _modelsDirControllers[language]!.text;
      final String newText = config.modelsDir ?? '';
      if (currentText != newText) {
        _modelsDirControllers[language]!.text = newText;
      }
    }
    return _modelsDirControllers[language]!;
  }

  void _updateTestText() {
    // Generate multi-line test text with all languages
    final List<String> lines = <String>[];
    for (final String lang in LANGUAGES.keys) {
      final String langName = LANGUAGES[lang] ?? lang;
      final String testText =
          DEFAULT_TEST_TEXTS[lang] ?? DEFAULT_TEST_TEXTS['en']!;
      lines.add('$langName ($lang): $testText');
    }
    final String multiLineText = lines.join('\n');
    if (_testTextController.text.isEmpty) {
      _testTextController.text = multiLineText;
    }
  }

  @override
  Widget build(BuildContext context) {
    final AnonymizationSettingsState state =
        ref.watch(anonymizationSettingsProvider);
    final AnonymizationSettingsNotifier notifier =
        ref.read(anonymizationSettingsProvider.notifier);

    // Get available languages from backend options (all available languages, not just configured ones)
    final List<String> availableLanguages =
        state.availableModelOptions.keys.toList()..sort();
    // If no options loaded yet, fallback to configured languages
    final List<String> finalAvailableLanguages = availableLanguages.isNotEmpty
        ? availableLanguages
        : state.languageConfigs.keys.toList()
      ..sort();
    final List<String> filteredLanguages = _languageSearch.isEmpty
        ? finalAvailableLanguages
        : finalAvailableLanguages.where((String lang) {
            final String langName = LANGUAGES[lang] ?? lang;
            return lang.toLowerCase().contains(_languageSearch.toLowerCase()) ||
                langName.toLowerCase().contains(_languageSearch.toLowerCase());
          }).toList();

    // Get current language config
    final LanguageModelConfig currentConfig =
        state.languageConfigs[_selectedLanguage] ??
            const LanguageModelConfig(preferred: '');

    // Get model options for current language (from backend)
    final List<String> modelOptions =
        state.availableModelOptions[_selectedLanguage] ?? <String>[];
    // Fallback to default if backend options not available
    final List<String> finalModelOptions = modelOptions.isNotEmpty
        ? modelOptions
        : _getModelOptionsForLanguage(_selectedLanguage);

    return Column(
      children: <Widget>[
        // Status Bar
        const AnonymizationStatusBar(),
        // Main Content
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: <Widget>[
                // Language & Model Configuration
                Card(
                  elevation: 4,
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            Icon(Icons.language, color: Colors.orange.shade700),
                            const SizedBox(width: 8),
                            Text(
                              'Language & Model Configuration',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade700,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          AppLocalizations.of(context)!.settingsAnonymizationNewTaskNotice,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade600,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Language Selector
                        Row(
                          children: <Widget>[
                            Expanded(
                              flex: 2,
                              child: DropdownButtonFormField<String>(
                                initialValue: filteredLanguages
                                        .contains(_selectedLanguage)
                                    ? _selectedLanguage
                                    : (filteredLanguages.isNotEmpty
                                        ? filteredLanguages.first
                                        : null),
                                decoration: const InputDecoration(
                                  labelText: 'Language',
                                  border: OutlineInputBorder(),
                                ),
                                items: filteredLanguages.map((String lang) {
                                  final String langName =
                                      LANGUAGES[lang] ?? lang;
                                  return DropdownMenuItem(
                                    value: lang,
                                    child: Text('$langName ($lang)'),
                                  );
                                }).toList(),
                                onChanged: (String? value) {
                                  if (value != null) {
                                    setState(() {
                                      _selectedLanguage = value;
                                    });
                                  }
                                },
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              flex: 2,
                              child: TextField(
                                decoration: const InputDecoration(
                                  labelText: 'Search language',
                                  hintText: 'Type to filter...',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.search),
                                ),
                                onChanged: (String value) {
                                  setState(() {
                                    _languageSearch = value;
                                  });
                                },
                              ),
                            ),
                            const SizedBox(width: 8),
                            SizedBox(
                              width: 80,
                              child: OutlinedButton(
                                onPressed: () {
                                  setState(() {
                                    _languageSearch = '';
                                  });
                                },
                                child: const Text('Reset'),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        // Model Configuration Panel
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey.shade300),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                '${LANGUAGES[_selectedLanguage] ?? _selectedLanguage} ($_selectedLanguage)',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 16),
                              // Preferred Model
                              DropdownButtonFormField<String>(
                                initialValue: _getPreferredModelValue(
                                  currentConfig,
                                  finalModelOptions,
                                  state,
                                ),
                                decoration: const InputDecoration(
                                  labelText: 'Preferred Model',
                                  border: OutlineInputBorder(),
                                ),
                                items: finalModelOptions.map((String model) {
                                  // Get model status
                                  final ModelStatus? modelStatus = state
                                      .modelStatus[_selectedLanguage]?[model];
                                  final bool isInstalled =
                                      modelStatus?.installed ?? false;

                                  // LED indicator like in Quick Settings
                                  final String ledEmoji =
                                      isInstalled ? '🟢' : '🔴';
                                  final String statusText = isInstalled
                                      ? 'Installed'
                                      : 'Not Installed';
                                  final String tooltip = isInstalled
                                      ? 'Model installed and available'
                                      : 'Model not installed';

                                  return DropdownMenuItem(
                                    value: model,
                                    child: Tooltip(
                                      message: tooltip,
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: <Widget>[
                                          Text(
                                            ledEmoji,
                                            style:
                                                const TextStyle(fontSize: 14),
                                          ),
                                          const SizedBox(width: 8),
                                          Flexible(
                                            child: Text(
                                              model,
                                              style:
                                                  const TextStyle(fontSize: 14),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            statusText,
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: isInstalled
                                                  ? Colors.green.shade700
                                                  : Colors.grey.shade600,
                                              fontWeight: FontWeight.w500,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                }).toList(),
                                onChanged: (String? value) {
                                  if (value != null) {
                                    notifier.updateLanguageModelConfig(
                                      _selectedLanguage,
                                      currentConfig.copyWith(preferred: value),
                                    );
                                  }
                                },
                              ),
                              const SizedBox(height: 16),
                              // Models Directory (Fixed path, read-only with browse button)
                              Row(
                                children: <Widget>[
                                  Expanded(
                                    child: TextField(
                                      controller: _getModelsDirController(
                                        _selectedLanguage,
                                        currentConfig,
                                      ),
                                      readOnly: true,
                                      decoration: const InputDecoration(
                                        labelText: 'Models Directory',
                                        hintText:
                                            r'C:\ProgramData\Owlangs\models\spacy',
                                        border: OutlineInputBorder(),
                                        helperText:
                                            'Fixed path for desktop version',
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  OutlinedButton.icon(
                                    onPressed: () async {
                                      // Browse directory (desktop only)
                                      if (Platform.isWindows ||
                                          Platform.isLinux ||
                                          Platform.isMacOS) {
                                        final selectedDirectory =
                                            await FilePicker.platform
                                                .getDirectoryPath();
                                        if (selectedDirectory != null) {
                                          // Note: The path is fixed, but we can show the selected directory
                                          // for reference (though it won't be saved)
                                          MessageService.showInfo(
                                            context,
                                            'Selected directory: $selectedDirectory\nNote: Model directory is fixed to C:\\ProgramData\\Owlangs\\models\\spacy',
                                          );
                                        }
                                      } else {
                                        MessageService.showInfo(
                                          context,
                                          'Directory browsing is only available on desktop platforms.',
                                        );
                                      }
                                    },
                                    icon: const Icon(Icons.folder_open),
                                    label: const Text('Browse'),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              // Fallback Option
                              SwitchListTile(
                                title: const Text('Allow fallback (lg→md→sm)'),
                                subtitle: const Text(
                                  'If preferred model is not available, try larger models first',
                                ),
                                value: currentConfig.fallback,
                                onChanged: (bool value) {
                                  notifier.updateLanguageModelConfig(
                                    _selectedLanguage,
                                    currentConfig.copyWith(fallback: value),
                                  );
                                },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Download Button
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () {
                              final String model = currentConfig.preferred;
                              if (model.isEmpty) {
                                MessageService.showWarning(
                                  context,
                                  'Please select a model first',
                                );
                                return;
                              }
                              notifier.downloadModel(
                                _selectedLanguage,
                                model,
                                currentConfig.modelsDir,
                                onProgress: (double progress) {
                                  // Progress is handled by state
                                },
                              );
                            },
                            icon: const Icon(Icons.download),
                            label: const Text('Download Model'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // Engine & Basic Settings
                Card(
                  elevation: 4,
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            Icon(Icons.settings, color: Colors.orange.shade700),
                            const SizedBox(width: 8),
                            Text(
                              'Basic Settings',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade700,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        // Engine info (Presidio only, no selection needed)
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.blue.shade50,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.blue.shade200),
                          ),
                          child: Row(
                            children: <Widget>[
                              Icon(
                                Icons.info_outline,
                                color: Colors.blue.shade700,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Using Microsoft Presidio engine for anonymization',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: Colors.blue.shade900,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Default Language
                        DropdownButtonFormField<String>(
                          initialValue: state.defaultLanguage,
                          decoration: const InputDecoration(
                            labelText: 'Default Language',
                            border: OutlineInputBorder(),
                          ),
                          items: finalAvailableLanguages.map((String lang) {
                            final String langName = LANGUAGES[lang] ?? lang;
                            return DropdownMenuItem(
                              value: lang,
                              child: Text('$langName ($lang)'),
                            );
                          }).toList(),
                          onChanged: (String? value) {
                            if (value != null) {
                              notifier.updateDefaultLanguage(value);
                            }
                          },
                        ),
                        const SizedBox(height: 16),
                        // Confidence Threshold
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: <Widget>[
                                const Text(
                                  'Confidence Threshold',
                                  style: TextStyle(fontWeight: FontWeight.w500),
                                ),
                                Text(
                                  state.confidenceThreshold.toStringAsFixed(1),
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.orange.shade700,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Slider(
                              value: state.confidenceThreshold,
                              min: 0.1,
                              divisions: 9,
                              activeColor: Colors.orange.shade700,
                              onChanged: notifier.updateConfidenceThreshold,
                            ),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: <Widget>[
                                Text(
                                  'Low (0.1)',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey.shade600,
                                  ),
                                ),
                                Text(
                                  'High (1.0)',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey.shade600,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // Test Model
                Card(
                  elevation: 4,
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            Icon(
                              Icons.bug_report,
                              color: Colors.orange.shade700,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Test Model',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade700,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          controller: _testTextController,
                          decoration: const InputDecoration(
                            labelText: 'Test Text',
                            hintText:
                                'Each line contains a language and its test text',
                            border: OutlineInputBorder(),
                            alignLabelWithHint: true,
                          ),
                          maxLines: null,
                          minLines: 10,
                          textAlignVertical: TextAlignVertical.top,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Each line contains a language name, code, and test text. Used for quick validation of models.',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade600,
                          ),
                        ),
                        const SizedBox(height: 16),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: state.testState.isTesting
                                ? null
                                : () {
                                    final String model =
                                        currentConfig.preferred;
                                    if (model.isEmpty) {
                                      MessageService.showWarning(
                                        context,
                                        'Please select a model first',
                                      );
                                      return;
                                    }
                                    // Extract test text for current language from multi-line text
                                    // Format: "Language Name (code): test text"
                                    String? testText;
                                    if (_testTextController.text.isNotEmpty) {
                                      final List<String> lines =
                                          _testTextController.text.split('\n');
                                      final String languagePattern =
                                          '($_selectedLanguage):';
                                      for (final String line in lines) {
                                        final int colonIndex =
                                            line.indexOf(languagePattern);
                                        if (colonIndex != -1) {
                                          // Extract text after the colon
                                          testText = line
                                              .substring(
                                                colonIndex +
                                                    languagePattern.length,
                                              )
                                              .trim();
                                          break;
                                        }
                                      }
                                      // Fallback: use default test text for current language
                                      if (testText == null ||
                                          testText.isEmpty) {
                                        testText = DEFAULT_TEST_TEXTS[
                                                _selectedLanguage] ??
                                            DEFAULT_TEST_TEXTS['en'];
                                      }
                                    }
                                    notifier.testModel(
                                      _selectedLanguage,
                                      model,
                                      currentConfig.modelsDir,
                                      testText,
                                    );
                                  },
                            icon: state.testState.isTesting
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        Colors.white,
                                      ),
                                    ),
                                  )
                                : const Icon(Icons.play_circle),
                            label: Text(
                              state.testState.isTesting
                                  ? 'Testing...'
                                  : 'Test Model',
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.orange.shade700,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // Save Button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: () {
                      // Settings are auto-saved, but we can show a confirmation
                      MessageService.showSuccess(
                        context,
                        'Settings saved successfully',
                      );
                    },
                    icon: const Icon(Icons.save),
                    label: const Text('Save'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.shade700,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  /// Get preferred model value with auto-selection based on priority (trf > lg > md > sm)
  String? _getPreferredModelValue(
    LanguageModelConfig currentConfig,
    List<String> finalModelOptions,
    AnonymizationSettingsState state,
  ) {
    // If current config has a valid preferred model, use it
    if (currentConfig.preferred.isNotEmpty &&
        finalModelOptions.contains(currentConfig.preferred)) {
      return currentConfig.preferred;
    }

    // Auto-select highest priority installed model
    // Priority: trf > lg > md > sm
    final List<String> priorityOrder = <String>['trf', 'lg', 'md', 'sm'];
    final Map<String, ModelStatus> langModelStatus =
        state.modelStatus[_selectedLanguage] ?? <String, ModelStatus>{};

    for (final String priority in priorityOrder) {
      // Find models with this priority suffix (e.g., _trf, _lg, _md, _sm)
      for (final String model in finalModelOptions) {
        // Check if model name contains the priority suffix
        // e.g., "zh_core_web_trf" contains "_trf"
        if (model.contains('_$priority')) {
          final ModelStatus? status = langModelStatus[model];
          if (status?.installed ?? false) {
            return model;
          }
        }
      }
    }

    // If no installed model found, return first available model
    return finalModelOptions.isNotEmpty ? finalModelOptions.first : null;
  }

  List<String> _getModelOptionsForLanguage(String language) {
    // This should be loaded from backend, but for now we'll use defaults
    const Map<String, List<String>> modelOptions = <String, List<String>>{
      'zh': <String>[
        'zh_core_web_trf',
        'zh_core_web_lg',
        'zh_core_web_md',
        'zh_core_web_sm',
      ],
      'en': <String>[
        'en_core_web_trf',
        'en_core_web_lg',
        'en_core_web_md',
        'en_core_web_sm',
      ],
      'de': <String>[
        'de_core_news_trf',
        'de_core_news_lg',
        'de_core_news_md',
        'de_core_news_sm',
      ],
      'fr': <String>[
        'fr_core_news_trf',
        'fr_core_news_lg',
        'fr_core_news_md',
        'fr_core_news_sm',
      ],
      'es': <String>[
        'es_core_news_trf',
        'es_core_news_lg',
        'es_core_news_md',
        'es_core_news_sm',
      ],
      'it': <String>[
        'it_core_news_trf',
        'it_core_news_lg',
        'it_core_news_md',
        'it_core_news_sm',
      ],
      'nl': <String>[
        'nl_core_news_trf',
        'nl_core_news_lg',
        'nl_core_news_md',
        'nl_core_news_sm',
      ],
      'pt': <String>[
        'pt_core_news_trf',
        'pt_core_news_lg',
        'pt_core_news_md',
        'pt_core_news_sm',
      ],
      'ru': <String>[
        'ru_core_news_trf',
        'ru_core_news_lg',
        'ru_core_news_md',
        'ru_core_news_sm',
      ],
      'ja': <String>[
        'ja_core_news_trf',
        'ja_core_news_lg',
        'ja_core_news_md',
        'ja_core_news_sm',
      ],
      'ko': <String>[
        'ko_core_news_trf',
        'ko_core_news_lg',
        'ko_core_news_md',
        'ko_core_news_sm',
      ],
      'pl': <String>[
        'pl_core_news_trf',
        'pl_core_news_lg',
        'pl_core_news_md',
        'pl_core_news_sm',
      ],
      'da': <String>[
        'da_core_news_trf',
        'da_core_news_lg',
        'da_core_news_md',
        'da_core_news_sm',
      ],
      'nb': <String>[
        'nb_core_news_trf',
        'nb_core_news_lg',
        'nb_core_news_md',
        'nb_core_news_sm',
      ],
      'sv': <String>[
        'sv_core_news_trf',
        'sv_core_news_lg',
        'sv_core_news_md',
        'sv_core_news_sm',
      ],
      'fi': <String>[
        'fi_core_news_trf',
        'fi_core_news_lg',
        'fi_core_news_md',
        'fi_core_news_sm',
      ],
      'el': <String>['el_core_news_sm'],
      'lt': <String>['lt_core_news_sm'],
      'ro': <String>['ro_core_news_sm'],
      'uk': <String>['uk_core_news_sm'],
      'ar': <String>['ar_core_news_sm'],
      'hi': <String>['hi_core_news_sm'],
      'th': <String>['th_core_news_sm'],
      'vi': <String>['vi_core_news_sm'],
    };
    return List<String>.from(modelOptions[language] ?? <dynamic>[]);
  }
}
