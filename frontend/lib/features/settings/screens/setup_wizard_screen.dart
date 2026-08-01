// Copyright 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

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
import '../../../shared/utils/mineru_test_result_utils.dart';
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

  String? _selectedPlatformKey;

  // Parsing platform selection (MinerU / PaddleOCR)
  String _selectedParsingPlatform = 'mineru';
  bool _parsingPlatformSelectionInitialized = false;

  static bool _isMineruParsingPlatform(String platform) =>
      platform == 'mineru' || platform == 'mineru_local';

  static bool _isPaddleParsingPlatform(String platform) =>
      platform == 'paddle' || platform == 'paddle_local';

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

  // PaddleOCR config state (shared form; synced when switching paddle / paddle_local)
  late TextEditingController _paddleNameController;
  late TextEditingController _paddleApiKeyController;
  late TextEditingController _paddleApiUrlController;
  bool _paddleObscureText = true;
  bool _paddleHasApiKey = true;
  String? _paddleTestResult;
  bool? _paddleLastTestSuccess;
  Map<String, dynamic>? _paddleLastTestRawResult;
  bool _paddleIsTestingConnection = false;
  bool _paddleUseDocOrientationClassify = false;
  bool _paddleRestructurePages = false;
  String? _paddleFormSyncedFor;

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
  late TextEditingController _llmTestConnectTimeoutController;
  late TextEditingController _llmTestRequestTimeoutController;
  bool _llmThinkingModeSupported = false;  // Whether this platform supports thinking mode
  String _llmThinkingMode = 'disable';
  int _llmSegmentLimit = 100;  // Max segments per translation batch (0 = unlimited)
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
  Color _platformStatusColor(AIPlatformInfo? p, {Map<String, dynamic>? testRawResult}) {
    if (testRawResult != null && paddleTestHasCapabilityWarning(testRawResult)) {
      return Colors.orange;
    }
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
    _paddleNameController = TextEditingController();
    _paddleApiKeyController = TextEditingController();
    _paddleApiUrlController = TextEditingController();
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
    _llmTestConnectTimeoutController = TextEditingController(text: '30');
    _llmTestRequestTimeoutController = TextEditingController(text: '10');
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
    _paddleNameController.dispose();
    _paddleApiKeyController.dispose();
    _paddleApiUrlController.dispose();
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
    _llmTestConnectTimeoutController.dispose();
    _llmTestRequestTimeoutController.dispose();
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
    _ensureParsingPlatformSelectionInitialized(globalSettings);
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
        child: Column(
          children: <Widget>[
            Expanded(
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1100),
                  child: Card(
                    elevation: 4,
                    margin: const EdgeInsets.all(16),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
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
                    const SizedBox(height: 12),
                    _buildStepHeader(aiSettings, aiNotifier),
                  ],
                    ),
                  ),
                ),
              ),
            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepHeader(
    AIPlatformSettings aiSettings,
    AIPlatformSettingsNotifier aiNotifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final titles = <String>[
      l10n.setupWizardStepWelcome,
      l10n.aiPlatformCategoryLanguageModels,
      l10n.setupWizardStepMineru,
    ];
    final bool isLast = _currentStep == 2;
    final bool isLLMStep = _currentStep == 1;
    final bool isMineruStep = _currentStep == 2;
    final bool hasTest = isLLMStep || isMineruStep;
    final bool isTesting = isLLMStep
        ? _llmIsTestingConnection
        : isMineruStep
            ? (_isPaddleParsingPlatform(_selectedParsingPlatform)
                ? _paddleIsTestingConnection
                : _selectedParsingPlatform == 'mineru'
                    ? _mineruIsTestingConnection
                    : _mineruLocalIsTestingConnection)
            : false;

    // Determine current step's test result
    String? testResult;
    bool? testSuccess;
    Map<String, dynamic>? testRawResult;
    if (isLLMStep) {
      testResult = _llmTestResult;
      testSuccess = _llmLastTestSuccess;
    } else if (isMineruStep) {
      if (_isPaddleParsingPlatform(_selectedParsingPlatform)) {
        testResult = _paddleTestResult;
        testSuccess = _paddleLastTestSuccess;
        testRawResult = _paddleLastTestRawResult;
      } else if (_selectedParsingPlatform == 'mineru') {
        testResult = _mineruTestResult;
        testSuccess = _mineruLastTestSuccess;
      } else {
        testResult = _mineruLocalTestResult;
        testSuccess = _mineruLocalLastTestSuccess;
      }
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        // Previous button (hidden on first step)
        if (_currentStep > 0)
          TextButton(
            onPressed: _prevStep,
            child: Text(l10n.setupWizardPrevStep),
          )
        else
          const SizedBox(width: 8),
        const SizedBox(width: 12),
        // Title + test result + progress bar
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Flexible(
                    child: Text(
                      titles[_currentStep],
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  if (hasTest && testResult != null) ...[
                    const SizedBox(width: 10),
                    Flexible(
                      child: Builder(
                        builder: (BuildContext ctx) {
                          final PlatformTestVisualState visualState =
                              resolvePlatformTestVisualState(
                            lastTestSuccess: testSuccess,
                            rawResult: testRawResult,
                          );
                          final style = platformTestResultStyle(visualState);
                          return Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: style.backgroundColor,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: style.borderColor),
                            ),
                            child: Text(
                              testResult!,
                              style: TextStyle(
                                color: style.contentColor,
                                fontSize: 11,
                              ),
                              maxLines: visualState == PlatformTestVisualState.warning
                                  ? 3
                                  : 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 4),
              LinearProgressIndicator(
                value: (_currentStep + 1) / 3,
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        // Test Connection button
        if (hasTest)
          OutlinedButton(
            onPressed: isTesting
                ? null
                : () {
                    if (isLLMStep) {
                      _testLlmConnection(aiNotifier);
                    } else if (isMineruStep) {
                      if (_isPaddleParsingPlatform(_selectedParsingPlatform)) {
                        _testPaddleConnection(aiNotifier, _selectedParsingPlatform);
                      } else if (_selectedParsingPlatform == 'mineru') {
                        _testMineruConnection(aiNotifier);
                      } else {
                        _testMineruLocalConnection(aiNotifier);
                      }
                    }
                  },
            child: isTesting
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.aiPlatformTestConnection),
          ),
        if (hasTest) const SizedBox(width: 8),
        // Next / Save & Exit button
        FilledButton(
          onPressed:
              isLast
                  ? () {
                      unawaited(_saveAndExit(aiSettings, aiNotifier));
                    }
                  : _nextStep,
          child: Text(
              isLast ? l10n.setupWizardSaveAndExit : l10n.setupWizardNextStep,),
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
    _llmTestConnectTimeoutController.text = p.testConnectTimeout.toString();
    _llmTestRequestTimeoutController.text = p.testRequestTimeout.toString();
    _llmThinkingModeSupported = p.thinkingModeSupported;
    _llmThinkingMode = p.thinkingMode;
    _llmSegmentLimit = p.segmentLimit;
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

  void _ensureParsingPlatformSelectionInitialized(GlobalSettings globalSettings) {
    if (_parsingPlatformSelectionInitialized) return;
    final String engine = globalSettings.parsingEngine;
    if (engine == 'mineru' ||
        engine == 'mineru_local' ||
        engine == 'paddle' ||
        engine == 'paddle_local') {
      _selectedParsingPlatform = engine;
    }
    _parsingPlatformSelectionInitialized = true;
  }

  void _syncPaddleFormFromPlatform(
    AIPlatformSettings settings,
    String platformKey,
  ) {
    final AIPlatformInfo? paddle = settings.platforms[platformKey];
    if (paddle != null) {
      _paddleNameController.text = paddle.name;
      _paddleApiUrlController.text = paddle.url;
      _paddleApiKeyController.text = paddle.apiKey ?? '';
      _paddleHasApiKey = paddle.requiresApiKey;
      _paddleUseDocOrientationClassify = paddle.useDocOrientationClassify;
      _paddleRestructurePages = paddle.restructurePages;
    }
    _paddleFormSyncedFor = platformKey;
  }

  void _ensurePaddleFormSynced(AIPlatformSettings settings) {
    if (!_isPaddleParsingPlatform(_selectedParsingPlatform)) return;
    if (_paddleFormSyncedFor == _selectedParsingPlatform) return;
    _syncPaddleFormFromPlatform(settings, _selectedParsingPlatform);
  }

  String _parsingPlatformDisplayName(AppLocalizations l10n, String code) {
    switch (code) {
      case 'mineru':
        return l10n.settingsParsingEngineMineru;
      case 'mineru_local':
        return l10n.settingsParsingEngineMineruLocal;
      case 'paddle':
        return l10n.settingsParsingEnginePaddle;
      case 'paddle_local':
        return l10n.settingsParsingEnginePaddleLocal;
      default:
        return code;
    }
  }

  String _parsingPlatformDescription(AppLocalizations l10n, String code) {
    switch (code) {
      case 'paddle':
        return l10n.settingsParsingEnginePaddleDesc;
      case 'paddle_local':
        return l10n.settingsParsingEnginePaddleLocalDesc;
      default:
        return l10n.setupWizardMineruDescription;
    }
  }

  Widget _buildPaddleOptionSwitches(AppLocalizations l10n) => Column(
        children: <Widget>[
          SwitchListTile.adaptive(
            dense: true,
            title: Text(
              l10n.settingsPaddleUseDocOrientationClassify,
              style: const TextStyle(fontSize: 13),
            ),
            subtitle: Text(
              l10n.settingsPaddleUseDocOrientationClassifySubtitle,
              style: const TextStyle(fontSize: 11),
            ),
            value: _paddleUseDocOrientationClassify,
            onChanged: (bool value) {
              setState(() {
                _paddleUseDocOrientationClassify = value;
              });
            },
          ),
          SwitchListTile.adaptive(
            dense: true,
            title: Text(
              l10n.settingsPaddleRestructurePages,
              style: const TextStyle(fontSize: 13),
            ),
            subtitle: Text(
              l10n.settingsPaddleRestructurePagesSubtitle,
              style: const TextStyle(fontSize: 11),
            ),
            value: _paddleRestructurePages,
            onChanged: (bool value) {
              setState(() {
                _paddleRestructurePages = value;
              });
            },
          ),
        ],
      );

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
  ) {
    _ensurePaddleFormSynced(settings);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          l10n.settingsParsingEngineLabel,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 6),
        DropdownButtonFormField<String>(
          initialValue: _selectedParsingPlatform,
          decoration: InputDecoration(
            labelText: l10n.settingsParsingEngineLabel,
            border: const OutlineInputBorder(),
            labelStyle: const TextStyle(fontSize: 12),
            hintStyle: const TextStyle(fontSize: 11),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          ),
          items: <String>['mineru', 'mineru_local', 'paddle', 'paddle_local']
              .map(
                (String code) => DropdownMenuItem<String>(
                  value: code,
                  child: Text(_parsingPlatformDisplayName(l10n, code)),
                ),
              )
              .toList(),
          onChanged: (String? value) {
            if (value == null) return;
            setState(() {
              _selectedParsingPlatform = value;
              if (_isPaddleParsingPlatform(value)) {
                _syncPaddleFormFromPlatform(settings, value);
              }
            });
          },
        ),
        const SizedBox(height: 16),
        if (_selectedParsingPlatform == 'mineru')
          _buildEmbeddedMineruCloudForm(settings, notifier)
        else if (_selectedParsingPlatform == 'mineru_local')
          _buildEmbeddedMineruLocalForm(settings, notifier)
        else
          _buildEmbeddedPaddleForm(settings, notifier, _selectedParsingPlatform),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.shade200),
            ),
            child: Text(
              _parsingPlatformDescription(l10n, _selectedParsingPlatform),
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ),
      ],
    );
  }

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
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
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
        const SizedBox(height: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
        const SizedBox(height: 6),
        _wrapIfUnavailable(
          showUnavailableHint && _mineruHasApiKey,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    TextFormField(
                      controller: _mineruApiUrlController,
                      decoration: InputDecoration(
                        labelText: l10n.aiPlatformApiUrl,
                        hintText: l10n.aiPlatformMineruApiUrlHint,
                        prefixIcon: const Icon(Icons.link),
                        border: const OutlineInputBorder(),
                        labelStyle: const TextStyle(fontSize: 12),
                        hintStyle: const TextStyle(fontSize: 11),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                    ),
                    const SizedBox(height: 6),
                    _buildMineruHasApiKeySwitch(l10n, tokenLink: mineruTokenLink),
                    const SizedBox(height: 6),
                    TextFormField(
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
                        labelStyle: const TextStyle(fontSize: 12),
                        hintStyle: const TextStyle(fontSize: 11),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  children: <Widget>[
                    SwitchListTile.adaptive(
                      dense: true,
                      title: Text(l10n.aiPlatformFormulaOcr, style: const TextStyle(fontSize: 13)),
                      subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle, style: const TextStyle(fontSize: 11)),
                      value: _mineruFormulaOcr,
                      onChanged: (bool value) {
                        setState(() {
                          _mineruFormulaOcr = value;
                        });
                      },
                    ),
                    SwitchListTile.adaptive(
                      dense: true,
                      title: Text(l10n.aiPlatformTableOcr, style: const TextStyle(fontSize: 13)),
                      subtitle: Text(l10n.aiPlatformTableOcrSubtitle, style: const TextStyle(fontSize: 11)),
                      value: _mineruTableOcr,
                      onChanged: (bool value) {
                        setState(() {
                          _mineruTableOcr = value;
                        });
                      },
                    ),
                  ],
                ),
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
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
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
        const SizedBox(height: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
        const SizedBox(height: 6),
        _wrapIfUnavailable(
          showUnavailableHint && _mineruLocalHasApiKey,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    TextFormField(
                      controller: _mineruLocalApiUrlController,
                      decoration: InputDecoration(
                        labelText: l10n.aiPlatformApiUrl,
                        hintText: 'http://localhost:8920',
                        prefixIcon: const Icon(Icons.link),
                        border: const OutlineInputBorder(),
                        labelStyle: const TextStyle(fontSize: 12),
                        hintStyle: const TextStyle(fontSize: 11),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                    ),
                    const SizedBox(height: 6),
                    _buildMineruLocalHasApiKeySwitch(l10n),
                    const SizedBox(height: 6),
                    TextFormField(
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
                        labelStyle: const TextStyle(fontSize: 12),
                        hintStyle: const TextStyle(fontSize: 11),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  children: <Widget>[
                    DropdownButtonFormField<String>(
                      initialValue: _mineruLocalParserSubtypeController.text.isNotEmpty
                          ? _mineruLocalParserSubtypeController.text
                          : 'local',
                      decoration: InputDecoration(
                        labelText: l10n.aiPlatformParserSubtype,
                        prefixIcon: const Icon(Icons.category_outlined),
                        border: const OutlineInputBorder(),
                        labelStyle: const TextStyle(fontSize: 12),
                        hintStyle: const TextStyle(fontSize: 11),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                    SwitchListTile.adaptive(
                      dense: true,
                      title: Text(l10n.aiPlatformFormulaOcr, style: const TextStyle(fontSize: 13)),
                      subtitle: Text(l10n.aiPlatformFormulaOcrSubtitle, style: const TextStyle(fontSize: 11)),
                      value: _mineruLocalFormulaOcr,
                      onChanged: (bool value) {
                        setState(() {
                          _mineruLocalFormulaOcr = value;
                        });
                      },
                    ),
                    SwitchListTile.adaptive(
                      dense: true,
                      title: Text(l10n.aiPlatformTableOcr, style: const TextStyle(fontSize: 13)),
                      subtitle: Text(l10n.aiPlatformTableOcrSubtitle, style: const TextStyle(fontSize: 11)),
                      value: _mineruLocalTableOcr,
                      onChanged: (bool value) {
                        setState(() {
                          _mineruLocalTableOcr = value;
                        });
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEmbeddedPaddleForm(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    String platformKey,
  ) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final AIPlatformInfo? paddle = settings.platforms[platformKey];
    final Color statusColor = _platformStatusColor(
      paddle,
      testRawResult: _paddleLastTestRawResult,
    );
    final String statusText = paddleTestHasCapabilityWarning(_paddleLastTestRawResult)
        ? (_paddleTestResult ?? _platformStatusText(paddle, l10n))
        : _platformStatusText(paddle, l10n);
    final bool showUnavailableHint =
        _platformConnectionUnavailable(paddle) &&
            !platformTestMeetsRequirements(_paddleLastTestRawResult) &&
            (_paddleLastTestSuccess != true);
    final String? tokenLink = paddle?.tokenLink;
    final String defaultName = platformKey == 'paddle'
        ? l10n.settingsParsingEnginePaddle
        : l10n.settingsParsingEnginePaddleLocal;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text(
              defaultName,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
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
        const SizedBox(height: 6),
        TextFormField(
          controller: _paddleNameController,
          decoration: InputDecoration(
            labelText: l10n.aiPlatformDisplayName,
            hintText: defaultName,
            prefixIcon: const Icon(Icons.label_outline),
            border: const OutlineInputBorder(),
            labelStyle: const TextStyle(fontSize: 12),
            hintStyle: const TextStyle(fontSize: 11),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          ),
        ),
        const SizedBox(height: 6),
        _wrapIfUnavailable(
          showUnavailableHint && _paddleHasApiKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              TextFormField(
                controller: _paddleApiUrlController,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformApiUrl,
                  prefixIcon: const Icon(Icons.link),
                  border: const OutlineInputBorder(),
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
              const SizedBox(height: 6),
              _buildPaddleHasApiKeySwitch(l10n, tokenLink: tokenLink),
              const SizedBox(height: 6),
              TextFormField(
                controller: _paddleApiKeyController,
                obscureText: _paddleObscureText,
                decoration: InputDecoration(
                  labelText: _paddleHasApiKey
                      ? l10n.aiPlatformApiKey
                      : '${l10n.aiPlatformApiKey} (${l10n.optional})',
                  hintText: _paddleHasApiKey
                      ? null
                      : l10n.aiPlatformApiKeyOptionalHint,
                  prefixIcon: const Icon(Icons.vpn_key),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _paddleObscureText
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(() {
                        _paddleObscureText = !_paddleObscureText;
                      });
                    },
                  ),
                  border: const OutlineInputBorder(),
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 6),
        _buildPaddleOptionSwitches(l10n),
        if (_paddleTestResult != null) ...<Widget>[
          const SizedBox(height: 8),
          buildPlatformTestResultBanner(
            message: _paddleTestResult!,
            lastTestSuccess: _paddleLastTestSuccess,
            rawResult: _paddleLastTestRawResult,
          ),
        ],
      ],
    );
  }

  Widget _buildPaddleHasApiKeySwitch(
    AppLocalizations l10n, {
    String? tokenLink,
  }) {
    return SizedBox(
      height: 36,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          children: <Widget>[
            Icon(
              _paddleHasApiKey ? Icons.vpn_key : Icons.vpn_key_off_outlined,
              size: 18,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                l10n.aiPlatformHasApiKey,
                style:
                    const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (tokenLink != null && tokenLink.isNotEmpty)
              TextButton(
                onPressed: () => _openApiKeyUrl(tokenLink),
                style: TextButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  minimumSize: const Size(0, 24),
                ),
                child: Text(
                  l10n.aiPlatformGetApiKey,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.blue.shade700,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
            Switch(
              value: _paddleHasApiKey,
              onChanged: (bool value) {
                setState(() {
                  _paddleHasApiKey = value;
                });
              },
            ),
          ],
        ),
      ),
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
            ? buildPlatformTestSuccessMessage(l10n, 'mineru', result)
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
            ? buildPlatformTestSuccessMessage(l10n, 'mineru_local', result)
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

  Future<void> _testPaddleConnection(
    AIPlatformSettingsNotifier notifier,
    String platformKey,
  ) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    if (_paddleApiUrlController.text.trim().isEmpty) {
      setState(() {
        _paddleTestResult = l10n.aiPlatformPleaseEnterApiUrlFirst;
        _paddleLastTestSuccess = false;
      });
      return;
    }
    if (_paddleHasApiKey && _paddleApiKeyController.text.trim().isEmpty) {
      setState(() {
        _paddleTestResult = l10n.aiPlatformPleaseEnterApiKeyFirst;
        _paddleLastTestSuccess = false;
      });
      return;
    }

    setState(() {
      _paddleIsTestingConnection = true;
      _paddleTestResult = null;
      _paddleLastTestSuccess = null;
      _paddleLastTestRawResult = null;
    });

    try {
      final Map<String, dynamic> result = await notifier.testConnection(
        platformKey,
        _paddleApiKeyController.text.trim(),
        baseUrlOverride: _paddleApiUrlController.text.trim(),
      );
      final bool success = result['success'] == true ||
          result['success'] == 'true' ||
          result['success'] == 1;
      if (!mounted) return;
      setState(() {
        _paddleLastTestSuccess = success;
        _paddleLastTestRawResult = result;
        _paddleTestResult = success
            ? buildPlatformTestSuccessMessage(l10n, platformKey, result)
            : buildPlatformTestFailureMessage(l10n, platformKey, result);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _paddleLastTestSuccess = false;
        _paddleTestResult = l10n.aiPlatformConnectionTestFailed(e.toString());
      });
    } finally {
      if (mounted) {
        setState(() {
          _paddleIsTestingConnection = false;
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
        platformType: 'parser',
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
        platformType: 'parser',
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

  void _savePaddleConfig(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    String platformKey, {
    bool showSnackBar = true,
  }) {
    final AIPlatformInfo? current = settings.platforms[platformKey];
    final String defaultName = platformKey == 'paddle'
        ? AppLocalizations.of(context)!.settingsParsingEnginePaddle
        : AppLocalizations.of(context)!.settingsParsingEnginePaddleLocal;
    final AIPlatformInfo updated;
    if (current == null) {
      updated = AIPlatformInfo(
        key: platformKey,
        name: _paddleNameController.text.trim().isNotEmpty
            ? _paddleNameController.text.trim()
            : defaultName,
        url: _paddleApiUrlController.text.trim(),
        model: 'paddleocr-vl',
        apiKey: _paddleApiKeyController.text.trim(),
        parserSubtype: platformKey == 'paddle' ? 'cloud' : 'local',
        maxTokens: 0,
        temperature: 0,
        temperatureMin: 0,
        temperatureMax: 0,
        thinkingModeSupported: false,
        thinkingMode: 'disable',
        platformType: 'parser',
        parserEngine: 'paddle',
        requiresApiKey: _paddleHasApiKey,
        useDocOrientationClassify: _paddleUseDocOrientationClassify,
        restructurePages: _paddleRestructurePages,
      );
    } else {
      updated = current.copyWith(
        name: _paddleNameController.text.trim().isNotEmpty
            ? _paddleNameController.text.trim()
            : current.name,
        apiKey: _paddleApiKeyController.text.trim(),
        url: _paddleApiUrlController.text.trim(),
        requiresApiKey: _paddleHasApiKey,
        useDocOrientationClassify: _paddleUseDocOrientationClassify,
        restructurePages: _paddleRestructurePages,
      );
    }
    notifier.updatePlatformConfig(platformKey, updated);
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
            fontSize: 13,
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
          if (_selectedPlatformKey != null) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      DropdownButtonFormField<String>(
                        initialValue: _selectedPlatformKey,
                        decoration: InputDecoration(
                          labelText: l10n.setupWizardSelectLlmPlatform,
                          border: const OutlineInputBorder(),
                          labelStyle: const TextStyle(fontSize: 12),
                          hintStyle: const TextStyle(fontSize: 11),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _llmNameController,
                        decoration: InputDecoration(
                          labelText: l10n.aiPlatformPlatformName,
                          hintText: l10n.aiPlatformPlatformNameHint,
                          border: const OutlineInputBorder(),
                          labelStyle: const TextStyle(fontSize: 12),
                          hintStyle: const TextStyle(fontSize: 11),
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _llmUrlController,
                        decoration: InputDecoration(
                          labelText: l10n.aiPlatformApiUrl,
                          hintText: l10n.aiPlatformApiUrlHint,
                          border: const OutlineInputBorder(),
                          labelStyle: const TextStyle(fontSize: 12),
                          hintStyle: const TextStyle(fontSize: 11),
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: <Widget>[
                          Expanded(
                            child: TextFormField(
                              controller: _llmModelController,
                              decoration: InputDecoration(
                                labelText: l10n.aiPlatformModel,
                                hintText: l10n.aiPlatformModelHint,
                                border: const OutlineInputBorder(),
                                labelStyle: const TextStyle(fontSize: 12),
                                hintStyle: const TextStyle(fontSize: 11),
                                contentPadding:
                                    const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                                  const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              minimumSize: const Size(0, 48),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      _buildLlmApiProtocolField(l10n),
                      const SizedBox(height: 6),
                      _buildLlmHasApiKeySwitch(l10n, tokenLink: settings.platforms[_selectedPlatformKey]!.tokenLink),
                      const SizedBox(height: 6),
                      TextFormField(
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
                          labelStyle: const TextStyle(fontSize: 12),
                          hintStyle: const TextStyle(fontSize: 11),
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildLlmParametersFields(l10n, settings.platforms[_selectedPlatformKey]!),
                ),
              ],
            ),
          ] else ...[
            Row(
              children: <Widget>[
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: null,
                    decoration: InputDecoration(
                      labelText: l10n.setupWizardSelectLlmPlatform,
                      border: const OutlineInputBorder(),
                      labelStyle: const TextStyle(fontSize: 12),
                      hintStyle: const TextStyle(fontSize: 11),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                        _llmFormPlatformKey = null;
                      });
                    },
                  ),
                ),
              ],
            ),
          ],
        ],
      ],
    );
  }

  Widget _buildLlmParametersFields(AppLocalizations l10n, AIPlatformInfo platform) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: TextFormField(
                controller: _llmTestConnectTimeoutController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformTestConnectTimeout,
                  hintText: l10n.aiPlatformTestConnectTimeoutHint,
                  border: const OutlineInputBorder(),
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextFormField(
                controller: _llmTestRequestTimeoutController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: l10n.aiPlatformTestRequestTimeout,
                  hintText: l10n.aiPlatformTestRequestTimeoutHint,
                  border: const OutlineInputBorder(),
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
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
                  labelStyle: const TextStyle(fontSize: 12),
                  hintStyle: const TextStyle(fontSize: 11),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(child: _buildLlmTemperatureField(platform)),
          ],
        ),
        const SizedBox(height: 2),
        _buildLlmThinkingModeSupportedField(l10n),
        if (_llmThinkingModeSupported) ...<Widget>[
          const SizedBox(height: 6),
          _buildLlmThinkingModeField(l10n),
        ],
        const SizedBox(height: 6),
        _buildLlmSegmentLimitField(l10n),
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
          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
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
                EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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

  Widget _buildLlmThinkingModeSupportedField(AppLocalizations l10n) {
    return SizedBox(
      height: 60,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
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
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    l10n.aiPlatformThinkingModeSupported,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    l10n.aiPlatformThinkingModeSupportedHint,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Switch(
              value: _llmThinkingModeSupported,
              onChanged: (bool value) {
                setState(() {
                  _llmThinkingModeSupported = value;
                });
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLlmSegmentLimitField(AppLocalizations l10n) {
    const List<int> segmentLimitOptions = <int>[1, 3, 5, 10, 20, 50, 100, 200, 500, 1000, 0];
    String _labelForValue(int v) => v == 0 ? l10n.aiPlatformSegmentLimitUnlimited : v.toString();

    return DropdownButtonFormField<int>(
      value: segmentLimitOptions.contains(_llmSegmentLimit) ? _llmSegmentLimit : 100,
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
            _llmSegmentLimit = value;
          });
        }
      },
    );
  }

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
        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
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
                    fontSize: 13,
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
      height: 36,
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
            size: 18,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              l10n.aiPlatformHasApiKey,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (tokenLink != null && tokenLink.isNotEmpty)
            TextButton(
              onPressed: () => _openApiKeyUrl(tokenLink),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                minimumSize: const Size(0, 24),
              ),
              child: Text(
                l10n.aiPlatformGetApiKey,
                style: TextStyle(
                  fontSize: 12,
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
      height: 36,
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
            size: 18,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              l10n.aiPlatformHasApiKey,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (tokenLink != null && tokenLink.isNotEmpty)
            TextButton(
              onPressed: () => _openApiKeyUrl(tokenLink),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                minimumSize: const Size(0, 24),
              ),
              child: Text(
                l10n.aiPlatformGetApiKey,
                style: TextStyle(
                  fontSize: 12,
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
      // Persist on success so Quick Settings / translation use the same Key+model.
      if (success) {
        final AIPlatformSettings settings =
            ref.read(aiPlatformSettingsProvider);
        final AIPlatformInfo? platform =
            settings.platforms[_selectedPlatformKey!];
        if (platform != null) {
          await _saveLlmConfig(
            settings,
            notifier,
            platform,
            showSnackBar: false,
          );
          await notifier.setDefaultPlatform(_selectedPlatformKey!);
        }
      }
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

  Future<void> _saveLlmConfig(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
    AIPlatformInfo platform, {
    bool showSnackBar = true,
  }) async {
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
      testConnectTimeout: int.tryParse(_llmTestConnectTimeoutController.text) ?? current.testConnectTimeout,
      testRequestTimeout: int.tryParse(_llmTestRequestTimeoutController.text) ?? current.testRequestTimeout,
      thinkingModeSupported: _llmThinkingModeSupported,
      thinkingMode: _llmThinkingModeSupported ? _llmThinkingMode : current.thinkingMode,
      segmentLimit: _llmSegmentLimit,
      apiProtocol: _llmApiProtocol,
      requiresApiKey: _llmHasApiKey,
    );
    await notifier.updatePlatformConfig(_selectedPlatformKey!, updated);
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
  Future<void> _saveAndExit(
    AIPlatformSettings settings,
    AIPlatformSettingsNotifier notifier,
  ) async {
    if (_selectedPlatformKey != null) {
      // Ensure LLM form reflects the actual platform config before saving.
      // The form is normally synced via addPostFrameCallback when the LLM step
      // is first rendered; this guard handles edge cases where the sync hasn't
      // fired yet (e.g. rapid navigation) to prevent hardcoded controller
      // defaults from overwriting the platform's real configuration.
      if (_llmFormPlatformKey != _selectedPlatformKey) {
        _syncLlmFormFromPlatform(_selectedPlatformKey!, settings);
      }
      final AIPlatformInfo? platform =
          settings.platforms[_selectedPlatformKey!];
      if (platform != null) {
        await _saveLlmConfig(
          settings,
          notifier,
          platform,
          showSnackBar: false,
        );
      }
      // Save the selected platform as default
      await notifier.setDefaultPlatform(_selectedPlatformKey!);
    }
    // Save config for the selected parsing platform
    if (_isPaddleParsingPlatform(_selectedParsingPlatform)) {
      _savePaddleConfig(
        settings,
        notifier,
        _selectedParsingPlatform,
        showSnackBar: false,
      );
    } else if (_selectedParsingPlatform == 'mineru') {
      final AIPlatformInfo? mineru = settings.platforms['mineru'];
      _saveMineruConfig(settings, notifier, mineru, showSnackBar: false);
    } else {
      final AIPlatformInfo? mineruLocal = settings.platforms['mineru_local'];
      _saveMineruLocalConfig(settings, notifier, mineruLocal, showSnackBar: false);
    }

    // Update the parsing engine setting to match the selected platform
    final GlobalSettingsNotifier globalNotifier =
        ref.read(globalSettingsProvider.notifier);
    globalNotifier.updateParsingEngineSettings(
      parsingEngine: _selectedParsingPlatform,
    );
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

}
