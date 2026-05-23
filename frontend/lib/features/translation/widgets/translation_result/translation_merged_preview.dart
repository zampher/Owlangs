// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';

/// Clean-mode preview panel showing source/target text side by side
/// without segment labels/numbers or action buttons.
class TranslationMergedPreviewPanel extends StatefulWidget {
  const TranslationMergedPreviewPanel({
    required this.sourceParagraphs,
    required this.targetParagraphs,
    required this.scrollController,
    required this.highlightedIndexNotifier,
    required this.onHighlightParagraph,
    this.onEdit,
    this.onEditingStarted,
    this.previewFontSize = 14.0,
    super.key,
  });

  final List<String> sourceParagraphs;
  final List<String> targetParagraphs;
  final ScrollController scrollController;
  final double previewFontSize;
  final ValueNotifier<int?> highlightedIndexNotifier;
  final void Function(int) onHighlightParagraph;
  final Future<void> Function(int index, String newText)? onEdit;
  final void Function(int index)? onEditingStarted;

  @override
  State<TranslationMergedPreviewPanel> createState() =>
      _TranslationMergedPreviewPanelState();
}

class _TranslationMergedPreviewPanelState
    extends State<TranslationMergedPreviewPanel> {
  final Map<int, GlobalKey> _itemKeys = <int, GlobalKey>{};

  int? _editingIndex;
  TextEditingController? _editController;
  FocusNode? _editFocusNode;
  String _originalText = '';

  @override
  void initState() {
    super.initState();
    widget.highlightedIndexNotifier.addListener(_onHighlightChanged);
    // If a segment is already highlighted when this widget mounts
    // (e.g. after mode toggle), schedule a scroll to it.
    if (widget.highlightedIndexNotifier.value != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _scrollToHighlighted(widget.highlightedIndexNotifier.value!);
        }
      });
    }
  }

  @override
  void dispose() {
    widget.highlightedIndexNotifier.removeListener(_onHighlightChanged);
    _editController?.dispose();
    _editFocusNode?.dispose();
    super.dispose();
  }

  void _startEditing(int index) {
    if (widget.onEdit == null || index >= widget.targetParagraphs.length) {
      return;
    }
    // Set editing state FIRST so that _onHighlightChanged (triggered by
    // onEditingStarted's notifier update) sees _editingIndex==index and
    // skips the scroll, preventing viewport jump.
    setState(() {
      _editingIndex = index;
      _originalText = widget.targetParagraphs[index];
      _editController?.dispose();
      _editController = TextEditingController(text: _originalText);
      _editFocusNode?.dispose();
      _editFocusNode = FocusNode(debugLabel: 'merged_edit_$index');
    });
    widget.onEditingStarted?.call(index);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _editingIndex == index) {
        _editFocusNode?.requestFocus();
      }
    });
  }

  void _cancelEditing() {
    setState(() {
      _editingIndex = null;
      _editController?.dispose();
      _editController = null;
      _editFocusNode?.dispose();
      _editFocusNode = null;
    });
  }

  Future<void> _saveEditing() async {
    if (_editingIndex == null || _editController == null) return;
    final String newText = _editController!.text.trim();
    if (newText.isEmpty) return;
    if (newText == _originalText) {
      _cancelEditing();
      return;
    }
    final int index = _editingIndex!;
    try {
      await widget.onEdit!(index, newText);
      if (mounted) {
        setState(() {
          _editingIndex = null;
          _editController?.dispose();
          _editController = null;
          _editFocusNode?.dispose();
          _editFocusNode = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _editingIndex = null;
          _editController?.dispose();
          _editController = null;
          _editFocusNode?.dispose();
          _editFocusNode = null;
        });
      }
    }
  }

  void _onHighlightChanged() {
    if (!mounted) return;
    setState(() {});
    final int? index = widget.highlightedIndexNotifier.value;
    if (index == null) return;
    // Don't scroll when already editing this segment — the user just
    // clicked the edit button and the segment is already visible.
    // Scrolling would fight with the layout change (TextField expansion)
    // and push the segment out of the viewport.
    if (_editingIndex == index) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _scrollToHighlighted(index);
    });
  }

  void _scrollToHighlighted(int index) {
    final GlobalKey? key = _itemKeys[index];
    if (key == null) return;
    final BuildContext? itemContext = key.currentContext;
    if (itemContext == null) return;
    try {
      Scrollable.ensureVisible(
        itemContext,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        alignment: 0.1,
      );
    } catch (_) {
      // Scrollable not available yet — silently ignore.
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final ColorScheme scheme = theme.colorScheme;

    final int itemCount = widget.sourceParagraphs.length;

    if (itemCount == 0) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'No content available.',
            textAlign: TextAlign.center,
            style: TextStyle(color: scheme.onSurfaceVariant),
          ),
        ),
      );
    }

    Widget listView = Scrollbar(
      controller: widget.scrollController,
      thickness: 8,
      radius: const Radius.circular(4),
      thumbVisibility: true,
      child: ListView.builder(
        controller: widget.scrollController,
        padding: const EdgeInsets.all(12),
        itemCount: itemCount,
        addAutomaticKeepAlives: true,
        itemBuilder: (BuildContext context, int index) {
          final GlobalKey itemKey =
              _itemKeys.putIfAbsent(index, () => GlobalKey());
          final bool hasSource = index < widget.sourceParagraphs.length;
          final bool hasTarget = index < widget.targetParagraphs.length;
          final String sourceText =
              hasSource ? widget.sourceParagraphs[index] : '';
          final String targetText =
              hasTarget ? widget.targetParagraphs[index] : '';
          final TextStyle textStyle =
              TextStyle(fontSize: widget.previewFontSize);
          final bool isHighlighted =
              widget.highlightedIndexNotifier.value == index;

          final Color highlightBg = theme.brightness == Brightness.dark
              ? Colors.amber.shade900.withOpacity(0.15)
              : Colors.amber.shade50.withOpacity(0.4);
          final Color defaultBg = scheme.surfaceContainerLow;

          return Padding(
            key: itemKey,
            padding: const EdgeInsets.only(bottom: 1),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                // Source paragraph (left panel)
                Expanded(
                  child: Listener(
                    onPointerDown: (_) => widget.onHighlightParagraph(index),
                    // translucent + Listener bypasses the gesture arena so taps
                    // work even over SelectableText (which would otherwise win
                    // the arena and block GestureDetector.onTap).
                    behavior: HitTestBehavior.translucent,
                    child: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: isHighlighted ? highlightBg : defaultBg,
                        border: Border(
                          left: BorderSide(
                            color: isHighlighted
                                ? Colors.amber.shade400
                                : Colors.transparent,
                            width: 3,
                          ),
                          top: BorderSide(
                            color: theme.dividerColor.withOpacity(0.3),
                          ),
                        ),
                      ),
                      child: MarkdownTextWithImages(
                        text: sourceText,
                        style: textStyle,
                      ),
                    ),
                  ),
                ),
                // Segment ID in the gap between source and target
                SizedBox(
                  width: 24,
                  child: GestureDetector(
                    onTap: () => widget.onHighlightParagraph(index),
                    child: _editingIndex == index
                        ? Column(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              const SizedBox(height: 12),
                              Text(
                                '${index + 1}',
                                style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 12),
                            ],
                          )
                        : Column(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Container(
                                width: 1,
                                height: isHighlighted ? 6 : 12,
                                color: theme.dividerColor.withOpacity(0.2),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                '${index + 1}',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: isHighlighted
                                      ? Colors.amber.shade600
                                      : scheme.onSurfaceVariant.withOpacity(0.5),
                                  fontWeight: isHighlighted
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                ),
                              ),
                              if (isHighlighted) ...[
                                const SizedBox(height: 1),
                                _EditIconButton(
                                  onTap: () => _startEditing(index),
                                ),
                                const SizedBox(height: 1),
                              ] else
                                const SizedBox(height: 3),
                              Container(
                                width: 1,
                                height: isHighlighted ? 6 : 12,
                                color: theme.dividerColor.withOpacity(0.2),
                              ),
                            ],
                          ),
                  ),
                ),
                // Target paragraph (right panel)
                Expanded(
                  child: _editingIndex == index
                      ? Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: highlightBg,
                            border: Border(
                              left: BorderSide(
                                color: Colors.amber.shade400,
                                width: 3,
                              ),
                              bottom: BorderSide(
                                color: theme.dividerColor.withOpacity(0.3),
                              ),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              TextField(
                                controller: _editController,
                                focusNode: _editFocusNode,
                                maxLines: null,
                                keyboardType: TextInputType.multiline,
                                textInputAction: TextInputAction.newline,
                                style: TextStyle(
                                  fontSize: widget.previewFontSize,
                                ),
                                decoration: const InputDecoration(
                                  border: OutlineInputBorder(),
                                  contentPadding: EdgeInsets.all(8),
                                  isDense: true,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.end,
                                children: <Widget>[
                                  TextButton(
                                    onPressed: _cancelEditing,
                                    style: TextButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 2,
                                      ),
                                      minimumSize: Size.zero,
                                      tapTargetSize:
                                          MaterialTapTargetSize.shrinkWrap,
                                    ),
                                    child: Text(
                                      'Cancel',
                                      style: TextStyle(fontSize: 11),
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  TextButton(
                                    onPressed: _saveEditing,
                                    style: TextButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 2,
                                      ),
                                      minimumSize: Size.zero,
                                      tapTargetSize:
                                          MaterialTapTargetSize.shrinkWrap,
                                    ),
                                    child: Text(
                                      'Save',
                                      style: TextStyle(fontSize: 11),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        )
                      : GestureDetector(
                          onDoubleTap: widget.onEdit != null
                              ? () => _startEditing(index)
                              : null,
                          child: Listener(
                            onPointerDown: (_) =>
                                widget.onHighlightParagraph(index),
                            behavior: HitTestBehavior.translucent,
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: isHighlighted ? highlightBg : defaultBg,
                                border: Border(
                                  left: BorderSide(
                                    color: isHighlighted
                                        ? Colors.amber.shade400
                                        : Colors.transparent,
                                    width: 3,
                                  ),
                                  bottom: BorderSide(
                                    color: theme.dividerColor.withOpacity(0.3),
                                  ),
                                ),
                              ),
                              child: MarkdownTextWithImages(
                                text: targetText,
                                style: textStyle,
                              ),
                            ),
                          ),
                        ),
                ),
              ],
            ),
          );
        },
      ),
    );

    // Only activate keyboard shortcuts when editing — avoids focus/keyboard
    // interference with dialogs (e.g. save-and-close confirmation dialog).
    if (_editingIndex != null) {
      listView = CallbackShortcuts(
        bindings: <ShortcutActivator, VoidCallback>{
          SingleActivator(LogicalKeyboardKey.escape): _cancelEditing,
          SingleActivator(LogicalKeyboardKey.enter, control: true):
              _saveEditing,
        },
        child: Focus(
          autofocus: false,
          child: listView,
        ),
      );
    }

    return listView;
  }
}

/// Small edit icon button used in the segment divider when highlighted.
class _EditIconButton extends StatelessWidget {
  const _EditIconButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(1),
        child: Icon(
          Icons.edit_outlined,
          size: 12,
          color: Colors.amber.shade600,
        ),
      ),
    );
  }
}
