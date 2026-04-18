import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../app/app_router.dart';
import '../../contact/screens/contact_screen.dart';
import 'help_screen.dart';
import 'edition_comparison_screen.dart';
import 'quick_start_guide_screen.dart';
import 'donate_screen.dart';

/// Main screen managing Donate, Help, and Contact tabs.
class DonateHelpContactScreen extends StatefulWidget {
  const DonateHelpContactScreen({super.key});

  @override
  State<DonateHelpContactScreen> createState() =>
      _DonateHelpContactScreenState();
}

class _DonateHelpContactScreenState extends State<DonateHelpContactScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    // OpenSource edition: activation is removed, so the tab count decreases.
    _tabController = TabController(length: 5, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Optionally honor initialTab index passed via GoRouter.extra
    final extra = GoRouterState.of(context).extra;
    if (extra is Map && extra['initialTab'] is int) {
      final int idx = extra['initialTab'] as int;
      // Compatibility:
      // Old tabs (before removing Activation): 0 Quick Start, 1 Help, 2 Editions,
      // 3 Donate, 4 Activation, 5 Contact.
      // New tabs: 0 Quick Start, 1 Help, 2 Editions, 3 Donate, 4 Contact.
      int mappedIdx = idx;
      if (idx == 4) mappedIdx = 3; // Activation -> Donate
      if (idx == 5) mappedIdx = 4; // Contact stays Contact
      if (mappedIdx >= 0 && mappedIdx < _tabController.length) {
        _tabController.index = mappedIdx;
      }
    }

    return Scaffold(
      appBar: AppBar(
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
          tabs: const <Widget>[
            Tab(icon: Icon(Icons.play_circle_outline), text: 'Quick Start'),
            Tab(icon: Icon(Icons.help_outline), text: 'Help'),
            Tab(icon: Icon(Icons.compare_arrows), text: 'Editions'),
            Tab(icon: Icon(Icons.volunteer_activism), text: 'Donate'),
            Tab(icon: Icon(Icons.contact_support), text: 'Contact'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const <Widget>[
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
