import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../backend_manager.dart';

final backendManagerProvider = Provider<BackendManager>((ref) => BackendManager());

final FutureProvider<bool> backendStatusProvider = FutureProvider<bool>((ref) async {
  final backendManager = ref.watch(backendManagerProvider);
  return await backendManager.startBackend();
});
