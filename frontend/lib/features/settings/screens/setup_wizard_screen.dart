// Copyright 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../l10n/app_localizations.dart';

import '../../../app/app_router.dart';
import '../../../shared/providers/settings_provider.dart'
    show GlobalSettings, GlobalSettingsNotifier, globalSettingsProvider;
import '../../../shared/services/config_service.dart'
    show AIPlatformInfo, ConfigService;
import 'ai_platform_settings.dart'
    show
        AIPlatformSettings,
        AIPlatformSettingsNotifier,
        aiPlatformSettingsProvider;

/// Simple first-time configuration wizard.
class SetupWizardScreen extends ConsumerStatefulWidget {
  const SetupWizardScreen({super.key});

  @override
  ConsumerState<SetupWizardScreen> createState() => _SetupWizardScreenState();
}

class _SetupWizardScreenState extends ConsumerState<SetupWizardScreen> {
  int _currentStep = 0;
  bool _needsPdfTranslation = true;
  String? _selectedPlatformKey;

  // MinerU platform selection
  String _selectedMineruPlatform = 'mineru'; // 'mineru' or 'mineru_local'

  // MinerU Cloud config state (embedded form)
  late TextEditingController _mineruNameController;
  late TextEditingController _mineruApiKeyController;
  late TextEditingController _mineruApiUrlController;
  late TextEditingController _mineruParserSubtypeController;
  bool _mineruObscureText = true;
  bool _mineruHasApiKey = true;  // Whether MinerU Cloud requires API key
  String? _mineruTestResult;
  bool? _mineruLastTestSuccess;
  bool _mineruIsTestingConnection = false;
  bool _mineruFormulaOcr = true;
  bool _mineruTableOcr = true;
  bool _mineruInitializedFromSettings = false;

  // MinerU Local config state (embedded form)
  late TextEditingController _mineruLocalNameController;
  late TextEditingController _mineruLocalApiKeyController;
  late TextEditingController _mineruLocalApiUrlController;
  late TextEditingController _mineruLocalModelVersionController;
  late TextEditingController _mineruLocalParserSubtypeController;
  bool _mineruLocalObscureText = true;
  bool _mineruLocalHasApiKey = false;  // Whether MinerU Local requires API key (default false for local)
  String? _mineruLocalTestResult;
  bool? _mineruLocalLastTestSuccess;
  bool _mineruLocalIsTestingConnection = false;
  bool _mineruLocalFormulaOcr = true;
  bool _mineruLocalTableOcr = true;
  bool _mineruLocalInitializedFromSettings = false;

  // LLM config state (embedded form for selected platform)
  String? _llmFormPlatformKey;
  late TextEditingController _llmNameController;
  late TextEditingController _llmUrlController;
  late TextEditingController _llmModelController;
  late TextEditingController _llmApiKeyController;
  late TextEditingController _llmMaxTokensController;
  late TextEditingController _llmTemperatureController;
  late TextEditingController _llmChunkSizeController;
  late TextEditingController _llmConcurrentController;
  late TextEditingController _llmTimeoutController;
  late TextEditingController _llmWriteTimeoutController;
  String _llmThinkingMode = 'disable';
  String _llmApiProtocol = 'openai';  // API protocol: openai, ollama, anthropic
  bool _llmHasApiKey = true;  // Whether platform has API key (if false, API key is optional)
  late final FocusNode _llmTemperatureFocusNode;
  bool _llmTemperatureFocused = false;
  bool _llmObscureText = true;
  String? _llmTestResult;
  bool? _llmLastTestSuccess;
  bool _llmIsTestingConnection = false;
  bool _llmIsLoadingModels = false;

  void _goHome() {
    if (kDebugMode) {
      print('[SetupWizard] Navigating to Home at ${DateTime.now()}');
    }
    context.go(AppRouter.homeRoute);
  }

  /// Platform connection status color and label (same logic as Quick Settings).
  static Color _platformStatusColor(AIPlatformInfo? p) {
    if (p == null) return Colors.grey;
    final bool configured = p.isConfigured;
    final bool? available = p.isApiAvailable;
    if (!configured) return Colors.grey;
    if (available ?? false) return Colors.green;
    if (available == false) return Colors.red;
    return Colors.grey;
  }

  static String _platformStatusText(
    AIPlatformInfo? p,
    AppLocalizations l10n,
  ) {
    if (p == null) return l10n.quickSettingsNotConfigured;
    if (!p.isConfigured) return l10n.quickSettingsNotConfigured;
    if (p.isApiAvailable ?? false) return l10n.quickSettingsApiOk;
    if (p.isApiAvailable == false) {
      return p.lastTestError ?? l10n.quickSettingsApiUnavailable;
    }
    return l10n.quickSettingsNotTestedYet;
  }

  /// True when platform is not configured or connection not verified (show prominent hint).
  /// For platforms that don't require API key, only show warning when explicitly tested and failed.
  static bool _platformConnectionUnavailable(AIPlatformInfo? p) {
    if (p == null) return true;
    if (!p.isConfigured) return true;
    // For platforms that don't require API key, don't show warning if just not tested yet (null)
    // Only show warning when explicitly failed (false)
    if (!p.requiresApiKey && p.isApiAvailable == null) return false;
    return p.isApiAvailable != true;
  }

  /// Open API Key management page (same behavior as AI Platform settings).
  Future<void> _openApiKeyUrl(String url) async {
    try {
      if (url.isEmpty) return;
      final uri = Uri.parse(url);
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
        webOnlyWindowName: '_blank',
      );
      if (!launched) {
        await launchUrl(uri);
      }
    } catch (e) {
      if (kDebugMode) {
        // Silent failure to avoid interrupting user flow.
        // ignore: avoid_print
        print('Error opening URL in setup wizard: $e');
      }
    }
  }

  @override
  void initState() {
    super.initState();
    // Cloud MinerU controllers
    _mineruNameController = TextEditingController();
    _mineruApiKeyController = TextEditingController();
    _mineruApiUrlController = TextEditingController();
    _mineruParserSubtypeController = TextEditingController(text: 'cloud');
    // Local MinerU controllers
    _mineruLocalNameController = TextEditingController();
    _mineruLocalApiKeyController = TextEditingController();
    _mineruLocalApiUrlController = TextEditingController();
    _mineruLocalModelVersionController = TextEditingController(text: 'hybrid-auto-engine');
    _mineruLocalParserSubtypeController = TextEditingController(text: 'local');
    // LLM controllers
    _llmNameController = TextEditingController();
    _llmUrlController = TextEditingController();
    _llmModelController = TextEditingController();
    _llmApiKeyController = TextEditingController();
    _llmMaxTokensController = TextEditingController(text: '4096');
    _llmTemperatureController = TextEditingController(text: '0.3');
    _llmChunkSizeController = TextEditingController(text: '3000');
    _llmConcurrentController = TextEditingController(text: '5');
    _llmTimeoutController = TextEditingController(text: '200');
    _llmWriteTimeoutController = TextEditingController(text: '300');
    _llmTemperatureFocusNode = FocusNode();
    _llmTemperatureFocusNode.addListener(() {
      setState(() {
        _llmTemperatureFocused = _llmTemperatureFocusNode.hasFocus;
      });
    });
  }

  @override
  void dispose() {
    // Cloud MinerU controllers
    _mineruNameController.dispose();
    _mineruApiKeyController.dispose();
    _mineruApiUrlController.dispose();
    _mineruParserSubtypeController.dispose();
    // Local MinerU controllers
    _mineruLocalNameController.dispose();
    _mineruLocalApiKeyController.dispose();
    _mineruLocalApiUrlController.dispose();
    _mineruLocalModelVersionController.dispose();
    _mineruLocalParserSubtypeController.dispose();
    // LLM controllers
    _llmNameController.dispose();
    _llmUrlController.dispose();
    _llmModelController.dispose();
    _llmApiKeyController.dispose();
    _llmMaxTokensController.dispose();
    _llmTemperatureController.dispose();
    _llmChunkSizeController.dispose();
    _llmConcurrentController.dispose();
    _llmTimeoutController.dispose();
    _llmWriteTimeoutController.dispose();
    _llmTemperatureFocusNode.dispose();
    super.dispose();
  }

  /// Migrate old model version short names to official MinerU 3.2 names.
  static const Map<String, String> _migrationMap = {
    'vlm': 'vlm-auto-engine',
    'hybrid': 'hybrid-auto-engine',
  };
  static String _normalizeModelVersion(String mv) =>
      _migrationMap[mv] ?? mv;

  void _nextStep() {
    setState(() {
      if (_currentStep < 2) {
        _currentStep++;
      } else {
        _goHome();
      }
    });
  }

  void _prevStep() {
    if (_currentStep == 0) return;
    setState(() {
      _currentStep--;
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final AIPlatformSettings aiSettings = ref.watch(aiPlatformSettingsProvider);
    final AIPlatformSettingsNotifier aiNotifier =
        ref.read(aiPlatformSettingsProvider.notifier);
    _ensureMineruInitialValues(aiSettings);
    _ensureMineruLocalInitialValues(aiSettings);
    _ensureSelectedPlatformInitialized(aiSettings);
    final GlobalSettings globalSettings = ref.watch(globalSettingsProvider);
    final GlobalSettingsNotifier globalNotifier =
        ref.read(globalSettingsProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.setupWizardTitle),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: _goHome,
        ),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.home_outlined),
            tooltip: AppLocalizations.of(context)!.backToHome,
            onPressed: _goHome,
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Card(
              elevation: 4,
              margin: const EdgeInsets.all(16),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    _buildStepHeader(),
                    const SizedBox(height: 16),
                    Expanded(
                      child: SingleChildScrollView(
                        child: _buildStepContent(
                          l10n,
                          aiSettings,
                          aiNotifier,
                          globalSettings,
                          globalNotifier,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildStepActions(aiSettings, aiNotifier),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStepHeader() {
    final l10n = AppLocalizations.of(context)!;
    final titles = <String>[
      l10n.setupWizardStepWelcome,
      l10n.aiPlatformCategoryLanguageModels,
      l10n.setupWizardStepMineru,
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          titles[_currentStep],
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(
          value: (_currentStep + 1) / 3,
        ),
      ],
    );
  }

  Widget _buildStepContent(
    AppLocalizations l10n,
    AIPlatformSettings aiSettings,
    AIPlatformSettingsNotifier aiNotifier,
    GlobalSettings globalSettings,
    GlobalSettingsNotifier globalNotifier,
  ) {
    switch (_currentStep) {
      case 0:
        return _buildWelcomeStep(l10n, globalSettings, globalNotifier);
      case 1:
        return _buildModelStep(aiSettings, aiNotifier);
      case 2:
      default:
        return _buildMineruStep(l10n, aiSettings, aiNotifier);
    }
  }

  void _syncLlmFormFromPlatform(
      String platformKey, AIPlatformSettings settings,) {
    final AIPlatformInfo? p = settings.platforms[platformKey];
    if (p == null) return;
    _llmFormPlatformKey = platformKey;
    _llmNameController.text = p.name;
    _llmUrlController.text = p.url;
    _llmModelController.text = p.model;
    _llmApiKeyController.text = p.apiKey ?? '';
    _llmMaxTokensController.text = p.maxTokens.toString();
    _llmTemperatureController.text = p.temperature.toString();
    _llmChunkSizeController.text = p.chunkSize.toString();
    _llmConcurrentController.text = p.concurrent.toString();
    _llmTimeoutController.text = p.timeout.toString();
    _llmWriteTimeoutController.text = p.writeTimeout.toString();
    _llmThinkingMode = p.thinkingMode;
    _llmApiProtocol = p.apiProtocol;
    _llmHasApiKey = p.requiresApiKey;
  }

  Widget _buildWelcomeStep(
    AppLocalizations l10n,
    GlobalSettings globalSettings,
    GlobalSettingsNotifier globalNotifier,
  ) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          l10n.setupWizardWelcomeIntro,
          style: const TextStyle(fontSize: 18),
        ),
        const SizedBox(height: 10),
        Text(
          l10n.setupWizardWelcomeBody,
          style: const TextStyle(fontSize: 18),
        ),
        // Language selector removed - now available in Home screen for desktop
        // and Settings -> General for all platforms
      ],
    );

  void _ensureMineruInitialValues(AIPlatformSettings settings) {
    if (_mineruInitializedFromSettings) return;
    final AIPlatformInfo? mineru = settings.platforms['mineru'];
    if (mineru != null) {
      _mineruNameController.text = mineru.name;
      _mineruApiKeyController.text = mineru.apiKey ?? '';
      _mineruApiUrlController.text = mineru.url;
      // Parser subtype: default to 'cloud' for cloud MinerU
      _mineruParserSubtypeController.text = mineru.parserSubtype ?? 'cloud';
      // Requires API key: load from saved config (default true for cloud)
      _mineruHasApiKey = mineru.requiresApiKey;
    }
    _mineruInitializedFromSettings = true;
  }

  void _ensureMineruLocalInitialValues(AIPlatformSettings settings) {
    if (_mineruLocalInitializedFromSettings) return;
    final AIPlatformInfo? mineruLocal = settings.platforms['mineru_local'];
    if (mineruLocal != null) {
      _mineruLocalNameController.text = mineruLocal.name;
      _mineruLocalApiKeyController.text = mineruLocal.apiKey ?? '';
      _mineruLocalApiUrlController.text = mineruLocal.url;
      // Model version: load from saved config or use default
      _mineruLocalModelVersionController.text =
          _normalizeModelVersion(mineruLocal.model.isNotEmpty ? mineruLocal.model : 'hybrid-auto-engine');
      // Parser subtype: default to 'local' for local MinerU
      _mineruLocalParserSubtypeController.text = mineruLocal.parserSubtype ?? 'local';
      // Requires API key: load from saved config (default false for local)
      _mineruLocalHasApiKey = mineruLocal.requiresApiKey;
    }
    _mineruLocalInitializedFromSettings = true;
  }

  void _ensureSelectedPlatformInitialized(AIPlatformSettings settings) {
    if (_selectedPlatformKey != null) return;
    final String defaultKey = settings.defaultPlatform;
    if (settings.platforms.containsKey(defaultKey)) {
      _selectedPlatformKey = defaultKey;
      return;
    }
    // Fallback to first LLM platform if default not found.
    final Iterable<AIPlatformInfo> llmPlatforms = settings.platforms.values
        .where((AIPlatformInfo p) => p.platformType == 'llm');
    if (llmPlatforms.isNotEmpty) {
      _selectedPlatformKey = llmPlatforms.first.key;
    }
  }

  Widget _buildMineruStep(
    AppLocalizations l10n,
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          l10n.setupWizardMineruQuestion,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 8),
        RadioListTile<bool>(
          title: Text(l10n.setupWizardMineruYes),
          value: true,
          groupValue: _needsPdfTranslation,
          onChanged: (value) {
            if (value == null) return;
            setState(() {
              _needsPdfTranslation = value;
            });
          },
        ),
        RadioListTile<bool>(
          title: Text(l10n.setupWizardMineruNo),
          value: false,
          groupValue: _needsPdfTranslation,
          onChanged: (value) {
            if (value == null) return;
            setState(() {
              _needsPdfTranslation = value;
            });
          },
        ),
        const SizedBox(height: 16),
        if (_needsPdfTranslation) ...<Widget>[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.shade200),
            ),
            child: Text(
              l10n.setupWizardMineruDescription,
              style: const TextStyle(fontSize: 13),
            ),
          ),
          const SizedBox(height: 16),
          // MinerU Platform Selection
          Text(
            l10n.setupWizardSelectMineruPlatform,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            initialValue: _selectedMineruPlatform,
            decoration: InputDecoration(
              labelText: l10n.setupWizardSelectMineruPlatform,
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            ),
            items: <DropdownMenuItem<String>>[
              DropdownMenuItem<String>(
                value: 'mineru',
                child: Text(l10n.setupWizardMineruCloudOption),
              ),
              DropdownMenuItem<String>(
                value: 'mineru_local',
                child: Text(l10n.setupWizardMineruLocalOption),
              ),
            ],
            onChanged: (value) {
              if (value == null) return;
              setState(() {
                _selectedMineruPlatform = value;
              });
            },
          ),
          const SizedBox(height: 16),
          // Show config form based on selected platform
          if (_selectedMineruPlatform == 'mineru')
            _buildEmbeddedMineruCloudForm(settings, notifier)
          else
            _buildEmbeddedMineruLocalForm(settings, notifier),
        ] else
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              l10n.setupWizardMineruSkipped,
              style: const TextStyle(fontSize: 13),
            ),
          ),
      ],
    );

  Widget _buildEmbeddedMineruCloudForm(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final AIPlatformInfo? mineru = settings.platforms['mineru'];
    final Color statusColor = _platformStatusColor(mineru);
    final String statusText = _platformStatusText(mineru, l10n);
    // Hide unavailable hint if connection test was successful
    final bool showUnavailableHint = _platformConnectionUnavailable(mineru) && 
        (_mineruLastTestSuccess != true);
    final String? mineruTokenLink = mineru?.tokenLink;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.setupWizardMineruConfigTitle,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 12),
            Icon(Icons.circle, size: 10, color: statusColor),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                statusText,
                style: TextStyle(
                  fontSize: 12,
                  color: statusColor,
                  fontWeight: FontWeight.w500,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: TextFormField(
                controller: _mineruNameController,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformDisplayName,
                  hintText: 'MinerU (Cloud)',
                  prefixIcon: const Icon(Icons.label_outline),
                  border: const OutlineInputBorder(),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _mineruParserSubtypeController.text.isNotEmpty
                    ? _mineruParserSubtypeController.text
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
                    _mineruParserSubtypeController.text = value;
                  }
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _mineruApiUrlController,
          decoration: InputDecoration(
            labelText: l10n.aiPlatformApiUrl,
            hintText: l10n.aiPlatformMineruApiUrlHint,
            prefixIcon: const Icon(Icons.link),
            border: const OutlineInputBorder(),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: _buildMineruHasApiKeySwitch(l10n, tokenLink: mineruTokenLink),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _wrapIfUnavailable(
                showUnavailableHint && _mineruHasApiKey,
                child: TextFormField(
                  controller: _mineruApiKeyController,
                  obscureText: _mineruObscureText,
                  decoration: InputDecoration(
                    labelText: _mineruHasApiKey
                        ? l10n.aiPlatformApiKey
                        : '${l10n.aiPlatformApiKey} (${l10n.optional})',
                    hintText: _mineruHasApiKey
                        ? l10n.aiPlatformEnterMineruApiKey
                        : l10n.aiPlatformApiKeyOptionalHint,
                    prefixIcon: const Icon(Icons.key),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _mineruObscureText ? Icons.visibility : Icons.visibility_off,
                      ),
                      onPressed: () {
                        setState(() {
                          _mineruObscureText = !_mineruObscureText;
                        });
                      },
                    ),
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                  ),
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
              child: SwitchListTile.adaptive(
                title: Text(l10n.aiPlatformFormulaOcr),
                subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle),
                value: _mineruFormulaOcr,
                onChanged: (bool value) {
                  setState(() {
                    _mineruFormulaOcr = value;
                  });
                },
              ),
            ),
            Expanded(
              child: SwitchListTile.adaptive(
                title: Text(l10n.aiPlatformTableOcr),
                subtitle: Text(l10n.aiPlatformTableOcrSubtitle),
                value: _mineruTableOcr,
                onChanged: (bool value) {
                  setState(() {
                    _mineruTableOcr = value;
                  });
                },
              ),
            ),
          ],
        ),
        if (_mineruTestResult != null) ...<Widget>[
          const SizedBox(height: 8),
          Builder(
            builder: (BuildContext ctx) {
              final bool isSuccess = _mineruLastTestSuccess ?? false;
              final Color bgColor =
                  isSuccess ? Colors.green.shade50 : Colors.red.shade50;
              final Color borderColor =
                  isSuccess ? Colors.green.shade300 : Colors.red.shade300;
              final Color contentColor =
                  isSuccess ? Colors.green.shade700 : Colors.red.shade700;
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: borderColor),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      isSuccess ? Icons.check_circle : Icons.error,
                      color: contentColor,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SelectableText(
                        _mineruTestResult!,
                        style: TextStyle(
                          color: contentColor,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
        const SizedBox(height: 8),
        _wrapIfUnavailable(
          showUnavailableHint,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              if (showUnavailableHint) ...<Widget>[
                Expanded(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.orange.shade300),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.warning_amber_rounded,
                            color: Colors.orange.shade700, size: 18,),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            l10n.localeName == 'zh'
                                ? '当前连接不可用，请配置 API URL 并点击「测试连接」以确认平台可用。'
                                : l10n.localeName == 'ja'
                                    ? '接続不可。API URL を設定し「接続テスト」をクリックして確認してください。'
                                    : l10n.localeName == 'ko'
                                        ? '연결 불가. API URL을 설정하고 "연결 테스트"를 클릭하여 확인하세요.'
                                        : 'Connection unavailable. Please configure API URL and click "Test Connection" to verify.',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.orange.shade900,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
              ],
              OutlinedButton(
                onPressed: _mineruIsTestingConnection
                    ? null
                    : () => _testMineruConnection(notifier),
                child: _mineruIsTestingConnection
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(l10n.aiPlatformTestConnection),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEmbeddedMineruLocalForm(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final AIPlatformInfo? mineruLocal = settings.platforms['mineru_local'];
    final Color statusColor = _platformStatusColor(mineruLocal);
    final String statusText = _platformStatusText(mineruLocal, l10n);
    // Hide unavailable hint if connection test was successful
    final bool showUnavailableHint = _platformConnectionUnavailable(mineruLocal) && 
        (_mineruLocalLastTestSuccess != true);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              l10n.setupWizardMineruConfigTitle,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 12),
            Icon(Icons.circle, size: 10, color: statusColor),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                statusText,
                style: TextStyle(
                  fontSize: 12,
                  color: statusColor,
                  fontWeight: FontWeight.w500,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: TextFormField(
                controller: _mineruLocalNameController,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformDisplayName,
                  hintText: 'MinerU (Local)',
                  prefixIcon: const Icon(Icons.label_outline),
                  border: const OutlineInputBorder(),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<String>(
                value: _mineruLocalModelVersionController.text,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformModelVersion,
                  prefixIcon: const Icon(Icons.schema_outlined),
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
                    _mineruLocalModelVersionController.text = value;
                  }
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: TextFormField(
                controller: _mineruLocalApiUrlController,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformApiUrl,
                  hintText: 'http://localhost:8920',
                  prefixIcon: const Icon(Icons.link),
                  border: const OutlineInputBorder(),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _mineruLocalParserSubtypeController.text.isNotEmpty
                    ? _mineruLocalParserSubtypeController.text
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
                    _mineruLocalParserSubtypeController.text = value;
                  }
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: _buildMineruLocalHasApiKeySwitch(l10n),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextFormField(
                controller: _mineruLocalApiKeyController,
                obscureText: _mineruLocalObscureText,
                decoration: InputDecoration(
                  labelText: _mineruLocalHasApiKey
                      ? l10n.aiPlatformApiKey
                      : '${l10n.aiPlatformApiKey} (${l10n.optional})',
                  hintText: _mineruLocalHasApiKey
                      ? l10n.aiPlatformEnterMineruApiKey
                      : l10n.aiPlatformApiKeyOptionalHint,
                  prefixIcon: const Icon(Icons.key),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _mineruLocalObscureText ? Icons.visibility : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(() {
                        _mineruLocalObscureText = !_mineruLocalObscureText;
                      });
                    },
                  ),
                  border: const OutlineInputBorder(),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
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
              child: SwitchListTile.adaptive(
                title: Text(l10n.aiPlatformFormulaOcr),
                subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle),
                value: _mineruLocalFormulaOcr,
                onChanged: (bool value) {
                  setState(() {
                    _mineruLocalFormulaOcr = value;
                  });
                },
              ),
            ),
            Expanded(
              child: SwitchListTile.adaptive(
                title: Text(l10n.aiPlatformTableOcr),
                subtitle: Text(l10n.aiPlatformTableOcrSubtitle),
                value: _mineruLocalTableOcr,
                onChanged: (bool value) {
                  setState(() {
                    _mineruLocalTableOcr = value;
                  });
                },
              ),
            ),
          ],
        ),
        if (_mineruLocalTestResult != null) ...<Widget>[
          const SizedBox(height: 8),
          Builder(
            builder: (BuildContext ctx) {
              final bool isSuccess = _mineruLocalLastTestSuccess ?? false;
              final Color bgColor =
                  isSuccess ? Colors.green.shade50 : Colors.red.shade50;
              final Color borderColor =
                  isSuccess ? Colors.green.shade300 : Colors.red.shade300;
              final Color contentColor =
                  isSuccess ? Colors.green.shade700 : Colors.red.shade700;
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: bgColor,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: borderColor),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      isSuccess ? Icons.check_circle : Icons.error,
                      color: contentColor,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SelectableText(
                        _mineruLocalTestResult!,
                        style: TextStyle(
                          color: contentColor,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
        const SizedBox(height: 8),
        _wrapIfUnavailable(
          showUnavailableHint,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              if (showUnavailableHint) ...<Widget>[
                Expanded(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.orange.shade300),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.warning_amber_rounded,
                            color: Colors.orange.shade700, size: 18,),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            l10n.localeName == 'zh'
                                ? '当前连接不可用，请配置 API URL 并点击「测试连接」以确认平台可用。'
                                : l10n.localeName == 'ja'
                                    ? '接続不可。API URL を設定し「接続テスト」をクリックして確認してください。'
                                    : l10n.localeName == 'ko'
                                        ? '연결 불가. API URL을 설정하고 "연결 테스트"를 클릭하여 확인하세요.'
                                        : 'Connection unavailable. Please configure API URL and click "Test Connection" to verify.',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.orange.shade900,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
              ],
              OutlinedButton(
                onPressed: _mineruLocalIsTestingConnection
                    ? null
                    : () => _testMineruLocalConnection(notifier),
                child: _mineruLocalIsTestingConnection
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(l10n.aiPlatformTestConnection),
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// Wraps [child] in an orange highlight box when [unavailable]; otherwise returns [child].
  Widget _wrapIfUnavailable(bool unavailable, {required Widget child}) {
    if (!unavailable) return child;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.orange.shade50.withOpacity(0.4),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.orange.shade400, width: 2),
      ),
      child: child,
    );
  }

  Future<void> _testMineruConnection(
    AIPlatformSettingsNotifier notifier,
  ) async {
    final l10n = AppLocalizations.of(context)!;
    // Check if API key is required
    if (_mineruHasApiKey && _mineruApiKeyController.text.trim().isEmpty) {
      setState(() {
        _mineruTestResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
        _mineruLastTestSuccess = false;
      });
      return;
    }

    setState(() {
      _mineruIsTestingConnection = true;
      _mineruTestResult = null;
      _mineruLastTestSuccess = null;
    });

    try {
      final Map<String, dynamic> result = await notifier.testConnection(
        'mineru',
        _mineruApiKeyController.text.trim(),
        baseUrlOverride: _mineruApiUrlController.text.trim(),
      );
      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      final loc = AppLocalizations.of(context)!;
      setState(() {
        _mineruLastTestSuccess = success;
        _mineruTestResult = success
            ? loc.aiPlatformConnectionTestSucceeded
            : loc.aiPlatformConnectionTestFailed(
                result['message']?.toString() ?? '',
              );
      });
    } catch (e) {
      if (!mounted) return;
      final loc = AppLocalizations.of(context)!;
      setState(() {
        _mineruLastTestSuccess = false;
        _mineruTestResult = loc.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _mineruIsTestingConnection = false;
        });
      }
    }
  }

  Future<void> _testMineruLocalConnection(
    AIPlatformSettingsNotifier notifier,
  ) async {
    final l10n = AppLocalizations.of(context)!;
    
    // Check if API URL is required
    if (_mineruLocalApiUrlController.text.trim().isEmpty) {
      setState(() {
        _mineruLocalTestResult = l10n.aiPlatformPleaseEnterApiUrlFirst;
        _mineruLocalLastTestSuccess = false;
      });
      return;
    }
    
    // Check if API key is required
    if (_mineruLocalHasApiKey && _mineruLocalApiKeyController.text.trim().isEmpty) {
      setState(() {
        _mineruLocalTestResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
        _mineruLocalLastTestSuccess = false;
      });
      return;
    }

    setState(() {
      _mineruLocalIsTestingConnection = true;
      _mineruLocalTestResult = null;
      _mineruLocalLastTestSuccess = null;
    });

    try {
      final Map<String, dynamic> result = await notifier.testConnection(
        'mineru_local',
        _mineruLocalApiKeyController.text.trim(),
        baseUrlOverride: _mineruLocalApiUrlController.text.trim(),
      );
      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      final loc = AppLocalizations.of(context)!;
      setState(() {
        _mineruLocalLastTestSuccess = success;
        _mineruLocalTestResult = success
            ? loc.aiPlatformConnectionTestSucceeded
            : loc.aiPlatformConnectionTestFailed(
                result['message']?.toString() ?? '',
              );
      });
    } catch (e) {
      if (!mounted) return;
      final loc = AppLocalizations.of(context)!;
      setState(() {
        _mineruLocalLastTestSuccess = false;
        _mineruLocalTestResult = loc.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _mineruLocalIsTestingConnection = false;
        });
      }
    }
  }

  void _saveMineruConfig(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    AIPlatformInfo? mineru, {
    bool showSnackBar = true,
  }) {
    final AIPlatformInfo? current = mineru ?? settings.platforms['mineru'];
    final AIPlatformInfo updated;
    if (current == null) {
      // Create new platform if it doesn't exist
      updated = AIPlatformInfo(
        key: 'mineru',
        name: _mineruNameController.text.trim().isNotEmpty
            ? _mineruNameController.text.trim()
            : 'MinerU (Cloud)',
        url: _mineruApiUrlController.text.trim(),
        model: 'vlm', // Cloud MinerU API v4 supports: pipeline, vlm, MinerU-HTML
        apiKey: _mineruApiKeyController.text.trim(),
        parserSubtype: _mineruParserSubtypeController.text.trim().isNotEmpty
            ? _mineruParserSubtypeController.text.trim()
            : 'cloud',
        maxTokens: 0,
        temperature: 0,
        temperatureMin: 0,
        temperatureMax: 0,
        thinkingModeSupported: false,
        thinkingMode: 'disable',
        platformType: 'pdf_parser',
        requiresApiKey: _mineruHasApiKey,
      );
    } else {
      updated = current.copyWith(
        name: _mineruNameController.text.trim().isNotEmpty
            ? _mineruNameController.text.trim()
            : current.name,
        apiKey: _mineruApiKeyController.text.trim(),
        url: _mineruApiUrlController.text.trim(),
        model: 'vlm', // Cloud MinerU API v4 supports: pipeline, vlm, MinerU-HTML
        parserSubtype: _mineruParserSubtypeController.text.trim().isNotEmpty
            ? _mineruParserSubtypeController.text.trim()
            : current.parserSubtype,
        requiresApiKey: _mineruHasApiKey,
      );
    }
    notifier.updatePlatformConfig('mineru', updated);
    if (showSnackBar && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.setupWizardMineruSaved),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  void _saveMineruLocalConfig(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    AIPlatformInfo? mineruLocal, {
    bool showSnackBar = true,
  }) {
    final AIPlatformInfo? current = mineruLocal ?? settings.platforms['mineru_local'];
    final AIPlatformInfo updated;
    if (current == null) {
      // Create new platform if it doesn't exist
      updated = AIPlatformInfo(
        key: 'mineru_local',
        name: _mineruLocalNameController.text.trim().isNotEmpty
            ? _mineruLocalNameController.text.trim()
            : 'MinerU (Local)',
        url: _mineruLocalApiUrlController.text.trim(),
        model: _mineruLocalModelVersionController.text.trim().isNotEmpty
            ? _mineruLocalModelVersionController.text.trim()
            : 'hybrid-auto-engine',
        apiKey: _mineruLocalApiKeyController.text.trim(),
        parserSubtype: _mineruLocalParserSubtypeController.text.trim().isNotEmpty
            ? _mineruLocalParserSubtypeController.text.trim()
            : 'local',
        maxTokens: 0,
        temperature: 0,
        temperatureMin: 0,
        temperatureMax: 0,
        thinkingModeSupported: false,
        thinkingMode: 'disable',
        platformType: 'pdf_parser',
        requiresApiKey: _mineruLocalHasApiKey,
      );
    } else {
      updated = current.copyWith(
        name: _mineruLocalNameController.text.trim().isNotEmpty
            ? _mineruLocalNameController.text.trim()
            : current.name,
        apiKey: _mineruLocalApiKeyController.text.trim(),
        url: _mineruLocalApiUrlController.text.trim(),
        model: _mineruLocalModelVersionController.text.trim().isNotEmpty
            ? _mineruLocalModelVersionController.text.trim()
            : current.model,
        parserSubtype: _mineruLocalParserSubtypeController.text.trim().isNotEmpty
            ? _mineruLocalParserSubtypeController.text.trim()
            : current.parserSubtype,
        requiresApiKey: _mineruLocalHasApiKey,
      );
    }
    notifier.updatePlatformConfig('mineru_local', updated);
    if (showSnackBar && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.setupWizardMineruSaved),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  Widget _buildModelStep(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final List<AIPlatformInfo> llmPlatforms = settings.platforms.values
        .where((AIPlatformInfo p) => p.platformType == 'llm')
        .toList();
    if (settings.platformOrder.isNotEmpty) {
      llmPlatforms.sort((AIPlatformInfo a, AIPlatformInfo b) {
        final int indexA = settings.platformOrder.indexOf(a.key);
        final int indexB = settings.platformOrder.indexOf(b.key);
        if (indexA == -1 && indexB == -1) return 0;
        if (indexA == -1) return 1;
        if (indexB == -1) return -1;
        return indexA.compareTo(indexB);
      });
    }

    // Sync form when selected platform changes (e.g. first time entering step or dropdown change)
    if (_currentStep == 1 &&
        _selectedPlatformKey != null &&
        _llmFormPlatformKey != _selectedPlatformKey) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _selectedPlatformKey != null) {
          _syncLlmFormFromPlatform(_selectedPlatformKey!, settings);
          setState(() {});
        }
      });
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          l10n.aiPlatformCategoryLanguageModels,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        if (llmPlatforms.isEmpty)
          Text(
            l10n.setupWizardNoLlmPlatforms,
            style: const TextStyle(fontSize: 13),
          )
        else ...<Widget>[
          DropdownButtonFormField<String>(
            initialValue: _selectedPlatformKey,
            decoration: InputDecoration(
              labelText: l10n.setupWizardSelectLlmPlatform,
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            ),
            items: llmPlatforms.map(
              (AIPlatformInfo p) {
                final Color statusColor = _platformStatusColor(p);
                final String tooltip = _platformStatusText(p, l10n);
                return DropdownMenuItem<String>(
                  value: p.key,
                  child: Tooltip(
                    message: tooltip,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.circle, size: 10, color: statusColor),
                        const SizedBox(width: 8),
                        Flexible(
                          child: Text(
                            p.name,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ).toList(),
            onChanged: (String? value) {
              if (value == null) return;
              setState(() {
                _selectedPlatformKey = value;
                _llmFormPlatformKey = null; // force sync on next build
              });
            },
          ),
          if (_selectedPlatformKey != null) ...<Widget>[
            const SizedBox(height: 16),
            _buildEmbeddedLlmForm(settings, notifier, l10n),
          ],
        ],
      ],
    );
  }

  Widget _buildEmbeddedLlmForm(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    AppLocalizations l10n,
  ) {
    final AIPlatformInfo? platform = _selectedPlatformKey == null
        ? null
        : settings.platforms[_selectedPlatformKey];
    if (platform == null) return const SizedBox.shrink();

    // Hide unavailable hint if connection test was successful
    final bool showUnavailableHint = _platformConnectionUnavailable(platform) && 
        (_llmLastTestSuccess != true);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // Left column: Basic Information
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    l10n.aiPlatformBasicInformation,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _llmNameController,
                    decoration: InputDecoration(
                      labelText: l10n.aiPlatformPlatformName,
                      hintText: l10n.aiPlatformPlatformNameHint,
                      border: const OutlineInputBorder(),
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _llmUrlController,
                    decoration: InputDecoration(
                      labelText: l10n.aiPlatformApiUrl,
                      hintText: l10n.aiPlatformApiUrlHint,
                      border: const OutlineInputBorder(),
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: TextFormField(
                          controller: _llmModelController,
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
                        onPressed: _llmIsLoadingModels ? null : _loadLlmModels,
                        icon: _llmIsLoadingModels
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.search, size: 18),
                        label: Text(l10n.aiPlatformList),
                        style: OutlinedButton.styleFrom(
                          padding:
                              const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          minimumSize: const Size(0, 48),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _buildLlmApiProtocolField(l10n),
                  const SizedBox(height: 16),
                  _buildLlmHasApiKeySwitch(l10n, tokenLink: platform.tokenLink),
                  const SizedBox(height: 8),
                  _wrapIfUnavailable(
                    showUnavailableHint && _llmHasApiKey,
                    child: TextFormField(
                      controller: _llmApiKeyController,
                      obscureText: _llmObscureText,
                      decoration: InputDecoration(
                        labelText: !_llmHasApiKey
                            ? '${l10n.aiPlatformApiKey} (${l10n.optional})'
                            : l10n.aiPlatformApiKey,
                        hintText: !_llmHasApiKey
                            ? l10n.aiPlatformApiKeyOptionalHint
                            : null,
                        border: const OutlineInputBorder(),
                        contentPadding:
                            const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _llmObscureText ? Icons.visibility : Icons.visibility_off,
                          ),
                          onPressed: () {
                            setState(() {
                              _llmObscureText = !_llmObscureText;
                            });
                          },
                        ),
                      ),
                    ),
                  ),
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
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(
                        child: TextFormField(
                          controller: _llmTimeoutController,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformTimeout,
                            hintText: l10n.aiPlatformTimeoutHint,
                            border: const OutlineInputBorder(),
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextFormField(
                          controller: _llmWriteTimeoutController,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformWriteTimeout,
                            hintText: l10n.aiPlatformWriteTimeoutHint,
                            border: const OutlineInputBorder(),
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
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
                        child: TextFormField(
                          controller: _llmMaxTokensController,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformMaxTokens,
                            hintText: l10n.aiPlatformMaxTokensHint,
                            border: const OutlineInputBorder(),
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextFormField(
                          controller: _llmChunkSizeController,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformChunkSize,
                            hintText: l10n.aiPlatformChunkSizeHint,
                            border: const OutlineInputBorder(),
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
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
                        child: TextFormField(
                          controller: _llmConcurrentController,
                          keyboardType: TextInputType.number,
                          decoration: InputDecoration(
                            labelText: l10n.aiPlatformConcurrent,
                            hintText: l10n.aiPlatformConcurrentHint,
                            border: const OutlineInputBorder(),
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: _buildLlmTemperatureField(platform)),
                    ],
                  ),
                  if (platform.thinkingModeSupported) ...<Widget>[
                    const SizedBox(height: 8),
                    _buildLlmThinkingModeField(l10n),
                  ],
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (_llmTestResult != null) ...<Widget>[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: (_llmLastTestSuccess ?? false)
                  ? Colors.green.shade50
                  : Colors.red.shade50,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(
                color: (_llmLastTestSuccess ?? false)
                    ? Colors.green.shade300
                    : Colors.red.shade300,
              ),
            ),
            child: Row(
              children: <Widget>[
                Icon(
                  (_llmLastTestSuccess ?? false)
                      ? Icons.check_circle
                      : Icons.error,
                  color: (_llmLastTestSuccess ?? false)
                      ? Colors.green.shade700
                      : Colors.red.shade700,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: SelectableText(
                    _llmTestResult!,
                    style: TextStyle(
                      color: (_llmLastTestSuccess ?? false)
                          ? Colors.green.shade700
                          : Colors.red.shade700,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        _wrapIfUnavailable(
          showUnavailableHint,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              if (showUnavailableHint) ...<Widget>[
                Expanded(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.orange.shade300),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.warning_amber_rounded,
                            color: Colors.orange.shade700, size: 18,),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            l10n.setupWizardConfigureApiKeyAndTest,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.orange.shade900,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
              ],
              OutlinedButton(
                onPressed: _llmIsTestingConnection
                    ? null
                    : () => _testLlmConnection(notifier),
                child: _llmIsTestingConnection
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(l10n.aiPlatformTestConnection),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLlmTemperatureField(AIPlatformInfo platform) {
    final l10n = AppLocalizations.of(context)!;
    final double tempMin = platform.temperatureMin;
    final double tempMax = platform.temperatureMax;
    final int divisions = ((tempMax - tempMin) * 10).round().clamp(1, 100);

    return SizedBox(
      height: 64,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: l10n.aiPlatformTemperature,
          floatingLabelBehavior: FloatingLabelBehavior.always,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
        ),
        isFocused: _llmTemperatureFocused,
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
                      value: (double.tryParse(_llmTemperatureController.text) ?? 0.3)
                          .clamp(tempMin, tempMax),
                      min: tempMin,
                      max: tempMax,
                      divisions: divisions,
                      onChanged: (double value) {
                        _llmTemperatureController.text = value.toStringAsFixed(1);
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
                controller: _llmTemperatureController,
                focusNode: _llmTemperatureFocusNode,
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
                      numValue >= tempMin &&
                      numValue <= tempMax) {
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

  Widget _buildLlmApiProtocolField(AppLocalizations l10n) => DropdownButtonFormField<String>(
          initialValue: _llmApiProtocol,
          decoration: const InputDecoration(
            labelText: 'API Protocol',
            hintText: 'Select API protocol',
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
                  Icon(Icons.cloud, size: 18, color: Colors.blue),
                  SizedBox(width: 8),
                  Text('OpenAI API'),
                ],
              ),
            ),
            DropdownMenuItem<String>(
              value: 'ollama',
              child: Row(
                children: <Widget>[
                  Icon(Icons.computer, size: 18, color: Colors.orange),
                  SizedBox(width: 8),
                  Text('Ollama API'),
                ],
              ),
            ),
            DropdownMenuItem<String>(
              value: 'anthropic',
              child: Row(
                children: <Widget>[
                  Icon(Icons.psychology, size: 18, color: Colors.purple),
                  SizedBox(width: 8),
                  Text('Anthropic API'),
                ],
              ),
            ),
          ],
          onChanged: (value) {
            if (value != null) {
              setState(() {
                _llmApiProtocol = value;
              });
            }
          },
        );


  Widget _buildLlmThinkingModeField(AppLocalizations l10n) {
    final List<Map<String, String>> options = <Map<String, String>>[
      <String, String>{
        'value': 'disable',
        'label': l10n.aiPlatformThinkingDisable,
      },
      <String, String>{
        'value': 'enable',
        'label': l10n.aiPlatformThinkingEnable,
      },
      <String, String>{
        'value': 'default',
        'label': l10n.aiPlatformThinkingDefault,
      },
    ];

    return DropdownButtonFormField<String>(
      value: _llmThinkingMode,
      decoration: InputDecoration(
        labelText: l10n.aiPlatformThinkingMode,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
      items: options
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
            _llmThinkingMode = value;
          });
        }
      },
    );
  }

  /// "Has API Key" switch - for local deployments like Ollama that don't require API key
  Widget _buildLlmHasApiKeySwitch(AppLocalizations l10n, {String? tokenLink}) {
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
            _llmHasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
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
          if (tokenLink != null && tokenLink.isNotEmpty)
            TextButton(
              onPressed: () => _openLlmApiKeyUrl(tokenLink),
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
            value: _llmHasApiKey,
            onChanged: (value) {
              setState(() {
                _llmHasApiKey = value;
              });
            },
          ),
        ],
      ),
    ),
  );
  }

  /// MinerU Cloud "Requires API Key" switch
  Widget _buildMineruHasApiKeySwitch(AppLocalizations l10n, {String? tokenLink}) {
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
            _mineruHasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
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
          if (tokenLink != null && tokenLink.isNotEmpty)
            TextButton(
              onPressed: () => _openApiKeyUrl(tokenLink),
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
            value: _mineruHasApiKey,
            onChanged: (value) {
              setState(() {
                _mineruHasApiKey = value;
              });
            },
          ),
        ],
      ),
    ),
  );
  }

  /// MinerU Local "Requires API Key" switch
  Widget _buildMineruLocalHasApiKeySwitch(AppLocalizations l10n, {String? tokenLink}) {
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
            _mineruLocalHasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
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
          if (tokenLink != null && tokenLink.isNotEmpty)
            TextButton(
              onPressed: () => _openApiKeyUrl(tokenLink),
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
            value: _mineruLocalHasApiKey,
            onChanged: (value) {
              setState(() {
                _mineruLocalHasApiKey = value;
              });
            },
          ),
        ],
      ),
    ),
  );
  }

  Future<void> _openLlmApiKeyUrl(String url) async {
    try {
      final uri = Uri.parse(url);
      final launched = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
        webOnlyWindowName: '_blank',
      );
      if (!launched) await launchUrl(uri);
    } catch (e) {
      if (kDebugMode) debugPrint('Error opening URL: $e');
    }
  }

  Future<void> _loadLlmModels() async {
    final l10n = AppLocalizations.of(context)!;
    final String baseUrl = _llmUrlController.text.trim();
    final String apiKey = _llmApiKeyController.text.trim();
    final String? platformKey = _selectedPlatformKey;
    final AIPlatformSettings settings = ref.read(aiPlatformSettingsProvider);
    final AIPlatformInfo? platform = platformKey != null ? settings.platforms[platformKey] : null;
    // Check if API key is required based on platform config
    final bool requiresApiKey = platform != null && platform.requiresApiKey;
    if (baseUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.aiPlatformPleaseEnterApiUrlFirst),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
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
      _llmIsLoadingModels = true;
    });

    try {
      if (kDebugMode) {
        print('[SetupWizard] Loading models with:');
        print('  platformKey: $platformKey');
        print('  baseUrl: $baseUrl');
        print('  apiKey: ${apiKey.isEmpty ? "(empty)" : "${apiKey.substring(0, apiKey.length > 10 ? 10 : apiKey.length)}..."}');
      }
      
      final ConfigService configService = ConfigService();
      final Map<String, dynamic> result =
          await configService.listPlatformModels(
        _selectedPlatformKey!,
        baseUrl,
        apiKey,
        apiProtocol: _llmApiProtocol,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        final List<String> models = (result['models'] as List<dynamic>?)
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
          _showLlmModelSelectionDialog(models, l10n);
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              result['error']?.toString() ?? l10n.aiPlatformFailedToLoadModels,
            ),
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
          _llmIsLoadingModels = false;
        });
      }
    }
  }

  void _showLlmModelSelectionDialog(
      List<String> models, AppLocalizations l10n,) {
    showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: Text(l10n.aiPlatformSelectModel),
        content: SizedBox(
          width: 400,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: models.length,
            itemBuilder: (BuildContext context, int index) {
              final String model = models[index];
              final bool isSelected = model == _llmModelController.text.trim();
              return ListTile(
                title: Text(model),
                selected: isSelected,
                onTap: () {
                  _llmModelController.text = model;
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
      ),
    );
  }

  Future<void> _testLlmConnection(AIPlatformSettingsNotifier notifier) async {
    final l10n = AppLocalizations.of(context)!;
    if (_selectedPlatformKey == null) return;
    // Check if API key is required based on current form state
    final bool requiresApiKey = _llmHasApiKey;
    if (requiresApiKey && _llmApiKeyController.text.trim().isEmpty) {
      setState(() {
        _llmTestResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
        _llmLastTestSuccess = false;
      });
      return;
    }

    setState(() {
      _llmIsTestingConnection = true;
      _llmTestResult = null;
      _llmLastTestSuccess = null;
    });

    try {
      final String apiKey = _llmApiKeyController.text.trim();
      final String baseUrl = _llmUrlController.text.trim();
      final String modelName = _llmModelController.text.trim();
      
      if (kDebugMode) {
        print('[SetupWizard] Testing connection with:');
        print('  platform: $_selectedPlatformKey');
        print('  apiKey: ${apiKey.isEmpty ? "(empty)" : "${apiKey.substring(0, apiKey.length > 10 ? 10 : apiKey.length)}..."}');
        print('  baseUrl: $baseUrl');
        print('  modelName: $modelName');
      }
      
      final Map<String, dynamic> result = await notifier.testConnection(
        _selectedPlatformKey!,
        apiKey,
        baseUrlOverride: baseUrl,
        modelNameOverride: modelName,
      );
      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      setState(() {
        _llmLastTestSuccess = success;
        _llmTestResult = success
            ? l10n.aiPlatformConnectionTestSucceeded
            : l10n.aiPlatformConnectionTestFailed(
                result['message']?.toString() ?? '',
              );
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _llmLastTestSuccess = false;
        _llmTestResult = l10n.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _llmIsTestingConnection = false;
        });
      }
    }
  }

  void _saveLlmConfig(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    AIPlatformInfo platform, {
    bool showSnackBar = true,
  }) {
    if (_selectedPlatformKey == null) return;
    final AIPlatformInfo current =
        settings.platforms[_selectedPlatformKey!] ?? platform;
    final AIPlatformInfo updated = current.copyWith(
      name: _llmNameController.text.trim().isEmpty
          ? current.name
          : _llmNameController.text.trim(),
      url: _llmUrlController.text.trim().isEmpty
          ? current.url
          : _llmUrlController.text.trim(),
      model: _llmModelController.text.trim(),
      apiKey: _llmApiKeyController.text,
      maxTokens:
          int.tryParse(_llmMaxTokensController.text) ?? current.maxTokens,
      temperature: double.tryParse(_llmTemperatureController.text) ??
          current.temperature,
      chunkSize: int.tryParse(_llmChunkSizeController.text) ?? current.chunkSize,
      concurrent: int.tryParse(_llmConcurrentController.text) ?? current.concurrent,
      timeout: int.tryParse(_llmTimeoutController.text) ?? current.timeout,
      writeTimeout: int.tryParse(_llmWriteTimeoutController.text) ?? current.writeTimeout,
      thinkingMode: current.thinkingModeSupported
          ? _llmThinkingMode
          : current.thinkingMode,
      apiProtocol: _llmApiProtocol,
      requiresApiKey: _llmHasApiKey,
    );
    notifier.updatePlatformConfig(_selectedPlatformKey!, updated);
    if (showSnackBar && mounted) {
      final String savedMessage = AppLocalizations.of(context)!.aiPlatformSave;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('$savedMessage: ${platform.name}'),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  /// Saves LLM then MinerU config from current form state, then exits wizard.
  void _saveAndExit(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) {
    if (_selectedPlatformKey != null) {
      final AIPlatformInfo? platform =
          settings.platforms[_selectedPlatformKey!];
      if (platform != null) {
        _saveLlmConfig(settings, notifier, platform, showSnackBar: false);
      }
      // Save the selected platform as default
      notifier.setDefaultPlatform(_selectedPlatformKey!);
    }
    if (_needsPdfTranslation) {
      // Save config for the selected MinerU platform (Cloud or Local)
      if (_selectedMineruPlatform == 'mineru') {
        final AIPlatformInfo? mineru = settings.platforms['mineru'];
        _saveMineruConfig(settings, notifier, mineru, showSnackBar: false);
      } else {
        final AIPlatformInfo? mineruLocal = settings.platforms['mineru_local'];
        _saveMineruLocalConfig(settings, notifier, mineruLocal, showSnackBar: false);
      }
      
      // Update the parsing engine setting to match the selected platform
      final globalNotifier = ref.read(globalSettingsProvider.notifier);
      globalNotifier.updateParsingEngineSettings(
        parsingEngine: _selectedMineruPlatform,
      );
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.setupWizardSaveAndExit),
          duration: const Duration(seconds: 2),
        ),
      );
    }
    _goHome();
  }

  Widget _buildStepActions(
    AIPlatformSettings aiSettings,
    AIPlatformSettingsNotifier aiNotifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final bool isLast = _currentStep == 2;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: <Widget>[
        if (_currentStep > 0)
          TextButton(
            onPressed: _prevStep,
            child: Text(l10n.setupWizardPrevStep),
          )
        else
          const SizedBox.shrink(),
        const Spacer(),
        FilledButton(
          onPressed:
              isLast ? () => _saveAndExit(aiSettings, aiNotifier) : _nextStep,
          child: Text(
              isLast ? l10n.setupWizardSaveAndExit : l10n.setupWizardNextStep,),
        ),
      ],
    );
  }
}
