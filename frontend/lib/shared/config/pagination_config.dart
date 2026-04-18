// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Pagination configuration constants.
///
/// This file provides centralized configuration for pagination limits across the application.
/// Modify these values to change pagination behavior globally.
///
/// Note: These values should match the backend configuration in
/// `backend/app/config/pagination_config.py` for consistency.
library;

/// Maximum number of items that can be requested in a single pagination request.
/// This is a safety limit to prevent excessive memory usage and API abuse.
const int maxPaginationLimit = 100000;

/// Default number of items to return when limit is not specified.
const int defaultPaginationLimit = 200;

/// Default limit for segment preview requests.
/// This can be increased if needed, but should not exceed [maxPaginationLimit].
const int defaultSegmentPreviewLimit = 1000;
