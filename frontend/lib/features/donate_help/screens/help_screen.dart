import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../widgets/help_qa_content.dart';

/// Official documentation URL (detailed help).
const String kHelpDocumentationUrl = 'https://www.owlangs.org';

/// Help screen: documentation and Q&A content.
class HelpScreen extends StatefulWidget {
  const HelpScreen({super.key});

  @override
  State<HelpScreen> createState() => _HelpScreenState();
}

class _HelpScreenState extends State<HelpScreen> {
  final ScrollController _scrollController = ScrollController();
  late final FocusNode _headerSelectionFocusNode;
  bool _helpTocVisible = true;
  final Map<String, GlobalKey> _helpSectionKeys =
      <String, GlobalKey<State<StatefulWidget>>>{
    for (final String id in kHelpQaSectionIds) id: GlobalKey(),
  };

  @override
  void initState() {
    super.initState();
    _headerSelectionFocusNode = FocusNode();
  }

  @override
  void dispose() {
    _headerSelectionFocusNode.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollHelpToSection(String sectionId) {
    final GlobalKey<State<StatefulWidget>>? key = _helpSectionKeys[sectionId];
    if (key?.currentContext == null) return;
    Scrollable.ensureVisible(
      key!.currentContext!,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Center: Q&A content (selectable, copyable)
          Expanded(
            child: Scrollbar(
              controller: _scrollController,
              thumbVisibility: true,
              child: SingleChildScrollView(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(24, 24, 16, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    _buildHelpHeader(context),
                    const SizedBox(height: 24),
                    HelpQaContent(sectionKeys: _helpSectionKeys),
                  ],
                ),
              ),
            ),
          ),
          // TOC: collapsible navigation
          _buildHelpToc(context),
        ],
      );

  Widget _buildHelpHeader(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        Icon(Icons.help_outline, color: colorScheme.primary, size: 28),
        const SizedBox(width: 12),
        Expanded(
          child: SelectableRegion(
            focusNode: _headerSelectionFocusNode,
            selectionControls: materialTextSelectionControls,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Help & Q&A',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: colorScheme.primary,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Documentation and quick start.',
                  style: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: <Widget>[
                    Text(
                      'For more detailed documentation, visit ',
                      style: TextStyle(
                        color: colorScheme.onSurfaceVariant,
                        fontSize: 13,
                      ),
                    ),
                    MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: GestureDetector(
                        onTap: () async {
                          final Uri uri = Uri.parse(kHelpDocumentationUrl);
                          if (await canLaunchUrl(uri)) {
                            await launchUrl(
                              uri,
                              mode: LaunchMode.externalApplication,
                            );
                          }
                        },
                        child: Text(
                          'www.owlangs.org',
                          style: TextStyle(
                            fontSize: 13,
                            color: colorScheme.primary,
                            decoration: TextDecoration.underline,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHelpToc(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    if (!_helpTocVisible) {
      return Material(
        color: colorScheme.surfaceContainerLow.withValues(alpha: 0.5),
        child: InkWell(
          onTap: () => setState(() => _helpTocVisible = true),
          child: Tooltip(
            message: 'Show table of contents',
            child: Center(
              child: Icon(
                Icons.list,
                color: colorScheme.onSurfaceVariant,
                size: 28,
              ),
            ),
          ),
        ),
      );
    }
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow.withValues(alpha: 0.5),
        border: Border(
          left: BorderSide(color: colorScheme.outlineVariant.withOpacity(0.5)),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: <Widget>[
                Text(
                  'Contents',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: colorScheme.primary,
                      ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.chevron_right),
                  iconSize: 20,
                  onPressed: () => setState(() => _helpTocVisible = false),
                  tooltip: 'Hide table of contents',
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: kHelpQaSectionIds.length,
              itemBuilder: (BuildContext context, int index) {
                final String id = kHelpQaSectionIds[index];
                final String title = kHelpQaSectionTitles[index];
                return ListTile(
                  dense: true,
                  title: Text(
                    title,
                    style: TextStyle(
                      fontSize: 13,
                      color: colorScheme.onSurface,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () => _scrollHelpToSection(id),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
