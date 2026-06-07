import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/app_config.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/services/translation_stats_service.dart';
import '../../../shared/utils/language_mapper.dart';
import '../../home/widgets/translation_stats_widget.dart';
import 'ai_platform_settings.dart';
import 'parsing_engine_settings.dart';
import 'glossary_settings.dart';
import 'anonymization_settings.dart';
import 'user_management_settings.dart';
// prompts_settings removed: prompt is now controlled per task in Quick Settings

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key, this.initialTabIndex});

  /// Initial tab index to show (0=General, 1=AI Platforms, 2=Parsing Engine, etc.)
  final int? initialTabIndex;

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen>
    with TickerProviderStateMixin {
  final List<Map<String, String>> _languages = <Map<String, String>>[
    <String, String>{'code': 'en', 'name': 'English'},
    <String, String>{'code': 'zh', 'name': '中文'},
    <String, String>{'code': 'ja', 'name': '日本語'},
    <String, String>{'code': 'ko', 'name': '한국어'},
  ];

  late TabController _tabController;

  int get _tabCount =>
      5 +
      (AppConfig.kEnableFeaturesInDevelopment ? 1 : 0) +
      (kIsWeb ? 1 : 0);

  @override
  void initState() {
    super.initState();
    // Initialize TabController with initial index if specified
    final maxIndex = _tabCount - 1;
    final initialIndex = widget.initialTabIndex != null &&
            widget.initialTabIndex! >= 0 &&
            widget.initialTabIndex! <= maxIndex
        ? widget.initialTabIndex!
        : 0;
    _tabController = TabController(
        length: _tabCount, vsync: this, initialIndex: initialIndex,);

    // Also ensure tab is switched after first frame (in case initialIndex doesn't work)
    if (widget.initialTabIndex != null &&
        widget.initialTabIndex! >= 0 &&
        widget.initialTabIndex! <= maxIndex) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _tabController.index != widget.initialTabIndex!) {
          _tabController.animateTo(widget.initialTabIndex!);
        }
      });
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
        children: <Widget>[
          // Tab Bar
          ColoredBox(
            color: Theme.of(context).brightness == Brightness.dark
                ? Theme.of(context).colorScheme.surface
                : Colors.grey.shade100,
            child: TabBar(
              controller: _tabController,
              labelColor: Theme.of(context).brightness == Brightness.dark
                  ? Theme.of(context).colorScheme.primary
                  : Colors.blue.shade700,
              unselectedLabelColor:
                  Theme.of(context).brightness == Brightness.dark
                      ? Theme.of(context).colorScheme.onSurfaceVariant
                      : Colors.grey.shade600,
              indicatorColor: Theme.of(context).brightness == Brightness.dark
                  ? Theme.of(context).colorScheme.primary
                  : Colors.blue.shade700,
              isScrollable: true,
              tabs: <Widget>[
                Tab(text: AppLocalizations.of(context)!.settingsTabsGeneral),
                Tab(text: AppLocalizations.of(context)!.settingsTabsAiPlatforms),
                Tab(text: AppLocalizations.of(context)!.settingsTabsParsingEngine),
                Tab(text: AppLocalizations.of(context)!.settingsTabsGlossary),
                Tab(text: AppLocalizations.of(context)!.settingsTabsTranslation),
                if (AppConfig.kEnableFeaturesInDevelopment)
                  Tab(
                    text:
                        AppLocalizations.of(context)!.settingsTabsAnonymization,
                  ),
                if (kIsWeb)
                  Tab(
                    text: AppLocalizations.of(context)!.settingsTabsUserManagement,
                  ),
              ],
            ),
          ),
          // Tab Content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: <Widget>[
                _buildGeneralSettings(),
                const AIPlatformSettingsScreen(),
                const ParsingEngineSettingsScreen(),
                const GlossarySettingsScreen(),
                _buildTranslationSettings(),
                if (AppConfig.kEnableFeaturesInDevelopment)
                  const AnonymizationSettingsScreen(),
                if (kIsWeb) const UserManagementSettingsScreen(),
              ],
            ),
          ),
        ],
      );

  Widget _buildGeneralSettings() {
    final globalSettings = ref.watch(globalSettingsProvider);
    final globalNotifier = ref.read(globalSettingsProvider.notifier);
    final colorScheme = Theme.of(context).colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: <Widget>[
          Container(
            padding: const EdgeInsets.all(20),
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
                      Icons.settings,
                      color: colorScheme.primary,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      AppLocalizations.of(context)!.settingsGeneralTitle,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.primary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  title: Text(
                    AppLocalizations.of(context)!.settingsGeneralDarkModeTitle,
                  ),
                  subtitle: Text(
                    AppLocalizations.of(context)!
                        .settingsGeneralDarkModeSubtitle,
                  ),
                  value: globalSettings.darkMode,
                  onChanged: (bool value) {
                    globalNotifier.updateGeneralSettings(darkMode: value);
                  },
                  secondary: const Icon(Icons.dark_mode),
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.language),
                  title: Text(
                    AppLocalizations.of(context)!.settingsGeneralLanguageTitle,
                  ),
                  subtitle: Text(
                    _languages.firstWhere(
                      (lang) => lang['code'] == globalSettings.language,
                    )['name']!,
                  ),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () =>
                      _showLanguageDialog(globalSettings, globalNotifier),
                ),
                const Divider(),
                SwitchListTile(
                  title: Text(
                    AppLocalizations.of(context)!
                        .settingsGeneralNotificationsTitle,
                  ),
                  subtitle: Text(
                    AppLocalizations.of(context)!
                        .settingsGeneralNotificationsSubtitle,
                  ),
                  value: globalSettings.notifications,
                  onChanged: (bool value) {
                    globalNotifier.updateGeneralSettings(notifications: value);
                  },
                  secondary: const Icon(Icons.notifications),
                ),
                const Divider(),
                SwitchListTile(
                  title: Text(
                    AppLocalizations.of(context)!.settingsGeneralAutoSaveTitle,
                  ),
                  subtitle: Text(
                    AppLocalizations.of(context)!
                        .settingsGeneralAutoSaveSubtitle,
                  ),
                  value: globalSettings.autoSave,
                  onChanged: (bool value) {
                    globalNotifier.updateGeneralSettings(autoSave: value);
                  },
                  secondary: const Icon(Icons.save),
                ),
                const Divider(),
                _buildShowAdsTile(),
                const Divider(),
                // Font Settings
                _buildFontSizeSection(globalSettings, globalNotifier),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Statistics management
          _buildStatsManagementSection(),
          const SizedBox(height: 16),
          // Server Configuration (Web only)
          if (kIsWeb) _buildServerConfigSection(),
        ],
      ),
    );
  }

  Widget _buildStatsManagementSection() {
    final colorScheme = Theme.of(context).colorScheme;
    final l10n = AppLocalizations.of(context)!;

    return Container(
      padding: const EdgeInsets.all(20),
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
                Icons.analytics_outlined,
                color: colorScheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                l10n.translationStatsTitle,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            icon: const Icon(Icons.delete_sweep, size: 18),
            label: Text(l10n.settingsGeneralClearStatsButton),
            onPressed: () => _confirmClearStats(),
            style: OutlinedButton.styleFrom(
              foregroundColor: colorScheme.error,
              side: BorderSide(color: colorScheme.error.withOpacity(0.5)),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmClearStats() async {
    final l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.settingsGeneralClearStatsConfirmTitle),
        content: Text(l10n.settingsGeneralClearStatsConfirmMessage),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.commonCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: Text(l10n.settingsGeneralClearStatsConfirmButton),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      final service = TranslationStatsService();
      await service.resetStats();
      service.clearCache();
      // Invalidate the provider so the home page stats widget refreshes
      ref.invalidate(translationStatsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(l10n.settingsGeneralClearStatsSuccess),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
  }

  Widget _buildServerConfigSection() {
    final colorScheme = Theme.of(context).colorScheme;
    final l10n = AppLocalizations.of(context)!;
    final currentUrl = AppConfig.baseUrl;
    final customUrl = AppConfig.customServerUrl;
    
    return Container(
      padding: const EdgeInsets.all(20),
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
                Icons.dns,
                color: colorScheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                '服务器设置',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ListTile(
            leading: const Icon(Icons.link),
            title: const Text('服务器地址'),
            subtitle: Text(
              customUrl != null && customUrl.isNotEmpty
                  ? '$customUrl (自定义)'
                  : '$currentUrl (默认)',
              style: TextStyle(
                color: customUrl != null && customUrl.isNotEmpty
                    ? colorScheme.primary
                    : colorScheme.onSurfaceVariant,
              ),
            ),
            trailing: const Icon(Icons.edit),
            onTap: _showServerUrlDialog,
          ),
          if (customUrl != null && customUrl.isNotEmpty)
            ListTile(
              leading: const Icon(Icons.restore),
              title: const Text('恢复默认设置'),
              subtitle: const Text('使用自动检测的服务器地址'),
              trailing: const Icon(Icons.arrow_forward_ios),
              onTap: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('确认恢复'),
                    content: const Text('确定要恢复默认服务器地址吗？'),
                    actions: <Widget>[
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('取消'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('恢复'),
                      ),
                    ],
                  ),
                );
                if (confirmed ?? false) {
                  await AppConfig.resetToDefaultServerUrl();
                  if (mounted) {
                    setState(() {});
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('已恢复默认服务器地址，刷新页面后生效'),
                        duration: Duration(seconds: 3),
                      ),
                    );
                  }
                }
              },
            ),
        ],
      ),
    );
  }

  Future<void> _showServerUrlDialog() async {
    final controller = TextEditingController(
      text: AppConfig.customServerUrl ?? '',
    );
    final formKey = GlobalKey<FormState>();
    
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('设置服务器地址'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              TextFormField(
                controller: controller,
                decoration: InputDecoration(
                  labelText: '服务器地址',
                  hintText: AppConfig.defaultBaseUrl,
                  helperText: '例如: http://192.168.1.100:8800 或 https://api.example.com',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: controller.clear,
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return null; // Empty means use default
                  }
                  try {
                    final uri = Uri.parse(value);
                    if (!uri.isScheme('http') && !uri.isScheme('https')) {
                      return '必须以 http:// 或 https:// 开头';
                    }
                    if (uri.host.isEmpty) {
                      return '请输入有效的主机名';
                    }
                    return null;
                  } catch (e) {
                    return '请输入有效的 URL';
                  }
                },
              ),
              const SizedBox(height: 8),
              Text(
                '提示: 留空将使用默认地址 (${AppConfig.defaultBaseUrl})',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              if (formKey.currentState!.validate()) {
                Navigator.pop(context, controller.text.trim());
              }
            },
            child: const Text('保存'),
          ),
        ],
      ),
    );
    
    if (result != null) {
      final success = await AppConfig.setCustomServerUrl(
        result.isEmpty ? null : result,
      );
      if (mounted) {
        if (success) {
          setState(() {});
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                result.isEmpty
                    ? '已恢复默认服务器地址，刷新页面后生效'
                    : '服务器地址已更新为 $result，刷新页面后生效',
              ),
              duration: const Duration(seconds: 3),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('保存失败，请重试'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }
    controller.dispose();
  }

  Widget _buildShowAdsTile() {
    final showAdsAsync = ref.watch(showAdsProvider);
    final showAds = showAdsAsync.value ?? false;
    return SwitchListTile(
      title: Text(
        AppLocalizations.of(context)!.settingsGeneralShowAdsTitle,
      ),
      subtitle: Text(
        AppLocalizations.of(context)!.settingsGeneralShowAdsSubtitle,
      ),
      value: showAds,
      onChanged: showAdsAsync.isLoading
          ? null
          : (bool value) async {
              final ok = await ConfigService().patchSystemShowAds(value);
              if (ok && mounted) ref.invalidate(showAdsProvider);
            },
      secondary: const Icon(Icons.campaign_outlined),
    );
  }

  Widget _buildFontSizeSection(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) {
    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Icon(
              Icons.text_fields,
              color: colorScheme.primary,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              AppLocalizations.of(context)!.settingsFontSectionTitle,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: colorScheme.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        // Preview Font Size
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    AppLocalizations.of(context)!.settingsFontPreviewSizeTitle,
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                  Text(
                    AppLocalizations.of(context)!
                        .settingsFontPreviewSizeSubtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 80,
              child: TextFormField(
                initialValue: settings.previewFontSize.toStringAsFixed(0),
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                  isDense: true,
                ),
                onChanged: (String value) {
                  final double? fontSize = double.tryParse(value);
                  if (fontSize != null && fontSize >= 8 && fontSize <= 32) {
                    notifier.updateGeneralSettings(previewFontSize: fontSize);
                    // Auto-adjust edit font size to be 2pt larger if not explicitly set
                    if ((settings.editFontSize - settings.previewFontSize)
                            .abs() <
                        1.0) {
                      notifier.updateGeneralSettings(
                        editFontSize: fontSize + 2.0,
                      );
                    }
                  }
                },
              ),
            ),
            const SizedBox(width: 8),
            Text(AppLocalizations.of(context)!.settingsUnitPt),
          ],
        ),
        const SizedBox(height: 16),
        // Edit Font Size
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    AppLocalizations.of(context)!.settingsFontEditSizeTitle,
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                  Text(
                    AppLocalizations.of(context)!.settingsFontEditSizeSubtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 80,
              child: TextFormField(
                initialValue: settings.editFontSize.toStringAsFixed(0),
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                  isDense: true,
                ),
                onChanged: (String value) {
                  final double? fontSize = double.tryParse(value);
                  if (fontSize != null && fontSize >= 8 && fontSize <= 32) {
                    notifier.updateGeneralSettings(editFontSize: fontSize);
                  }
                },
              ),
            ),
            const SizedBox(width: 8),
            Text(AppLocalizations.of(context)!.settingsUnitPt),
          ],
        ),
      ],
    );
  }

  Widget _buildTranslationSettings() {
    final globalSettings = ref.watch(globalSettingsProvider);
    final globalNotifier = ref.read(globalSettingsProvider.notifier);
    final l10n = AppLocalizations.of(context)!;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: <Widget>[
          // Basic Translation Settings
          Card(
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Icon(Icons.translate, color: Colors.blue.shade700),
                      const SizedBox(width: 8),
                      Text(
                        AppLocalizations.of(context)!.settingsTranslationTitle,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.blue.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.shade200),
                    ),
                    child: Row(
                      children: <Widget>[
                        Icon(
                          Icons.info,
                          color: Colors.orange.shade700,
                          size: 16,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            AppLocalizations.of(context)!
                                .settingsTranslationNotice,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.orange.shade700,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Removed default AI platform selector (migrated to Translation Quick Settings)
                  const Divider(),
                  // Auto Generate Glossary Switch
                  SwitchListTile(
                    title: Text(
                      AppLocalizations.of(context)!
                          .settingsTranslationAutoGlossaryTitle,
                    ),
                    subtitle: Text(
                      AppLocalizations.of(context)!
                          .settingsTranslationAutoGlossarySubtitle,
                    ),
                    value: globalSettings.glossaryGenerateEnable,
                    onChanged: (bool value) {
                      globalNotifier.updateGlossarySettings(
                        glossaryGenerateEnable: value,
                      );
                    },
                    secondary: const Icon(Icons.book),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Default Target Language
          Card(
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Icon(Icons.language, color: Colors.teal.shade700),
                      const SizedBox(width: 8),
                      Text(
                        AppLocalizations.of(context)!
                            .settingsTargetLanguageTitle,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.teal.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.teal.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.teal.shade200),
                    ),
                    child: Row(
                      children: <Widget>[
                        Icon(
                          Icons.info_outline,
                          color: Colors.teal.shade700,
                          size: 16,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            AppLocalizations.of(context)!
                                .settingsTargetLanguageNotice,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.teal.shade700,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: globalSettings.targetLanguage,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: languageDropdownEntries.map((
                      Map<String, String> lang,
                    ) {
                      return DropdownMenuItem<String>(
                        value: lang['code'],
                        child: Text(
                          languageDisplayName(l10n, lang['code']!),
                        ),
                      );
                    }).toList(),
                    onChanged: (String? value) {
                      if (value != null) {
                        globalNotifier.updateTranslationSettings(
                          targetLanguage: value,
                        );
                      }
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Detailed Translation Parameters
          Card(
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Icon(Icons.tune, color: Colors.green.shade700),
                      const SizedBox(width: 8),
                      Text(
                        AppLocalizations.of(context)!
                            .settingsTranslationParamsTitle,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.green.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Temperature removed - now in Quick Settings
                  // _buildTemperatureSlider(globalSettings, globalNotifier),
                  // const SizedBox(height: 16),

                  // Thinking Mode removed - now in AI Platform Settings
                  // _buildThinkingDropdown(globalSettings, globalNotifier),
                  // const SizedBox(height: 16),

                  // Performance Parameters
                  _buildRetryField(globalSettings, globalNotifier),
                  const SizedBox(height: 16),
                  _buildSegmentAutoRetryField(globalSettings, globalNotifier),
                  const SizedBox(height: 16),
                  _buildTranslateOutputSuffixField(globalSettings, globalNotifier),
                  const SizedBox(height: 16),
                  _buildConvertOutputSuffixField(globalSettings, globalNotifier),
                  const SizedBox(height: 16),

                  // Custom Prompt removed: Prompt is now controlled per task in Quick Settings
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Default Exclusion Rules
          Card(
            elevation: 4,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Icon(Icons.filter_alt, color: Colors.deepPurple.shade700),
                      const SizedBox(width: 8),
                      Text(
                        AppLocalizations.of(context)!.settingsExclusionTitle,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.deepPurple.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.deepPurple.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.deepPurple.shade200),
                    ),
                    child: Row(
                      children: <Widget>[
                        Icon(
                          Icons.info_outline,
                          color: Colors.deepPurple.shade700,
                          size: 16,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            AppLocalizations.of(context)!
                                .settingsExclusionNotice,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.deepPurple.shade700,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  ..._buildExclusionSwitches(globalSettings, globalNotifier),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Build the list of exclusion toggle switches.
  List<Widget> _buildExclusionSwitches(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) {
    final Map<String, bool> defaults =
        Map<String, bool>.from(settings.exclusionDefaults);

    final List<Map<String, String>> exclusionItems = <Map<String, String>>[
      <String, String>{
        'key': 'image',
        'title': AppLocalizations.of(context)!.settingsExclusionImageTitle,
        'subtitle':
            AppLocalizations.of(context)!.settingsExclusionImageSubtitle,
        'icon': 'image',
      },
      <String, String>{
        'key': 'formula',
        'title': AppLocalizations.of(context)!.settingsExclusionFormulaTitle,
        'subtitle':
            AppLocalizations.of(context)!.settingsExclusionFormulaSubtitle,
        'icon': 'functions',
      },
      <String, String>{
        'key': 'reference',
        'title': AppLocalizations.of(context)!.settingsExclusionReferenceTitle,
        'subtitle':
            AppLocalizations.of(context)!.settingsExclusionReferenceSubtitle,
        'icon': 'format_quote',
      },
      <String, String>{
        'key': 'identifier',
        'title': AppLocalizations.of(context)!.settingsExclusionIdentifierTitle,
        'subtitle': AppLocalizations.of(context)!
            .settingsExclusionIdentifierSubtitle,
        'icon': 'tag',
      },
      <String, String>{
        'key': 'structural',
        'title': AppLocalizations.of(context)!.settingsExclusionStructuralTitle,
        'subtitle': AppLocalizations.of(context)!
            .settingsExclusionStructuralSubtitle,
        'icon': 'view_agenda',
      },
      <String, String>{
        'key': 'table',
        'title': AppLocalizations.of(context)!.settingsExclusionTableTitle,
        'subtitle':
            AppLocalizations.of(context)!.settingsExclusionTableSubtitle,
        'icon': 'table_chart',
      },
      <String, String>{
        'key': 'language_match',
        'title':
            AppLocalizations.of(context)!.settingsExclusionLanguageMatchTitle,
        'subtitle': AppLocalizations.of(context)!
            .settingsExclusionLanguageMatchSubtitle,
        'icon': 'language',
      },
    ];

    const Map<String, IconData> iconMap = <String, IconData>{
      'image': Icons.image,
      'functions': Icons.functions,
      'format_quote': Icons.format_quote,
      'tag': Icons.tag,
      'view_agenda': Icons.view_agenda,
      'table_chart': Icons.table_chart,
      'language': Icons.language,
    };

    return exclusionItems.map((Map<String, String> item) {
      final String key = item['key']!;
      final bool value = defaults[key] ?? false;
      return SwitchListTile(
        title: Text(item['title']!),
        subtitle: Text(item['subtitle']!),
        value: value,
        onChanged: (bool newValue) {
          final Map<String, bool> updated = Map<String, bool>.from(defaults);
          updated[key] = newValue;
          notifier.updateExclusionDefaults(exclusionDefaults: updated);
        },
        secondary: Icon(iconMap[item['icon']] ?? Icons.help_outline),
      );
    }).toList();
  }

  void _showLanguageDialog(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) {
    showDialog(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: Text(
          AppLocalizations.of(context)!.settingsLanguageDialogTitle,
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: _languages
              .map(
                (Map<String, String> lang) => RadioListTile<String>(
                  title: Text(lang['name']!),
                  value: lang['code']!,
                  groupValue: settings.language,
                  onChanged: (String? value) async {
                    if (value == null) return;
                    await notifier.updateGeneralSettings(language: value);
                    if (context.mounted) {
                      Navigator.of(context).pop();
                    }
                  },
                ),
              )
              .toList(),
        ),
      ),
    );
  }

  // Removed: _buildDefaultAIPlatformSection (migrated to Translation Quick Settings)

  // Translation Parameters UI Components
  // Removed: _buildTemperatureSlider (moved to Quick Settings)
  // Removed: _buildThinkingDropdown (moved to AI Platform Settings)



  Widget _buildRetryField(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!.settingsTranslationChunkRetryTitle,
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          TextFormField(
            initialValue: settings.retry.toString(),
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              hintText:
                  AppLocalizations.of(context)!.settingsTranslationChunkRetryHint,
            ),
            onChanged: (String value) {
              final int? intValue = int.tryParse(value);
              if (intValue != null && intValue >= 0) {
                notifier.updateTranslationSettings(retry: intValue);
              }
            },
          ),
        ],
      );

  Widget _buildSegmentAutoRetryField(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!
                .settingsTranslationSegmentAutoRetryTitle,
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          TextFormField(
            initialValue: settings.segmentAutoRetryRounds.toString(),
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              hintText: AppLocalizations.of(context)!
                  .settingsTranslationSegmentAutoRetryHint,
            ),
            onChanged: (String value) {
              final int? intValue = int.tryParse(value);
              if (intValue != null && intValue >= 1 && intValue <= 10) {
                notifier.updateTranslationSettings(
                  segmentAutoRetryRounds: intValue,
                );
              }
            },
          ),
        ],
      );

  Widget _buildTranslateOutputSuffixField(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!.settingsTranslateOutputSuffixTitle,
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          TextFormField(
            initialValue: settings.translateOutputSuffix,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              hintText:
                  AppLocalizations.of(context)!.settingsTranslateOutputSuffixHint,
            ),
            onChanged: (String value) {
              notifier.updateTranslationSettings(translateOutputSuffix: value);
            },
          ),
        ],
      );

  Widget _buildConvertOutputSuffixField(
    GlobalSettings settings,
    GlobalSettingsNotifier notifier,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            AppLocalizations.of(context)!.settingsConvertOutputSuffixTitle,
            style: const TextStyle(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          TextFormField(
            initialValue: settings.convertOutputSuffix,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              hintText:
                  AppLocalizations.of(context)!.settingsConvertOutputSuffixHint,
            ),
            onChanged: (String value) {
              notifier.updateTranslationSettings(convertOutputSuffix: value);
            },
          ),
        ],
      );

}
