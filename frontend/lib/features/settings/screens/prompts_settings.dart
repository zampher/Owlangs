import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// 提示词设置状态管理
final StateNotifierProvider<PromptsSettingsNotifier, PromptsSettings>
    promptsSettingsProvider =
    StateNotifierProvider<PromptsSettingsNotifier, PromptsSettings>(
  (
    StateNotifierProviderRef<PromptsSettingsNotifier, PromptsSettings> ref,
  ) =>
      PromptsSettingsNotifier(),
);

class PromptsSettings {
  const PromptsSettings({
    this.translationPrompts = const <PromptTemplate>[],
    this.anonymizationPrompts = const <PromptTemplate>[],
    this.customPrompts = const <PromptTemplate>[],
    this.defaultTranslationPrompt = '',
    this.defaultAnonymizationPrompt = '',
    this.isEditing = false,
  });
  final List<PromptTemplate> translationPrompts;
  final List<PromptTemplate> anonymizationPrompts;
  final List<PromptTemplate> customPrompts;
  final String defaultTranslationPrompt;
  final String defaultAnonymizationPrompt;
  final bool isEditing;

  PromptsSettings copyWith({
    List<PromptTemplate>? translationPrompts,
    List<PromptTemplate>? anonymizationPrompts,
    List<PromptTemplate>? customPrompts,
    String? defaultTranslationPrompt,
    String? defaultAnonymizationPrompt,
    bool? isEditing,
  }) =>
      PromptsSettings(
        translationPrompts: translationPrompts ?? this.translationPrompts,
        anonymizationPrompts: anonymizationPrompts ?? this.anonymizationPrompts,
        customPrompts: customPrompts ?? this.customPrompts,
        defaultTranslationPrompt:
            defaultTranslationPrompt ?? this.defaultTranslationPrompt,
        defaultAnonymizationPrompt:
            defaultAnonymizationPrompt ?? this.defaultAnonymizationPrompt,
        isEditing: isEditing ?? this.isEditing,
      );
}

class PromptTemplate {
  const PromptTemplate({
    required this.id,
    required this.name,
    required this.content,
    required this.category,
    required this.createdAt,
    required this.updatedAt,
    this.isDefault = false,
  });
  final String id;
  final String name;
  final String content;
  final String category;
  final bool isDefault;
  final DateTime createdAt;
  final DateTime updatedAt;

  PromptTemplate copyWith({
    String? id,
    String? name,
    String? content,
    String? category,
    bool? isDefault,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) =>
      PromptTemplate(
        id: id ?? this.id,
        name: name ?? this.name,
        content: content ?? this.content,
        category: category ?? this.category,
        isDefault: isDefault ?? this.isDefault,
        createdAt: createdAt ?? this.createdAt,
        updatedAt: updatedAt ?? this.updatedAt,
      );
}

class PromptsSettingsNotifier extends StateNotifier<PromptsSettings> {
  PromptsSettingsNotifier() : super(const PromptsSettings()) {
    _initializeDefaultPrompts();
  }

  void _initializeDefaultPrompts() {
    final DateTime now = DateTime.now();

    final List<PromptTemplate> translationPrompts = <PromptTemplate>[
      PromptTemplate(
        id: '1',
        name: 'Academic Translation',
        content:
            'Please translate the following text from {source_lang} to {target_lang} while maintaining the academic tone and technical accuracy. Pay special attention to terminology consistency.',
        category: 'translation',
        isDefault: true,
        createdAt: now,
        updatedAt: now,
      ),
      PromptTemplate(
        id: '2',
        name: 'Business Translation',
        content:
            'Translate the following business document from {source_lang} to {target_lang}. Maintain professional tone and business terminology. Ensure clarity and conciseness.',
        category: 'translation',
        createdAt: now,
        updatedAt: now,
      ),
    ];

    final List<PromptTemplate> anonymizationPrompts = <PromptTemplate>[
      PromptTemplate(
        id: '3',
        name: 'Standard Anonymization',
        content:
            'Please anonymize the following text by replacing personal information with appropriate placeholders. Identify and replace names, addresses, phone numbers, and other sensitive data.',
        category: 'anonymization',
        isDefault: true,
        createdAt: now,
        updatedAt: now,
      ),
      PromptTemplate(
        id: '4',
        name: 'Medical Anonymization',
        content:
            'Anonymize this medical text by replacing patient information, medical record numbers, and other healthcare identifiers with appropriate placeholders while preserving medical terminology.',
        category: 'anonymization',
        createdAt: now,
        updatedAt: now,
      ),
    ];

    state = state.copyWith(
      translationPrompts: translationPrompts,
      anonymizationPrompts: anonymizationPrompts,
      defaultTranslationPrompt: translationPrompts.first.id,
      defaultAnonymizationPrompt: anonymizationPrompts.first.id,
    );
  }

  void addPromptTemplate(PromptTemplate template) {
    List<PromptTemplate> updatedPrompts;
    switch (template.category) {
      case 'translation':
        updatedPrompts = List<PromptTemplate>.from(state.translationPrompts);
        updatedPrompts.add(template);
        state = state.copyWith(translationPrompts: updatedPrompts);
        break;
      case 'anonymization':
        updatedPrompts = List<PromptTemplate>.from(state.anonymizationPrompts);
        updatedPrompts.add(template);
        state = state.copyWith(anonymizationPrompts: updatedPrompts);
        break;
      default:
        updatedPrompts = List<PromptTemplate>.from(state.customPrompts);
        updatedPrompts.add(template);
        state = state.copyWith(customPrompts: updatedPrompts);
    }
  }

  void updatePromptTemplate(PromptTemplate template) {
    List<PromptTemplate> updatedPrompts;
    switch (template.category) {
      case 'translation':
        updatedPrompts = state.translationPrompts
            .map((PromptTemplate p) => p.id == template.id ? template : p)
            .toList();
        state = state.copyWith(translationPrompts: updatedPrompts);
        break;
      case 'anonymization':
        updatedPrompts = state.anonymizationPrompts
            .map((PromptTemplate p) => p.id == template.id ? template : p)
            .toList();
        state = state.copyWith(anonymizationPrompts: updatedPrompts);
        break;
      default:
        updatedPrompts = state.customPrompts
            .map((PromptTemplate p) => p.id == template.id ? template : p)
            .toList();
        state = state.copyWith(customPrompts: updatedPrompts);
    }
  }

  void removePromptTemplate(String id, String category) {
    List<PromptTemplate> updatedPrompts;
    switch (category) {
      case 'translation':
        updatedPrompts = state.translationPrompts
            .where((PromptTemplate p) => p.id != id)
            .toList();
        state = state.copyWith(translationPrompts: updatedPrompts);
        break;
      case 'anonymization':
        updatedPrompts = state.anonymizationPrompts
            .where((PromptTemplate p) => p.id != id)
            .toList();
        state = state.copyWith(anonymizationPrompts: updatedPrompts);
        break;
      default:
        updatedPrompts = state.customPrompts
            .where((PromptTemplate p) => p.id != id)
            .toList();
        state = state.copyWith(customPrompts: updatedPrompts);
    }
  }

  void setDefaultTranslationPrompt(String promptId) {
    state = state.copyWith(defaultTranslationPrompt: promptId);
  }

  void setDefaultAnonymizationPrompt(String promptId) {
    state = state.copyWith(defaultAnonymizationPrompt: promptId);
  }

  void reset() {
    state = const PromptsSettings();
    _initializeDefaultPrompts();
  }
}

class PromptsSettingsScreen extends ConsumerWidget {
  const PromptsSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final PromptsSettings settings = ref.watch(promptsSettingsProvider);
    final PromptsSettingsNotifier notifier =
        ref.read(promptsSettingsProvider.notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Translation Prompts
          _buildPromptsSection(
            'Translation Prompts',
            Icons.translate,
            Colors.blue.shade700,
            settings.translationPrompts,
            settings.defaultTranslationPrompt,
            notifier.setDefaultTranslationPrompt,
            notifier.updatePromptTemplate,
            (String id) => notifier.removePromptTemplate(id, 'translation'),
          ),
          const SizedBox(height: 24),

          // Anonymization Prompts
          _buildPromptsSection(
            'Anonymization Prompts',
            Icons.security,
            Colors.orange.shade700,
            settings.anonymizationPrompts,
            settings.defaultAnonymizationPrompt,
            notifier.setDefaultAnonymizationPrompt,
            notifier.updatePromptTemplate,
            (String id) => notifier.removePromptTemplate(id, 'anonymization'),
          ),
          const SizedBox(height: 24),

          // Custom Prompts
          _buildPromptsSection(
            'Custom Prompts',
            Icons.edit,
            Colors.purple.shade700,
            settings.customPrompts,
            '',
            (String promptId) {}, // No default for custom prompts
            notifier.updatePromptTemplate,
            (String id) => notifier.removePromptTemplate(id, 'custom'),
          ),
        ],
      ),
    );
  }

  Widget _buildPromptsSection(
    String title,
    IconData icon,
    Color color,
    List<PromptTemplate> prompts,
    String defaultPromptId,
    Function(String) onSetDefault,
    Function(PromptTemplate) onUpdate,
    Function(String) onRemove,
  ) =>
      Card(
        elevation: 4,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(icon, color: color),
                  const SizedBox(width: 8),
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  const Spacer(),
                  ElevatedButton.icon(
                    onPressed: () => _showAddPromptDialog(onUpdate),
                    icon: const Icon(Icons.add),
                    label: const Text('Add Prompt'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: color,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (prompts.isEmpty)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: Text(
                      'No prompts available.\nAdd your first prompt template.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.grey,
                      ),
                    ),
                  ),
                )
              else
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: prompts.length,
                  itemBuilder: (context, index) {
                    final prompt = prompts[index];
                    return _buildPromptCard(
                      context,
                      prompt,
                      defaultPromptId,
                      onSetDefault,
                      onUpdate,
                      onRemove,
                    );
                  },
                ),
            ],
          ),
        ),
      );

  Widget _buildPromptCard(
    BuildContext context,
    PromptTemplate prompt,
    String defaultPromptId,
    Function(String) onSetDefault,
    Function(PromptTemplate) onUpdate,
    Function(String) onRemove,
  ) {
    final bool isDefault = prompt.id == defaultPromptId;

    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        title: Row(
          children: <Widget>[
            Expanded(
              child: Text(
                prompt.name,
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
            if (isDefault)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.green.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'DEFAULT',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: Colors.green.shade700,
                  ),
                ),
              ),
          ],
        ),
        subtitle: Text(
          'Created: ${_formatDate(prompt.createdAt)}',
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Prompt Content:',
                  style: TextStyle(
                    fontWeight: FontWeight.w500,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceContainerLowest,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: Theme.of(context).colorScheme.outlineVariant,
                    ),
                  ),
                  child: Text(
                    prompt.content,
                    style: const TextStyle(fontSize: 14),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: <Widget>[
                    if (!isDefault)
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => onSetDefault(prompt.id),
                          icon: const Icon(Icons.star),
                          label: const Text('Set as Default'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.blue.shade700,
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ),
                    if (!isDefault) const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () =>
                            _showEditPromptDialog(prompt, onUpdate),
                        icon: const Icon(Icons.edit),
                        label: const Text('Edit'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => onRemove(prompt.id),
                        icon: const Icon(Icons.delete),
                        label: const Text('Delete'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.red.shade700,
                          side: BorderSide(color: Colors.red.shade300),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) => '${date.day}/${date.month}/${date.year}';

  void _showAddPromptDialog(Function(PromptTemplate) onUpdate) {
    // TODO: Implement add prompt dialog
  }

  void _showEditPromptDialog(
    PromptTemplate prompt,
    Function(PromptTemplate) onUpdate,
  ) {
    // TODO: Implement edit prompt dialog
  }
}
