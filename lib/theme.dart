import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// Same palette as www.germansmedia.nl so the subsite feels like part of the family.
const Color backgroundColor = Color(0xFF23272C);
const Color surfaceColor = Color(0xFF2D3238);
const Color textColor = Colors.white;
const Color softColor = Color(0xFFB0B6BD);
const Color primaryColor = Color(0xFFFFD540);

ThemeData buildTheme({bool useGoogleFonts = true}) {
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    scaffoldBackgroundColor: backgroundColor,
    colorScheme: ColorScheme.fromSeed(
      seedColor: primaryColor,
      brightness: Brightness.dark,
      primary: primaryColor,
      onPrimary: Colors.black,
      surface: surfaceColor,
      onSurface: textColor,
    ),
  );
  TextStyle heading(double size) => useGoogleFonts
      ? GoogleFonts.oswald(fontSize: size, color: textColor)
      : TextStyle(fontSize: size, color: textColor, fontWeight: FontWeight.w600);
  TextStyle body(double size) =>
      useGoogleFonts ? GoogleFonts.montserrat(fontSize: size, color: textColor) : TextStyle(fontSize: size, color: textColor);

  return base.copyWith(
    textTheme: base.textTheme.copyWith(
      displayLarge: heading(44),
      displayMedium: heading(36),
      displaySmall: heading(24),
      headlineMedium: heading(18),
      titleLarge: heading(22),
      bodyLarge: body(15),
      bodyMedium: body(14),
      labelLarge: body(14).copyWith(fontWeight: FontWeight.w600),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: backgroundColor,
      foregroundColor: textColor,
      titleTextStyle: heading(26),
      elevation: 0,
    ),
    cardTheme: const CardTheme(color: surfaceColor, margin: EdgeInsets.zero),
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(), filled: true, fillColor: backgroundColor),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: primaryColor, linearTrackColor: Color(0xFF3A4048)),
  );
}
