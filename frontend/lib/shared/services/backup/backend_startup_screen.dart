import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/app_config.dart';
import 'backend_provider.dart';

class BackendStartupScreen extends ConsumerWidget {
  const BackendStartupScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final backendStatus = ref.watch(backendStatusProvider);

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            // 应用图标
            Image.asset(
              'images/logos/owlangs_logo.png',
              width: 100,
              height: 100,
            ),
            const SizedBox(height: 24),
            
            // 应用名称
            const Text(
              AppConfig.appName,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 32),
            
            // 启动状态
            backendStatus.when(
              loading: () => Column(
                children: <Widget>[
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  Text(
                    'Starting backend service...',
                    style: TextStyle(
                      color: Theme.of(context).textTheme.bodyMedium?.color,
                    ),
                  ),
                ],
              ),
              error: (error, stack) => Column(
                children: <Widget>[
                  const Icon(
                    Icons.error_outline,
                    color: Colors.red,
                    size: 48,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Failed to start backend',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Please check if Python is installed',
                    style: TextStyle(
                      color: Theme.of(context).textTheme.bodyMedium?.color,
                    ),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: () {
                      // 重新尝试启动
                      ref.refresh(backendStatusProvider);
                    },
                    child: const Text('Retry'),
                  ),
                ],
              ),
              data: (success) {
                if (success) {
                  // 后端启动成功，延迟一小段时间后进入应用
                  Future.delayed(const Duration(milliseconds: 500), () {
                    // 导航到主应用
                  });
                  
                  return Column(
                    children: <Widget>[
                      const Icon(
                        Icons.check_circle_outline,
                        color: Colors.green,
                        size: 48,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Backend started successfully',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  );
                } else {
                  return Column(
                    children: <Widget>[
                      const Icon(
                        Icons.error_outline,
                        color: Colors.red,
                        size: 48,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Failed to start backend',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Please check if Python is installed',
                        style: TextStyle(
                          color: Theme.of(context).textTheme.bodyMedium?.color,
                        ),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: () {
                          // 重新尝试启动
                          ref.refresh(backendStatusProvider);
                        },
                        child: const Text('Retry'),
                      ),
                    ],
                  );
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}
