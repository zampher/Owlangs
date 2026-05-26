import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../app/app_router.dart';
import '../../contact/screens/contact_screen.dart';
import 'help_screen.dart';
import 'edition_comparison_screen.dart';
import 'quick_start_guide_screen.dart';
import 'donate_screen.dart';

/// Main screen managing Donate, Help, and Contact tabs.
///
/// [mode] controls which tabs are shown:
/// - 'full' (default): Quick Start, Help, Editions, Donate, Contact
/// - 'help': Quick Start, Help, Editions, Contact (no Donate tab)
/// - 'donate': Only Donate content, no TabBar
class DonateHelpContactScreen extends StatefulWidget {
  final String mode;
  const DonateHelpContactScreen({super.key, this.mode = 'full'});

  @override
  State<DonateHelpContactScreen> createState() =>
      _DonateHelpContactScreenState();
}

class _DonateHelpContactScreenState extends State<DonateHelpContactScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late int _tabCount;

  @override
  void initState() {
    super.initState();
    if (widget.mode == 'donate') {
      _tabCount = 1;
    } else if (widget.mode == 'help') {
      // Quick Start, Help, Editions, Contact (no Donate)
      _tabCount = 4;
    } else {
      // full: Quick Start, Help, Editions, Donate, Contact
      _tabCount = 5;
    }
    _tabController = TabController(length: _tabCount, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: widget.mode == 'donate'
          ? AppBar(
              title: const Text('Donate'),
              leadingWidth: 220,
              leading: OwlangsAppBarLeading(
                onTap: () => context.go(AppRouter.homeRoute),
              ),
              actions: <Widget>[
                IconButton(
                  tooltip: 'Home',
                  onPressed: () => context.go(AppRouter.homeRoute),
                  icon: const Icon(Icons.home_outlined),
                ),
              ],
            )
          : AppBar(
              title: const Text('Donate & Help'),
              leadingWidth: 220,
              leading: OwlangsAppBarLeading(
                onTap: () => context.go(AppRouter.homeRoute),
              ),
              actions: <Widget>[
                IconButton(
                  tooltip: 'Home',
                  onPressed: () => context.go(AppRouter.homeRoute),
                  icon: const Icon(Icons.home_outlined),
                ),
              ],
              bottom: TabBar(
                controller: _tabController,
                tabs: widget.mode == 'help'
                    ? const <Widget>[
                        Tab(icon: Icon(Icons.play_circle_outline), text: 'Quick Start'),
                        Tab(icon: Icon(Icons.help_outline), text: 'Help'),
                        Tab(icon: Icon(Icons.compare_arrows), text: 'Editions'),
                        Tab(icon: Icon(Icons.contact_support), text: 'Contact'),
                      ]
                    : const <Widget>[
                        Tab(icon: Icon(Icons.play_circle_outline), text: 'Quick Start'),
                        Tab(icon: Icon(Icons.help_outline), text: 'Help'),
                        Tab(icon: Icon(Icons.compare_arrows), text: 'Editions'),
                        Tab(icon: Icon(Icons.volunteer_activism), text: 'Donate'),
                        Tab(icon: Icon(Icons.contact_support), text: 'Contact'),
                      ],
              ),
            ),
      body: widget.mode == 'donate'
          ? const DonateScreen()
          : TabBarView(
              controller: _tabController,
              children: widget.mode == 'help'
                  ? const <Widget>[
                      QuickStartGuideScreen(),
                      HelpScreen(),
                      EditionComparisonScreen(),
                      ContactScreen(),
                    ]
                  : const <Widget>[
                      QuickStartGuideScreen(),
                      HelpScreen(),
                      EditionComparisonScreen(),
                      DonateScreen(),
                      ContactScreen(),
                    ],
            ),
    );
  }
}
