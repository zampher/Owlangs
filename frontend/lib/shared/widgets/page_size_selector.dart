/// Page size selector widget for choosing items per page.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Page size selector widget.
///
/// Allows users to select how many items to display per page.
/// Optionally persists the selection to SharedPreferences.
class PageSizeSelector extends StatefulWidget {
  const PageSizeSelector({
    required this.currentPageSize,
    required this.onPageSizeChanged,
    super.key,
    this.pageSizeOptions = const <int>[50, 100, 200, 500],
    this.preferenceKey,
    this.showLabel = true,
    this.labelText,
  });

  /// Current page size
  final int currentPageSize;

  /// Available page size options
  final List<int> pageSizeOptions;

  /// Callback when page size changes
  final ValueChanged<int> onPageSizeChanged;

  /// Optional preference key for persisting selection
  final String? preferenceKey;

  /// Whether to show label
  final bool showLabel;

  /// Custom label text
  final String? labelText;

  @override
  State<PageSizeSelector> createState() => _PageSizeSelectorState();
}

class _PageSizeSelectorState extends State<PageSizeSelector> {
  @override
  void initState() {
    super.initState();
    if (widget.preferenceKey != null) {
      _loadSavedPageSize();
    }
  }

  Future<void> _loadSavedPageSize() async {
    if (widget.preferenceKey == null) return;
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final int? saved = prefs.getInt(widget.preferenceKey!);
      if (saved != null && widget.pageSizeOptions.contains(saved)) {
        if (saved != widget.currentPageSize) {
          widget.onPageSizeChanged(saved);
        }
      }
    } catch (e) {
      // Ignore errors
    }
  }

  Future<void> _savePageSize(int size) async {
    if (widget.preferenceKey == null) return;
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setInt(widget.preferenceKey!, size);
    } catch (e) {
      // Ignore errors
    }
  }

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (widget.showLabel) ...<Widget>[
            Text(
              widget.labelText ?? 'Items per page:',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(width: 8),
          ],
          DropdownButton<int>(
            value: widget.currentPageSize,
            isDense: true,
            items: widget.pageSizeOptions
                .map(
                  (size) => DropdownMenuItem<int>(
                    value: size,
                    child: Text(
                      size.toString(),
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                )
                .toList(),
            onChanged: (int? newSize) {
              if (newSize != null && newSize != widget.currentPageSize) {
                widget.onPageSizeChanged(newSize);
                _savePageSize(newSize);
              }
            },
          ),
        ],
      );
}
