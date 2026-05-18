// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Stub replacement for `package:desktop_drop/desktop_drop.dart` when
/// compiled for web (where the native plugin is unavailable).
///
/// Drag-and-drop on web is handled via `dart:html` window event listeners
/// in [FileUploadArea] and [GlossaryPreview], so this stub simply renders
/// the child widget without any drag interaction.
library;

import 'package:flutter/material.dart';

/// DropTarget stub — always renders [child] untouched.
// ignore: subtype_of_sealed_class
class DropTarget extends StatelessWidget {
  const DropTarget({
    super.key,
    this.onDragEntered,
    this.onDragExited,
    this.onDragDone,
    required this.child,
  });

  final void Function(DropEventDetails)? onDragEntered;
  final void Function(DropEventDetails)? onDragExited;
  final void Function(DropDoneDetails)? onDragDone;
  final Widget child;

  @override
  Widget build(BuildContext context) => child;
}

/// Stub for [DropEventDetails].
class DropEventDetails {
  const DropEventDetails({this.x = 0.0, this.y = 0.0});
  final double x;
  final double y;
}

/// Stub for [DropDoneDetails].
class DropDoneDetails {
  const DropDoneDetails({
    this.files = const <DropFile>[],
    this.x = 0.0,
    this.y = 0.0,
  });
  final List<DropFile> files;
  final double x;
  final double y;
}

/// Stub for [DropFile].
class DropFile {
  const DropFile({
    this.name = '',
    this.path,
    this.size = 0,
    this.bytes,
  });
  final String name;
  final String? path;
  final int size;
  final List<int>? bytes;
}
