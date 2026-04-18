// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:html' as html;

/// Sets the browser document title (Web only).
void setPageTitle(String title) {
  html.document.title = title;
}
