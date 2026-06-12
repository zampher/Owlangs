// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import '../html_stub.dart' if (dart.library.html) 'dart:html' as html;

import '../app_logger.dart';
import 'compare_scroll_sync_base.dart';

void _scrollSyncLog(String message) {
  AppLogger.log('CompareScrollSync', message);
}

const String _hideScrollbarStyleId = 'owlangs-compare-hide-scrollbar';

final Map<CompareScrollSyncGroup, _WebScrollState> _webStates =
    <CompareScrollSyncGroup, _WebScrollState>{};

class _WebScrollState {
  final Map<String, html.IFrameElement> iframes = <String, html.IFrameElement>{};
  final Map<String, void Function()> cleanups = <String, void Function()>{};
}

void registerWebIframe(
  CompareScrollSyncGroup group,
  String paneId,
  dynamic iframe,
) {
  if (iframe is! html.IFrameElement) {
    return;
  }
  final _WebScrollState state = _webStates.putIfAbsent(
    group,
    () => _WebScrollState(),
  );
  unregisterWebPane(group, paneId);
  state.iframes[paneId] = iframe;

  void onLoad(html.Event _) {
    _applyPaneUi(group, paneId);
    refreshScrollMetrics(group);
  }
  iframe.onLoad.listen(onLoad);
  _applyPaneUi(group, paneId);
  refreshScrollMetrics(group);
  _schedulePaneSetupRetry(group, paneId);
}

void _schedulePaneSetupRetry(CompareScrollSyncGroup group, String paneId) {
  for (final int delayMs in <int>[100, 300, 800, 1500, 3000]) {
    Future<void>.delayed(Duration(milliseconds: delayMs), () {
      final _WebScrollState? state = _webStates[group];
      if (state == null || !state.iframes.containsKey(paneId)) {
        return;
      }
      _applyPaneUi(group, paneId);
      refreshScrollMetrics(group);
    });
  }
}

void unregisterWebPane(CompareScrollSyncGroup group, String paneId) {
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }
  state.cleanups[paneId]?.call();
  state.cleanups.remove(paneId);
  state.iframes.remove(paneId);
}

void disposeWeb(CompareScrollSyncGroup group) {
  final _WebScrollState? state = _webStates.remove(group);
  if (state == null) {
    return;
  }
  for (final void Function() cleanup in state.cleanups.values) {
    cleanup();
  }
  state.cleanups.clear();
  state.iframes.clear();
}

void setCompareScrollUiEnabled(CompareScrollSyncGroup group, bool enabled) {
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }
  for (final String paneId in state.iframes.keys) {
    _applyPaneUi(group, paneId);
  }
}

void refreshScrollMetrics(CompareScrollSyncGroup group) {
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }

  double maxExtent = 0;
  for (final html.IFrameElement iframe in state.iframes.values) {
    final html.Window? window = _windowFromIframe(iframe);
    if (window == null) {
      continue;
    }
    final html.Element? root = _scrollRoot(window.document);
    if (root == null) {
      continue;
    }
    final double extent =
        (root.scrollHeight - root.clientHeight).toDouble();
    if (extent > maxExtent) {
      maxExtent = extent;
    }
  }

  if (maxExtent != group.masterScrollExtent) {
    group.masterScrollExtent = maxExtent;
    group.notifyMetricsChanged();
    _scrollSyncLog('Master scroll extent updated: $maxExtent px');
  }
}

void applyMasterOffset(CompareScrollSyncGroup group, double offset) {
  if (!group.enabled) {
    return;
  }
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }

  final double maxExtent = group.masterScrollExtent;
  final double ratio =
      maxExtent > 0 ? (offset / maxExtent).clamp(0.0, 1.0) : 0.0;

  group.beginPropagation();
  for (final html.IFrameElement iframe in state.iframes.values) {
    final html.Window? window = _windowFromIframe(iframe);
    if (window == null) {
      continue;
    }
    final html.Element? root = _scrollRoot(window.document);
    if (root == null) {
      continue;
    }
    final double paneMax =
        (root.scrollHeight - root.clientHeight).toDouble();
    root.scrollTop = (ratio * paneMax).round();
  }
  group.endPropagation();
}

html.Window? _windowFromIframe(html.IFrameElement iframe) {
  final html.WindowBase? windowBase = iframe.contentWindow;
  if (windowBase is! html.Window) {
    return null;
  }
  return windowBase as html.Window;
}

html.Element? _scrollRoot(html.Document doc) {
  return doc.scrollingElement ?? doc.documentElement;
}

void _applyPaneUi(CompareScrollSyncGroup group, String paneId) {
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }
  final html.IFrameElement? iframe = state.iframes[paneId];
  if (iframe == null) {
    return;
  }

  final html.Window? window = _windowFromIframe(iframe);
  if (window == null) {
    return;
  }

  final html.Document doc = window.document;
  _setHideScrollbarStyle(doc, group.enabled);
  _bindWheelToMaster(group, paneId, window, doc);
}

void _setHideScrollbarStyle(html.Document doc, bool hide) {
  final html.Element? existing = doc.getElementById(_hideScrollbarStyleId);
  if (hide) {
    if (existing != null) {
      return;
    }
    final html.StyleElement style = html.StyleElement()
      ..id = _hideScrollbarStyleId
      ..text = '''
html {
  overflow-y: auto !important;
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
}
html::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}
''';
    final html.Element? head =
        doc.querySelector('head') ?? doc.documentElement;
    head?.append(style);
    return;
  }
  existing?.remove();
}

void _bindWheelToMaster(
  CompareScrollSyncGroup group,
  String paneId,
  html.Window window,
  html.Document doc,
) {
  final _WebScrollState? state = _webStates[group];
  if (state == null) {
    return;
  }

  state.cleanups[paneId]?.call();

  if (!group.enabled) {
    return;
  }

  void onWheel(html.Event event) {
    if (!group.enabled) {
      return;
    }
    final num deltaY = (event as dynamic).deltaY as num? ?? 0;
    if (deltaY == 0) {
      return;
    }
    event.preventDefault();
    group.nudgeMasterScroll(deltaY.toDouble());
  }

  window.addEventListener('wheel', onWheel);
  doc.addEventListener('wheel', onWheel);
  state.cleanups[paneId] = () {
    window.removeEventListener('wheel', onWheel);
    doc.removeEventListener('wheel', onWheel);
  };
}
