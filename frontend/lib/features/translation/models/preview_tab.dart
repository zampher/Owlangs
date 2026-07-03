// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Preview tab id for full-document / revision compare preview.
const String kTranslationPreviewTabId = 'translation_preview_tab';

/// Preview tab types
enum PreviewTabType {
  translationResult,
  glossary,
  prompt,
  formatConversion,
}

/// Preview tab data model
class PreviewTab {
  // For persistence

  PreviewTab({
    required this.id,
    required this.type,
    required this.title,
    required this.content,
    this.icon,
    DateTime? createdAt,
    this.dataRef,
  }) : createdAt = createdAt ?? DateTime.now();

  /// Deserialize from JSON (without content, will be recreated)
  ///
  /// Note: Icon is not restored from JSON to ensure compile-time constants.
  /// Use defaultIcon getter to get the appropriate icon for the tab type.
  factory PreviewTab.fromJson(Map<String, dynamic> json) {
    final type = PreviewTabType.values.firstWhere(
      (e) => e.toString() == json['type'],
      orElse: () => PreviewTabType.translationResult,
    );

    // Use defaultIcon instead of restoring from iconCodePoint
    // This ensures IconData is a compile-time constant for tree-shaking
    final tab = PreviewTab(
      id: json['id'] as String,
      type: type,
      title: json['title'] as String,
      content: Container(), // Will be recreated based on dataRef
      createdAt: DateTime.parse(json['createdAt'] as String),
      dataRef: json['dataRef'] as Map<String, dynamic>?,
    );

    return tab;
  }
  final String id;
  final PreviewTabType type;
  final String title;
  final Widget content;
  final IconData? icon;
  final DateTime createdAt;
  final Map<String, dynamic>? dataRef;

  /// Get default icon for tab type
  IconData get defaultIcon {
    switch (type) {
      case PreviewTabType.translationResult:
        return Icons.translate;
      case PreviewTabType.glossary:
        return Icons.book;
      case PreviewTabType.prompt:
        return Icons.edit_note;
      case PreviewTabType.formatConversion:
        return Icons.transform;
    }
  }

  /// Serialize for persistence
  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'type': type.toString(),
        'title': title,
        'iconCodePoint': icon?.codePoint,
        'createdAt': createdAt.toIso8601String(),
        'dataRef': dataRef,
      };
}
