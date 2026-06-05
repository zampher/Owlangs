// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:io' if (dart.library.html) '../../../shared/utils/io_stub.dart' as io;

import 'package:archive/archive.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:go_router/go_router.dart';

import '../../../app/app_router.dart';
import '../../../core/utils/file_picker_helper.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/file_format_service.dart';
import '../../../features/settings/screens/ai_platform_settings.dart'
    show aiPlatformSettingsProvider;
import '../../translation/widgets/translation_quick_settings.dart'
    show translationQuickSettingsProvider;
import '../../../shared/providers/settings_provider.dart'
    show globalSettingsProvider;
import '../models/discovered_file.dart';
import '../services/batch_submission_service.dart';
import '../utils/zip_filename_utils.dart';
import 'batch_quick_settings_panel.dart';

/// Reusable body for batch file upload — used by [BatchUploadScreen].
///
/// Three phases:
///   1. Source selection (folder or ZIP)
///   2. File review with checkboxes
///   3. Submission progress
class BatchUploadPageBody extends ConsumerStatefulWidget {
  const BatchUploadPageBody({super.key, this.showAppBar = false, this.initialSource});

  /// When true, the title bar is omitted (Scaffold AppBar provides it).
  final bool showAppBar;

  /// If 'folder' or 'zip', auto-trigger the corresponding source picker on startup.
  final String? initialSource;

  @override
  ConsumerState<BatchUploadPageBody> createState() => _BatchUploadPageBodyState();
}

enum _DialogPhase { chooseSource, reviewFiles, submitting, done }

class _BatchUploadPageBodyState extends ConsumerState<BatchUploadPageBody> {
  _DialogPhase _phase = _DialogPhase.chooseSource;
  final List<DiscoveredFile> _files = [];
  final List<String> _legacyFileNames = [];
  String? _sourceType; // 'single', 'folder', or 'zip'
  bool _isAppending = false; // true when adding more files to existing list

  // ── Batch-local quick settings (initialized from global providers) ──
  String _batchToLang = 'en';
  String _batchPlatformKey = 'openai';
  double? _batchTemperature;
  String _batchPromptMode = 'off';
  String? _batchPromptStyle;
  String? _batchTaskNote;
  List<String> _batchSelectedGlossaries = <String>[];
  String _batchParsingEngine = 'mineru';
  bool _batchToLangUserModified = false;

  final BatchSubmissionService _submissionService = BatchSubmissionService();
  StreamSubscription<BatchSubmissionProgress>? _progressSub;
  int _completed = 0;
  int _total = 0;
  int _succeeded = 0;
  int _failed = 0;
  List<FileSubmissionStatus> _statuses = [];

  @override
  void initState() {
    super.initState();
    if (widget.initialSource != null) {
      // Skip the source-selection phase entirely when auto-picking
      _sourceType = widget.initialSource;
      _phase = _DialogPhase.reviewFiles;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        if (widget.initialSource == 'folder') {
          _pickFolder();
        } else if (widget.initialSource == 'zip') {
          _pickZip();
        } else if (widget.initialSource == 'single') {
          _pickSingleFile();
        }
      });
    }
  }

  @override
  void dispose() {
    _progressSub?.cancel();
    super.dispose();
  }

  // ── Source selection ──────────────────────────────────────────────

  Future<void> _addMoreFiles() async {
    if (_sourceType == null) return;
    _isAppending = true;
    final l10n = AppLocalizations.of(context)!;
    final source = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(l10n.batchUploadSelectSourceHint),
        children: [
          _SourceOptionCard(
            icon: Icons.insert_drive_file,
            title: l10n.batchUploadSelectSingleFile,
            subtitle: l10n.batchUploadSingleFileDescription,
            onTap: () => Navigator.of(ctx).pop('single'),
          ),
          const SizedBox(height: 8),
          _SourceOptionCard(
            icon: Icons.folder,
            title: l10n.batchUploadSelectFolder,
            subtitle: l10n.batchUploadFolderDescription,
            onTap: () => Navigator.of(ctx).pop('folder'),
          ),
          const SizedBox(height: 8),
          _SourceOptionCard(
            icon: Icons.folder_zip_outlined,
            title: l10n.batchUploadSelectZip,
            subtitle: l10n.batchUploadZipDescription,
            onTap: () => Navigator.of(ctx).pop('zip'),
          ),
        ],
      ),
    );
    if (source == null || !mounted) return;
    switch (source) {
      case 'folder':
        await _pickFolder();
      case 'zip':
        await _pickZip();
      case 'single':
        await _pickSingleFile();
    }
  }

  Future<void> _pickFolder() async {
    _sourceType = 'folder';
    final l10n = AppLocalizations.of(context)!;
    if (kIsWeb) {
      // Web: use webkitdirectory to get files directly.
      final result = await FilePickerHelper.pickDirectoryFiles(
        dialogTitle: l10n.batchUploadFolderPickerTitle,
      );
      if (result == null || result.isEmpty || !mounted) return;
      _processWebDirectoryFiles(result);
    } else {
      // Desktop: get directory path, then scan with dart:io.
      final path = await FilePickerHelper.pickDirectory(
        dialogTitle: l10n.batchUploadFolderPickerTitle,
      );
      if (path == null || !mounted) return;
      _scanFolder(path);
    }
  }

  void _processWebDirectoryFiles(List<PlatformFile> platformFiles) {
    final formats = FileFormatService().getAllFormats();
    final files = <DiscoveredFile>[];
    final legacyNames = <String>[];

    debugPrint('[BatchUpload] _processWebDirectoryFiles: ${platformFiles.length} platform files');

    for (final pf in platformFiles) {
      final name = pf.name; // should be webkitRelativePath, e.g. "subdir/file.docx"
      debugPrint('[BatchUpload]   pf.name=$name, size=${pf.size}, hasBytes=${pf.bytes != null}');
      if (name.endsWith('/')) continue;
      final ext = name.split('.').last.toLowerCase();

      // Nested ZIP: extract and add contents, using ZIP name as path prefix
      if (ext == 'zip' && pf.bytes != null && pf.bytes!.isNotEmpty) {
        final lastSlash = name.lastIndexOf('/');
        final zipRelativeDir = lastSlash > 0 ? name.substring(0, lastSlash) : null;
        try {
          _scanNestedZip(pf.bytes!, name.split('/').last, zipRelativeDir, files, legacyNames, formats);
        } catch (_) {
          // skip corrupted/invalid nested zips silently
        }
        continue;
      }

      if (FileFormatService().isLegacyFormat(ext)) {
        legacyNames.add(name.split('/').last);
        continue;
      }
      if (!formats.contains(ext)) continue;
      final lastSlash = name.lastIndexOf('/');
      final fileName = lastSlash >= 0 ? name.substring(lastSlash + 1) : name;
      final relativeDir = lastSlash > 0 ? name.substring(0, lastSlash) : null;
      files.add(DiscoveredFile(
        fileName: fileName,
        fileSizeBytes: pf.size,
        fileBytes: pf.bytes,
        relativePath: relativeDir,
        isSelected: true,
      ));
    }
    _onFilesDiscovered(files, legacyNames);
  }

  void _scanFolder(String path) {
    final l10n = AppLocalizations.of(context)!;
    try {
      final dir = io.Directory(path);
      final entities = dir.listSync(recursive: true);
      final formats = FileFormatService().getAllFormats();
      final files = <DiscoveredFile>[];
      final legacyNames = <String>[];

      // Normalize and extract folder name to match web's webkitRelativePath
      // behavior which includes the selected folder in the relative path.
      final rootPath = path.replaceAll('\\', '/');
      final folderName = rootPath.split('/').last;

      for (final entity in entities) {
        if (entity is! io.File) continue;
        final entityPath = entity.path.replaceAll('\\', '/');
        final rawRelPath = entityPath.startsWith('$rootPath/')
            ? entityPath.substring(rootPath.length + 1)
            : entityPath;
        // Prepend folder name so relative paths include the selected directory
        // root, matching web's webkitRelativePath format.
        final relPath = '$folderName/$rawRelPath';
        final lastSlash = relPath.lastIndexOf('/');
        final fileName = lastSlash >= 0 ? relPath.substring(lastSlash + 1) : relPath;
        final ext = fileName.split('.').last.toLowerCase();

        // Nested ZIP: extract and add contents, using ZIP name as path prefix
        if (ext == 'zip') {
          final zipRelativeDir = lastSlash > 0 ? relPath.substring(0, lastSlash) : null;
          try {
            final zipBytes = entity.readAsBytesSync();
            _scanNestedZip(zipBytes, fileName, zipRelativeDir, files, legacyNames, formats);
          } catch (_) {
            // skip corrupted/invalid nested zips silently
          }
          continue;
        }

        if (FileFormatService().isLegacyFormat(ext)) {
          legacyNames.add(fileName);
          continue;
        }
        if (!formats.contains(ext)) continue;
        final stat = entity.statSync();
        final relativeDir = lastSlash > 0 ? relPath.substring(0, lastSlash) : null;
        files.add(DiscoveredFile(
          fileName: fileName,
          fileSizeBytes: stat.size,
          filePath: entity.path,
          relativePath: relativeDir,
          isSelected: true,
        ));
      }
      _onFilesDiscovered(files, legacyNames);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.batchUploadScanFolderError(e.toString()))),
      );
    }
  }

  Future<void> _pickZip() async {
    _sourceType = 'zip';
    final l10n = AppLocalizations.of(context)!;
    final result = await FilePickerHelper.pickFiles(
      allowedExtensions: ['zip'],
      type: FileType.custom,
      dialogTitle: l10n.batchUploadZipPickerTitle,
    );
    if (result == null || result.files.isEmpty || !mounted) return;
    final pf = result.files.first;
    List<int> zipBytes;
    if (pf.bytes != null && pf.bytes!.isNotEmpty) {
      zipBytes = pf.bytes!;
    } else if (pf.path != null && pf.path!.isNotEmpty) {
      zipBytes = await io.File(pf.path!).readAsBytes();
    } else {
      return;
    }
    _scanZip(zipBytes);
  }

  Future<void> _pickSingleFile() async {
    _sourceType = 'single';
    final l10n = AppLocalizations.of(context)!;
    final result = await FilePickerHelper.pickFiles(
      dialogTitle: l10n.batchUploadSelectSingleFile,
    );
    if (result == null || result.files.isEmpty || !mounted) return;

    final pf = result.files.first;
    final ext = pf.name.split('.').last.toLowerCase();
    final formats = FileFormatService().getAllFormats();
    final legacyNames = <String>[];

    if (FileFormatService().isLegacyFormat(ext)) {
      legacyNames.add(pf.name);
      _onFilesDiscovered([], legacyNames);
      return;
    }
    if (!formats.contains(ext)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${pf.name}: ${l10n.batchUploadNoSupportedFiles}')),
      );
      return;
    }

    final files = <DiscoveredFile>[
      DiscoveredFile(
        fileName: pf.name,
        fileSizeBytes: pf.size,
        fileBytes: pf.bytes,
        isSelected: true,
      ),
    ];
    _onFilesDiscovered(files, legacyNames);
  }

  void _scanZip(List<int> zipBytes) {
    final l10n = AppLocalizations.of(context)!;
    try {
      final archive = ZipDecoder().decodeBytes(zipBytes);
      final formats = FileFormatService().getAllFormats();
      final files = <DiscoveredFile>[];
      final legacyNames = <String>[];

      // The archive package always decodes ZIP filenames as UTF-8, but ZIPs
      // created on Japanese Windows encode filenames in Shift-JIS.  Recover
      // the original bytes from the Latin-1 fallback strings and re-decode
      // as Shift-JIS.
      final garbledNames = archive.map((e) => e.name).toList();
      final correctNames = correctZipFilenames(garbledNames, zipBytes);
      if (correctNames.length == archive.length) {
        for (int i = 0; i < archive.length; i++) {
          archive[i].name = correctNames[i];
        }
      }

      for (final entry in archive) {
        if (entry.isFile) {
          final name = entry.name;
          // Skip directories and macOS metadata files.
          if (name.endsWith('/')) continue;
          if (name.startsWith('__MACOSX/')) continue;

          final lastSlash = name.lastIndexOf('/');
          final fileName = lastSlash >= 0 ? name.substring(lastSlash + 1) : name;
          final ext = fileName.split('.').last.toLowerCase();
          final relativeDir = lastSlash > 0 ? name.substring(0, lastSlash) : null;

          // Nested ZIP: extract and add contents, using ZIP name as path prefix
          if (ext == 'zip') {
            try {
              _scanNestedZip(
                entry.content as List<int>,
                fileName,
                relativeDir,
                files,
                legacyNames,
                formats,
              );
            } catch (_) {
              // skip corrupted/invalid nested zips silently
            }
            continue;
          }

          if (FileFormatService().isLegacyFormat(ext)) {
            legacyNames.add(fileName);
            continue;
          }
          if (!formats.contains(ext)) continue;
          files.add(DiscoveredFile(
            fileName: fileName,
            fileSizeBytes: entry.size,
            fileBytes: entry.content,
            relativePath: relativeDir,
            isSelected: true,
          ));
        }
      }
      _onFilesDiscovered(files, legacyNames);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.batchUploadReadZipError(e.toString()))),
      );
    }
  }

  /// Extract files from a nested ZIP (found inside a folder or parent ZIP).
  ///
  /// [zipFileName] is used as the starting path segment for relative paths.
  /// [parentRelativePath] is prepended to all extracted file paths.
  void _scanNestedZip(
    List<int> zipBytes,
    String zipFileName,
    String? parentRelativePath,
    List<DiscoveredFile> files,
    List<String> legacyNames,
    List<String> formats,
  ) {
    final archive = ZipDecoder().decodeBytes(zipBytes);
    final zipBaseName = zipFileName.endsWith('.zip')
        ? zipFileName.substring(0, zipFileName.length - 4)
        : zipFileName;

    // Apply same Shift-JIS filename fix on nested ZIPs
    final garbledNames = archive.map((e) => e.name).toList();
    final correctNames = correctZipFilenames(garbledNames, zipBytes);
    if (correctNames.length == archive.length) {
      for (int i = 0; i < archive.length; i++) {
        archive[i].name = correctNames[i];
      }
    }

    for (final entry in archive) {
      if (!entry.isFile) continue;
      final name = entry.name;
      if (name.endsWith('/')) continue;
      if (name.startsWith('__MACOSX/')) continue;

      final ext = name.split('.').last.toLowerCase();
      if (FileFormatService().isLegacyFormat(ext)) {
        legacyNames.add(name.split('/').last);
        continue;
      }
      if (!formats.contains(ext)) continue;

      final lastSlash = name.lastIndexOf('/');
      final fileName = lastSlash >= 0 ? name.substring(lastSlash + 1) : name;
      final entryDir = lastSlash > 0 ? name.substring(0, lastSlash) : null;

      // Build full relative path: [parent]/[zip base name]/[entry dir]
      String? fullRelativePath;
      if (parentRelativePath != null && parentRelativePath.isNotEmpty) {
        fullRelativePath = entryDir != null
            ? '$parentRelativePath/$zipBaseName/$entryDir'
            : '$parentRelativePath/$zipBaseName';
      } else {
        fullRelativePath = entryDir != null
            ? '$zipBaseName/$entryDir'
            : zipBaseName;
      }

      files.add(DiscoveredFile(
        fileName: fileName,
        fileSizeBytes: entry.size,
        fileBytes: entry.content,
        relativePath: fullRelativePath,
        isSelected: true,
      ));
    }
  }

  void _onFilesDiscovered(List<DiscoveredFile> files, [List<String> legacyNames = const []]) {
    final bool append = _isAppending;
    _isAppending = false;

    // Dedup when appending: skip files already in the list.
    final List<DiscoveredFile> toAdd;
    if (append) {
      final existingNames = _files.map((f) => f.fileName).toSet();
      toAdd = files.where((f) => !existingNames.contains(f.fileName)).toList();
    } else {
      toAdd = files;
    }

    // Initialize batch-local settings from global providers (only on first load).
    if (!append) {
      final qs = ref.read(translationQuickSettingsProvider);
      final aiSettings = ref.read(aiPlatformSettingsProvider);
      final gs = ref.read(globalSettingsProvider);

      final withPath = files.where((f) => f.relativePath != null && f.relativePath!.isNotEmpty).length;
      debugPrint('[BatchUpload] Discovered ${files.length} files, $withPath with relative paths');
      for (final f in files) {
        if (f.relativePath != null && f.relativePath!.isNotEmpty) {
          debugPrint('[BatchUpload]   ${f.relativePath}/${f.fileName}');
        }
      }

      setState(() {
        _files
          ..clear()
          ..addAll(toAdd);
        _legacyFileNames
          ..clear()
          ..addAll(legacyNames);
        _batchToLang = qs.toLang;
        _batchPlatformKey = aiSettings.defaultPlatform;
        _batchTemperature = qs.temperature;
        _batchPromptMode = qs.promptMode;
        _batchPromptStyle = qs.promptStyle;
        _batchTaskNote = qs.taskNote;
        _batchSelectedGlossaries = List<String>.from(qs.selectedGlossaries);
        _batchParsingEngine = gs.parsingEngine;
        _phase = files.isEmpty ? _DialogPhase.chooseSource : _DialogPhase.reviewFiles;
      });
    } else {
      final skipped = files.length - toAdd.length;
      setState(() {
        _files.addAll(toAdd);
        if (legacyNames.isNotEmpty) {
          _legacyFileNames.addAll(legacyNames);
        }
      });
      if (skipped > 0 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Skipped $skipped duplicate file(s)'),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
    if (files.isEmpty && legacyNames.isNotEmpty && mounted) {
      // Only legacy-format files found — show specific conversion message.
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.batchUploadLegacyFormatsFound(
              legacyNames.join(', '),
            ),
          ),
          duration: const Duration(seconds: 5),
        ),
      );
    } else if (files.isNotEmpty && legacyNames.isNotEmpty && mounted) {
      // Mix of supported and legacy files — show brief hint.
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.batchUploadLegacyFormatsSkipped(
              legacyNames.length.toString(),
            ),
          ),
          duration: const Duration(seconds: 4),
        ),
      );
    } else if (files.isEmpty && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.batchUploadNoSupportedFiles),
        ),
      );
    }
  }

  // ── Phase 2: File review ──────────────────────────────────────────

  void _toggleSelectAll() {
    final anyUnselected = _files.any((f) => !f.isSelected);
    setState(() {
      for (final f in _files) {
        f.isSelected = anyUnselected;
      }
    });
  }

  int get _selectedCount => _files.where((f) => f.isSelected).length;

  // ── Phase 3: Submission ────────────────────────────────────────────

  Future<void> _startSubmission() async {
    final selected = _files.where((f) => f.isSelected).toList();
    if (selected.isEmpty) return;

    // If user hasn't explicitly changed the target language, ask for confirmation.
    if (!_batchToLangUserModified && mounted) {
      final l10n = AppLocalizations.of(context)!;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(l10n.batchUploadConfirmLangTitle),
          content: Text(l10n.batchUploadConfirmLangMessage(_langDisplayName(l10n, _batchToLang))),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: Text(l10n.commonCancel),
            ),
            FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              child: Text(l10n.commonOk),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
    }

    // Build base payload from batch-local settings.
    final Map<String, dynamic> basePayload = <String, dynamic>{
      'to_lang': _batchToLang,
      'from_lang': 'auto',
      'prompt_mode': _batchPromptMode,
      if (_batchPromptStyle != null) 'prompt_style': _batchPromptStyle,
      if (_batchTaskNote != null && _batchTaskNote!.isNotEmpty)
        'custom_note': _batchTaskNote,
      // MinerU setting for the extraction phase.
      'convert_engine': _batchParsingEngine,
    };

    // Add AI platform info from batch-local platform key.
    try {
      final aiSettings = ref.read(aiPlatformSettingsProvider);
      if (_batchPlatformKey.isNotEmpty) {
        basePayload['platform_key'] = _batchPlatformKey;
        final platform = aiSettings.platforms[_batchPlatformKey];
        if (platform != null) {
          basePayload['base_url'] = platform.url;
          basePayload['model_id'] = platform.model;
          if (platform.apiKey != null && platform.apiKey!.isNotEmpty) {
            basePayload['api_key'] = platform.apiKey;
          }
          basePayload['temperature'] =
              _batchTemperature ?? platform.temperature;
        }
      }
    } catch (_) {
      // AI settings not ready, backend will use defaults.
    }

    // Include glossaries if any are selected.
    if (_batchSelectedGlossaries.isNotEmpty) {
      basePayload['glossary_ids'] = _batchSelectedGlossaries;
    }

    setState(() {
      _phase = _DialogPhase.submitting;
      _total = selected.length;
      _completed = 0;
      _succeeded = 0;
      _failed = 0;
      _statuses = selected
          .map((f) => FileSubmissionStatus(fileName: f.fileName))
          .toList();
    });

    _progressSub = _submissionService
        .submitBatch(files: selected, basePayload: basePayload)
        .listen((progress) {
      if (!mounted) return;
      setState(() {
        _completed = progress.completed;
        final statusIndex = _statuses.indexWhere(
            (s) => s.fileName == progress.currentFileName);
        if (statusIndex >= 0) {
          _statuses[statusIndex] = FileSubmissionStatus(
            fileName: progress.currentFileName,
            state: progress.isSuccess
                ? FileSubmissionState.done
                : FileSubmissionState.failed,
            errorMessage: progress.errorMessage,
          );
        }
        if (progress.isSuccess) {
          _succeeded++;
        } else {
          _failed++;
        }
      });
    }, onDone: () {
      if (!mounted) return;
      setState(() {
        _phase = _DialogPhase.done;
      });
    }, onError: (e) {
      if (!mounted) return;
      setState(() {
        _phase = _DialogPhase.done;
      });
    });

    // Navigate to task queue after queuing tasks.
    if (mounted) {
      Navigator.of(context).pop();
      context.push(AppRouter.translationQueueRoute);
    }
  }

  void _cancelSubmission() {
    _submissionService.cancel();
    _progressSub?.cancel();
  }

  /// Returns the localized display name for a language code.
  String _langDisplayName(AppLocalizations l10n, String code) {
    return switch (code) {
      'ar' => l10n.translationLangArabic,
      'bn' => l10n.translationLangBengali,
      'ca' => l10n.translationLangCatalan,
      'zh' => l10n.translationLangChinese,
      'zh-TW' => l10n.translationLangChineseTraditional,
      'cs' => l10n.translationLangCzech,
      'hr' => l10n.translationLangCroatian,
      'da' => l10n.translationLangDanish,
      'nl' => l10n.translationLangDutch,
      'en' => l10n.translationLangEnglish,
      'fil' => l10n.translationLangFilipino,
      'fi' => l10n.translationLangFinnish,
      'fr' => l10n.translationLangFrench,
      'de' => l10n.translationLangGerman,
      'el' => l10n.translationLangGreek,
      'he' => l10n.translationLangHebrew,
      'hi' => l10n.translationLangHindi,
      'it' => l10n.translationLangItalian,
      'ja' => l10n.translationLangJapanese,
      'ko' => l10n.translationLangKorean,
      'km' => l10n.translationLangKhmer,
      'lt' => l10n.translationLangLithuanian,
      'mk' => l10n.translationLangMacedonian,
      'ms' => l10n.translationLangMalay,
      'nb' => l10n.translationLangNorwegian,
      'pl' => l10n.translationLangPolish,
      'pt' => l10n.translationLangPortuguese,
      'ro' => l10n.translationLangRomanian,
      'ru' => l10n.translationLangRussian,
      'sl' => l10n.translationLangSlovenian,
      'es' => l10n.translationLangSpanish,
      'sv' => l10n.translationLangSwedish,
      'th' => l10n.translationLangThai,
      'tr' => l10n.translationLangTurkish,
      'uk' => l10n.translationLangUkrainian,
      'vi' => l10n.translationLangVietnamese,
      _ => code,
    };
  }

  /// Start batch format conversion for selected files (parse + convert, no translation).
  Future<void> _startConversion() async {
    final selected = _files.where((f) => f.isSelected).toList();
    if (selected.isEmpty) return;

    // Build payload for conversion-only tasks.
    final Map<String, dynamic> basePayload = <String, dynamic>{
      'skip_translate': true,
      'to_lang': _batchToLang,
      'convert_engine': _batchParsingEngine,
    };

    setState(() {
      _phase = _DialogPhase.submitting;
      _total = selected.length;
      _completed = 0;
      _succeeded = 0;
      _failed = 0;
      _statuses = selected
          .map((f) => FileSubmissionStatus(fileName: f.fileName))
          .toList();
    });

    _progressSub = _submissionService
        .submitBatch(files: selected, basePayload: basePayload)
        .listen((progress) {
      if (!mounted) return;
      setState(() {
        _completed = progress.completed;
        final statusIndex = _statuses.indexWhere(
            (s) => s.fileName == progress.currentFileName);
        if (statusIndex >= 0) {
          _statuses[statusIndex] = FileSubmissionStatus(
            fileName: progress.currentFileName,
            state: progress.isSuccess
                ? FileSubmissionState.done
                : FileSubmissionState.failed,
            errorMessage: progress.errorMessage,
          );
        }
        if (progress.isSuccess) {
          _succeeded++;
        } else {
          _failed++;
        }
      });
    }, onDone: () {
      if (!mounted) return;
      setState(() {
        _phase = _DialogPhase.done;
      });
    }, onError: (e) {
      if (!mounted) return;
      setState(() {
        _phase = _DialogPhase.done;
      });
    });

    // Navigate to task queue after queuing tasks.
    if (mounted) {
      Navigator.of(context).pop();
      context.push(AppRouter.translationQueueRoute);
    }
  }

  // ── Toolbar ──────────────────────────────────────────────────────────

  Widget _buildBatchToolbar(AppLocalizations l10n, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      constraints: const BoxConstraints(minHeight: 36, maxHeight: 36),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(color: theme.dividerColor),
        ),
      ),
      child: Row(
        children: <Widget>[
          // Add more files to the current batch
          TextButton.icon(
            onPressed: _addMoreFiles,
            icon: const Icon(Icons.add, size: 16),
            label: Text(
              l10n.batchUploadAddFiles,
              style: const TextStyle(fontSize: 12),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
          ),
          const Spacer(),
          // Convert + Translate grouped together as equal-level operations
          Tooltip(
            message: l10n.batchUploadFormatConvert,
            child: TextButton.icon(
              onPressed: _selectedCount > 0 ? _startConversion : null,
              icon: const Icon(Icons.transform, size: 16),
              label: Text(
                l10n.batchUploadConvert,
                style: const TextStyle(fontSize: 12),
              ),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
          ),
          const SizedBox(width: 4),
          Tooltip(
            message: l10n.batchUploadStartTranslation,
            child: FilledButton.icon(
              onPressed: _selectedCount > 0 ? _startSubmission : null,
              icon: const Icon(Icons.translate, size: 16),
              label: Text(
                l10n.batchUploadTranslate,
                style: TextStyle(fontSize: 12),
              ),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
          ),
        ],
      ),
    );
  }


  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Title bar (only when not embedded in a Scaffold with AppBar)
        if (!widget.showAppBar)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(20, 16, 8, 16),
            decoration: BoxDecoration(
              color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
            ),
            child: Row(
              children: [
                Icon(Icons.folder_open, color: theme.colorScheme.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _phase == _DialogPhase.chooseSource
                        ? l10n.batchUploadTitle
                        : _phase == _DialogPhase.reviewFiles
                            ? l10n.batchUploadFilesFound(_files.length)
                            : _phase == _DialogPhase.submitting
                                ? l10n.batchUploadSubmitting
                                : l10n.batchUploadCompleteTitle,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
        // Body
        Flexible(
          child: _buildBody(l10n, theme),
        ),
        // Bottom bar
        if (_phase != _DialogPhase.chooseSource)
          _buildBottomBar(l10n, theme),
      ],
    );
  }

  Widget _buildBody(AppLocalizations l10n, ThemeData theme) {
    switch (_phase) {
      case _DialogPhase.chooseSource:
        return _buildSourceSelection(l10n, theme);
      case _DialogPhase.reviewFiles:
        return _buildFileReview(l10n, theme);
      case _DialogPhase.submitting:
        return _buildProgress(l10n, theme);
      case _DialogPhase.done:
        return _buildSummary(l10n, theme);
    }
  }

  // ── Phase 1: Source selection ─────────────────────────────────────
  Widget _buildSourceSelection(AppLocalizations l10n, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Spacer(),
          Text(
            l10n.batchUploadSelectSourceHint,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),
          // Single file button
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: SizedBox(
              width: double.infinity,
              height: 80,
              child: _SourceOptionCard(
                icon: Icons.insert_drive_file,
                title: l10n.batchUploadSelectSingleFile,
                subtitle: l10n.batchUploadSingleFileDescription,
                onTap: _pickSingleFile,
              ),
            ),
          ),
          // Folder button
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: SizedBox(
              width: double.infinity,
              height: 80,
              child: _SourceOptionCard(
                icon: Icons.folder,
                title: l10n.batchUploadSelectFolder,
                subtitle: l10n.batchUploadFolderDescription,
                onTap: _pickFolder,
              ),
            ),
          ),
          // ZIP button
          SizedBox(
            width: double.infinity,
            height: 80,
            child: _SourceOptionCard(
              icon: Icons.folder_zip_outlined,
              title: l10n.batchUploadSelectZip,
              subtitle: l10n.batchUploadZipDescription,
              onTap: _pickZip,
            ),
          ),
          const Spacer(),
        ],
      ),
    );
  }

  // ── Phase 2: File review ──────────────────────────────────────────
  Widget _buildFileReview(AppLocalizations l10n, ThemeData theme) {
    final formats = FileFormatService();

    return Column(
      children: [
        // Toolbar (full width, top)
        _buildBatchToolbar(l10n, theme),
        // Settings (left) | File list (right)
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left: Quick Settings panel (always visible, scrollable)
              SizedBox(
                  width: 240,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    child: BatchQuickSettingsPanel(
                      toLang: _batchToLang,
                      platformKey: _batchPlatformKey,
                      temperature: _batchTemperature,
                      promptMode: _batchPromptMode,
                      promptStyle: _batchPromptStyle,
                      taskNote: _batchTaskNote,
                      selectedGlossaries: _batchSelectedGlossaries,
                      onToLangChanged: (v) => setState(() {
                        _batchToLang = v;
                        _batchToLangUserModified = true;
                      }),
                      onPlatformChanged: (v) => setState(() => _batchPlatformKey = v),
                      onTemperatureChanged: (v) => setState(() => _batchTemperature = v),
                      onPromptModeChanged: (v) => setState(() => _batchPromptMode = v),
                      onPromptStyleChanged: (v) => setState(() => _batchPromptStyle = v),
                      onTaskNoteChanged: (v) => setState(() => _batchTaskNote = v),
                      onGlossariesChanged: (v) => setState(() => _batchSelectedGlossaries = v),
                      parsingEngine: _batchParsingEngine,
                      onParsingEngineChanged: (v) => setState(() => _batchParsingEngine = v),
                    ),
                  ),
                ),
                const VerticalDivider(width: 1),
              // Right: File list area
              Expanded(
                child: Column(
                  children: [
                    // Legacy format warning banner
                    if (_legacyFileNames.isNotEmpty)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.orange.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: Colors.orange.withValues(alpha: 0.4),
                          ),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.info_outline,
                                size: 18, color: Colors.orange.shade700),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                l10n.batchUploadLegacyFormatsSkipped(
                                  _legacyFileNames.length.toString(),
                                ),
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.orange.shade900,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    // Select-all header
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: Row(
                        children: [
                          TextButton.icon(
                            icon: Icon(
                              _files.every((f) => f.isSelected)
                                  ? Icons.check_box
                                  : Icons.check_box_outline_blank,
                              size: 20,
                            ),
                            label: Text(
                              _files.every((f) => f.isSelected)
                                  ? l10n.batchUploadDeselectAll
                                  : l10n.batchUploadSelectAll,
                            ),
                            onPressed: _toggleSelectAll,
                          ),
                          const Spacer(),
                          Text(
                            '${_selectedCount} / ${_files.length}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    // File list
                    Expanded(
                      child: ListView.builder(
                        itemCount: _files.length,
                        itemBuilder: (context, index) {
                          final file = _files[index];
                          final hasRelativePath = file.relativePath != null && file.relativePath!.isNotEmpty;
                          return CheckboxListTile(
                            value: file.isSelected,
                            onChanged: (v) => setState(() => file.isSelected = v ?? false),
                            dense: true,
                            secondary: Icon(
                              _iconForExtension(file.extension),
                              size: 22,
                              color: theme.colorScheme.primary,
                            ),
                            title: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (hasRelativePath)
                                  Text(
                                    file.relativePath!,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                Text(
                                  file.fileName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 14),
                                ),
                              ],
                            ),
                            subtitle: Text(
                              '${file.formattedSize}  ·  ${formats.getFormatDisplayName(file.extension)}',
                              style: const TextStyle(fontSize: 12),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── Phase 3: Progress ─────────────────────────────────────────────
  Widget _buildProgress(AppLocalizations l10n, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LinearProgressIndicator(
            value: _total > 0 ? _completed / _total : 0,
          ),
          const SizedBox(height: 12),
          Text(
            l10n.batchUploadProgress(_completed, _total),
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          Expanded(
            child: ListView.builder(
              itemCount: _statuses.length,
              itemBuilder: (context, index) {
                final s = _statuses[index];
                return ListTile(
                  dense: true,
                  leading: Icon(
                    s.state == FileSubmissionState.pending
                        ? Icons.hourglass_empty
                        : s.state == FileSubmissionState.submitting
                            ? Icons.cloud_upload
                            : s.state == FileSubmissionState.done
                                ? Icons.check_circle
                                : Icons.error,
                    size: 20,
                    color: s.state == FileSubmissionState.done
                        ? Colors.green
                        : s.state == FileSubmissionState.failed
                            ? Colors.red
                            : null,
                  ),
                  title: Text(
                    s.fileName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // ── Phase 4: Summary ──────────────────────────────────────────────
  Widget _buildSummary(AppLocalizations l10n, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _failed == 0 ? Icons.check_circle : Icons.warning_amber,
            size: 48,
            color: _failed == 0 ? Colors.green : Colors.orange,
          ),
          const SizedBox(height: 16),
          Text(
            l10n.batchUploadComplete(_succeeded, _failed),
            textAlign: TextAlign.center,
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 24),
          if (_failed > 0)
            Expanded(
              child: ListView(
                children: _statuses
                    .where((s) => s.state == FileSubmissionState.failed)
                    .map((s) => Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            s.errorMessage ?? s.fileName,
                            style: const TextStyle(
                                fontSize: 12, color: Colors.red),
                          ),
                        ))
                    .toList(),
              ),
            ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  // ── Bottom bar ────────────────────────────────────────────────────
  Widget _buildBottomBar(AppLocalizations l10n, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: theme.dividerColor),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          if (_phase == _DialogPhase.reviewFiles)
            Text(
              l10n.batchUploadSelectedCount(_selectedCount),
              style: theme.textTheme.bodySmall,
            ),
          if (_phase == _DialogPhase.submitting)
            OutlinedButton(
              onPressed: _cancelSubmission,
              child: Text(l10n.commonCancel),
            ),
          if (_phase == _DialogPhase.done)
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.commonClose),
            ),
        ],
      ),
    );
  }

  IconData _iconForExtension(String ext) {
    switch (ext.toLowerCase()) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'docx':
      case 'doc':
        return Icons.description;
      case 'pptx':
      case 'ppt':
        return Icons.slideshow;
      case 'xlsx':
      case 'xls':
      case 'csv':
        return Icons.table_chart;
      case 'md':
        return Icons.code;
      case 'html':
      case 'htm':
        return Icons.web;
      case 'txt':
        return Icons.text_snippet;
      case 'srt':
        return Icons.subtitles;
      case 'json':
      case 'arb':
        return Icons.data_object;
      case 'epub':
      case 'mobi':
      case 'azw':
        return Icons.book;
      case 'ts':
        return Icons.translate;
      case 'png':
      case 'jpg':
      case 'jpeg':
        return Icons.image;
      default:
        return Icons.insert_drive_file;
    }
  }
}

// ── Source option card ──────────────────────────────────────────────

class _SourceOptionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _SourceOptionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(icon, size: 32, color: theme.colorScheme.primary),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(title,
                        style: theme.textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text(subtitle,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        )),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: theme.colorScheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Status models ───────────────────────────────────────────────────

enum FileSubmissionState { pending, submitting, done, failed }

class FileSubmissionStatus {
  final String fileName;
  final FileSubmissionState state;
  final String? errorMessage;

  const FileSubmissionStatus({
    required this.fileName,
    this.state = FileSubmissionState.pending,
    this.errorMessage,
  });
}
