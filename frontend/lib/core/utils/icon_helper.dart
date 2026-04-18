// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Helper class to convert icon code points to compile-time constants
///
/// This ensures that IconData instances are compile-time constants,
/// which is required for Flutter Web tree-shaking to work properly.
class IconHelper {
  /// Map of common Material Icons code points to their const IconData instances
  ///
  /// This map allows us to convert runtime code points to compile-time constants.
  /// Only includes icons that are actually used in the app.
  static const Map<int, IconData> _iconMap = <int, IconData>{
    // Translation icons
    0xe8e2: Icons.translate, // translate
    0xe865: Icons.book, // book
    0xe8e5: Icons.transform, // transform
    0xe8e6: Icons.fact_check, // fact_check
    0xe2c6: Icons.upload_file, // upload_file
    0xe8e7: Icons.visibility, // visibility
    0xe8e8: Icons.visibility_off, // visibility_off
    0xe8e9: Icons.download, // download
    0xe8ea: Icons.upload, // upload
    0xe8eb: Icons.file_present, // file_present
    0xe8ec: Icons.description, // description
    0xe8ed: Icons.insert_drive_file, // insert_drive_file
    0xe8ee: Icons.picture_as_pdf, // picture_as_pdf
    0xe8ef: Icons.text_snippet, // text_snippet
    0xe8f0: Icons.code, // code
    0xe8f1: Icons.settings, // settings
    0xe8f2: Icons.home, // home
    0xe8f3: Icons.menu, // menu
    0xe8f4: Icons.close, // close
    0xe8f5: Icons.check, // check
    0xe8f6: Icons.cancel, // cancel
    0xe8f7: Icons.arrow_back, // arrow_back
    0xe8f8: Icons.arrow_forward, // arrow_forward
    0xe8f9: Icons.refresh, // refresh
    0xe8fa: Icons.delete, // delete
    0xe8fb: Icons.edit, // edit
    0xe8fc: Icons.add, // add
    0xe8fd: Icons.remove, // remove
    0xe8fe: Icons.search, // search
    0xe8ff: Icons.filter_list, // filter_list
    0xe900: Icons.sort, // sort
    0xe901: Icons.more_vert, // more_vert
    0xe902: Icons.more_horiz, // more_horiz
    0xe903: Icons.info, // info
    0xe904: Icons.warning, // warning
    0xe905: Icons.error, // error
    0xe906: Icons.check_circle, // check_circle
    0xe907: Icons.cancel, // cancel (replaces cancel_circle)
    0xe908: Icons.help, // help
    0xe909: Icons.arrow_drop_down, // arrow_drop_down
    0xe90a: Icons.arrow_drop_up, // arrow_drop_up
    0xe90b: Icons.expand_more, // expand_more
    0xe90c: Icons.expand_less, // expand_less
    0xe90d: Icons.play_arrow, // play_arrow
    0xe90e: Icons.pause, // pause
    0xe90f: Icons.stop, // stop
    0xe910: Icons.skip_next, // skip_next
    0xe911: Icons.skip_previous, // skip_previous
    0xe912: Icons.first_page, // first_page
    0xe913: Icons.last_page, // last_page
    0xe914: Icons.chevron_left, // chevron_left
    0xe915: Icons.chevron_right, // chevron_right
    0xe916: Icons.keyboard_arrow_up, // keyboard_arrow_up (replaces chevron_up)
    0xe917: Icons
        .keyboard_arrow_down, // keyboard_arrow_down (replaces chevron_down)
    0xe918: Icons.fullscreen, // fullscreen
    0xe919: Icons.fullscreen_exit, // fullscreen_exit
    0xe91a: Icons.zoom_in, // zoom_in
    0xe91b: Icons.zoom_out, // zoom_out
    0xe91c: Icons.fit_screen, // fit_screen
    0xe91d: Icons.aspect_ratio, // aspect_ratio
    0xe91e: Icons.crop, // crop
    0xe91f: Icons.rotate_left, // rotate_left
    0xe920: Icons.rotate_right, // rotate_right
    0xe921: Icons.flip, // flip
    0xe922: Icons.brightness_6, // brightness_6 (replaces brightness)
    0xe923: Icons.contrast, // contrast
    0xe924: Icons.tune, // tune (replaces saturation)
    0xe925: Icons.palette, // palette (replaces hue)
    0xe926: Icons.blur_on, // blur_on (replaces blur)
    0xe927: Icons.auto_fix_high, // auto_fix_high (replaces sharpness)
    0xe928: Icons.filter, // filter
    0xe929: Icons.filter_none, // filter_none
    0xe92a: Icons.filter_1, // filter_1
    0xe92b: Icons.filter_2, // filter_2
    0xe92c: Icons.filter_3, // filter_3
    0xe92d: Icons.filter_4, // filter_4
    0xe92e: Icons.filter_5, // filter_5
    0xe92f: Icons.filter_6, // filter_6
    0xe930: Icons.filter_7, // filter_7
    0xe931: Icons.filter_8, // filter_8
    0xe932: Icons.filter_9, // filter_9
    0xe933: Icons.filter_9_plus, // filter_9_plus
    0xe934: Icons.filter_b_and_w, // filter_b_and_w
    0xe935: Icons.filter_center_focus, // filter_center_focus
    0xe936: Icons.filter_drama, // filter_drama
    0xe937: Icons.filter_frames, // filter_frames
    0xe938: Icons.filter_hdr, // filter_hdr
    0xe939: Icons.filter_none, // filter_none
    0xe93a: Icons.filter_tilt_shift, // filter_tilt_shift
    0xe93b: Icons.filter_vintage, // filter_vintage
  };

  /// Get IconData from code point, returning a compile-time constant if available
  ///
  /// If the code point is in the map, returns the const IconData.
  /// Otherwise, returns null (caller should use a default icon).
  ///
  /// This ensures all IconData instances are compile-time constants,
  /// which is required for Flutter Web tree-shaking.
  static IconData? fromCodePoint(int? codePoint) {
    if (codePoint == null) return null;
    return _iconMap[codePoint];
  }

  /// Get IconData from code point with fallback
  ///
  /// If the code point is in the map, returns the const IconData.
  /// Otherwise, returns the provided fallback icon.
  static IconData fromCodePointWithFallback(int? codePoint, IconData fallback) {
    if (codePoint == null) return fallback;
    return _iconMap[codePoint] ?? fallback;
  }
}
