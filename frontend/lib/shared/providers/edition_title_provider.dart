// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/app_config.dart';

/// Full app title including target platform:
/// OpenSource edition keeps the app title stable as "Owlangs".
Future<String> _loadEditionTitle() async => AppConfig.appName;

/// Provider for the app title with platform suffix.
final FutureProvider<String> editionTitleProvider =
    FutureProvider<String>((ref) => _loadEditionTitle());
