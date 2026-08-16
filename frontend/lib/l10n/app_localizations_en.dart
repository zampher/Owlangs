// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get settingsGeneralTitle => 'General Settings';

  @override
  String get settingsGeneralDarkModeTitle => 'Dark Mode';

  @override
  String get settingsGeneralDarkModeSubtitle =>
      'Enable dark theme (applied immediately)';

  @override
  String get settingsGeneralLanguageTitle => 'Language';

  @override
  String get settingsGeneralNotificationsTitle => 'Notifications';

  @override
  String get settingsGeneralNotificationsSubtitle =>
      'Receive notifications for completed tasks (applied immediately)';

  @override
  String get settingsGeneralAutoSaveTitle => 'Auto Save';

  @override
  String get settingsGeneralAutoSaveSubtitle =>
      'Automatically save work in progress (applied immediately)';

  @override
  String get settingsGeneralShowAdsTitle => 'Show ADs';

  @override
  String get settingsGeneralShowAdsSubtitle =>
      'Show AD placeholders on Home and in Flow (stored in system.json)';

  @override
  String get settingsGeneralClearStatsButton => 'Clear Statistics';

  @override
  String get settingsGeneralClearStatsConfirmTitle => 'Clear Statistics?';

  @override
  String get settingsGeneralClearStatsConfirmMessage =>
      'This will reset the document and page count displayed on the home page to 0. This action cannot be undone.';

  @override
  String get settingsGeneralClearStatsConfirmButton => 'Clear';

  @override
  String get settingsGeneralClearStatsSuccess =>
      'Statistics cleared successfully.';

  @override
  String get backToHome => 'Back to Home';

  @override
  String get settingsFontSectionTitle => 'Font Settings';

  @override
  String get settingsFontPreviewSizeTitle => 'Preview Font Size';

  @override
  String get settingsFontPreviewSizeSubtitle =>
      'Font size for source and target text in preview';

  @override
  String get translationToolbarFilterAll => 'All';

  @override
  String get translationToolbarFilterFailed => 'Failed';

  @override
  String get translationToolbarFilterIncluded => 'Included';

  @override
  String get translationToolbarFilterExcluded => 'Excluded';

  @override
  String get translationToolbarSearchTooltip => 'Search (Ctrl+F / Cmd+F)';

  @override
  String get translationToolbarPrevRetryTooltip => 'Previous Retry Segment';

  @override
  String get translationToolbarNextRetryTooltip => 'Next Retry Segment';

  @override
  String get translationToolbarPreviewTooltip => 'Preview';

  @override
  String get translationToolbarFormatSettingsTooltip => 'Format Settings';

  @override
  String get translationToolbarExportTooltip => 'Export Document';

  @override
  String get translationToolbarPdfPreviewTooltip => 'PDF Preview (Debug)';

  @override
  String get translationToolbarCancelButton => 'Cancel';

  @override
  String get translationToolbarExitFullscreenTooltip => 'Exit Fullscreen';

  @override
  String get translationToolbarEnterFullscreenTooltip => 'Enter Fullscreen';

  @override
  String get translationToolbarDecreaseFontSize => 'Decrease font size';

  @override
  String get translationToolbarIncreaseFontSize => 'Increase font size';

  @override
  String get translationToolbarMergedView => 'Reading Mode';

  @override
  String get translationToolbarSegmentView => 'Labeled Mode';

  @override
  String get translationToolbarUpload => 'Upload';

  @override
  String get translationToolbarUploading => 'Uploading...';

  @override
  String get translationToolbarFileUploaded => 'File Uploaded';

  @override
  String get translationToolbarReextract => 'Re-extract';

  @override
  String get translationToolbarReextracting => 'Re-extracting...';

  @override
  String translationToolbarTokensCount(Object count) {
    return '$count tokens';
  }

  @override
  String get translationToolbarOpenGlossaryTab => 'Open glossary tab';

  @override
  String get translationToolbarHintWaitExtract =>
      'Please wait for Extract to complete';

  @override
  String get translationToolbarHintOperationInProgress =>
      'An operation is in progress';

  @override
  String get translationToolbarGlossary => 'Glossary';

  @override
  String get translationToolbarPrompt => 'Prompt';

  @override
  String get translationToolbarOpenPromptTab => 'Open prompt tab';

  @override
  String get translationToolbarConvertHint =>
      'Convert format, exclude all segments, translate, then export from the Convert tab';

  @override
  String get translationToolbarConvert => 'Convert';

  @override
  String get translationToolbarHintSaveGlossaryFirst =>
      'Please save the glossary first (click Apply)';

  @override
  String get translationToolbarHintUpdatingExcluded =>
      'Updating excluded segments...';

  @override
  String get translationToolbarStartTranslation => 'Start translation';

  @override
  String get translationToolbarTranslateAll => 'Translate All';

  @override
  String get translationToolbarTranslating => 'Translating...';

  @override
  String get translationToolbarRetryInProgress => 'Retry in progress...';

  @override
  String get translationToolbarRetryTooltip =>
      'Retry all failed or marked segments. This will retranslate segments that failed during translation or were manually marked for retry, using the currently selected AI platform. Excluded and cleared segments will be skipped.';

  @override
  String get translationToolbarRetry => 'Retry';

  @override
  String get translationPersistQueueTooltip =>
      'Write current exports to the server and update the task queue so downloads match your latest edits here.';

  @override
  String get translationPersistQueueButton => 'Save update to queue';

  @override
  String get translationPersistQueueAlreadySyncedTooltip =>
      'Already matches the queue snapshot. No save needed.';

  @override
  String get translationPersistQueueSuccess =>
      'Latest exports saved for the task queue.';

  @override
  String translationPersistQueueFailed(Object error) {
    return 'Could not save exports for the queue: $error';
  }

  @override
  String get translationCloseTranslateTabTitle =>
      'Task queue may not reflect your latest result';

  @override
  String get translationCloseTranslateTabMessage =>
      'Your edits here are not saved to the task queue snapshot yet. If you close without saving, files you download from the Task queue will not be the final version you see in this tab.\n\nYou can update the queue and then close, or close this tab without saving to the queue.';

  @override
  String get translationCloseTranslateTabStay => 'Stay';

  @override
  String get translationCloseTranslateTabClose => 'Close without saving';

  @override
  String get translationCloseTranslateTabSaveAndClose =>
      'Save to queue and close';

  @override
  String get translationCloseTranslateTabKeepTitle => 'Keep task in queue?';

  @override
  String get translationCloseTranslateTabKeepMessage =>
      'The task is completed. Keep it in the translation queue for later review and editing?';

  @override
  String get translationCloseTranslateTabKeepInQueue => 'Keep in queue';

  @override
  String get translationCloseTranslateTabDiscard => 'Discard';

  @override
  String get translationToolbarSwitchToFile => 'Switch to File';

  @override
  String get translationToolbarSwitchToText => 'Enter Text';

  @override
  String get translationStatusCompleted => 'Translation Completed';

  @override
  String get translationStatusRetry => 'Translation Retry';

  @override
  String get translationStatusFailed => 'Translation Failed';

  @override
  String get translationStatusCancelled => 'Translation Cancelled';

  @override
  String get translationStatusTranslating => 'Translating';

  @override
  String get translationStatusTranslatingFallback => 'Translating...';

  @override
  String get translationStatusReady => 'Ready';

  @override
  String get translationStatusTaskPending => 'Task Pending';

  @override
  String get translationStatusProcessing => 'Processing...';

  @override
  String translationStatsSuccessOnly(Object success, Object total) {
    return 'Success: $success/$total';
  }

  @override
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total) {
    return 'Success: $success/$total, Failed: $fail/$total';
  }

  @override
  String translationStatsTotal(Object count) {
    return 'Total: $count | ';
  }

  @override
  String translationStatsTranslated(Object count) {
    return 'Translated: $count | ';
  }

  @override
  String translationStatsPending(Object count) {
    return 'Pending: $count';
  }

  @override
  String translationStatsExcluded(Object count) {
    return ' | Excluded: $count';
  }

  @override
  String translationStatsRetryCount(Object count) {
    return ' | Retry: $count';
  }

  @override
  String translationStatsCleared(Object count) {
    return ' | Cleared: $count';
  }

  @override
  String translationStatsImages(Object count) {
    return ' | Images: $count';
  }

  @override
  String translationStatsSegment(Object current, Object total) {
    return 'Segment: $current / $total';
  }

  @override
  String get translationStatsDoubleClickToEdit => 'Double click text to edit.';

  @override
  String get translationStatsTranslatedLabel => 'Translated';

  @override
  String get translationStatsPendingLabel => 'Pending';

  @override
  String get translationStatsClearedLabel => 'Cleared';

  @override
  String get translationStatsImagesLabel => 'Images';

  @override
  String get translationStatsLoadingContent => 'Loading content...';

  @override
  String get translationStatsNoContentAvailable => 'No content available.';

  @override
  String get translationStatsNoSegmentsAvailable => 'No segments available';

  @override
  String translationStatsTokenIn(Object count) {
    return 'In: $count';
  }

  @override
  String translationStatsTokenOut(Object count) {
    return 'Out: $count';
  }

  @override
  String translationStatsTokenTotal(Object count) {
    return '($count)';
  }

  @override
  String get translationLangArabic => 'Arabic';

  @override
  String get translationLangBengali => 'Bengali';

  @override
  String get translationLangCatalan => 'Catalan';

  @override
  String get translationLangChinese => 'Chinese';

  @override
  String get translationLangChineseTraditional => 'Chinese (Traditional)';

  @override
  String get translationLangCzech => 'Czech';

  @override
  String get translationLangCroatian => 'Croatian';

  @override
  String get translationLangDanish => 'Danish';

  @override
  String get translationLangDutch => 'Dutch';

  @override
  String get translationLangEnglish => 'English';

  @override
  String get translationLangFilipino => 'Filipino';

  @override
  String get translationLangFinnish => 'Finnish';

  @override
  String get translationLangFrench => 'French';

  @override
  String get translationLangGerman => 'German';

  @override
  String get translationLangGreek => 'Greek';

  @override
  String get translationLangHebrew => 'Hebrew';

  @override
  String get translationLangHindi => 'Hindi';

  @override
  String get translationLangItalian => 'Italian';

  @override
  String get translationLangJapanese => 'Japanese';

  @override
  String get translationLangKorean => 'Korean';

  @override
  String get translationLangKhmer => 'Khmer';

  @override
  String get translationLangLithuanian => 'Lithuanian';

  @override
  String get translationLangMacedonian => 'Macedonian';

  @override
  String get translationLangMalay => 'Malay';

  @override
  String get translationLangNorwegian => 'Norwegian Bokmål';

  @override
  String get translationLangPolish => 'Polish';

  @override
  String get translationLangPortuguese => 'Portuguese';

  @override
  String get translationLangRomanian => 'Romanian';

  @override
  String get translationLangRussian => 'Russian';

  @override
  String get translationLangSlovenian => 'Slovenian';

  @override
  String get translationLangSpanish => 'Spanish';

  @override
  String get translationLangSwedish => 'Swedish';

  @override
  String get translationLangThai => 'Thai';

  @override
  String get translationLangTurkish => 'Turkish';

  @override
  String get translationLangUkrainian => 'Ukrainian';

  @override
  String get translationLangUrdu => 'Urdu';

  @override
  String get translationLangVietnamese => 'Vietnamese';

  @override
  String get translationExportNoFormats => 'No export formats available';

  @override
  String get translationExportDialogTitle => 'Export Document';

  @override
  String get translationExportDocumentType => 'Document Type';

  @override
  String get translationExportFormatOptionsTitle => 'Format Options (PDF only)';

  @override
  String get translationExportTableFormatLabel => 'Table Format:';

  @override
  String get translationExportTableFormatImage => 'Image';

  @override
  String get translationExportTableFormatHtml => 'HTML';

  @override
  String get translationExportEquationFormatLabel => 'Equation Format:';

  @override
  String get translationExportEquationFormatImage => 'Image';

  @override
  String get translationExportEquationFormatLatex => 'LaTeX';

  @override
  String get translationExportChartFormatLabel => 'Chart Format:';

  @override
  String get translationExportChartFormatImage => 'Image';

  @override
  String get translationExportChartFormatHtml => 'HTML';

  @override
  String get translationImageCoverColorModeLabel => 'Erase background:';

  @override
  String get translationImageCoverColorModeMax => 'Brightest pixel (max)';

  @override
  String get translationImageCoverColorModeMin => 'Darkest pixel (min)';

  @override
  String get translationImageCoverColorModeAvg => 'Average pixel (mean)';

  @override
  String get translationExportBilingualExport => 'Bilingual Export';

  @override
  String get translationExportBilingualOrderTargetAfter => 'Source First';

  @override
  String get translationExportBilingualOrderTargetAfterSub =>
      'Source first, target after';

  @override
  String get translationExportBilingualOrderTargetBefore =>
      'Target Before Source';

  @override
  String get translationExportBilingualOrderTargetBeforeSub =>
      'Target first, source after';

  @override
  String get translationExportSourceTextItalic => 'Source text italic';

  @override
  String get translationExportSourceTextColor => 'Source text color:';

  @override
  String get translationExportTargetTextItalic => 'Target text italic';

  @override
  String get translationExportTargetTextColor => 'Target text color:';

  @override
  String get translationExportSourceFontSizeDelta => 'Source font size delta:';

  @override
  String get translationExportTargetFontSizeDelta => 'Target font size delta:';

  @override
  String get translationExportColorDefault => 'Default';

  @override
  String get translationExportColorGray => 'Gray';

  @override
  String get translationExportColorBlue => 'Blue';

  @override
  String get translationExportColorRed => 'Red';

  @override
  String get translationExportColorGreen => 'Green';

  @override
  String get translationExportColorOrange => 'Orange';

  @override
  String get translationExportColorBlack => 'Black';

  @override
  String get translationExportDownloadButton => 'Download';

  @override
  String get translationExportMdEmbeddedImages => 'MD (Embedded Images)';

  @override
  String get translationExportMdWithImagesFolder => 'MD (With Images Folder)';

  @override
  String get translationExportPdfPreserveLayout => 'Original Layout PDF';

  @override
  String get translationExportPdfPreserveLayoutDesc =>
      'Overlay translation on the original PDF layout';

  @override
  String get translationExportImageOriginalLayout => 'Original layout image';

  @override
  String get translationExportImageOriginalLayoutDesc =>
      'Erase OCR text and write translation on the source image';

  @override
  String get translationExportPdfReflow => 'Reflow PDF';

  @override
  String get translationExportPdfReflowDesc =>
      'Re-typeset from translation Markdown; layout may differ from the source';

  @override
  String get translationPreviewDialogTitle => 'Preview Settings';

  @override
  String get translationPreviewStart => 'Start Preview';

  @override
  String get translationPreviewModeSectionTitle => 'Translation preview';

  @override
  String get translationPreviewModeHtml => 'HTML / Markdown';

  @override
  String get translationPreviewModeHtmlDesc =>
      'View rendered translation in the browser (default)';

  @override
  String get translationPreviewFullDocumentCompare =>
      'Full document comparison';

  @override
  String get translationPreviewFullDocumentCompareDesc =>
      'View source and translation side by side (export format; works with any preview mode above)';

  @override
  String get translationPreviewSyncScroll => 'Link scrollbars';

  @override
  String get translationPreviewSyncScrollDesc =>
      'When enabled, link PDF compare panes with a shared scroll bar (PDF compare only)';

  @override
  String get translationPreviewRevisionSyncScrollDesc =>
      'When enabled, hide separate scroll bars on source and translation previews; show one shared scroll bar between them with linked scrolling';

  @override
  String get translationPreviewPanelSource => 'Source';

  @override
  String get translationPreviewPanelTarget => 'Translation';

  @override
  String get translationPreviewNoExtraOptions =>
      'No extra options for this preview mode';

  @override
  String get translationPreviewReopenSettings => 'Preview settings';

  @override
  String get translationPreviewZoomIn => 'Zoom in';

  @override
  String get translationPreviewZoomOut => 'Zoom out';

  @override
  String get translationPreviewZoomReset => 'Reset zoom';

  @override
  String get translationLeftPanelExpandTooltip => 'Expand left panel';

  @override
  String get translationLeftPanelCollapseTooltip => 'Collapse left panel';

  @override
  String get translationSnackGlossarySaved => 'Glossary saved';

  @override
  String get translationSnackTranslationCancelled => 'Translation cancelled';

  @override
  String get translationSnackNoLlmpSelected => 'No LLM Platform selected';

  @override
  String get translationSnackTextEmpty => 'Text input is empty.';

  @override
  String get translationSnackTextConverted => 'Text converted to file format';

  @override
  String get translationSnackSourceResplitCompleted =>
      'Source re-split completed';

  @override
  String get translationSnackPleaseSelectFileOrText =>
      'Please select a file or enter text first';

  @override
  String get translationSnackPleaseSelectFileOrTextWithDot =>
      'Please select a file or enter text first.';

  @override
  String get translationSnackPleaseSelectFile => 'Please select a file first';

  @override
  String get translationSnackPleaseSelectDocumentFirst =>
      'Please select a document first.';

  @override
  String get translationSnackGlossaryGenerated =>
      'Glossary generated successfully!';

  @override
  String get translationSnackGlossaryGenerationCancelled =>
      'Glossary generation cancelled';

  @override
  String get translationSnackGlossaryAppliedToTask =>
      'Glossary applied to translation task';

  @override
  String get translationSnackPreviousTranslationCancelled =>
      'Previous translation cancelled';

  @override
  String get translationSnackGlossarySavedAndApplied =>
      'Glossary saved and applied';

  @override
  String get translationDialogMixedLangTitle => 'Mixed Language Detected';

  @override
  String translationDialogMixedLangContent(Object distribution) {
    return 'The document contains multiple languages:\n$distribution';
  }

  @override
  String get translationDialogMixedLangPromptTitle =>
      'To improve translation quality, you can add prompt instructions:';

  @override
  String get translationDialogMixedLangOption1Title =>
      'Only translate text in source language';

  @override
  String translationDialogMixedLangOption1Subtitle(Object languageName) {
    return 'Only translate text in $languageName language';
  }

  @override
  String get translationDialogMixedLangOption2Title =>
      'Keep code and technical terms unchanged';

  @override
  String get translationDialogMixedLangOption2Subtitle =>
      'Keep code blocks, technical terms, function names, and text in other languages unchanged';

  @override
  String get translationDialogMixedLangCancel => 'Cancel';

  @override
  String get translationDialogMixedLangSkip => 'Skip';

  @override
  String get translationDialogMixedLangApply => 'Apply';

  @override
  String get translationSnackExportStarted =>
      'Export task has been started, please wait.';

  @override
  String get translationSnackPromptUpdated => 'Prompt instructions updated';

  @override
  String translationSnackFailedToCancel(Object error) {
    return 'Failed to cancel: $error';
  }

  @override
  String translationSnackFailedConvertTextFormat(Object error) {
    return 'Failed to convert text format: $error';
  }

  @override
  String translationSnackFailedConvertText(Object error) {
    return 'Failed to convert text: $error';
  }

  @override
  String translationSnackFailedResplit(Object error) {
    return 'Failed to re-split: $error';
  }

  @override
  String get translationSnackRequestFailed => 'Request failed';

  @override
  String translationSnackFileImportFailed(Object error) {
    return 'File import failed: $error';
  }

  @override
  String translationSnackTaskStatus(Object status) {
    return 'Task status: $status';
  }

  @override
  String translationSnackFileDownloaded(Object filename) {
    return 'File downloaded: $filename';
  }

  @override
  String translationSnackFileSaved(Object filename) {
    return 'File saved: $filename';
  }

  @override
  String translationSnackFailedDownload(Object error, Object fileType) {
    return 'Failed to download $fileType: $error';
  }

  @override
  String translationSnackFailedOpenDownload(Object url) {
    return 'Failed to open download: $url';
  }

  @override
  String get translationDialogSwitchToFileTitle => 'Switch to File Mode';

  @override
  String get translationDialogSwitchToFileBody =>
      'Switching to file mode will clear your current text input. Do you want to continue?';

  @override
  String get translationDialogSwitchToTextTitle => 'Switch to Text Mode';

  @override
  String get translationDialogSwitchToTextBody =>
      'Switching to text mode will clear the current file selection. Do you want to continue?';

  @override
  String get translationSnackAllSegmentsExcludedSkipped =>
      'All segments are excluded. Translation will be skipped. You can export the file for format conversion.';

  @override
  String get translationDialogCancelButton => 'Cancel';

  @override
  String get translationDialogContinueButton => 'Continue';

  @override
  String get translationNoLlmAvailableTitle => 'No LLM platform available';

  @override
  String get translationNoLlmAvailableMessage =>
      'No configured and available LLM platform. To translate, please configure an LLM API Key in Settings first; if you only need format conversion, you can continue.';

  @override
  String get translationNoLlmConfigureButton => 'Configure LLM';

  @override
  String get translationNoLlmContinueFormatOnlyButton =>
      'Format conversion only';

  @override
  String get languageMatchWarningTitle => 'Language Match Warning';

  @override
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName) {
    return 'The detected source language ($detectedName) is the same as the target language ($targetName). Are you sure you want to continue with glossary generation?';
  }

  @override
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName) {
    return 'The detected source language ($detectedName) is the same as the target language ($targetName). Are you sure you want to continue with translation?';
  }

  @override
  String get translationDialogCancelTaskTitle => 'Cancel Current Task';

  @override
  String get translationDialogCancelTaskBody =>
      'This will cancel the current extraction/translation task and clear the selected file. Do you want to continue?';

  @override
  String get translationDialogCancelTaskNo => 'No';

  @override
  String get translationDialogCancelTaskYesCancel => 'Yes, Cancel';

  @override
  String get translationQuickSettingsTitle => 'Quick Settings';

  @override
  String get quickSettingsTargetLanguage => 'Target Language';

  @override
  String get quickSettingsSourceLanguage => 'Source language (MinerU OCR)';

  @override
  String get quickSettingsLanguageSwitchDisabled =>
      'Language switching is disabled during translation. Please switch to Extract tab to change target language.';

  @override
  String get quickSettingsParsingPlatform => 'Parsing Platform';

  @override
  String get quickSettingsTestMineru => 'Test MinerU connection';

  @override
  String get quickSettingsNotConfigured => 'Not configured';

  @override
  String get quickSettingsApiOk => 'API OK';

  @override
  String get quickSettingsApiUnavailable => 'API unavailable';

  @override
  String get quickSettingsNotTestedYet => 'Not tested yet';

  @override
  String get quickSettingsConnectionSuccessful => 'Connection successful';

  @override
  String get quickSettingsMineruConnectionFailed => 'MinerU connection failed';

  @override
  String get quickSettingsOpenMineruSettings => 'Open MinerU settings';

  @override
  String get quickSettingsTableOcr => 'Table OCR';

  @override
  String get quickSettingsTableOcrSubtitle =>
      'Recognize tables during document parsing';

  @override
  String get quickSettingsFormulaOcr => 'Formula OCR';

  @override
  String get quickSettingsFormulaOcrSubtitle =>
      'Recognize formulas during document parsing';

  @override
  String get quickSettingsPaddleUseDocOrientationClassify =>
      'Auto-Detect Orientation';

  @override
  String get quickSettingsPaddleUseDocOrientationClassifySubtitle =>
      'Automatically detect and correct document orientation before OCR';

  @override
  String get quickSettingsPaddleRestructurePages => 'Restructure Pages';

  @override
  String get quickSettingsPaddleRestructurePagesSubtitle =>
      'Restructure page layout for better reading order';

  @override
  String get quickSettingsMineruLabel => 'MinerU (mineru)';

  @override
  String get quickSettingsLlmPlatform => 'LLM Platform';

  @override
  String get quickSettingsTestLlmPlatform => 'Test current LLM platform';

  @override
  String get quickSettingsTestFailed => 'Test failed';

  @override
  String get quickSettingsOpenAiPlatformsSettings =>
      'Open AI Platforms settings';

  @override
  String get quickSettingsTemperature => 'Temperature';

  @override
  String get quickSettingsTemperatureHint =>
      'Controls randomness: Lower = more focused, Higher = more creative';

  @override
  String get quickSettingsQtTsOptions => 'Qt .ts Translation Options';

  @override
  String get quickSettingsQtTsSkipExisting => 'Skip existing translations';

  @override
  String get quickSettingsQtTsSkipExistingSubtitle =>
      'Skip messages that already have translations';

  @override
  String get quickSettingsQtTsTranslateUnfinished =>
      'Translate unfinished entries';

  @override
  String get quickSettingsQtTsTranslateUnfinishedSubtitle =>
      'Translate messages marked as unfinished (type=\"unfinished\")';

  @override
  String get quickSettingsQtTsTranslateVanished => 'Translate vanished entries';

  @override
  String get quickSettingsQtTsTranslateVanishedSubtitle =>
      'Translate messages marked as vanished (type=\"vanished\")';

  @override
  String get quickSettingsQtTsTranslateObsolete => 'Translate obsolete entries';

  @override
  String get quickSettingsQtTsTranslateObsoleteSubtitle =>
      'Translate messages marked as obsolete (type=\"obsolete\")';

  @override
  String get quickSettingsPrompt => 'Prompt';

  @override
  String get quickSettingsPromptMode => 'Prompt Mode';

  @override
  String get quickSettingsPromptModeOff => 'Off (No prompt)';

  @override
  String get quickSettingsPromptModeSimple => 'Simple (Style only)';

  @override
  String get quickSettingsPromptModeAdvanced => 'Advanced (Style + Note)';

  @override
  String get quickSettingsStyle => 'Style';

  @override
  String get quickSettingsStyleLiteral => 'Literal';

  @override
  String get quickSettingsStyleFluent => 'Fluent';

  @override
  String get quickSettingsStyleAcademic => 'Academic';

  @override
  String get quickSettingsStyleBusiness => 'Business';

  @override
  String get quickSettingsStyleTechnical => 'Technical';

  @override
  String get quickSettingsStyleNone => 'None';

  @override
  String get quickSettingsTaskNoteLabel => 'Task note (short instruction)';

  @override
  String get quickSettingsTaskNoteHint =>
      'e.g. Keep formulas unmodified; annotate proper nouns';

  @override
  String get promptTabDescription =>
      'Choose prompt mode and translation style. When enabled, add detailed custom instructions in the text area below.';

  @override
  String get promptTabLongInstructionLabel => 'Custom instruction';

  @override
  String get promptTabLongInstructionHint =>
      'Long-form guidance for translation, e.g. tone, terminology, formatting rules, or domain-specific requirements.';

  @override
  String get quickSettingsAdRegionF =>
      'Region F: Bottom of Quick Settings\n(Medium Rectangle 300×250)';

  @override
  String quickSettingsPlatformMessage(Object label, Object message) {
    return '$label: $message';
  }

  @override
  String quickSettingsPlatformTestFailed(Object error, Object label) {
    return '$label: Test failed — $error';
  }

  @override
  String get homeTagline =>
      'AI Based, Immersion\nPrivate, Secure(Developing)\nTeam Shared, Customizable\n';

  @override
  String get homeIntro =>
      'Upload documents and translate them into multiple languages with AI-powered accuracy.\n';

  @override
  String get homeHowItWorks =>
      'How it works\nTranslation: Import -> Parse Document -> Glossary -> Translate -> Export\nFile format conversion: Import -> Parse Document -> Convert -> Export\nURL Fetch: Enter URL -> Fetch Page -> Parse Content -> Extract Text -> Translate/Export';

  @override
  String get homeSnackDonorExpired =>
      'Your registration code has expired. Please re-register to continue Pro benefits.';

  @override
  String get commonCancel => 'Cancel';

  @override
  String get commonOk => 'OK';

  @override
  String get homeAuthErrorTitle => 'Authentication Error';

  @override
  String get homeAuthRetryLogin => 'Retry Login';

  @override
  String homeAiPlatformsAvailable(Object platforms) {
    return 'Available AI Platforms: $platforms';
  }

  @override
  String get homeAiPlatformsConfigureNotice =>
      'Please configure your AI platforms in the settings panel before using the app.';

  @override
  String get homeBackendStatusStarting => 'Backend is starting up...';

  @override
  String get homeBackendStatusConnecting => 'Connecting to backend...';

  @override
  String get homeBackendStatusConnected => 'Backend is connected';

  @override
  String get homeBackendStatusDisconnected =>
      'Backend is disconnected. Please retry.';

  @override
  String get homeBackendStatusUnknown => 'Connecting to backend...';

  @override
  String get homeBackendRetry => 'Retry';

  @override
  String get homeNewTask => 'New task';

  @override
  String get homeNewTaskImmersiveTooltip =>
      'Compare source and translation side by side in the UI';

  @override
  String get homeNewTaskQueuedTooltip =>
      'Batch import files and run the full pipeline in order';

  @override
  String get homeNavTranslate => 'Immersive task';

  @override
  String get homeNavTranslationQueue => 'Tasks';

  @override
  String get homeNavCompareReading => 'Compare';

  @override
  String get homeNavTooltipCompareReading =>
      'Open two files side by side for compare reading (source left, translation right)';

  @override
  String get compareReadingTitle => 'Compare reading';

  @override
  String get compareReadingIntro =>
      'Import a source document and its translation to read them side by side. No translation or revision workflow — pure compare reading with zoom and linked scroll.';

  @override
  String compareReadingSupportedFormats(String formats) {
    return 'Supported formats: $formats';
  }

  @override
  String get compareReadingPickSource => 'Select source document';

  @override
  String get compareReadingPickTarget => 'Select translation document';

  @override
  String get compareReadingImport => 'Import';

  @override
  String get compareReadingReplaceFile => 'Replace';

  @override
  String get compareReadingChangeFiles => 'Change files';

  @override
  String get compareReadingClearSession => 'Clear both';

  @override
  String get compareReadingModeCompare => 'Compare reading';

  @override
  String get compareReadingModeSourceOnly =>
      'Source only (double-click source pane to toggle)';

  @override
  String get compareReadingModeTargetOnly =>
      'Translation only (double-click translation pane to toggle)';

  @override
  String get compareReadingKindMismatch =>
      'Source and translation must use the same preview type (PDF, image, or text).';

  @override
  String compareReadingReadBytesFailed(String fileName) {
    return 'Could not read file bytes: $fileName';
  }

  @override
  String get homeNavAnonymize => 'Anonymize';

  @override
  String get homeNavSettings => 'Settings';

  @override
  String get homeNavDonateHelp => 'Help';

  @override
  String get homeNavDonate => 'Donate';

  @override
  String get homeNavHome => 'Home';

  @override
  String get homeNavBatchUpload => 'Batch upload';

  @override
  String get homeNavTooltipNewTask =>
      'Start a new translation — immersive side-by-side, or queued batch processing';

  @override
  String get homeNavTooltipTasks =>
      'View and manage all translation tasks, download completed results';

  @override
  String get homeNavTooltipAnonymize =>
      'Anonymize document content to protect sensitive information';

  @override
  String get homeNavTooltipSettings =>
      'Configure language, theme, notifications and more';

  @override
  String get homeNavTooltipSetupWizard =>
      'Guided setup wizard to configure your translation environment';

  @override
  String get homeNavTooltipHelp => 'Get help and technical support';

  @override
  String get homeNavTooltipDonate => 'Support our open source project';

  @override
  String get homeNavTooltipHome => 'Return to home page';

  @override
  String get homeNavTooltipGitHub =>
      'View source code on GitHub — star us if you find it useful!';

  @override
  String get batchUploadTitle => 'Batch file upload';

  @override
  String get batchUploadFormatConvert => 'Format conversion';

  @override
  String get batchUploadSelectSourceHint =>
      'Choose supported files to translate. Each file becomes a queued task.';

  @override
  String get batchUploadSelectFolder => 'Select folder';

  @override
  String get batchUploadFolderDescription =>
      'Pick a folder containing files to translate';

  @override
  String get batchUploadSelectZip => 'Select ZIP archive';

  @override
  String get batchUploadZipDescription =>
      'Pick a ZIP archive containing files to translate';

  @override
  String get batchUploadSelectSingleFile => 'Select file';

  @override
  String get batchUploadSingleFileDescription =>
      'Pick a single file to translate';

  @override
  String get batchUploadAddFiles => 'Add files';

  @override
  String batchUploadFilesFound(Object count) {
    return '$count supported files found';
  }

  @override
  String get batchUploadSelectAll => 'Select all';

  @override
  String get batchUploadDeselectAll => 'Deselect all';

  @override
  String get batchUploadStartTranslation => 'Start translation';

  @override
  String get batchUploadSubmitting => 'Submitting files...';

  @override
  String batchUploadProgress(Object completed, Object total) {
    return 'Submitted $completed of $total files';
  }

  @override
  String get batchUploadCompleteTitle => 'Batch complete';

  @override
  String batchUploadComplete(Object success, Object failed) {
    return '$success succeeded, $failed failed';
  }

  @override
  String get batchUploadNoSupportedFiles =>
      'No supported files found in this source';

  @override
  String batchUploadSelectedCount(Object count) {
    return '$count files selected';
  }

  @override
  String batchUploadLegacyFormatsFound(Object files) {
    return '$files cannot be translated directly. Please convert .doc to .docx, .ppt to .pptx, .xls to .xlsx before submitting.';
  }

  @override
  String batchUploadLegacyFormatsSkipped(Object count) {
    return '$count file(s) skipped — legacy format not directly supported. Please convert .doc to .docx, .ppt to .pptx, .xls to .xlsx and try again.';
  }

  @override
  String get batchUploadSettingsToggle => 'Quick settings';

  @override
  String get batchUploadSaveDefaults => 'Save as defaults';

  @override
  String batchUploadTemperature(Object value) {
    return 'Temperature: $value';
  }

  @override
  String batchUploadGlossaryHint(Object count) {
    return 'Glossaries selected: $count';
  }

  @override
  String get batchUploadGlossaryNone => 'No glossaries selected';

  @override
  String get batchUploadConfirmLangTitle => 'Confirm Target Language';

  @override
  String batchUploadConfirmLangMessage(Object lang) {
    return 'The target language is \"$lang\". Do you want to continue?';
  }

  @override
  String get batchUploadConvert => 'Convert';

  @override
  String get batchUploadTranslate => 'Translate';

  @override
  String get batchUploadFolderPickerTitle =>
      'Select folder with files to translate';

  @override
  String get batchUploadZipPickerTitle =>
      'Select ZIP archive containing files to translate';

  @override
  String batchUploadScanFolderError(Object error) {
    return 'Failed to scan folder: $error';
  }

  @override
  String batchUploadReadZipError(Object error) {
    return 'Failed to read ZIP archive: $error';
  }

  @override
  String get batchUploadGlossarySection => 'Glossary';

  @override
  String batchUploadGlossaryMore(Object count) {
    return '+$count';
  }

  @override
  String batchUploadGlossaryLoadError(Object error) {
    return 'Error: $error';
  }

  @override
  String get batchUploadNoGlossaries => 'No glossaries available';

  @override
  String get batchUploadMineru => 'MinerU';

  @override
  String get batchUploadMineruLocal => 'MinerU Local';

  @override
  String get batchUploadPaddle => 'PaddleOCR';

  @override
  String get batchUploadPaddleLocal => 'PaddleOCR Local';

  @override
  String get commonClose => 'Close';

  @override
  String get translationQueueTitle => 'Task queue';

  @override
  String get translationQueueHint =>
      'Tasks refresh automatically. Downloads appear when a task completes.';

  @override
  String get translationQueueCancelExitHint =>
      'For queued or running tasks, use Cancel task to stop work; after you confirm, you return to the home page.';

  @override
  String get translationQueueCancelDialogTitle =>
      'Cancel this translation task?';

  @override
  String get translationQueueCancelDialogMessage =>
      'Queued tasks are removed from the queue; running tasks are stopped. After confirming, you will return to the home page.';

  @override
  String get translationQueueCancelDialogKeep => 'Keep';

  @override
  String get translationQueueCancelDialogConfirm => 'Cancel task';

  @override
  String get translationQueueEmpty => 'No translation tasks yet.';

  @override
  String get translationQueueNewQueuedTask => 'Queued task';

  @override
  String get translationQueueImport => 'Import';

  @override
  String get translationQueueBackToQueueTooltip => 'Back to task queue';

  @override
  String get translationQueuedStarted =>
      'Task added to the queue. Track it here.';

  @override
  String get translationQueueRefresh => 'Refresh';

  @override
  String get translationQueueCancel => 'Cancel task';

  @override
  String get translationQueueRelease => 'Remove from list';

  @override
  String get translationQueueDownloads => 'Downloads';

  @override
  String get translationQueueDownloadMdEmbedded => 'MD (embedded)';

  @override
  String get translationQueueDownloadMdZip => 'MD (images)';

  @override
  String get translationQueueExecutionModeQueued => 'Queued';

  @override
  String get translationQueueExecutionModeImmediate => 'Immediate';

  @override
  String get translationQueueTaskTypeTranslation => 'Translation';

  @override
  String get translationQueueTaskTypeConversion => 'Conversion';

  @override
  String translationQueuePositionLabel(Object position) {
    return 'Queue #$position';
  }

  @override
  String translationQueueLoadFailed(Object error) {
    return 'Failed to load tasks: $error';
  }

  @override
  String translationQueueActionFailed(Object error) {
    return 'Action failed: $error';
  }

  @override
  String translationQueueSubmittedBy(Object user) {
    return 'Submitted by: $user';
  }

  @override
  String translationQueueStartedAt(Object time) {
    return 'Started: $time';
  }

  @override
  String translationQueueCompletedAt(Object time) {
    return 'Completed: $time';
  }

  @override
  String get translationQueueTimeUnknown => '—';

  @override
  String get translationQueueGuestUser => 'Guest';

  @override
  String get translationQueueClearAllTooltip =>
      'Clear task queue and server-side result cache (admin only)';

  @override
  String get translationQueueClearAllButton => 'Clear queue';

  @override
  String get translationQueueClearAllTitle => 'Clear task queue';

  @override
  String get translationQueueClearAllMessage =>
      'This cancels queued and in-flight work, removes all in-memory tasks, and deletes on-disk queue snapshots. This cannot be undone.';

  @override
  String get translationQueueClearAllConfirm => 'Clear';

  @override
  String get translationQueueClearAllCancel => 'Cancel';

  @override
  String get translationQueueClearAllSuccess => 'Task queue cleared.';

  @override
  String translationQueueClearAllFailed(Object error) {
    return 'Could not clear queue: $error';
  }

  @override
  String get translationQueueClearMyQueueTooltip => 'Clear my queue';

  @override
  String get translationQueueClearMyQueueTitle => 'Clear my queue';

  @override
  String get translationQueueClearMyQueueMessage =>
      'Remove all your tasks from the queue?';

  @override
  String get translationQueueClearMyQueueConfirm => 'Clear';

  @override
  String get translationQueueClearMyQueueCancel => 'Cancel';

  @override
  String get translationQueueClearMyQueueSuccess => 'My queue cleared.';

  @override
  String translationQueueClearMyQueueFailed(Object error) {
    return 'Could not clear your queue: $error';
  }

  @override
  String get translationQueueErrorMessageCopied => 'Error message copied';

  @override
  String get translationQueueSelected => 'selected';

  @override
  String get translationQueueSelectMode => 'Select';

  @override
  String get translationQueueClearSelection => 'Clear selection';

  @override
  String translationQueueBatchDownloadFailed(Object error) {
    return 'Batch download failed: $error';
  }

  @override
  String translationQueueBatchDownloadSuccess(Object fileType) {
    return 'Batch download: $fileType ready';
  }

  @override
  String get translationQueueView => 'Reading Edit';

  @override
  String get translationQueueViewSourcePath => 'View original file path';

  @override
  String get translationQueueSourcePathTitle => 'Source File Path';

  @override
  String get translationQueueFileNameLabel => 'File Name';

  @override
  String get translationQueueRelativePathLabel => 'Relative Path';

  @override
  String get homeFeatureUnderDevelopment =>
      'This feature is under development.';

  @override
  String homeAnonymizeNotSupportedVersion(Object version) {
    return 'Not supported yet. Will be available in v$version.';
  }

  @override
  String get homeAnonymizeInDevelopment =>
      'Anonymization is in development and not yet available.';

  @override
  String get homeScrollLeft => 'Scroll left';

  @override
  String get homeScrollRight => 'Scroll right';

  @override
  String get homeTabHome => 'Home';

  @override
  String get homeToolbarAdBanner =>
      'Toolbar Ad Banner\n(728×90 Leaderboard / 320×50 Mobile)';

  @override
  String get homeSteps => 'Steps';

  @override
  String get homePhaseUpload => 'Upload';

  @override
  String get homePhaseExtract => 'Extract';

  @override
  String get homePhaseGlossary => 'Glossary';

  @override
  String get homePhasePrompt => 'Prompt';

  @override
  String get homePhaseTranslate => 'Translate';

  @override
  String get homePhaseViewer => 'Revise';

  @override
  String get homePhaseAnonymize => 'Anonymize';

  @override
  String get homePhaseDeAnonymize => 'De-anonymize';

  @override
  String get homePhaseExport => 'Export';

  @override
  String get taskDefaultTitleTranslate => 'Task';

  @override
  String get taskDefaultTitleAnonymize => 'Anonymization';

  @override
  String get homeReleaseNotesTitle => 'Release Notes';

  @override
  String get homeReleaseNotesViewOnGitHub => 'View on GitHub';

  @override
  String get homeEditionEnterprise => 'Enterprise';

  @override
  String get homeEditionEnterpriseStatusActivated => 'Activated';

  @override
  String get homeEditionActivateEnterprise => 'Activate Enterprise';

  @override
  String get homeEditionPro => 'Pro';

  @override
  String get homeEditionStandard => 'Standard';

  @override
  String get homeEditionStandardStatus => 'Always available';

  @override
  String homeEditionProStatusTrialRemaining(Object days) {
    return '$days days left';
  }

  @override
  String get homeEditionProStatusNotActivated => 'Not activated';

  @override
  String get homeEditionProStatusActivated => 'Activated';

  @override
  String get homeWelcomeDearPro =>
      'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.';

  @override
  String get homeWelcomeDearStandard =>
      'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.';

  @override
  String get homeWelcomeDearProNoUser =>
      'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.';

  @override
  String get homeWelcomeDearStandardNoUser =>
      'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.';

  @override
  String get homeWelcomeHello =>
      'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.';

  @override
  String get homeLoading => 'Loading...';

  @override
  String get homeWelcomeGuest => 'Welcome!';

  @override
  String homeFileNotFound(Object fileName) {
    return 'File not found: $fileName. The file may have been moved or deleted.';
  }

  @override
  String homeFileSelectedMismatch(Object expected, Object selected) {
    return 'Selected file name does not match: $selected. Expected: $expected';
  }

  @override
  String homeFileLoaded(Object fileName) {
    return 'File loaded: $fileName';
  }

  @override
  String get homeFileSelectionCancelled => 'File selection cancelled.';

  @override
  String homeFileLoadFailed(Object error) {
    return 'Failed to load file: $error';
  }

  @override
  String homeFlowCreateFailed(Object error) {
    return 'Failed to create flow: $error';
  }

  @override
  String commonPageNotFound(Object uri) {
    return 'Page not found: $uri';
  }

  @override
  String get commonGoHome => 'Go Home';

  @override
  String get commonLogin => 'Login';

  @override
  String get commonLogout => 'Logout';

  @override
  String get userMenuChangePassword => 'Change password';

  @override
  String get changePasswordCurrentPasswordLabel => 'Current password';

  @override
  String get changePasswordNewPasswordLabel => 'New password';

  @override
  String get changePasswordConfirmPasswordLabel => 'Confirm new password';

  @override
  String get changePasswordRequiredError =>
      'Current password and new password are required.';

  @override
  String get changePasswordConfirmMismatchError =>
      'The two new passwords do not match.';

  @override
  String get changePasswordSuccessMessage => 'Password changed successfully.';

  @override
  String get changePasswordRequirementsTitle => 'Password requirements';

  @override
  String get changePasswordRequirementLength => '8–128 characters';

  @override
  String get changePasswordRequirementUppercase =>
      'At least 1 uppercase letter';

  @override
  String get changePasswordRequirementLowercase =>
      'At least 1 lowercase letter';

  @override
  String get changePasswordRequirementDigit => 'At least 1 digit';

  @override
  String get settingsTabsGeneral => 'General';

  @override
  String get settingsTabsAiPlatforms => 'AI Platforms';

  @override
  String get settingsTabsParsingEngine => 'Parsing Engine';

  @override
  String get settingsParsingEngineTitle => 'Parsing Engine';

  @override
  String get settingsParsingEngineSubtitle =>
      'Select the document parsing engine for text extraction and processing.';

  @override
  String get settingsParsingEngineLabel => 'Parsing Engine';

  @override
  String get settingsParsingEngineMineru => 'MinerU (Cloud)';

  @override
  String get settingsParsingEngineMineruDesc =>
      'Advanced document parsing with OCR support';

  @override
  String get settingsParsingEngineMineruLocal => 'MinerU (Local)';

  @override
  String get settingsParsingEngineMineruLocalDesc =>
      'Self-hosted MinerU; API key optional';

  @override
  String get settingsParsingEnginePaddle => 'PaddleOCR (Cloud)';

  @override
  String get settingsParsingEnginePaddleDesc =>
      'High-accuracy OCR with layout parsing for titles, tables, and formulas';

  @override
  String get settingsParsingEnginePaddleLocal => 'PaddleOCR (Local)';

  @override
  String get settingsParsingEnginePaddleLocalDesc =>
      'Self-hosted PaddleOCR; requires NVIDIA GPU (~8.5 GB VRAM)';

  @override
  String get settingsParsingEnginePdfplumber => 'PDFPlumber';

  @override
  String get settingsParsingEnginePdfplumberDesc => 'Fast PDF text extraction';

  @override
  String get settingsParsingEngineTesseract => 'Tesseract OCR';

  @override
  String get settingsParsingEngineTesseractDesc => 'OCR-based text extraction';

  @override
  String get settingsFormulaOcr => 'Formula OCR';

  @override
  String get settingsFormulaOcrSubtitle =>
      'Enable OCR for mathematical formulas';

  @override
  String get settingsTableOcr => 'Table OCR';

  @override
  String get settingsTableOcrSubtitle => 'Enable OCR for tables';

  @override
  String get settingsMineruModelVersion => 'Model Version';

  @override
  String get settingsMineruModelVersionSubtitle =>
      'Select the MinerU parsing mode (pipeline, vlm-auto-engine, hybrid-auto-engine, vlm-http-client, or hybrid-http-client)';

  @override
  String get settingsAnonymizationNewTaskNotice =>
      'Changes apply to new tasks only';

  @override
  String get settingsParsingEngineNewTaskNotice =>
      'Changes apply to new tasks only';

  @override
  String get settingsPaddleOcrModelLabel => 'PaddleOCR Model';

  @override
  String get settingsPaddleUseDocOrientationClassify =>
      'Auto-Detect Orientation';

  @override
  String get settingsPaddleUseDocOrientationClassifySubtitle =>
      'Automatically detect and correct document orientation before OCR';

  @override
  String get settingsPaddleRestructurePages => 'Restructure Pages';

  @override
  String get settingsPaddleRestructurePagesSubtitle =>
      'Restructure page layout for better reading order';

  @override
  String get settingsPdfSplitMaxPages => 'PDF Split Max Pages';

  @override
  String get settingsPdfSplitMaxWorkers => 'PDF Split Max Workers';

  @override
  String get settingsRequestRetryCount => 'Request Retry Count';

  @override
  String get settingsOcrLanguageTitle => 'OCR Language';

  @override
  String get settingsOcrLanguageSubtitle =>
      'Configure the OCR language for text recognition in images and scanned documents.';

  @override
  String get settingsOcrLanguageLabel => 'OCR Language';

  @override
  String get settingsOcrLangEnglish => 'English';

  @override
  String get settingsOcrLangChineseSimplified => 'Chinese (Simplified)';

  @override
  String get settingsOcrLangChineseTraditional => 'Chinese (Traditional)';

  @override
  String get settingsOcrLangJapanese => 'Japanese';

  @override
  String get settingsOcrLangKorean => 'Korean';

  @override
  String get settingsOcrLangFrench => 'French';

  @override
  String get settingsOcrLangGerman => 'German';

  @override
  String get settingsOcrLangSpanish => 'Spanish';

  @override
  String get settingsOcrLangRussian => 'Russian';

  @override
  String get settingsOcrLangArabic => 'Arabic';

  @override
  String get settingsOcrLangAuto => 'Auto Detect';

  @override
  String get mineruLangAuto => 'Auto Detect';

  @override
  String get mineruLangChServer => 'Chinese (Server)';

  @override
  String get mineruLangChLite => 'Chinese (Lite)';

  @override
  String get mineruLangTamil => 'Tamil';

  @override
  String get mineruLangTelugu => 'Telugu';

  @override
  String get mineruLangKannada => 'Kannada';

  @override
  String get mineruLangLatinScript => 'Latin Script';

  @override
  String get mineruLangArabicScript => 'Arabic Script';

  @override
  String get mineruLangEastSlavic => 'East Slavic';

  @override
  String get mineruLangCyrillicScript => 'Cyrillic Script';

  @override
  String get mineruLangDevanagariScript => 'Devanagari Script';

  @override
  String get settingsTabsGlossary => 'Glossary';

  @override
  String get settingsGlossaryManagementTitle => 'Glossary Management';

  @override
  String get settingsGlossaryManagementSubtitle =>
      'Manage your terminology entries for consistent translation quality.';

  @override
  String get settingsGlossarySelectGlossary => 'Select Glossary';

  @override
  String get settingsGlossaryCreateGlossary => 'Create';

  @override
  String get settingsGlossaryImportCsv => 'Import';

  @override
  String get settingsGlossaryExport => 'Export';

  @override
  String get settingsGlossaryExportAll => 'Export All';

  @override
  String get settingsGlossaryDeleteGlossary => 'Delete';

  @override
  String get settingsGlossarySaveZip => 'Save ZIP';

  @override
  String settingsGlossaryEntriesTitle(Object count) {
    return 'Glossary Entries ($count)';
  }

  @override
  String get settingsGlossaryAddEntry => 'Add Entry';

  @override
  String get settingsGlossaryNoEntriesYet =>
      'No glossary entries yet.\nAdd your first entry to get started.';

  @override
  String get settingsGlossaryFilterLabel => 'Filter:';

  @override
  String get settingsGlossaryFilterAll => 'All';

  @override
  String get settingsGlossaryFilterUncategorized => 'Uncategorized';

  @override
  String get settingsGlossaryTableSource => 'Source';

  @override
  String get settingsGlossaryTableTarget => 'Target';

  @override
  String get settingsGlossaryTableCategory => 'Category (Optional)';

  @override
  String get settingsGlossaryTableTargetLang => 'Target Language';

  @override
  String get settingsGlossaryCategoryHint => 'Category';

  @override
  String get settingsGlossaryUncategorizedDisplay => '(Uncategorized)';

  @override
  String get settingsGlossaryCopyAction => 'Copy';

  @override
  String get settingsGlossaryCopiedToClipboard => 'Copied to clipboard';

  @override
  String get settingsGlossaryDeleteDialogTitle => 'Delete Glossary';

  @override
  String settingsGlossaryDeleteDialogMessage(Object id) {
    return 'Are you sure to delete this glossary?\nID: $id';
  }

  @override
  String get settingsGlossaryCancel => 'Cancel';

  @override
  String get settingsGlossaryDelete => 'Delete';

  @override
  String get settingsGlossaryCreateDialogTitle => 'Create Glossary';

  @override
  String get settingsGlossaryNameLabel => 'Name';

  @override
  String get settingsGlossaryDescriptionLabel => 'Description (optional)';

  @override
  String get settingsGlossaryGlobalGlossary => 'Global Glossary';

  @override
  String get settingsGlossaryGlobalGlossarySubtitle =>
      'If off, it will be your personal glossary';

  @override
  String get settingsGlossaryCreate => 'Create';

  @override
  String get settingsGlossaryNameRequired => 'Name is required';

  @override
  String settingsGlossaryCreatedSnack(Object name) {
    return 'Created: $name';
  }

  @override
  String settingsGlossaryCreateFailedSnack(Object error) {
    return 'Create failed: $error';
  }

  @override
  String get settingsGlossaryAddEntryDialogTitle => 'Add Entry to Glossary';

  @override
  String get settingsGlossarySourceTextLabel => 'Source Text';

  @override
  String get settingsGlossaryTargetTextLabel => 'Target Text';

  @override
  String get settingsGlossaryCategoryOptionalLabel => 'Category (optional)';

  @override
  String get settingsGlossaryCategoryOptionalHint =>
      'Leave empty for unclassified';

  @override
  String get settingsGlossaryAdd => 'Add';

  @override
  String get settingsGlossarySourceTargetRequired =>
      'Source text and target text are required';

  @override
  String get settingsGlossaryEntryAddedSnack => 'Entry added';

  @override
  String settingsGlossaryAddFailedSnack(Object error) {
    return 'Failed: $error';
  }

  @override
  String get settingsGlossaryImportDialogTitle => 'Import CSV/TBX to Glossary';

  @override
  String get settingsGlossaryMergeModeLabel => 'Merge Mode';

  @override
  String get settingsGlossaryMergeUpdate => 'Update (Upsert)';

  @override
  String get settingsGlossaryMergeAppend => 'Append (New Only)';

  @override
  String get settingsGlossaryMergeReplace => 'Replace (Overwrite All)';

  @override
  String get settingsGlossaryImport => 'Import';

  @override
  String get settingsGlossaryUnableToReadFile => 'Unable to read file';

  @override
  String settingsGlossaryImportedSnack(Object count) {
    return 'Imported: $count items';
  }

  @override
  String settingsGlossaryImportFailedSnack(Object error) {
    return 'Failed: $error';
  }

  @override
  String get settingsGlossaryExportDialogTitle => 'Export Glossary';

  @override
  String get settingsGlossarySaveCsv => 'Save CSV/TBX';

  @override
  String get settingsGlossaryDownload => 'Download';

  @override
  String settingsGlossaryDownloadedSnack(Object info) {
    return 'Downloaded: $info';
  }

  @override
  String settingsGlossaryExportFailedSnack(Object error) {
    return 'Failed: $error';
  }

  @override
  String settingsGlossaryLoadedSnack(Object count) {
    return 'Loaded $count entries';
  }

  @override
  String settingsGlossaryLoadFailedSnack(Object error) {
    return 'Load failed: $error';
  }

  @override
  String settingsGlossaryDeletedSnack(Object id) {
    return 'Glossary deleted: $id';
  }

  @override
  String settingsGlossaryDeleteFailedSnack(Object error) {
    return 'Delete failed: $error';
  }

  @override
  String settingsGlossaryExportAllFailedSnack(Object error) {
    return 'Export all failed: $error';
  }

  @override
  String get settingsGlossaryEntryUpdatedSnack => 'Entry updated';

  @override
  String settingsGlossaryUpdateFailedSnack(Object error) {
    return 'Failed to update: $error';
  }

  @override
  String get settingsGlossaryEntryDeletedSnack => 'Entry deleted';

  @override
  String settingsGlossaryDeleteEntryFailedSnack(Object error) {
    return 'Failed to delete: $error';
  }

  @override
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type) {
    return '$name ($type) · $count items';
  }

  @override
  String settingsGlossaryErrorPrefix(Object error) {
    return 'Error: $error';
  }

  @override
  String settingsGlossaryExportedAllSnack(Object info) {
    return 'Exported: $info';
  }

  @override
  String settingsGlossaryEntryCount(Object count) {
    return 'Entry count: $count';
  }

  @override
  String get settingsGlossaryEdit => 'Edit';

  @override
  String get settingsGlossaryConfirmDeleteEntryTitle => 'Confirm Delete';

  @override
  String settingsGlossaryConfirmDeleteEntryMessage(Object source) {
    return 'Delete entry \"$source\"?';
  }

  @override
  String get settingsGlossaryEditEntryDialogTitle => 'Edit Entry';

  @override
  String get settingsGlossaryUpdate => 'Update';

  @override
  String get settingsGlossaryEntryDeleteFailedSnack => 'Failed to delete entry';

  @override
  String get settingsGlossaryEmptyStateTitle =>
      'No glossaries yet. Create your first glossary to get started.';

  @override
  String get settingsGlossaryTooltipCreate => 'Create a new glossary';

  @override
  String get settingsGlossaryTooltipImport =>
      'Import entries from CSV or TBX format';

  @override
  String get settingsGlossaryTooltipExport =>
      'Export selected glossary to CSV or TBX format';

  @override
  String get settingsGlossaryTooltipExportAll =>
      'Export all glossaries as a ZIP archive';

  @override
  String get settingsGlossaryTooltipDeleteGlossary =>
      'Delete the selected glossary permanently';

  @override
  String get settingsGlossaryExportTemplate => 'Export Template';

  @override
  String get settingsGlossaryTooltipExportTemplate =>
      'Download a CSV template with header row and one example entry';

  @override
  String get settingsGlossarySaveTemplateCsv => 'Save glossary template CSV';

  @override
  String get settingsGlossaryTemplateExportedSnack =>
      'Glossary template downloaded';

  @override
  String get settingsGlossaryTooltipFormatHelp =>
      'View glossary file format requirements';

  @override
  String get settingsGlossaryFormatHelpTitle => 'Glossary File Format';

  @override
  String get settingsGlossaryFormatHelpContent =>
      'CSV format (recommended for bulk editing):\n\nFile encoding: UTF-8 (UTF-8 with BOM recommended)\n\nColumns:\n• src — source text (required)\n• dst — translated text (required)\n• category — optional grouping label\n• target_lang — optional target language code (see list below)\n\nRules:\n• Header row must include src and dst\n• Rows with empty src or dst are skipped on import\n• Import also supports TBX format\n\nUse \"Export Template\" to download a sample CSV with one example row.';

  @override
  String get settingsGlossaryFormatHelpTargetLangListTitle =>
      'Available target_lang values:';

  @override
  String get settingsGlossaryBatchEditCategory => 'Edit category';

  @override
  String get settingsGlossaryBatchDelete => 'Delete';

  @override
  String get settingsGlossaryBatchDeselect => 'Deselect';

  @override
  String settingsGlossaryBatchSelectedCount(Object count) {
    return '$count selected';
  }

  @override
  String get settingsGlossaryExportFormatLabel => 'Export format';

  @override
  String get settingsGlossaryExportFormatCsv => 'CSV';

  @override
  String get settingsGlossaryExportFormatTbx => 'TBX (TermBase eXchange)';

  @override
  String get settingsGlossaryExportSourceLanguage => 'Source language';

  @override
  String get settingsGlossaryExportSaveTbxTitle => 'Save TBX file';

  @override
  String get settingsGlossaryDeleteEntriesTitle => 'Delete entries';

  @override
  String settingsGlossaryDeleteEntriesBody(Object count) {
    return 'Delete $count selected entries? This cannot be undone.';
  }

  @override
  String get settingsGlossaryDeleteEntriesConfirm => 'Delete';

  @override
  String get settingsGlossaryEditCategoryTitle => 'Edit Category';

  @override
  String settingsGlossaryEditCategoryBody(Object count) {
    return 'Set category for $count selected entries:';
  }

  @override
  String get settingsGlossaryEditCategoryLabel => 'Category';

  @override
  String get settingsGlossaryEditCategoryHint => 'Enter category name';

  @override
  String get settingsGlossaryEditCategoryApply => 'Apply';

  @override
  String get glossaryPanelSaveNameHint => 'Enter name or select existing...';

  @override
  String get glossaryPanelClearSelection => 'Clear selection';

  @override
  String get glossaryPanelListTitle => 'Glossary';

  @override
  String get glossaryPanelNoEntries => 'No entries';

  @override
  String get glossaryPanelOneEntry => '1 entry';

  @override
  String glossaryPanelEntriesCount(Object count) {
    return '$count entries';
  }

  @override
  String get glossaryPanelProcessing => 'Processing...';

  @override
  String get glossaryPanelDropCsvHere => 'Drop CSV or TBX file here';

  @override
  String get glossaryPanelNoEntriesHint =>
      'No glossary entries.\nClick on the Detect Glossary button to get started.\nOr select a glossary from the list to view its entries.\nOr drag and drop a CSV or TBX file here.';

  @override
  String get glossaryPanelSelectBody => 'Select a glossary to work with:';

  @override
  String get glossaryPanelSaveDialogTitleReplace => 'Replace Glossary';

  @override
  String get glossaryPanelSaveDialogTitleSave => 'Save Glossary';

  @override
  String glossaryPanelSaveReplaceInfo(Object name) {
    return 'This will replace the existing glossary \"$name\"';
  }

  @override
  String get glossaryPanelSaveButtonSaveAs => 'Save As';

  @override
  String get glossaryPanelGenerating => 'Generating glossary...';

  @override
  String get glossaryPanelDeleteEntry => 'Delete entry';

  @override
  String get glossaryPanelInvertSelection => 'Invert selection';

  @override
  String get glossaryWidgetTitle => 'Glossary';

  @override
  String get glossaryWidgetRefreshTooltip => 'Refresh glossary list';

  @override
  String glossaryWidgetGlossariesSelected(Object count) {
    return '$count glossary selected';
  }

  @override
  String glossaryWidgetGlossariesSelectedPlural(Object count) {
    return '$count glossaries selected';
  }

  @override
  String get glossaryWidgetSelectGlossaries => 'Select Glossaries';

  @override
  String glossaryWidgetLoadFailed(Object error) {
    return 'Failed to load glossaries: $error';
  }

  @override
  String get glossaryWidgetNoGlossariesHint =>
      'No glossaries available. Create one in Settings -> Glossary';

  @override
  String glossaryWidgetTypeCountItems(Object type, Object count) {
    return '$type · $count items';
  }

  @override
  String glossaryWidgetTermsExtracted(Object count) {
    return '$count terms extracted from translation';
  }

  @override
  String glossaryWidgetPersonalCreated(Object count) {
    return 'Personal glossary created successfully!\nAdded $count terms.';
  }

  @override
  String glossaryWidgetPersonalReplaced(Object total) {
    return 'Personal glossary replaced successfully!\nTotal terms: $total';
  }

  @override
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total) {
    return 'Added $newCount new terms to personal glossary.\nSkipped $skipped existing terms.\nTotal terms: $total';
  }

  @override
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total) {
    return 'Personal glossary updated successfully!\nAdded $newCount new terms, updated $updatedCount existing terms.\nTotal terms: $total';
  }

  @override
  String glossaryWidgetAddToPersonalFailed(Object error) {
    return 'Failed to add to personal glossary: $error';
  }

  @override
  String get settingsTabsTranslation => 'Translation';

  @override
  String get settingsTabsAnonymization => 'Anonymization';

  @override
  String get settingsTabsUserManagement => 'User Management';

  @override
  String get settingsUserManagementTitle => 'User Management Mode';

  @override
  String get settingsUserManagementSubtitle =>
      'Choose login and permission policy for Web deployment. Settings and Setup Wizard are admin-only.';

  @override
  String get settingsUserManagementModeNoLogin => 'No login required';

  @override
  String get settingsUserManagementModeNoLoginDesc =>
      'Use without login; Settings and Setup Wizard available only after admin login.';

  @override
  String get settingsUserManagementModeLdap => 'LDAP login';

  @override
  String get settingsUserManagementModeLdapDesc =>
      'Log in with LDAP/AD; Settings and Setup Wizard for admin (domain group) only.';

  @override
  String get settingsUserManagementModeLocal => 'Local user login';

  @override
  String get settingsUserManagementModeLocalDesc =>
      'Authenticate against local user list on server.';

  @override
  String get settingsUserManagementInDevelopment => 'In development';

  @override
  String get settingsUserManagementSaveSuccess => 'User management mode saved';

  @override
  String settingsUserManagementSaveFailed(Object message) {
    return 'Save failed: $message';
  }

  @override
  String get settingsLocalUsersTitle => 'Local Users';

  @override
  String get settingsLocalUsersAddUser => 'Add user';

  @override
  String get settingsLocalUsersNoUsers => 'No local users found.';

  @override
  String get settingsLocalUsersDialogAddTitle => 'Add local user';

  @override
  String get settingsLocalUsersDialogEditTitle => 'Edit local user';

  @override
  String get settingsLocalUsersFieldUsername => 'Username';

  @override
  String get settingsLocalUsersFieldDisplayName => 'Display name (optional)';

  @override
  String get settingsLocalUsersFieldEmail => 'Email (optional)';

  @override
  String get settingsLocalUsersFieldRole => 'Role';

  @override
  String get settingsLocalUsersRoleUser => 'User';

  @override
  String get settingsLocalUsersRoleAdmin => 'Admin';

  @override
  String get settingsLocalUsersFieldPassword => 'Password';

  @override
  String get settingsLocalUsersPasswordHelper =>
      '8-128 chars, upper, lower, digit';

  @override
  String get settingsLocalUsersValidationUsernameRequired =>
      'Username is required';

  @override
  String get settingsLocalUsersValidationPasswordRequired =>
      'Password is required';

  @override
  String get settingsLocalUsersValidationPasswordTooShort =>
      'Password must be at least 8 characters';

  @override
  String get settingsLocalUsersValidationPasswordTooLong =>
      'Password must be no more than 128 characters';

  @override
  String get settingsLocalUsersValidationPasswordComplexity =>
      'Password must contain uppercase, lowercase, and digit';

  @override
  String get settingsLocalUsersOperationFailed => 'Operation failed';

  @override
  String get settingsLocalUsersResetPassword => 'Reset password';

  @override
  String settingsLocalUsersResetPasswordTitle(Object username) {
    return 'Reset password: $username';
  }

  @override
  String get settingsLocalUsersFieldNewPassword => 'New password';

  @override
  String get settingsLocalUsersPasswordResetSuccess =>
      'Password reset successfully';

  @override
  String get settingsLocalUsersPasswordResetFailed =>
      'Failed to reset password';

  @override
  String get settingsLocalUsersDeleteUser => 'Delete';

  @override
  String settingsLocalUsersDeleteUserTitle(Object username) {
    return 'Delete user: $username';
  }

  @override
  String get settingsLocalUsersDeleteConfirmation =>
      'This action will permanently delete the user from local user store. This cannot be undone.';

  @override
  String get settingsLocalUsersDeleteSuccess => 'User deleted';

  @override
  String get settingsLocalUsersDeleteFailed => 'Failed to delete user';

  @override
  String get settingsLocalUsersEdit => 'Edit';

  @override
  String get settingsLocalUsersCancel => 'Cancel';

  @override
  String get settingsLocalUsersSave => 'Save';

  @override
  String get settingsLocalUsersConfirm => 'Confirm';

  @override
  String get settingsLocalUsersTableUsername => 'Username';

  @override
  String get settingsLocalUsersTableDisplayName => 'Display name';

  @override
  String get settingsLocalUsersTableEmail => 'Email';

  @override
  String get settingsLocalUsersTableRole => 'Role';

  @override
  String get settingsLdapEnabled => 'Enable LDAP login';

  @override
  String get settingsLdapEnableHint =>
      'Test LDAP connection first before enabling.';

  @override
  String get settingsLdapProtocol => 'Protocol';

  @override
  String get settingsLdapProtocolLdap => 'LDAP';

  @override
  String get settingsLdapProtocolLdaps => 'LDAPS';

  @override
  String get settingsLdapHost => 'LDAP server (match certificate CN/SAN)';

  @override
  String get settingsLdapHostPlaceholder => 'ad.example.com or 192.168.x.x';

  @override
  String get settingsLdapPort => 'Port';

  @override
  String get settingsLdapPortPlaceholder => '389';

  @override
  String get settingsLdapBaseDn => 'User search Base DN';

  @override
  String get settingsLdapBaseDnPlaceholder => 'OU=Users,DC=example,DC=com';

  @override
  String get settingsLdapBindDnTemplate => 'Bind DN template';

  @override
  String settingsLdapBindDnPlaceholder(Object username) {
    return 'EXAMPLE\\$username or $username@example.com';
  }

  @override
  String get settingsLdapUserFilter => 'User filter';

  @override
  String settingsLdapUserFilterPlaceholder(Object username) {
    return '(sAMAccountName=$username)';
  }

  @override
  String get settingsLdapAdminGroupEnabled => 'Enable admin group query';

  @override
  String get settingsLdapAdminGroup => 'Admin group name';

  @override
  String get settingsLdapAdminGroupPlaceholder => 'Owlangs-Admins';

  @override
  String get settingsLdapGroupBaseDn => 'Group search Base DN';

  @override
  String get settingsLdapGroupBaseDnPlaceholder =>
      'OU=Groups,DC=example,DC=com';

  @override
  String get settingsLdapTlsVerify => 'Verify TLS certificate';

  @override
  String get settingsLdapTlsCacertfile => 'TLS CA certificate file path';

  @override
  String get settingsLdapTlsCacertfilePlaceholder => '/path/to/ca.crt';

  @override
  String get settingsLdapTestConnection => 'Test LDAP connection';

  @override
  String get settingsLdapSaveConfig => 'Save LDAP config';

  @override
  String get settingsLdapTestDialogTitle => 'Test LDAP connection';

  @override
  String get settingsLdapTestUsername => 'Username (without domain)';

  @override
  String get settingsLdapTestUsernamePlaceholder => 'testuser';

  @override
  String get settingsLdapTestPassword => 'Password';

  @override
  String get settingsLdapTestPasswordPlaceholder => '********';

  @override
  String get settingsLdapTestStart => 'Start test';

  @override
  String get settingsLdapTestSuccess =>
      'LDAP connection test succeeded. You can now enable LDAP.';

  @override
  String get settingsLdapTestFailed => 'LDAP connection test failed';

  @override
  String get settingsLdapConfigSaved => 'LDAP configuration saved';

  @override
  String get settingsLdapEnableRequireTest =>
      'Please test LDAP connection first before enabling LDAP.';

  @override
  String get settingsAdminOnlyDialogTitle => 'Admin Only';

  @override
  String get settingsAdminOnlyDialogMessage =>
      'Settings and Setup Wizard are available only to administrators. Please log in with an admin account to continue.';

  @override
  String get settingsAdminOnlyDialogGoToLogin => 'Go to Login';

  @override
  String get settingsAdminOnlyDialogClose => 'Close';

  @override
  String get aiPlatformOverview => 'Platform Overview';

  @override
  String aiPlatformConfiguredCount(Object configured, Object total) {
    return 'Configured $configured/$total platforms';
  }

  @override
  String get aiPlatformTestApiStatus => 'Test API Status';

  @override
  String get aiPlatformTesting => 'Testing...';

  @override
  String get aiPlatformCategoryLanguageModels => 'Language Models';

  @override
  String get aiPlatformCategoryParsingEngines => 'Parsing Engines';

  @override
  String aiPlatformConfiguredDragReorder(Object configured, Object total) {
    return 'Configured $configured/$total platforms (drag to reorder)';
  }

  @override
  String get aiPlatformNotConfigured => 'Not configured';

  @override
  String get aiPlatformNotTested => 'Not tested';

  @override
  String get aiPlatformApiAvailable => 'API available';

  @override
  String get aiPlatformAvailable => 'Available';

  @override
  String get aiPlatformUnavailable => 'Unavailable';

  @override
  String get aiPlatformConfigure => 'Configure';

  @override
  String aiPlatformConfigureTitle(Object name) {
    return 'Configure $name';
  }

  @override
  String get aiPlatformBasicInformation => 'Basic Information';

  @override
  String get aiPlatformPlatformName => 'Platform Name';

  @override
  String get aiPlatformPlatformNameHint =>
      'e.g., Doubao (DeepSeek / Volcano Ark)';

  @override
  String get aiPlatformApiUrl => 'API URL';

  @override
  String get aiPlatformApiUrlHint =>
      'e.g., https://ark.cn-beijing.volces.com/api/v3';

  @override
  String get aiPlatformMaxTokens => 'Max Tokens';

  @override
  String get aiPlatformMaxTokensHint => 'e.g., 4096';

  @override
  String get aiPlatformChunkSize => 'Chunk Size';

  @override
  String get aiPlatformChunkSizeHint => 'e.g., 3000';

  @override
  String get aiPlatformConcurrent => 'Concurrent Requests';

  @override
  String get aiPlatformConcurrentHint => 'e.g., 5';

  @override
  String get aiPlatformModel => 'Model';

  @override
  String get aiPlatformModelHint => 'e.g., deepseek-v3 / llama3.1-70b';

  @override
  String get aiPlatformApiKey => 'API Key';

  @override
  String get aiPlatformApiConfiguration => 'API Configuration';

  @override
  String get aiPlatformGetApiKey => 'Get API Key';

  @override
  String get aiPlatformCancel => 'Cancel';

  @override
  String get aiPlatformTestConnection => 'Test Connection';

  @override
  String get aiPlatformTestConnectionHint =>
      'After updating configuration, please click \"Test Connection\" below to verify the platform is available.';

  @override
  String get setupWizardConfigureApiKeyAndTest =>
      'Connection unavailable. Please configure API Key and click \"Test Connection\" to verify.';

  @override
  String get setupWizardSaveAndExit => 'Save and exit';

  @override
  String get setupWizardTitle => 'Setup Wizard';

  @override
  String get setupWizardStepWelcome => 'Welcome';

  @override
  String get setupWizardStepMineru => 'PDF / MinerU';

  @override
  String get setupWizardWelcomeIntro =>
      'This wizard will help you complete two key configurations:';

  @override
  String get setupWizardWelcomeBody =>
      '1. Select and configure your primary LLM platform.\n2. If you need to translate PDF/PNG etc., configure the MinerU parsing engine (optional).\n\nNote: After configuring, use \"Test Connection\" to verify.';

  @override
  String get setupWizardUiLanguageLabel => 'UI Language';

  @override
  String get setupWizardMineruDescription =>
      'MinerU handles layout parsing and segmentation for PDF / images.\nEnter MinerU API Key and URL below, then click \"Test Connection\" to verify.';

  @override
  String get setupWizardMineruConfigTitle => 'MinerU (parsing engine)';

  @override
  String get setupWizardSelectMineruPlatform => 'Select MinerU Platform';

  @override
  String get setupWizardMineruCloudOption =>
      'MinerU (Cloud) - Official cloud service';

  @override
  String get setupWizardMineruLocalOption =>
      'MinerU (Local) - Self-hosted deployment';

  @override
  String get setupWizardSelectLlmPlatform => 'Select LLM platform';

  @override
  String get setupWizardNoLlmPlatforms =>
      'No LLM platforms in AI Platform Settings. Add a platform in Settings first.';

  @override
  String get setupWizardMineruSaved => 'MinerU configuration saved';

  @override
  String get setupWizardPrevStep => 'Previous';

  @override
  String get setupWizardNextStep => 'Next';

  @override
  String get aiPlatformSave => 'Save';

  @override
  String get aiPlatformList => 'List';

  @override
  String get aiPlatformTemperature => 'Temperature';

  @override
  String get aiPlatformThinkingMode => 'Thinking Mode';

  @override
  String get aiPlatformThinkingDisable => 'Disable (Recommended)';

  @override
  String get aiPlatformThinkingEnable => 'Enable';

  @override
  String get aiPlatformThinkingDefault => 'Default';

  @override
  String get aiPlatformThinkingHint =>
      'Enable AI reasoning process for better translation quality';

  @override
  String get aiPlatformThinkingModeSupported => 'Support Thinking Mode';

  @override
  String get aiPlatformThinkingModeSupportedHint =>
      'Enable this if the platform supports thinking mode (e.g., Ollama with Qwen3)';

  @override
  String get aiPlatformSegmentLimitLabel => 'Segment Limit';

  @override
  String get aiPlatformSegmentLimitHint =>
      'Max segments per translation batch. Limits are applied together with chunk size. 0 = unlimited (cloud), 10 = recommended for local LLMs';

  @override
  String get aiPlatformSegmentLimitUnlimited => 'Unlimited';

  @override
  String get aiPlatformPleaseEnterApiKeyFirst =>
      'Please enter an API key first';

  @override
  String get aiPlatformPleaseEnterApiUrlFirst => 'Please enter API URL first';

  @override
  String get aiPlatformHasApiKey => 'Requires API Key';

  @override
  String get aiPlatformHasApiKeyHint =>
      'Uncheck for local deployments without API authentication';

  @override
  String get aiPlatformApiKeyOptionalHint => 'Leave empty if not required';

  @override
  String get optional => 'optional';

  @override
  String get aiPlatformConnectionTestSucceeded => 'Connection test succeeded';

  @override
  String get paddleOcrTestWarningTextOnly =>
      'Connected, but this server only returns basic text OCR (rec_texts lines — no doc_title, table, or formula blocks). Owlangs needs PaddleOCR-VL-1.6 document parsing. Example: deploy the cloud-style API POST /api/v2/ocr/jobs with model PaddleOCR-VL-1.6, not infer-only POST /ocr.';

  @override
  String get paddleOcrTestWarningUnverified =>
      'Connected (POST /ocr), but PaddleOCR-VL-1.6 layout parsing could not be verified. Ask your admin to deploy VL document parsing (titles, tables, formulas), e.g. POST /api/v2/ocr/jobs like cloud.';

  @override
  String get paddleOcrTestUnreachable =>
      'Cannot reach the self-hosted PaddleOCR service. Confirm it is running and the URL/port is correct (template default: http://localhost:8099). After a successful connection, Owlangs checks for PaddleOCR-VL-1.6 document parsing; infer-only text OCR will show a separate orange warning.';

  @override
  String mineruConnectionSuccessWithVersion(String version) {
    return 'Connection test succeeded. MinerU version: $version';
  }

  @override
  String mineruConnectionSuccessWithApiVersion(String version) {
    return 'Connection test succeeded. MinerU API $version';
  }

  @override
  String mineruConnectionSuccessWithModelVersion(String modelVersion) {
    return 'Connection test succeeded. MinerU engine: $modelVersion';
  }

  @override
  String mineruConnectionSuccessCloudWithApi(String apiVersion) {
    return 'Connection test succeeded. Cloud MinerU (API $apiVersion; server version is not exposed by the cloud API)';
  }

  @override
  String aiPlatformConnectionTestFailed(Object message) {
    return 'Connection test failed: $message';
  }

  @override
  String get aiPlatformNoModelsFound => 'No models found';

  @override
  String get aiPlatformFailedToLoadModels => 'Failed to load models';

  @override
  String aiPlatformErrorLoadingModels(Object error) {
    return 'Error loading models: $error';
  }

  @override
  String get aiPlatformSelectModel => 'Select Model';

  @override
  String get aiPlatformNoModelsAvailable => 'No models available';

  @override
  String get aiPlatformMineruSettings => 'MinerU Settings';

  @override
  String get aiPlatformEnterMineruApiKey => 'Enter MinerU API Key';

  @override
  String get aiPlatformGetMineruApiKey => 'Get MinerU API Key';

  @override
  String get aiPlatformModelVersion => 'Model Version';

  @override
  String get aiPlatformModelVersionHint => 'hybrid-auto-engine';

  @override
  String get aiPlatformTimeout => 'Read Timeout (seconds)';

  @override
  String get aiPlatformTimeoutHint =>
      '200 (cloud) or 300 (local). Max wait time for LLM response.';

  @override
  String get aiPlatformWriteTimeout => 'Write Timeout (seconds)';

  @override
  String get aiPlatformWriteTimeoutHint =>
      '300 (default). Max wait time for sending data to LLM.';

  @override
  String get aiPlatformTestConnectTimeout => 'Connect Test Timeout (seconds)';

  @override
  String get aiPlatformTestConnectTimeoutHint =>
      '30 (default). Max wait time for connectivity test before starting translation.';

  @override
  String get aiPlatformTestRequestTimeout => 'Test Request Timeout (seconds)';

  @override
  String get aiPlatformTestRequestTimeoutHint =>
      '10 (default). Max wait for each probe request during connectivity test.';

  @override
  String get aiPlatformMineruApiUrlHint => 'https://mineru.net/api/v4';

  @override
  String get aiPlatformOcrSettings => 'OCR Settings';

  @override
  String get aiPlatformFormulaOcr => 'Formula OCR';

  @override
  String get aiPlatformFormulaOcrSubtitle =>
      'Enable OCR for mathematical formulas';

  @override
  String get aiPlatformTableOcr => 'Table OCR';

  @override
  String get aiPlatformTableOcrSubtitle => 'Enable OCR for tables';

  @override
  String get settingsFontEditSizeTitle => 'Edit Font Size';

  @override
  String get settingsFontEditSizeSubtitle =>
      'Font size when editing translated segments';

  @override
  String get settingsTranslationTitle => 'Translation Settings';

  @override
  String get settingsTranslationNotice =>
      'These settings will apply to new translation tasks only.';

  @override
  String get settingsTargetLanguageTitle => 'Default Target Language';

  @override
  String get settingsTargetLanguageNotice =>
      'Sets the default target language for new translation tasks. You can still change it per task in Quick Settings.';

  @override
  String get settingsTranslationParamsTitle => 'Translation Parameters';

  @override
  String get settingsTranslationConcurrentTitle => 'Concurrent Requests';

  @override
  String get settingsTranslationConcurrentHint =>
      'Recommended: 3 (adjust 1–8 based on model and quota)';

  @override
  String get settingsTranslationChunkRetryTitle => 'Chunk retry (per request)';

  @override
  String get settingsTranslationChunkRetryHint =>
      'Recommended: 3–5 (retries when a translation chunk or API call fails)';

  @override
  String get settingsTranslationSegmentAutoRetryTitle =>
      'Queue mode: failed-segment auto rounds';

  @override
  String get settingsTranslationSegmentAutoRetryHint =>
      'Recommended: 3 (1–10 batch retranslate rounds after main translation; queued mode only)';

  @override
  String get settingsTranslationChunkSizeTitle => 'Chunk Size (tokens)';

  @override
  String get settingsTranslationChunkSizeHint =>
      'Recommended: 3000 tokens per request (adjust by model context size)';

  @override
  String get settingsExclusionTitle => 'Default Exclusion Rules';

  @override
  String get settingsExclusionNotice =>
      'Toggle ON = auto-exclude during Extract; Toggle OFF = detect only (user decides per segment).';

  @override
  String get settingsExclusionImageTitle => 'Image';

  @override
  String get settingsExclusionImageSubtitle =>
      'Image placeholders and pure-image content';

  @override
  String get settingsExclusionFormulaTitle => 'Formula';

  @override
  String get settingsExclusionFormulaSubtitle => 'LaTeX / MathML formulas';

  @override
  String get settingsExclusionReferenceTitle => 'Reference';

  @override
  String get settingsExclusionReferenceSubtitle =>
      'Citations and bibliographic references';

  @override
  String get settingsExclusionIdentifierTitle => 'Identifier';

  @override
  String get settingsExclusionIdentifierSubtitle =>
      'URLs, emails, serial numbers, code snippets';

  @override
  String get settingsExclusionStructuralTitle => 'Structural';

  @override
  String get settingsExclusionStructuralSubtitle =>
      'Headers, footers, footnotes, page numbers';

  @override
  String get settingsExclusionTableTitle => 'Table';

  @override
  String get settingsExclusionTableSubtitle =>
      'Table content (markdown / PDF tables)';

  @override
  String get settingsExclusionChartTitle => 'Chart';

  @override
  String get settingsExclusionChartSubtitle =>
      'Chart content (Figure, chart blocks)';

  @override
  String get settingsExclusionLanguageMatchTitle => 'Language Match';

  @override
  String get settingsExclusionLanguageMatchSubtitle =>
      'Source language matches target language';

  @override
  String get settingsTranslateOutputSuffixTitle => 'Translation Output Suffix';

  @override
  String get settingsTranslateOutputSuffixHint =>
      'Appended to translated filenames (leave empty for no suffix)';

  @override
  String get settingsConvertOutputSuffixTitle => 'Conversion Output Suffix';

  @override
  String get settingsConvertOutputSuffixHint =>
      'Appended to converted filenames (leave empty for no suffix)';

  @override
  String get settingsLanguageDialogTitle => 'Select Language';

  @override
  String get settingsUnitPt => 'pt';

  @override
  String get glossaryGeneratedTabTitle => 'Generated Glossary';

  @override
  String glossaryErrorRefresh(Object error) {
    return 'Failed to refresh glossaries: $error';
  }

  @override
  String get glossaryWarningNoGenerated => 'No generated glossary available';

  @override
  String get glossaryPanelView => 'View';

  @override
  String get glossaryPanelAddToPersonal => 'Add to Personal';

  @override
  String get glossaryPanelNoGlobalGlossaries =>
      'No global glossaries available';

  @override
  String get glossaryPanelSelectTitle => 'Select Glossary';

  @override
  String get glossaryPanelSelectHint => 'Select glossary...';

  @override
  String glossaryPanelSelected(Object name) {
    return 'Selected: $name';
  }

  @override
  String get glossaryPanelSelectConfirm => 'Select';

  @override
  String get glossaryPanelMergeToCurrent => 'Merge to Current Glossary';

  @override
  String glossaryPanelLoadedGlossary(Object name) {
    return 'Loaded glossary: $name';
  }

  @override
  String glossaryPanelLoadFailed(Object error) {
    return 'Failed to load glossary: $error';
  }

  @override
  String glossaryPanelMergedIntoCurrent(Object glossaryName) {
    return 'Merged \"$glossaryName\" into current glossary';
  }

  @override
  String glossaryPanelMergeFailed(Object error) {
    return 'Merge failed: $error';
  }

  @override
  String get glossaryPanelEnterName => 'Enter a name for the glossary';

  @override
  String get glossaryPanelSaveDialogHint =>
      'Enter a name for the glossary or select an existing one to replace:';

  @override
  String get glossaryPanelReplaceTitle => 'Replace Global Glossary';

  @override
  String glossaryPanelReplaceBody(Object glossaryName) {
    return 'This will replace all entries in \"$glossaryName\" with current glossary entries. Continue?';
  }

  @override
  String get glossaryPanelReplaceConfirm => 'Replace';

  @override
  String glossaryPanelReplacedGlobal(Object name) {
    return 'Replaced global glossary: $name';
  }

  @override
  String glossaryPanelSavedAsNewGlobal(Object name) {
    return 'Saved as new global glossary: $name';
  }

  @override
  String glossaryPanelSaveFailed(Object error) {
    return 'Save failed: $error';
  }

  @override
  String get glossaryPanelDetect => 'Detect Glossary';

  @override
  String get glossaryPanelEdit => 'Edit';

  @override
  String get glossaryPanelCreate => 'Create Glossary';

  @override
  String get glossaryPanelSelect => 'Select';

  @override
  String get glossaryPanelImport => 'Import';

  @override
  String get glossaryPanelExport => 'Export';

  @override
  String get glossaryPanelSave => 'Save';

  @override
  String get glossaryPanelAddEntry => 'Add Entry';

  @override
  String get glossaryPanelClear => 'Clear';

  @override
  String get glossaryPanelApply => 'Apply';

  @override
  String get glossaryPanelColumnSource => 'Source';

  @override
  String get glossaryPanelColumnTarget => 'Target';

  @override
  String get glossaryPanelColumnActions => 'Actions';

  @override
  String get translationStepsUploadTooltipReady => 'File selected';

  @override
  String get translationStepsUploadTooltipNotReady => 'Select a file to start';

  @override
  String get translationStepsExtractTooltipReady => 'View extracted source';

  @override
  String get translationStepsExtractTooltipNotReady =>
      'Extract will be ready after import';

  @override
  String get translationStepsGlossaryTooltipSkipped => 'Glossary skipped';

  @override
  String get translationStepsGlossaryTooltipEnabled => 'Glossary enabled';

  @override
  String get translationStepsGlossaryTooltipDisabled =>
      'Generate or select a glossary to enable';

  @override
  String get translationStepsTranslateTooltipReady => 'Translation completed';

  @override
  String get translationStepsTranslateTooltipNotReady =>
      'Run translation to enable';

  @override
  String get glossaryDialogAddTitle => 'Add to Personal Glossary';

  @override
  String glossaryDialogAddBody(Object termCount) {
    return 'This will add $termCount terms to your personal glossary.';
  }

  @override
  String get glossaryDialogAddPreviewTitle => 'Preview (first 5 terms):';

  @override
  String glossaryDialogAddMoreTerms(Object remainingCount) {
    return '... and $remainingCount more terms';
  }

  @override
  String get glossaryDialogMergeStrategyTitle => 'Merge Strategy:';

  @override
  String get glossaryDialogMergeUpdateTitle => 'Update (Recommended)';

  @override
  String get glossaryDialogMergeUpdateSubtitle =>
      'Update existing terms, add new ones';

  @override
  String get glossaryDialogMergeAppendTitle => 'Append';

  @override
  String get glossaryDialogMergeAppendSubtitle =>
      'Only add new terms, skip existing ones';

  @override
  String get glossaryDialogMergeReplaceTitle => 'Replace';

  @override
  String get glossaryDialogMergeReplaceSubtitle =>
      'Replace entire glossary with these terms';

  @override
  String get glossaryDialogCancel => 'Cancel';

  @override
  String get glossaryDialogReviewAndAdd => 'Review & Add';

  @override
  String get glossaryConfirmAddTitle => 'Confirm Add to Personal Glossary';

  @override
  String glossaryConfirmAddBody(Object termCount) {
    return 'Add $termCount terms to your personal glossary?';
  }

  @override
  String get glossaryConfirmAddStrategyUpdate =>
      'Strategy: Update existing terms, add new ones';

  @override
  String get glossaryConfirmAddStrategyAppend =>
      'Strategy: Only add new terms, skip existing ones';

  @override
  String get glossaryConfirmAddStrategyReplace =>
      'Strategy: Replace entire glossary';

  @override
  String get glossaryConfirmAddAutoCreateHint =>
      'If your personal glossary doesn\'t exist, it will be created automatically.';

  @override
  String get glossaryConfirmAddButton => 'Add';

  @override
  String get glossaryExportDialogTitle => 'Save Glossary';

  @override
  String glossaryExportSuccess(Object filename) {
    return 'Glossary exported: $filename';
  }

  @override
  String glossaryExportFailed(Object error) {
    return 'Failed to export glossary: $error';
  }

  @override
  String glossaryCsvValidationFailed(Object errors) {
    return 'CSV file validation failed:\n\n$errors';
  }

  @override
  String get glossaryCsvNoValidEntries => 'CSV file contains no valid entries.';

  @override
  String get glossaryImportDialogTitle => 'Import Glossary';

  @override
  String glossaryImportDialogBodyEmpty(Object count) {
    return 'Found $count entries in the file.\n\nThe current glossary is empty. Imported entries will be added.';
  }

  @override
  String glossaryImportDialogBody(Object count) {
    return 'Found $count entries in the file.\n\nChoose how to import:';
  }

  @override
  String get glossaryImportButtonImport => 'Import';

  @override
  String get glossaryImportButtonReplace => 'Replace';

  @override
  String get glossaryImportButtonMerge => 'Merge';

  @override
  String glossaryImportResult(Object count, Object mode) {
    return 'Imported $count entries ($mode)';
  }

  @override
  String glossaryErrorImport(Object error) {
    return 'Failed to import glossary: $error';
  }

  @override
  String get glossaryErrorFileData =>
      'Failed to read file data. Please try again.';

  @override
  String get glossaryErrorFilePath =>
      'File path is not available. Please try again.';

  @override
  String get glossaryErrorOnlyCsv =>
      'Only CSV and TBX files are supported for glossary import.';

  @override
  String get glossaryExportFormatLabel => 'Export format';

  @override
  String get glossaryExportFormatTbxSubtitle => 'TermBase eXchange (ISO 12620)';

  @override
  String get glossaryExportSourceLanguage => 'Source language';

  @override
  String get glossaryExportButtonExport => 'Export';

  @override
  String get extractFormatConversionFailed => 'Format conversion failed.';

  @override
  String get fileUploadDisabledMessage =>
      'File selection disabled (processing in progress)';

  @override
  String get fileUploadSupportedFormats =>
      'Supported: Word (DOCX), PowerPoint (PPTX), Excel (XLSX/CSV), PDF, Markdown, TXT, HTML, SRT, JSON, EPUB, MOBI, Qt TS, PNG, JPEG';

  @override
  String get fileUploadDropHere => 'Drop file here';

  @override
  String get fileUploadHint => 'Drag & drop file here or click to select';

  @override
  String get fileUploadCancelTask => 'Cancel Current Task';

  @override
  String get exclusionPanelExcludeAll => 'Exclude All';

  @override
  String get exclusionPanelCancelUserExclusion => 'Restore Auto Exclusions';

  @override
  String get exclusionPanelClearAllExclusions => 'Clear All Exclusions';

  @override
  String get exclusionPanelExclusionByType => 'Exclusion By Type:';

  @override
  String get exclusionPanelStructuralHeader => 'Structural (Header)';

  @override
  String get exclusionPanelStructuralFooter => 'Structural (Footer)';

  @override
  String get exclusionPanelUserExcluded => 'User Excluded';

  @override
  String get exclusionPanelExcluded => 'Excluded';

  @override
  String get exclusionPanelFilterDisplayMode => 'Filter Display Mode:';

  @override
  String get exclusionPanelRebuild => 'Rebuild';

  @override
  String get exclusionPanelPage => 'Page';

  @override
  String get exclusionPanelRebuildTooltip =>
      'Show only matching segments in new pagination';

  @override
  String get exclusionPanelPageTooltip => 'Filter within current page';

  @override
  String get exclusionPanelSegmentTypeFilters => 'Segment Type Filters:';

  @override
  String get exclusionPanelCollapsePanelTooltip => 'Collapse panel';

  @override
  String get exclusionPanelExclusionControls => 'Exclusion Controls:';

  @override
  String exclusionPanelExcludeCategory(Object count, Object name) {
    return 'Exclude $name ($count)';
  }

  @override
  String get exclusionPanelChangeReasonTitle => 'Change Exclusion Reason';

  @override
  String get exclusionPanelCurrentLabel => 'Current: ';

  @override
  String get exclusionPanelSelectNewReason => 'Select new reason:';

  @override
  String get exclusionPanelNoneRemoveExclusion => 'None (Remove Exclusion)';

  @override
  String get exclusionPanelApply => 'Apply';

  @override
  String get exclusionPanelExpandFilterPanel => 'Expand Filter Panel';

  @override
  String get exclusionPanelCollapseFilterPanel => 'Collapse Filter Panel';

  @override
  String extractToolbarSegments(Object end, Object start, Object total) {
    return 'Segments ($start-$end of $total)';
  }

  @override
  String get extractToolbarCancel => 'Cancel';

  @override
  String get extractCancelExtractionTitle => 'Cancel Extraction';

  @override
  String get extractCancelExtractionContent =>
      'Are you sure you want to cancel the extraction? This cannot be undone.';

  @override
  String get extractCancelExtractionNo => 'No';

  @override
  String get extractCancelExtractionYes => 'Yes';

  @override
  String get extractExtractionCancelled => 'Extraction cancelled';

  @override
  String get extractMineruConfigRequiredTitle =>
      'MinerU Configuration Required';

  @override
  String extractMineruConfigRequiredContent(Object error) {
    return 'Failed to connect to MinerU API. Please configure MinerU settings in the Settings page.\n\nError details:\n$error';
  }

  @override
  String get extractOpenSettings => 'Open Settings';

  @override
  String extractErrorLabel(Object error) {
    return 'Error: $error';
  }

  @override
  String get extractRetry => 'Retry';

  @override
  String get extractTaskTypeDetectIdentifier => 'Detect Identifier';

  @override
  String get extractTaskTypeDetectLanguage => 'Detect Language';

  @override
  String get extractTaskTypeDetectExclusions => 'Detect Exclusions';

  @override
  String get translationStatsTitle => 'Translation Statistics';

  @override
  String get translationStatsDocuments => 'Documents';

  @override
  String get translationStatsPages => 'Pages';

  @override
  String translationStatsLastUpdated(Object date) {
    return 'Last updated: $date';
  }

  @override
  String get translationStatsLoadFailed => 'Failed to load statistics';

  @override
  String get translationStatsJustNow => 'Just now';

  @override
  String get translationStatsOneMinuteAgo => '1 minute ago';

  @override
  String translationStatsMinutesAgo(Object count) {
    return '$count minutes ago';
  }

  @override
  String get translationStatsOneHourAgo => '1 hour ago';

  @override
  String translationStatsHoursAgo(Object count) {
    return '$count hours ago';
  }

  @override
  String get translationStatsYesterday => 'Yesterday';

  @override
  String translationStatsDaysAgo(Object count) {
    return '$count days ago';
  }

  @override
  String get aiPlatformDisplayName => 'Display Name';

  @override
  String get aiPlatformParserSubtype => 'Parser Subtype';

  @override
  String get aiPlatformParserSubtypeCloud => 'Cloud';

  @override
  String get aiPlatformParserSubtypeLocal => 'Local';

  @override
  String get translationQueueEdit => 'Labeled Edit';

  @override
  String get translationQueueSelectFormats => 'Select';

  @override
  String get translationQueueSelectFormatsTitle => 'Select Download Formats';

  @override
  String get translationQueueSelectFormatsFormatLabel => 'Format';

  @override
  String get translationQueueSelectFormatsDownload => 'Download';

  @override
  String get translationQueueBatchLabelHint =>
      'Batch label (for task queue grouping)';

  @override
  String get translationQueueBatchCreateFailed =>
      'Failed to create upload batch';

  @override
  String get translationQueueUngroupedSection => 'Ungrouped';

  @override
  String translationQueueBatchProgress(int completed, int total) {
    return '$completed/$total completed';
  }

  @override
  String get translationQueueBatchSelectAll => 'Select batch';

  @override
  String get translationQueueBatchDownload => 'Download batch';

  @override
  String get translationQueueBatchDelete => 'Delete batch';

  @override
  String get translationQueueBatchDeleteTitle => 'Delete this batch?';

  @override
  String get translationQueueBatchDeleteMessage =>
      'All tasks in this batch will be removed from the queue and their cached results deleted.';

  @override
  String get reeditTitle => 'Edit Translation';

  @override
  String get reeditSaveExport => 'Save && Export';

  @override
  String get reeditFetchError => 'Failed to load translation segments.';

  @override
  String get reeditSaveSuccess => 'Changes saved successfully.';

  @override
  String get reeditSaveError => 'Failed to save changes.';

  @override
  String get workspaceCloseFlowTitle => 'Close this flow?';

  @override
  String get workspaceCloseFlowMessage =>
      'Closing this flow will discard any unsaved changes.';

  @override
  String get workspaceCloseFlowSaveToQueue => 'Save and close';

  @override
  String get workspaceCloseFlowDestroy => 'Destroy and close';

  @override
  String get workspaceCloseFlowCancel => 'Cancel';

  @override
  String get fetchUrlCancel => 'Cancel';

  @override
  String get fetchUrl => 'Fetch URL';

  @override
  String get fetchUrlClose => 'Close';

  @override
  String get loginSubtitleFeatures =>
      'Document Translation\nFormat Conversion\nURL Fetch';

  @override
  String get loginSubtitleTagline => 'AI Document Processing System';

  @override
  String get loginUsernameLabel => 'Username';

  @override
  String get loginUsernameHint => 'Please enter username';

  @override
  String get loginUsernameRequiredError => 'Please enter your username';

  @override
  String get loginUsernameMinLengthError =>
      'Username must be at least 3 characters';

  @override
  String get loginPasswordLabel => 'Password';

  @override
  String get loginPasswordHint => 'Please enter password';

  @override
  String get loginPasswordRequiredError => 'Please enter your password';

  @override
  String get loginForgotPassword => 'Forgot Password?';

  @override
  String get loginPasswordRecoveryTitle => 'Password Recovery';

  @override
  String get loginPasswordRecoveryContactAdmin =>
      'Please contact your administrator to reset your password.';

  @override
  String get loginPasswordRecoveryAdminHint =>
      'Administrators can reset passwords through the user management page after logging in.';

  @override
  String get loginAuthMethodDefault => 'Using Default Authentication';

  @override
  String get loginCopyErrorLabel => 'Copy';

  @override
  String get loginErrorCopiedMessage => 'Error message copied to clipboard';

  @override
  String get loginWelcomeBack => 'Welcome back';

  @override
  String get loginFeatureFormats =>
      'PDF, DOCX, XLSX, HTML, EPUB, MOBI\nand 15+ more formats';

  @override
  String get loginFeatureLayout =>
      'Layout-preserving translation\nwith high fidelity';

  @override
  String get loginFeaturePlatforms =>
      '20+ LLM platforms supported\nincluding OpenAI, Claude, Ollama';

  @override
  String get loginPasswordRecoveryAdminGuide =>
      'If you are an administrator, please follow the password recovery process.';

  @override
  String get commonDarkMode => 'Dark Mode';

  @override
  String get commonLightMode => 'Light Mode';

  @override
  String segmentPdfFontSizeAuto(String sizePt) {
    return 'Auto (${sizePt}pt)';
  }

  @override
  String get segmentPdfFontSizeAutoUnknown => 'Auto';

  @override
  String segmentPdfFontSizeManual(String sizePt) {
    return '${sizePt}pt';
  }

  @override
  String segmentRotationLabel(int degrees) {
    return '$degrees°';
  }

  @override
  String get segmentRotationOff => 'Rotate';

  @override
  String get segmentRotationNone => 'No rotation';

  @override
  String get segmentRotationMenuTitle => 'Angle';

  @override
  String segmentTableStrokeLabel(String strokePt) {
    return '$strokePt pt';
  }

  @override
  String get segmentTableStrokeOff => 'Grid';

  @override
  String get segmentTableStrokeNone => 'None';

  @override
  String get segmentTableStrokeMenuTitle => 'Border weight';

  @override
  String get segmentTableBorderMenuTitle => 'Border style';

  @override
  String get segmentTableBorderGrid => 'Full grid';

  @override
  String get segmentTableBorderBooktabs => 'Three lines (1 title row)';

  @override
  String get segmentTableBorderBooktabs2 => 'Three lines (2 title rows)';

  @override
  String get segmentTableBorderBooktabs3 => 'Three lines (3 title rows)';

  @override
  String get segmentTableBorderHorizontal => 'Horizontal lines';

  @override
  String get segmentTableBorderOuter => 'Outer box';

  @override
  String get segmentTableBorderNone => 'No lines';

  @override
  String get segmentTableBorderFollowGlobal => 'Follow task default';

  @override
  String get segmentItemExclude => 'Exclude';

  @override
  String get segmentItemEdit => 'Edit';

  @override
  String get segmentItemRetry => 'Retry';

  @override
  String get segmentItemMarkedRetry => 'Marked Retry';

  @override
  String get segmentItemClear => 'Clear';

  @override
  String get segmentItemCleared => 'Cleared';

  @override
  String get segmentItemFix => 'Fix';

  @override
  String segmentItemExclusionBadge(String reason) {
    return 'EX: $reason';
  }

  @override
  String get segmentItemExclusionRemoveTooltip => 'Click to remove exclusion';

  @override
  String get segmentItemExclusionLockedTooltip =>
      'This segment is automatically excluded and cannot be unexcluded';

  @override
  String get segmentItemExclusionEditTooltip =>
      'Click to edit exclusion reason';

  @override
  String get segmentItemExclusionRemoved => 'Exclusion removed';

  @override
  String get segmentItemExclusionReasonUpdated => 'Exclusion reason updated';

  @override
  String segmentItemExclusionUpdateFailed(String error) {
    return 'Failed to update exclusion reason: $error';
  }

  @override
  String get segmentItemUndoEditTooltip => 'Undo (Edit)';

  @override
  String get segmentItemRedoEditTooltip => 'Redo (Edit)';

  @override
  String get segmentItemUndoSaveTooltip => 'Undo (Save)';

  @override
  String get segmentItemRedoSaveTooltip => 'Redo (Save)';

  @override
  String get segmentItemCancel => 'Cancel';

  @override
  String get segmentItemSave => 'Save';

  @override
  String get segmentItemEditShortcutHint =>
      'Press Ctrl+Enter to save, Esc to cancel';

  @override
  String get segmentItemTranslationHint => 'Enter translation...';

  @override
  String segmentItemSaveFailed(String error) {
    return 'Failed to save: $error';
  }

  @override
  String get segmentPdfFontSizeTitle => 'PDF font size';

  @override
  String get segmentPdfTypographyTitle => 'PDF typography';

  @override
  String get segmentPdfTypographyFontTitle => 'PDF font';

  @override
  String get segmentPdfTypographyLeadingTitle => 'Line spacing';

  @override
  String get segmentPdfTypographyPreviewLabel => 'Preview';

  @override
  String get segmentPdfTypographyBold => 'Bold';

  @override
  String get segmentPdfTypographyItalic => 'Italic';

  @override
  String segmentPdfTypographyFontSizeLabel(String sizePt) {
    return 'Font size: $sizePt pt';
  }

  @override
  String segmentPdfTypographyLeadingLabel(String leadingEm) {
    return 'Line spacing: $leadingEm em';
  }

  @override
  String get segmentPdfFontSizeReset => 'Reset to auto';

  @override
  String get segmentPdfTypographyResetFont => 'Reset font to auto';

  @override
  String get segmentPdfTypographyResetLeading => 'Reset line spacing to auto';

  @override
  String get segmentPdfFontSizeApply => 'Apply';

  @override
  String get translationPreviewPdfRevision => 'Preview revision';

  @override
  String get translationPreviewPdfRevisionCompare => 'Compare view';

  @override
  String get translationPreviewLayoutComparePreview => 'Compare preview';

  @override
  String get translationPreviewLayoutTranslationRevision =>
      'Translation revision';

  @override
  String get translationPreviewLayoutCompareRevision => 'Compare revision';

  @override
  String get translationPreviewAutoRefreshPdf => 'Auto refresh PDF';

  @override
  String get translationPreviewFollowSegmentPage => 'Follow segment page';

  @override
  String get translationPreviewFollowSegmentPageDesc =>
      'When enabled, the translation PDF preview jumps to the page of the focused or checked segment';

  @override
  String get translationPreviewMarkSelectedSegment => 'Mark selected segment';

  @override
  String get translationPreviewMarkSelectedSegmentDesc =>
      'When enabled, show a frame around the selected segment on the translation preview';

  @override
  String get translationPreviewEditSegmentBbox => 'Edit Bbox';

  @override
  String get translationPreviewEditSegmentBboxDesc =>
      'When enabled, drag handles to adjust bounding box of the selected segment';

  @override
  String get translationPreviewAutoRotateSidewaysText => 'Auto rotate';

  @override
  String get translationPreviewAutoRotateSidewaysTextDesc =>
      'When enabled, rotate tall narrow text blocks (height/width above threshold) by 90° for sideways layout';

  @override
  String get translationPreviewAutoRotateAspectRatio => 'H/W ≥';

  @override
  String get translationPreviewAutoRotateAspectRatioDesc =>
      'Minimum bbox height/width ratio to trigger auto rotation (default 20)';

  @override
  String get translationPreviewAutoRotateDegrees => 'Angle°';

  @override
  String get translationPreviewAutoRotateControlsDesc =>
      'Auto rotation threshold (height/width) and angle in degrees (90, 180, or 270; default 270)';

  @override
  String get translationPreviewStaleSession =>
      'Preview unavailable. Reopen revision preview from the translation panel.';

  @override
  String translationPreviewPdfPageIndicator(String current, String total) {
    return 'Page $current / $total';
  }

  @override
  String get translationPreviewRefreshPdf => 'Refresh PDF';

  @override
  String get translationPreviewPdfUpdating => 'Updating PDF…';

  @override
  String get translationPreviewBatchFont => 'Font';

  @override
  String get translationPreviewBatchFontTooltip =>
      'Apply font settings to selected segments';

  @override
  String get translationPreviewBatchFontSizeDecreaseTooltip =>
      'Decrease font size by 0.1 pt for selected segments';

  @override
  String get translationPreviewBatchFontSizeIncreaseTooltip =>
      'Increase font size by 0.1 pt for selected segments';

  @override
  String get translationPreviewBatchTableBorder => 'Table lines';

  @override
  String get translationPreviewBatchTableBorderTooltip =>
      'Set this task\'s table border style and stroke width for preview revision (segment settings override)';

  @override
  String get translationPreviewBatchLeading => 'Batch line spacing';

  @override
  String get translationPreviewBatchLeadingTooltip =>
      'Apply line spacing to selected segments';

  @override
  String get translationPreviewPdfRevisionSelectAll => 'Select all';

  @override
  String get translationPreviewPdfRevisionInvertSelection => 'Invert selection';

  @override
  String get translationPreviewPdfRevisionPageFilterLabel => 'Page';

  @override
  String get translationPreviewPdfRevisionPageFilterAll => 'All pages';

  @override
  String get translationPreviewPdfRevisionPageFilterSelectAll =>
      'Select all pages';

  @override
  String get segmentPdfRevisionFontLabel => 'Font';

  @override
  String get segmentPdfRevisionEditLabel => 'Edit';

  @override
  String get segmentPdfRevisionClearLabel => 'Clear';
}
