import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_config.dart';

class AppTheme {
  // Color scheme from AppConfig
  static const Color primaryColor = AppConfig.primaryColor;
  static const Color secondaryColor = AppConfig.secondaryColor;
  static const Color errorColor = AppConfig.errorColor;
  static const Color surfaceColor = AppConfig.surfaceColor;
  static const Color backgroundColor = AppConfig.backgroundColor;

  // Light theme
  static ThemeData get lightTheme => ThemeData(
        useMaterial3: true,
        fontFamily: 'Roboto',
        // Only use bundled fonts (Noto Sans HK is now bundled in fonts/NotoSansHK-Regular.otf)
        fontFamilyFallback: const <String>[
          'Noto Sans',
          'Noto Sans SC',
          'Noto Sans KR',
          'Noto Sans HK',
          'Noto Sans Symbols',
          'Noto Sans Arabic',
          'Noto Sans Bengali',
          'Noto Sans Devanagari',
          'Noto Sans Hebrew',
          'Noto Sans Thai',
          'Noto Sans Khmer',
        ],
        textTheme: const TextTheme().apply(
          fontFamily: 'Roboto',
          fontFamilyFallback: <String>[
            'Noto Sans',
            'Noto Sans SC',
            'Noto Sans KR',
            'Noto Sans HK',
            'Noto Sans Symbols',
            'Noto Sans Arabic',
            'Noto Sans Bengali',
            'Noto Sans Devanagari',
            'Noto Sans Hebrew',
            'Noto Sans Thai',
            'Noto Sans Khmer',
          ],
        ),
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryColor,
        ),
        appBarTheme: const AppBarTheme(
          elevation: 0,
          centerTitle: true,
          systemOverlayStyle: SystemUiOverlayStyle.dark,
        ),
        cardTheme: const CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            elevation: 2,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      );

  // Dark theme
  static ThemeData get darkTheme => ThemeData(
        useMaterial3: true,
        fontFamily: 'Roboto',
        // Only use bundled fonts (Noto Sans HK is now bundled in fonts/NotoSansHK-Regular.otf)
        fontFamilyFallback: const <String>[
          'Noto Sans',
          'Noto Sans SC',
          'Noto Sans KR',
          'Noto Sans HK',
          'Noto Sans Symbols',
          'Noto Sans Arabic',
          'Noto Sans Bengali',
          'Noto Sans Devanagari',
          'Noto Sans Hebrew',
          'Noto Sans Thai',
          'Noto Sans Khmer',
        ],
        textTheme: const TextTheme().apply(
          fontFamily: 'Roboto',
          fontFamilyFallback: <String>[
            'Noto Sans',
            'Noto Sans SC',
            'Noto Sans KR',
            'Noto Sans HK',
            'Noto Sans Symbols',
            'Noto Sans Arabic',
            'Noto Sans Bengali',
            'Noto Sans Devanagari',
            'Noto Sans Hebrew',
            'Noto Sans Thai',
            'Noto Sans Khmer',
          ],
        ),
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryColor,
          brightness: Brightness.dark,
        ),
        appBarTheme: const AppBarTheme(
          elevation: 0,
          centerTitle: true,
          systemOverlayStyle: SystemUiOverlayStyle.light,
        ),
        cardTheme: const CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            elevation: 2,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      );
}
