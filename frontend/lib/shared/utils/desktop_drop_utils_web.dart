// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Overrides [desktop_drop]'s window property drag handlers on web so that
/// they no longer invoke the (unimplemented) method channel.
///
/// [desktop_drop 0.7.0] registers itself via ``pubspec.yaml``:
/// ```yaml
/// web:
///   pluginClass: DesktopDropWeb
///   fileName: desktop_drop_web.dart
/// ```
/// Its ``_registerEvents()`` sets ``window.ondragover`` / ``ondragenter`` /
/// ``ondragleave`` / ``ondrop`` to handlers that call
/// ``channel.invokeMethod(...)``, which throws ``MissingPluginException``
/// because ``handleMethodCall`` is a no-op that throws.
///
/// By nullifying those properties **after** the plugin has registered, we
/// prevent the unhandled channel calls while our own ``addEventListener``
/// listeners (set up in [FileUploadArea]) continue to work.
library;

import 'dart:js' as js;

void disableDesktopDropWebPlugin() {
  // js.context is the JS global object; in browsers this === window.
  // Setting properties directly on it is equivalent to
  // `window.ondragenter = null` etc.
  js.context['ondragenter'] = null;
  js.context['ondragover'] = null;
  js.context['ondragleave'] = null;
  js.context['ondrop'] = null;
}
