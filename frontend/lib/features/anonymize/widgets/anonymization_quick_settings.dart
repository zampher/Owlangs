import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

// Anonymization Quick Settings 状态管理
final StateNotifierProvider<AnonymizationQuickSettingsNotifier,
        AnonymizationQuickSettings> anonymizationQuickSettingsProvider =
    StateNotifierProvider<AnonymizationQuickSettingsNotifier,
        AnonymizationQuickSettings>(
  (
    ref,
  ) =>
      AnonymizationQuickSettingsNotifier(),
);

final StateNotifierProviderFamily<AnonymizationQuickSettingsNotifier,
        AnonymizationQuickSettings, String>
    anonymizationQuickSettingsProviderFamily = StateNotifierProvider.family<
        AnonymizationQuickSettingsNotifier,
        AnonymizationQuickSettings,
        String>((
  ref,
  flowId,
) {
  // Keep provider alive to avoid reloading when switching flows
  ref.keepAlive();
  return AnonymizationQuickSettingsNotifier(flowId: flowId);
});

class AnonymizationQuickSettings {
  // Advanced settings expansion state

  const AnonymizationQuickSettings({
    this.detectionLanguage = 'auto',
    this.detectedLanguage,
    this.anonymizeMode = 'placeholder',
    this.anonymizeConfidence = 0.5,
    this.customPlaceholder,
    this.selectedEntityTypes = const <String>[
      'PERSON',
      'EMAIL_ADDRESS',
      'PHONE_NUMBER',
      'LOCATION',
      'ORGANIZATION',
    ],
    this.showMoreGlobal = false,
    this.showRegional = false,
    this.advancedSettingsExpanded = false,
  });

  factory AnonymizationQuickSettings.fromJson(Map<String, dynamic> json) =>
      AnonymizationQuickSettings(
        detectionLanguage: json['detectionLanguage'] ?? 'auto',
        detectedLanguage: json['detectedLanguage'],
        anonymizeMode: json['anonymizeMode'] ?? 'placeholder',
        anonymizeConfidence:
            (json['anonymizeConfidence'] as num?)?.toDouble() ?? 0.5,
        customPlaceholder: json['customPlaceholder'],
        selectedEntityTypes: List<String>.from(
          json['selectedEntityTypes'] ??
              <dynamic>[
                'PERSON',
                'EMAIL_ADDRESS',
                'PHONE_NUMBER',
                'LOCATION',
                'ORGANIZATION',
              ],
        ),
        showMoreGlobal: json['showMoreGlobal'] ?? false,
        showRegional: json['showRegional'] ?? false,
        advancedSettingsExpanded: json['advancedSettingsExpanded'] ?? false,
      );
  // General Settings
  final String detectionLanguage; // auto + spaCy-supported languages
  final String?
      detectedLanguage; // Detected language from workflow (e.g., "zh", "en")
  final String anonymizeMode; // placeholder/mask/type/custom
  final double anonymizeConfidence; // 0.1-1.0
  final String? customPlaceholder; // Custom placeholder text (when mode=custom)

  // Entity Types
  final List<String>
      selectedEntityTypes; // All selected entity types (global + regional)

  // UI State
  final bool showMoreGlobal; // Show more global entity types
  final bool showRegional; // Show regional entity types
  final bool advancedSettingsExpanded;

  AnonymizationQuickSettings copyWith({
    String? detectionLanguage,
    String? detectedLanguage,
    String? anonymizeMode,
    double? anonymizeConfidence,
    String? customPlaceholder,
    List<String>? selectedEntityTypes,
    bool? showMoreGlobal,
    bool? showRegional,
    bool? advancedSettingsExpanded,
  }) =>
      AnonymizationQuickSettings(
        detectionLanguage: detectionLanguage ?? this.detectionLanguage,
        detectedLanguage: detectedLanguage ?? this.detectedLanguage,
        anonymizeMode: anonymizeMode ?? this.anonymizeMode,
        anonymizeConfidence: anonymizeConfidence ?? this.anonymizeConfidence,
        customPlaceholder: customPlaceholder ?? this.customPlaceholder,
        selectedEntityTypes: selectedEntityTypes ?? this.selectedEntityTypes,
        showMoreGlobal: showMoreGlobal ?? this.showMoreGlobal,
        showRegional: showRegional ?? this.showRegional,
        advancedSettingsExpanded:
            advancedSettingsExpanded ?? this.advancedSettingsExpanded,
      );

  Map<String, dynamic> toJson() => <String, dynamic>{
        'detectionLanguage': detectionLanguage,
        'detectedLanguage': detectedLanguage,
        'anonymizeMode': anonymizeMode,
        'anonymizeConfidence': anonymizeConfidence,
        'customPlaceholder': customPlaceholder,
        'selectedEntityTypes': selectedEntityTypes,
        'showMoreGlobal': showMoreGlobal,
        'showRegional': showRegional,
        'advancedSettingsExpanded': advancedSettingsExpanded,
      };
}

class AnonymizationQuickSettingsNotifier
    extends StateNotifier<AnonymizationQuickSettings> {
  AnonymizationQuickSettingsNotifier({this.flowId})
      : super(const AnonymizationQuickSettings()) {
    _loadSettings();
  }
  final String? flowId;

  Future<void> _loadSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = flowId == null
          ? 'anonymization_quick_settings'
          : 'anonymization_quick_settings_$flowId';
      final settingsJson = prefs.getString(key);
      if (settingsJson != null) {
        final settingsMap = jsonDecode(settingsJson) as Map<String, dynamic>;
        state = AnonymizationQuickSettings.fromJson(settingsMap);
      }
    } catch (e) {
      // If loading fails, use default settings
      debugPrint('Error loading anonymization quick settings: $e');
    }
  }

  Future<void> _saveSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final settingsJson = jsonEncode(state.toJson());
      final key = flowId == null
          ? 'anonymization_quick_settings'
          : 'anonymization_quick_settings_$flowId';
      await prefs.setString(key, settingsJson);
    } catch (e) {
      debugPrint('Error saving anonymization quick settings: $e');
    }
  }

  void updateDetectionLanguage(String language) {
    state = state.copyWith(detectionLanguage: language);
    _saveSettings();
  }

  void updateDetectedLanguage(String? language) {
    state = state.copyWith(detectedLanguage: language);
    _saveSettings();
  }

  void updateAnonymizeMode(String mode) {
    state = state.copyWith(anonymizeMode: mode);
    _saveSettings();
  }

  void updateAnonymizeConfidence(double confidence) {
    state = state.copyWith(anonymizeConfidence: confidence);
    _saveSettings();
  }

  void updateCustomPlaceholder(String? placeholder) {
    state = state.copyWith(customPlaceholder: placeholder);
    _saveSettings();
  }

  void toggleEntityType(String entityType) {
    final current = List<String>.from(state.selectedEntityTypes);
    if (current.contains(entityType)) {
      current.remove(entityType);
    } else {
      current.add(entityType);
    }
    state = state.copyWith(selectedEntityTypes: current);
    _saveSettings();
  }

  void setShowMoreGlobal(bool show) {
    state = state.copyWith(showMoreGlobal: show);
    _saveSettings();
  }

  void setShowRegional(bool show) {
    state = state.copyWith(showRegional: show);
    _saveSettings();
  }

  void setAdvancedSettingsExpanded(bool expanded) {
    state = state.copyWith(advancedSettingsExpanded: expanded);
    _saveSettings();
  }

  void reset() {
    state = const AnonymizationQuickSettings();
    _saveSettings();
  }
}

// Entity type definitions
const List<Map<String, String>> BASIC_ENTITY_TYPES = <Map<String, String>>[
  <String, String>{'code': 'PERSON', 'name': 'Person Names'},
  <String, String>{'code': 'EMAIL_ADDRESS', 'name': 'Email Addresses'},
  <String, String>{'code': 'PHONE_NUMBER', 'name': 'Phone Numbers'},
  <String, String>{'code': 'LOCATION', 'name': 'Locations'},
  <String, String>{'code': 'ORGANIZATION', 'name': 'Organizations'},
];

const List<Map<String, String>> MORE_GLOBAL_ENTITY_TYPES =
    <Map<String, String>>[
  <String, String>{'code': 'CREDIT_CARD', 'name': 'Credit Cards'},
  <String, String>{'code': 'DATE_TIME', 'name': 'Dates & Times'},
  <String, String>{'code': 'URL', 'name': 'URLs'},
  <String, String>{'code': 'IP_ADDRESS', 'name': 'IP Addresses'},
  <String, String>{'code': 'MEDICAL_LICENSE', 'name': 'Medical License'},
  <String, String>{'code': 'US_NPI', 'name': 'US NPI'},
  <String, String>{'code': 'TITLE', 'name': 'Titles/Positions'},
  <String, String>{'code': 'IBAN_CODE', 'name': 'IBAN'},
  <String, String>{'code': 'ROUTING_NUMBER', 'name': 'Routing Numbers'},
  <String, String>{'code': 'CRYPTO', 'name': 'Cryptocurrency'},
  <String, String>{'code': 'CRYPTO_WALLET', 'name': 'Crypto Wallets'},
  <String, String>{'code': 'PRODUCT', 'name': 'Products'},
  <String, String>{'code': 'PERCENT', 'name': 'Percentages'},
  <String, String>{'code': 'MONEY', 'name': 'Money'},
  <String, String>{'code': 'QUANTITY', 'name': 'Quantities'},
  <String, String>{'code': 'ORDINAL', 'name': 'Ordinals'},
  <String, String>{'code': 'CARDINAL', 'name': 'Cardinals'},
  <String, String>{'code': 'LAW', 'name': 'Laws'},
  <String, String>{'code': 'GPE', 'name': 'Geopolitical Entities'},
  <String, String>{'code': 'FAC', 'name': 'Facilities'},
  <String, String>{
    'code': 'NRP',
    'name': 'Nationalities/Religions/Political Groups',
  },
];

const Map<String, Map<String, String>> REGIONAL_ENTITY_TYPES =
    <String, Map<String, String>>{
  'US': <String, String>{
    'US_SSN': 'Social Security Number',
    'US_DRIVER_LICENSE': 'Driver License',
    'US_PASSPORT': 'US Passport',
    'US_BANK_ACCOUNT': 'Bank Account',
  },
  'EU': <String, String>{
    'EU_ID': 'EU ID',
    'EU_PASSPORT': 'EU Passport',
    'EU_IBAN': 'EU IBAN',
    'EU_DRIVER_LICENSE': 'EU Driver License',
  },
  'CN': <String, String>{
    'CN_ID_CARD': 'ID Card (18 digits)',
    'CN_PASSPORT': 'CN Passport',
    'CN_DRIVER_LICENSE': 'CN Driver License',
    'CN_BANK_ACCOUNT': 'CN Bank Card',
  },
  'JP': <String, String>{
    'JP_MY_NUMBER': 'My Number',
    'JP_PASSPORT': 'JP Passport',
  },
  'KR': <String, String>{
    'KR_RRN': 'Resident Registration Number',
    'KR_PASSPORT': 'KR Passport',
  },
  'OTHER': <String, String>{
    'UK_NINO': 'UK NINO',
    'CA_SIN': 'CA SIN',
    'AU_TFN': 'AU TFN',
    'IN_PAN': 'IN PAN',
  },
};

const Map<String, String> LANGUAGE_NAMES = <String, String>{
  'auto': 'Auto-detect',
  'ar': 'Arabic (العربية)',
  'ca': 'Catalan (Català)',
  'zh': 'Chinese (中文)',
  'hr': 'Croatian (Hrvatski)',
  'da': 'Danish (Dansk)',
  'nl': 'Dutch (Nederlands)',
  'en': 'English (English)',
  'fi': 'Finnish (Suomi)',
  'fr': 'French (Français)',
  'de': 'German (Deutsch)',
  'el': 'Greek (Ελληνικά)',
  'it': 'Italian (Italiano)',
  'ja': 'Japanese (日本語)',
  'ko': 'Korean (한국어)',
  'lt': 'Lithuanian (Lietuvių)',
  'mk': 'Macedonian (Македонски)',
  'xx': 'Multi-language',
  'nb': 'Norwegian Bokmål',
  'pl': 'Polish (Polski)',
  'pt': 'Portuguese (Português)',
  'ro': 'Romanian (Română)',
  'ru': 'Russian (Русский)',
  'sl': 'Slovenian (Slovenščina)',
  'es': 'Spanish (Español)',
  'sv': 'Swedish (Svenska)',
  'uk': 'Ukrainian (Українська)',
};

class AnonymizationQuickSettingsWidget extends ConsumerStatefulWidget {
  const AnonymizationQuickSettingsWidget({super.key, this.flowId});
  final String? flowId;

  @override
  ConsumerState<AnonymizationQuickSettingsWidget> createState() =>
      _AnonymizationQuickSettingsWidgetState();
}

class _AnonymizationQuickSettingsWidgetState
    extends ConsumerState<AnonymizationQuickSettingsWidget> {
  @override
  Widget build(BuildContext context) {
    final settings = widget.flowId != null
        ? ref.watch(anonymizationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(anonymizationQuickSettingsProvider);
    final notifier = widget.flowId != null
        ? ref.read(
            anonymizationQuickSettingsProviderFamily(widget.flowId!).notifier,
          )
        : ref.read(anonymizationQuickSettingsProvider.notifier);

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // Header
            Row(
              children: <Widget>[
                Icon(Icons.settings, color: Colors.blue.shade700, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Anonymization Quick Settings',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.blue.shade700,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Detection Language
            _buildDetectionLanguage(settings, notifier),
            const SizedBox(height: 16),

            // Entity Types Selector
            _buildEntityTypesSelector(settings, notifier),
            const SizedBox(height: 16),

            // Anonymization Mode
            _buildAnonymizationMode(settings, notifier),
            const SizedBox(height: 16),

            // Advanced Settings
            _buildAdvancedSettings(settings, notifier),
          ],
        ),
      ),
    );
  }

  Widget _buildDetectionLanguage(
    AnonymizationQuickSettings settings,
    AnonymizationQuickSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            'Detection Language',
            style: TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) =>
                DropdownButtonFormField<String>(
              initialValue: settings.detectionLanguage,
              isExpanded: true,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              items:
                  LANGUAGE_NAMES.entries.map<DropdownMenuItem<String>>((entry) {
                String itemText = entry.value;
                if (entry.key == 'auto' && settings.detectedLanguage != null) {
                  final detectedName =
                      LANGUAGE_NAMES[settings.detectedLanguage] ??
                          settings.detectedLanguage!.toUpperCase();
                  itemText = 'Auto-detect ($detectedName)';
                }
                return DropdownMenuItem(
                  value: entry.key,
                  child: Text(
                    itemText,
                    overflow: TextOverflow.ellipsis,
                  ),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null) {
                  notifier.updateDetectionLanguage(value);
                }
              },
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Language for entity detection',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey.shade600,
            ),
          ),
        ],
      );

  Widget _buildEntityTypesSelector(
    AnonymizationQuickSettings settings,
    AnonymizationQuickSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            'Entity Types to Detect',
            style: TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 12),

          // Basic Types (always visible)
          _buildEntityTypeChips(
            'Basic Types',
            BASIC_ENTITY_TYPES,
            settings.selectedEntityTypes,
            notifier,
          ),

          const SizedBox(height: 8),

          // Show More button
          if (!settings.showMoreGlobal)
            TextButton.icon(
              onPressed: () => notifier.setShowMoreGlobal(true),
              icon: const Icon(Icons.expand_more, size: 18),
              label: const Text('Show More...'),
              style: TextButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
            ),

          // More Global Entity Types (conditional)
          if (settings.showMoreGlobal) ...<Widget>[
            ExpansionTile(
              title: const Text('More Entity Types'),
              initiallyExpanded: true,
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _buildEntityTypeChips(
                    '',
                    MORE_GLOBAL_ENTITY_TYPES,
                    settings.selectedEntityTypes,
                    notifier,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],

          // Show All button
          if (!settings.showRegional)
            TextButton.icon(
              onPressed: () => notifier.setShowRegional(true),
              icon: const Icon(Icons.expand_more, size: 18),
              label: const Text('Show All (including Regional)...'),
              style: TextButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
            ),

          // Regional Entities (conditional)
          if (settings.showRegional) ...<Widget>[
            ExpansionTile(
              title: const Text('Regional Entities'),
              initiallyExpanded: true,
              children: <Widget>[
                ...REGIONAL_ENTITY_TYPES.entries.map<Widget>(
                  (MapEntry<String, Map<String, String>> region) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          _getRegionName(region.key),
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 8),
                        _buildEntityTypeChips(
                          '',
                          region.value.entries
                              .map((e) => <String, String>{
                                    'code': e.key,
                                    'name': e.value,
                                  },)
                              .toList(),
                          settings.selectedEntityTypes,
                          notifier,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      );

  String _getRegionName(String regionCode) {
    switch (regionCode) {
      case 'US':
        return '🇺🇸 United States (US)';
      case 'EU':
        return '🇪🇺 European Union (EU)';
      case 'CN':
        return '🇨🇳 China (CN)';
      case 'JP':
        return '🇯🇵 Japan (JP)';
      case 'KR':
        return '🇰🇷 Korea (KR)';
      case 'OTHER':
        return '🌍 Other Regions';
      default:
        return regionCode;
    }
  }

  Widget _buildEntityTypeChips(
    String title,
    List<Map<String, String>> entityTypes,
    List<String> selectedTypes,
    AnonymizationQuickSettingsNotifier notifier,
  ) {
    if (entityTypes.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        if (title.isNotEmpty) ...<Widget>[
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
        ],
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: entityTypes.map<Widget>((entity) {
            final isSelected = selectedTypes.contains(entity['code']);
            final isDark = Theme.of(context).brightness == Brightness.dark;
            return FilterChip(
              label: Text(entity['name']!),
              selected: isSelected,
              onSelected: (bool selected) {
                notifier.toggleEntityType(entity['code']!);
              },
              selectedColor: isDark
                  ? Colors.blue.shade800.withOpacity(0.4)
                  : Colors.blue.shade50,
              checkmarkColor:
                  isDark ? Colors.blue.shade200 : Colors.blue.shade700,
              labelStyle: TextStyle(
                color: isSelected
                    ? (isDark ? Colors.blue.shade100 : Colors.blue.shade900)
                    : Theme.of(context).colorScheme.onSurface,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildAnonymizationMode(
    AnonymizationQuickSettings settings,
    AnonymizationQuickSettingsNotifier notifier,
  ) {
    final modes = <Map<String, String>>[
      <String, String>{
        'code': 'placeholder',
        'name': 'Placeholder',
        'desc': 'Replace with [PERSON_1]',
      },
      <String, String>{'code': 'mask', 'name': 'Mask', 'desc': 'Mask with ***'},
      <String, String>{
        'code': 'type',
        'name': 'Type Indicator',
        'desc': 'Use [PERSON]',
      },
      <String, String>{
        'code': 'custom',
        'name': 'Custom',
        'desc': 'Use custom placeholder',
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text(
          'Anonymization Mode',
          style: TextStyle(fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          initialValue: settings.anonymizeMode,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          ),
          menuMaxHeight: 400,
          isExpanded: true,
          selectedItemBuilder: (BuildContext context) => modes
              .map<Widget>(
                (Map<String, String> mode) => Text(
                  '${mode['name']!} - ${mode['desc']!}',
                  style: const TextStyle(fontSize: 14),
                  overflow: TextOverflow.ellipsis,
                ),
              )
              .toList(),
          items: modes
              .map<DropdownMenuItem<String>>(
                (mode) => DropdownMenuItem(
                  value: mode['code'],
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          mode['name']!,
                          style: const TextStyle(fontSize: 14),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          mode['desc']!,
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              )
              .toList(),
          onChanged: (value) {
            if (value != null) {
              notifier.updateAnonymizeMode(value);
            }
          },
        ),
        const SizedBox(height: 4),
        Text(
          'Choose how to replace detected entities',
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey.shade600,
          ),
        ),
        // Custom Placeholder (only shown when mode is 'custom')
        if (settings.anonymizeMode == 'custom') ...<Widget>[
          const SizedBox(height: 12),
          TextField(
            controller: TextEditingController(
              text: settings.customPlaceholder ?? '[REDACTED]',
            ),
            onChanged: (value) =>
                notifier.updateCustomPlaceholder(value.isEmpty ? null : value),
            decoration: const InputDecoration(
              labelText: 'Custom Placeholder',
              hintText: 'e.g., [REDACTED]',
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildAdvancedSettings(
    AnonymizationQuickSettings settings,
    AnonymizationQuickSettingsNotifier notifier,
  ) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return ExpansionTile(
      title: const Text('Advanced Settings'),
      initiallyExpanded: settings.advancedSettingsExpanded,
      onExpansionChanged: (expanded) =>
          notifier.setAdvancedSettingsExpanded(expanded),
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Confidence Threshold
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          'Confidence Threshold',
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w500),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          softWrap: false,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Align(
                    alignment: Alignment.centerRight,
                    child: Text(
                      settings.anonymizeConfidence.toStringAsFixed(1),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      softWrap: false,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: scheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Slider(
                value: settings.anonymizeConfidence,
                min: 0.1,
                divisions: 9,
                activeColor: scheme.primary,
                onChanged: (value) => notifier.updateAnonymizeConfidence(value),
              ),
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      'Low (0.1)',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      softWrap: false,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'High (1.0)',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      softWrap: false,
                      textAlign: TextAlign.end,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Adjust detection sensitivity (0.1 = Low, 1.0 = High)',
                style: TextStyle(
                  fontSize: 12,
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
