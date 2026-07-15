// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/scheduler.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';
import '../../models/exclusion_reason.dart';
import '../common/exclusion_reason_editor.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/message_service.dart';

/// Reusable numbered segment item widget with hover, click, and highlight support
/// Used in Extract, Glossary, and Translate tabs
class SegmentNumberedItem extends StatefulWidget {
  // Callback to unexclude segment

  const SegmentNumberedItem({
    required this.text,
    required this.index,
    super.key,
    this.isHighlighted = false,
    this.onTap,
    this.onCopy,
    this.itemKey,
    this.badgeColor,
    this.badgeTextColor,
    this.fontSize,
    this.enableSelection = true,
    this.imageDataMap,
    this.isExcluded = false,
    this.exclusionReason,
    this.onExclude,
    this.onUnexclude,
    this.taskId,
    this.onExclusionUpdated,
  });
  final String text;
  final int index; // 0-based index
  final bool isHighlighted;
  final VoidCallback? onTap;
  final VoidCallback? onCopy;
  final GlobalKey? itemKey;
  final Color? badgeColor;
  final Color? badgeTextColor;
  final double? fontSize;
  final bool enableSelection; // Whether text is selectable
  final Map<String, Map<String, String>>?
      imageDataMap; // {placeholder_id: {"data": "data:image/...", "alt": "title"}}
  final bool isExcluded; // Whether this segment is excluded from translation
  final String?
      exclusionReason; // Exclusion reason (e.g., 'image', 'formula', 'reference')
  final Function(int index)? onExclude; // Callback to exclude segment
  final Function(int index)? onUnexclude; // Callback to unexclude segment
  final String? taskId; // Task ID for API calls
  final FutureOr<void> Function(
    int index, {
    String? exclusionReason,
    bool? isExcluded,
  })? onExclusionUpdated; // Callback when exclusion reason is updated

  @override
  State<SegmentNumberedItem> createState() => _SegmentNumberedItemState();
}

class _SegmentNumberedItemState extends State<SegmentNumberedItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final int displayIndex = widget.index + 1; // 1-based display
    final ThemeData theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;
    final Color badgeColor = widget.badgeColor ??
        (isDark ? theme.colorScheme.primaryContainer : Colors.blue.shade50);
    final Color badgeTextColor = widget.badgeTextColor ??
        (isDark ? theme.colorScheme.onPrimaryContainer : Colors.blue.shade700);
    final Color highlightColor = widget.isHighlighted
        ? (isDark
            ? theme.colorScheme.primaryContainer.withOpacity(0.5)
            : Colors.blue.shade100)
        : (_isHovered
            ? theme.colorScheme.onSurfaceVariant.withOpacity(0.06)
            : Colors.transparent);

    return MouseRegion(
      onEnter: (_) {
        // CRITICAL: Always use addPostFrameCallback to avoid setState during layout
        // This prevents "RenderObject was mutated during layout" errors
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            setState(() => _isHovered = true);
          }
        });
      },
      onExit: (_) {
        // CRITICAL: Always use addPostFrameCallback to avoid setState during layout
        // This prevents "RenderObject was mutated during layout" errors
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            setState(() => _isHovered = false);
          }
        });
      },
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          key: widget.itemKey,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          decoration: BoxDecoration(
            color: highlightColor,
            borderRadius: BorderRadius.circular(4),
            border: widget.isHighlighted
                ? Border.all(color: theme.colorScheme.primary, width: 2)
                : null,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Segment number badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: badgeColor,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: badgeColor.withOpacity(0.3)),
                ),
                child: Text(
                  '#$displayIndex',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: badgeTextColor,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // Segment content - may contain text and/or images
              // Use RepaintBoundary to prevent unnecessary repaints when hover state changes
              Expanded(
                child: RepaintBoundary(
                  child: _buildContent(),
                ),
              ),
              // Excluded badge (if excluded)
              if (widget.isExcluded)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: _buildExclusionBadge(context, isDark),
                ),
              // Exclude button (if not excluded and onExclude is provided)
              if (!widget.isExcluded && widget.onExclude != null)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: InkWell(
                    onTap: () {
                      // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                      WidgetsBinding.instance.addPostFrameCallback((_) async {
                        if (mounted && widget.onExclude != null) {
                          // Log exclusion action
                          debugPrint(
                            '[SegmentNumberedItem] Exclude button clicked for segment ${widget.index}',
                          );
                          await widget.onExclude!(widget.index);
                        }
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.orange.shade50,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: Colors.orange.shade300),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Icon(
                            Icons.block_outlined,
                            size: 12,
                            color: Colors.orange.shade700,
                          ),
                          const SizedBox(width: 2),
                          Text(
                            'Exclude?',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w500,
                              color: Colors.orange.shade700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              // Copy button (shown on hover)
              if (_isHovered && widget.onCopy != null) ...<Widget>[
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.copy, size: 16),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: widget.text));
                    widget.onCopy?.call();
                  },
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// Build exclusion badge with reason-specific styling
  /// New design: Badge body for quick unexclude, edit button for editing, x button for quick unexclude
  Widget _buildExclusionBadge(BuildContext context, bool isDark) {
    final ExclusionReason reason =
        ExclusionReason.fromString(widget.exclusionReason);
    final canUnexclude = reason.canUnexclude && widget.onUnexclude != null;
    final canEdit = widget.taskId != null;

    // Build display text with EX prefix
    final displayText = 'EX: ${reason.displayName}';

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        // Badge body: Click to quick unexclude (always allow click to try unexclude)
        Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (!mounted) return;
                // Always try to remove exclusion when clicking the badge
                // If taskId is available, call API directly
                if (widget.taskId != null) {
                  _quickRemoveExclusion(context);
                } else if (widget.onUnexclude != null) {
                  // Fallback to callback
                  // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted && widget.onUnexclude != null) {
                      widget.onUnexclude!(widget.index);
                    }
                  });
                } else if (canEdit) {
                  // If cannot unexclude directly, show edit dialog to allow user to change reason
                  _showEditExclusionDialog(context);
                }
              });
            },
            borderRadius: BorderRadius.circular(4),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 6,
                vertical: 2,
              ),
              decoration: BoxDecoration(
                color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: isDark
                      ? reason.color.withOpacity(0.6)
                      : reason.color.withOpacity(0.4),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    Icons.block,
                    size: 12,
                    color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                  ),
                  const SizedBox(width: 2),
                  Text(
                    displayText,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color:
                          isDark ? Colors.grey.shade300 : Colors.grey.shade800,
                    ),
                  ),
                  const SizedBox(width: 2),
                  Icon(
                    reason.icon,
                    size: 10,
                    color: isDark
                        ? reason.color.withOpacity(0.7)
                        : reason.color.withOpacity(0.8),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Edit button (if can edit) - for editing/switching exclusion reason
        if (canEdit) ...<Widget>[
          const SizedBox(width: 4),
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  _showEditExclusionDialog(context);
                }
              });
            },
            child: MouseRegion(
              cursor: SystemMouseCursors.click,
              child: Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  color: isDark ? Colors.grey.shade700 : Colors.grey.shade200,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Icon(
                  Icons.edit,
                  size: 10,
                  color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                ),
              ),
            ),
          ),
        ],
        // Close button (only if can be unexcluded) - alternative quick unexclude action
        if (canUnexclude) ...<Widget>[
          const SizedBox(width: 4),
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (!mounted) return;
                if (widget.taskId != null) {
                  _quickRemoveExclusion(context);
                } else {
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted && widget.onUnexclude != null) {
                      widget.onUnexclude!(widget.index);
                    }
                  });
                }
              });
            },
            child: MouseRegion(
              cursor: SystemMouseCursors.click,
              child: Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  color: isDark ? Colors.grey.shade700 : Colors.grey.shade200,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.close,
                  size: 10,
                  color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                ),
              ),
            ),
          ),
        ],
        // Info icon (if cannot be unexcluded and cannot edit)
        if (!canUnexclude && !canEdit) ...<Widget>[
          const SizedBox(width: 4),
          Icon(
            Icons.info_outline,
            size: 10,
            color: isDark ? Colors.grey.shade500 : Colors.grey.shade500,
          ),
        ],
      ],
    );
  }

  /// Quick remove exclusion (called by x button or badge click)
  Future<void> _quickRemoveExclusion(BuildContext context) async {
    if (widget.taskId == null) {
      // Fallback to callback if no taskId
      // CRITICAL: Use addPostFrameCallback to avoid setState during layout
      if (widget.onUnexclude != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && widget.onUnexclude != null) {
            widget.onUnexclude!(widget.index);
          }
        });
      }
      return;
    }

    try {
      // Call API to update backend first
      final svc = TranslationService();
      await svc.updateExclusionReason(
        widget.taskId!,
        widget.index,
        null, // Remove exclusion
      );

      // CRITICAL: Update local state AFTER API call succeeds
      // Use addPostFrameCallback to avoid setState during layout
      if (mounted && widget.onUnexclude != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && widget.onUnexclude != null) {
            widget.onUnexclude!(widget.index);
          }
        });
      }

      // CRITICAL: Use addPostFrameCallback to avoid showing message during layout
      if (mounted) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            MessageService.showInfo(
              context,
              'Exclusion removed',
            );
          }
        });
      }
    } catch (e) {
      // Show error message
      // CRITICAL: Use addPostFrameCallback to avoid showing message during layout
      if (mounted) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            MessageService.showError(
              context,
              'Failed to remove exclusion: $e',
            );
            // Revert local state on error
            // CRITICAL: Use addPostFrameCallback to avoid setState during layout
            if (widget.onExclude != null) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted && widget.onExclude != null) {
                  widget.onExclude!(widget.index);
                }
              });
            }
          }
        });
      }
    }
  }

  /// Show dialog to edit exclusion reason
  Future<void> _showEditExclusionDialog(BuildContext context) async {
    if (widget.taskId == null || !mounted) {
      return;
    }

    // CRITICAL: Ensure dialog is shown after layout completes
    // Use a small delay to ensure we're not in the middle of layout
    await Future.delayed(const Duration(milliseconds: 50));

    if (!mounted) return;

    final newReason = await showDialog<String?>(
      context: context,
      builder: (BuildContext context) => ExclusionReasonEditor(
        currentReason: widget.exclusionReason,
      ),
    );

    if (newReason != widget.exclusionReason &&
        widget.taskId != null &&
        mounted) {
      // Call API to update exclusion reason
      try {
        final svc = TranslationService();
        await svc.updateExclusionReason(
          widget.taskId!,
          widget.index,
          newReason,
        );

        // Refresh parent widget to get updated data
        // CRITICAL: Use addPostFrameCallback to avoid setState during layout
        if (widget.onExclusionUpdated != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) async {
            if (mounted && widget.onExclusionUpdated != null) {
              await widget.onExclusionUpdated!(
                widget.index,
                exclusionReason: newReason,
                isExcluded: newReason != null,
              );
            }
          });
        }

        // CRITICAL: Use addPostFrameCallback to avoid showing message during layout
        if (mounted) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              MessageService.showInfo(
                context,
                newReason == null
                    ? 'Exclusion removed'
                    : 'Exclusion reason updated',
              );
            }
          });
        }
      } catch (e) {
        // Show error message
        // CRITICAL: Use addPostFrameCallback to avoid showing message during layout
        if (mounted) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              MessageService.showError(
                context,
                'Failed to update exclusion reason: $e',
              );
            }
          });
        }
      }
    }
  }

  /// Build content widget that handles both text and images
  Widget _buildContent() => MarkdownTextWithImages(
        text: widget.text,
        imageDataMap: widget.imageDataMap,
        enableSelection: widget.enableSelection,
        style: TextStyle(
          fontSize: widget.fontSize ?? 14,
        ),
        imageMaxWidth: 600, // Limit image width for better display
        imageMaxHeight: 400, // Limit image height
      );
}
