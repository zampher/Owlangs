// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/flow.dart';

class FlowContextNotifier extends StateNotifier<FlowContext> {
  FlowContextNotifier() : super(const FlowContext());

  void setSource(FlowSource source) {
    state = state.copyWith(source: source);
  }

  void setAnonymize(AnonymizeArtifacts anonymize) {
    state = state.copyWith(anonymize: anonymize);
  }

  void setGlossary(GlossaryArtifacts glossary) {
    state = state.copyWith(glossary: glossary);
  }

  void setTranslate(TranslateArtifacts translate) {
    state = state.copyWith(translate: translate);
  }

  void setReview(ReviewArtifacts review) {
    state = state.copyWith(review: review);
  }

  void setDeAnonymize(DeAnonymizeArtifacts deAnonymize) {
    state = state.copyWith(deAnonymize: deAnonymize);
  }

  void reset() {
    state = const FlowContext();
  }
}

final StateNotifierProviderFamily<FlowContextNotifier, FlowContext, String>
    flowProviderFamily =
    StateNotifierProvider.family<FlowContextNotifier, FlowContext, String>((
  StateNotifierProviderRef<FlowContextNotifier, FlowContext> ref,
  String flowId,
) {
  // Keep provider alive to avoid reloading when switching flows
  ref.keepAlive();
  // Each flowId has its own FlowContext container
  return FlowContextNotifier();
});
