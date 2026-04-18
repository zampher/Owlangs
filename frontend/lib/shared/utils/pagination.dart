/// Generic pagination controller for managing paginated data.
///
/// This controller can be used with any data source that supports
/// offset/limit pagination. It manages state, loading, and provides
/// methods for navigation.
library;

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../config/pagination_config.dart';

/// Callback type for fetching paginated data.
///
/// Parameters:
/// - offset: Starting index
/// - limit: Maximum number of items to return
///
/// Returns: Map with keys: items (List), total (int), and optionally
///   offset, limit, page, page_size, has_prev, has_next
typedef PaginatedDataFetcher<T> = Future<Map<String, dynamic>> Function(
  int offset,
  int limit,
);

/// Generic pagination controller.
class PagedListController<T> extends ChangeNotifier {
  PagedListController({
    required PaginatedDataFetcher<T> fetcher,
    T Function(dynamic)? itemConverter,
    int? initialPageSize,
    bool prefetchEnabled = false,
  })  : _fetcher = fetcher,
        _itemConverter = itemConverter,
        _pageSize = initialPageSize ?? defaultPaginationLimit,
        _prefetchEnabled = prefetchEnabled;

  /// Current items in the page
  List<T> _items = <T>[];

  /// Total number of items across all pages
  int _total = 0;

  /// Current offset
  int _offset = 0;

  /// Current page size (limit)
  int _pageSize = defaultPaginationLimit;

  /// Whether data is currently loading
  bool _isLoading = false;

  /// Error message if loading failed
  String? _error;

  /// Data fetcher function
  final PaginatedDataFetcher<T> _fetcher;

  /// Item converter function (optional, for converting raw data to T)
  final T Function(dynamic)? _itemConverter;

  /// Whether to prefetch next page
  final bool _prefetchEnabled;

  /// Prefetched next page data
  List<T>? _prefetchedNextPage;

  // Getters
  List<T> get items => _items;
  int get total => _total;
  int get offset => _offset;
  int get pageSize => _pageSize;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get hasMore => _offset + _items.length < _total;
  bool get hasPrev => _offset > 0;
  int get currentPage => (_offset ~/ _pageSize) + 1;
  int get totalPages => (_total / _pageSize).ceil();
  int get startIndex => _offset + 1;
  int get endIndex => _offset + _items.length;

  /// Load first page (reset to beginning)
  Future<void> loadFirstPage() async {
    await _loadPage(offset: 0);
  }

  /// Load next page
  Future<void> loadNextPage() async {
    if (!hasMore || _isLoading) return;
    await _loadPage(offset: _offset + _items.length);
  }

  /// Load previous page
  Future<void> loadPrevPage() async {
    if (!hasPrev || _isLoading) return;
    final newOffset = (_offset - _pageSize).clamp(0, double.infinity).toInt();
    await _loadPage(offset: newOffset);
  }

  /// Jump to specific page (1-based)
  Future<void> jumpToPage(int page) async {
    if (page < 1 || page > totalPages || _isLoading) return;
    final newOffset = (page - 1) * _pageSize;
    await _loadPage(offset: newOffset);
  }

  /// Set page size and reload
  Future<void> setPageSize(int size) async {
    if (size < 1 || size == _pageSize || _isLoading) return;
    _pageSize = size;
    // Reset to first page when page size changes
    await loadFirstPage();
  }

  /// Refresh current page
  Future<void> refresh() async {
    await _loadPage(offset: _offset);
  }

  /// Internal method to load a page
  Future<void> _loadPage({required int offset}) async {
    if (_isLoading) return;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _fetcher(offset, _pageSize);

      // Extract data from response
      final itemsRaw = response['items'] as List<dynamic>? ??
          response['segments'] as List<dynamic>? ??
          <dynamic>[];
      final total = (response['total'] as num?)?.toInt() ??
          (response['total_segments'] as num?)?.toInt() ??
          itemsRaw.length;

      // Convert items
      final items = _itemConverter != null
          ? itemsRaw.map<T>((e) => _itemConverter!(e)).toList()
          : itemsRaw.cast<T>();

      // Update state
      _items = items;
      _total = total;
      _offset = (response['offset'] as num?)?.toInt() ?? offset;

      // Prefetch next page if enabled
      if (_prefetchEnabled && hasMore) {
        _prefetchNextPage();
      }

      _error = null;
    } catch (e) {
      _error = e.toString();
      _items = <T>[];
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Prefetch next page in background
  void _prefetchNextPage() {
    if (!hasMore || _prefetchedNextPage != null) return;

    final nextOffset = _offset + _items.length;
    _fetcher(nextOffset, _pageSize).then((response) {
      final itemsRaw = response['items'] as List<dynamic>? ??
          response['segments'] as List<dynamic>? ??
          <dynamic>[];
      _prefetchedNextPage = _itemConverter != null
          ? itemsRaw.map<T>((e) => _itemConverter!(e)).toList()
          : itemsRaw.cast<T>();
    }).catchError((_) {
      // Ignore prefetch errors
    });
  }
}
