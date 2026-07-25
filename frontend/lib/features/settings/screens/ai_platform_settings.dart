import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/services/settings_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/mineru_test_result_utils.dart';
import '../../../l10n/app_localizations.dart';

/// AI Platform Settings Screen
class AIPlatformSettingsScreen extends ConsumerStatefulWidget {
  const AIPlatformSettingsScreen({super.key});

  @override
  ConsumerState<AIPlatformSettingsScreen> createState() =>
      _AIPlatformSettingsScreenState();
}

class _AIPlatformSettingsScreenState
    extends ConsumerState<AIPlatformSettingsScreen> {
  @override
  Widget build(BuildContext context) {
    final aiPlatformSettings = ref.watch(aiPlatformSettingsProvider);
    final notifier = ref.read(aiPlatformSettingsProvider.notifier);

    if (aiPlatformSettings.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _buildPlatformOverview(aiPlatformSettings, notifier),
          const SizedBox(height: 24),
          _buildPlatformCategories(aiPlatformSettings, notifier),
        ],
      ),
    );
  }

  /// Build platform overview
  Widget _buildPlatformOverview(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final colorScheme = Theme.of(context).colorScheme;
    final totalPlatforms = settings.platforms.length;

    // Categorize platforms based on requiresApiKey and configuration status
    var availablePlatforms = 0;
    var unavailablePlatforms = 0;
    var unconfiguredCount = 0;
    var untestedCount = 0;

    for (final platform in settings.platforms.values) {
      if (platform.requiresApiKey) {
        // Platforms that require API key
        if (!platform.isConfigured) {
          // API key not configured - show as unconfigured
          unconfiguredCount++;
        } else if (platform.isApiAvailable == null) {
          // Has API key but not tested yet
          untestedCount++;
        } else if (platform.isApiAvailable ?? false) {
          // Has API key and test passed
          availablePlatforms++;
        } else {
          // Has API key but test failed
          unavailablePlatforms++;
        }
      } else {
        // Platforms that don't require API key (local platforms like Ollama)
        if (platform.isApiAvailable == null) {
          // Not tested yet
          untestedCount++;
        } else if (platform.isApiAvailable ?? false) {
          // Test passed
          availablePlatforms++;
        } else {
          // Test failed
          unavailablePlatforms++;
        }
      }
    }

    // Configured platforms = those that are ready to use (have required config)
    final configuredPlatforms = settings.platforms.values
        .where((p) => p.requiresApiKey ? p.isConfigured : true)
        .length;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                Icons.dashboard,
                color: colorScheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                l10n.aiPlatformOverview,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.primary,
                ),
              ),
              const Spacer(),
              // Platform status statistics (moved to right side of title row), using Material Icons to avoid emoji display issues with certain fonts
              // Green = Available (test passed), Red = Unavailable (test failed), 
              // Orange = Unconfigured (needs API key), Grey = Untested (not tested yet)
              Row(
                children: <Widget>[
                  _buildCompactStatusIndicator(
                    context,
                    availablePlatforms,
                    Colors.green,
                    tooltip: 'Available',
                  ),
                  const SizedBox(width: 12),
                  _buildCompactStatusIndicator(
                    context,
                    unavailablePlatforms,
                    Colors.red,
                    tooltip: 'Unavailable',
                  ),
                  const SizedBox(width: 12),
                  _buildCompactStatusIndicator(
                    context,
                    unconfiguredCount,
                    Colors.orange,
                    tooltip: 'Unconfigured (API key required)',
                  ),
                  const SizedBox(width: 12),
                  _buildCompactStatusIndicator(
                    context,
                    untestedCount,
                    Colors.grey,
                    tooltip: 'Untested',
                  ),
                  const SizedBox(width: 12),
                  Text(
                    l10n.aiPlatformConfiguredCount(configuredPlatforms, totalPlatforms),
                    style: TextStyle(
                      fontSize: 13,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: settings.isTestingConnection
                    ? null
                    : () => _testAllPlatforms(notifier),
                icon: settings.isTestingConnection
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.wifi_protected_setup, size: 16),
                label: Text(
                  settings.isTestingConnection
                      ? l10n.aiPlatformTesting
                      : l10n.aiPlatformTestApiStatus,
                ),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  minimumSize: const Size(0, 32),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Build platform categories
  Widget _buildPlatformCategories(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    // Categorize by platform type
    final allLlmPlatforms = settings.platforms.values
        .where((p) => p.platformType == 'llm')
        .toList();
    final parserPlatforms = settings.platforms.values
        .where((p) => p.platformType == 'parser')
        .toList();

    // Sort LLM platforms by order if available
    final llmPlatforms = List<AIPlatformInfo>.from(allLlmPlatforms);
    if (settings.platformOrder.isNotEmpty) {
      llmPlatforms.sort((a, b) {
        final indexA = settings.platformOrder.indexOf(a.key);
        final indexB = settings.platformOrder.indexOf(b.key);
        if (indexA == -1 && indexB == -1) return 0;
        if (indexA == -1) return 1;
        if (indexB == -1) return -1;
        return indexA.compareTo(indexB);
      });
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        _buildCollapsiblePlatformCategory(
          l10n.aiPlatformCategoryLanguageModels,
          llmPlatforms,
          notifier,
          isReorderable: true,
        ),
        const SizedBox(height: 16),
        _buildCollapsiblePlatformCategory(
          l10n.aiPlatformCategoryParsingEngines,
          parserPlatforms,
          notifier,
        ),
      ],
    );
  }

  /// Build collapsible platform category
  Widget _buildCollapsiblePlatformCategory(
    String title,
    List<AIPlatformInfo> platforms,
    AIPlatformSettingsNotifier notifier, {
    bool isReorderable = false,
  }) {
    final l10n = AppLocalizations.of(context)!;
    final configuredCount = platforms.where((p) => p.isConfigured).length;

    return ExpansionTile(
      title: Text(
        title,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(
        isReorderable
            ? l10n.aiPlatformConfiguredDragReorder(configuredCount, platforms.length)
            : l10n.aiPlatformConfiguredCount(configuredCount, platforms.length),
      ),
      children: isReorderable && platforms.isNotEmpty
          ? <Widget>[
              // Wrap ReorderableListView in a SizedBox to provide width constraints
              SizedBox(
                width: double.infinity,
                child: ReorderableListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: platforms.length,
                  onReorder: (oldIndex, newIndex) {
                    if (oldIndex < newIndex) {
                      newIndex -= 1;
                    }
                    final reordered = List<AIPlatformInfo>.from(platforms);
                    final item = reordered.removeAt(oldIndex);
                    reordered.insert(newIndex, item);
                    final newOrder = reordered.map((p) => p.key).toList();
                    notifier.updatePlatformOrder(newOrder);
                  },
                  itemBuilder: (context, index) => _buildCompactPlatformItem(
                    platforms[index],
                    notifier,
                    index: index,
                    key: ValueKey(platforms[index].key),
                    isReorderable: true,
                  ),
                ),
              ),
            ]
          : platforms
              .asMap()
              .entries
              .map(
                (e) =>
                    _buildCompactPlatformItem(e.value, notifier, index: e.key),
              )
              .toList(),
    );
  }

  /// Build compact platform item
  Widget _buildCompactPlatformItem(
    AIPlatformInfo platform,
    AIPlatformSettingsNotifier notifier, {
    int? index,
    Key? key,
    bool isReorderable = false,
  }) {
    final l10n = AppLocalizations.of(context)!;
    final colorScheme = Theme.of(context).colorScheme;
    final isEven = ((index ?? 0) % 2 == 0);
    final Color rowColor = isEven
        ? colorScheme.surfaceContainerLowest
        : colorScheme.surfaceContainerLow;

    final listTile = ColoredBox(
      color: rowColor,
      child: ListTile(
        leading: Icon(
          _getPlatformIcon(platform.key),
          color: _getPlatformColor(context, platform.key),
          size: 24,
        ),
        title: Text(platform.name),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(platform.url),
            // Show "Not Configured" for platforms that need API key but don't have it
            if (platform.requiresApiKey && !platform.isConfigured)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  l10n.aiPlatformNotConfigured,
                  style: TextStyle(fontSize: 12, color: Colors.orange.shade700),
                ),
              ),
            // Show "Not Configured" for local platforms without URL
            if (!platform.requiresApiKey && platform.url.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  l10n.aiPlatformNotConfigured,
                  style: TextStyle(fontSize: 12, color: Colors.orange.shade700),
                ),
              ),
            // Show "Not Tested" for configured platforms that haven't been tested
            if ((platform.requiresApiKey ? platform.isConfigured : platform.url.isNotEmpty) &&
                platform.isApiAvailable == null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  l10n.aiPlatformNotTested,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                ),
              ),
            // Show "Available" for platforms that passed the test
            if ((platform.isApiAvailable ?? false) &&
                (platform.lastTestError == null ||
                    platform.lastTestError!.isEmpty))
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  l10n.aiPlatformApiAvailable,
                  style: TextStyle(fontSize: 12, color: Colors.green.shade700),
                ),
              ),
            // Show error for platforms that failed the test
            if (platform.isApiAvailable == false &&
                (platform.lastTestError != null &&
                    platform.lastTestError!.isNotEmpty))
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  platform.lastTestError!,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.red.shade700,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            // Display API status
            _buildApiStatusIndicator(platform),
            const SizedBox(width: 8),
            // Show different config dialogs based on platform type
            if (platform.key == 'mineru')
              OutlinedButton(
                onPressed: () =>
                    _showMinerUConfigDialog(context, platform, notifier),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  minimumSize: const Size(0, 28),
                ),
                child: Text(l10n.aiPlatformConfigure),
              )
            else if (platform.key == 'mineru_local')
              OutlinedButton(
                onPressed: () =>
                    _showMinerULocalConfigDialog(context, platform, notifier),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  minimumSize: const Size(0, 28),
                ),
                child: Text(l10n.aiPlatformConfigure),
              )
            else
              OutlinedButton.icon(
                onPressed: () =>
                    _showPlatformConfigDialog(context, platform, notifier),
                icon: const Icon(Icons.settings, size: 16),
                label: Text(l10n.aiPlatformConfigure),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  minimumSize: const Size(0, 28),
                ),
              ),
          ],
        ),
      ),
    );

    // If reorderable, wrap with ReorderableDragStartListener and hide drag handle
    if (isReorderable) {
      return ReorderableDragStartListener(
        index: index ?? 0,
        key: key,
        child: listTile,
      );
    }
    return key != null ? KeyedSubtree(key: key, child: listTile) : listTile;
  }

  /// Build API status indicator
  /// Not configured (empty API key) -> orange; not tested -> grey; unavailable (API failed) -> red.
  Widget _buildApiStatusIndicator(AIPlatformInfo platform) {
    final l10n = AppLocalizations.of(context)!;
    final colorScheme = Theme.of(context).colorScheme;
    
    // Determine if platform is effectively configured
    final bool isEffectivelyConfigured = platform.requiresApiKey
        ? platform.isConfigured  // Need API key
        : platform.url.isNotEmpty;  // Local platform just needs URL
    
    if (!isEffectivelyConfigured) {
      // Not configured -> orange (different from grey which means not tested)
      return Tooltip(
        message: l10n.aiPlatformNotConfigured,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: Colors.orange.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.orange.shade200, width: 0.5),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.lens, size: 12, color: Colors.orange),
              const SizedBox(width: 4),
              Text(
                l10n.aiPlatformNotConfigured,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.orange.shade900,
                ),
              ),
            ],
          ),
        ),
      );
    }
    if (platform.isApiAvailable == null) {
      // Not tested yet
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: colorScheme.outlineVariant, width: 0.5),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.lens, size: 12, color: Colors.grey),
            const SizedBox(width: 4),
            Text(
              l10n.aiPlatformNotTested,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      );
    }
    if (platform.isApiAvailable ?? false) {
      // Available
      return Tooltip(
        message: l10n.aiPlatformApiAvailable,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: colorScheme.outlineVariant, width: 0.5),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.lens, size: 12, color: Colors.green),
              const SizedBox(width: 4),
              Text(
                l10n.aiPlatformAvailable,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onPrimaryContainer,
                ),
              ),
            ],
          ),
        ),
      );
    }
    // Configured but API failed -> red
    final errorMsg = platform.lastTestError ?? l10n.aiPlatformUnavailable;
    return Tooltip(
      message: errorMsg,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: colorScheme.errorContainer,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: colorScheme.outlineVariant, width: 0.5),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.lens, size: 12, color: Colors.red),
            const SizedBox(width: 4),
            Text(
              l10n.aiPlatformUnavailable,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: colorScheme.onErrorContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build compact status indicator (using Material Icons.lens to avoid emoji font missing display issues)
  Widget _buildCompactStatusIndicator(
    BuildContext context,
    int count,
    MaterialColor color, {
    String? tooltip,
  }) {
    final colorScheme = Theme.of(context).colorScheme;
    final Color bgColor;
    final Color textColor;
    if (color == Colors.green) {
      bgColor = colorScheme.primaryContainer;
      textColor = colorScheme.onPrimaryContainer;
    } else if (color == Colors.red) {
      bgColor = colorScheme.errorContainer;
      textColor = colorScheme.onErrorContainer;
    } else if (color == Colors.orange) {
      bgColor = Colors.orange.shade100;
      textColor = Colors.orange.shade900;
    } else {
      bgColor = colorScheme.surfaceContainerHighest;
      textColor = colorScheme.onSurfaceVariant;
    }
    final indicator = Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(Icons.lens, size: 14, color: color),
        const SizedBox(width: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: bgColor,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: colorScheme.outlineVariant, width: 0.5),
          ),
          child: Text(
            count.toString(),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: textColor,
            ),
          ),
        ),
      ],
    );
    
    if (tooltip != null && tooltip.isNotEmpty) {
      return Tooltip(
        message: tooltip,
        child: indicator,
      );
    }
    return indicator;
  }

  /// Test all platform connections
  Future<void> _testAllPlatforms(AIPlatformSettingsNotifier notifier) async {
    await notifier.startTestingAllConnections();

    // Test all platforms using the notifier method
    await notifier.testAllConnections();

    await notifier.finishTestingAllConnections();
  }

  /// Show platform config dialog; invalidate on close so Quick Settings and other screens can get the latest test results
  void _showPlatformConfigDialog(
    BuildContext context,
    AIPlatformInfo platformInfo,
    AIPlatformSettingsNotifier notifier,
  ) {
    showDialog(
      context: context,
      builder: (context) => _PlatformConfigDialog(
        platformInfo: platformInfo,
        notifier: notifier,
      ),
    ).then((_) {
      // Do not invalidate: testConnection already updated state; Quick Settings reads same provider.
      // Invalidate would recreate notifier and refetch; backend status is applied on next load anyway.
    });
  }

  /// Show MinerU config dialog; do not invalidate on close, consistent with platform config dialog, state updated by testConnection
  void _showMinerUConfigDialog(
    BuildContext context,
    AIPlatformInfo platformInfo,
    AIPlatformSettingsNotifier notifier,
  ) {
    showDialog(
      context: context,
      builder: (context) => _MinerUConfigDialog(
        platformInfo: platformInfo,
        notifier: notifier,
      ),
    ).then((_) {
      // Do not invalidate: testConnection already updated state; Quick Settings reads same provider.
    });
  }

  /// Show Local MinerU config dialog (similar to parsing engine settings)
  void _showMinerULocalConfigDialog(
    BuildContext context,
    AIPlatformInfo platformInfo,
    AIPlatformSettingsNotifier notifier,
  ) {
    showDialog(
      context: context,
      builder: (context) => _MinerULocalConfigDialog(
        platformInfo: platformInfo,
        notifier: notifier,
      ),
    ).then((_) {
      // Do not invalidate: testConnection already updated state; Quick Settings reads same provider.
    });
  }

  /// Get platform icon
  IconData _getPlatformIcon(String platformKey) {
    switch (platformKey) {
      case 'openai':
        return Icons.smart_toy;
      case 'anthropic':
        return Icons.psychology;
      case 'google':
        return Icons.search;
      case 'azure':
        return Icons.cloud;
      case 'deepseek':
        return Icons.rocket_launch;
      case 'dashscope':
        return Icons.auto_awesome;
      case 'zhipu':
        return Icons.school;
      case 'baidu':
        return Icons.language;
      case 'moonshot':
        return Icons.nightlight_round;
      case 'hunyuan':
        return Icons.group;
      case 'volcengine_ark':
        return Icons.bolt;
      case 'groq':
        return Icons.speed;
      case 'mistral':
        return Icons.wind_power;
      case 'cohere':
        return Icons.chat;
      case 'xai':
        return Icons.close;
      case 'aleph_alpha':
        return Icons.auto_awesome;
      case 'rinna':
        return Icons.flag;
      case 'naver':
        return Icons.flag;
      case 'mineru':
        return Icons.description;
      case 'custom':
        return Icons.settings;
      default:
        return Icons.api;
    }
  }

  /// Get platform color
  Color _getPlatformColor(BuildContext context, String platformKey) {
    switch (platformKey) {
      case 'openai':
        return Colors.green;
      case 'anthropic':
        return Colors.purple;
      case 'google':
        return Colors.blue;
      case 'azure':
        return Colors.orange;
      case 'deepseek':
        return Colors.indigo;
      case 'dashscope':
        return Colors.orange;
      case 'zhipu':
        return Colors.blue;
      case 'baidu':
        return Colors.red;
      case 'moonshot':
        return Colors.deepPurple;
      case 'hunyuan':
        return Colors.blue;
      case 'volcengine_ark':
        return Colors.orange;
      case 'groq':
        return Colors.teal;
      case 'mistral':
        return Colors.blue;
      case 'cohere':
        return Colors.pink;
      case 'xai':
        return Theme.of(context).colorScheme.onSurface;
      case 'aleph_alpha':
        return Colors.red;
      case 'rinna':
        return Colors.red;
      case 'naver':
        return Colors.green;
      case 'mineru':
        return Colors.purple;
      case 'custom':
        return Colors.grey;
      default:
        return Colors.grey;
    }
  }
}

/// Platform config dialog
class _PlatformConfigDialog extends StatefulWidget {
  const _PlatformConfigDialog({
    required this.platformInfo,
    required this.notifier,
  });
  final AIPlatformInfo platformInfo;
  final AIPlatformSettingsNotifier notifier;

  @override
  State<_PlatformConfigDialog> createState() => _PlatformConfigDialogState();
}

class _PlatformConfigDialogState extends State<_PlatformConfigDialog> {
  late TextEditingController _apiKeyController;
  late TextEditingController _nameController;
  late TextEditingController _urlController;
  late TextEditingController _modelController;
  late TextEditingController _maxTokensController;
  late TextEditingController _temperatureController;
  late TextEditingController _chunkSizeController;
  late TextEditingController _concurrentController;
  late TextEditingController _timeoutController;
  late TextEditingController _writeTimeoutController;
  late TextEditingController _testConnectTimeoutController;
  late TextEditingController _testRequestTimeoutController;
  late bool _thinkingModeSupported; // Whether this platform supports thinking mode
  late String _thinkingMode; // "enable", "disable", "default"
  late int _segmentLimit; // Max segments per translation batch (0 = unlimited)
  late String _apiProtocol; // "openai", "ollama", "anthropic"
  late bool _hasApiKey; // Whether platform has API key (if false, API key is optional)
  late final FocusNode _temperatureFocusNode;
  bool _temperatureFocused = false;
  bool _obscureText = true;
  String? _testResult;
  bool?
      _lastTestSuccess; // drive success/failure styling from API result, not message text
  Map<String, dynamic>? _lastTestRawResult;
  bool _isTestingConnection = false;
  bool _isLoadingModels = false;

  @override
  void initState() {
    super.initState();
    _apiKeyController =
        TextEditingController(text: widget.platformInfo.apiKey ?? '');
    _nameController = TextEditingController(text: widget.platformInfo.name);
    _urlController = TextEditingController(text: widget.platformInfo.url);
    _modelController = TextEditingController(text: widget.platformInfo.model);
    _maxTokensController =
        TextEditingController(text: widget.platformInfo.maxTokens.toString());
    _temperatureController =
        TextEditingController(text: widget.platformInfo.temperature.toString());
    _chunkSizeController =
        TextEditingController(text: widget.platformInfo.chunkSize.toString());
    _concurrentController =
        TextEditingController(text: widget.platformInfo.concurrent.toString());
    _timeoutController =
        TextEditingController(text: widget.platformInfo.timeout.toString());
    _writeTimeoutController =
        TextEditingController(text: widget.platformInfo.writeTimeout.toString());
    _testConnectTimeoutController =
        TextEditingController(text: widget.platformInfo.testConnectTimeout.toString());
    _testRequestTimeoutController =
        TextEditingController(text: widget.platformInfo.testRequestTimeout.toString());
    _thinkingModeSupported = widget.platformInfo.thinkingModeSupported;
    _thinkingMode = widget.platformInfo.thinkingMode;
    _segmentLimit = widget.platformInfo.segmentLimit;
    _apiProtocol = widget.platformInfo.apiProtocol;
    _hasApiKey = widget.platformInfo.requiresApiKey;
    _temperatureFocusNode = FocusNode();
    _temperatureFocusNode.addListener(() {
      setState(() {
        _temperatureFocused = _temperatureFocusNode.hasFocus;
      });
    });
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    _nameController.dispose();
    _urlController.dispose();
    _modelController.dispose();
    _maxTokensController.dispose();
    _temperatureController.dispose();
    _chunkSizeController.dispose();
    _concurrentController.dispose();
    _timeoutController.dispose();
    _writeTimeoutController.dispose();
    _testConnectTimeoutController.dispose();
    _testRequestTimeoutController.dispose();
    _temperatureFocusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AlertDialog(
        title: Text(l10n.aiPlatformConfigureTitle(widget.platformInfo.name)),
        contentPadding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        insetPadding: const EdgeInsets.all(16),
        content: SizedBox(
          width: 1100,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    // Left column: Basic Information + API Key
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                          l10n.aiPlatformBasicInformation,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                          const SizedBox(height: 8),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Expanded(
                                child: _buildTextField(
                                  l10n.aiPlatformPlatformName,
                                  _nameController,
                                  hintText: l10n.aiPlatformPlatformNameHint,
                                ),
                              ),
                              // API Protocol is for LLM platforms only
                              if (widget.platformInfo.platformType != 'parser') ...<Widget>[
                                const SizedBox(width: 8),
                                Expanded(child: _buildApiProtocolDropdown()),
                              ],
                            ],
                          ),
                          const SizedBox(height: 8),
                          _buildTextField(
                            l10n.aiPlatformApiUrl,
                            _urlController,
                            hintText: l10n.aiPlatformApiUrlHint,
                          ),
                          // Model field is for LLM platforms only, parsers use parser_subtype dropdown instead
                          if (widget.platformInfo.platformType != 'parser') ...<Widget>[
                            const SizedBox(height: 8),
                            _buildModelField(),
                          ],
                          if (widget.platformInfo.platformType == 'parser') ...<Widget>[
                            const SizedBox(height: 8),
                            _buildParserSubtypeDropdown(),
                            // PaddleOCR model dropdown — only for paddle parsers
                            if (widget.platformInfo.parserEngine == 'paddle') ...<Widget>[
                              const SizedBox(height: 8),
                              _buildPaddleModelDropdown(),
                            ],
                          ],
                          const SizedBox(height: 16),
                          _buildHasApiKeySwitch(),
                          const SizedBox(height: 8),
                          _buildApiKeyField(),
                          // Thinking mode is only for LLM platforms, not parsers
                          if (widget.platformInfo.platformType != 'parser') ...<Widget>[
                            const SizedBox(height: 8),
                            _buildThinkingModeSupportedField(),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(width: 16),
                    // Right column: Parameters
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'Parameters',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          // Only show advanced parameters config for LLM type platforms
                          if (widget.platformInfo.platformType != 'parser') ...<Widget>[
                            const SizedBox(height: 8),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: _buildTextField(
                                    'Read Timeout (seconds)',
                                    _timeoutController,
                                    keyboardType: TextInputType.number,
                                    hintText: '200 (cloud) or 300 (local). Max wait time for LLM response.',
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _buildTextField(
                                    'Write Timeout (seconds)',
                                    _writeTimeoutController,
                                    keyboardType: TextInputType.number,
                                    hintText: '300 (default). Max wait time for sending data to LLM.',
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: _buildTextField(
                                    l10n.aiPlatformTestConnectTimeout,
                                    _testConnectTimeoutController,
                                    keyboardType: TextInputType.number,
                                    hintText: l10n.aiPlatformTestConnectTimeoutHint,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _buildTextField(
                                    l10n.aiPlatformTestRequestTimeout,
                                    _testRequestTimeoutController,
                                    keyboardType: TextInputType.number,
                                    hintText: l10n.aiPlatformTestRequestTimeoutHint,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: _buildTextField(
                                    l10n.aiPlatformMaxTokens,
                                    _maxTokensController,
                                    keyboardType: TextInputType.number,
                                    hintText: l10n.aiPlatformMaxTokensHint,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _buildTextField(
                                    'Chunk Size',
                                    _chunkSizeController,
                                    keyboardType: TextInputType.number,
                                    hintText: 'Tokens per chunk (e.g. 2500 for Ollama, 8000 for OpenAI)',
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: _buildTextField(
                                    'Concurrent Requests',
                                    _concurrentController,
                                    keyboardType: TextInputType.number,
                                    hintText: 'Max parallel requests (e.g. 1 for Ollama, 10 for cloud)',
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(child: _buildTemperatureField()),
                            ],
                          ),
                          if (_thinkingModeSupported) ...<Widget>[
                            const SizedBox(height: 8),
                            _buildThinkingModeField(),
                          ],
                          const SizedBox(height: 8),
                          _buildSegmentLimitField(),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_testResult != null) ...<Widget>[
                  Builder(
                    builder: (BuildContext ctx) {
                      final PlatformTestVisualState visualState =
                          resolvePlatformTestVisualState(
                        lastTestSuccess: _lastTestSuccess,
                        rawResult: _lastTestRawResult,
                      );
                      final style = platformTestResultStyle(visualState);
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: style.backgroundColor,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: style.borderColor),
                        ),
                        child: Row(
                          children: <Widget>[
                            Icon(
                              style.icon,
                              color: style.contentColor,
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: SelectableText(
                                _testResult!,
                                style: TextStyle(
                                  color: style.contentColor,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 12),
                ],
              ],
            ),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.aiPlatformCancel),
          ),
          OutlinedButton(
            onPressed: _isTestingConnection ? null : _testConnection,
            child: _isTestingConnection
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.aiPlatformTestConnection),
          ),
          FilledButton(
            onPressed: _saveConfig,
            child: Text(l10n.aiPlatformSave),
          ),
        ],
      );
  }

  Widget _buildSectionTitle(String title) => Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
        ),
      );

  bool _isSuccessMessage(String? message) {
    if (message == null) return false;
    return message.toLowerCase().contains('success');
  }

  // Removed unused _buildInfoField after making fields editable

  Widget _buildTextField(
    String label,
    TextEditingController controller, {
    TextInputType? keyboardType,
    String? hintText,
  }) =>
      TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        decoration: InputDecoration(
          labelText: label,
          hintText: hintText,
          border: const OutlineInputBorder(),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        ),
      );

  Widget _buildModelField() {
    final l10n = AppLocalizations.of(context)!;
    return Row(
        children: <Widget>[
          Expanded(
            child: TextFormField(
              controller: _modelController,
              decoration: InputDecoration(
                labelText: l10n.aiPlatformModel,
                hintText: l10n.aiPlatformModelHint,
                border: const OutlineInputBorder(),
                contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              ),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: _isLoadingModels ? null : _loadModels,
            icon: _isLoadingModels
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.search, size: 18),
            label: Text(l10n.aiPlatformList),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              minimumSize: const Size(0, 48),
            ),
          ),
        ],
      );
  }

  Widget _buildApiKeyField() {
    final l10n = AppLocalizations.of(context)!;
    // When "has API key" is unchecked, API key is optional (can be empty)
    final bool apiKeyOptional = !_hasApiKey;
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          TextFormField(
            controller: _apiKeyController,
            obscureText: _obscureText,
            decoration: InputDecoration(
              labelText: apiKeyOptional 
                  ? '${l10n.aiPlatformApiKey} (${l10n.optional})'
                  : l10n.aiPlatformApiKey,
              hintText: apiKeyOptional 
                  ? l10n.aiPlatformApiKeyOptionalHint
                  : null,
              border: const OutlineInputBorder(),
              contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscureText ? Icons.visibility : Icons.visibility_off,
                ),
                onPressed: () {
                  setState(() {
                    _obscureText = !_obscureText;
                  });
                },
              ),
            ),
          ),
        ],
      );
  }

  /// "Has API Key" switch - for local deployments like Ollama that don't require API key
  Widget _buildHasApiKeySwitch() {
    final l10n = AppLocalizations.of(context)!;
    final apiKeyUrl = widget.platformInfo.tokenLink;
    return SizedBox(
      height: 60,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
          Icon(
            _hasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
            size: 20,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  l10n.aiPlatformHasApiKey,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  l10n.aiPlatformHasApiKeyHint,
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          if (apiKeyUrl != null && apiKeyUrl.isNotEmpty)
            TextButton(
              onPressed: () => _openApiKeyUrl(apiKeyUrl),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
              ),
              child: Text(
                l10n.aiPlatformGetApiKey,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.blue.shade700,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
          Switch(
            value: _hasApiKey,
            onChanged: (bool value) {
              setState(() {
                _hasApiKey = value;
              });
            },
          ),
        ],
      ),
    ),
  );
  }

  /// Parser Subtype dropdown for PDF parser platforms (MinerU)
  Widget _buildParserSubtypeDropdown() {
    final l10n = AppLocalizations.of(context)!;
    final String currentSubtype = widget.platformInfo.parserSubtype ?? 'cloud';

    return DropdownButtonFormField<String>(
      value: currentSubtype,
      decoration: InputDecoration(
        labelText: l10n.aiPlatformParserSubtype,
        prefixIcon: const Icon(Icons.category_outlined),
        border: const OutlineInputBorder(),
        contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      items: <DropdownMenuItem<String>>[
        DropdownMenuItem<String>(
          value: 'cloud',
          child: Text(l10n.aiPlatformParserSubtypeCloud),
        ),
        DropdownMenuItem<String>(
          value: 'local',
          child: Text(l10n.aiPlatformParserSubtypeLocal),
        ),
      ],
      onChanged: (String? value) {
        // Subtype is saved via copyWith in _saveConfig
      },
    );
  }

  /// Known PaddleOCR document parsing models (order: newest first).
  static const List<String> _paddleOcrModels = <String>[
    'PaddleOCR-VL-1.6',
    'PaddleOCR-VL',
    'paddleocr-vl',
  ];

  /// PaddleOCR model dropdown for Paddle parser platforms.
  Widget _buildPaddleModelDropdown() {
    final l10n = AppLocalizations.of(context)!;
    final String currentModel = _modelController.text.trim();
    // If the current model is not in the known list, add it as an option
    final List<String> modelOptions = _paddleOcrModels.contains(currentModel)
        ? _paddleOcrModels
        : <String>[currentModel, ..._paddleOcrModels];

    return DropdownButtonFormField<String>(
      value: modelOptions.contains(currentModel) ? currentModel : modelOptions.first,
      decoration: InputDecoration(
        labelText: l10n.settingsPaddleOcrModelLabel,
        prefixIcon: const Icon(Icons.model_training),
        border: const OutlineInputBorder(),
        contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      items: modelOptions
          .map(
            (String model) => DropdownMenuItem<String>(
              value: model,
              child: Text(
                model,
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ),
          )
          .toList(),
      onChanged: (String? value) {
        if (value != null) {
          _modelController.text = value;
        }
      },
    );
  }

  /// API Protocol dropdown selector
  Widget _buildApiProtocolDropdown() {
    return DropdownButtonFormField<String>(
      value: _apiProtocol,
      decoration: const InputDecoration(
        labelText: 'API Protocol',
        prefixIcon: Icon(Icons.api),
        border: OutlineInputBorder(),
        contentPadding:
              EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      items: const <DropdownMenuItem<String>>[
        DropdownMenuItem<String>(
          value: 'openai',
          child: Row(
            children: <Widget>[
              Icon(Icons.cloud, size: 18),
              SizedBox(width: 8),
              Text('OpenAI API'),
            ],
          ),
        ),
        DropdownMenuItem<String>(
          value: 'ollama',
          child: Row(
            children: <Widget>[
              Icon(Icons.computer, size: 18),
              SizedBox(width: 8),
              Text('Ollama API'),
            ],
          ),
        ),
        DropdownMenuItem<String>(
          value: 'anthropic',
          child: Row(
            children: <Widget>[
              Icon(Icons.psychology, size: 18),
              SizedBox(width: 8),
              Text('Anthropic API'),
            ],
          ),
        ),
      ],
      onChanged: (String? value) {
        if (value != null) {
          setState(() {
            _apiProtocol = value;
          });
        }
      },
    );
  }

  /// Open API Key management page
  Future<void> _openApiKeyUrl(String url) async {
    try {
      if (url.isEmpty) return;
      final uri = Uri.parse(url);
      // Desktop/Mobile: open in external browser; Web: open in new tab
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
        webOnlyWindowName: '_blank',
      );
      if (!launched) {
        // Try with platform default method
        await launchUrl(uri);
      }
    } catch (e) {
      if (kDebugMode) {
        print('Error opening URL: $e');
      }
      // Silently fail to avoid interrupting user operation
    }
  }

  Widget _buildTemperatureField() {
    final l10n = AppLocalizations.of(context)!;
    final double temperatureMin = widget.platformInfo.temperatureMin;
    final double temperatureMax = widget.platformInfo.temperatureMax;
    final int divisions = ((temperatureMax - temperatureMin) * 10).round();

    return SizedBox(
      height: 64,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: l10n.aiPlatformTemperature,
          floatingLabelBehavior: FloatingLabelBehavior.always,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
        ),
        isFocused: _temperatureFocused,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
            Expanded(
              child: ClipRect(
                child: SizedBox(
                  height: 32,
                  child: SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      trackHeight: 3,
                      thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                      overlayShape: const RoundSliderOverlayShape(overlayRadius: 10),
                    ),
                    child: Slider(
                      value: (double.tryParse(_temperatureController.text) ?? 0.3)
                          .clamp(temperatureMin, temperatureMax),
                      min: temperatureMin,
                      max: temperatureMax,
                      divisions: divisions,
                      onChanged: (double value) {
                        _temperatureController.text = value.toStringAsFixed(1);
                        setState(() {});
                      },
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 60,
              child: TextFormField(
                controller: _temperatureController,
                focusNode: _temperatureFocusNode,
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
                onChanged: (String value) {
                  final double? numValue = double.tryParse(value);
                  if (numValue != null &&
                      numValue >= temperatureMin &&
                      numValue <= temperatureMax) {
                    setState(() {});
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildThinkingModeSupportedField() {
    final l10n = AppLocalizations.of(context)!;
    return SwitchListTile(
      title: Text(l10n.aiPlatformThinkingModeSupported),
      subtitle: Text(l10n.aiPlatformThinkingModeSupportedHint),
      value: _thinkingModeSupported,
      onChanged: (bool value) {
        setState(() {
          _thinkingModeSupported = value;
        });
      },
    );
  }

  Widget _buildSegmentLimitField() {
    final l10n = AppLocalizations.of(context)!;
    const List<int> segmentLimitOptions = <int>[1, 3, 5, 10, 20, 50, 100, 200, 500, 1000, 0];
    String _labelForValue(int v) => v == 0 ? l10n.aiPlatformSegmentLimitUnlimited : v.toString();

    return DropdownButtonFormField<int>(
      value: segmentLimitOptions.contains(_segmentLimit) ? _segmentLimit : 100,
      decoration: InputDecoration(
        labelText: l10n.aiPlatformSegmentLimitLabel,
        border: const OutlineInputBorder(),
      ),
      items: segmentLimitOptions.map((v) {
        return DropdownMenuItem<int>(
          value: v,
          child: Text(_labelForValue(v)),
        );
      }).toList(),
      onChanged: (int? value) {
        if (value != null) {
          setState(() {
            _segmentLimit = value;
          });
        }
      },
    );
  }

  Widget _buildThinkingModeField() {
    final l10n = AppLocalizations.of(context)!;
    final List<Map<String, String>> thinkingOptions = <Map<String, String>>[
      <String, String>{'value': 'disable', 'label': l10n.aiPlatformThinkingDisable},
      <String, String>{'value': 'enable', 'label': l10n.aiPlatformThinkingEnable},
      <String, String>{'value': 'default', 'label': l10n.aiPlatformThinkingDefault},
    ];

    return DropdownButtonFormField<String>(
      value: _thinkingMode,
      decoration: InputDecoration(
        labelText: l10n.aiPlatformThinkingMode,
        border: const OutlineInputBorder(),
        contentPadding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      items: thinkingOptions
          .map(
            (Map<String, String> option) => DropdownMenuItem<String>(
              value: option['value'],
              child: Text(option['label']!),
            ),
          )
          .toList(),
      onChanged: (String? value) {
        if (value != null) {
          setState(() {
            _thinkingMode = value;
          });
        }
      },
    );
  }

  /// Test connection
  Future<void> _testConnection() async {
    final l10n = AppLocalizations.of(context)!;
    // Use requiresApiKey from platform config instead of hardcoded platform keys
    final bool requiresApiKey = widget.platformInfo.requiresApiKey;
    if (requiresApiKey && _apiKeyController.text.isEmpty) {
      setState(() {
        _testResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
      });
      return;
    }

    setState(() {
      _isTestingConnection = true;
      _testResult = null;
      _lastTestSuccess = null;
      _lastTestRawResult = null;
    });

    try {
      final result = await widget.notifier.testConnection(
        widget.platformInfo.key,
        _apiKeyController.text,
        baseUrlOverride: _urlController.text.trim(),
        modelNameOverride: _modelController.text.trim(),
      );

      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = success;
        _lastTestRawResult = result;
        _testResult = success
            ? buildPlatformTestSuccessMessage(
                l10n,
                widget.platformInfo.key,
                result,
              )
            : buildPlatformTestFailureMessage(
                l10n,
                widget.platformInfo.key,
                result,
              );
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = false;
        _testResult = l10n.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _isTestingConnection = false;
        });
      }
    }
  }

  /// Load model list
  Future<void> _loadModels() async {
    final l10n = AppLocalizations.of(context)!;
    final baseUrl = _urlController.text.trim();
    final apiKey = _apiKeyController.text.trim();

    if (baseUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.aiPlatformPleaseEnterApiUrlFirst),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    final bool requiresApiKey = widget.platformInfo.key != 'ollama' && widget.platformInfo.key != 'local' && widget.platformInfo.key != 'mineru_local';
    if (requiresApiKey && apiKey.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.aiPlatformPleaseEnterApiKeyFirst),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() {
      _isLoadingModels = true;
    });

    try {
      final configService = ConfigService();
      final result = await configService.listPlatformModels(
        widget.platformInfo.key,
        baseUrl,
        apiKey,
        apiProtocol: _apiProtocol,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        final models = (result['models'] as List<dynamic>?)
                ?.map((e) => e.toString())
                .toList() ??
            <String>[];

        if (models.isEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(l10n.aiPlatformNoModelsFound),
              backgroundColor: Colors.orange,
            ),
          );
        } else {
          _showModelSelectionDialog(models);
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                result['error']?.toString() ?? l10n.aiPlatformFailedToLoadModels,),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.aiPlatformErrorLoadingModels(e.toString())),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingModels = false;
        });
      }
    }
  }

  /// Show model selection dialog
  void _showModelSelectionDialog(List<String> models) {
    showDialog(
      context: context,
      builder: (BuildContext dialogContext) {
        final l10n = AppLocalizations.of(dialogContext)!;
        return AlertDialog(
        title: Text(l10n.aiPlatformSelectModel),
        content: SizedBox(
          width: 400,
          child: models.isEmpty
              ? Text(l10n.aiPlatformNoModelsAvailable)
              : ListView.builder(
                  shrinkWrap: true,
                  itemCount: models.length,
                  itemBuilder: (BuildContext context, int index) {
                    final String model = models[index];
                    final bool isSelected =
                        model == _modelController.text.trim();
                    return ListTile(
                      title: Text(model),
                      selected: isSelected,
                      onTap: () {
                        _modelController.text = model;
                        Navigator.of(dialogContext).pop();
                      },
                    );
                  },
                ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(l10n.aiPlatformCancel),
          ),
        ],
      );
      },
    );
  }

  /// Save config
  void _saveConfig() {
    // Use latest platform info from notifier state (may include recent test results),
    // so we don't overwrite isConfigured / isApiAvailable / lastTestError with stale values.
    final platforms = widget.notifier.state.platforms;
    final current = platforms[widget.platformInfo.key] ?? widget.platformInfo;
    
    // Base fields (shared by all platform types)
    final baseUpdates = <String, dynamic>{
      'name': _nameController.text.trim().isEmpty
          ? current.name
          : _nameController.text.trim(),
      'url': _urlController.text.trim().isEmpty
          ? current.url
          : _urlController.text.trim(),
      'model': _modelController.text.trim(),
      'apiKey': _apiKeyController.text,
    };
    
    // Only add advanced parameters for LLM type platforms
    if (current.platformType != 'parser') {
      baseUpdates['maxTokens'] = int.tryParse(_maxTokensController.text) ?? current.maxTokens;
      baseUpdates['temperature'] = double.tryParse(_temperatureController.text) ?? current.temperature;
      baseUpdates['chunkSize'] = int.tryParse(_chunkSizeController.text) ?? current.chunkSize;
      baseUpdates['concurrent'] = int.tryParse(_concurrentController.text) ?? current.concurrent;
      baseUpdates['timeout'] = int.tryParse(_timeoutController.text) ?? current.timeout;
      baseUpdates['write_timeout'] = int.tryParse(_writeTimeoutController.text) ?? current.writeTimeout;
      baseUpdates['testConnectTimeout'] = int.tryParse(_testConnectTimeoutController.text) ?? current.testConnectTimeout;
      baseUpdates['testRequestTimeout'] = int.tryParse(_testRequestTimeoutController.text) ?? current.testRequestTimeout;
      baseUpdates['thinkingModeSupported'] = _thinkingModeSupported;
      baseUpdates['thinkingMode'] = _thinkingModeSupported ? _thinkingMode : current.thinkingMode;
      baseUpdates['segmentLimit'] = _segmentLimit;
    }
    
    // Always save API protocol
    baseUpdates['apiProtocol'] = _apiProtocol;
    
    // Save API key required setting
    baseUpdates['requiresApiKey'] = _hasApiKey;
    
    // Save parser subtype for PDF parser platforms
    if (current.platformType == 'parser') {
      baseUpdates['parserSubtype'] = widget.platformInfo.parserSubtype ?? 'cloud';
    }
    
    final updatedPlatform = current.copyWith(
      name: baseUpdates['name'] as String,
      url: baseUpdates['url'] as String,
      model: baseUpdates['model'] as String,
      apiKey: baseUpdates['apiKey'] as String,
      maxTokens: baseUpdates['maxTokens'] as int? ?? current.maxTokens,
      temperature: baseUpdates['temperature'] as double? ?? current.temperature,
      chunkSize: baseUpdates['chunkSize'] as int? ?? current.chunkSize,
      concurrent: baseUpdates['concurrent'] as int? ?? current.concurrent,
      timeout: baseUpdates['timeout'] as int? ?? current.timeout,
      writeTimeout: baseUpdates['write_timeout'] as int? ?? current.writeTimeout,
      testConnectTimeout: baseUpdates['testConnectTimeout'] as int? ?? current.testConnectTimeout,
      testRequestTimeout: baseUpdates['testRequestTimeout'] as int? ?? current.testRequestTimeout,
      thinkingModeSupported: baseUpdates['thinkingModeSupported'] as bool? ?? current.thinkingModeSupported,
      thinkingMode: baseUpdates['thinkingMode'] as String? ?? current.thinkingMode,
      segmentLimit: baseUpdates['segmentLimit'] as int? ?? current.segmentLimit,
      apiProtocol: baseUpdates['apiProtocol'] as String,
      requiresApiKey: baseUpdates['requiresApiKey'] as bool,
      parserSubtype: baseUpdates['parserSubtype'] as String? ?? current.parserSubtype,
    );

    widget.notifier
        .updatePlatformConfig(widget.platformInfo.key, updatedPlatform);
    Navigator.of(context).pop();
  }
}

// AI platform settings state management
final StateNotifierProvider<AIPlatformSettingsNotifier, AIPlatformSettings>
    aiPlatformSettingsProvider =
    StateNotifierProvider<AIPlatformSettingsNotifier, AIPlatformSettings>(
  (
    ref,
  ) =>
      AIPlatformSettingsNotifier(),
);

class AIPlatformSettings {
  const AIPlatformSettings({
    this.defaultPlatform = 'openai',
    this.platforms = const <String, AIPlatformInfo>{},
    this.platformOrder = const <String>[],
    this.isLoading = false,
    this.isTestingConnection = false,
    this.error,
  });
  final String defaultPlatform;
  final Map<String, AIPlatformInfo> platforms;
  final List<String>
      platformOrder; // Ordered list of platform keys for retry rotation
  final bool isLoading;
  final bool isTestingConnection;
  final String? error;

  AIPlatformSettings copyWith({
    String? defaultPlatform,
    Map<String, AIPlatformInfo>? platforms,
    List<String>? platformOrder,
    bool? isLoading,
    bool? isTestingConnection,
    String? error,
  }) =>
      AIPlatformSettings(
        defaultPlatform: defaultPlatform ?? this.defaultPlatform,
        platforms: platforms ?? this.platforms,
        platformOrder: platformOrder ?? this.platformOrder,
        isLoading: isLoading ?? this.isLoading,
        isTestingConnection: isTestingConnection ?? this.isTestingConnection,
        error: error ?? this.error,
      );

  /// Get available LLM platforms in order (for retry rotation)
  List<AIPlatformInfo> getAvailablePlatformsInOrder() {
    final available = platforms.values
        .where(
          (p) =>
              p.platformType == 'llm' &&
              p.isConfigured &&
              (p.isApiAvailable ?? false),
        )
        .toList();

    // If platformOrder is set, sort by it
    if (platformOrder.isNotEmpty) {
      available.sort((a, b) {
        final indexA = platformOrder.indexOf(a.key);
        final indexB = platformOrder.indexOf(b.key);
        if (indexA == -1 && indexB == -1) return 0;
        if (indexA == -1) return 1;
        if (indexB == -1) return -1;
        return indexA.compareTo(indexB);
      });
    }

    return available;
  }
}

class AIPlatformSettingsNotifier extends StateNotifier<AIPlatformSettings> {
  
  AIPlatformSettingsNotifier() : super(const AIPlatformSettings()) {
    loadPlatforms();
  }
  // Static cache to persist across widget rebuilds but within same app session
  static Map<String, AIPlatformInfo>? _cachedPlatforms;
  static String? _cachedDefaultPlatform;
  static List<String>? _cachedPlatformOrder;
  static DateTime? _staticLastLoadTime;
  final ConfigService _configService = ConfigService();
  final SettingsService _settingsService = SettingsService();
  bool _loadPlatformsInProgress = false;
  DateTime? _lastLoadTime;
  static const Duration _minReloadInterval = Duration(minutes: 1);
  /// True after a successful load from backend (blocks empty/unhydrated writes).
  bool _hydratedFromServer = false;
  int _hydratedPlatformCount = 0;

  /// Load platform config (with cache - won't reload if loaded recently)
  Future<void> loadPlatforms({bool force = false}) async {
    if (_loadPlatformsInProgress) return;

    final bool hadError = state.error != null;

    // Check instance cache first (fastest)
    // If there was a previous error (e.g. auth required but no token), allow
    // retry even if the cache interval has not elapsed.
    if (!force && !hadError && _lastLoadTime != null) {
      final timeSinceLastLoad = DateTime.now().difference(_lastLoadTime!);
      if (timeSinceLastLoad < _minReloadInterval) return;
    }

    // Check static cache (survives widget rebuilds)
    if (!force && !hadError && _staticLastLoadTime != null && _cachedPlatforms != null) {
      final timeSinceLastLoad = DateTime.now().difference(_staticLastLoadTime!);
      if (timeSinceLastLoad < _minReloadInterval) {
        state = state.copyWith(
          platforms: _cachedPlatforms,
          defaultPlatform: _cachedDefaultPlatform ?? 'openai',
          platformOrder: _cachedPlatformOrder ?? <String>[],
          isLoading: false,
        );
        _lastLoadTime = _staticLastLoadTime;
        return;
      }
    }
    
    _loadPlatformsInProgress = true;
    state = state.copyWith(isLoading: true);

    try {
      // Fetch config and secrets in parallel to reduce loading time
      final results = await Future.wait(<Future<Map<String, dynamic>?>>[
        _configService.getAppConfig(),
        _configService.getSecretsConfig(),
      ]);
      final appConfig = results[0];
      final Map<String, dynamic>? secretsConfig = results[1];

      if (appConfig == null) {
        state = state.copyWith(
          error: 'Failed to load app config',
          isLoading: false,
        );
        _hydratedFromServer = false;
        return;
      }
      if (kDebugMode) {
        print('[AIPlatformSettings] AppConfig loaded: ${appConfig.keys.toList()}');
        print('[AIPlatformSettings] ai_platforms type: ${appConfig['ai_platforms']?.runtimeType}');
      }

      // appConfig always exists; secretsConfig may be null for regular users (no permission to get keys).
      // For non-admins, we still need to show platform availability based on backend status, so allow secretsConfig to be empty here,
      // only relying on its content when displaying/editing keys.
      {
        final platforms = <String, AIPlatformInfo>{};
        final aiPlatforms =
            appConfig['ai_platforms'] as Map<String, dynamic>? ??
                <String, dynamic>{};
        if (kDebugMode) {
          print('[AIPlatformSettings] Loading ${aiPlatforms.length} platforms from config');
          print('[AIPlatformSettings] Platform keys: ${aiPlatforms.keys.toList()}');
        }
        final platformApiKeys =
            secretsConfig?['platform_api_keys'] as Map<String, dynamic>? ??
                <String, dynamic>{};

        // Get MinerU tokens (special handling). Regular users may not get the key, treat as not configured, only determine availability based on backend status.
        final Map<String, dynamic>? mineruTokenData =
            secretsConfig?['translator_mineru_token_meta']
                as Map<String, dynamic>?;
        final String? mineruToken = mineruTokenData?['key'] as String?;
        final bool? mineruConfigured =
            mineruTokenData?['configured'] as bool?;
        
        // Get MinerU Local token (separate from cloud MinerU)
        final Map<String, dynamic>? mineruLocalTokenData =
            secretsConfig?['mineru_local_token_meta']
                as Map<String, dynamic>?;
        final String? mineruLocalToken = mineruLocalTokenData?['key'] as String?;
        final bool? mineruLocalConfigured =
            mineruLocalTokenData?['configured'] as bool?;

        for (final entry in aiPlatforms.entries) {
          final platformKey = entry.key;

          // Skip default platform field or any non-Map data (compatible with backend embedding default_platform in ai_platforms)
          final entryValue = entry.value;
          if (platformKey == 'default_platform' ||
              entryValue is! Map<String, dynamic>) {
            continue;
          }

          // entryValue has been type-checked as Map<String, dynamic>
          final platformData = Map<String, dynamic>.from(entryValue as Map);

          String? apiKey;
          bool? configured;

          // MinerU cloud uses translator_mineru_token
          if (platformKey == 'mineru') {
            apiKey = mineruToken;
            configured = mineruConfigured;
          } else if (platformKey == 'mineru_local') {
            // MinerU Local uses separate mineru_local_token
            apiKey = mineruLocalToken;
            configured = mineruLocalConfigured;
          } else {
            // Other platforms use platform_api_keys
            final apiKeyData = platformApiKeys[platformKey];
            if (apiKeyData is Map<String, dynamic>) {
              // New format: {key: "...", configured: true}
              apiKey = apiKeyData['key'] as String?;
              configured = apiKeyData['configured'] as bool?;
            } else if (apiKeyData is String) {
              // Old format: direct string
              apiKey = apiKeyData;
              configured = apiKey.isNotEmpty;
            }
          }

          try {
            platforms[platformKey] = AIPlatformInfo.fromJson(
              platformKey,
              platformData,
              apiKey: apiKey,
              configured: configured,
            );
          } catch (e) {
            // Don't interrupt overall flow, continue processing other platforms
            if (kDebugMode) {
              print('[AIPlatformSettings] Failed to parse platform $platformKey: $e');
              print('[AIPlatformSettings] Platform data: $platformData');
            }
            continue;
          }
        }

        // OpenSource edition: do not restrict Ollama (or any other platform)
        // based on donor/pro authorization state.

        // Backend is single source of truth: fetch and apply. Preserve existing status when backend fails (e.g. after invalidate).
        final t1 = DateTime.now();
        await _applyBackendPlatformStatus(platforms,
            previousPlatforms: state.platforms,);
        final t2 = DateTime.now();
        if (kDebugMode) {
          print('[AIPlatformSettings] _applyBackendPlatformStatus took ${t2.difference(t1).inMilliseconds}ms');
        }
        
        // Fallback: load from SharedPreferences only for platforms with no backend status
        final t3 = DateTime.now();
        await _loadSavedTestResults(platforms);
        final t4 = DateTime.now();
        if (kDebugMode && platforms.isEmpty) {
          print('[AIPlatformSettings] No platforms loaded');
        }

        // Load platform order from config
        final platformOrder =
            (appConfig['ai_platforms_order'] as List<dynamic>?)
                    ?.map((e) => e.toString())
                    .toList() ??
                <String>[];



        String defaultPlatform =
            appConfig['default_platform'] as String? ?? 'openai';
        if (kDebugMode) {
          print('[AIPlatformSettings] Loaded ${platforms.length} platforms successfully');
        }
        state = state.copyWith(
          platforms: platforms,
          defaultPlatform: defaultPlatform,
          platformOrder: platformOrder,
        );
        _hydratedFromServer = platforms.isNotEmpty;
        _hydratedPlatformCount = platforms.length;
      }
    } catch (e) {
      if (kDebugMode) {
        print('[AIPlatformSettings] Error loading platforms: $e');
      }
      state = state.copyWith(error: e.toString());
      _hydratedFromServer = false;
    } finally {
      _loadPlatformsInProgress = false;
      _lastLoadTime = DateTime.now();
      _staticLastLoadTime = _lastLoadTime;
      // Update static cache to survive widget rebuilds
      if (state.platforms.isNotEmpty) {
        _cachedPlatforms = Map<String, AIPlatformInfo>.from(state.platforms);
        _cachedDefaultPlatform = state.defaultPlatform;
        _cachedPlatformOrder = List<String>.from(state.platformOrder);
      }
      state = state.copyWith(isLoading: false);
    }
  }

  /// Update platform config
  Future<void> updatePlatformConfig(
    String platformKey,
    AIPlatformInfo platformInfo,
  ) async {
    // 1. Immediately update local state (for fast UI response)
    final updatedPlatforms = Map<String, AIPlatformInfo>.from(state.platforms);

    // isConfigured: optional-key platforms need URL; required-key need non-empty key
    var updatedInfo = platformInfo;
    if (!platformInfo.requiresApiKey) {
      updatedInfo = platformInfo.copyWith(
        isConfigured: platformInfo.url.trim().isNotEmpty,
      );
    } else if (platformInfo.apiKey != null) {
      updatedInfo = platformInfo.copyWith(
        isConfigured: platformInfo.apiKey!.trim().isNotEmpty,
      );
    }

    updatedPlatforms[platformKey] = updatedInfo;
    state = state.copyWith(platforms: updatedPlatforms);

    // 2. Persist non-sensitive platform configuration (single-platform delta)
    if (!_hydratedFromServer || state.platforms.isEmpty) {
      AppLogger.log(
        'AIPlatformSettings',
        'Skip ai_platforms save: not hydrated or empty '
        '(hydrated=$_hydratedFromServer count=${state.platforms.length})',
        level: LogLevel.warn,
      );
    } else if (state.platforms.length < (_hydratedPlatformCount / 2).ceil() &&
        _hydratedPlatformCount >= 4) {
      AppLogger.log(
        'AIPlatformSettings',
        'Skip ai_platforms save: local count ${state.platforms.length} '
        'far below hydrated $_hydratedPlatformCount (config-loss guard)',
        level: LogLevel.error,
      );
    } else {
      try {
        // Only send the changed platform to avoid full-table overwrite races
        await _configService.updateAppConfig(
          <String, dynamic>{
            'ai_platforms': <String, dynamic>{
              platformKey: updatedInfo.toJson(),
            },
          },
        );
      } catch (e) {
        if (kDebugMode) {
          print('Failed to update platform config: $e');
        }
      }
    }

    // 3. Persist API key when provided.
    // - Required-key platforms: never write empty (avoids wiping secrets).
    // - Optional-key platforms (requiresApiKey=false) and mineru_local: empty OK.
    final bool keyOptional =
        !platformInfo.requiresApiKey || platformKey == 'mineru_local';
    final shouldSaveApiKey = platformInfo.apiKey != null &&
        (platformInfo.apiKey!.trim().isNotEmpty || keyOptional);

    if (shouldSaveApiKey) {
      final hasValidApiKey = platformInfo.apiKey!.trim().isNotEmpty;

      if (platformKey == 'mineru') {
        if (!hasValidApiKey) {
          AppLogger.log(
            'AIPlatformSettings',
            'Skip empty translator_mineru_token save (config-loss guard)',
            level: LogLevel.warn,
          );
        } else {
          await _settingsService.saveSetting(
            '',
            'translator_mineru_token',
            platformInfo.apiKey,
          );
        }
      } else if (platformKey == 'mineru_local') {
        await _settingsService.saveSetting(
          '',
          'mineru_local_token',
          platformInfo.apiKey,
        );
      } else if (hasValidApiKey || keyOptional) {
        final apiKeyData = <String, Map<String, Object?>>{
          platformKey: <String, Object?>{
            'key': platformInfo.apiKey ?? '',
            // Optional-key local platforms are "configured" even with empty key
            'configured': keyOptional ? true : hasValidApiKey,
          },
        };
        await _settingsService.saveSetting('', 'api_keys', apiKeyData);
      }
    }
  }

  /// Test platform connection
  Future<Map<String, dynamic>> testConnection(
    String platformKey,
    String apiKey, {
    String? baseUrlOverride,
    String? modelNameOverride,
  }) async {
    try {
      final info = state.platforms[platformKey];
      final result = await _configService.testAIPlatform(
        platformKey,
        apiKey,
        // If override value is passed (even empty string), use it first; otherwise fall back to saved config
        baseUrl: (baseUrlOverride != null) ? baseUrlOverride.trim() : info?.url,
        modelName: (modelNameOverride != null)
            ? modelNameOverride.trim()
            : info?.model,
        testConnectTimeout: info?.testConnectTimeout,
        testRequestTimeout: info?.testRequestTimeout,
      );

      // Update platform API availability status and last error message
      final updatedPlatforms =
          Map<String, AIPlatformInfo>.from(state.platforms);
      if (updatedPlatforms.containsKey(platformKey)) {
        // Ensure apiKey / url / isConfigured are updated in local state based on this test,
        // so Platform Overview statistics reflect the latest configuration immediately.
        final existing = updatedPlatforms[platformKey]!;
        // API key is valid if not empty (empty string means not configured)
        final hasValidApiKey = apiKey.isNotEmpty;
        // For platforms that don't require API key, check basic config instead
        final bool requiresApiKey = existing.requiresApiKey;
        final bool isConfigured = requiresApiKey 
            ? hasValidApiKey 
            : ((baseUrlOverride?.trim().isNotEmpty ?? false) || existing.url.isNotEmpty);
        updatedPlatforms[platformKey] = existing.copyWith(
          apiKey: apiKey,
          url: baseUrlOverride?.trim() ?? existing.url,
          isConfigured: isConfigured,
          isApiAvailable: platformTestMeetsRequirements(result),
          lastTestError: platformTestMeetsRequirements(result)
              ? null
              : (result?['message']?.toString() ??
                  result?['error']?.toString() ??
                  'Unknown error'),
        );
        state = state.copyWith(platforms: updatedPlatforms);
        if (kDebugMode) {
          print(
              '[AIPlatformSettings] testConnection updated $platformKey isApiAvailable=${platformTestMeetsRequirements(result)}',);
        }
        // Save single test result
        await _saveTestResults(state.platforms);
      }

      // Refresh from backend to ensure consistency (backend is single source of truth)
      await refreshPlatformStatus();

      // Uniformly return backend payload (includes Paddle capability fields).
      if (result == null) {
        return <String, dynamic>{'success': false, 'message': 'Unknown error'};
      }
      final Map<String, dynamic> payload = Map<String, dynamic>.from(result);
      if (payload['message'] == null && payload['error'] != null) {
        payload['message'] = payload['error'];
      }
      payload['success'] = payload['success'] == true;
      payload['meets_requirements'] = platformTestMeetsRequirements(payload);
      return payload;
    } catch (e) {
      // Even if test fails, update status to unavailable
      final updatedPlatforms =
          Map<String, AIPlatformInfo>.from(state.platforms);
      if (updatedPlatforms.containsKey(platformKey)) {
        updatedPlatforms[platformKey] = updatedPlatforms[platformKey]!.copyWith(
          isApiAvailable: false,
          lastTestError: e.toString(),
        );
        state = state.copyWith(platforms: updatedPlatforms);
        // Save failure result
        await _saveTestResults(state.platforms);
      }

      return <String, dynamic>{'success': false, 'message': e.toString()};
    }
  }

  /// Start batch testing all connections
  Future<void> startTestingAllConnections() async {
    state = state.copyWith(isTestingConnection: true);
  }

  /// Finish batch testing all connections
  Future<void> finishTestingAllConnections() async {
    state = state.copyWith(isTestingConnection: false);
  }

  /// Test all configured platform connections (parallel for better performance)
  Future<void> testAllConnections() async {
    final futures = <Future<void>>[];
    
    for (final platform in state.platforms.values) {
      bool shouldTest = false;
      
      if (platform.requiresApiKey) {
        // Platforms that require API key: test if configured (has valid API key)
        shouldTest = platform.isConfigured;
      } else {
        // Platforms that don't require API key (local platforms like Ollama):
        // Test if URL is configured (model may be optional for some local platforms)
        shouldTest = platform.url.isNotEmpty;
      }
      
      if (shouldTest) {
        // Run tests in parallel instead of sequentially
        // For platforms without API key, pass empty string
        futures.add(testConnection(platform.key, platform.apiKey ?? ''));
      }
    }
    
    // Wait for all tests to complete
    await Future.wait(futures);
    
    // Save test results
    await _saveTestResults(state.platforms);
  }

  /// Refresh platform status from backend (e.g. after testing from Quick Settings).
  Future<void> refreshPlatformStatus() async {
    try {
      final status = await _configService.getAiPlatformStatus();
      final platformsStatus = status?['platforms'] as Map<String, dynamic>?;
      if (platformsStatus == null || platformsStatus.isEmpty) return;
      final updatedPlatforms =
          Map<String, AIPlatformInfo>.from(state.platforms);
      for (final entry in platformsStatus.entries) {
        final platformKey = entry.key;
        if (!updatedPlatforms.containsKey(platformKey)) continue;
        final data = entry.value;
        if (data is! Map<String, dynamic>) continue;
        final isApiAvailable = data['isApiAvailable'] as bool?;
        final lastTestError = data['lastTestError'] as String?;
        updatedPlatforms[platformKey] = updatedPlatforms[platformKey]!.copyWith(
          isApiAvailable: isApiAvailable,
          lastTestError: lastTestError,
        );
      }
      state = state.copyWith(platforms: updatedPlatforms);
    } catch (_) {
      // Keep current state on error
    }
  }

  /// Apply backend AI platform status (single source of truth). When backend returns nothing, keep [previousPlatforms] status so reload/invalidate does not clear Quick Settings.
  Future<void> _applyBackendPlatformStatus(
    Map<String, AIPlatformInfo> platforms, {
    Map<String, AIPlatformInfo>? previousPlatforms,
  }) async {
    try {
      final status = await _configService.getAiPlatformStatus();
      final platformsStatus = status?['platforms'] as Map<String, dynamic>?;
      if (platformsStatus == null || platformsStatus.isEmpty) {
        // Preserve existing status so invalidate + failed refetch does not clear green/red in Quick Settings
        if (previousPlatforms != null && previousPlatforms.isNotEmpty) {
          for (final key in platforms.keys) {
            final prev = previousPlatforms[key];
            if (prev != null &&
                (prev.isApiAvailable != null || prev.lastTestError != null)) {
              platforms[key] = platforms[key]!.copyWith(
                isApiAvailable: prev.isApiAvailable,
                lastTestError: prev.lastTestError,
              );
            }
          }
        }
        return;
      }
      for (final entry in platformsStatus.entries) {
        final platformKey = entry.key;
        if (!platforms.containsKey(platformKey)) continue;
        final data = entry.value;
        if (data is! Map<String, dynamic>) continue;
        final isApiAvailable = data['isApiAvailable'] as bool?;
        final lastTestError = data['lastTestError'] as String?;
        platforms[platformKey] = platforms[platformKey]!.copyWith(
          isApiAvailable: isApiAvailable,
          lastTestError: lastTestError,
        );
      }
    } catch (_) {
      // Preserve previous status on error so Quick Settings does not lose state
      if (previousPlatforms != null && previousPlatforms.isNotEmpty) {
        for (final key in platforms.keys) {
          final prev = previousPlatforms[key];
          if (prev != null &&
              (prev.isApiAvailable != null || prev.lastTestError != null)) {
            platforms[key] = platforms[key]!.copyWith(
              isApiAvailable: prev.isApiAvailable,
              lastTestError: prev.lastTestError,
            );
          }
        }
      }
    }
  }

  /// Load saved test results from SharedPreferences
  Future<void> _loadSavedTestResults(
    Map<String, AIPlatformInfo> platforms,
  ) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final testResultsJson = prefs.getString('ai_platform_test_results');
      if (testResultsJson != null) {
        final testResults = jsonDecode(testResultsJson) as Map<String, dynamic>;
        for (final entry in testResults.entries) {
          final platformKey = entry.key;
          if (!platforms.containsKey(platformKey)) continue;
          // Only use saved result when backend did not provide status (single source of truth)
          if (platforms[platformKey]!.isApiAvailable != null) continue;
          final result = entry.value as Map<String, dynamic>;
          final isAvailable = result['isAvailable'] as bool?;
          final lastError = result['lastError'] as String?;
          platforms[platformKey] = platforms[platformKey]!.copyWith(
            isApiAvailable: isAvailable,
            lastTestError: lastError,
          );
        }
      }
    } catch (e) {
      // Failed to load saved test results
    }
  }

  /// Save test results to SharedPreferences
  Future<void> _saveTestResults(Map<String, AIPlatformInfo> platforms) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final testResults = <String, dynamic>{};
      for (final entry in platforms.entries) {
        if (entry.value.isConfigured) {
          testResults[entry.key] = <String, Object?>{
            'isAvailable': entry.value.isApiAvailable,
            'lastError': entry.value.lastTestError,
          };
        }
      }
      await prefs.setString(
        'ai_platform_test_results',
        jsonEncode(testResults),
      );
    } catch (e) {
      // Failed to save test results
    }
  }

  /// Initialize platform status from backend cache
  /// Note: Backend runs periodic checks (hourly), frontend only fetches cached results
  Future<void> initializePlatformTests({bool force = false}) async {
    // Ensure platforms are loaded (this fetches backend-cached status)
    // With cache: if loaded within 1 minute, skip unless forced
    if (state.platforms.isEmpty || force) {
      await loadPlatforms(force: force);
    }
    // Frontend no longer initiates connection tests
    // Backend runs hourly checks and saves results to config
  }

  /// Set default AI platform and persist to backend
  Future<void> setDefaultPlatform(String platformKey) async {
    // 1. Immediately update local state (for fast UI response)
    state = state.copyWith(defaultPlatform: platformKey);

    // 2. Trigger batch save to backend (with debounce)
    await _settingsService.saveSetting(
      '',
      'ai_platforms_default_platform',
      platformKey,
    );
  }

  /// Update platform order and persist
  Future<void> updatePlatformOrder(List<String> orderedKeys) async {
    // 1) Update local state
    state = state.copyWith(platformOrder: orderedKeys);
    // 2) Persist to global config
    await _configService
        .updateAppConfig(<String, dynamic>{'ai_platforms_order': orderedKeys});
  }

  void clearError() {
    state = state.copyWith();
  }
}

/// MinerU config dialog
class _MinerUConfigDialog extends StatefulWidget {
  const _MinerUConfigDialog({
    required this.platformInfo,
    required this.notifier,
  });
  final AIPlatformInfo platformInfo;
  final AIPlatformSettingsNotifier notifier;

  @override
  State<_MinerUConfigDialog> createState() => _MinerUConfigDialogState();
}

class _MinerUConfigDialogState extends State<_MinerUConfigDialog> {
  late TextEditingController _nameController;
  late TextEditingController _apiKeyController;
  late TextEditingController _apiUrlController;
  late TextEditingController _parserSubtypeController;
  bool _obscureText = true;
  String? _testResult;
  bool? _lastTestSuccess; // drive success/failure styling from API result
  Map<String, dynamic>? _lastTestRawResult;
  bool _isTestingConnection = false;
  bool _formulaOcr = true;
  bool _tableOcr = true;
  late bool _hasApiKey;

  @override
  void initState() {
    super.initState();
    _nameController =
        TextEditingController(text: widget.platformInfo.name);
    _apiKeyController =
        TextEditingController(text: widget.platformInfo.apiKey ?? '');
    _apiUrlController = TextEditingController(text: widget.platformInfo.url);
    _parserSubtypeController =
        TextEditingController(text: widget.platformInfo.parserSubtype ?? 'cloud');
    _hasApiKey = widget.platformInfo.requiresApiKey;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _apiKeyController.dispose();
    _apiUrlController.dispose();
    _parserSubtypeController.dispose();
    super.dispose();
  }

  Future<void> _testConnection() async {
    final l10n = AppLocalizations.of(context)!;
    if (_apiKeyController.text.isEmpty) {
      setState(() {
        _testResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
      });
      return;
    }

    setState(() {
      _isTestingConnection = true;
      _testResult = null;
      _lastTestSuccess = null;
      _lastTestRawResult = null;
    });

    try {
      final result = await widget.notifier.testConnection(
        widget.platformInfo.key, // Use platform key dynamically instead of hardcoded 'mineru'
        _apiKeyController.text,
        baseUrlOverride: _apiUrlController.text.trim(),
      );

      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = success;
        _lastTestRawResult = result;
        _testResult = success
            ? buildPlatformTestSuccessMessage(
                l10n,
                widget.platformInfo.key,
                result,
              )
            : buildPlatformTestFailureMessage(
                l10n,
                widget.platformInfo.key,
                result,
              );
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = false;
        _testResult = l10n.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _isTestingConnection = false;
        });
      }
    }
  }

  void _saveConfig() {
    // Use latest platform info from notifier state (may include recent test results),
    // so we don't overwrite isConfigured / isApiAvailable / lastTestError with stale values.
    final platforms = widget.notifier.state.platforms;
    final current = platforms[widget.platformInfo.key] ?? widget.platformInfo;
    final updatedPlatform = current.copyWith(
      name: _nameController.text.trim().isNotEmpty
          ? _nameController.text.trim()
          : current.name,
      apiKey: _hasApiKey ? _apiKeyController.text.trim() : '',
      url: _apiUrlController.text.trim(),
      model: 'vlm', // Cloud MinerU API v4 supports: pipeline, vlm, MinerU-HTML
      parserSubtype: _parserSubtypeController.text.trim().isNotEmpty
          ? _parserSubtypeController.text.trim()
          : current.parserSubtype,
      requiresApiKey: _hasApiKey,
    );

    widget.notifier
        .updatePlatformConfig(widget.platformInfo.key, updatedPlatform);
    Navigator.of(context).pop();
  }

  /// Open MinerU API Key management page
  Future<void> _openMinerUApiKeyUrl() async {
    try {
      const url = 'https://mineru.net/';
      if (url.isEmpty) return;
      final uri = Uri.parse(url);
      // Desktop/Mobile: open in external browser; Web: open in new tab
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
        webOnlyWindowName: '_blank',
      );
      if (!launched) {
        // Try with platform default method
        await launchUrl(uri);
      }
    } catch (e) {
      if (kDebugMode) {
        print('Error opening MinerU URL: $e');
      }
      // Silently fail to avoid interrupting user operation
    }
  }

  Widget _buildHasApiKeySwitch() {
    final l10n = AppLocalizations.of(context)!;
    return SizedBox(
      height: 60,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
            Icon(
              _hasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
              size: 20,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    l10n.aiPlatformHasApiKey,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    l10n.aiPlatformHasApiKeyHint,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: _openMinerUApiKeyUrl,
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
              ),
              child: Text(
                l10n.aiPlatformGetMineruApiKey,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.blue.shade700,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
            Switch(
              value: _hasApiKey,
              onChanged: (bool value) {
                setState(() {
                  _hasApiKey = value;
                });
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AlertDialog(
      title: Row(
        children: <Widget>[
          const Icon(Icons.description, color: Colors.purple, size: 24),
          const SizedBox(width: 8),
          Text(l10n.aiPlatformMineruSettings),
        ],
      ),
      contentPadding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      insetPadding: const EdgeInsets.all(16),
      content: SizedBox(
        width: 900,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(
                    Icons.info_outline,
                    size: 16,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      l10n.aiPlatformTestConnectionHint,
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context)
                            .colorScheme
                            .onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          l10n.aiPlatformBasicInformation,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _nameController,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformDisplayName,
                            hintText: 'MinerU (Cloud)',
                            prefixIcon: const Icon(Icons.label_outline),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _apiUrlController,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformApiUrl,
                            hintText: l10n.aiPlatformMineruApiUrlHint,
                            prefixIcon: const Icon(Icons.link),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                        const SizedBox(height: 8),
                        DropdownButtonFormField<String>(
                          value: _parserSubtypeController.text.isNotEmpty
                              ? _parserSubtypeController.text
                              : 'cloud',
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformParserSubtype,
                            prefixIcon: const Icon(Icons.category_outlined),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                          items: <DropdownMenuItem<String>>[
                            DropdownMenuItem<String>(
                              value: 'cloud',
                              child: Text(l10n.aiPlatformParserSubtypeCloud),
                            ),
                            DropdownMenuItem<String>(
                              value: 'local',
                              child: Text(l10n.aiPlatformParserSubtypeLocal),
                            ),
                          ],
                          onChanged: (String? value) {
                            if (value != null) {
                              setState(() {
                                _parserSubtypeController.text = value;
                              });
                            }
                          },
                        ),
                        const SizedBox(height: 16),
                        _buildHasApiKeySwitch(),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _apiKeyController,
                          obscureText: _obscureText,
                          decoration: InputDecoration(
                            labelText: _hasApiKey
                                ? l10n.aiPlatformApiKey
                                : '${l10n.aiPlatformApiKey} (${l10n.optional})',
                            hintText: _hasApiKey
                                ? 'Enter your API key'
                                : 'API Key (optional)',
                            prefixIcon: const Icon(Icons.key),
                            suffixIcon: IconButton(
                              icon: Icon(
                                _obscureText
                                    ? Icons.visibility
                                    : Icons.visibility_off,
                              ),
                              onPressed: () {
                                setState(() {
                                  _obscureText = !_obscureText;
                                });
                              },
                            ),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          l10n.aiPlatformOcrSettings,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Column(
                          children: <Widget>[
                            SwitchListTile(
                              title: Text(l10n.aiPlatformFormulaOcr),
                              subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle),
                              value: _formulaOcr,
                              onChanged: (bool value) {
                                setState(() {
                                  _formulaOcr = value;
                                });
                              },
                              contentPadding: EdgeInsets.zero,
                            ),
                            SwitchListTile(
                              title: Text(l10n.aiPlatformTableOcr),
                              subtitle: Text(l10n.aiPlatformTableOcrSubtitle),
                              value: _tableOcr,
                              onChanged: (bool value) {
                                setState(() {
                                  _tableOcr = value;
                                });
                              },
                              contentPadding: EdgeInsets.zero,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (_testResult != null) ...<Widget>[
                const SizedBox(height: 12),
                Builder(
                  builder: (BuildContext ctx) {
                    final PlatformTestVisualState visualState =
                        resolvePlatformTestVisualState(
                      lastTestSuccess: _lastTestSuccess,
                      rawResult: _lastTestRawResult,
                    );
                    final style = platformTestResultStyle(visualState);
                    return Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: style.backgroundColor,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: style.borderColor),
                      ),
                      width: double.infinity,
                      child: Row(
                        children: <Widget>[
                          Icon(
                            style.icon,
                            color: style.contentColor,
                          ),
                          const SizedBox(width: 8),
                          Flexible(
                            child: SelectableText(
                              _testResult!,
                              style: TextStyle(color: style.contentColor),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ],
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.aiPlatformCancel),
        ),
        OutlinedButton(
          onPressed: _isTestingConnection ? null : _testConnection,
          child: _isTestingConnection
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(l10n.aiPlatformTestConnection),
        ),
        FilledButton(
          onPressed: _saveConfig,
          child: Text(l10n.aiPlatformSave),
        ),
      ],
    );
  }

  bool _isSuccessMessage(String? message) {
    if (message == null) return false;
    return message.toLowerCase().contains('success');
  }
}

/// Local MinerU config dialog
/// Uses the same UI structure as _MinerUConfigDialog
class _MinerULocalConfigDialog extends StatefulWidget {
  const _MinerULocalConfigDialog({
    required this.platformInfo,
    required this.notifier,
  });

  final AIPlatformInfo platformInfo;
  final AIPlatformSettingsNotifier notifier;

  @override
  State<_MinerULocalConfigDialog> createState() => _MinerULocalConfigDialogState();
}

class _MinerULocalConfigDialogState extends State<_MinerULocalConfigDialog> {
  late TextEditingController _nameController;
  late TextEditingController _apiKeyController;
  late TextEditingController _apiUrlController;
  late TextEditingController _modelVersionController;
  late TextEditingController _parserSubtypeController;
  bool _obscureText = true;
  String? _testResult;
  bool? _lastTestSuccess; // drive success/failure styling from API result
  Map<String, dynamic>? _lastTestRawResult;
  bool _isTestingConnection = false;
  bool _formulaOcr = true;
  bool _tableOcr = true;
  late bool _hasApiKey;

  @override
  void initState() {
    super.initState();
    _nameController =
        TextEditingController(text: widget.platformInfo.name);
    _apiKeyController =
        TextEditingController(text: widget.platformInfo.apiKey ?? '');
    _apiUrlController = TextEditingController(text: widget.platformInfo.url);
    _modelVersionController =
        TextEditingController(text: _normalizeModelVersion(
            widget.platformInfo.model.isNotEmpty
                ? widget.platformInfo.model
                : 'hybrid-auto-engine'));
    _parserSubtypeController =
        TextEditingController(text: widget.platformInfo.parserSubtype ?? 'local');
    _hasApiKey = widget.platformInfo.requiresApiKey;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _apiKeyController.dispose();
    _apiUrlController.dispose();
    _modelVersionController.dispose();
    _parserSubtypeController.dispose();
    super.dispose();
  }

  /// Migrate old model version short names to official MinerU 3.2 names.
  static const Map<String, String> _migrationMap = {
    'vlm': 'vlm-auto-engine',
    'hybrid': 'hybrid-auto-engine',
  };
  static String _normalizeModelVersion(String mv) =>
      _migrationMap[mv] ?? mv;

  Future<void> _testConnection() async {
    final l10n = AppLocalizations.of(context)!;
    // API Key is optional for local MinerU deployment
    setState(() {
      _isTestingConnection = true;
      _testResult = null;
      _lastTestSuccess = null;
      _lastTestRawResult = null;
    });

    try {
      final result = await widget.notifier.testConnection(
        widget.platformInfo.key, // Use platform key dynamically
        _apiKeyController.text,
        baseUrlOverride: _apiUrlController.text.trim(),
      );

      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = success;
        _lastTestRawResult = result;
        _testResult = success
            ? buildPlatformTestSuccessMessage(
                l10n,
                widget.platformInfo.key,
                result,
              )
            : buildPlatformTestFailureMessage(
                l10n,
                widget.platformInfo.key,
                result,
              );
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _lastTestSuccess = false;
        _testResult = l10n.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _isTestingConnection = false;
        });
      }
    }
  }

  void _saveConfig() {
    // Use latest platform info from notifier state (may include recent test results),
    // so we don't overwrite isConfigured / isApiAvailable / lastTestError with stale values.
    final platforms = widget.notifier.state.platforms;
    final current = platforms[widget.platformInfo.key] ?? widget.platformInfo;
    final updatedPlatform = current.copyWith(
      name: _nameController.text.trim().isNotEmpty
          ? _nameController.text.trim()
          : current.name,
      apiKey: _hasApiKey ? _apiKeyController.text.trim() : '',
      url: _apiUrlController.text.trim(),
      model: _modelVersionController.text.trim().isNotEmpty
          ? _modelVersionController.text.trim()
          : current.model,
      parserSubtype: _parserSubtypeController.text.trim().isNotEmpty
          ? _parserSubtypeController.text.trim()
          : current.parserSubtype,
      requiresApiKey: _hasApiKey,
    );

    widget.notifier
        .updatePlatformConfig(widget.platformInfo.key, updatedPlatform);
    Navigator.of(context).pop();
  }

  /// Open API Key management page
  Future<void> _openApiKeyUrl() async {
    try {
      const url = 'https://mineru.net/';
      if (url.isEmpty) return;
      final uri = Uri.parse(url);
      // Desktop/Mobile: open in external browser; Web: open in new tab
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
        webOnlyWindowName: '_blank',
      );
      if (!launched) {
        // Try with platform default method
        await launchUrl(uri);
      }
    } catch (e) {
      if (kDebugMode) {
        print('Error opening URL: $e');
      }
      // Silently fail to avoid interrupting user operation
    }
  }

  Widget _buildHasApiKeySwitch() {
    final l10n = AppLocalizations.of(context)!;
    return SizedBox(
      height: 60,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
            Icon(
              _hasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
              size: 20,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    l10n.aiPlatformHasApiKey,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    l10n.aiPlatformHasApiKeyHint,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: _openApiKeyUrl,
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
              ),
              child: Text(
                l10n.aiPlatformGetMineruApiKey,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.blue.shade700,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
            Switch(
              value: _hasApiKey,
              onChanged: (bool value) {
                setState(() {
                  _hasApiKey = value;
                });
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AlertDialog(
      title: Row(
        children: <Widget>[
          const Icon(Icons.computer, color: Colors.purple, size: 24),
          const SizedBox(width: 8),
          Text('${widget.platformInfo.name} Settings'),
        ],
      ),
      contentPadding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      insetPadding: const EdgeInsets.all(16),
      content: SizedBox(
        width: 900,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(
                    Icons.info_outline,
                    size: 16,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      l10n.aiPlatformTestConnectionHint,
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context)
                            .colorScheme
                            .onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          l10n.aiPlatformBasicInformation,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _nameController,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformDisplayName,
                            hintText: 'MinerU (Local)',
                            prefixIcon: const Icon(Icons.label_outline),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _apiUrlController,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformApiUrl,
                            hintText: l10n.aiPlatformMineruApiUrlHint,
                            prefixIcon: const Icon(Icons.link),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                        const SizedBox(height: 8),
                        DropdownButtonFormField<String>(
                          value: _modelVersionController.text,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformModelVersion,
                            prefixIcon: const Icon(Icons.model_training),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                          items: const <DropdownMenuItem<String>>[
                            DropdownMenuItem(value: 'pipeline', child: Text('pipeline')),
                            DropdownMenuItem(value: 'vlm-auto-engine', child: Text('vlm-auto-engine')),
                            DropdownMenuItem(value: 'hybrid-auto-engine', child: Text('hybrid-auto-engine')),
                            DropdownMenuItem(value: 'vlm-http-client', child: Text('vlm-http-client')),
                            DropdownMenuItem(value: 'hybrid-http-client', child: Text('hybrid-http-client')),
                          ],
                          onChanged: (String? value) {
                            if (value != null) {
                              _modelVersionController.text = value;
                            }
                          },
                        ),
                        const SizedBox(height: 8),
                        DropdownButtonFormField<String>(
                          value: _parserSubtypeController.text.isNotEmpty
                              ? _parserSubtypeController.text
                              : 'local',
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformParserSubtype,
                            prefixIcon: const Icon(Icons.category_outlined),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                          items: <DropdownMenuItem<String>>[
                            DropdownMenuItem<String>(
                              value: 'cloud',
                              child: Text(l10n.aiPlatformParserSubtypeCloud),
                            ),
                            DropdownMenuItem<String>(
                              value: 'local',
                              child: Text(l10n.aiPlatformParserSubtypeLocal),
                            ),
                          ],
                          onChanged: (String? value) {
                            if (value != null) {
                              setState(() {
                                _parserSubtypeController.text = value;
                              });
                            }
                          },
                        ),
                        const SizedBox(height: 16),
                        _buildHasApiKeySwitch(),
                        const SizedBox(height: 8),
                        TextFormField(
                          controller: _apiKeyController,
                          obscureText: _obscureText,
                          decoration: InputDecoration(
                            labelText: _hasApiKey
                                ? l10n.aiPlatformApiKey
                                : '${l10n.aiPlatformApiKey} (${l10n.optional})',
                            hintText: _hasApiKey
                                ? l10n.aiPlatformEnterMineruApiKey
                                : l10n.aiPlatformApiKeyOptionalHint,
                            prefixIcon: const Icon(Icons.key),
                            suffixIcon: IconButton(
                              icon: Icon(
                                _obscureText
                                    ? Icons.visibility
                                    : Icons.visibility_off,
                              ),
                              onPressed: () {
                                setState(() {
                                  _obscureText = !_obscureText;
                                });
                              },
                            ),
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          l10n.aiPlatformOcrSettings,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Column(
                          children: <Widget>[
                            SwitchListTile(
                              title: Text(l10n.aiPlatformFormulaOcr),
                              subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle),
                              value: _formulaOcr,
                              onChanged: (bool value) {
                                setState(() {
                                  _formulaOcr = value;
                                });
                              },
                              contentPadding: EdgeInsets.zero,
                            ),
                            SwitchListTile(
                              title: Text(l10n.aiPlatformTableOcr),
                              subtitle: Text(l10n.aiPlatformTableOcrSubtitle),
                              value: _tableOcr,
                              onChanged: (bool value) {
                                setState(() {
                                  _tableOcr = value;
                                });
                              },
                              contentPadding: EdgeInsets.zero,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (_testResult != null) ...<Widget>[
                const SizedBox(height: 12),
                Builder(
                  builder: (BuildContext ctx) {
                    final PlatformTestVisualState visualState =
                        resolvePlatformTestVisualState(
                      lastTestSuccess: _lastTestSuccess,
                      rawResult: _lastTestRawResult,
                    );
                    final style = platformTestResultStyle(visualState);
                    return Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: style.backgroundColor,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: style.borderColor),
                      ),
                      width: double.infinity,
                      child: Row(
                        children: <Widget>[
                          Icon(
                            style.icon,
                            color: style.contentColor,
                          ),
                          const SizedBox(width: 8),
                          Flexible(
                            child: SelectableText(
                              _testResult!,
                              style: TextStyle(color: style.contentColor),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ],
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.aiPlatformCancel),
        ),
        OutlinedButton(
          onPressed: _isTestingConnection ? null : _testConnection,
          child: _isTestingConnection
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(l10n.aiPlatformTestConnection),
        ),
        FilledButton(
          onPressed: _saveConfig,
          child: Text(l10n.aiPlatformSave),
        ),
      ],
    );
  }

  bool _isSuccessMessage(String? message) {
    if (message == null) return false;
    return message.toLowerCase().contains('success');
  }
}
