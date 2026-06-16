// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../shared/utils/language_mapper.dart';
import '../../../shared/services/glossary_api_service.dart';
import '../../../shared/services/config_service.dart' show AIPlatformInfo, ConfigService;
import '../../../shared/utils/mineru_test_result_utils.dart';
import '../../../shared/providers/settings_provider.dart'
    show globalSettingsProvider;
import '../../../features/settings/screens/ai_platform_settings.dart'
    show aiPlatformSettingsProvider;

/// Compact quick settings panel for the batch upload dialog.
///
/// Shows essential settings only — workflow-specific controls (source language,
/// MinerU parsing, Qt .ts) are excluded since batch files may have mixed types.
class BatchQuickSettingsPanel extends ConsumerStatefulWidget {
  const BatchQuickSettingsPanel({
    super.key,
    required this.toLang,
    required this.platformKey,
    required this.temperature,
    required this.promptMode,
    this.promptStyle,
    this.taskNote,
    required this.selectedGlossaries,
    required this.onToLangChanged,
    required this.onPlatformChanged,
    required this.onTemperatureChanged,
    required this.onPromptModeChanged,
    required this.onPromptStyleChanged,
    required this.onTaskNoteChanged,
    required this.onGlossariesChanged,
    this.parsingEngine = 'mineru',
    this.onParsingEngineChanged,
  });

  final String toLang;
  final String platformKey;
  final double? temperature;
  final String promptMode;
  final String? promptStyle;
  final String? taskNote;
  final List<String> selectedGlossaries;

  final ValueChanged<String> onToLangChanged;
  final ValueChanged<String> onPlatformChanged;
  final ValueChanged<double> onTemperatureChanged;
  final ValueChanged<String> onPromptModeChanged;
  final ValueChanged<String?> onPromptStyleChanged;
  final ValueChanged<String?> onTaskNoteChanged;
  final ValueChanged<List<String>> onGlossariesChanged;

  final String parsingEngine;
  final ValueChanged<String>? onParsingEngineChanged;

  @override
  ConsumerState<BatchQuickSettingsPanel> createState() =>
      _BatchQuickSettingsPanelState();
}

class _BatchQuickSettingsPanelState
    extends ConsumerState<BatchQuickSettingsPanel> {
  bool _temperatureExpanded = false;
  bool _glossaryExpanded = false;
  Future<List<Map<String, dynamic>>>? _glossariesFuture;
  List<Map<String, dynamic>>? _cachedGlossaries;

  // Target language entries (same list as translation_quick_settings.dart)
  static const List<Map<String, String>> _languageEntries = <Map<String, String>>[
    <String, String>{'code': 'ar', 'native': 'العربية'},
    <String, String>{'code': 'bn', 'native': 'বাংলা'},
    <String, String>{'code': 'ca', 'native': 'Català'},
    <String, String>{'code': 'zh', 'native': '中文'},
    <String, String>{'code': 'zh-TW', 'native': '繁體中文'},
    <String, String>{'code': 'cs', 'native': 'Čeština'},
    <String, String>{'code': 'hr', 'native': 'Hrvatski'},
    <String, String>{'code': 'da', 'native': 'Dansk'},
    <String, String>{'code': 'nl', 'native': 'Nederlands'},
    <String, String>{'code': 'en', 'native': 'English'},
    <String, String>{'code': 'fil', 'native': 'Filipino'},
    <String, String>{'code': 'fi', 'native': 'Suomi'},
    <String, String>{'code': 'fr', 'native': 'Français'},
    <String, String>{'code': 'de', 'native': 'Deutsch'},
    <String, String>{'code': 'el', 'native': 'Ελληνικά'},
    <String, String>{'code': 'he', 'native': 'עברית'},
    <String, String>{'code': 'hi', 'native': 'हिन्दी'},
    <String, String>{'code': 'it', 'native': 'Italiano'},
    <String, String>{'code': 'ja', 'native': '日本語'},
    <String, String>{'code': 'ko', 'native': '한국어'},
    <String, String>{'code': 'km', 'native': 'ភាសាខ្មែរ'},
    <String, String>{'code': 'lt', 'native': 'Lietuvių'},
    <String, String>{'code': 'mk', 'native': 'Македонски'},
    <String, String>{'code': 'ms', 'native': 'Bahasa Melayu'},
    <String, String>{'code': 'nb', 'native': 'Norwegian Bokmål'},
    <String, String>{'code': 'pl', 'native': 'Polski'},
    <String, String>{'code': 'pt', 'native': 'Português'},
    <String, String>{'code': 'ro', 'native': 'Română'},
    <String, String>{'code': 'ru', 'native': 'Русский'},
    <String, String>{'code': 'sl', 'native': 'Slovenščina'},
    <String, String>{'code': 'es', 'native': 'Español'},
    <String, String>{'code': 'sv', 'native': 'Svenska'},
    <String, String>{'code': 'th', 'native': 'ไทย'},
    <String, String>{'code': 'tr', 'native': 'Türkçe'},
    <String, String>{'code': 'uk', 'native': 'Українська'},
    <String, String>{'code': 'ur', 'native': 'اردو'},
    <String, String>{'code': 'vi', 'native': 'Tiếng Việt'},
  ];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // Parsing Engine (MinerU) — placed at top like Immersive Translation
          _buildParsingEngineSection(l10n, theme),
          const SizedBox(height: 12),

          // Target Language
          _buildLabel(l10n.quickSettingsTargetLanguage),
          const SizedBox(height: 4),
          _buildLanguageDropdown(l10n),
          const SizedBox(height: 12),

          // AI Platform
          _buildAIPlatformSection(l10n, theme),
          const SizedBox(height: 12),

          // Temperature
          _buildTemperatureSection(l10n, theme),
          const SizedBox(height: 12),

          // Prompt Mode
          _buildLabel(l10n.quickSettingsPromptMode),
          const SizedBox(height: 4),
          _buildPromptModeDropdown(l10n),
          if (widget.promptMode != 'off') ...[
            const SizedBox(height: 8),
            _buildLabel(l10n.quickSettingsStyle),
            const SizedBox(height: 4),
            _buildPromptStyleDropdown(l10n),
          ],
          if (widget.promptMode == 'advanced') ...[
            const SizedBox(height: 8),
            _buildLabel(l10n.quickSettingsTaskNoteLabel),
            const SizedBox(height: 4),
            _buildTaskNoteField(l10n),
          ],
          const SizedBox(height: 12),

          // Glossaries
          _buildGlossarySection(l10n, theme),
        ],
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Text(
      text,
      style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
    );
  }

  // ── Target Language ──────────────────────────────────────────────

  Widget _buildLanguageDropdown(AppLocalizations l10n) {
    return DropdownButtonFormField<String>(
      initialValue: widget.toLang,
      isExpanded: true,
      decoration: const InputDecoration(
        border: OutlineInputBorder(),
        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        isDense: true,
      ),
      items: _languageEntries
          .map(
            (Map<String, String> lang) => DropdownMenuItem<String>(
              value: lang['code'],
              child: Text(
                languageDisplayName(l10n, lang['code']!),
                style: const TextStyle(fontSize: 13),
              ),
            ),
          )
          .toList(),
      onChanged: (String? value) {
        if (value != null) widget.onToLangChanged(value);
      },
    );
  }

  // ── AI Platform ──────────────────────────────────────────────────

  Widget _buildAIPlatformSection(AppLocalizations l10n, ThemeData theme) {
    final aiSettings = ref.watch(aiPlatformSettingsProvider);
    final aiNotifier = ref.read(aiPlatformSettingsProvider.notifier);
    final allPlatforms = aiSettings.platforms.values.toList();
    var llmPlatforms = allPlatforms
        .where((AIPlatformInfo p) => p.platformType == 'llm')
        .toList();
    if (llmPlatforms.isEmpty) {
      llmPlatforms = allPlatforms;
    }
    final current = widget.platformKey;
    final validSelected =
        llmPlatforms.any((AIPlatformInfo p) => p.key == current) ? current : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.quickSettingsLlmPlatform,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
            ),
            const Spacer(),
            Tooltip(
              message: l10n.quickSettingsTestLlmPlatform,
              child: IconButton(
                icon: const Icon(Icons.wifi_tethering, size: 18),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                onPressed: validSelected == null
                    ? null
                    : () async {
                        final platformKey = validSelected;
                        final info = aiSettings.platforms[platformKey];
                        try {
                          final result = await ConfigService().testAIPlatform(
                            platformKey,
                            '',
                            baseUrl: info?.url,
                            modelName: info?.model,
                          );
                          await aiNotifier.refreshPlatformStatus();
                          if (!context.mounted) return;
                          final success = result?['success'] == true;
                          final platformLabel = info?.name ?? platformKey;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                l10n.quickSettingsPlatformMessage(
                                  platformLabel,
                                  result?['message']?.toString() ?? (success ? l10n.quickSettingsConnectionSuccessful : l10n.quickSettingsTestFailed),
                                ),
                              ),
                              duration: const Duration(seconds: 3),
                              backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        } catch (e) {
                          await aiNotifier.refreshPlatformStatus();
                          if (!context.mounted) return;
                          final platformLabel = info?.name ?? platformKey;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(l10n.quickSettingsPlatformTestFailed(platformLabel, e.toString())),
                              backgroundColor: Colors.red.shade700,
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        DropdownButtonFormField<String>(
          initialValue: validSelected,
          isExpanded: true,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            isDense: true,
          ),
          items: llmPlatforms.map((AIPlatformInfo p) {
            final Color dotColor;
            if (p.isApiAvailable == true) {
              dotColor = Colors.green;
            } else if (p.isApiAvailable == false) {
              dotColor = Colors.red;
            } else {
              dotColor = Colors.grey;
            }
            return DropdownMenuItem<String>(
              value: p.key,
              child: Row(
                children: <Widget>[
                  Icon(Icons.circle, size: 8, color: dotColor),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      p.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
          onChanged: (String? value) {
            if (value != null) {
              widget.onPlatformChanged(value);
              // Reset temperature when platform changes
              final platform = aiSettings.platforms[value];
              if (platform != null && platform.temperature != null) {
                widget.onTemperatureChanged(platform.temperature!);
              }
            }
          },
        ),
      ],
    );
  }

  // ── Temperature ──────────────────────────────────────────────────

  Widget _buildTemperatureSection(AppLocalizations l10n, ThemeData theme) {
    final globalSettings = ref.watch(globalSettingsProvider);
    final aiSettings = ref.watch(aiPlatformSettingsProvider);
    final platform = aiSettings.platforms[widget.platformKey];
    final tempMin = platform?.temperatureMin ?? 0.0;
    final tempMax = platform?.temperatureMax ?? 2.0;
    final currentTemp = widget.temperature ??
        globalSettings.temperature ??
        0.3;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        InkWell(
          onTap: () => setState(() => _temperatureExpanded = !_temperatureExpanded),
          child: Row(
            children: <Widget>[
              Text(
                l10n.quickSettingsTemperature,
                style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  currentTemp.toStringAsFixed(2),
                  style: TextStyle(fontSize: 12, color: theme.colorScheme.primary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Spacer(),
              Icon(
                _temperatureExpanded ? Icons.expand_less : Icons.expand_more,
                size: 18,
              ),
            ],
          ),
        ),
        if (_temperatureExpanded) ...[
          const SizedBox(height: 4),
          Slider(
            value: currentTemp.clamp(tempMin, tempMax),
            min: tempMin,
            max: tempMax,
            divisions: ((tempMax - tempMin) * 10).round().clamp(1, 100),
            label: currentTemp.toStringAsFixed(2),
            onChanged: (double v) => widget.onTemperatureChanged(v),
          ),
        ],
      ],
    );
  }

  // ── Prompt Mode / Style ──────────────────────────────────────────

  Widget _buildPromptModeDropdown(AppLocalizations l10n) {
    return DropdownButtonFormField<String>(
      initialValue: widget.promptMode,
      isExpanded: true,
      decoration: const InputDecoration(
        border: OutlineInputBorder(),
        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        isDense: true,
      ),
      items: <DropdownMenuItem<String>>[
        DropdownMenuItem<String>(
          value: 'off',
          child: Text(l10n.quickSettingsPromptModeOff, style: const TextStyle(fontSize: 13)),
        ),
        DropdownMenuItem<String>(
          value: 'simple',
          child: Text(l10n.quickSettingsPromptModeSimple, style: const TextStyle(fontSize: 13)),
        ),
        DropdownMenuItem<String>(
          value: 'advanced',
          child: Text(l10n.quickSettingsPromptModeAdvanced, style: const TextStyle(fontSize: 13)),
        ),
      ],
      onChanged: (String? value) {
        if (value != null) widget.onPromptModeChanged(value);
      },
    );
  }

  Widget _buildPromptStyleDropdown(AppLocalizations l10n) {
    final styles = <Map<String, String?>>[
      <String, String?>{'code': null, 'label': l10n.quickSettingsStyleNone},
      <String, String?>{'code': 'literal', 'label': l10n.quickSettingsStyleLiteral},
      <String, String?>{'code': 'fluent', 'label': l10n.quickSettingsStyleFluent},
      <String, String?>{'code': 'academic', 'label': l10n.quickSettingsStyleAcademic},
      <String, String?>{'code': 'business', 'label': l10n.quickSettingsStyleBusiness},
      <String, String?>{'code': 'technical', 'label': l10n.quickSettingsStyleTechnical},
    ];
    return DropdownButtonFormField<String?>(
      initialValue: widget.promptStyle,
      isExpanded: true,
      decoration: const InputDecoration(
        border: OutlineInputBorder(),
        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        isDense: true,
      ),
      items: styles
          .map(
            (s) => DropdownMenuItem<String?>(
              value: s['code'],
              child: Text(s['label']!, style: const TextStyle(fontSize: 13)),
            ),
          )
          .toList(),
      onChanged: (String? value) => widget.onPromptStyleChanged(value),
    );
  }

  // ── Task Note ────────────────────────────────────────────────────

  Widget _buildTaskNoteField(AppLocalizations l10n) {
    return TextField(
      controller: TextEditingController(text: widget.taskNote ?? '')
        ..selection = TextSelection.collapsed(offset: (widget.taskNote ?? '').length),
      decoration: InputDecoration(
        hintText: l10n.quickSettingsTaskNoteHint,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        isDense: true,
      ),
      style: const TextStyle(fontSize: 13),
      maxLines: 2,
      minLines: 1,
      onChanged: widget.onTaskNoteChanged,
    );
  }

  // ── Parsing Engine ───────────────────────────────────────────────

  Widget _buildParsingEngineSection(AppLocalizations l10n, ThemeData theme) {
    final aiSettings = ref.watch(aiPlatformSettingsProvider);
    final aiNotifier = ref.read(aiPlatformSettingsProvider.notifier);
    final parserOptions = <String>['mineru', 'mineru_local'];
    final selectedParser = widget.parsingEngine;

    Color parserStatusColor(String key) {
      final info = aiSettings.platforms[key];
      final available = info?.isApiAvailable;
      if (available == true) return Colors.green;
      if (available == false) return Colors.red;
      return Colors.grey;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.quickSettingsParsingPlatform,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
            ),
            const Spacer(),
            Tooltip(
              message: l10n.quickSettingsTestMineru,
              child: IconButton(
                icon: const Icon(Icons.wifi_tethering, size: 18),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                onPressed: () async {
                  try {
                    final result = await ConfigService().testAIPlatform(
                      selectedParser,
                      selectedParser == 'mineru_local'
                          ? (aiSettings.platforms['mineru_local']?.apiKey ?? '')
                          : '',
                      baseUrl: aiSettings.platforms[selectedParser]?.url,
                    );
                    await aiNotifier.refreshPlatformStatus();
                    if (!context.mounted) return;
                    final success = result?['success'] == true;
                    final testLabel = selectedParser == 'mineru_local'
                        ? l10n.batchUploadMineruLocal
                        : l10n.batchUploadMineru;
                    final String detailMessage = success
                        ? buildMinerUTestSuccessMessage(l10n, result)
                        : (result?['message']?.toString() ??
                            l10n.quickSettingsMineruConnectionFailed);
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          l10n.quickSettingsPlatformMessage(
                            testLabel,
                            detailMessage,
                          ),
                        ),
                        duration: const Duration(seconds: 3),
                        backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
                        behavior: SnackBarBehavior.floating,
                      ),
                    );
                  } catch (e) {
                    await aiNotifier.refreshPlatformStatus();
                    if (!context.mounted) return;
                    final testLabel = selectedParser == 'mineru_local'
                        ? l10n.batchUploadMineruLocal
                        : l10n.batchUploadMineru;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(l10n.quickSettingsPlatformTestFailed(testLabel, e.toString())),
                        backgroundColor: Colors.red.shade700,
                        behavior: SnackBarBehavior.floating,
                      ),
                    );
                  }
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        DropdownButtonFormField<String>(
          key: ValueKey<String>('parser:$selectedParser'),
          initialValue: parserOptions.contains(selectedParser) ? selectedParser : parserOptions.first,
          isExpanded: true,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            isDense: true,
          ),
          items: parserOptions.map((String code) {
            final info = aiSettings.platforms[code];
            final color = parserStatusColor(code);
            final String label = info?.name.isNotEmpty == true
                ? info!.name
                : (code == 'mineru_local' ? l10n.batchUploadMineruLocal : l10n.batchUploadMineru);
            return DropdownMenuItem<String>(
              value: code,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(Icons.circle, size: 8, color: color),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      label,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
          onChanged: (v) {
            if (v != null) widget.onParsingEngineChanged?.call(v);
          },
        ),
      ],
    );
  }

  // ── Glossaries ───────────────────────────────────────────────────

  Widget _buildGlossarySection(AppLocalizations l10n, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        InkWell(
          onTap: () {
            setState(() {
              _glossaryExpanded = !_glossaryExpanded;
              if (_glossaryExpanded && _glossariesFuture == null) {
                _glossariesFuture = GlossaryApiService.getSimpleGlossaryList();
              }
            });
          },
          child: Row(
            children: <Widget>[
              Text(
                l10n.batchUploadGlossarySection,
                style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 12),
              ),
              const SizedBox(width: 8),
              if (widget.selectedGlossaries.isNotEmpty)
                Expanded(
                  child: Text(
                    _buildSelectedGlossaryNames(l10n),
                    style: TextStyle(
                      fontSize: 12,
                      color: theme.colorScheme.primary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              const Spacer(),
              Icon(
                _glossaryExpanded ? Icons.expand_less : Icons.expand_more,
                size: 18,
              ),
            ],
          ),
        ),
        if (_glossaryExpanded) ...[
          const SizedBox(height: 4),
          _buildGlossaryList(l10n),
        ],
      ],
    );
  }

  String _buildSelectedGlossaryNames(AppLocalizations l10n) {
    if (widget.selectedGlossaries.isEmpty) {
      return '';
    }
    final names = <String>[];
    for (final id in widget.selectedGlossaries) {
      try {
        final match = _cachedGlossaries?.firstWhere(
          (g) => g['id'].toString() == id,
        );
        if (match != null && match['name'] != null) {
          names.add(match['name'].toString());
        } else {
          names.add(id);
        }
      } catch (_) {
        names.add(id);
      }
    }
    if (names.length <= 3) {
      return names.join(', ');
    }
    return '${names.take(3).join(', ')} ${l10n.batchUploadGlossaryMore(names.length - 3)}';
  }

  Widget _buildGlossaryList(AppLocalizations l10n) {
    if (_glossariesFuture == null) return const SizedBox.shrink();

    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _glossariesFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.all(8),
            child: LinearProgressIndicator(),
          );
        }
        if (snapshot.hasError) {
          return Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              l10n.batchUploadGlossaryLoadError(snapshot.error.toString()),
              style: const TextStyle(fontSize: 11, color: Colors.red),
            ),
          );
        }
        final glossaries = snapshot.data ?? <Map<String, dynamic>>[];
        if (_cachedGlossaries == null) {
          _cachedGlossaries = glossaries;
        }
        if (glossaries.isEmpty) {
          return Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              l10n.batchUploadNoGlossaries,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          );
        }

        return ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 150),
          child: ListView(
            shrinkWrap: true,
            children: glossaries.map((g) {
              final id = g['id']?.toString() ?? '';
              final name = g['name']?.toString() ?? id;
              final checked = widget.selectedGlossaries.contains(id);
              return CheckboxListTile(
                value: checked,
                onChanged: (v) {
                  final updated = List<String>.from(widget.selectedGlossaries);
                  if (v == true) {
                    if (!updated.contains(id)) updated.add(id);
                  } else {
                    updated.remove(id);
                  }
                  widget.onGlossariesChanged(updated);
                },
                dense: true,
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
                title: Text(
                  name,
                  style: const TextStyle(fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }).toList(),
          ),
        );
      },
    );
  }
}
