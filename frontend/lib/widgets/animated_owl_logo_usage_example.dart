// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Example usage of AnimatedOwlLogo widget
///
/// This file demonstrates how to use the animated owl logo in different contexts:
/// - Loading screen
/// - Splash screen
/// - About page
/// - Settings page
library;

import 'package:flutter/material.dart';
import 'animated_owl_logo.dart';

// Example 1: Loading screen
class LoadingScreenWithOwl extends StatelessWidget {
  const LoadingScreenWithOwl({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              const AnimatedOwlLogo(
                width: 400,
                height: 200,
              ),
              const SizedBox(height: 32),
              Text(
                'Processing your document...',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              const CircularProgressIndicator(),
            ],
          ),
        ),
      );
}

// Example 2: Compact version for app bar or small spaces
class CompactOwlLogo extends StatelessWidget {
  const CompactOwlLogo({super.key});

  @override
  Widget build(BuildContext context) => const SizedBox(
        width: 200,
        height: 100,
        child: AnimatedOwlLogo(
          width: 200,
          height: 100,
        ),
      );
}

// Example 3: With custom duration
class CustomSpeedOwlLogo extends StatelessWidget {
  const CustomSpeedOwlLogo({super.key});

  @override
  Widget build(BuildContext context) => const AnimatedOwlLogo(
        animationDuration: Duration(seconds: 4), // Faster animation
      );
}

// Example 4: Manual control
class ControllableOwlLogo extends StatefulWidget {
  const ControllableOwlLogo({super.key});

  @override
  State<ControllableOwlLogo> createState() => _ControllableOwlLogoState();
}

class _ControllableOwlLogoState extends State<ControllableOwlLogo> {
  bool _isPlaying = false;

  @override
  Widget build(BuildContext context) => Column(
        children: <Widget>[
          AnimatedOwlLogo(
            width: 400,
            height: 200,
            autoPlay: _isPlaying,
          ),
          ElevatedButton(
            onPressed: () {
              setState(() {
                _isPlaying = !_isPlaying;
              });
            },
            child: Text(_isPlaying ? 'Pause' : 'Play'),
          ),
        ],
      );
}
