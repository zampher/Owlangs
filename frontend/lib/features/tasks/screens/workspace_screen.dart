// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:material_design_icons_flutter/material_design_icons_flutter.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../l10n/app_localizations.dart';
import '../../../app/app_config.dart';
import '../../../app/app_router.dart';
import '../../../core/constants/app_constants.dart';
import '../../../shared/models/user_model.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/services/donor_activation_service.dart';
import '../providers/tasks_provider.dart';
import '../models/task.dart';
import '../models/persisted_flow_state.dart';
import '../services/flow_data_cache.dart';
import '../../translation/screens/translation_screen.dart';
import '../../translation/providers/translation_state_provider_family.dart';
import '../../translation/providers/preview_tabs_provider.dart';
import '../../translation/providers/queue_persist_dirty_provider.dart';
import '../../../shared/services/translation_service.dart';
import '../../anonymize/screens/anonymize_screen.dart';
import '../../anonymize/screens/anonymize_and_translate_screen.dart';
import '../../anonymize/screens/de_anonymize_screen.dart';
import '../../home/screens/home_screen.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/providers/admin_permissions_provider.dart';
import '../../../shared/providers/auth_provider.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/widgets/admin_required_dialog.dart';
import '../../settings/screens/ai_platform_settings.dart'
    show AIPlatformSettings, aiPlatformSettingsProvider;
import '../../../widgets/ad_placeholder.dart' show AdPlaceholder;

class WorkspaceScreen extends ConsumerStatefulWidget {
  const WorkspaceScreen({super.key});

  @override
  ConsumerState<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

enum _UserMenuAction {
  changePassword,
  logout,
}

class _WorkspaceScreenState extends ConsumerState<WorkspaceScreen> {
  String? _editingTaskId;
  final TextEditingController _titleController = TextEditingController();
  bool _isAdBannerVisible = true;

  /// Seed for owl pose/position in banner ad placeholder; independent from flow.
  int _bannerOwlPoseSeed = 0;

  // Flag to prevent duplicate flow creation from rapid clicks
  bool _isCreatingFlow = false;

  // Pro activation status: null = loading, false = Basic, true = Pro
  bool? _isDonor;

  // Scroll controller for task tabs
  final ScrollController _taskTabsScrollController = ScrollController();
  bool _canScrollLeft = false;
  bool _canScrollRight = false;

  // GlobalKey for Help button to get its position
  final GlobalKey _helpButtonKey = GlobalKey();

  /// Defer building HomeScreen to next frame so route transition paints quickly.
  bool _homeContentReady = false;
  bool _homeDeferScheduled = false;

  Future<void> _closeFlowAndReleaseResources(String flowId) async {
    try {
      // Release backend translation task resources for this flow if present
      final translationState = ref.read(
        translationStateProviderFamily(flowId),
      );
      final String? taskId = translationState.taskId;
      if (taskId != null &&
          taskId.isNotEmpty &&
          !taskId.startsWith('pending_')) {
        try {
          final TranslationService svc = TranslationService();
          await svc.releaseTask(taskId);
        } catch (_) {
          // Ignore errors when closing flow; failing to release is non-fatal
        }
      }

      // Clear preview tabs and translation state for this flow
      ref.read(previewTabsProviderFamily(flowId).notifier).clearAllTabs();
      ref
          .read(translationStateProviderFamily(flowId).notifier)
          .resetTranslation();
    } finally {
      // Finally close the flow tab itself
      ref.read(tasksProvider.notifier).closeTask(flowId);
    }
  }

  Future<void> _confirmCloseFlow(String flowId) async {
    final translationState = ref.read(
      translationStateProviderFamily(flowId),
    );
    final String? taskId = translationState.taskId;
    final bool hasResources =
        taskId != null && taskId.isNotEmpty && !taskId.startsWith('pending_');
    final bool dirty = ref.read(queuePersistDirtyProvider(flowId));

    // No task resources and not dirty — close silently
    if (!hasResources && !dirty) {
      await _closeFlowAndReleaseResources(flowId);
      return;
    }

    final bool hasPersistableTask = hasResources;

    final String? choice = await showDialog<String>(
      context: context,
      builder: (BuildContext dialogContext) {
        final l10n = AppLocalizations.of(dialogContext)!;
        return AlertDialog(
          title: Text(l10n.workspaceCloseFlowTitle),
          content: Text(l10n.workspaceCloseFlowMessage),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop('cancel'),
              child: Text(l10n.workspaceCloseFlowCancel),
            ),
            if (hasPersistableTask)
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop('save'),
                child: Text(l10n.workspaceCloseFlowSaveToQueue),
              ),
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop('destroy'),
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(dialogContext).colorScheme.error,
              ),
              child: Text(l10n.workspaceCloseFlowDestroy),
            ),
          ],
        );
      },
    );

    if (choice == null || choice == 'cancel') {
      return;
    }

    if (choice == 'save' && hasPersistableTask) {
      try {
        final TranslationService svc = TranslationService();
        await svc.persistQueueSnapshot(taskId);
        ref.read(queuePersistDirtyProvider(flowId).notifier).clear();
      } catch (e) {
        if (mounted) {
          final String label = AppLocalizations.of(context)!
              .workspaceCloseFlowSaveToQueue;
          MessageService.showError(
            context,
            '$label failed: $e',
          );
        }
        return;
      }
      // Close tab without releasing — release would delete the stash we just saved.
      // The task stays alive in the backend so it appears in the queue screen.
      ref.read(tasksProvider.notifier).closeTask(flowId);
      return;
    }

    // choice == 'destroy' — release backend resources, then close tab
    await _closeFlowAndReleaseResources(flowId);
  }

  void _startEditing(String taskId, String currentTitle) {
    setState(() {
      _editingTaskId = taskId;
      _titleController.text = currentTitle;
    });
  }

  void _finishEditing(TasksNotifier notifier, String taskId) {
    final newTitle = _titleController.text.trim();
    if (newTitle.isNotEmpty) {
      notifier.renameTask(taskId, newTitle);
    }
    setState(() {
      _editingTaskId = null;
      _titleController.clear();
    });
  }

  Future<void> _showChangePasswordDialog(BuildContext context) async {
    final TextEditingController currentPasswordController =
        TextEditingController();
    final TextEditingController newPasswordController = TextEditingController();
    final TextEditingController confirmPasswordController =
        TextEditingController();

    String? errorText;
    bool isSubmitting = false;
    String newPasswordValue = '';

    await showDialog<void>(
      context: context,
      barrierDismissible: !isSubmitting,
      builder: (BuildContext dialogContext) {
        final l10n = AppLocalizations.of(dialogContext)!;
        final ColorScheme colorScheme = Theme.of(dialogContext).colorScheme;

        bool hasLength(String value) =>
            value.length >= 8 && value.length <= 128;
        bool hasUppercase(String value) => value.contains(RegExp('[A-Z]'));
        bool hasLowercase(String value) => value.contains(RegExp('[a-z]'));
        bool hasDigit(String value) => value.contains(RegExp('[0-9]'));

        Widget buildRequirementRow(String label, bool met) => Row(
            children: <Widget>[
              Icon(
                met ? Icons.check_circle : Icons.cancel,
                size: 16,
                color: met ? Colors.green : colorScheme.error.withOpacity(0.7),
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  color: met
                      ? Colors.green
                      : colorScheme.onSurface.withOpacity(0.7),
                ),
              ),
            ],
          );

        return StatefulBuilder(
          builder:
              (BuildContext context, void Function(void Function()) setState) =>
                  AlertDialog(
            title: Text(l10n.userMenuChangePassword),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                TextField(
                  controller: currentPasswordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: l10n.changePasswordCurrentPasswordLabel,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: newPasswordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: l10n.changePasswordNewPasswordLabel,
                  ),
                  onChanged: (String value) {
                    setState(() {
                      newPasswordValue = value;
                    });
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: confirmPasswordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: l10n.changePasswordConfirmPasswordLabel,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest.withOpacity(0.3),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        l10n.changePasswordRequirementsTitle,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: colorScheme.onSurface.withOpacity(0.85),
                        ),
                      ),
                      const SizedBox(height: 6),
                      buildRequirementRow(
                        l10n.changePasswordRequirementLength,
                        hasLength(newPasswordValue),
                      ),
                      buildRequirementRow(
                        l10n.changePasswordRequirementUppercase,
                        hasUppercase(newPasswordValue),
                      ),
                      buildRequirementRow(
                        l10n.changePasswordRequirementLowercase,
                        hasLowercase(newPasswordValue),
                      ),
                      buildRequirementRow(
                        l10n.changePasswordRequirementDigit,
                        hasDigit(newPasswordValue),
                      ),
                    ],
                  ),
                ),
                if (errorText != null) ...<Widget>[
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      errorText!,
                      style: TextStyle(
                        fontSize: 13,
                        color: colorScheme.error,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            actions: <Widget>[
              TextButton(
                onPressed: isSubmitting
                    ? null
                    : () {
                        Navigator.of(dialogContext).pop();
                      },
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: isSubmitting
                    ? null
                    : () async {
                        final currentPassword =
                            currentPasswordController.text.trim();
                        final newPassword = newPasswordController.text.trim();
                        final confirmPassword =
                            confirmPasswordController.text.trim();

                        if (currentPassword.isEmpty ||
                            newPassword.isEmpty ||
                            confirmPassword.isEmpty) {
                          setState(() {
                            errorText = l10n.changePasswordRequiredError;
                          });
                          return;
                        }
                        if (newPassword != confirmPassword) {
                          setState(() {
                            errorText = l10n.changePasswordConfirmMismatchError;
                          });
                          return;
                        }
                        if (!hasLength(newPassword) ||
                            !hasUppercase(newPassword) ||
                            !hasLowercase(newPassword) ||
                            !hasDigit(newPassword)) {
                          setState(() {
                            errorText =
                                '${l10n.changePasswordRequirementsTitle}: ${l10n.changePasswordRequirementLength}, ${l10n.changePasswordRequirementUppercase}, ${l10n.changePasswordRequirementLowercase}, ${l10n.changePasswordRequirementDigit}';
                          });
                          return;
                        }

                        setState(() {
                          isSubmitting = true;
                          errorText = null;
                        });

                        try {
                          await ConfigService().changeOwnPassword(
                            currentPassword: currentPassword,
                            newPassword: newPassword,
                          );
                          if (!mounted) {
                            return;
                          }
                          Navigator.of(dialogContext).pop();
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                l10n.changePasswordSuccessMessage,
                              ),
                            ),
                          );
                        } catch (e) {
                          setState(() {
                            errorText = e.toString();
                            isSubmitting = false;
                          });
                        }
                      },
                child: isSubmitting
                    ? SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            colorScheme.primary,
                          ),
                        ),
                      )
                    : const Text('Save'),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showSourceTypeDialog(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    showDialog<void>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueNewQueuedTask),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            ListTile(
              leading: const Icon(Icons.upload_file),
              title: Text(l10n.batchUploadSelectSingleFile),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push(
                  '${AppRouter.batchUploadRoute}?source=single',
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.folder_open),
              title: Text(l10n.batchUploadSelectFolder),
              subtitle: Text(l10n.batchUploadFolderDescription),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push('${AppRouter.batchUploadRoute}?source=folder');
              },
            ),
            ListTile(
              leading: const Icon(Icons.folder_zip_outlined),
              title: Text(l10n.batchUploadSelectZip),
              subtitle: Text(l10n.batchUploadZipDescription),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push('${AppRouter.batchUploadRoute}?source=zip');
              },
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(l10n.commonCancel),
          ),
        ],
      ),
    );
  }

  Future<void> _createFlowWithProtection(TaskFlow flowType) async {
    // Prevent duplicate flow creation
    if (_isCreatingFlow) {
      return;
    }

    if (flowType == TaskFlow.anonymizeAndTranslate) {
      MessageService.showInfo(
        context,
        AppLocalizations.of(context)!.homeFeatureUnderDevelopment,
      );
      return;
    }

    if (flowType == TaskFlow.anonymize && !kIsWeb) {
      MessageService.showInfo(
        context,
        AppLocalizations.of(context)!.homeAnonymizeNotSupportedVersion(
          AppConstants.plannedVersionAnonymize,
        ),
      );
      return;
    }

    _isCreatingFlow = true;
    try {
      final notifier = ref.read(tasksProvider.notifier);
      await notifier.createFlow(sourceType: TaskType.file, flowType: flowType);
      if (mounted) {
        setState(() {
          _bannerOwlPoseSeed++;
        });
      }
    } finally {
      // Reset flag after a short delay to allow UI to update
      Future.delayed(const Duration(milliseconds: 500), () {
        if (mounted) {
          setState(() {
            _isCreatingFlow = false;
          });
        }
      });
    }
  }

  /// Settings and Setup wizard buttons. Web: show when admin or when unauthenticated (click then redirects to login). Desktop: show when admin.
  List<Widget> _adminOnlyActionButtons(
    AppLocalizations l10n,
    bool highlightSetupWizardButton,
  ) {
    final canAccess = ref.watch(canAccessAdminSettingsProvider).valueOrNull;
    final authState = ref.watch(authProvider);
    final isUnauthenticated = authState.maybeWhen(
      unauthenticated: () => true,
      orElse: () => false,
    );
    final showOnWeb = kIsWeb && ((canAccess ?? false) || isUnauthenticated);
    if (!kIsWeb && canAccess != true) return <Widget>[];
    if (kIsWeb && !showOnWeb) return <Widget>[];
    return <Widget>[
      _buildActionButton(
        icon: Icons.settings_outlined,
        label: l10n.homeNavSettings,
        onPressed: () {
          if (kIsWeb && isUnauthenticated) {
            showAdminRequiredDialog(context);
            return;
          }
          context.go(AppRouter.settingsRoute);
        },
      ),
      const SizedBox(width: 4),
      _buildActionButton(
        icon: Icons.auto_fix_high,
        label: l10n.setupWizardTitle,
        onPressed: () {
          if (kIsWeb && isUnauthenticated) {
            showAdminRequiredDialog(context);
            return;
          }
          context.go(AppRouter.setupWizardRoute);
        },
        width: 96,
        highlight: highlightSetupWizardButton,
      ),
      const SizedBox(width: 4),
    ];
  }

  /// Build language selector dropdown for desktop
  Widget _buildLanguageSelector() {
    final globalSettings = ref.watch(globalSettingsProvider);
    final globalNotifier = ref.read(globalSettingsProvider.notifier);

    final supportedLanguages = <Map<String, String>>[
      <String, String>{'code': 'en', 'name': 'EN'},
      <String, String>{'code': 'zh', 'name': '中文'},
      <String, String>{'code': 'ja', 'name': '日本語'},
      <String, String>{'code': 'ko', 'name': '한국어'},
      <String, String>{'code': 'es', 'name': 'ES'},
    ];

    return Container(
      height: 36,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant.withOpacity(0.5),
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: supportedLanguages
                  .any((e) => e['code'] == globalSettings.language)
              ? globalSettings.language
              : 'en',
          icon: const Icon(Icons.arrow_drop_down, size: 18),
          borderRadius: BorderRadius.circular(6),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: Theme.of(context).colorScheme.onSurface,
          ),
          items: supportedLanguages
              .map(
                (lang) => DropdownMenuItem<String>(
                  value: lang['code'],
                  child: Text(
                    lang['name']!,
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              )
              .toList(),
          onChanged: (String? value) async {
            if (value != null && value != globalSettings.language) {
              await globalNotifier.updateGeneralSettings(language: value);
            }
          },
        ),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    // Listen to scroll position changes to update button states
    _taskTabsScrollController.addListener(_updateScrollButtons);
    _loadUserType();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _taskTabsScrollController.removeListener(_updateScrollButtons);
    _taskTabsScrollController.dispose();
    super.dispose();
  }

  void _updateScrollButtons() {
    final scrollController = _taskTabsScrollController;
    if (!scrollController.hasClients) {
      return;
    }

    final canScrollLeft = scrollController.position.pixels > 0;
    final canScrollRight = scrollController.position.pixels <
        scrollController.position.maxScrollExtent;

    if (canScrollLeft != _canScrollLeft || canScrollRight != _canScrollRight) {
      setState(() {
        _canScrollLeft = canScrollLeft;
        _canScrollRight = canScrollRight;
      });
    }
  }

  Future<void> _loadUserType() async {
    try {
      final donorService = DonorActivationService();
      final status = await donorService.getStatus();
      if (mounted) {
        setState(() {
          _isDonor = status.activated;
        });
        if (status.expired) {
          donorService.clearExpiredFlag();
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            final l10n = AppLocalizations.of(context)!;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(l10n.homeSnackDonorExpired),
                duration: const Duration(seconds: 6),
              ),
            );
          });
        }
      }
    } catch (_) {
      // On error, default to Basic user
      if (mounted) {
        setState(() {
          _isDonor = false;
        });
      }
    }
  }

  void _scrollTabsLeft() {
    if (_taskTabsScrollController.hasClients) {
      _taskTabsScrollController.animateTo(
        _taskTabsScrollController.position.pixels - 200,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  void _scrollTabsRight() {
    if (_taskTabsScrollController.hasClients) {
      _taskTabsScrollController.animateTo(
        _taskTabsScrollController.position.pixels + 200,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final ref = this.ref;
    final tasks = ref.watch(tasksProvider);
    final notifier = ref.read(tasksProvider.notifier);
    final l10n = AppLocalizations.of(context)!;
    final AIPlatformSettings aiSettings = ref.watch(aiPlatformSettingsProvider);
    final bool highlightSetupWizardButton = !aiSettings.isLoading &&
        aiSettings.platforms.values
            .where((p) => p.platformType == 'llm' && p.isConfigured)
            .isEmpty;

    // Update scroll buttons after layout
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _updateScrollButtons();
    });

    final showAds = ref.watch(showAdsProvider).value ?? false;

    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(90),
        child: AnimatedSize(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          child: AppBar(
            elevation: 0,
            backgroundColor: Theme.of(context).colorScheme.surface,
            toolbarHeight: 90,
            centerTitle: false,
            titleSpacing: 0,
            automaticallyImplyLeading: false,
            title: LayoutBuilder(
              builder: (context, constraints) {
                // When AppBar title area is very narrow (< 300px), hide
                // secondary widgets (language selector, auth) and shrink logos
                // so the title never overflows.
                final bool spacious = constraints.maxWidth >= 300;
                return Row(
              children: <Widget>[
                Flexible(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      // Leading: Logo
                      Padding(
                        padding: const EdgeInsets.all(4),
                        child: Image.asset(
                          'images/logo_96.png',
                          width: spacious ? 56 : 40,
                          height: spacious ? 56 : 40,
                          errorBuilder: (
                            BuildContext context,
                            Object error,
                            StackTrace? stackTrace,
                          ) =>
                              Icon(
                            Icons.language,
                            size: spacious ? 36 : 28,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                        ),
                      ),
                      // Title
                      Text(
                        'Owlangs',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 2,
                      ),
                      // Desktop only: Language selector next to title
                      if (spacious && !kIsWeb) ...<Widget>[
                        const SizedBox(width: 12),
                        _buildLanguageSelector(),
                      ],
                      // Web only: show username, language switcher, and Login/Logout links
                      if (spacious && kIsWeb) ...<Widget>[
                        const SizedBox(width: 12),
                        Builder(
                          builder: (BuildContext context) {
                            final authState = ref.watch(authProvider);
                            final isAuthenticated = authState.maybeWhen(
                              authenticated: (_) => true,
                              orElse: () => false,
                            );
                            final displayName = authState.maybeWhen(
                              authenticated: (user) => user.username,
                              orElse: () => 'guest',
                            );
                            final bool isGuestUser = !isAuthenticated ||
                                displayName.toLowerCase() == 'guest';
                            final Color linkColor = Theme.of(context)
                                .colorScheme
                                .primary
                                .withOpacity(0.85);
                            final globalSettings = ref.watch(globalSettingsProvider);
                            final GlobalSettingsNotifier globalNotifier =
                                ref.read(globalSettingsProvider.notifier);
                            const List<Map<String, String>> languages =
                                <Map<String, String>>[
                              <String, String>{'code': 'zh', 'label': '中文'},
                              <String, String>{'code': 'en', 'label': 'English'},
                              <String, String>{'code': 'ja', 'label': '日本語'},
                              <String, String>{'code': 'ko', 'label': '한국어'},
                              <String, String>{'code': 'es', 'label': 'Español'},
                            ];
                            final String currentLang = globalSettings.language;
                            final String currentLabel = languages.firstWhere(
                                  (Map<String, String> lang) =>
                                      lang['code'] == currentLang,
                                  orElse: () => const <String, String>{
                                    'code': 'en',
                                    'label': 'English',
                                  },
                                )['label'] ??
                                currentLang;

                            return Row(
                              mainAxisSize: MainAxisSize.min,
                              children: <Widget>[
                                if (!isGuestUser)
                                  PopupMenuButton<_UserMenuAction>(
                                    tooltip: displayName,
                                    onSelected:
                                        (_UserMenuAction selectedAction) async {
                                      switch (selectedAction) {
                                        case _UserMenuAction.changePassword:
                                          await _showChangePasswordDialog(context);
                                          break;
                                        case _UserMenuAction.logout:
                                          await ref
                                              .read(authProvider.notifier)
                                              .logout();
                                          if (context.mounted) {
                                            context.go(AppRouter.loginRoute);
                                          }
                                          break;
                                      }
                                    },
                                    itemBuilder: (BuildContext context) =>
                                        <PopupMenuEntry<_UserMenuAction>>[
                                      PopupMenuItem<_UserMenuAction>(
                                        value: _UserMenuAction.changePassword,
                                        child: Text(
                                          l10n.userMenuChangePassword,
                                        ),
                                      ),
                                      PopupMenuItem<_UserMenuAction>(
                                        value: _UserMenuAction.logout,
                                        child: Text(
                                          l10n.commonLogout,
                                        ),
                                      ),
                                    ],
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: <Widget>[
                                        Icon(
                                          Icons.person,
                                          size: 18,
                                          color: linkColor,
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          displayName,
                                          style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w500,
                                            color: linkColor,
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const Icon(
                                          Icons.arrow_drop_down,
                                          size: 18,
                                        ),
                                      ],
                                    ),
                                  )
                                else ...<Widget>[
                                  Icon(
                                    Icons.person,
                                    size: 18,
                                    color: linkColor,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    displayName,
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                      color: linkColor,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                                const SizedBox(width: 12),
                                Text(
                                  '|',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: linkColor.withOpacity(0.5),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                PopupMenuButton<String>(
                                  tooltip: 'Language',
                                  initialValue: currentLang,
                                  padding: EdgeInsets.zero,
                                  itemBuilder: (BuildContext context) =>
                                      languages.map((Map<String, String> lang) {
                                    final String code = lang['code']!;
                                    final String label = lang['label']!;
                                    return PopupMenuItem<String>(
                                      value: code,
                                      child: Text(label),
                                    );
                                  }).toList(),
                                  onSelected:
                                      globalNotifier.updateUiLanguageLocalOnly,
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: <Widget>[
                                      Icon(
                                        Icons.language,
                                        size: 18,
                                        color: linkColor,
                                      ),
                                      const SizedBox(width: 4),
                                      Text(
                                        currentLabel,
                                        style: TextStyle(
                                          fontSize: 13,
                                          color: linkColor,
                                        ),
                                      ),
                                      const Icon(
                                        Icons.arrow_drop_down,
                                        size: 18,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  '|',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: linkColor.withOpacity(0.5),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                if (!isAuthenticated)
                                  TextButton(
                                    onPressed: () {
                                      context.go(AppRouter.loginRoute);
                                    },
                                    style: TextButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 4,
                                      ),
                                      minimumSize: Size.zero,
                                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: <Widget>[
                                        Icon(
                                          Icons.login,
                                          size: 16,
                                          color: linkColor,
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          l10n.commonLogin,
                                          style: TextStyle(
                                            fontSize: 13,
                                            color: linkColor,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                              ],
                            );
                          },
                        ),
                      ],
                    ],
                  ),
                ),
                const Spacer(),
                const SizedBox(width: 8),
                // Optional ad banner on the left of buttons
                if (showAds && _isAdBannerVisible) ...<Widget>[
                  Expanded(
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: _buildAdBanner728x90(),
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
              ],
            );
          },
        ),
        actions: <Widget>[
              // Immersive translate (flow tab)
              _buildActionButton(
                icon: Icons.translate,
                label: l10n.homeNavTranslate,
                width: 92,
                maxLabelLines: 2,
                onPressed: _isCreatingFlow
                    ? null
                    : () => _createFlowWithProtection(
                          TaskFlow.translate,
                        ),
              ),
              const SizedBox(width: 4),
              // Queued translation: standalone flow (same entry as task queue "new" button)
              _buildActionButton(
                icon: Icons.playlist_add,
                label: l10n.translationQueueNewQueuedTask,
                width: 92,
                maxLabelLines: 2,
                onPressed: () => _showSourceTypeDialog(context),
              ),
              const SizedBox(width: 4),
              // Translation queue (list + poll + download)
              _buildActionButton(
                icon: Icons.queue_play_next_outlined,
                label: l10n.homeNavTranslationQueue,
                width: 92,
                maxLabelLines: 2,
                onPressed: () => context.push(AppRouter.translationQueueRoute),
              ),
              const SizedBox(width: 4),
              // Anonymize button - visible only for Pro users on Web
              if ((_isDonor ?? false) && kIsWeb) ...<Widget>[
                _buildActionButton(
                  icon: Icons.visibility_off,
                  label: l10n.homeNavAnonymize,
                  onPressed: _isCreatingFlow
                      ? null
                      : () {
                          if (!AppConfig.kEnableFeaturesInDevelopment) {
                            MessageService.showInfo(
                              context,
                              l10n.homeAnonymizeInDevelopment,
                            );
                            return;
                          }
                          _createFlowWithProtection(TaskFlow.anonymize);
                        },
                ),
                const SizedBox(width: 4),
              ],
              // Settings and Setup wizard (Web: admin only)
              ..._adminOnlyActionButtons(l10n, highlightSetupWizardButton),
              const SizedBox(width: 4),
              // Help button
              _buildActionButton(
                key: _helpButtonKey,
                icon: Icons.help_outline,
                label: l10n.homeNavDonateHelp,
                onPressed: () => context.push(
                  AppRouter.donateRoute,
                  extra: <String, dynamic>{'mode': 'help'},
                ),
                width: 72,
              ),
              const SizedBox(width: 4),
              // Donate button
              _buildActionButton(
                icon: Icons.volunteer_activism,
                label: l10n.homeNavDonate,
                onPressed: () => context.push(
                  AppRouter.donateRoute,
                  extra: <String, dynamic>{'mode': 'donate'},
                ),
                width: 72,
              ),
              const SizedBox(width: 4),
              const _GitHubStarButton(),
              Builder(
                builder: (BuildContext context) {
                  final currentPath = GoRouter.of(context)
                      .routerDelegate
                      .currentConfiguration
                      .uri
                      .path;
                  final isHomePage =
                      currentPath == AppRouter.homeRoute || currentPath == '/';
                  if (isHomePage) {
                    return const SizedBox.shrink();
                  }
                  return Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const SizedBox(width: 4),
                      _buildActionButton(
                        icon: Icons.home_outlined,
                        label: l10n.homeNavHome,
                        onPressed: () => context.go(AppRouter.homeRoute),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(width: 8),
            ],
          ),
        ),
      ),
      body: Column(
        children: <Widget>[
          // Task bar with scroll buttons
          Container(
            height: 32, // Fixed height at 32px for Tab Title
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              border: Border(
                bottom: BorderSide(color: Theme.of(context).dividerColor),
              ),
            ),
            child: Row(
              children: <Widget>[
                // Left scroll button
                if (_canScrollLeft)
                  Container(
                    width: 32,
                    height: 32, // Fixed height at 32px for Tab Title
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: IconButton(
                      icon: const Icon(
                        Icons.chevron_left,
                        size: 18,
                      ), // Reduced from 20 to 18
                      onPressed: _scrollTabsLeft,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 28, // Reduced from 32 to 28
                      ),
                      tooltip: l10n.homeScrollLeft,
                    ),
                  ),
                // Scrollable tabs list
                Expanded(
                  child: ListView(
                    controller: _taskTabsScrollController,
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    children: <Widget>[
                      // Home tab (pinned, non-closable)
                      GestureDetector(
                        onTap: () => notifier
                            .setActive(''), // use empty to represent home
                        child: Container(
                          margin: const EdgeInsets.only(right: 6),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 6,
                          ), // Reduced from 8 to 6
                          decoration: BoxDecoration(
                            color: tasks.activeTaskId == null ||
                                    tasks.activeTaskId == ''
                                ? Theme.of(context).colorScheme.primaryContainer
                                : Theme.of(context).colorScheme.surface,
                            border: Border(
                              bottom: BorderSide(
                                color: tasks.activeTaskId == null ||
                                        tasks.activeTaskId == ''
                                    ? Theme.of(context).colorScheme.primary
                                    : Colors.transparent,
                                width: 2,
                              ),
                            ),
                          ),
                          child: Row(
                            children: <Widget>[
                              Icon(
                                Icons.home,
                                size: 14, // Reduced from 16 to 14
                                color: (tasks.activeTaskId == null ||
                                        tasks.activeTaskId == '')
                                    ? Theme.of(context).colorScheme.primary
                                    : Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                l10n.homeTabHome,
                                style: TextStyle(
                                  fontSize: 13, // Added explicit font size
                                  color: (tasks.activeTaskId == null ||
                                          tasks.activeTaskId == '')
                                      ? Theme.of(context)
                                          .colorScheme
                                          .onPrimaryContainer
                                      : Theme.of(context).colorScheme.onSurface,
                                  fontWeight: (tasks.activeTaskId == null ||
                                          tasks.activeTaskId == '')
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      // Task tabs
                      ...tasks.tasks.map((t) {
                        final isActive = t.id == tasks.activeTaskId;
                        return GestureDetector(
                          onTap: () => notifier.setActive(t.id),
                          onDoubleTap: () => _startEditing(t.id, t.title),
                          child: Container(
                            margin: const EdgeInsets.only(right: 6),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 6, // Reduced from 8 to 6
                            ),
                            decoration: BoxDecoration(
                              color: isActive
                                  ? Theme.of(context)
                                      .colorScheme
                                      .primaryContainer
                                  : Theme.of(context).colorScheme.surface,
                              border: Border(
                                bottom: BorderSide(
                                  color: isActive
                                      ? Theme.of(context).colorScheme.primary
                                      : Colors.transparent,
                                  width: 2,
                                ),
                              ),
                            ),
                            child: Row(
                              children: <Widget>[
                                Icon(
                                  t.type == TaskType.file
                                      ? Icons.description
                                      : Icons.notes,
                                  size: 14, // Reduced from 16 to 14
                                  color: isActive
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context)
                                          .colorScheme
                                          .onSurfaceVariant,
                                ),
                                const SizedBox(width: 6),
                                if (_editingTaskId == t.id)
                                  SizedBox(
                                    width: 180,
                                    height: 28,
                                    child: TextField(
                                      controller: _titleController,
                                      autofocus: true,
                                      onSubmitted: (_) =>
                                          _finishEditing(notifier, t.id),
                                      onTapOutside: (_) =>
                                          _finishEditing(notifier, t.id),
                                      decoration: const InputDecoration(
                                        isDense: true,
                                        contentPadding: EdgeInsets.symmetric(
                                          vertical: 4,
                                          horizontal: 8,
                                        ),
                                        border: OutlineInputBorder(),
                                      ),
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: isActive
                                            ? Theme.of(context)
                                                .colorScheme
                                                .onPrimaryContainer
                                            : Theme.of(context)
                                                .colorScheme
                                                .onSurface,
                                        fontWeight: isActive
                                            ? FontWeight.w600
                                            : FontWeight.w400,
                                      ),
                                    ),
                                  )
                                else
                                  Text(
                                    t.title,
                                    style: TextStyle(
                                      fontSize: 13, // Added explicit font size
                                      color: isActive
                                          ? Theme.of(context)
                                              .colorScheme
                                              .onPrimaryContainer
                                          : Theme.of(context)
                                              .colorScheme
                                              .onSurface,
                                      fontWeight: isActive
                                          ? FontWeight.w600
                                          : FontWeight.w400,
                                    ),
                                  ),
                                const SizedBox(width: 8),
                                GestureDetector(
                                  onTap: () async =>
                                      _confirmCloseFlow(t.id),
                                  child: Icon(
                                    Icons.close,
                                    size: 14,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
                // Right scroll button
                if (_canScrollRight)
                  Container(
                    width: 32,
                    height: 32, // Fixed height at 32px for Tab Title
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: IconButton(
                      icon: const Icon(
                        Icons.chevron_right,
                        size: 18,
                      ), // Reduced from 20 to 18
                      onPressed: _scrollTabsRight,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 28, // Reduced from 32 to 28
                      ),
                      tooltip: l10n.homeScrollRight,
                    ),
                  ),
              ],
            ),
          ),
          // Content placeholder (pipeline view). Defer HomeScreen to next frame
          // so that context.go(homeRoute) paints the workspace shell immediately.
          Expanded(
            child: (tasks.activeTaskId == null || tasks.activeTaskId == '')
                ? _buildHomeTabContent()
                : Row(
                    children: <Widget>[
                      // Unified left column: Flows (top) + Pipeline (bottom)
                      SizedBox(
                        width: 68,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.surface,
                            border: Border(
                              right: BorderSide(
                                color: Theme.of(context).dividerColor,
                              ),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: <Widget>[
                              const Padding(
                                padding: EdgeInsets.symmetric(
                                  horizontal: 4,
                                  vertical: 12,
                                ),
                                child: _FlowSwitcher(),
                              ),
                              Divider(
                                height: 1,
                                color: Theme.of(context).dividerColor,
                              ),
                              Expanded(
                                child: _PipelineList(),
                              ),
                            ],
                          ),
                        ),
                      ),
                      // Phase content: use existing TranslationScreen as Translate phase (temporary)
                      const Expanded(child: _PhaseContent()),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  /// Home tab body: defer HomeScreen to next frame so first paint is fast.
  Widget _buildHomeTabContent() {
    if (_homeContentReady) {
      return const HomeScreen();
    }
    if (!_homeDeferScheduled) {
      _homeDeferScheduled = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          setState(() {
            _homeContentReady = true;
          });
        }
      });
    }
    return const Center(
      child: SizedBox(
        width: 32,
        height: 32,
        child: CircularProgressIndicator(strokeWidth: 2),
      ),
    );
  }

  /// Build 728×90px ad banner for toolbar
  Widget _buildAdBanner728x90() => LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          // Calculate responsive width
          final availableWidth = constraints.maxWidth;
          // Desktop: 728×90px, Mobile: 320×50px
          final adWidth = availableWidth > 768 ? 728 : 320;
          final adHeight = availableWidth > 768 ? 90 : 50;
          final l10n = AppLocalizations.of(context)!;
          return SizedBox(
            width: adWidth.clamp(0, availableWidth).toDouble(),
            height: adHeight.toDouble(),
            child: AdPlaceholder(
              width: adWidth.clamp(0, availableWidth).toDouble(),
              height: adHeight.toDouble(),
              label: l10n.homeToolbarAdBanner,
              // Use null for initial random pose, then use seed after first flow creation
              poseSeed: _bannerOwlPoseSeed > 0 ? _bannerOwlPoseSeed : null,
              onVisibilityChanged: (isVisible) {
                setState(() {
                  _isAdBannerVisible = isVisible;
                });
              },
            ),
          );
        },
      );

  /// Build action button matching Quick Start style (Card + InkWell)
  Widget _buildActionButton({
    required IconData icon,
    required String label,
    Key? key,
    VoidCallback? onPressed,
    double? width,
    bool highlight = false,
    int maxLabelLines = 1,
    double? height,
  }) {
    // Use uniform height for all action buttons regardless of label line count
    final double boxHeight = height ?? 76;
    return Card(
      elevation: highlight ? 4 : 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(4),
        side: highlight
            ? BorderSide(color: Colors.orange.shade400, width: 2)
            : const BorderSide(color: Colors.transparent, width: 0),
      ),
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(4),
        child: Container(
          key: key,
          width: width ?? 70,
          height: boxHeight,
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(
                icon,
                color: Theme.of(context).colorScheme.primary,
                size: 28,
              ),
              const SizedBox(height: 3),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  height: maxLabelLines > 1 ? 1.15 : null,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
                softWrap: true,
                maxLines: maxLabelLines,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// GitHub star count button displayed in the home page toolbar.
/// Fetches the star count from the GitHub API on init.
class _GitHubStarButton extends StatefulWidget {
  const _GitHubStarButton();

  @override
  State<_GitHubStarButton> createState() => _GitHubStarButtonState();
}

class _GitHubStarButtonState extends State<_GitHubStarButton> {
  int? _starCount;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _fetchStars();
  }

  Future<void> _fetchStars() async {
    try {
      final response = await Dio().get(
        'https://api.github.com/repos/zampher/Owlangs',
        options: Options(headers: {'Accept': 'application/vnd.github.v3+json'}),
      );
      if (response.statusCode == 200) {
        final data = response.data is Map ? response.data as Map : {};
        final count = data['stargazers_count'];
        if (mounted) {
          setState(() {
            _starCount = count is int ? count : 0;
            _loading = false;
          });
        }
      } else {
        if (mounted) setState(() => _loading = false);
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatCount(int count) {
    if (count >= 1000) {
      return '${(count / 1000).toStringAsFixed(1)}k';
    }
    return count.toString();
  }

  @override
  Widget build(BuildContext context) {
    final String label;
    if (_loading) {
      label = '...';
    } else if (_starCount != null) {
      label = '★ ${_formatCount(_starCount!)} Github';
    } else {
      label = 'GitHub';
    }
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(4),
      ),
      child: InkWell(
        onTap: () async {
          await launchUrl(
            Uri.parse('https://github.com/zampher/Owlangs'),
            mode: LaunchMode.externalApplication,
          );
        },
        borderRadius: BorderRadius.circular(4),
        child: Container(
          width: 80,
          height: 70,
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(
                MdiIcons.github,
                color: Theme.of(context).colorScheme.primary,
                size: 32,
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Deprecated placeholder tile removed in favor of _SelectablePhase

class _PipelineList extends ConsumerStatefulWidget {
  @override
  ConsumerState<_PipelineList> createState() => _PipelineListState();
}

class _PipelineListState extends ConsumerState<_PipelineList> {
  PersistedStepsState? _stepsState;
  String? _lastTaskId;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _loadStepsState();
      }
    });
    // Periodically refresh steps state (every 3 seconds - reduced frequency for better performance)
    _refreshTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (mounted) {
        _loadStepsState();
      }
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadStepsState() async {
    // CRITICAL: Check mounted before accessing ref to prevent "Looking up a deactivated widget's ancestor" error
    if (!mounted) {
      return;
    }

    final state = ref.read(tasksProvider);
    final active = state.activeTask;
    if (active == null) {
      if (_stepsState != null && mounted) {
        setState(() {
          _stepsState = null;
          _lastTaskId = null;
        });
      }
      return;
    }

    // Reload if task changed or periodically refresh
    if (active.id != _lastTaskId) {
      _lastTaskId = active.id;
    }

    // Use cache to avoid repeated SharedPreferences reads
    final cache = FlowDataCache();
    final stepsState = await cache.getStepsState(active.id);

    // CRITICAL: Check mounted again after async operation
    if (!mounted) {
      return;
    }

    // CRITICAL: Check if task hasn't changed during async operation
    // Re-read tasksProvider to get current state
    final currentState = ref.read(tasksProvider);
    final currentActive = currentState.activeTask;
    if (currentActive?.id == _lastTaskId) {
      // Only update if task hasn't changed during async operation
      setState(() {
        _stepsState = stepsState;
      });
    }
  }

  // Map PipelinePhase to step completion status
  _StepStatus _getStepStatus(
    PipelinePhase phase,
    PersistedStepsState? stepsState,
    PipelinePhase? currentPhase,
  ) {
    if (stepsState == null) {
      // No state available, show based on current phase
      return currentPhase == phase ? _StepStatus.active : _StepStatus.pending;
    }

    switch (phase) {
      case PipelinePhase.importPhase:
        return stepsState.uploadCompleted
            ? _StepStatus.completed
            : (currentPhase == phase
                ? _StepStatus.active
                : _StepStatus.pending);
      case PipelinePhase.glossary:
        // For Translate flow, glossary phase might represent Extract
        // Check if we're in Translate flow and glossary is Extract
        if (stepsState.extractCompleted &&
            !stepsState.glossaryCompleted &&
            !stepsState.glossarySkipped) {
          // This is Extract step
          return stepsState.extractCompleted
              ? _StepStatus.completed
              : (currentPhase == phase
                  ? _StepStatus.active
                  : _StepStatus.pending);
        }
        // This is Glossary step
        if (stepsState.glossarySkipped) {
          return _StepStatus.skipped;
        }
        return stepsState.glossaryCompleted
            ? _StepStatus.completed
            : (currentPhase == phase
                ? _StepStatus.active
                : _StepStatus.pending);
      case PipelinePhase.translate:
        return stepsState.translateCompleted
            ? _StepStatus.completed
            : (currentPhase == phase
                ? _StepStatus.active
                : _StepStatus.pending);
      case PipelinePhase.review:
        // Review is completed if translate is completed (for Translate flow)
        // For Anonymize flow, Review is completed if anonymize is completed
        // We check if we're in Anonymize flow by checking if anonymize phase exists
        if (stepsState.translateCompleted) {
          return _StepStatus.completed;
        }
        // For Anonymize flow, Review is completed when anonymize is completed
        // We'll use a heuristic: if we have anonymized text, consider review as accessible
        return currentPhase == phase ? _StepStatus.active : _StepStatus.pending;
      case PipelinePhase.anonymize:
        return stepsState.anonymizeCompleted
            ? _StepStatus.completed
            : (currentPhase == phase
                ? _StepStatus.active
                : _StepStatus.pending);
      case PipelinePhase.deAnonymize:
        return stepsState.deAnonymizeCompleted
            ? _StepStatus.completed
            : (currentPhase == phase
                ? _StepStatus.active
                : _StepStatus.pending);
      default:
        return currentPhase == phase ? _StepStatus.active : _StepStatus.pending;
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tasksProvider);
    final active = state.activeTask;
    final l10n = AppLocalizations.of(context)!;

    // Reload steps state when active task changes
    if (active != null && active.id != _lastTaskId) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _loadStepsState();
        }
      });
    }

    // Define display info for phases
    IconData iconFor(PipelinePhase p) {
      switch (p) {
        case PipelinePhase.importPhase:
          return Icons.file_open;
        case PipelinePhase.anonymize:
          return Icons.visibility_off;
        case PipelinePhase.glossary:
          return Icons.book;
        case PipelinePhase.translate:
          return Icons.translate;
        case PipelinePhase.review:
          return Icons.rate_review;
        case PipelinePhase.deAnonymize:
          return Icons.visibility;
        case PipelinePhase.exportPhase:
          return Icons.download;
      }
    }

    String titleFor(PipelinePhase p) {
      switch (p) {
        case PipelinePhase.importPhase:
          return l10n.homePhaseUpload;
        case PipelinePhase.anonymize:
          return l10n.homePhaseAnonymize;
        case PipelinePhase.glossary:
          return l10n.homePhaseGlossary;
        case PipelinePhase.translate:
          return l10n.homePhaseTranslate;
        case PipelinePhase.review:
          return l10n.homePhaseViewer;
        case PipelinePhase.deAnonymize:
          return l10n.homePhaseDeAnonymize;
        case PipelinePhase.exportPhase:
          return l10n.homePhaseExport;
      }
    }

    // Translate Flow -> show 5 steps explicitly
    if (active?.currentFlow == TaskFlow.translate) {
      final items = <Widget>[];
      // Upload
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.importPhase),
          title: l10n.homePhaseUpload,
          status: _stepsState?.uploadCompleted ?? false
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.importPhase
                  ? _StepStatus.active
                  : _StepStatus.pending),
        ),
      );
      // Extract (synthetic)
      final extractStatus = _stepsState == null
          ? _StepStatus.pending
          : (_stepsState!.extractCompleted
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.glossary &&
                      _stepsState!.extractCompleted == false
                  ? _StepStatus.active
                  : _StepStatus.pending));
      items.add(
        _StepStatusWidget(
          icon: Icons.segment,
          title: l10n.homePhaseExtract,
          status: extractStatus,
        ),
      );
      // Glossary
      final glossaryStatus = (_stepsState?.glossarySkipped ?? false)
          ? _StepStatus.skipped
          : ((_stepsState?.glossaryCompleted ?? false)
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.glossary
                  ? _StepStatus.active
                  : _StepStatus.pending));
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.glossary),
          title: l10n.homePhaseGlossary,
          status: glossaryStatus,
        ),
      );
      // Translate
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.translate),
          title: l10n.homePhaseTranslate,
          status: (_stepsState?.translateCompleted ?? false)
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.translate
                  ? _StepStatus.active
                  : _StepStatus.pending),
        ),
      );
      // Viewer
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.review),
          title: l10n.homePhaseViewer,
          status: (_stepsState?.translateCompleted ?? false)
              ? _StepStatus.completed
              : _StepStatus.pending,
        ),
      );

      return ListView(children: items);
    }

    // Anonymize Flow -> show 3 steps explicitly
    if (active?.currentFlow == TaskFlow.anonymize) {
      final items = <Widget>[];
      // Upload
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.importPhase),
          title: l10n.homePhaseUpload,
          status: _stepsState?.uploadCompleted ?? false
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.importPhase
                  ? _StepStatus.active
                  : _StepStatus.pending),
        ),
      );
      // Anonymize
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.anonymize),
          title: l10n.homePhaseAnonymize,
          status: _getStepStatus(
            PipelinePhase.anonymize,
            _stepsState,
            active?.currentPhase,
          ),
        ),
      );
      // De-anonymize
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.deAnonymize),
          title: l10n.homePhaseDeAnonymize,
          status: _getStepStatus(
            PipelinePhase.deAnonymize,
            _stepsState,
            active?.currentPhase,
          ),
        ),
      );

      return ListView(children: items);
    }

    // Anonymize+Translate Flow -> show 7 steps explicitly (with Extract)
    if (active?.currentFlow == TaskFlow.anonymizeAndTranslate) {
      final items = <Widget>[];
      // Upload
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.importPhase),
          title: l10n.homePhaseUpload,
          status: _stepsState?.uploadCompleted ?? false
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.importPhase
                  ? _StepStatus.active
                  : _StepStatus.pending),
        ),
      );
      // Extract (synthetic)
      final extractStatus = _stepsState == null
          ? _StepStatus.pending
          : (_stepsState!.extractCompleted
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.anonymize &&
                      _stepsState!.extractCompleted == false
                  ? _StepStatus.active
                  : _StepStatus.pending));
      items.add(
        _StepStatusWidget(
          icon: Icons.segment,
          title: l10n.homePhaseExtract,
          status: extractStatus,
        ),
      );
      // Anonymize
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.anonymize),
          title: l10n.homePhaseAnonymize,
          status: _getStepStatus(
            PipelinePhase.anonymize,
            _stepsState,
            active?.currentPhase,
          ),
        ),
      );
      // Glossary
      final glossaryStatus = (_stepsState?.glossarySkipped ?? false)
          ? _StepStatus.skipped
          : ((_stepsState?.glossaryCompleted ?? false)
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.glossary
                  ? _StepStatus.active
                  : _StepStatus.pending));
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.glossary),
          title: l10n.homePhaseGlossary,
          status: glossaryStatus,
        ),
      );
      // Translate
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.translate),
          title: l10n.homePhaseTranslate,
          status: (_stepsState?.translateCompleted ?? false)
              ? _StepStatus.completed
              : (active?.currentPhase == PipelinePhase.translate
                  ? _StepStatus.active
                  : _StepStatus.pending),
        ),
      );
      // Viewer
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.review),
          title: l10n.homePhaseViewer,
          status: (_stepsState?.translateCompleted ?? false)
              ? _StepStatus.completed
              : _StepStatus.pending,
        ),
      );
      // De-anonymize
      items.add(
        _StepStatusWidget(
          icon: iconFor(PipelinePhase.deAnonymize),
          title: l10n.homePhaseDeAnonymize,
          status: _getStepStatus(
            PipelinePhase.deAnonymize,
            _stepsState,
            active?.currentPhase,
          ),
        ),
      );

      return ListView(children: items);
    }

    // Build phase list from current flow's planned phases
    final List<PipelinePhase> planned =
        (active?.plannedPhases.isNotEmpty ?? false)
            ? active!.plannedPhases
            : <PipelinePhase>[
                // Fallback (should rarely be used): show a minimal helpful list
                PipelinePhase.importPhase,
                PipelinePhase.glossary,
                PipelinePhase.translate,
                PipelinePhase.review,
              ];

    return ListView(
      children: planned.map((p) {
        final stepStatus = _getStepStatus(p, _stepsState, active?.currentPhase);
        return GestureDetector(
          onTap: () {
            // Allow switching to any phase (completed or active)
            // User can navigate between phases freely
            if (active != null) {
              final tasksNotifier = ref.read(tasksProvider.notifier);
              tasksNotifier.setPhase(active.id, p);
            }
          },
          child: _StepStatusWidget(
            icon: iconFor(p),
            title: titleFor(p),
            status: stepStatus,
          ),
        );
      }).toList(),
    );
  }
}

enum _StepStatus {
  pending, // Not started (gray)
  active, // Currently active (blue)
  completed, // Completed (green)
  skipped, // Skipped (orange)
}

class _StepStatusWidget extends StatelessWidget {
  const _StepStatusWidget({
    required this.icon,
    required this.title,
    required this.status,
  });
  final IconData icon;
  final String title;
  final _StepStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    Color iconColor;
    Color bgColor;
    Color borderColor;

    switch (status) {
      case _StepStatus.completed:
        iconColor = isDark ? Colors.green.shade300 : Colors.green.shade700;
        bgColor = isDark
            ? Colors.green.shade900.withOpacity(0.3)
            : Colors.green.shade50;
        borderColor = Colors.green;
        break;
      case _StepStatus.active:
        iconColor = theme.colorScheme.primary;
        bgColor = theme.colorScheme.primaryContainer;
        borderColor = theme.colorScheme.primary;
        break;
      case _StepStatus.skipped:
        iconColor = isDark ? Colors.orange.shade300 : Colors.orange.shade700;
        bgColor = isDark
            ? Colors.orange.shade900.withOpacity(0.3)
            : Colors.orange.shade50;
        borderColor = Colors.orange;
        break;
      case _StepStatus.pending:
        iconColor = theme.colorScheme.onSurfaceVariant;
        bgColor = Colors.transparent;
        borderColor = theme.dividerColor.withOpacity(0.3);
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
      decoration: BoxDecoration(
        color: bgColor,
        border: Border(
          left: BorderSide(
            color: borderColor,
            width: 1.5,
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(
            icon,
            size: 16,
            color: iconColor,
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: TextStyle(
              fontSize: 11,
              color: iconColor,
              fontWeight: status == _StepStatus.active ||
                      status == _StepStatus.completed
                  ? FontWeight.w600
                  : FontWeight.w400,
            ),
            textAlign: TextAlign.center,
            softWrap: false,
            overflow: TextOverflow.visible,
          ),
        ],
      ),
    );
  }
}

class _PhaseContent extends ConsumerStatefulWidget {
  const _PhaseContent();
  @override
  ConsumerState<_PhaseContent> createState() => _PhaseContentState();
}

class _PhaseContentState extends ConsumerState<_PhaseContent> {
  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tasksProvider);
    final active = state.activeTask;
    if (active == null) {
      return const SizedBox.shrink();
    }

    // Check if we're in deAnonymize phase - show DeAnonymizeScreen regardless of flow type
    if (active.currentPhase == PipelinePhase.deAnonymize) {
      return ProviderScope(
        key: ValueKey('task-scope-${active.id}'),
        child: DeAnonymizeScreen(flowId: active.id),
      );
    }

    // Determine which screen to show based on flow type
    switch (active.currentFlow) {
      case TaskFlow.translate:
        // Translate flow: always use TranslationScreen
        return ProviderScope(
          key: ValueKey('task-scope-${active.id}'),
          child: TranslationScreen(flowId: active.id),
        );
      case TaskFlow.anonymize:
        // Anonymize flow: use AnonymizeScreen
        return ProviderScope(
          key: ValueKey('task-scope-${active.id}'),
          child: AnonymizeScreen(flowId: active.id),
        );
      case TaskFlow.anonymizeAndTranslate:
        // Anonymize+Translate flow: use AnonymizeAndTranslateScreen
        return ProviderScope(
          key: ValueKey('task-scope-${active.id}'),
          child: AnonymizeAndTranslateScreen(flowId: active.id),
        );
    }
  }
}

class _FlowSwitcher extends ConsumerStatefulWidget {
  const _FlowSwitcher();

  @override
  ConsumerState<_FlowSwitcher> createState() => _FlowSwitcherState();
}

class _FlowSwitcherState extends ConsumerState<_FlowSwitcher> {
  @override
  Widget build(BuildContext context) {
    // Flow type selection moved to AppBar; Flow switcher buttons removed.
    final l10n = AppLocalizations.of(context)!;
    return Column(
      children: <Widget>[
        Text(
          l10n.homeSteps,
          style: TextStyle(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
}
