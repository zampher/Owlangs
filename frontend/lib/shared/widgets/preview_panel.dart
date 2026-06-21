// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../features/translation/providers/preview_tabs_provider.dart';
import '../../../features/translation/models/preview_tab.dart';
import '../../l10n/app_localizations.dart';

/// Preview panel widget that displays tabs with content
class PreviewPanel extends ConsumerStatefulWidget {
  const PreviewPanel({
    super.key,
    this.flowId,
    this.emptyState,
    this.onTabClose,
    this.onTabCloseConfirm,
  });
  final String? flowId;
  final Widget? emptyState;
  final void Function(PreviewTab)? onTabClose;

  /// When closing a tab, return `false` to cancel closing (e.g. unsaved warning).
  final Future<bool> Function(PreviewTab)? onTabCloseConfirm;

  @override
  ConsumerState<PreviewPanel> createState() => _PreviewPanelState();
}

class _PreviewPanelState extends ConsumerState<PreviewPanel> {
  final ScrollController _scrollController = ScrollController();
  bool _canScrollLeft = false;
  bool _canScrollRight = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_updateScrollButtons);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_updateScrollButtons);
    _scrollController.dispose();
    super.dispose();
  }

  void _updateScrollButtons() {
    if (!_scrollController.hasClients) {
      return;
    }

    final canScrollLeft = _scrollController.position.pixels > 0;
    final canScrollRight = _scrollController.position.pixels <
        _scrollController.position.maxScrollExtent;

    if (canScrollLeft != _canScrollLeft || canScrollRight != _canScrollRight) {
      if (mounted) {
        setState(() {
          _canScrollLeft = canScrollLeft;
          _canScrollRight = canScrollRight;
        });
      }
    }
  }

  void _scrollLeft() {
    final currentPosition = _scrollController.position.pixels;
    const scrollAmount = 200; // Scroll 200 pixels at a time
    final newPosition = (currentPosition - scrollAmount).clamp(
      0.0,
      _scrollController.position.maxScrollExtent,
    );
    _scrollController.animateTo(
      newPosition,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
    );
  }

  void _scrollRight() {
    final currentPosition = _scrollController.position.pixels;
    const scrollAmount = 200; // Scroll 200 pixels at a time
    final newPosition = (currentPosition + scrollAmount).clamp(
      0.0,
      _scrollController.position.maxScrollExtent,
    );
    _scrollController.animateTo(
      newPosition,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
    );
  }

  void _scrollToActiveTab(int activeIndex, int totalTabs) {
    // Wait for the next frame to ensure layout is complete
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;

      // Calculate approximate position of active tab
      // Each tab is approximately 120 pixels wide (icon + text + padding + close button)
      const int estimatedTabWidth = 120;
      final int targetPosition = activeIndex * estimatedTabWidth;
      final double viewportWidth = _scrollController.position.viewportDimension;
      final double currentPosition = _scrollController.position.pixels;

      // Check if active tab is outside viewport
      if (targetPosition < currentPosition) {
        // Tab is to the left of viewport, scroll to show it
        _scrollController.animateTo(
          targetPosition.toDouble(),
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      } else if (targetPosition + estimatedTabWidth >
          currentPosition + viewportWidth) {
        // Tab is to the right of viewport, scroll to show it
        _scrollController.animateTo(
          (targetPosition + estimatedTabWidth - viewportWidth).toDouble(),
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);
    final tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    // Update scroll buttons when tabs change
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _updateScrollButtons();
      // Auto-scroll to active tab when it changes
      if (tabsState.tabs.isNotEmpty) {
        _scrollToActiveTab(tabsState.activeTabIndex, tabsState.tabs.length);
      }
    });

    if (tabsState.tabs.isEmpty) {
      final empty = widget.emptyState;
      if (empty == null) return const SizedBox.shrink();
      // Fill parent so the business panel (file upload / text input) uses full area
      return SizedBox.expand(child: empty);
    }

    // Fill parent and resize with parent so tab content uses all available space
    return SizedBox.expand(
      child: FocusableActionDetector(
      shortcuts: <ShortcutActivator, Intent>{
        LogicalKeySet(LogicalKeyboardKey.arrowLeft): const _ScrollLeftIntent(),
        LogicalKeySet(LogicalKeyboardKey.arrowRight):
            const _ScrollRightIntent(),
      },
      actions: <Type, Action<Intent>>{
        _ScrollLeftIntent: CallbackAction<_ScrollLeftIntent>(
          onInvoke: (_) {
            if (_canScrollLeft) {
              _scrollLeft();
            }
            return null;
          },
        ),
        _ScrollRightIntent: CallbackAction<_ScrollRightIntent>(
          onInvoke: (_) {
            if (_canScrollRight) {
              _scrollRight();
            }
            return null;
          },
        ),
      },
      child: Card(
        elevation: 4,
        margin:
            EdgeInsets.zero, // Remove default margin to fill available space
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            // Tab Bar with close buttons and scroll controls
            DecoratedBox(
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Theme.of(context).dividerColor),
                ),
              ),
              child: Row(
                children: <Widget>[
                  // Left scroll button
                  if (_canScrollLeft || _canScrollRight)
                    IconButton(
                      icon: const Icon(
                        Icons.chevron_left,
                        size: 18,
                      ), // Reduced from 20 to 18
                      tooltip: 'Scroll tabs left (or press Left Arrow)',
                      onPressed: _canScrollLeft ? _scrollLeft : null,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32, // Reduced from 40 to 32
                      ),
                    ),
                  Expanded(
                    child: SingleChildScrollView(
                      controller: _scrollController,
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: <Widget>[
                          for (int i = 0; i < tabsState.tabs.length; i++)
                            Builder(
                              builder: (context) {
                                final tab = tabsState.tabs[i];
                                return _PreviewTab(
                                  tab: tab,
                                  isActive: i == tabsState.activeTabIndex,
                                  onTap: () => tabsNotifier.switchToTab(i),
                                  onClose: () async {
                                    if (widget.onTabCloseConfirm != null) {
                                      final bool proceed =
                                          await widget.onTabCloseConfirm!(tab);
                                      if (!proceed) {
                                        return;
                                      }
                                    }
                                    widget.onTabClose?.call(tab);
                                    tabsNotifier.closeTab(i);
                                  },
                                );
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                  // Right scroll button
                  if (_canScrollLeft || _canScrollRight)
                    IconButton(
                      icon: const Icon(
                        Icons.chevron_right,
                        size: 18,
                      ), // Reduced from 20 to 18
                      tooltip: 'Scroll tabs right (or press Right Arrow)',
                      onPressed: _canScrollRight ? _scrollRight : null,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32, // Reduced from 40 to 32
                      ),
                    ),
                ],
              ),
            ),
            // Tab Content: wrap each tab in SizedBox.expand so content fills parent width
            Expanded(
              child: IndexedStack(
                index: tabsState.activeTabIndex
                    .clamp(0, tabsState.tabs.length - 1),
                children: tabsState.tabs
                    .map<Widget>(
                      (PreviewTab tab) => SizedBox.expand(
                        key: ValueKey<String>('preview_tab_panel_${tab.id}'),
                        child: tab.content,
                      ),
                    )
                    .toList(),
              ),
            ),
          ],
        ),
      ),
    ),
    );
  }
}

/// Intent classes for keyboard shortcuts
class _ScrollLeftIntent extends Intent {
  const _ScrollLeftIntent();
}

class _ScrollRightIntent extends Intent {
  const _ScrollRightIntent();
}

/// Individual preview tab widget
class _PreviewTab extends StatelessWidget {
  const _PreviewTab({
    required this.tab,
    required this.isActive,
    required this.onTap,
    required this.onClose,
  });
  final PreviewTab tab;
  final bool isActive;
  final VoidCallback onTap;
  final VoidCallback onClose;

  String _resolveTitle(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    if (tab.id == 'extract_tab') return l10n.homePhaseExtract;
    if (tab.id == 'translate_tab') return l10n.homePhaseTranslate;
    if (tab.id == 'glossary_tab') return l10n.homePhaseGlossary;
    return tab.title;
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(
            minHeight: 32,
            maxHeight: 32,
          ), // Fixed height at 32px for Tab Title
          padding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 6,
          ), // Reduced from 8 to 6
          decoration: BoxDecoration(
            color: isActive
                ? Theme.of(context).colorScheme.primaryContainer
                : Colors.transparent,
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
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(
                tab.icon ?? tab.defaultIcon,
                size: 14, // Reduced from 16 to 14
                color: isActive
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 6),
              Text(
                _resolveTitle(context),
                style: TextStyle(
                  fontSize: 12, // Reduced from 13 to 12
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                  color: isActive
                      ? Theme.of(context).colorScheme.onPrimaryContainer
                      : Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(width: 6),
              MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: onClose,
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Icon(
                      Icons.close,
                      size: 14, // Reduced from 16 to 14
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
}
