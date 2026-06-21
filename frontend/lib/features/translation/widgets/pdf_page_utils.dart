// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:pdfx/pdfx.dart';

/// Close a [PdfPage] without throwing when the page or document is already closed.
Future<void> safeClosePdfPage(PdfPage? page) async {
  if (page == null) {
    return;
  }
  try {
    await page.close();
  } catch (_) {
    // Expected when the parent document was closed during an in-flight render.
  }
}
