// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/translation_stats_service.dart';

/// Provider for translation statistics.
/// Not autoDispose so that when returning to Home from Settings/Wizard we show
/// cached stats immediately instead of a loading flash.
final FutureProvider<TranslationStats> translationStatsProvider =
    FutureProvider<TranslationStats>((ref) async {
  final service = TranslationStatsService();
  return service.getStats();
});

/// Widget to display translation statistics
class TranslationStatsWidget extends ConsumerWidget {
  const TranslationStatsWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statsAsync = ref.watch(translationStatsProvider);

    return statsAsync.when(
      data: (stats) => _buildStatsCard(context, stats),
      loading: () => _buildLoadingCard(context),
      error: (error, stack) => _buildErrorCard(context),
    );
  }

  Widget _buildStatsCard(BuildContext context, TranslationStats stats) {
    final primaryColor = Theme.of(context).colorScheme.primary;
    final surfaceColor = Theme.of(context).colorScheme.surface;
    final onSurfaceColor = Theme.of(context).colorScheme.onSurface;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: primaryColor.withOpacity(0.3),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: surfaceColor,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.analytics_outlined,
                  color: primaryColor,
                  size: 24,
                ),
                const SizedBox(width: 8),
                Text(
                  AppLocalizations.of(context)!.translationStatsTitle,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: onSurfaceColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: <Widget>[
                Expanded(
                  child: _buildStatItem(
                    context,
                    icon: Icons.description_outlined,
                    label: AppLocalizations.of(context)!.translationStatsDocuments,
                    value: stats.documentCount.toString(),
                    color: primaryColor,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildStatItem(
                    context,
                    icon: Icons.pages_outlined,
                    label: AppLocalizations.of(context)!.translationStatsPages,
                    value: stats.pageCount.toString(),
                    color: primaryColor,
                  ),
                ),
              ],
            ),
            if (stats.lastUpdated != null) ...<Widget>[
              const SizedBox(height: 12),
              Text(
                AppLocalizations.of(context)!.translationStatsLastUpdated(
                  _formatDate(context, stats.lastUpdated!),
                ),
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) =>
      Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: color.withOpacity(0.3),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              icon,
              color: color,
              size: 20,
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      );

  Widget _buildLoadingCard(BuildContext context) => Card(
        elevation: 2,
        child: Container(
          padding: const EdgeInsets.all(16),
          child: const Center(
            child: CircularProgressIndicator(),
          ),
        ),
      );

  Widget _buildErrorCard(BuildContext context) => Card(
        elevation: 2,
        child: Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: <Widget>[
              Icon(
                Icons.error_outline,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Failed to load statistics',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
            ],
          ),
        ),
      );

  String _formatDate(BuildContext context, DateTime date) {
    final l10n = AppLocalizations.of(context)!;
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays == 0) {
      if (difference.inHours == 0) {
        if (difference.inMinutes == 0) {
          return l10n.translationStatsJustNow;
        }
        if (difference.inMinutes == 1) {
          return l10n.translationStatsOneMinuteAgo;
        }
        return l10n.translationStatsMinutesAgo(difference.inMinutes.toString());
      }
      if (difference.inHours == 1) {
        return l10n.translationStatsOneHourAgo;
      }
      return l10n.translationStatsHoursAgo(difference.inHours.toString());
    } else if (difference.inDays == 1) {
      return l10n.translationStatsYesterday;
    } else if (difference.inDays < 7) {
      return l10n.translationStatsDaysAgo(difference.inDays.toString());
    } else {
      return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
    }
  }
}
