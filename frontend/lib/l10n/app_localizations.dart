import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_ko.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
    Locale('ja'),
    Locale('ko'),
    Locale('zh')
  ];

  /// No description provided for @settingsGeneralTitle.
  ///
  /// In en, this message translates to:
  /// **'General Settings'**
  String get settingsGeneralTitle;

  /// No description provided for @settingsGeneralDarkModeTitle.
  ///
  /// In en, this message translates to:
  /// **'Dark Mode'**
  String get settingsGeneralDarkModeTitle;

  /// No description provided for @settingsGeneralDarkModeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable dark theme (applied immediately)'**
  String get settingsGeneralDarkModeSubtitle;

  /// No description provided for @settingsGeneralLanguageTitle.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get settingsGeneralLanguageTitle;

  /// No description provided for @settingsGeneralNotificationsTitle.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get settingsGeneralNotificationsTitle;

  /// No description provided for @settingsGeneralNotificationsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Receive notifications for completed tasks (applied immediately)'**
  String get settingsGeneralNotificationsSubtitle;

  /// No description provided for @settingsGeneralAutoSaveTitle.
  ///
  /// In en, this message translates to:
  /// **'Auto Save'**
  String get settingsGeneralAutoSaveTitle;

  /// No description provided for @settingsGeneralAutoSaveSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Automatically save work in progress (applied immediately)'**
  String get settingsGeneralAutoSaveSubtitle;

  /// No description provided for @settingsGeneralShowAdsTitle.
  ///
  /// In en, this message translates to:
  /// **'Show ADs'**
  String get settingsGeneralShowAdsTitle;

  /// No description provided for @settingsGeneralShowAdsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Show AD placeholders on Home and in Flow (stored in system.json)'**
  String get settingsGeneralShowAdsSubtitle;

  /// No description provided for @settingsGeneralClearStatsButton.
  ///
  /// In en, this message translates to:
  /// **'Clear Statistics'**
  String get settingsGeneralClearStatsButton;

  /// No description provided for @settingsGeneralClearStatsConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Clear Statistics?'**
  String get settingsGeneralClearStatsConfirmTitle;

  /// No description provided for @settingsGeneralClearStatsConfirmMessage.
  ///
  /// In en, this message translates to:
  /// **'This will reset the document and page count displayed on the home page to 0. This action cannot be undone.'**
  String get settingsGeneralClearStatsConfirmMessage;

  /// No description provided for @settingsGeneralClearStatsConfirmButton.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get settingsGeneralClearStatsConfirmButton;

  /// No description provided for @settingsGeneralClearStatsSuccess.
  ///
  /// In en, this message translates to:
  /// **'Statistics cleared successfully.'**
  String get settingsGeneralClearStatsSuccess;

  /// No description provided for @backToHome.
  ///
  /// In en, this message translates to:
  /// **'Back to Home'**
  String get backToHome;

  /// No description provided for @settingsFontSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Font Settings'**
  String get settingsFontSectionTitle;

  /// No description provided for @settingsFontPreviewSizeTitle.
  ///
  /// In en, this message translates to:
  /// **'Preview Font Size'**
  String get settingsFontPreviewSizeTitle;

  /// No description provided for @settingsFontPreviewSizeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Font size for source and target text in preview'**
  String get settingsFontPreviewSizeSubtitle;

  /// No description provided for @translationToolbarFilterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get translationToolbarFilterAll;

  /// No description provided for @translationToolbarFilterFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get translationToolbarFilterFailed;

  /// No description provided for @translationToolbarFilterIncluded.
  ///
  /// In en, this message translates to:
  /// **'Included'**
  String get translationToolbarFilterIncluded;

  /// No description provided for @translationToolbarFilterExcluded.
  ///
  /// In en, this message translates to:
  /// **'Excluded'**
  String get translationToolbarFilterExcluded;

  /// No description provided for @translationToolbarSearchTooltip.
  ///
  /// In en, this message translates to:
  /// **'Search (Ctrl+F / Cmd+F)'**
  String get translationToolbarSearchTooltip;

  /// No description provided for @translationToolbarPrevRetryTooltip.
  ///
  /// In en, this message translates to:
  /// **'Previous Retry Segment'**
  String get translationToolbarPrevRetryTooltip;

  /// No description provided for @translationToolbarNextRetryTooltip.
  ///
  /// In en, this message translates to:
  /// **'Next Retry Segment'**
  String get translationToolbarNextRetryTooltip;

  /// No description provided for @translationToolbarPreviewTooltip.
  ///
  /// In en, this message translates to:
  /// **'Preview'**
  String get translationToolbarPreviewTooltip;

  /// No description provided for @translationToolbarFormatSettingsTooltip.
  ///
  /// In en, this message translates to:
  /// **'Format Settings'**
  String get translationToolbarFormatSettingsTooltip;

  /// No description provided for @translationToolbarExportTooltip.
  ///
  /// In en, this message translates to:
  /// **'Export Document'**
  String get translationToolbarExportTooltip;

  /// No description provided for @translationToolbarPdfPreviewTooltip.
  ///
  /// In en, this message translates to:
  /// **'PDF Preview (Debug)'**
  String get translationToolbarPdfPreviewTooltip;

  /// No description provided for @translationToolbarCancelButton.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get translationToolbarCancelButton;

  /// No description provided for @translationToolbarExitFullscreenTooltip.
  ///
  /// In en, this message translates to:
  /// **'Exit Fullscreen'**
  String get translationToolbarExitFullscreenTooltip;

  /// No description provided for @translationToolbarEnterFullscreenTooltip.
  ///
  /// In en, this message translates to:
  /// **'Enter Fullscreen'**
  String get translationToolbarEnterFullscreenTooltip;

  /// No description provided for @translationToolbarDecreaseFontSize.
  ///
  /// In en, this message translates to:
  /// **'Decrease font size'**
  String get translationToolbarDecreaseFontSize;

  /// No description provided for @translationToolbarIncreaseFontSize.
  ///
  /// In en, this message translates to:
  /// **'Increase font size'**
  String get translationToolbarIncreaseFontSize;

  /// No description provided for @translationToolbarMergedView.
  ///
  /// In en, this message translates to:
  /// **'Reading Mode'**
  String get translationToolbarMergedView;

  /// No description provided for @translationToolbarSegmentView.
  ///
  /// In en, this message translates to:
  /// **'Labeled Mode'**
  String get translationToolbarSegmentView;

  /// No description provided for @translationToolbarUpload.
  ///
  /// In en, this message translates to:
  /// **'Upload'**
  String get translationToolbarUpload;

  /// No description provided for @translationToolbarUploading.
  ///
  /// In en, this message translates to:
  /// **'Uploading...'**
  String get translationToolbarUploading;

  /// No description provided for @translationToolbarFileUploaded.
  ///
  /// In en, this message translates to:
  /// **'File Uploaded'**
  String get translationToolbarFileUploaded;

  /// No description provided for @translationToolbarReextract.
  ///
  /// In en, this message translates to:
  /// **'Re-extract'**
  String get translationToolbarReextract;

  /// No description provided for @translationToolbarReextracting.
  ///
  /// In en, this message translates to:
  /// **'Re-extracting...'**
  String get translationToolbarReextracting;

  /// No description provided for @translationToolbarTokensCount.
  ///
  /// In en, this message translates to:
  /// **'{count} tokens'**
  String translationToolbarTokensCount(Object count);

  /// No description provided for @translationToolbarOpenGlossaryTab.
  ///
  /// In en, this message translates to:
  /// **'Open glossary tab'**
  String get translationToolbarOpenGlossaryTab;

  /// No description provided for @translationToolbarHintWaitExtract.
  ///
  /// In en, this message translates to:
  /// **'Please wait for Extract to complete'**
  String get translationToolbarHintWaitExtract;

  /// No description provided for @translationToolbarHintOperationInProgress.
  ///
  /// In en, this message translates to:
  /// **'An operation is in progress'**
  String get translationToolbarHintOperationInProgress;

  /// No description provided for @translationToolbarGlossary.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get translationToolbarGlossary;

  /// No description provided for @translationToolbarConvertHint.
  ///
  /// In en, this message translates to:
  /// **'Convert format, exclude all segments, translate, then export from the Convert tab'**
  String get translationToolbarConvertHint;

  /// No description provided for @translationToolbarConvert.
  ///
  /// In en, this message translates to:
  /// **'Convert'**
  String get translationToolbarConvert;

  /// No description provided for @translationToolbarHintSaveGlossaryFirst.
  ///
  /// In en, this message translates to:
  /// **'Please save the glossary first (click Apply)'**
  String get translationToolbarHintSaveGlossaryFirst;

  /// No description provided for @translationToolbarHintUpdatingExcluded.
  ///
  /// In en, this message translates to:
  /// **'Updating excluded segments...'**
  String get translationToolbarHintUpdatingExcluded;

  /// No description provided for @translationToolbarStartTranslation.
  ///
  /// In en, this message translates to:
  /// **'Start translation'**
  String get translationToolbarStartTranslation;

  /// No description provided for @translationToolbarTranslateAll.
  ///
  /// In en, this message translates to:
  /// **'Translate All'**
  String get translationToolbarTranslateAll;

  /// No description provided for @translationToolbarTranslating.
  ///
  /// In en, this message translates to:
  /// **'Translating...'**
  String get translationToolbarTranslating;

  /// No description provided for @translationToolbarRetryInProgress.
  ///
  /// In en, this message translates to:
  /// **'Retry in progress...'**
  String get translationToolbarRetryInProgress;

  /// No description provided for @translationToolbarRetryTooltip.
  ///
  /// In en, this message translates to:
  /// **'Retry all failed or marked segments. This will retranslate segments that failed during translation or were manually marked for retry, using the currently selected AI platform. Excluded and cleared segments will be skipped.'**
  String get translationToolbarRetryTooltip;

  /// No description provided for @translationToolbarRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get translationToolbarRetry;

  /// No description provided for @translationPersistQueueTooltip.
  ///
  /// In en, this message translates to:
  /// **'Write current exports to the server and update the task queue so downloads match your latest edits here.'**
  String get translationPersistQueueTooltip;

  /// No description provided for @translationPersistQueueButton.
  ///
  /// In en, this message translates to:
  /// **'Save update to queue'**
  String get translationPersistQueueButton;

  /// No description provided for @translationPersistQueueAlreadySyncedTooltip.
  ///
  /// In en, this message translates to:
  /// **'Already matches the queue snapshot. No save needed.'**
  String get translationPersistQueueAlreadySyncedTooltip;

  /// No description provided for @translationPersistQueueSuccess.
  ///
  /// In en, this message translates to:
  /// **'Latest exports saved for the task queue.'**
  String get translationPersistQueueSuccess;

  /// No description provided for @translationPersistQueueFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not save exports for the queue: {error}'**
  String translationPersistQueueFailed(Object error);

  /// No description provided for @translationCloseTranslateTabTitle.
  ///
  /// In en, this message translates to:
  /// **'Task queue may not reflect your latest result'**
  String get translationCloseTranslateTabTitle;

  /// No description provided for @translationCloseTranslateTabMessage.
  ///
  /// In en, this message translates to:
  /// **'Your edits here are not saved to the task queue snapshot yet. If you close without saving, files you download from the Task queue will not be the final version you see in this tab.\n\nYou can update the queue and then close, or close this tab without saving to the queue.'**
  String get translationCloseTranslateTabMessage;

  /// No description provided for @translationCloseTranslateTabStay.
  ///
  /// In en, this message translates to:
  /// **'Stay'**
  String get translationCloseTranslateTabStay;

  /// No description provided for @translationCloseTranslateTabClose.
  ///
  /// In en, this message translates to:
  /// **'Close without saving'**
  String get translationCloseTranslateTabClose;

  /// No description provided for @translationCloseTranslateTabSaveAndClose.
  ///
  /// In en, this message translates to:
  /// **'Save to queue and close'**
  String get translationCloseTranslateTabSaveAndClose;

  /// No description provided for @translationCloseTranslateTabKeepTitle.
  ///
  /// In en, this message translates to:
  /// **'Keep task in queue?'**
  String get translationCloseTranslateTabKeepTitle;

  /// No description provided for @translationCloseTranslateTabKeepMessage.
  ///
  /// In en, this message translates to:
  /// **'The task is completed. Keep it in the translation queue for later review and editing?'**
  String get translationCloseTranslateTabKeepMessage;

  /// No description provided for @translationCloseTranslateTabKeepInQueue.
  ///
  /// In en, this message translates to:
  /// **'Keep in queue'**
  String get translationCloseTranslateTabKeepInQueue;

  /// No description provided for @translationCloseTranslateTabDiscard.
  ///
  /// In en, this message translates to:
  /// **'Discard'**
  String get translationCloseTranslateTabDiscard;

  /// No description provided for @translationToolbarSwitchToFile.
  ///
  /// In en, this message translates to:
  /// **'Switch to File'**
  String get translationToolbarSwitchToFile;

  /// No description provided for @translationToolbarSwitchToText.
  ///
  /// In en, this message translates to:
  /// **'Enter Text'**
  String get translationToolbarSwitchToText;

  /// No description provided for @translationStatusCompleted.
  ///
  /// In en, this message translates to:
  /// **'Translation Completed'**
  String get translationStatusCompleted;

  /// No description provided for @translationStatusRetry.
  ///
  /// In en, this message translates to:
  /// **'Translation Retry'**
  String get translationStatusRetry;

  /// No description provided for @translationStatusFailed.
  ///
  /// In en, this message translates to:
  /// **'Translation Failed'**
  String get translationStatusFailed;

  /// No description provided for @translationStatusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Translation Cancelled'**
  String get translationStatusCancelled;

  /// No description provided for @translationStatusTranslating.
  ///
  /// In en, this message translates to:
  /// **'Translating'**
  String get translationStatusTranslating;

  /// No description provided for @translationStatusTranslatingFallback.
  ///
  /// In en, this message translates to:
  /// **'Translating...'**
  String get translationStatusTranslatingFallback;

  /// No description provided for @translationStatusReady.
  ///
  /// In en, this message translates to:
  /// **'Ready'**
  String get translationStatusReady;

  /// No description provided for @translationStatusTaskPending.
  ///
  /// In en, this message translates to:
  /// **'Task Pending'**
  String get translationStatusTaskPending;

  /// No description provided for @translationStatusProcessing.
  ///
  /// In en, this message translates to:
  /// **'Processing...'**
  String get translationStatusProcessing;

  /// No description provided for @translationStatsSuccessOnly.
  ///
  /// In en, this message translates to:
  /// **'Success: {success}/{total}'**
  String translationStatsSuccessOnly(Object success, Object total);

  /// No description provided for @translationStatsSuccessFailed.
  ///
  /// In en, this message translates to:
  /// **'Success: {success}/{total}, Failed: {fail}/{total}'**
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total);

  /// No description provided for @translationStatsTotal.
  ///
  /// In en, this message translates to:
  /// **'Total: {count} | '**
  String translationStatsTotal(Object count);

  /// No description provided for @translationStatsTranslated.
  ///
  /// In en, this message translates to:
  /// **'Translated: {count} | '**
  String translationStatsTranslated(Object count);

  /// No description provided for @translationStatsPending.
  ///
  /// In en, this message translates to:
  /// **'Pending: {count}'**
  String translationStatsPending(Object count);

  /// No description provided for @translationStatsExcluded.
  ///
  /// In en, this message translates to:
  /// **' | Excluded: {count}'**
  String translationStatsExcluded(Object count);

  /// No description provided for @translationStatsRetryCount.
  ///
  /// In en, this message translates to:
  /// **' | Retry: {count}'**
  String translationStatsRetryCount(Object count);

  /// No description provided for @translationStatsCleared.
  ///
  /// In en, this message translates to:
  /// **' | Cleared: {count}'**
  String translationStatsCleared(Object count);

  /// No description provided for @translationStatsImages.
  ///
  /// In en, this message translates to:
  /// **' | Images: {count}'**
  String translationStatsImages(Object count);

  /// No description provided for @translationStatsSegment.
  ///
  /// In en, this message translates to:
  /// **'Segment: {current} / {total}'**
  String translationStatsSegment(Object current, Object total);

  /// No description provided for @translationStatsDoubleClickToEdit.
  ///
  /// In en, this message translates to:
  /// **'Double click text to edit.'**
  String get translationStatsDoubleClickToEdit;

  /// No description provided for @translationStatsTranslatedLabel.
  ///
  /// In en, this message translates to:
  /// **'Translated'**
  String get translationStatsTranslatedLabel;

  /// No description provided for @translationStatsPendingLabel.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get translationStatsPendingLabel;

  /// No description provided for @translationStatsClearedLabel.
  ///
  /// In en, this message translates to:
  /// **'Cleared'**
  String get translationStatsClearedLabel;

  /// No description provided for @translationStatsImagesLabel.
  ///
  /// In en, this message translates to:
  /// **'Images'**
  String get translationStatsImagesLabel;

  /// No description provided for @translationStatsLoadingContent.
  ///
  /// In en, this message translates to:
  /// **'Loading content...'**
  String get translationStatsLoadingContent;

  /// No description provided for @translationStatsNoContentAvailable.
  ///
  /// In en, this message translates to:
  /// **'No content available.'**
  String get translationStatsNoContentAvailable;

  /// No description provided for @translationStatsNoSegmentsAvailable.
  ///
  /// In en, this message translates to:
  /// **'No segments available'**
  String get translationStatsNoSegmentsAvailable;

  /// No description provided for @translationStatsTokenIn.
  ///
  /// In en, this message translates to:
  /// **'In: {count}'**
  String translationStatsTokenIn(Object count);

  /// No description provided for @translationStatsTokenOut.
  ///
  /// In en, this message translates to:
  /// **'Out: {count}'**
  String translationStatsTokenOut(Object count);

  /// No description provided for @translationStatsTokenTotal.
  ///
  /// In en, this message translates to:
  /// **'({count})'**
  String translationStatsTokenTotal(Object count);

  /// No description provided for @translationLangArabic.
  ///
  /// In en, this message translates to:
  /// **'Arabic'**
  String get translationLangArabic;

  /// No description provided for @translationLangBengali.
  ///
  /// In en, this message translates to:
  /// **'Bengali'**
  String get translationLangBengali;

  /// No description provided for @translationLangCatalan.
  ///
  /// In en, this message translates to:
  /// **'Catalan'**
  String get translationLangCatalan;

  /// No description provided for @translationLangChinese.
  ///
  /// In en, this message translates to:
  /// **'Chinese'**
  String get translationLangChinese;

  /// No description provided for @translationLangChineseTraditional.
  ///
  /// In en, this message translates to:
  /// **'Chinese (Traditional)'**
  String get translationLangChineseTraditional;

  /// No description provided for @translationLangCzech.
  ///
  /// In en, this message translates to:
  /// **'Czech'**
  String get translationLangCzech;

  /// No description provided for @translationLangCroatian.
  ///
  /// In en, this message translates to:
  /// **'Croatian'**
  String get translationLangCroatian;

  /// No description provided for @translationLangDanish.
  ///
  /// In en, this message translates to:
  /// **'Danish'**
  String get translationLangDanish;

  /// No description provided for @translationLangDutch.
  ///
  /// In en, this message translates to:
  /// **'Dutch'**
  String get translationLangDutch;

  /// No description provided for @translationLangEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get translationLangEnglish;

  /// No description provided for @translationLangFilipino.
  ///
  /// In en, this message translates to:
  /// **'Filipino'**
  String get translationLangFilipino;

  /// No description provided for @translationLangFinnish.
  ///
  /// In en, this message translates to:
  /// **'Finnish'**
  String get translationLangFinnish;

  /// No description provided for @translationLangFrench.
  ///
  /// In en, this message translates to:
  /// **'French'**
  String get translationLangFrench;

  /// No description provided for @translationLangGerman.
  ///
  /// In en, this message translates to:
  /// **'German'**
  String get translationLangGerman;

  /// No description provided for @translationLangGreek.
  ///
  /// In en, this message translates to:
  /// **'Greek'**
  String get translationLangGreek;

  /// No description provided for @translationLangHebrew.
  ///
  /// In en, this message translates to:
  /// **'Hebrew'**
  String get translationLangHebrew;

  /// No description provided for @translationLangHindi.
  ///
  /// In en, this message translates to:
  /// **'Hindi'**
  String get translationLangHindi;

  /// No description provided for @translationLangItalian.
  ///
  /// In en, this message translates to:
  /// **'Italian'**
  String get translationLangItalian;

  /// No description provided for @translationLangJapanese.
  ///
  /// In en, this message translates to:
  /// **'Japanese'**
  String get translationLangJapanese;

  /// No description provided for @translationLangKorean.
  ///
  /// In en, this message translates to:
  /// **'Korean'**
  String get translationLangKorean;

  /// No description provided for @translationLangKhmer.
  ///
  /// In en, this message translates to:
  /// **'Khmer'**
  String get translationLangKhmer;

  /// No description provided for @translationLangLithuanian.
  ///
  /// In en, this message translates to:
  /// **'Lithuanian'**
  String get translationLangLithuanian;

  /// No description provided for @translationLangMacedonian.
  ///
  /// In en, this message translates to:
  /// **'Macedonian'**
  String get translationLangMacedonian;

  /// No description provided for @translationLangMalay.
  ///
  /// In en, this message translates to:
  /// **'Malay'**
  String get translationLangMalay;

  /// No description provided for @translationLangNorwegian.
  ///
  /// In en, this message translates to:
  /// **'Norwegian Bokmål'**
  String get translationLangNorwegian;

  /// No description provided for @translationLangPolish.
  ///
  /// In en, this message translates to:
  /// **'Polish'**
  String get translationLangPolish;

  /// No description provided for @translationLangPortuguese.
  ///
  /// In en, this message translates to:
  /// **'Portuguese'**
  String get translationLangPortuguese;

  /// No description provided for @translationLangRomanian.
  ///
  /// In en, this message translates to:
  /// **'Romanian'**
  String get translationLangRomanian;

  /// No description provided for @translationLangRussian.
  ///
  /// In en, this message translates to:
  /// **'Russian'**
  String get translationLangRussian;

  /// No description provided for @translationLangSlovenian.
  ///
  /// In en, this message translates to:
  /// **'Slovenian'**
  String get translationLangSlovenian;

  /// No description provided for @translationLangSpanish.
  ///
  /// In en, this message translates to:
  /// **'Spanish'**
  String get translationLangSpanish;

  /// No description provided for @translationLangSwedish.
  ///
  /// In en, this message translates to:
  /// **'Swedish'**
  String get translationLangSwedish;

  /// No description provided for @translationLangThai.
  ///
  /// In en, this message translates to:
  /// **'Thai'**
  String get translationLangThai;

  /// No description provided for @translationLangTurkish.
  ///
  /// In en, this message translates to:
  /// **'Turkish'**
  String get translationLangTurkish;

  /// No description provided for @translationLangUkrainian.
  ///
  /// In en, this message translates to:
  /// **'Ukrainian'**
  String get translationLangUkrainian;

  /// No description provided for @translationLangUrdu.
  ///
  /// In en, this message translates to:
  /// **'Urdu'**
  String get translationLangUrdu;

  /// No description provided for @translationLangVietnamese.
  ///
  /// In en, this message translates to:
  /// **'Vietnamese'**
  String get translationLangVietnamese;

  /// No description provided for @translationExportNoFormats.
  ///
  /// In en, this message translates to:
  /// **'No export formats available'**
  String get translationExportNoFormats;

  /// No description provided for @translationExportDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Export Document'**
  String get translationExportDialogTitle;

  /// No description provided for @translationExportDocumentType.
  ///
  /// In en, this message translates to:
  /// **'Document Type'**
  String get translationExportDocumentType;

  /// No description provided for @translationExportFormatOptionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Format Options (PDF only)'**
  String get translationExportFormatOptionsTitle;

  /// No description provided for @translationExportTableFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Table Format:'**
  String get translationExportTableFormatLabel;

  /// No description provided for @translationExportTableFormatImage.
  ///
  /// In en, this message translates to:
  /// **'Image'**
  String get translationExportTableFormatImage;

  /// No description provided for @translationExportTableFormatHtml.
  ///
  /// In en, this message translates to:
  /// **'HTML'**
  String get translationExportTableFormatHtml;

  /// No description provided for @translationExportEquationFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Equation Format:'**
  String get translationExportEquationFormatLabel;

  /// No description provided for @translationExportEquationFormatImage.
  ///
  /// In en, this message translates to:
  /// **'Image'**
  String get translationExportEquationFormatImage;

  /// No description provided for @translationExportEquationFormatLatex.
  ///
  /// In en, this message translates to:
  /// **'LaTeX'**
  String get translationExportEquationFormatLatex;

  /// No description provided for @translationExportChartFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Chart Format:'**
  String get translationExportChartFormatLabel;

  /// No description provided for @translationExportChartFormatImage.
  ///
  /// In en, this message translates to:
  /// **'Image'**
  String get translationExportChartFormatImage;

  /// No description provided for @translationExportChartFormatHtml.
  ///
  /// In en, this message translates to:
  /// **'HTML'**
  String get translationExportChartFormatHtml;

  /// No description provided for @translationImageCoverColorModeLabel.
  ///
  /// In en, this message translates to:
  /// **'Erase background:'**
  String get translationImageCoverColorModeLabel;

  /// No description provided for @translationImageCoverColorModeMax.
  ///
  /// In en, this message translates to:
  /// **'Brightest pixel (max)'**
  String get translationImageCoverColorModeMax;

  /// No description provided for @translationImageCoverColorModeMin.
  ///
  /// In en, this message translates to:
  /// **'Darkest pixel (min)'**
  String get translationImageCoverColorModeMin;

  /// No description provided for @translationImageCoverColorModeAvg.
  ///
  /// In en, this message translates to:
  /// **'Average pixel (mean)'**
  String get translationImageCoverColorModeAvg;

  /// No description provided for @translationExportBilingualExport.
  ///
  /// In en, this message translates to:
  /// **'Bilingual Export'**
  String get translationExportBilingualExport;

  /// No description provided for @translationExportBilingualOrderTargetAfter.
  ///
  /// In en, this message translates to:
  /// **'Source First'**
  String get translationExportBilingualOrderTargetAfter;

  /// No description provided for @translationExportBilingualOrderTargetAfterSub.
  ///
  /// In en, this message translates to:
  /// **'Source first, target after'**
  String get translationExportBilingualOrderTargetAfterSub;

  /// No description provided for @translationExportBilingualOrderTargetBefore.
  ///
  /// In en, this message translates to:
  /// **'Target Before Source'**
  String get translationExportBilingualOrderTargetBefore;

  /// No description provided for @translationExportBilingualOrderTargetBeforeSub.
  ///
  /// In en, this message translates to:
  /// **'Target first, source after'**
  String get translationExportBilingualOrderTargetBeforeSub;

  /// No description provided for @translationExportSourceTextItalic.
  ///
  /// In en, this message translates to:
  /// **'Source text italic'**
  String get translationExportSourceTextItalic;

  /// No description provided for @translationExportSourceTextColor.
  ///
  /// In en, this message translates to:
  /// **'Source text color:'**
  String get translationExportSourceTextColor;

  /// No description provided for @translationExportTargetTextItalic.
  ///
  /// In en, this message translates to:
  /// **'Target text italic'**
  String get translationExportTargetTextItalic;

  /// No description provided for @translationExportTargetTextColor.
  ///
  /// In en, this message translates to:
  /// **'Target text color:'**
  String get translationExportTargetTextColor;

  /// No description provided for @translationExportSourceFontSizeDelta.
  ///
  /// In en, this message translates to:
  /// **'Source font size delta:'**
  String get translationExportSourceFontSizeDelta;

  /// No description provided for @translationExportTargetFontSizeDelta.
  ///
  /// In en, this message translates to:
  /// **'Target font size delta:'**
  String get translationExportTargetFontSizeDelta;

  /// No description provided for @translationExportColorDefault.
  ///
  /// In en, this message translates to:
  /// **'Default'**
  String get translationExportColorDefault;

  /// No description provided for @translationExportColorGray.
  ///
  /// In en, this message translates to:
  /// **'Gray'**
  String get translationExportColorGray;

  /// No description provided for @translationExportColorBlue.
  ///
  /// In en, this message translates to:
  /// **'Blue'**
  String get translationExportColorBlue;

  /// No description provided for @translationExportColorRed.
  ///
  /// In en, this message translates to:
  /// **'Red'**
  String get translationExportColorRed;

  /// No description provided for @translationExportColorGreen.
  ///
  /// In en, this message translates to:
  /// **'Green'**
  String get translationExportColorGreen;

  /// No description provided for @translationExportColorOrange.
  ///
  /// In en, this message translates to:
  /// **'Orange'**
  String get translationExportColorOrange;

  /// No description provided for @translationExportColorBlack.
  ///
  /// In en, this message translates to:
  /// **'Black'**
  String get translationExportColorBlack;

  /// No description provided for @translationExportDownloadButton.
  ///
  /// In en, this message translates to:
  /// **'Download'**
  String get translationExportDownloadButton;

  /// No description provided for @translationExportMdEmbeddedImages.
  ///
  /// In en, this message translates to:
  /// **'MD (Embedded Images)'**
  String get translationExportMdEmbeddedImages;

  /// No description provided for @translationExportMdWithImagesFolder.
  ///
  /// In en, this message translates to:
  /// **'MD (With Images Folder)'**
  String get translationExportMdWithImagesFolder;

  /// No description provided for @translationExportPdfPreserveLayout.
  ///
  /// In en, this message translates to:
  /// **'Original Layout PDF'**
  String get translationExportPdfPreserveLayout;

  /// No description provided for @translationExportPdfPreserveLayoutDesc.
  ///
  /// In en, this message translates to:
  /// **'Overlay translation on the original PDF layout'**
  String get translationExportPdfPreserveLayoutDesc;

  /// No description provided for @translationExportImageOriginalLayout.
  ///
  /// In en, this message translates to:
  /// **'Original layout image'**
  String get translationExportImageOriginalLayout;

  /// No description provided for @translationExportImageOriginalLayoutDesc.
  ///
  /// In en, this message translates to:
  /// **'Erase OCR text and write translation on the source image'**
  String get translationExportImageOriginalLayoutDesc;

  /// No description provided for @translationExportPdfReflow.
  ///
  /// In en, this message translates to:
  /// **'Reflow PDF'**
  String get translationExportPdfReflow;

  /// No description provided for @translationExportPdfReflowDesc.
  ///
  /// In en, this message translates to:
  /// **'Re-typeset from translation Markdown; layout may differ from the source'**
  String get translationExportPdfReflowDesc;

  /// No description provided for @translationPreviewDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Preview Settings'**
  String get translationPreviewDialogTitle;

  /// No description provided for @translationPreviewStart.
  ///
  /// In en, this message translates to:
  /// **'Start Preview'**
  String get translationPreviewStart;

  /// No description provided for @translationPreviewModeSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Translation preview'**
  String get translationPreviewModeSectionTitle;

  /// No description provided for @translationPreviewModeHtml.
  ///
  /// In en, this message translates to:
  /// **'HTML / Markdown'**
  String get translationPreviewModeHtml;

  /// No description provided for @translationPreviewModeHtmlDesc.
  ///
  /// In en, this message translates to:
  /// **'View rendered translation in the browser (default)'**
  String get translationPreviewModeHtmlDesc;

  /// No description provided for @translationPreviewFullDocumentCompare.
  ///
  /// In en, this message translates to:
  /// **'Full document comparison'**
  String get translationPreviewFullDocumentCompare;

  /// No description provided for @translationPreviewFullDocumentCompareDesc.
  ///
  /// In en, this message translates to:
  /// **'View source and translation side by side (export format; works with any preview mode above)'**
  String get translationPreviewFullDocumentCompareDesc;

  /// No description provided for @translationPreviewSyncScroll.
  ///
  /// In en, this message translates to:
  /// **'Link scrollbars'**
  String get translationPreviewSyncScroll;

  /// No description provided for @translationPreviewSyncScrollDesc.
  ///
  /// In en, this message translates to:
  /// **'When enabled, link PDF compare panes with a shared scroll bar (PDF compare only)'**
  String get translationPreviewSyncScrollDesc;

  /// No description provided for @translationPreviewRevisionSyncScrollDesc.
  ///
  /// In en, this message translates to:
  /// **'When enabled, hide separate scroll bars on source and translation previews; show one shared scroll bar between them with linked scrolling'**
  String get translationPreviewRevisionSyncScrollDesc;

  /// No description provided for @translationPreviewPanelSource.
  ///
  /// In en, this message translates to:
  /// **'Source'**
  String get translationPreviewPanelSource;

  /// No description provided for @translationPreviewPanelTarget.
  ///
  /// In en, this message translates to:
  /// **'Translation'**
  String get translationPreviewPanelTarget;

  /// No description provided for @translationPreviewNoExtraOptions.
  ///
  /// In en, this message translates to:
  /// **'No extra options for this preview mode'**
  String get translationPreviewNoExtraOptions;

  /// No description provided for @translationPreviewReopenSettings.
  ///
  /// In en, this message translates to:
  /// **'Preview settings'**
  String get translationPreviewReopenSettings;

  /// No description provided for @translationPreviewZoomIn.
  ///
  /// In en, this message translates to:
  /// **'Zoom in'**
  String get translationPreviewZoomIn;

  /// No description provided for @translationPreviewZoomOut.
  ///
  /// In en, this message translates to:
  /// **'Zoom out'**
  String get translationPreviewZoomOut;

  /// No description provided for @translationPreviewZoomReset.
  ///
  /// In en, this message translates to:
  /// **'Reset zoom'**
  String get translationPreviewZoomReset;

  /// No description provided for @translationLeftPanelExpandTooltip.
  ///
  /// In en, this message translates to:
  /// **'Expand left panel'**
  String get translationLeftPanelExpandTooltip;

  /// No description provided for @translationLeftPanelCollapseTooltip.
  ///
  /// In en, this message translates to:
  /// **'Collapse left panel'**
  String get translationLeftPanelCollapseTooltip;

  /// No description provided for @translationSnackGlossarySaved.
  ///
  /// In en, this message translates to:
  /// **'Glossary saved'**
  String get translationSnackGlossarySaved;

  /// No description provided for @translationSnackTranslationCancelled.
  ///
  /// In en, this message translates to:
  /// **'Translation cancelled'**
  String get translationSnackTranslationCancelled;

  /// No description provided for @translationSnackNoLlmpSelected.
  ///
  /// In en, this message translates to:
  /// **'No LLM Platform selected'**
  String get translationSnackNoLlmpSelected;

  /// No description provided for @translationSnackTextEmpty.
  ///
  /// In en, this message translates to:
  /// **'Text input is empty.'**
  String get translationSnackTextEmpty;

  /// No description provided for @translationSnackTextConverted.
  ///
  /// In en, this message translates to:
  /// **'Text converted to file format'**
  String get translationSnackTextConverted;

  /// No description provided for @translationSnackSourceResplitCompleted.
  ///
  /// In en, this message translates to:
  /// **'Source re-split completed'**
  String get translationSnackSourceResplitCompleted;

  /// No description provided for @translationSnackPleaseSelectFileOrText.
  ///
  /// In en, this message translates to:
  /// **'Please select a file or enter text first'**
  String get translationSnackPleaseSelectFileOrText;

  /// No description provided for @translationSnackPleaseSelectFileOrTextWithDot.
  ///
  /// In en, this message translates to:
  /// **'Please select a file or enter text first.'**
  String get translationSnackPleaseSelectFileOrTextWithDot;

  /// No description provided for @translationSnackPleaseSelectFile.
  ///
  /// In en, this message translates to:
  /// **'Please select a file first'**
  String get translationSnackPleaseSelectFile;

  /// No description provided for @translationSnackPleaseSelectDocumentFirst.
  ///
  /// In en, this message translates to:
  /// **'Please select a document first.'**
  String get translationSnackPleaseSelectDocumentFirst;

  /// No description provided for @translationSnackGlossaryGenerated.
  ///
  /// In en, this message translates to:
  /// **'Glossary generated successfully!'**
  String get translationSnackGlossaryGenerated;

  /// No description provided for @translationSnackGlossaryGenerationCancelled.
  ///
  /// In en, this message translates to:
  /// **'Glossary generation cancelled'**
  String get translationSnackGlossaryGenerationCancelled;

  /// No description provided for @translationSnackGlossaryAppliedToTask.
  ///
  /// In en, this message translates to:
  /// **'Glossary applied to translation task'**
  String get translationSnackGlossaryAppliedToTask;

  /// No description provided for @translationSnackPreviousTranslationCancelled.
  ///
  /// In en, this message translates to:
  /// **'Previous translation cancelled'**
  String get translationSnackPreviousTranslationCancelled;

  /// No description provided for @translationSnackGlossarySavedAndApplied.
  ///
  /// In en, this message translates to:
  /// **'Glossary saved and applied'**
  String get translationSnackGlossarySavedAndApplied;

  /// No description provided for @translationDialogMixedLangTitle.
  ///
  /// In en, this message translates to:
  /// **'Mixed Language Detected'**
  String get translationDialogMixedLangTitle;

  /// No description provided for @translationDialogMixedLangContent.
  ///
  /// In en, this message translates to:
  /// **'The document contains multiple languages:\n{distribution}'**
  String translationDialogMixedLangContent(Object distribution);

  /// No description provided for @translationDialogMixedLangPromptTitle.
  ///
  /// In en, this message translates to:
  /// **'To improve translation quality, you can add prompt instructions:'**
  String get translationDialogMixedLangPromptTitle;

  /// No description provided for @translationDialogMixedLangOption1Title.
  ///
  /// In en, this message translates to:
  /// **'Only translate text in source language'**
  String get translationDialogMixedLangOption1Title;

  /// No description provided for @translationDialogMixedLangOption1Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Only translate text in {languageName} language'**
  String translationDialogMixedLangOption1Subtitle(Object languageName);

  /// No description provided for @translationDialogMixedLangOption2Title.
  ///
  /// In en, this message translates to:
  /// **'Keep code and technical terms unchanged'**
  String get translationDialogMixedLangOption2Title;

  /// No description provided for @translationDialogMixedLangOption2Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Keep code blocks, technical terms, function names, and text in other languages unchanged'**
  String get translationDialogMixedLangOption2Subtitle;

  /// No description provided for @translationDialogMixedLangCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get translationDialogMixedLangCancel;

  /// No description provided for @translationDialogMixedLangSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get translationDialogMixedLangSkip;

  /// No description provided for @translationDialogMixedLangApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get translationDialogMixedLangApply;

  /// No description provided for @translationSnackExportStarted.
  ///
  /// In en, this message translates to:
  /// **'Export task has been started, please wait.'**
  String get translationSnackExportStarted;

  /// No description provided for @translationSnackPromptUpdated.
  ///
  /// In en, this message translates to:
  /// **'Prompt instructions updated'**
  String get translationSnackPromptUpdated;

  /// No description provided for @translationSnackFailedToCancel.
  ///
  /// In en, this message translates to:
  /// **'Failed to cancel: {error}'**
  String translationSnackFailedToCancel(Object error);

  /// No description provided for @translationSnackFailedConvertTextFormat.
  ///
  /// In en, this message translates to:
  /// **'Failed to convert text format: {error}'**
  String translationSnackFailedConvertTextFormat(Object error);

  /// No description provided for @translationSnackFailedConvertText.
  ///
  /// In en, this message translates to:
  /// **'Failed to convert text: {error}'**
  String translationSnackFailedConvertText(Object error);

  /// No description provided for @translationSnackFailedResplit.
  ///
  /// In en, this message translates to:
  /// **'Failed to re-split: {error}'**
  String translationSnackFailedResplit(Object error);

  /// No description provided for @translationSnackRequestFailed.
  ///
  /// In en, this message translates to:
  /// **'Request failed'**
  String get translationSnackRequestFailed;

  /// No description provided for @translationSnackFileImportFailed.
  ///
  /// In en, this message translates to:
  /// **'File import failed: {error}'**
  String translationSnackFileImportFailed(Object error);

  /// No description provided for @translationSnackTaskStatus.
  ///
  /// In en, this message translates to:
  /// **'Task status: {status}'**
  String translationSnackTaskStatus(Object status);

  /// No description provided for @translationSnackFileDownloaded.
  ///
  /// In en, this message translates to:
  /// **'File downloaded: {filename}'**
  String translationSnackFileDownloaded(Object filename);

  /// No description provided for @translationSnackFileSaved.
  ///
  /// In en, this message translates to:
  /// **'File saved: {filename}'**
  String translationSnackFileSaved(Object filename);

  /// No description provided for @translationSnackFailedDownload.
  ///
  /// In en, this message translates to:
  /// **'Failed to download {fileType}: {error}'**
  String translationSnackFailedDownload(Object error, Object fileType);

  /// No description provided for @translationSnackFailedOpenDownload.
  ///
  /// In en, this message translates to:
  /// **'Failed to open download: {url}'**
  String translationSnackFailedOpenDownload(Object url);

  /// No description provided for @translationDialogSwitchToFileTitle.
  ///
  /// In en, this message translates to:
  /// **'Switch to File Mode'**
  String get translationDialogSwitchToFileTitle;

  /// No description provided for @translationDialogSwitchToFileBody.
  ///
  /// In en, this message translates to:
  /// **'Switching to file mode will clear your current text input. Do you want to continue?'**
  String get translationDialogSwitchToFileBody;

  /// No description provided for @translationDialogSwitchToTextTitle.
  ///
  /// In en, this message translates to:
  /// **'Switch to Text Mode'**
  String get translationDialogSwitchToTextTitle;

  /// No description provided for @translationDialogSwitchToTextBody.
  ///
  /// In en, this message translates to:
  /// **'Switching to text mode will clear the current file selection. Do you want to continue?'**
  String get translationDialogSwitchToTextBody;

  /// No description provided for @translationSnackAllSegmentsExcludedSkipped.
  ///
  /// In en, this message translates to:
  /// **'All segments are excluded. Translation will be skipped. You can export the file for format conversion.'**
  String get translationSnackAllSegmentsExcludedSkipped;

  /// No description provided for @translationDialogCancelButton.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get translationDialogCancelButton;

  /// No description provided for @translationDialogContinueButton.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get translationDialogContinueButton;

  /// No description provided for @translationNoLlmAvailableTitle.
  ///
  /// In en, this message translates to:
  /// **'No LLM platform available'**
  String get translationNoLlmAvailableTitle;

  /// No description provided for @translationNoLlmAvailableMessage.
  ///
  /// In en, this message translates to:
  /// **'No configured and available LLM platform. To translate, please configure an LLM API Key in Settings first; if you only need format conversion, you can continue.'**
  String get translationNoLlmAvailableMessage;

  /// No description provided for @translationNoLlmConfigureButton.
  ///
  /// In en, this message translates to:
  /// **'Configure LLM'**
  String get translationNoLlmConfigureButton;

  /// No description provided for @translationNoLlmContinueFormatOnlyButton.
  ///
  /// In en, this message translates to:
  /// **'Format conversion only'**
  String get translationNoLlmContinueFormatOnlyButton;

  /// No description provided for @languageMatchWarningTitle.
  ///
  /// In en, this message translates to:
  /// **'Language Match Warning'**
  String get languageMatchWarningTitle;

  /// No description provided for @languageMatchWarningGlossaryBody.
  ///
  /// In en, this message translates to:
  /// **'The detected source language ({detectedName}) is the same as the target language ({targetName}). Are you sure you want to continue with glossary generation?'**
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName);

  /// No description provided for @languageMatchWarningTranslationBody.
  ///
  /// In en, this message translates to:
  /// **'The detected source language ({detectedName}) is the same as the target language ({targetName}). Are you sure you want to continue with translation?'**
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName);

  /// No description provided for @translationDialogCancelTaskTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel Current Task'**
  String get translationDialogCancelTaskTitle;

  /// No description provided for @translationDialogCancelTaskBody.
  ///
  /// In en, this message translates to:
  /// **'This will cancel the current extraction/translation task and clear the selected file. Do you want to continue?'**
  String get translationDialogCancelTaskBody;

  /// No description provided for @translationDialogCancelTaskNo.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get translationDialogCancelTaskNo;

  /// No description provided for @translationDialogCancelTaskYesCancel.
  ///
  /// In en, this message translates to:
  /// **'Yes, Cancel'**
  String get translationDialogCancelTaskYesCancel;

  /// No description provided for @translationQuickSettingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Quick Settings'**
  String get translationQuickSettingsTitle;

  /// No description provided for @quickSettingsTargetLanguage.
  ///
  /// In en, this message translates to:
  /// **'Target Language'**
  String get quickSettingsTargetLanguage;

  /// No description provided for @quickSettingsSourceLanguage.
  ///
  /// In en, this message translates to:
  /// **'Source language (MinerU OCR)'**
  String get quickSettingsSourceLanguage;

  /// No description provided for @quickSettingsLanguageSwitchDisabled.
  ///
  /// In en, this message translates to:
  /// **'Language switching is disabled during translation. Please switch to Extract tab to change target language.'**
  String get quickSettingsLanguageSwitchDisabled;

  /// No description provided for @quickSettingsParsingPlatform.
  ///
  /// In en, this message translates to:
  /// **'Parsing Platform'**
  String get quickSettingsParsingPlatform;

  /// No description provided for @quickSettingsTestMineru.
  ///
  /// In en, this message translates to:
  /// **'Test MinerU connection'**
  String get quickSettingsTestMineru;

  /// No description provided for @quickSettingsNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Not configured'**
  String get quickSettingsNotConfigured;

  /// No description provided for @quickSettingsApiOk.
  ///
  /// In en, this message translates to:
  /// **'API OK'**
  String get quickSettingsApiOk;

  /// No description provided for @quickSettingsApiUnavailable.
  ///
  /// In en, this message translates to:
  /// **'API unavailable'**
  String get quickSettingsApiUnavailable;

  /// No description provided for @quickSettingsNotTestedYet.
  ///
  /// In en, this message translates to:
  /// **'Not tested yet'**
  String get quickSettingsNotTestedYet;

  /// No description provided for @quickSettingsConnectionSuccessful.
  ///
  /// In en, this message translates to:
  /// **'Connection successful'**
  String get quickSettingsConnectionSuccessful;

  /// No description provided for @quickSettingsMineruConnectionFailed.
  ///
  /// In en, this message translates to:
  /// **'MinerU connection failed'**
  String get quickSettingsMineruConnectionFailed;

  /// No description provided for @quickSettingsOpenMineruSettings.
  ///
  /// In en, this message translates to:
  /// **'Open MinerU settings'**
  String get quickSettingsOpenMineruSettings;

  /// No description provided for @quickSettingsTableOcr.
  ///
  /// In en, this message translates to:
  /// **'Table OCR'**
  String get quickSettingsTableOcr;

  /// No description provided for @quickSettingsTableOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Recognize tables during document parsing'**
  String get quickSettingsTableOcrSubtitle;

  /// No description provided for @quickSettingsFormulaOcr.
  ///
  /// In en, this message translates to:
  /// **'Formula OCR'**
  String get quickSettingsFormulaOcr;

  /// No description provided for @quickSettingsFormulaOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Recognize formulas during document parsing'**
  String get quickSettingsFormulaOcrSubtitle;

  /// No description provided for @quickSettingsPaddleUseDocOrientationClassify.
  ///
  /// In en, this message translates to:
  /// **'Auto-Detect Orientation'**
  String get quickSettingsPaddleUseDocOrientationClassify;

  /// No description provided for @quickSettingsPaddleUseDocOrientationClassifySubtitle.
  ///
  /// In en, this message translates to:
  /// **'Automatically detect and correct document orientation before OCR'**
  String get quickSettingsPaddleUseDocOrientationClassifySubtitle;

  /// No description provided for @quickSettingsPaddleRestructurePages.
  ///
  /// In en, this message translates to:
  /// **'Restructure Pages'**
  String get quickSettingsPaddleRestructurePages;

  /// No description provided for @quickSettingsPaddleRestructurePagesSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Restructure page layout for better reading order'**
  String get quickSettingsPaddleRestructurePagesSubtitle;

  /// No description provided for @quickSettingsMineruLabel.
  ///
  /// In en, this message translates to:
  /// **'MinerU (mineru)'**
  String get quickSettingsMineruLabel;

  /// No description provided for @quickSettingsLlmPlatform.
  ///
  /// In en, this message translates to:
  /// **'LLM Platform'**
  String get quickSettingsLlmPlatform;

  /// No description provided for @quickSettingsTestLlmPlatform.
  ///
  /// In en, this message translates to:
  /// **'Test current LLM platform'**
  String get quickSettingsTestLlmPlatform;

  /// No description provided for @quickSettingsTestFailed.
  ///
  /// In en, this message translates to:
  /// **'Test failed'**
  String get quickSettingsTestFailed;

  /// No description provided for @quickSettingsOpenAiPlatformsSettings.
  ///
  /// In en, this message translates to:
  /// **'Open AI Platforms settings'**
  String get quickSettingsOpenAiPlatformsSettings;

  /// No description provided for @quickSettingsTemperature.
  ///
  /// In en, this message translates to:
  /// **'Temperature'**
  String get quickSettingsTemperature;

  /// No description provided for @quickSettingsTemperatureHint.
  ///
  /// In en, this message translates to:
  /// **'Controls randomness: Lower = more focused, Higher = more creative'**
  String get quickSettingsTemperatureHint;

  /// No description provided for @quickSettingsQtTsOptions.
  ///
  /// In en, this message translates to:
  /// **'Qt .ts Translation Options'**
  String get quickSettingsQtTsOptions;

  /// No description provided for @quickSettingsQtTsSkipExisting.
  ///
  /// In en, this message translates to:
  /// **'Skip existing translations'**
  String get quickSettingsQtTsSkipExisting;

  /// No description provided for @quickSettingsQtTsSkipExistingSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Skip messages that already have translations'**
  String get quickSettingsQtTsSkipExistingSubtitle;

  /// No description provided for @quickSettingsQtTsTranslateUnfinished.
  ///
  /// In en, this message translates to:
  /// **'Translate unfinished entries'**
  String get quickSettingsQtTsTranslateUnfinished;

  /// No description provided for @quickSettingsQtTsTranslateUnfinishedSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Translate messages marked as unfinished (type=\"unfinished\")'**
  String get quickSettingsQtTsTranslateUnfinishedSubtitle;

  /// No description provided for @quickSettingsQtTsTranslateVanished.
  ///
  /// In en, this message translates to:
  /// **'Translate vanished entries'**
  String get quickSettingsQtTsTranslateVanished;

  /// No description provided for @quickSettingsQtTsTranslateVanishedSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Translate messages marked as vanished (type=\"vanished\")'**
  String get quickSettingsQtTsTranslateVanishedSubtitle;

  /// No description provided for @quickSettingsQtTsTranslateObsolete.
  ///
  /// In en, this message translates to:
  /// **'Translate obsolete entries'**
  String get quickSettingsQtTsTranslateObsolete;

  /// No description provided for @quickSettingsQtTsTranslateObsoleteSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Translate messages marked as obsolete (type=\"obsolete\")'**
  String get quickSettingsQtTsTranslateObsoleteSubtitle;

  /// No description provided for @quickSettingsPrompt.
  ///
  /// In en, this message translates to:
  /// **'Prompt'**
  String get quickSettingsPrompt;

  /// No description provided for @quickSettingsPromptMode.
  ///
  /// In en, this message translates to:
  /// **'Prompt Mode'**
  String get quickSettingsPromptMode;

  /// No description provided for @quickSettingsPromptModeOff.
  ///
  /// In en, this message translates to:
  /// **'Off (No prompt)'**
  String get quickSettingsPromptModeOff;

  /// No description provided for @quickSettingsPromptModeSimple.
  ///
  /// In en, this message translates to:
  /// **'Simple (Style only)'**
  String get quickSettingsPromptModeSimple;

  /// No description provided for @quickSettingsPromptModeAdvanced.
  ///
  /// In en, this message translates to:
  /// **'Advanced (Style + Note)'**
  String get quickSettingsPromptModeAdvanced;

  /// No description provided for @quickSettingsStyle.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get quickSettingsStyle;

  /// No description provided for @quickSettingsStyleLiteral.
  ///
  /// In en, this message translates to:
  /// **'Literal'**
  String get quickSettingsStyleLiteral;

  /// No description provided for @quickSettingsStyleFluent.
  ///
  /// In en, this message translates to:
  /// **'Fluent'**
  String get quickSettingsStyleFluent;

  /// No description provided for @quickSettingsStyleAcademic.
  ///
  /// In en, this message translates to:
  /// **'Academic'**
  String get quickSettingsStyleAcademic;

  /// No description provided for @quickSettingsStyleBusiness.
  ///
  /// In en, this message translates to:
  /// **'Business'**
  String get quickSettingsStyleBusiness;

  /// No description provided for @quickSettingsStyleTechnical.
  ///
  /// In en, this message translates to:
  /// **'Technical'**
  String get quickSettingsStyleTechnical;

  /// No description provided for @quickSettingsStyleNone.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get quickSettingsStyleNone;

  /// No description provided for @quickSettingsTaskNoteLabel.
  ///
  /// In en, this message translates to:
  /// **'Task note (short instruction)'**
  String get quickSettingsTaskNoteLabel;

  /// No description provided for @quickSettingsTaskNoteHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. Keep formulas unmodified; annotate proper nouns'**
  String get quickSettingsTaskNoteHint;

  /// No description provided for @quickSettingsAdRegionF.
  ///
  /// In en, this message translates to:
  /// **'Region F: Bottom of Quick Settings\n(Medium Rectangle 300×250)'**
  String get quickSettingsAdRegionF;

  /// No description provided for @quickSettingsPlatformMessage.
  ///
  /// In en, this message translates to:
  /// **'{label}: {message}'**
  String quickSettingsPlatformMessage(Object label, Object message);

  /// No description provided for @quickSettingsPlatformTestFailed.
  ///
  /// In en, this message translates to:
  /// **'{label}: Test failed — {error}'**
  String quickSettingsPlatformTestFailed(Object error, Object label);

  /// No description provided for @homeTagline.
  ///
  /// In en, this message translates to:
  /// **'AI Based, Immersion\nPrivate, Secure(Developing)\nTeam Shared, Customizable\n'**
  String get homeTagline;

  /// No description provided for @homeIntro.
  ///
  /// In en, this message translates to:
  /// **'Upload documents and translate them into multiple languages with AI-powered accuracy.\n'**
  String get homeIntro;

  /// No description provided for @homeHowItWorks.
  ///
  /// In en, this message translates to:
  /// **'How it works\nTranslation: Import -> Parse Document -> Glossary -> Translate -> Export\nFile format conversion: Import -> Parse Document -> Convert -> Export\nURL Fetch: Enter URL -> Fetch Page -> Parse Content -> Extract Text -> Translate/Export'**
  String get homeHowItWorks;

  /// No description provided for @homeSnackDonorExpired.
  ///
  /// In en, this message translates to:
  /// **'Your registration code has expired. Please re-register to continue Pro benefits.'**
  String get homeSnackDonorExpired;

  /// No description provided for @commonCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get commonCancel;

  /// No description provided for @commonOk.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get commonOk;

  /// No description provided for @homeAuthErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'Authentication Error'**
  String get homeAuthErrorTitle;

  /// No description provided for @homeAuthRetryLogin.
  ///
  /// In en, this message translates to:
  /// **'Retry Login'**
  String get homeAuthRetryLogin;

  /// No description provided for @homeAiPlatformsAvailable.
  ///
  /// In en, this message translates to:
  /// **'Available AI Platforms: {platforms}'**
  String homeAiPlatformsAvailable(Object platforms);

  /// No description provided for @homeAiPlatformsConfigureNotice.
  ///
  /// In en, this message translates to:
  /// **'Please configure your AI platforms in the settings panel before using the app.'**
  String get homeAiPlatformsConfigureNotice;

  /// No description provided for @homeBackendStatusStarting.
  ///
  /// In en, this message translates to:
  /// **'Backend is starting up...'**
  String get homeBackendStatusStarting;

  /// No description provided for @homeBackendStatusConnecting.
  ///
  /// In en, this message translates to:
  /// **'Connecting to backend...'**
  String get homeBackendStatusConnecting;

  /// No description provided for @homeBackendStatusConnected.
  ///
  /// In en, this message translates to:
  /// **'Backend is connected'**
  String get homeBackendStatusConnected;

  /// No description provided for @homeBackendStatusDisconnected.
  ///
  /// In en, this message translates to:
  /// **'Backend is disconnected. Please retry.'**
  String get homeBackendStatusDisconnected;

  /// No description provided for @homeBackendStatusUnknown.
  ///
  /// In en, this message translates to:
  /// **'Connecting to backend...'**
  String get homeBackendStatusUnknown;

  /// No description provided for @homeBackendRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get homeBackendRetry;

  /// No description provided for @homeNewTask.
  ///
  /// In en, this message translates to:
  /// **'New task'**
  String get homeNewTask;

  /// No description provided for @homeNewTaskImmersiveTooltip.
  ///
  /// In en, this message translates to:
  /// **'Compare source and translation side by side in the UI'**
  String get homeNewTaskImmersiveTooltip;

  /// No description provided for @homeNewTaskQueuedTooltip.
  ///
  /// In en, this message translates to:
  /// **'Batch import files and run the full pipeline in order'**
  String get homeNewTaskQueuedTooltip;

  /// No description provided for @homeNavTranslate.
  ///
  /// In en, this message translates to:
  /// **'Immersive task'**
  String get homeNavTranslate;

  /// No description provided for @homeNavTranslationQueue.
  ///
  /// In en, this message translates to:
  /// **'Tasks'**
  String get homeNavTranslationQueue;

  /// No description provided for @homeNavAnonymize.
  ///
  /// In en, this message translates to:
  /// **'Anonymize'**
  String get homeNavAnonymize;

  /// No description provided for @homeNavSettings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get homeNavSettings;

  /// No description provided for @homeNavDonateHelp.
  ///
  /// In en, this message translates to:
  /// **'Help'**
  String get homeNavDonateHelp;

  /// No description provided for @homeNavDonate.
  ///
  /// In en, this message translates to:
  /// **'Donate'**
  String get homeNavDonate;

  /// No description provided for @homeNavHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get homeNavHome;

  /// No description provided for @homeNavBatchUpload.
  ///
  /// In en, this message translates to:
  /// **'Batch upload'**
  String get homeNavBatchUpload;

  /// No description provided for @homeNavTooltipNewTask.
  ///
  /// In en, this message translates to:
  /// **'Start a new translation — immersive side-by-side, or queued batch processing'**
  String get homeNavTooltipNewTask;

  /// No description provided for @homeNavTooltipTasks.
  ///
  /// In en, this message translates to:
  /// **'View and manage all translation tasks, download completed results'**
  String get homeNavTooltipTasks;

  /// No description provided for @homeNavTooltipAnonymize.
  ///
  /// In en, this message translates to:
  /// **'Anonymize document content to protect sensitive information'**
  String get homeNavTooltipAnonymize;

  /// No description provided for @homeNavTooltipSettings.
  ///
  /// In en, this message translates to:
  /// **'Configure language, theme, notifications and more'**
  String get homeNavTooltipSettings;

  /// No description provided for @homeNavTooltipSetupWizard.
  ///
  /// In en, this message translates to:
  /// **'Guided setup wizard to configure your translation environment'**
  String get homeNavTooltipSetupWizard;

  /// No description provided for @homeNavTooltipHelp.
  ///
  /// In en, this message translates to:
  /// **'Get help and technical support'**
  String get homeNavTooltipHelp;

  /// No description provided for @homeNavTooltipDonate.
  ///
  /// In en, this message translates to:
  /// **'Support our open source project'**
  String get homeNavTooltipDonate;

  /// No description provided for @homeNavTooltipHome.
  ///
  /// In en, this message translates to:
  /// **'Return to home page'**
  String get homeNavTooltipHome;

  /// No description provided for @homeNavTooltipGitHub.
  ///
  /// In en, this message translates to:
  /// **'View source code on GitHub — star us if you find it useful!'**
  String get homeNavTooltipGitHub;

  /// No description provided for @batchUploadTitle.
  ///
  /// In en, this message translates to:
  /// **'Batch file upload'**
  String get batchUploadTitle;

  /// No description provided for @batchUploadFormatConvert.
  ///
  /// In en, this message translates to:
  /// **'Format conversion'**
  String get batchUploadFormatConvert;

  /// No description provided for @batchUploadSelectSourceHint.
  ///
  /// In en, this message translates to:
  /// **'Choose supported files to translate. Each file becomes a queued task.'**
  String get batchUploadSelectSourceHint;

  /// No description provided for @batchUploadSelectFolder.
  ///
  /// In en, this message translates to:
  /// **'Select folder'**
  String get batchUploadSelectFolder;

  /// No description provided for @batchUploadFolderDescription.
  ///
  /// In en, this message translates to:
  /// **'Pick a folder containing files to translate'**
  String get batchUploadFolderDescription;

  /// No description provided for @batchUploadSelectZip.
  ///
  /// In en, this message translates to:
  /// **'Select ZIP archive'**
  String get batchUploadSelectZip;

  /// No description provided for @batchUploadZipDescription.
  ///
  /// In en, this message translates to:
  /// **'Pick a ZIP archive containing files to translate'**
  String get batchUploadZipDescription;

  /// No description provided for @batchUploadSelectSingleFile.
  ///
  /// In en, this message translates to:
  /// **'Select file'**
  String get batchUploadSelectSingleFile;

  /// No description provided for @batchUploadSingleFileDescription.
  ///
  /// In en, this message translates to:
  /// **'Pick a single file to translate'**
  String get batchUploadSingleFileDescription;

  /// No description provided for @batchUploadAddFiles.
  ///
  /// In en, this message translates to:
  /// **'Add files'**
  String get batchUploadAddFiles;

  /// No description provided for @batchUploadFilesFound.
  ///
  /// In en, this message translates to:
  /// **'{count} supported files found'**
  String batchUploadFilesFound(Object count);

  /// No description provided for @batchUploadSelectAll.
  ///
  /// In en, this message translates to:
  /// **'Select all'**
  String get batchUploadSelectAll;

  /// No description provided for @batchUploadDeselectAll.
  ///
  /// In en, this message translates to:
  /// **'Deselect all'**
  String get batchUploadDeselectAll;

  /// No description provided for @batchUploadStartTranslation.
  ///
  /// In en, this message translates to:
  /// **'Start translation'**
  String get batchUploadStartTranslation;

  /// No description provided for @batchUploadSubmitting.
  ///
  /// In en, this message translates to:
  /// **'Submitting files...'**
  String get batchUploadSubmitting;

  /// No description provided for @batchUploadProgress.
  ///
  /// In en, this message translates to:
  /// **'Submitted {completed} of {total} files'**
  String batchUploadProgress(Object completed, Object total);

  /// No description provided for @batchUploadCompleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Batch complete'**
  String get batchUploadCompleteTitle;

  /// No description provided for @batchUploadComplete.
  ///
  /// In en, this message translates to:
  /// **'{success} succeeded, {failed} failed'**
  String batchUploadComplete(Object success, Object failed);

  /// No description provided for @batchUploadNoSupportedFiles.
  ///
  /// In en, this message translates to:
  /// **'No supported files found in this source'**
  String get batchUploadNoSupportedFiles;

  /// No description provided for @batchUploadSelectedCount.
  ///
  /// In en, this message translates to:
  /// **'{count} files selected'**
  String batchUploadSelectedCount(Object count);

  /// Shown when legacy formats (.doc/.ppt/.xls) are found but no supported files
  ///
  /// In en, this message translates to:
  /// **'{files} cannot be translated directly. Please convert .doc to .docx, .ppt to .pptx, .xls to .xlsx before submitting.'**
  String batchUploadLegacyFormatsFound(Object files);

  /// Shown when legacy format files are skipped in batch upload
  ///
  /// In en, this message translates to:
  /// **'{count} file(s) skipped — legacy format not directly supported. Please convert .doc to .docx, .ppt to .pptx, .xls to .xlsx and try again.'**
  String batchUploadLegacyFormatsSkipped(Object count);

  /// No description provided for @batchUploadSettingsToggle.
  ///
  /// In en, this message translates to:
  /// **'Quick settings'**
  String get batchUploadSettingsToggle;

  /// No description provided for @batchUploadSaveDefaults.
  ///
  /// In en, this message translates to:
  /// **'Save as defaults'**
  String get batchUploadSaveDefaults;

  /// Shows temperature value in batch upload settings
  ///
  /// In en, this message translates to:
  /// **'Temperature: {value}'**
  String batchUploadTemperature(Object value);

  /// Shows how many glossaries are selected
  ///
  /// In en, this message translates to:
  /// **'Glossaries selected: {count}'**
  String batchUploadGlossaryHint(Object count);

  /// No description provided for @batchUploadGlossaryNone.
  ///
  /// In en, this message translates to:
  /// **'No glossaries selected'**
  String get batchUploadGlossaryNone;

  /// No description provided for @batchUploadConfirmLangTitle.
  ///
  /// In en, this message translates to:
  /// **'Confirm Target Language'**
  String get batchUploadConfirmLangTitle;

  /// No description provided for @batchUploadConfirmLangMessage.
  ///
  /// In en, this message translates to:
  /// **'The target language is \"{lang}\". Do you want to continue?'**
  String batchUploadConfirmLangMessage(Object lang);

  /// No description provided for @batchUploadConvert.
  ///
  /// In en, this message translates to:
  /// **'Convert'**
  String get batchUploadConvert;

  /// No description provided for @batchUploadTranslate.
  ///
  /// In en, this message translates to:
  /// **'Translate'**
  String get batchUploadTranslate;

  /// No description provided for @batchUploadFolderPickerTitle.
  ///
  /// In en, this message translates to:
  /// **'Select folder with files to translate'**
  String get batchUploadFolderPickerTitle;

  /// No description provided for @batchUploadZipPickerTitle.
  ///
  /// In en, this message translates to:
  /// **'Select ZIP archive containing files to translate'**
  String get batchUploadZipPickerTitle;

  /// No description provided for @batchUploadScanFolderError.
  ///
  /// In en, this message translates to:
  /// **'Failed to scan folder: {error}'**
  String batchUploadScanFolderError(Object error);

  /// No description provided for @batchUploadReadZipError.
  ///
  /// In en, this message translates to:
  /// **'Failed to read ZIP archive: {error}'**
  String batchUploadReadZipError(Object error);

  /// No description provided for @batchUploadGlossarySection.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get batchUploadGlossarySection;

  /// No description provided for @batchUploadGlossaryMore.
  ///
  /// In en, this message translates to:
  /// **'+{count}'**
  String batchUploadGlossaryMore(Object count);

  /// No description provided for @batchUploadGlossaryLoadError.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String batchUploadGlossaryLoadError(Object error);

  /// No description provided for @batchUploadNoGlossaries.
  ///
  /// In en, this message translates to:
  /// **'No glossaries available'**
  String get batchUploadNoGlossaries;

  /// No description provided for @batchUploadMineru.
  ///
  /// In en, this message translates to:
  /// **'MinerU'**
  String get batchUploadMineru;

  /// No description provided for @batchUploadMineruLocal.
  ///
  /// In en, this message translates to:
  /// **'MinerU Local'**
  String get batchUploadMineruLocal;

  /// No description provided for @batchUploadPaddle.
  ///
  /// In en, this message translates to:
  /// **'PaddleOCR'**
  String get batchUploadPaddle;

  /// No description provided for @batchUploadPaddleLocal.
  ///
  /// In en, this message translates to:
  /// **'PaddleOCR Local'**
  String get batchUploadPaddleLocal;

  /// No description provided for @commonClose.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get commonClose;

  /// No description provided for @translationQueueTitle.
  ///
  /// In en, this message translates to:
  /// **'Task queue'**
  String get translationQueueTitle;

  /// No description provided for @translationQueueHint.
  ///
  /// In en, this message translates to:
  /// **'Tasks refresh automatically. Downloads appear when a task completes.'**
  String get translationQueueHint;

  /// No description provided for @translationQueueCancelExitHint.
  ///
  /// In en, this message translates to:
  /// **'For queued or running tasks, use Cancel task to stop work; after you confirm, you return to the home page.'**
  String get translationQueueCancelExitHint;

  /// No description provided for @translationQueueCancelDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel this translation task?'**
  String get translationQueueCancelDialogTitle;

  /// No description provided for @translationQueueCancelDialogMessage.
  ///
  /// In en, this message translates to:
  /// **'Queued tasks are removed from the queue; running tasks are stopped. After confirming, you will return to the home page.'**
  String get translationQueueCancelDialogMessage;

  /// No description provided for @translationQueueCancelDialogKeep.
  ///
  /// In en, this message translates to:
  /// **'Keep'**
  String get translationQueueCancelDialogKeep;

  /// No description provided for @translationQueueCancelDialogConfirm.
  ///
  /// In en, this message translates to:
  /// **'Cancel task'**
  String get translationQueueCancelDialogConfirm;

  /// No description provided for @translationQueueEmpty.
  ///
  /// In en, this message translates to:
  /// **'No translation tasks yet.'**
  String get translationQueueEmpty;

  /// No description provided for @translationQueueNewQueuedTask.
  ///
  /// In en, this message translates to:
  /// **'Queued task'**
  String get translationQueueNewQueuedTask;

  /// No description provided for @translationQueueImport.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get translationQueueImport;

  /// No description provided for @translationQueueBackToQueueTooltip.
  ///
  /// In en, this message translates to:
  /// **'Back to task queue'**
  String get translationQueueBackToQueueTooltip;

  /// No description provided for @translationQueuedStarted.
  ///
  /// In en, this message translates to:
  /// **'Task added to the queue. Track it here.'**
  String get translationQueuedStarted;

  /// No description provided for @translationQueueRefresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get translationQueueRefresh;

  /// No description provided for @translationQueueCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel task'**
  String get translationQueueCancel;

  /// No description provided for @translationQueueRelease.
  ///
  /// In en, this message translates to:
  /// **'Remove from list'**
  String get translationQueueRelease;

  /// No description provided for @translationQueueDownloads.
  ///
  /// In en, this message translates to:
  /// **'Downloads'**
  String get translationQueueDownloads;

  /// No description provided for @translationQueueDownloadMdEmbedded.
  ///
  /// In en, this message translates to:
  /// **'MD (embedded)'**
  String get translationQueueDownloadMdEmbedded;

  /// No description provided for @translationQueueDownloadMdZip.
  ///
  /// In en, this message translates to:
  /// **'MD (ZIP)'**
  String get translationQueueDownloadMdZip;

  /// No description provided for @translationQueueExecutionModeQueued.
  ///
  /// In en, this message translates to:
  /// **'Queued'**
  String get translationQueueExecutionModeQueued;

  /// No description provided for @translationQueueExecutionModeImmediate.
  ///
  /// In en, this message translates to:
  /// **'Immediate'**
  String get translationQueueExecutionModeImmediate;

  /// No description provided for @translationQueueTaskTypeTranslation.
  ///
  /// In en, this message translates to:
  /// **'Translation'**
  String get translationQueueTaskTypeTranslation;

  /// No description provided for @translationQueueTaskTypeConversion.
  ///
  /// In en, this message translates to:
  /// **'Conversion'**
  String get translationQueueTaskTypeConversion;

  /// No description provided for @translationQueuePositionLabel.
  ///
  /// In en, this message translates to:
  /// **'Queue #{position}'**
  String translationQueuePositionLabel(Object position);

  /// No description provided for @translationQueueLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load tasks: {error}'**
  String translationQueueLoadFailed(Object error);

  /// No description provided for @translationQueueActionFailed.
  ///
  /// In en, this message translates to:
  /// **'Action failed: {error}'**
  String translationQueueActionFailed(Object error);

  /// No description provided for @translationQueueSubmittedBy.
  ///
  /// In en, this message translates to:
  /// **'Submitted by: {user}'**
  String translationQueueSubmittedBy(Object user);

  /// No description provided for @translationQueueStartedAt.
  ///
  /// In en, this message translates to:
  /// **'Started: {time}'**
  String translationQueueStartedAt(Object time);

  /// No description provided for @translationQueueCompletedAt.
  ///
  /// In en, this message translates to:
  /// **'Completed: {time}'**
  String translationQueueCompletedAt(Object time);

  /// No description provided for @translationQueueTimeUnknown.
  ///
  /// In en, this message translates to:
  /// **'—'**
  String get translationQueueTimeUnknown;

  /// No description provided for @translationQueueGuestUser.
  ///
  /// In en, this message translates to:
  /// **'Guest'**
  String get translationQueueGuestUser;

  /// No description provided for @translationQueueClearAllTooltip.
  ///
  /// In en, this message translates to:
  /// **'Clear task queue and server-side result cache (admin only)'**
  String get translationQueueClearAllTooltip;

  /// No description provided for @translationQueueClearAllButton.
  ///
  /// In en, this message translates to:
  /// **'Clear queue'**
  String get translationQueueClearAllButton;

  /// No description provided for @translationQueueClearAllTitle.
  ///
  /// In en, this message translates to:
  /// **'Clear task queue'**
  String get translationQueueClearAllTitle;

  /// No description provided for @translationQueueClearAllMessage.
  ///
  /// In en, this message translates to:
  /// **'This cancels queued and in-flight work, removes all in-memory tasks, and deletes on-disk queue snapshots. This cannot be undone.'**
  String get translationQueueClearAllMessage;

  /// No description provided for @translationQueueClearAllConfirm.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get translationQueueClearAllConfirm;

  /// No description provided for @translationQueueClearAllCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get translationQueueClearAllCancel;

  /// No description provided for @translationQueueClearAllSuccess.
  ///
  /// In en, this message translates to:
  /// **'Task queue cleared.'**
  String get translationQueueClearAllSuccess;

  /// No description provided for @translationQueueClearAllFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not clear queue: {error}'**
  String translationQueueClearAllFailed(Object error);

  /// No description provided for @translationQueueClearMyQueueTooltip.
  ///
  /// In en, this message translates to:
  /// **'Clear my queue'**
  String get translationQueueClearMyQueueTooltip;

  /// No description provided for @translationQueueClearMyQueueTitle.
  ///
  /// In en, this message translates to:
  /// **'Clear my queue'**
  String get translationQueueClearMyQueueTitle;

  /// No description provided for @translationQueueClearMyQueueMessage.
  ///
  /// In en, this message translates to:
  /// **'Remove all your tasks from the queue?'**
  String get translationQueueClearMyQueueMessage;

  /// No description provided for @translationQueueClearMyQueueConfirm.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get translationQueueClearMyQueueConfirm;

  /// No description provided for @translationQueueClearMyQueueCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get translationQueueClearMyQueueCancel;

  /// No description provided for @translationQueueClearMyQueueSuccess.
  ///
  /// In en, this message translates to:
  /// **'My queue cleared.'**
  String get translationQueueClearMyQueueSuccess;

  /// No description provided for @translationQueueClearMyQueueFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not clear your queue: {error}'**
  String translationQueueClearMyQueueFailed(Object error);

  /// No description provided for @translationQueueErrorMessageCopied.
  ///
  /// In en, this message translates to:
  /// **'Error message copied'**
  String get translationQueueErrorMessageCopied;

  /// No description provided for @translationQueueSelected.
  ///
  /// In en, this message translates to:
  /// **'selected'**
  String get translationQueueSelected;

  /// No description provided for @translationQueueSelectMode.
  ///
  /// In en, this message translates to:
  /// **'Select'**
  String get translationQueueSelectMode;

  /// No description provided for @translationQueueClearSelection.
  ///
  /// In en, this message translates to:
  /// **'Clear selection'**
  String get translationQueueClearSelection;

  /// No description provided for @translationQueueBatchDownloadFailed.
  ///
  /// In en, this message translates to:
  /// **'Batch download failed: {error}'**
  String translationQueueBatchDownloadFailed(Object error);

  /// No description provided for @translationQueueBatchDownloadSuccess.
  ///
  /// In en, this message translates to:
  /// **'Batch download: {fileType} ready'**
  String translationQueueBatchDownloadSuccess(Object fileType);

  /// No description provided for @translationQueueView.
  ///
  /// In en, this message translates to:
  /// **'Reading Edit'**
  String get translationQueueView;

  /// No description provided for @translationQueueViewSourcePath.
  ///
  /// In en, this message translates to:
  /// **'View original file path'**
  String get translationQueueViewSourcePath;

  /// No description provided for @translationQueueSourcePathTitle.
  ///
  /// In en, this message translates to:
  /// **'Source File Path'**
  String get translationQueueSourcePathTitle;

  /// No description provided for @translationQueueFileNameLabel.
  ///
  /// In en, this message translates to:
  /// **'File Name'**
  String get translationQueueFileNameLabel;

  /// No description provided for @translationQueueRelativePathLabel.
  ///
  /// In en, this message translates to:
  /// **'Relative Path'**
  String get translationQueueRelativePathLabel;

  /// No description provided for @homeFeatureUnderDevelopment.
  ///
  /// In en, this message translates to:
  /// **'This feature is under development.'**
  String get homeFeatureUnderDevelopment;

  /// No description provided for @homeAnonymizeNotSupportedVersion.
  ///
  /// In en, this message translates to:
  /// **'Not supported yet. Will be available in v{version}.'**
  String homeAnonymizeNotSupportedVersion(Object version);

  /// No description provided for @homeAnonymizeInDevelopment.
  ///
  /// In en, this message translates to:
  /// **'Anonymization is in development and not yet available.'**
  String get homeAnonymizeInDevelopment;

  /// No description provided for @homeScrollLeft.
  ///
  /// In en, this message translates to:
  /// **'Scroll left'**
  String get homeScrollLeft;

  /// No description provided for @homeScrollRight.
  ///
  /// In en, this message translates to:
  /// **'Scroll right'**
  String get homeScrollRight;

  /// No description provided for @homeTabHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get homeTabHome;

  /// No description provided for @homeToolbarAdBanner.
  ///
  /// In en, this message translates to:
  /// **'Toolbar Ad Banner\n(728×90 Leaderboard / 320×50 Mobile)'**
  String get homeToolbarAdBanner;

  /// No description provided for @homeSteps.
  ///
  /// In en, this message translates to:
  /// **'Steps'**
  String get homeSteps;

  /// No description provided for @homePhaseUpload.
  ///
  /// In en, this message translates to:
  /// **'Upload'**
  String get homePhaseUpload;

  /// No description provided for @homePhaseExtract.
  ///
  /// In en, this message translates to:
  /// **'Extract'**
  String get homePhaseExtract;

  /// No description provided for @homePhaseGlossary.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get homePhaseGlossary;

  /// No description provided for @homePhaseTranslate.
  ///
  /// In en, this message translates to:
  /// **'Translate'**
  String get homePhaseTranslate;

  /// No description provided for @homePhaseViewer.
  ///
  /// In en, this message translates to:
  /// **'Revise'**
  String get homePhaseViewer;

  /// No description provided for @homePhaseAnonymize.
  ///
  /// In en, this message translates to:
  /// **'Anonymize'**
  String get homePhaseAnonymize;

  /// No description provided for @homePhaseDeAnonymize.
  ///
  /// In en, this message translates to:
  /// **'De-anonymize'**
  String get homePhaseDeAnonymize;

  /// No description provided for @homePhaseExport.
  ///
  /// In en, this message translates to:
  /// **'Export'**
  String get homePhaseExport;

  /// No description provided for @taskDefaultTitleTranslate.
  ///
  /// In en, this message translates to:
  /// **'Task'**
  String get taskDefaultTitleTranslate;

  /// No description provided for @taskDefaultTitleAnonymize.
  ///
  /// In en, this message translates to:
  /// **'Anonymization'**
  String get taskDefaultTitleAnonymize;

  /// No description provided for @homeReleaseNotesTitle.
  ///
  /// In en, this message translates to:
  /// **'Release Notes'**
  String get homeReleaseNotesTitle;

  /// No description provided for @homeReleaseNotesViewOnGitHub.
  ///
  /// In en, this message translates to:
  /// **'View on GitHub'**
  String get homeReleaseNotesViewOnGitHub;

  /// No description provided for @homeEditionEnterprise.
  ///
  /// In en, this message translates to:
  /// **'Enterprise'**
  String get homeEditionEnterprise;

  /// No description provided for @homeEditionEnterpriseStatusActivated.
  ///
  /// In en, this message translates to:
  /// **'Activated'**
  String get homeEditionEnterpriseStatusActivated;

  /// No description provided for @homeEditionActivateEnterprise.
  ///
  /// In en, this message translates to:
  /// **'Activate Enterprise'**
  String get homeEditionActivateEnterprise;

  /// No description provided for @homeEditionPro.
  ///
  /// In en, this message translates to:
  /// **'Pro'**
  String get homeEditionPro;

  /// No description provided for @homeEditionStandard.
  ///
  /// In en, this message translates to:
  /// **'Standard'**
  String get homeEditionStandard;

  /// No description provided for @homeEditionStandardStatus.
  ///
  /// In en, this message translates to:
  /// **'Always available'**
  String get homeEditionStandardStatus;

  /// No description provided for @homeEditionProStatusTrialRemaining.
  ///
  /// In en, this message translates to:
  /// **'{days} days left'**
  String homeEditionProStatusTrialRemaining(Object days);

  /// No description provided for @homeEditionProStatusNotActivated.
  ///
  /// In en, this message translates to:
  /// **'Not activated'**
  String get homeEditionProStatusNotActivated;

  /// No description provided for @homeEditionProStatusActivated.
  ///
  /// In en, this message translates to:
  /// **'Activated'**
  String get homeEditionProStatusActivated;

  /// No description provided for @homeWelcomeDearPro.
  ///
  /// In en, this message translates to:
  /// **'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.'**
  String get homeWelcomeDearPro;

  /// No description provided for @homeWelcomeDearStandard.
  ///
  /// In en, this message translates to:
  /// **'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.'**
  String get homeWelcomeDearStandard;

  /// No description provided for @homeWelcomeDearProNoUser.
  ///
  /// In en, this message translates to:
  /// **'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.'**
  String get homeWelcomeDearProNoUser;

  /// No description provided for @homeWelcomeDearStandardNoUser.
  ///
  /// In en, this message translates to:
  /// **'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.'**
  String get homeWelcomeDearStandardNoUser;

  /// No description provided for @homeWelcomeHello.
  ///
  /// In en, this message translates to:
  /// **'Immersive translation: Compare source and translation side by side in the UI.\nQueue translation: Enqueue documents and run the full pipeline in order.'**
  String get homeWelcomeHello;

  /// No description provided for @homeLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get homeLoading;

  /// No description provided for @homeWelcomeGuest.
  ///
  /// In en, this message translates to:
  /// **'Welcome!'**
  String get homeWelcomeGuest;

  /// No description provided for @homeFileNotFound.
  ///
  /// In en, this message translates to:
  /// **'File not found: {fileName}. The file may have been moved or deleted.'**
  String homeFileNotFound(Object fileName);

  /// No description provided for @homeFileSelectedMismatch.
  ///
  /// In en, this message translates to:
  /// **'Selected file name does not match: {selected}. Expected: {expected}'**
  String homeFileSelectedMismatch(Object expected, Object selected);

  /// No description provided for @homeFileLoaded.
  ///
  /// In en, this message translates to:
  /// **'File loaded: {fileName}'**
  String homeFileLoaded(Object fileName);

  /// No description provided for @homeFileSelectionCancelled.
  ///
  /// In en, this message translates to:
  /// **'File selection cancelled.'**
  String get homeFileSelectionCancelled;

  /// No description provided for @homeFileLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load file: {error}'**
  String homeFileLoadFailed(Object error);

  /// No description provided for @homeFlowCreateFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to create flow: {error}'**
  String homeFlowCreateFailed(Object error);

  /// No description provided for @commonPageNotFound.
  ///
  /// In en, this message translates to:
  /// **'Page not found: {uri}'**
  String commonPageNotFound(Object uri);

  /// No description provided for @commonGoHome.
  ///
  /// In en, this message translates to:
  /// **'Go Home'**
  String get commonGoHome;

  /// No description provided for @commonLogin.
  ///
  /// In en, this message translates to:
  /// **'Login'**
  String get commonLogin;

  /// No description provided for @commonLogout.
  ///
  /// In en, this message translates to:
  /// **'Logout'**
  String get commonLogout;

  /// No description provided for @userMenuChangePassword.
  ///
  /// In en, this message translates to:
  /// **'Change password'**
  String get userMenuChangePassword;

  /// No description provided for @changePasswordCurrentPasswordLabel.
  ///
  /// In en, this message translates to:
  /// **'Current password'**
  String get changePasswordCurrentPasswordLabel;

  /// No description provided for @changePasswordNewPasswordLabel.
  ///
  /// In en, this message translates to:
  /// **'New password'**
  String get changePasswordNewPasswordLabel;

  /// No description provided for @changePasswordConfirmPasswordLabel.
  ///
  /// In en, this message translates to:
  /// **'Confirm new password'**
  String get changePasswordConfirmPasswordLabel;

  /// No description provided for @changePasswordRequiredError.
  ///
  /// In en, this message translates to:
  /// **'Current password and new password are required.'**
  String get changePasswordRequiredError;

  /// No description provided for @changePasswordConfirmMismatchError.
  ///
  /// In en, this message translates to:
  /// **'The two new passwords do not match.'**
  String get changePasswordConfirmMismatchError;

  /// No description provided for @changePasswordSuccessMessage.
  ///
  /// In en, this message translates to:
  /// **'Password changed successfully.'**
  String get changePasswordSuccessMessage;

  /// No description provided for @changePasswordRequirementsTitle.
  ///
  /// In en, this message translates to:
  /// **'Password requirements'**
  String get changePasswordRequirementsTitle;

  /// No description provided for @changePasswordRequirementLength.
  ///
  /// In en, this message translates to:
  /// **'8–128 characters'**
  String get changePasswordRequirementLength;

  /// No description provided for @changePasswordRequirementUppercase.
  ///
  /// In en, this message translates to:
  /// **'At least 1 uppercase letter'**
  String get changePasswordRequirementUppercase;

  /// No description provided for @changePasswordRequirementLowercase.
  ///
  /// In en, this message translates to:
  /// **'At least 1 lowercase letter'**
  String get changePasswordRequirementLowercase;

  /// No description provided for @changePasswordRequirementDigit.
  ///
  /// In en, this message translates to:
  /// **'At least 1 digit'**
  String get changePasswordRequirementDigit;

  /// No description provided for @settingsTabsGeneral.
  ///
  /// In en, this message translates to:
  /// **'General'**
  String get settingsTabsGeneral;

  /// No description provided for @settingsTabsAiPlatforms.
  ///
  /// In en, this message translates to:
  /// **'AI Platforms'**
  String get settingsTabsAiPlatforms;

  /// No description provided for @settingsTabsParsingEngine.
  ///
  /// In en, this message translates to:
  /// **'Parsing Engine'**
  String get settingsTabsParsingEngine;

  /// No description provided for @settingsParsingEngineTitle.
  ///
  /// In en, this message translates to:
  /// **'Parsing Engine'**
  String get settingsParsingEngineTitle;

  /// No description provided for @settingsParsingEngineSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Select the document parsing engine for text extraction and processing.'**
  String get settingsParsingEngineSubtitle;

  /// No description provided for @settingsParsingEngineLabel.
  ///
  /// In en, this message translates to:
  /// **'Parsing Engine'**
  String get settingsParsingEngineLabel;

  /// No description provided for @settingsParsingEngineMineru.
  ///
  /// In en, this message translates to:
  /// **'MinerU (Cloud)'**
  String get settingsParsingEngineMineru;

  /// No description provided for @settingsParsingEngineMineruDesc.
  ///
  /// In en, this message translates to:
  /// **'Advanced document parsing with OCR support'**
  String get settingsParsingEngineMineruDesc;

  /// No description provided for @settingsParsingEngineMineruLocal.
  ///
  /// In en, this message translates to:
  /// **'MinerU (Local)'**
  String get settingsParsingEngineMineruLocal;

  /// No description provided for @settingsParsingEngineMineruLocalDesc.
  ///
  /// In en, this message translates to:
  /// **'Self-hosted MinerU; API key optional'**
  String get settingsParsingEngineMineruLocalDesc;

  /// No description provided for @settingsParsingEnginePaddle.
  ///
  /// In en, this message translates to:
  /// **'PaddleOCR (Cloud)'**
  String get settingsParsingEnginePaddle;

  /// No description provided for @settingsParsingEnginePaddleDesc.
  ///
  /// In en, this message translates to:
  /// **'High-accuracy OCR with layout parsing for titles, tables, and formulas'**
  String get settingsParsingEnginePaddleDesc;

  /// No description provided for @settingsParsingEnginePaddleLocal.
  ///
  /// In en, this message translates to:
  /// **'PaddleOCR (Local)'**
  String get settingsParsingEnginePaddleLocal;

  /// No description provided for @settingsParsingEnginePaddleLocalDesc.
  ///
  /// In en, this message translates to:
  /// **'Self-hosted PaddleOCR; requires NVIDIA GPU (~8.5 GB VRAM)'**
  String get settingsParsingEnginePaddleLocalDesc;

  /// No description provided for @settingsParsingEnginePdfplumber.
  ///
  /// In en, this message translates to:
  /// **'PDFPlumber'**
  String get settingsParsingEnginePdfplumber;

  /// No description provided for @settingsParsingEnginePdfplumberDesc.
  ///
  /// In en, this message translates to:
  /// **'Fast PDF text extraction'**
  String get settingsParsingEnginePdfplumberDesc;

  /// No description provided for @settingsParsingEngineTesseract.
  ///
  /// In en, this message translates to:
  /// **'Tesseract OCR'**
  String get settingsParsingEngineTesseract;

  /// No description provided for @settingsParsingEngineTesseractDesc.
  ///
  /// In en, this message translates to:
  /// **'OCR-based text extraction'**
  String get settingsParsingEngineTesseractDesc;

  /// No description provided for @settingsFormulaOcr.
  ///
  /// In en, this message translates to:
  /// **'Formula OCR'**
  String get settingsFormulaOcr;

  /// No description provided for @settingsFormulaOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable OCR for mathematical formulas'**
  String get settingsFormulaOcrSubtitle;

  /// No description provided for @settingsTableOcr.
  ///
  /// In en, this message translates to:
  /// **'Table OCR'**
  String get settingsTableOcr;

  /// No description provided for @settingsTableOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable OCR for tables'**
  String get settingsTableOcrSubtitle;

  /// No description provided for @settingsMineruModelVersion.
  ///
  /// In en, this message translates to:
  /// **'Model Version'**
  String get settingsMineruModelVersion;

  /// No description provided for @settingsMineruModelVersionSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Select the MinerU parsing mode (pipeline, vlm-auto-engine, hybrid-auto-engine, vlm-http-client, or hybrid-http-client)'**
  String get settingsMineruModelVersionSubtitle;

  /// No description provided for @settingsAnonymizationNewTaskNotice.
  ///
  /// In en, this message translates to:
  /// **'Changes apply to new tasks only'**
  String get settingsAnonymizationNewTaskNotice;

  /// No description provided for @settingsParsingEngineNewTaskNotice.
  ///
  /// In en, this message translates to:
  /// **'Changes apply to new tasks only'**
  String get settingsParsingEngineNewTaskNotice;

  /// No description provided for @settingsPaddleOcrModelLabel.
  ///
  /// In en, this message translates to:
  /// **'PaddleOCR Model'**
  String get settingsPaddleOcrModelLabel;

  /// No description provided for @settingsPaddleUseDocOrientationClassify.
  ///
  /// In en, this message translates to:
  /// **'Auto-Detect Orientation'**
  String get settingsPaddleUseDocOrientationClassify;

  /// No description provided for @settingsPaddleUseDocOrientationClassifySubtitle.
  ///
  /// In en, this message translates to:
  /// **'Automatically detect and correct document orientation before OCR'**
  String get settingsPaddleUseDocOrientationClassifySubtitle;

  /// No description provided for @settingsPaddleRestructurePages.
  ///
  /// In en, this message translates to:
  /// **'Restructure Pages'**
  String get settingsPaddleRestructurePages;

  /// No description provided for @settingsPaddleRestructurePagesSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Restructure page layout for better reading order'**
  String get settingsPaddleRestructurePagesSubtitle;

  /// No description provided for @settingsPdfSplitMaxPages.
  ///
  /// In en, this message translates to:
  /// **'PDF Split Max Pages'**
  String get settingsPdfSplitMaxPages;

  /// No description provided for @settingsPdfSplitMaxWorkers.
  ///
  /// In en, this message translates to:
  /// **'PDF Split Max Workers'**
  String get settingsPdfSplitMaxWorkers;

  /// No description provided for @settingsRequestRetryCount.
  ///
  /// In en, this message translates to:
  /// **'Request Retry Count'**
  String get settingsRequestRetryCount;

  /// No description provided for @settingsOcrLanguageTitle.
  ///
  /// In en, this message translates to:
  /// **'OCR Language'**
  String get settingsOcrLanguageTitle;

  /// No description provided for @settingsOcrLanguageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Configure the OCR language for text recognition in images and scanned documents.'**
  String get settingsOcrLanguageSubtitle;

  /// No description provided for @settingsOcrLanguageLabel.
  ///
  /// In en, this message translates to:
  /// **'OCR Language'**
  String get settingsOcrLanguageLabel;

  /// No description provided for @settingsOcrLangEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get settingsOcrLangEnglish;

  /// No description provided for @settingsOcrLangChineseSimplified.
  ///
  /// In en, this message translates to:
  /// **'Chinese (Simplified)'**
  String get settingsOcrLangChineseSimplified;

  /// No description provided for @settingsOcrLangChineseTraditional.
  ///
  /// In en, this message translates to:
  /// **'Chinese (Traditional)'**
  String get settingsOcrLangChineseTraditional;

  /// No description provided for @settingsOcrLangJapanese.
  ///
  /// In en, this message translates to:
  /// **'Japanese'**
  String get settingsOcrLangJapanese;

  /// No description provided for @settingsOcrLangKorean.
  ///
  /// In en, this message translates to:
  /// **'Korean'**
  String get settingsOcrLangKorean;

  /// No description provided for @settingsOcrLangFrench.
  ///
  /// In en, this message translates to:
  /// **'French'**
  String get settingsOcrLangFrench;

  /// No description provided for @settingsOcrLangGerman.
  ///
  /// In en, this message translates to:
  /// **'German'**
  String get settingsOcrLangGerman;

  /// No description provided for @settingsOcrLangSpanish.
  ///
  /// In en, this message translates to:
  /// **'Spanish'**
  String get settingsOcrLangSpanish;

  /// No description provided for @settingsOcrLangRussian.
  ///
  /// In en, this message translates to:
  /// **'Russian'**
  String get settingsOcrLangRussian;

  /// No description provided for @settingsOcrLangArabic.
  ///
  /// In en, this message translates to:
  /// **'Arabic'**
  String get settingsOcrLangArabic;

  /// No description provided for @settingsOcrLangAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto Detect'**
  String get settingsOcrLangAuto;

  /// No description provided for @mineruLangAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto Detect'**
  String get mineruLangAuto;

  /// No description provided for @mineruLangChServer.
  ///
  /// In en, this message translates to:
  /// **'Chinese (Server)'**
  String get mineruLangChServer;

  /// No description provided for @mineruLangChLite.
  ///
  /// In en, this message translates to:
  /// **'Chinese (Lite)'**
  String get mineruLangChLite;

  /// No description provided for @mineruLangTamil.
  ///
  /// In en, this message translates to:
  /// **'Tamil'**
  String get mineruLangTamil;

  /// No description provided for @mineruLangTelugu.
  ///
  /// In en, this message translates to:
  /// **'Telugu'**
  String get mineruLangTelugu;

  /// No description provided for @mineruLangKannada.
  ///
  /// In en, this message translates to:
  /// **'Kannada'**
  String get mineruLangKannada;

  /// No description provided for @mineruLangLatinScript.
  ///
  /// In en, this message translates to:
  /// **'Latin Script'**
  String get mineruLangLatinScript;

  /// No description provided for @mineruLangArabicScript.
  ///
  /// In en, this message translates to:
  /// **'Arabic Script'**
  String get mineruLangArabicScript;

  /// No description provided for @mineruLangEastSlavic.
  ///
  /// In en, this message translates to:
  /// **'East Slavic'**
  String get mineruLangEastSlavic;

  /// No description provided for @mineruLangCyrillicScript.
  ///
  /// In en, this message translates to:
  /// **'Cyrillic Script'**
  String get mineruLangCyrillicScript;

  /// No description provided for @mineruLangDevanagariScript.
  ///
  /// In en, this message translates to:
  /// **'Devanagari Script'**
  String get mineruLangDevanagariScript;

  /// No description provided for @settingsTabsGlossary.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get settingsTabsGlossary;

  /// No description provided for @settingsGlossaryManagementTitle.
  ///
  /// In en, this message translates to:
  /// **'Glossary Management'**
  String get settingsGlossaryManagementTitle;

  /// No description provided for @settingsGlossaryManagementSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Manage your terminology entries for consistent translation quality.'**
  String get settingsGlossaryManagementSubtitle;

  /// No description provided for @settingsGlossarySelectGlossary.
  ///
  /// In en, this message translates to:
  /// **'Select Glossary'**
  String get settingsGlossarySelectGlossary;

  /// No description provided for @settingsGlossaryCreateGlossary.
  ///
  /// In en, this message translates to:
  /// **'Create'**
  String get settingsGlossaryCreateGlossary;

  /// No description provided for @settingsGlossaryImportCsv.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get settingsGlossaryImportCsv;

  /// No description provided for @settingsGlossaryExport.
  ///
  /// In en, this message translates to:
  /// **'Export'**
  String get settingsGlossaryExport;

  /// No description provided for @settingsGlossaryExportAll.
  ///
  /// In en, this message translates to:
  /// **'Export All'**
  String get settingsGlossaryExportAll;

  /// No description provided for @settingsGlossaryDeleteGlossary.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get settingsGlossaryDeleteGlossary;

  /// No description provided for @settingsGlossarySaveZip.
  ///
  /// In en, this message translates to:
  /// **'Save ZIP'**
  String get settingsGlossarySaveZip;

  /// No description provided for @settingsGlossaryEntriesTitle.
  ///
  /// In en, this message translates to:
  /// **'Glossary Entries ({count})'**
  String settingsGlossaryEntriesTitle(Object count);

  /// No description provided for @settingsGlossaryAddEntry.
  ///
  /// In en, this message translates to:
  /// **'Add Entry'**
  String get settingsGlossaryAddEntry;

  /// No description provided for @settingsGlossaryNoEntriesYet.
  ///
  /// In en, this message translates to:
  /// **'No glossary entries yet.\nAdd your first entry to get started.'**
  String get settingsGlossaryNoEntriesYet;

  /// No description provided for @settingsGlossaryFilterLabel.
  ///
  /// In en, this message translates to:
  /// **'Filter:'**
  String get settingsGlossaryFilterLabel;

  /// No description provided for @settingsGlossaryFilterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get settingsGlossaryFilterAll;

  /// No description provided for @settingsGlossaryFilterUncategorized.
  ///
  /// In en, this message translates to:
  /// **'Uncategorized'**
  String get settingsGlossaryFilterUncategorized;

  /// No description provided for @settingsGlossaryTableSource.
  ///
  /// In en, this message translates to:
  /// **'Source'**
  String get settingsGlossaryTableSource;

  /// No description provided for @settingsGlossaryTableTarget.
  ///
  /// In en, this message translates to:
  /// **'Target'**
  String get settingsGlossaryTableTarget;

  /// No description provided for @settingsGlossaryTableCategory.
  ///
  /// In en, this message translates to:
  /// **'Category (Optional)'**
  String get settingsGlossaryTableCategory;

  /// No description provided for @settingsGlossaryTableTargetLang.
  ///
  /// In en, this message translates to:
  /// **'Target Language'**
  String get settingsGlossaryTableTargetLang;

  /// No description provided for @settingsGlossaryCategoryHint.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get settingsGlossaryCategoryHint;

  /// No description provided for @settingsGlossaryUncategorizedDisplay.
  ///
  /// In en, this message translates to:
  /// **'(Uncategorized)'**
  String get settingsGlossaryUncategorizedDisplay;

  /// No description provided for @settingsGlossaryCopyAction.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get settingsGlossaryCopyAction;

  /// No description provided for @settingsGlossaryCopiedToClipboard.
  ///
  /// In en, this message translates to:
  /// **'Copied to clipboard'**
  String get settingsGlossaryCopiedToClipboard;

  /// No description provided for @settingsGlossaryDeleteDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete Glossary'**
  String get settingsGlossaryDeleteDialogTitle;

  /// No description provided for @settingsGlossaryDeleteDialogMessage.
  ///
  /// In en, this message translates to:
  /// **'Are you sure to delete this glossary?\nID: {id}'**
  String settingsGlossaryDeleteDialogMessage(Object id);

  /// No description provided for @settingsGlossaryCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get settingsGlossaryCancel;

  /// No description provided for @settingsGlossaryDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get settingsGlossaryDelete;

  /// No description provided for @settingsGlossaryCreateDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Create Glossary'**
  String get settingsGlossaryCreateDialogTitle;

  /// No description provided for @settingsGlossaryNameLabel.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get settingsGlossaryNameLabel;

  /// No description provided for @settingsGlossaryDescriptionLabel.
  ///
  /// In en, this message translates to:
  /// **'Description (optional)'**
  String get settingsGlossaryDescriptionLabel;

  /// No description provided for @settingsGlossaryGlobalGlossary.
  ///
  /// In en, this message translates to:
  /// **'Global Glossary'**
  String get settingsGlossaryGlobalGlossary;

  /// No description provided for @settingsGlossaryGlobalGlossarySubtitle.
  ///
  /// In en, this message translates to:
  /// **'If off, it will be your personal glossary'**
  String get settingsGlossaryGlobalGlossarySubtitle;

  /// No description provided for @settingsGlossaryCreate.
  ///
  /// In en, this message translates to:
  /// **'Create'**
  String get settingsGlossaryCreate;

  /// No description provided for @settingsGlossaryNameRequired.
  ///
  /// In en, this message translates to:
  /// **'Name is required'**
  String get settingsGlossaryNameRequired;

  /// No description provided for @settingsGlossaryCreatedSnack.
  ///
  /// In en, this message translates to:
  /// **'Created: {name}'**
  String settingsGlossaryCreatedSnack(Object name);

  /// No description provided for @settingsGlossaryCreateFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Create failed: {error}'**
  String settingsGlossaryCreateFailedSnack(Object error);

  /// No description provided for @settingsGlossaryAddEntryDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Add Entry to Glossary'**
  String get settingsGlossaryAddEntryDialogTitle;

  /// No description provided for @settingsGlossarySourceTextLabel.
  ///
  /// In en, this message translates to:
  /// **'Source Text'**
  String get settingsGlossarySourceTextLabel;

  /// No description provided for @settingsGlossaryTargetTextLabel.
  ///
  /// In en, this message translates to:
  /// **'Target Text'**
  String get settingsGlossaryTargetTextLabel;

  /// No description provided for @settingsGlossaryCategoryOptionalLabel.
  ///
  /// In en, this message translates to:
  /// **'Category (optional)'**
  String get settingsGlossaryCategoryOptionalLabel;

  /// No description provided for @settingsGlossaryCategoryOptionalHint.
  ///
  /// In en, this message translates to:
  /// **'Leave empty for unclassified'**
  String get settingsGlossaryCategoryOptionalHint;

  /// No description provided for @settingsGlossaryAdd.
  ///
  /// In en, this message translates to:
  /// **'Add'**
  String get settingsGlossaryAdd;

  /// No description provided for @settingsGlossarySourceTargetRequired.
  ///
  /// In en, this message translates to:
  /// **'Source text and target text are required'**
  String get settingsGlossarySourceTargetRequired;

  /// No description provided for @settingsGlossaryEntryAddedSnack.
  ///
  /// In en, this message translates to:
  /// **'Entry added'**
  String get settingsGlossaryEntryAddedSnack;

  /// No description provided for @settingsGlossaryAddFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed: {error}'**
  String settingsGlossaryAddFailedSnack(Object error);

  /// No description provided for @settingsGlossaryImportDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Import CSV/TBX to Glossary'**
  String get settingsGlossaryImportDialogTitle;

  /// No description provided for @settingsGlossaryMergeModeLabel.
  ///
  /// In en, this message translates to:
  /// **'Merge Mode'**
  String get settingsGlossaryMergeModeLabel;

  /// No description provided for @settingsGlossaryMergeUpdate.
  ///
  /// In en, this message translates to:
  /// **'Update (Upsert)'**
  String get settingsGlossaryMergeUpdate;

  /// No description provided for @settingsGlossaryMergeAppend.
  ///
  /// In en, this message translates to:
  /// **'Append (New Only)'**
  String get settingsGlossaryMergeAppend;

  /// No description provided for @settingsGlossaryMergeReplace.
  ///
  /// In en, this message translates to:
  /// **'Replace (Overwrite All)'**
  String get settingsGlossaryMergeReplace;

  /// No description provided for @settingsGlossaryImport.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get settingsGlossaryImport;

  /// No description provided for @settingsGlossaryUnableToReadFile.
  ///
  /// In en, this message translates to:
  /// **'Unable to read file'**
  String get settingsGlossaryUnableToReadFile;

  /// No description provided for @settingsGlossaryImportedSnack.
  ///
  /// In en, this message translates to:
  /// **'Imported: {count} items'**
  String settingsGlossaryImportedSnack(Object count);

  /// No description provided for @settingsGlossaryImportFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed: {error}'**
  String settingsGlossaryImportFailedSnack(Object error);

  /// No description provided for @settingsGlossaryExportDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Export Glossary'**
  String get settingsGlossaryExportDialogTitle;

  /// No description provided for @settingsGlossarySaveCsv.
  ///
  /// In en, this message translates to:
  /// **'Save CSV/TBX'**
  String get settingsGlossarySaveCsv;

  /// No description provided for @settingsGlossaryDownload.
  ///
  /// In en, this message translates to:
  /// **'Download'**
  String get settingsGlossaryDownload;

  /// No description provided for @settingsGlossaryDownloadedSnack.
  ///
  /// In en, this message translates to:
  /// **'Downloaded: {info}'**
  String settingsGlossaryDownloadedSnack(Object info);

  /// No description provided for @settingsGlossaryExportFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed: {error}'**
  String settingsGlossaryExportFailedSnack(Object error);

  /// No description provided for @settingsGlossaryLoadedSnack.
  ///
  /// In en, this message translates to:
  /// **'Loaded {count} entries'**
  String settingsGlossaryLoadedSnack(Object count);

  /// No description provided for @settingsGlossaryLoadFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Load failed: {error}'**
  String settingsGlossaryLoadFailedSnack(Object error);

  /// No description provided for @settingsGlossaryDeletedSnack.
  ///
  /// In en, this message translates to:
  /// **'Glossary deleted: {id}'**
  String settingsGlossaryDeletedSnack(Object id);

  /// No description provided for @settingsGlossaryDeleteFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String settingsGlossaryDeleteFailedSnack(Object error);

  /// No description provided for @settingsGlossaryExportAllFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Export all failed: {error}'**
  String settingsGlossaryExportAllFailedSnack(Object error);

  /// No description provided for @settingsGlossaryEntryUpdatedSnack.
  ///
  /// In en, this message translates to:
  /// **'Entry updated'**
  String get settingsGlossaryEntryUpdatedSnack;

  /// No description provided for @settingsGlossaryUpdateFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed to update: {error}'**
  String settingsGlossaryUpdateFailedSnack(Object error);

  /// No description provided for @settingsGlossaryEntryDeletedSnack.
  ///
  /// In en, this message translates to:
  /// **'Entry deleted'**
  String get settingsGlossaryEntryDeletedSnack;

  /// No description provided for @settingsGlossaryDeleteEntryFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed to delete: {error}'**
  String settingsGlossaryDeleteEntryFailedSnack(Object error);

  /// No description provided for @settingsGlossaryGlossaryDropdownItem.
  ///
  /// In en, this message translates to:
  /// **'{name} ({type}) · {count} items'**
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type);

  /// No description provided for @settingsGlossaryErrorPrefix.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String settingsGlossaryErrorPrefix(Object error);

  /// No description provided for @settingsGlossaryExportedAllSnack.
  ///
  /// In en, this message translates to:
  /// **'Exported: {info}'**
  String settingsGlossaryExportedAllSnack(Object info);

  /// No description provided for @settingsGlossaryEntryCount.
  ///
  /// In en, this message translates to:
  /// **'Entry count: {count}'**
  String settingsGlossaryEntryCount(Object count);

  /// No description provided for @settingsGlossaryEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get settingsGlossaryEdit;

  /// No description provided for @settingsGlossaryConfirmDeleteEntryTitle.
  ///
  /// In en, this message translates to:
  /// **'Confirm Delete'**
  String get settingsGlossaryConfirmDeleteEntryTitle;

  /// No description provided for @settingsGlossaryConfirmDeleteEntryMessage.
  ///
  /// In en, this message translates to:
  /// **'Delete entry \"{source}\"?'**
  String settingsGlossaryConfirmDeleteEntryMessage(Object source);

  /// No description provided for @settingsGlossaryEditEntryDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit Entry'**
  String get settingsGlossaryEditEntryDialogTitle;

  /// No description provided for @settingsGlossaryUpdate.
  ///
  /// In en, this message translates to:
  /// **'Update'**
  String get settingsGlossaryUpdate;

  /// No description provided for @settingsGlossaryEntryDeleteFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Failed to delete entry'**
  String get settingsGlossaryEntryDeleteFailedSnack;

  /// No description provided for @settingsGlossaryEmptyStateTitle.
  ///
  /// In en, this message translates to:
  /// **'No glossaries yet. Create your first glossary to get started.'**
  String get settingsGlossaryEmptyStateTitle;

  /// No description provided for @settingsGlossaryTooltipCreate.
  ///
  /// In en, this message translates to:
  /// **'Create a new glossary'**
  String get settingsGlossaryTooltipCreate;

  /// No description provided for @settingsGlossaryTooltipImport.
  ///
  /// In en, this message translates to:
  /// **'Import entries from CSV or TBX format'**
  String get settingsGlossaryTooltipImport;

  /// No description provided for @settingsGlossaryTooltipExport.
  ///
  /// In en, this message translates to:
  /// **'Export selected glossary to CSV or TBX format'**
  String get settingsGlossaryTooltipExport;

  /// No description provided for @settingsGlossaryTooltipExportAll.
  ///
  /// In en, this message translates to:
  /// **'Export all glossaries as a ZIP archive'**
  String get settingsGlossaryTooltipExportAll;

  /// No description provided for @settingsGlossaryTooltipDeleteGlossary.
  ///
  /// In en, this message translates to:
  /// **'Delete the selected glossary permanently'**
  String get settingsGlossaryTooltipDeleteGlossary;

  /// No description provided for @settingsGlossaryExportTemplate.
  ///
  /// In en, this message translates to:
  /// **'Export Template'**
  String get settingsGlossaryExportTemplate;

  /// No description provided for @settingsGlossaryTooltipExportTemplate.
  ///
  /// In en, this message translates to:
  /// **'Download a CSV template with header row and one example entry'**
  String get settingsGlossaryTooltipExportTemplate;

  /// No description provided for @settingsGlossarySaveTemplateCsv.
  ///
  /// In en, this message translates to:
  /// **'Save glossary template CSV'**
  String get settingsGlossarySaveTemplateCsv;

  /// No description provided for @settingsGlossaryTemplateExportedSnack.
  ///
  /// In en, this message translates to:
  /// **'Glossary template downloaded'**
  String get settingsGlossaryTemplateExportedSnack;

  /// No description provided for @settingsGlossaryTooltipFormatHelp.
  ///
  /// In en, this message translates to:
  /// **'View glossary file format requirements'**
  String get settingsGlossaryTooltipFormatHelp;

  /// No description provided for @settingsGlossaryFormatHelpTitle.
  ///
  /// In en, this message translates to:
  /// **'Glossary File Format'**
  String get settingsGlossaryFormatHelpTitle;

  /// No description provided for @settingsGlossaryFormatHelpContent.
  ///
  /// In en, this message translates to:
  /// **'CSV format (recommended for bulk editing):\n\nFile encoding: UTF-8 (UTF-8 with BOM recommended)\n\nColumns:\n• src — source text (required)\n• dst — translated text (required)\n• category — optional grouping label\n• target_lang — optional target language code (see list below)\n\nRules:\n• Header row must include src and dst\n• Rows with empty src or dst are skipped on import\n• Import also supports TBX format\n\nUse \"Export Template\" to download a sample CSV with one example row.'**
  String get settingsGlossaryFormatHelpContent;

  /// No description provided for @settingsGlossaryFormatHelpTargetLangListTitle.
  ///
  /// In en, this message translates to:
  /// **'Available target_lang values:'**
  String get settingsGlossaryFormatHelpTargetLangListTitle;

  /// No description provided for @settingsGlossaryBatchEditCategory.
  ///
  /// In en, this message translates to:
  /// **'Edit category'**
  String get settingsGlossaryBatchEditCategory;

  /// No description provided for @settingsGlossaryBatchDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get settingsGlossaryBatchDelete;

  /// No description provided for @settingsGlossaryBatchDeselect.
  ///
  /// In en, this message translates to:
  /// **'Deselect'**
  String get settingsGlossaryBatchDeselect;

  /// No description provided for @settingsGlossaryBatchSelectedCount.
  ///
  /// In en, this message translates to:
  /// **'{count} selected'**
  String settingsGlossaryBatchSelectedCount(Object count);

  /// No description provided for @settingsGlossaryExportFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Export format'**
  String get settingsGlossaryExportFormatLabel;

  /// No description provided for @settingsGlossaryExportFormatCsv.
  ///
  /// In en, this message translates to:
  /// **'CSV'**
  String get settingsGlossaryExportFormatCsv;

  /// No description provided for @settingsGlossaryExportFormatTbx.
  ///
  /// In en, this message translates to:
  /// **'TBX (TermBase eXchange)'**
  String get settingsGlossaryExportFormatTbx;

  /// No description provided for @settingsGlossaryExportSourceLanguage.
  ///
  /// In en, this message translates to:
  /// **'Source language'**
  String get settingsGlossaryExportSourceLanguage;

  /// No description provided for @settingsGlossaryExportSaveTbxTitle.
  ///
  /// In en, this message translates to:
  /// **'Save TBX file'**
  String get settingsGlossaryExportSaveTbxTitle;

  /// No description provided for @settingsGlossaryDeleteEntriesTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete entries'**
  String get settingsGlossaryDeleteEntriesTitle;

  /// No description provided for @settingsGlossaryDeleteEntriesBody.
  ///
  /// In en, this message translates to:
  /// **'Delete {count} selected entries? This cannot be undone.'**
  String settingsGlossaryDeleteEntriesBody(Object count);

  /// No description provided for @settingsGlossaryDeleteEntriesConfirm.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get settingsGlossaryDeleteEntriesConfirm;

  /// No description provided for @settingsGlossaryEditCategoryTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit Category'**
  String get settingsGlossaryEditCategoryTitle;

  /// No description provided for @settingsGlossaryEditCategoryBody.
  ///
  /// In en, this message translates to:
  /// **'Set category for {count} selected entries:'**
  String settingsGlossaryEditCategoryBody(Object count);

  /// No description provided for @settingsGlossaryEditCategoryLabel.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get settingsGlossaryEditCategoryLabel;

  /// No description provided for @settingsGlossaryEditCategoryHint.
  ///
  /// In en, this message translates to:
  /// **'Enter category name'**
  String get settingsGlossaryEditCategoryHint;

  /// No description provided for @settingsGlossaryEditCategoryApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get settingsGlossaryEditCategoryApply;

  /// No description provided for @glossaryPanelSaveNameHint.
  ///
  /// In en, this message translates to:
  /// **'Enter name or select existing...'**
  String get glossaryPanelSaveNameHint;

  /// No description provided for @glossaryPanelClearSelection.
  ///
  /// In en, this message translates to:
  /// **'Clear selection'**
  String get glossaryPanelClearSelection;

  /// No description provided for @glossaryPanelListTitle.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get glossaryPanelListTitle;

  /// No description provided for @glossaryPanelNoEntries.
  ///
  /// In en, this message translates to:
  /// **'No entries'**
  String get glossaryPanelNoEntries;

  /// No description provided for @glossaryPanelOneEntry.
  ///
  /// In en, this message translates to:
  /// **'1 entry'**
  String get glossaryPanelOneEntry;

  /// No description provided for @glossaryPanelEntriesCount.
  ///
  /// In en, this message translates to:
  /// **'{count} entries'**
  String glossaryPanelEntriesCount(Object count);

  /// No description provided for @glossaryPanelProcessing.
  ///
  /// In en, this message translates to:
  /// **'Processing...'**
  String get glossaryPanelProcessing;

  /// No description provided for @glossaryPanelDropCsvHere.
  ///
  /// In en, this message translates to:
  /// **'Drop CSV or TBX file here'**
  String get glossaryPanelDropCsvHere;

  /// No description provided for @glossaryPanelNoEntriesHint.
  ///
  /// In en, this message translates to:
  /// **'No glossary entries.\nClick on the Detect Glossary button to get started.\nOr select a glossary from the list to view its entries.\nOr drag and drop a CSV or TBX file here.'**
  String get glossaryPanelNoEntriesHint;

  /// No description provided for @glossaryPanelSelectBody.
  ///
  /// In en, this message translates to:
  /// **'Select a glossary to work with:'**
  String get glossaryPanelSelectBody;

  /// No description provided for @glossaryPanelSaveDialogTitleReplace.
  ///
  /// In en, this message translates to:
  /// **'Replace Glossary'**
  String get glossaryPanelSaveDialogTitleReplace;

  /// No description provided for @glossaryPanelSaveDialogTitleSave.
  ///
  /// In en, this message translates to:
  /// **'Save Glossary'**
  String get glossaryPanelSaveDialogTitleSave;

  /// No description provided for @glossaryPanelSaveReplaceInfo.
  ///
  /// In en, this message translates to:
  /// **'This will replace the existing glossary \"{name}\"'**
  String glossaryPanelSaveReplaceInfo(Object name);

  /// No description provided for @glossaryPanelSaveButtonSaveAs.
  ///
  /// In en, this message translates to:
  /// **'Save As'**
  String get glossaryPanelSaveButtonSaveAs;

  /// No description provided for @glossaryPanelGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating glossary...'**
  String get glossaryPanelGenerating;

  /// No description provided for @glossaryPanelDeleteEntry.
  ///
  /// In en, this message translates to:
  /// **'Delete entry'**
  String get glossaryPanelDeleteEntry;

  /// No description provided for @glossaryPanelInvertSelection.
  ///
  /// In en, this message translates to:
  /// **'Invert selection'**
  String get glossaryPanelInvertSelection;

  /// No description provided for @glossaryWidgetTitle.
  ///
  /// In en, this message translates to:
  /// **'Glossary'**
  String get glossaryWidgetTitle;

  /// No description provided for @glossaryWidgetRefreshTooltip.
  ///
  /// In en, this message translates to:
  /// **'Refresh glossary list'**
  String get glossaryWidgetRefreshTooltip;

  /// No description provided for @glossaryWidgetGlossariesSelected.
  ///
  /// In en, this message translates to:
  /// **'{count} glossary selected'**
  String glossaryWidgetGlossariesSelected(Object count);

  /// No description provided for @glossaryWidgetGlossariesSelectedPlural.
  ///
  /// In en, this message translates to:
  /// **'{count} glossaries selected'**
  String glossaryWidgetGlossariesSelectedPlural(Object count);

  /// No description provided for @glossaryWidgetSelectGlossaries.
  ///
  /// In en, this message translates to:
  /// **'Select Glossaries'**
  String get glossaryWidgetSelectGlossaries;

  /// No description provided for @glossaryWidgetLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load glossaries: {error}'**
  String glossaryWidgetLoadFailed(Object error);

  /// No description provided for @glossaryWidgetNoGlossariesHint.
  ///
  /// In en, this message translates to:
  /// **'No glossaries available. Create one in Settings -> Glossary'**
  String get glossaryWidgetNoGlossariesHint;

  /// No description provided for @glossaryWidgetTypeCountItems.
  ///
  /// In en, this message translates to:
  /// **'{type} · {count} items'**
  String glossaryWidgetTypeCountItems(Object type, Object count);

  /// No description provided for @glossaryWidgetTermsExtracted.
  ///
  /// In en, this message translates to:
  /// **'{count} terms extracted from translation'**
  String glossaryWidgetTermsExtracted(Object count);

  /// No description provided for @glossaryWidgetPersonalCreated.
  ///
  /// In en, this message translates to:
  /// **'Personal glossary created successfully!\nAdded {count} terms.'**
  String glossaryWidgetPersonalCreated(Object count);

  /// No description provided for @glossaryWidgetPersonalReplaced.
  ///
  /// In en, this message translates to:
  /// **'Personal glossary replaced successfully!\nTotal terms: {total}'**
  String glossaryWidgetPersonalReplaced(Object total);

  /// No description provided for @glossaryWidgetPersonalAppended.
  ///
  /// In en, this message translates to:
  /// **'Added {newCount} new terms to personal glossary.\nSkipped {skipped} existing terms.\nTotal terms: {total}'**
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total);

  /// No description provided for @glossaryWidgetPersonalUpdated.
  ///
  /// In en, this message translates to:
  /// **'Personal glossary updated successfully!\nAdded {newCount} new terms, updated {updatedCount} existing terms.\nTotal terms: {total}'**
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total);

  /// No description provided for @glossaryWidgetAddToPersonalFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to add to personal glossary: {error}'**
  String glossaryWidgetAddToPersonalFailed(Object error);

  /// No description provided for @settingsTabsTranslation.
  ///
  /// In en, this message translates to:
  /// **'Translation'**
  String get settingsTabsTranslation;

  /// No description provided for @settingsTabsAnonymization.
  ///
  /// In en, this message translates to:
  /// **'Anonymization'**
  String get settingsTabsAnonymization;

  /// No description provided for @settingsTabsUserManagement.
  ///
  /// In en, this message translates to:
  /// **'User Management'**
  String get settingsTabsUserManagement;

  /// No description provided for @settingsUserManagementTitle.
  ///
  /// In en, this message translates to:
  /// **'User Management Mode'**
  String get settingsUserManagementTitle;

  /// No description provided for @settingsUserManagementSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Choose login and permission policy for Web deployment. Settings and Setup Wizard are admin-only.'**
  String get settingsUserManagementSubtitle;

  /// No description provided for @settingsUserManagementModeNoLogin.
  ///
  /// In en, this message translates to:
  /// **'No login required'**
  String get settingsUserManagementModeNoLogin;

  /// No description provided for @settingsUserManagementModeNoLoginDesc.
  ///
  /// In en, this message translates to:
  /// **'Use without login; Settings and Setup Wizard available only after admin login.'**
  String get settingsUserManagementModeNoLoginDesc;

  /// No description provided for @settingsUserManagementModeLdap.
  ///
  /// In en, this message translates to:
  /// **'LDAP login'**
  String get settingsUserManagementModeLdap;

  /// No description provided for @settingsUserManagementModeLdapDesc.
  ///
  /// In en, this message translates to:
  /// **'Log in with LDAP/AD; Settings and Setup Wizard for admin (domain group) only.'**
  String get settingsUserManagementModeLdapDesc;

  /// No description provided for @settingsUserManagementModeLocal.
  ///
  /// In en, this message translates to:
  /// **'Local user login'**
  String get settingsUserManagementModeLocal;

  /// No description provided for @settingsUserManagementModeLocalDesc.
  ///
  /// In en, this message translates to:
  /// **'Authenticate against local user list on server.'**
  String get settingsUserManagementModeLocalDesc;

  /// No description provided for @settingsUserManagementInDevelopment.
  ///
  /// In en, this message translates to:
  /// **'In development'**
  String get settingsUserManagementInDevelopment;

  /// No description provided for @settingsUserManagementSaveSuccess.
  ///
  /// In en, this message translates to:
  /// **'User management mode saved'**
  String get settingsUserManagementSaveSuccess;

  /// No description provided for @settingsUserManagementSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'Save failed: {message}'**
  String settingsUserManagementSaveFailed(Object message);

  /// No description provided for @settingsLocalUsersTitle.
  ///
  /// In en, this message translates to:
  /// **'Local Users'**
  String get settingsLocalUsersTitle;

  /// No description provided for @settingsLocalUsersAddUser.
  ///
  /// In en, this message translates to:
  /// **'Add user'**
  String get settingsLocalUsersAddUser;

  /// No description provided for @settingsLocalUsersNoUsers.
  ///
  /// In en, this message translates to:
  /// **'No local users found.'**
  String get settingsLocalUsersNoUsers;

  /// No description provided for @settingsLocalUsersDialogAddTitle.
  ///
  /// In en, this message translates to:
  /// **'Add local user'**
  String get settingsLocalUsersDialogAddTitle;

  /// No description provided for @settingsLocalUsersDialogEditTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit local user'**
  String get settingsLocalUsersDialogEditTitle;

  /// No description provided for @settingsLocalUsersFieldUsername.
  ///
  /// In en, this message translates to:
  /// **'Username'**
  String get settingsLocalUsersFieldUsername;

  /// No description provided for @settingsLocalUsersFieldDisplayName.
  ///
  /// In en, this message translates to:
  /// **'Display name (optional)'**
  String get settingsLocalUsersFieldDisplayName;

  /// No description provided for @settingsLocalUsersFieldEmail.
  ///
  /// In en, this message translates to:
  /// **'Email (optional)'**
  String get settingsLocalUsersFieldEmail;

  /// No description provided for @settingsLocalUsersFieldRole.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get settingsLocalUsersFieldRole;

  /// No description provided for @settingsLocalUsersRoleUser.
  ///
  /// In en, this message translates to:
  /// **'User'**
  String get settingsLocalUsersRoleUser;

  /// No description provided for @settingsLocalUsersRoleAdmin.
  ///
  /// In en, this message translates to:
  /// **'Admin'**
  String get settingsLocalUsersRoleAdmin;

  /// No description provided for @settingsLocalUsersFieldPassword.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get settingsLocalUsersFieldPassword;

  /// No description provided for @settingsLocalUsersPasswordHelper.
  ///
  /// In en, this message translates to:
  /// **'8-128 chars, upper, lower, digit'**
  String get settingsLocalUsersPasswordHelper;

  /// No description provided for @settingsLocalUsersValidationUsernameRequired.
  ///
  /// In en, this message translates to:
  /// **'Username is required'**
  String get settingsLocalUsersValidationUsernameRequired;

  /// No description provided for @settingsLocalUsersValidationPasswordRequired.
  ///
  /// In en, this message translates to:
  /// **'Password is required'**
  String get settingsLocalUsersValidationPasswordRequired;

  /// No description provided for @settingsLocalUsersValidationPasswordTooShort.
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters'**
  String get settingsLocalUsersValidationPasswordTooShort;

  /// No description provided for @settingsLocalUsersValidationPasswordTooLong.
  ///
  /// In en, this message translates to:
  /// **'Password must be no more than 128 characters'**
  String get settingsLocalUsersValidationPasswordTooLong;

  /// No description provided for @settingsLocalUsersValidationPasswordComplexity.
  ///
  /// In en, this message translates to:
  /// **'Password must contain uppercase, lowercase, and digit'**
  String get settingsLocalUsersValidationPasswordComplexity;

  /// No description provided for @settingsLocalUsersOperationFailed.
  ///
  /// In en, this message translates to:
  /// **'Operation failed'**
  String get settingsLocalUsersOperationFailed;

  /// No description provided for @settingsLocalUsersResetPassword.
  ///
  /// In en, this message translates to:
  /// **'Reset password'**
  String get settingsLocalUsersResetPassword;

  /// No description provided for @settingsLocalUsersResetPasswordTitle.
  ///
  /// In en, this message translates to:
  /// **'Reset password: {username}'**
  String settingsLocalUsersResetPasswordTitle(Object username);

  /// No description provided for @settingsLocalUsersFieldNewPassword.
  ///
  /// In en, this message translates to:
  /// **'New password'**
  String get settingsLocalUsersFieldNewPassword;

  /// No description provided for @settingsLocalUsersPasswordResetSuccess.
  ///
  /// In en, this message translates to:
  /// **'Password reset successfully'**
  String get settingsLocalUsersPasswordResetSuccess;

  /// No description provided for @settingsLocalUsersPasswordResetFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to reset password'**
  String get settingsLocalUsersPasswordResetFailed;

  /// No description provided for @settingsLocalUsersDeleteUser.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get settingsLocalUsersDeleteUser;

  /// No description provided for @settingsLocalUsersDeleteUserTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete user: {username}'**
  String settingsLocalUsersDeleteUserTitle(Object username);

  /// No description provided for @settingsLocalUsersDeleteConfirmation.
  ///
  /// In en, this message translates to:
  /// **'This action will permanently delete the user from local user store. This cannot be undone.'**
  String get settingsLocalUsersDeleteConfirmation;

  /// No description provided for @settingsLocalUsersDeleteSuccess.
  ///
  /// In en, this message translates to:
  /// **'User deleted'**
  String get settingsLocalUsersDeleteSuccess;

  /// No description provided for @settingsLocalUsersDeleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to delete user'**
  String get settingsLocalUsersDeleteFailed;

  /// No description provided for @settingsLocalUsersEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get settingsLocalUsersEdit;

  /// No description provided for @settingsLocalUsersCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get settingsLocalUsersCancel;

  /// No description provided for @settingsLocalUsersSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get settingsLocalUsersSave;

  /// No description provided for @settingsLocalUsersConfirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get settingsLocalUsersConfirm;

  /// No description provided for @settingsLocalUsersTableUsername.
  ///
  /// In en, this message translates to:
  /// **'Username'**
  String get settingsLocalUsersTableUsername;

  /// No description provided for @settingsLocalUsersTableDisplayName.
  ///
  /// In en, this message translates to:
  /// **'Display name'**
  String get settingsLocalUsersTableDisplayName;

  /// No description provided for @settingsLocalUsersTableEmail.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get settingsLocalUsersTableEmail;

  /// No description provided for @settingsLocalUsersTableRole.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get settingsLocalUsersTableRole;

  /// No description provided for @settingsLdapEnabled.
  ///
  /// In en, this message translates to:
  /// **'Enable LDAP login'**
  String get settingsLdapEnabled;

  /// No description provided for @settingsLdapEnableHint.
  ///
  /// In en, this message translates to:
  /// **'Test LDAP connection first before enabling.'**
  String get settingsLdapEnableHint;

  /// No description provided for @settingsLdapProtocol.
  ///
  /// In en, this message translates to:
  /// **'Protocol'**
  String get settingsLdapProtocol;

  /// No description provided for @settingsLdapProtocolLdap.
  ///
  /// In en, this message translates to:
  /// **'LDAP'**
  String get settingsLdapProtocolLdap;

  /// No description provided for @settingsLdapProtocolLdaps.
  ///
  /// In en, this message translates to:
  /// **'LDAPS'**
  String get settingsLdapProtocolLdaps;

  /// No description provided for @settingsLdapHost.
  ///
  /// In en, this message translates to:
  /// **'LDAP server (match certificate CN/SAN)'**
  String get settingsLdapHost;

  /// No description provided for @settingsLdapHostPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'ad.example.com or 192.168.x.x'**
  String get settingsLdapHostPlaceholder;

  /// No description provided for @settingsLdapPort.
  ///
  /// In en, this message translates to:
  /// **'Port'**
  String get settingsLdapPort;

  /// No description provided for @settingsLdapPortPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'389'**
  String get settingsLdapPortPlaceholder;

  /// No description provided for @settingsLdapBaseDn.
  ///
  /// In en, this message translates to:
  /// **'User search Base DN'**
  String get settingsLdapBaseDn;

  /// No description provided for @settingsLdapBaseDnPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'OU=Users,DC=example,DC=com'**
  String get settingsLdapBaseDnPlaceholder;

  /// No description provided for @settingsLdapBindDnTemplate.
  ///
  /// In en, this message translates to:
  /// **'Bind DN template'**
  String get settingsLdapBindDnTemplate;

  /// No description provided for @settingsLdapBindDnPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'EXAMPLE\\{username} or {username}@example.com'**
  String settingsLdapBindDnPlaceholder(Object username);

  /// No description provided for @settingsLdapUserFilter.
  ///
  /// In en, this message translates to:
  /// **'User filter'**
  String get settingsLdapUserFilter;

  /// No description provided for @settingsLdapUserFilterPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'(sAMAccountName={username})'**
  String settingsLdapUserFilterPlaceholder(Object username);

  /// No description provided for @settingsLdapAdminGroupEnabled.
  ///
  /// In en, this message translates to:
  /// **'Enable admin group query'**
  String get settingsLdapAdminGroupEnabled;

  /// No description provided for @settingsLdapAdminGroup.
  ///
  /// In en, this message translates to:
  /// **'Admin group name'**
  String get settingsLdapAdminGroup;

  /// No description provided for @settingsLdapAdminGroupPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Owlangs-Admins'**
  String get settingsLdapAdminGroupPlaceholder;

  /// No description provided for @settingsLdapGroupBaseDn.
  ///
  /// In en, this message translates to:
  /// **'Group search Base DN'**
  String get settingsLdapGroupBaseDn;

  /// No description provided for @settingsLdapGroupBaseDnPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'OU=Groups,DC=example,DC=com'**
  String get settingsLdapGroupBaseDnPlaceholder;

  /// No description provided for @settingsLdapTlsVerify.
  ///
  /// In en, this message translates to:
  /// **'Verify TLS certificate'**
  String get settingsLdapTlsVerify;

  /// No description provided for @settingsLdapTlsCacertfile.
  ///
  /// In en, this message translates to:
  /// **'TLS CA certificate file path'**
  String get settingsLdapTlsCacertfile;

  /// No description provided for @settingsLdapTlsCacertfilePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'/path/to/ca.crt'**
  String get settingsLdapTlsCacertfilePlaceholder;

  /// No description provided for @settingsLdapTestConnection.
  ///
  /// In en, this message translates to:
  /// **'Test LDAP connection'**
  String get settingsLdapTestConnection;

  /// No description provided for @settingsLdapSaveConfig.
  ///
  /// In en, this message translates to:
  /// **'Save LDAP config'**
  String get settingsLdapSaveConfig;

  /// No description provided for @settingsLdapTestDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Test LDAP connection'**
  String get settingsLdapTestDialogTitle;

  /// No description provided for @settingsLdapTestUsername.
  ///
  /// In en, this message translates to:
  /// **'Username (without domain)'**
  String get settingsLdapTestUsername;

  /// No description provided for @settingsLdapTestUsernamePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'testuser'**
  String get settingsLdapTestUsernamePlaceholder;

  /// No description provided for @settingsLdapTestPassword.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get settingsLdapTestPassword;

  /// No description provided for @settingsLdapTestPasswordPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'********'**
  String get settingsLdapTestPasswordPlaceholder;

  /// No description provided for @settingsLdapTestStart.
  ///
  /// In en, this message translates to:
  /// **'Start test'**
  String get settingsLdapTestStart;

  /// No description provided for @settingsLdapTestSuccess.
  ///
  /// In en, this message translates to:
  /// **'LDAP connection test succeeded. You can now enable LDAP.'**
  String get settingsLdapTestSuccess;

  /// No description provided for @settingsLdapTestFailed.
  ///
  /// In en, this message translates to:
  /// **'LDAP connection test failed'**
  String get settingsLdapTestFailed;

  /// No description provided for @settingsLdapConfigSaved.
  ///
  /// In en, this message translates to:
  /// **'LDAP configuration saved'**
  String get settingsLdapConfigSaved;

  /// No description provided for @settingsLdapEnableRequireTest.
  ///
  /// In en, this message translates to:
  /// **'Please test LDAP connection first before enabling LDAP.'**
  String get settingsLdapEnableRequireTest;

  /// No description provided for @settingsAdminOnlyDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Admin Only'**
  String get settingsAdminOnlyDialogTitle;

  /// No description provided for @settingsAdminOnlyDialogMessage.
  ///
  /// In en, this message translates to:
  /// **'Settings and Setup Wizard are available only to administrators. Please log in with an admin account to continue.'**
  String get settingsAdminOnlyDialogMessage;

  /// No description provided for @settingsAdminOnlyDialogGoToLogin.
  ///
  /// In en, this message translates to:
  /// **'Go to Login'**
  String get settingsAdminOnlyDialogGoToLogin;

  /// No description provided for @settingsAdminOnlyDialogClose.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get settingsAdminOnlyDialogClose;

  /// No description provided for @aiPlatformOverview.
  ///
  /// In en, this message translates to:
  /// **'Platform Overview'**
  String get aiPlatformOverview;

  /// No description provided for @aiPlatformConfiguredCount.
  ///
  /// In en, this message translates to:
  /// **'Configured {configured}/{total} platforms'**
  String aiPlatformConfiguredCount(Object configured, Object total);

  /// No description provided for @aiPlatformTestApiStatus.
  ///
  /// In en, this message translates to:
  /// **'Test API Status'**
  String get aiPlatformTestApiStatus;

  /// No description provided for @aiPlatformTesting.
  ///
  /// In en, this message translates to:
  /// **'Testing...'**
  String get aiPlatformTesting;

  /// No description provided for @aiPlatformCategoryLanguageModels.
  ///
  /// In en, this message translates to:
  /// **'Language Models'**
  String get aiPlatformCategoryLanguageModels;

  /// No description provided for @aiPlatformCategoryParsingEngines.
  ///
  /// In en, this message translates to:
  /// **'Parsing Engines'**
  String get aiPlatformCategoryParsingEngines;

  /// No description provided for @aiPlatformConfiguredDragReorder.
  ///
  /// In en, this message translates to:
  /// **'Configured {configured}/{total} platforms (drag to reorder)'**
  String aiPlatformConfiguredDragReorder(Object configured, Object total);

  /// No description provided for @aiPlatformNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Not configured'**
  String get aiPlatformNotConfigured;

  /// No description provided for @aiPlatformNotTested.
  ///
  /// In en, this message translates to:
  /// **'Not tested'**
  String get aiPlatformNotTested;

  /// No description provided for @aiPlatformApiAvailable.
  ///
  /// In en, this message translates to:
  /// **'API available'**
  String get aiPlatformApiAvailable;

  /// No description provided for @aiPlatformAvailable.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get aiPlatformAvailable;

  /// No description provided for @aiPlatformUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Unavailable'**
  String get aiPlatformUnavailable;

  /// No description provided for @aiPlatformConfigure.
  ///
  /// In en, this message translates to:
  /// **'Configure'**
  String get aiPlatformConfigure;

  /// No description provided for @aiPlatformConfigureTitle.
  ///
  /// In en, this message translates to:
  /// **'Configure {name}'**
  String aiPlatformConfigureTitle(Object name);

  /// No description provided for @aiPlatformBasicInformation.
  ///
  /// In en, this message translates to:
  /// **'Basic Information'**
  String get aiPlatformBasicInformation;

  /// No description provided for @aiPlatformPlatformName.
  ///
  /// In en, this message translates to:
  /// **'Platform Name'**
  String get aiPlatformPlatformName;

  /// No description provided for @aiPlatformPlatformNameHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., Doubao (DeepSeek / Volcano Ark)'**
  String get aiPlatformPlatformNameHint;

  /// No description provided for @aiPlatformApiUrl.
  ///
  /// In en, this message translates to:
  /// **'API URL'**
  String get aiPlatformApiUrl;

  /// No description provided for @aiPlatformApiUrlHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., https://ark.cn-beijing.volces.com/api/v3'**
  String get aiPlatformApiUrlHint;

  /// No description provided for @aiPlatformMaxTokens.
  ///
  /// In en, this message translates to:
  /// **'Max Tokens'**
  String get aiPlatformMaxTokens;

  /// No description provided for @aiPlatformMaxTokensHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 4096'**
  String get aiPlatformMaxTokensHint;

  /// No description provided for @aiPlatformChunkSize.
  ///
  /// In en, this message translates to:
  /// **'Chunk Size'**
  String get aiPlatformChunkSize;

  /// No description provided for @aiPlatformChunkSizeHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 3000'**
  String get aiPlatformChunkSizeHint;

  /// No description provided for @aiPlatformConcurrent.
  ///
  /// In en, this message translates to:
  /// **'Concurrent Requests'**
  String get aiPlatformConcurrent;

  /// No description provided for @aiPlatformConcurrentHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., 5'**
  String get aiPlatformConcurrentHint;

  /// No description provided for @aiPlatformModel.
  ///
  /// In en, this message translates to:
  /// **'Model'**
  String get aiPlatformModel;

  /// No description provided for @aiPlatformModelHint.
  ///
  /// In en, this message translates to:
  /// **'e.g., deepseek-v3 / llama3.1-70b'**
  String get aiPlatformModelHint;

  /// No description provided for @aiPlatformApiKey.
  ///
  /// In en, this message translates to:
  /// **'API Key'**
  String get aiPlatformApiKey;

  /// No description provided for @aiPlatformApiConfiguration.
  ///
  /// In en, this message translates to:
  /// **'API Configuration'**
  String get aiPlatformApiConfiguration;

  /// No description provided for @aiPlatformGetApiKey.
  ///
  /// In en, this message translates to:
  /// **'Get API Key'**
  String get aiPlatformGetApiKey;

  /// No description provided for @aiPlatformCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get aiPlatformCancel;

  /// No description provided for @aiPlatformTestConnection.
  ///
  /// In en, this message translates to:
  /// **'Test Connection'**
  String get aiPlatformTestConnection;

  /// No description provided for @aiPlatformTestConnectionHint.
  ///
  /// In en, this message translates to:
  /// **'After updating configuration, please click \"Test Connection\" below to verify the platform is available.'**
  String get aiPlatformTestConnectionHint;

  /// No description provided for @setupWizardConfigureApiKeyAndTest.
  ///
  /// In en, this message translates to:
  /// **'Connection unavailable. Please configure API Key and click \"Test Connection\" to verify.'**
  String get setupWizardConfigureApiKeyAndTest;

  /// No description provided for @setupWizardSaveAndExit.
  ///
  /// In en, this message translates to:
  /// **'Save and exit'**
  String get setupWizardSaveAndExit;

  /// No description provided for @setupWizardTitle.
  ///
  /// In en, this message translates to:
  /// **'Setup Wizard'**
  String get setupWizardTitle;

  /// No description provided for @setupWizardStepWelcome.
  ///
  /// In en, this message translates to:
  /// **'Welcome'**
  String get setupWizardStepWelcome;

  /// No description provided for @setupWizardStepMineru.
  ///
  /// In en, this message translates to:
  /// **'PDF / MinerU'**
  String get setupWizardStepMineru;

  /// No description provided for @setupWizardWelcomeIntro.
  ///
  /// In en, this message translates to:
  /// **'This wizard will help you complete two key configurations:'**
  String get setupWizardWelcomeIntro;

  /// No description provided for @setupWizardWelcomeBody.
  ///
  /// In en, this message translates to:
  /// **'1. Select and configure your primary LLM platform.\n2. If you need to translate PDF/PNG etc., configure the MinerU parsing engine (optional).\n\nNote: After configuring, use \"Test Connection\" to verify.'**
  String get setupWizardWelcomeBody;

  /// No description provided for @setupWizardUiLanguageLabel.
  ///
  /// In en, this message translates to:
  /// **'UI Language'**
  String get setupWizardUiLanguageLabel;

  /// No description provided for @setupWizardMineruDescription.
  ///
  /// In en, this message translates to:
  /// **'MinerU handles layout parsing and segmentation for PDF / images.\nEnter MinerU API Key and URL below, then click \"Test Connection\" to verify.'**
  String get setupWizardMineruDescription;

  /// No description provided for @setupWizardMineruConfigTitle.
  ///
  /// In en, this message translates to:
  /// **'MinerU (parsing engine)'**
  String get setupWizardMineruConfigTitle;

  /// No description provided for @setupWizardSelectMineruPlatform.
  ///
  /// In en, this message translates to:
  /// **'Select MinerU Platform'**
  String get setupWizardSelectMineruPlatform;

  /// No description provided for @setupWizardMineruCloudOption.
  ///
  /// In en, this message translates to:
  /// **'MinerU (Cloud) - Official cloud service'**
  String get setupWizardMineruCloudOption;

  /// No description provided for @setupWizardMineruLocalOption.
  ///
  /// In en, this message translates to:
  /// **'MinerU (Local) - Self-hosted deployment'**
  String get setupWizardMineruLocalOption;

  /// No description provided for @setupWizardSelectLlmPlatform.
  ///
  /// In en, this message translates to:
  /// **'Select LLM platform'**
  String get setupWizardSelectLlmPlatform;

  /// No description provided for @setupWizardNoLlmPlatforms.
  ///
  /// In en, this message translates to:
  /// **'No LLM platforms in AI Platform Settings. Add a platform in Settings first.'**
  String get setupWizardNoLlmPlatforms;

  /// No description provided for @setupWizardMineruSaved.
  ///
  /// In en, this message translates to:
  /// **'MinerU configuration saved'**
  String get setupWizardMineruSaved;

  /// No description provided for @setupWizardPrevStep.
  ///
  /// In en, this message translates to:
  /// **'Previous'**
  String get setupWizardPrevStep;

  /// No description provided for @setupWizardNextStep.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get setupWizardNextStep;

  /// No description provided for @aiPlatformSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get aiPlatformSave;

  /// No description provided for @aiPlatformList.
  ///
  /// In en, this message translates to:
  /// **'List'**
  String get aiPlatformList;

  /// No description provided for @aiPlatformTemperature.
  ///
  /// In en, this message translates to:
  /// **'Temperature'**
  String get aiPlatformTemperature;

  /// No description provided for @aiPlatformThinkingMode.
  ///
  /// In en, this message translates to:
  /// **'Thinking Mode'**
  String get aiPlatformThinkingMode;

  /// No description provided for @aiPlatformThinkingDisable.
  ///
  /// In en, this message translates to:
  /// **'Disable (Recommended)'**
  String get aiPlatformThinkingDisable;

  /// No description provided for @aiPlatformThinkingEnable.
  ///
  /// In en, this message translates to:
  /// **'Enable'**
  String get aiPlatformThinkingEnable;

  /// No description provided for @aiPlatformThinkingDefault.
  ///
  /// In en, this message translates to:
  /// **'Default'**
  String get aiPlatformThinkingDefault;

  /// No description provided for @aiPlatformThinkingHint.
  ///
  /// In en, this message translates to:
  /// **'Enable AI reasoning process for better translation quality'**
  String get aiPlatformThinkingHint;

  /// No description provided for @aiPlatformThinkingModeSupported.
  ///
  /// In en, this message translates to:
  /// **'Support Thinking Mode'**
  String get aiPlatformThinkingModeSupported;

  /// No description provided for @aiPlatformThinkingModeSupportedHint.
  ///
  /// In en, this message translates to:
  /// **'Enable this if the platform supports thinking mode (e.g., Ollama with Qwen3)'**
  String get aiPlatformThinkingModeSupportedHint;

  /// No description provided for @aiPlatformSegmentLimitLabel.
  ///
  /// In en, this message translates to:
  /// **'Segment Limit'**
  String get aiPlatformSegmentLimitLabel;

  /// No description provided for @aiPlatformSegmentLimitHint.
  ///
  /// In en, this message translates to:
  /// **'Max segments per translation batch. Limits are applied together with chunk size. 0 = unlimited (cloud), 10 = recommended for local LLMs'**
  String get aiPlatformSegmentLimitHint;

  /// No description provided for @aiPlatformSegmentLimitUnlimited.
  ///
  /// In en, this message translates to:
  /// **'Unlimited'**
  String get aiPlatformSegmentLimitUnlimited;

  /// No description provided for @aiPlatformPleaseEnterApiKeyFirst.
  ///
  /// In en, this message translates to:
  /// **'Please enter an API key first'**
  String get aiPlatformPleaseEnterApiKeyFirst;

  /// No description provided for @aiPlatformPleaseEnterApiUrlFirst.
  ///
  /// In en, this message translates to:
  /// **'Please enter API URL first'**
  String get aiPlatformPleaseEnterApiUrlFirst;

  /// No description provided for @aiPlatformHasApiKey.
  ///
  /// In en, this message translates to:
  /// **'Requires API Key'**
  String get aiPlatformHasApiKey;

  /// No description provided for @aiPlatformHasApiKeyHint.
  ///
  /// In en, this message translates to:
  /// **'Uncheck for local deployments without API authentication'**
  String get aiPlatformHasApiKeyHint;

  /// No description provided for @aiPlatformApiKeyOptionalHint.
  ///
  /// In en, this message translates to:
  /// **'Leave empty if not required'**
  String get aiPlatformApiKeyOptionalHint;

  /// No description provided for @optional.
  ///
  /// In en, this message translates to:
  /// **'optional'**
  String get optional;

  /// No description provided for @aiPlatformConnectionTestSucceeded.
  ///
  /// In en, this message translates to:
  /// **'Connection test succeeded'**
  String get aiPlatformConnectionTestSucceeded;

  /// No description provided for @mineruConnectionSuccessWithVersion.
  ///
  /// In en, this message translates to:
  /// **'Connection test succeeded. MinerU version: {version}'**
  String mineruConnectionSuccessWithVersion(String version);

  /// No description provided for @mineruConnectionSuccessWithApiVersion.
  ///
  /// In en, this message translates to:
  /// **'Connection test succeeded. MinerU API {version}'**
  String mineruConnectionSuccessWithApiVersion(String version);

  /// No description provided for @mineruConnectionSuccessWithModelVersion.
  ///
  /// In en, this message translates to:
  /// **'Connection test succeeded. MinerU engine: {modelVersion}'**
  String mineruConnectionSuccessWithModelVersion(String modelVersion);

  /// No description provided for @mineruConnectionSuccessCloudWithApi.
  ///
  /// In en, this message translates to:
  /// **'Connection test succeeded. Cloud MinerU (API {apiVersion}; server version is not exposed by the cloud API)'**
  String mineruConnectionSuccessCloudWithApi(String apiVersion);

  /// No description provided for @aiPlatformConnectionTestFailed.
  ///
  /// In en, this message translates to:
  /// **'Connection test failed: {message}'**
  String aiPlatformConnectionTestFailed(Object message);

  /// No description provided for @aiPlatformNoModelsFound.
  ///
  /// In en, this message translates to:
  /// **'No models found'**
  String get aiPlatformNoModelsFound;

  /// No description provided for @aiPlatformFailedToLoadModels.
  ///
  /// In en, this message translates to:
  /// **'Failed to load models'**
  String get aiPlatformFailedToLoadModels;

  /// No description provided for @aiPlatformErrorLoadingModels.
  ///
  /// In en, this message translates to:
  /// **'Error loading models: {error}'**
  String aiPlatformErrorLoadingModels(Object error);

  /// No description provided for @aiPlatformSelectModel.
  ///
  /// In en, this message translates to:
  /// **'Select Model'**
  String get aiPlatformSelectModel;

  /// No description provided for @aiPlatformNoModelsAvailable.
  ///
  /// In en, this message translates to:
  /// **'No models available'**
  String get aiPlatformNoModelsAvailable;

  /// No description provided for @aiPlatformMineruSettings.
  ///
  /// In en, this message translates to:
  /// **'MinerU Settings'**
  String get aiPlatformMineruSettings;

  /// No description provided for @aiPlatformEnterMineruApiKey.
  ///
  /// In en, this message translates to:
  /// **'Enter MinerU API Key'**
  String get aiPlatformEnterMineruApiKey;

  /// No description provided for @aiPlatformGetMineruApiKey.
  ///
  /// In en, this message translates to:
  /// **'Get MinerU API Key'**
  String get aiPlatformGetMineruApiKey;

  /// No description provided for @aiPlatformModelVersion.
  ///
  /// In en, this message translates to:
  /// **'Model Version'**
  String get aiPlatformModelVersion;

  /// No description provided for @aiPlatformModelVersionHint.
  ///
  /// In en, this message translates to:
  /// **'hybrid-auto-engine'**
  String get aiPlatformModelVersionHint;

  /// No description provided for @aiPlatformTimeout.
  ///
  /// In en, this message translates to:
  /// **'Read Timeout (seconds)'**
  String get aiPlatformTimeout;

  /// No description provided for @aiPlatformTimeoutHint.
  ///
  /// In en, this message translates to:
  /// **'200 (cloud) or 300 (local). Max wait time for LLM response.'**
  String get aiPlatformTimeoutHint;

  /// No description provided for @aiPlatformWriteTimeout.
  ///
  /// In en, this message translates to:
  /// **'Write Timeout (seconds)'**
  String get aiPlatformWriteTimeout;

  /// No description provided for @aiPlatformWriteTimeoutHint.
  ///
  /// In en, this message translates to:
  /// **'300 (default). Max wait time for sending data to LLM.'**
  String get aiPlatformWriteTimeoutHint;

  /// No description provided for @aiPlatformTestConnectTimeout.
  ///
  /// In en, this message translates to:
  /// **'Connect Test Timeout (seconds)'**
  String get aiPlatformTestConnectTimeout;

  /// No description provided for @aiPlatformTestConnectTimeoutHint.
  ///
  /// In en, this message translates to:
  /// **'30 (default). Max wait time for connectivity test before starting translation.'**
  String get aiPlatformTestConnectTimeoutHint;

  /// No description provided for @aiPlatformTestRequestTimeout.
  ///
  /// In en, this message translates to:
  /// **'Test Request Timeout (seconds)'**
  String get aiPlatformTestRequestTimeout;

  /// No description provided for @aiPlatformTestRequestTimeoutHint.
  ///
  /// In en, this message translates to:
  /// **'10 (default). Max wait for each probe request during connectivity test.'**
  String get aiPlatformTestRequestTimeoutHint;

  /// No description provided for @aiPlatformMineruApiUrlHint.
  ///
  /// In en, this message translates to:
  /// **'https://mineru.net/api/v4'**
  String get aiPlatformMineruApiUrlHint;

  /// No description provided for @aiPlatformOcrSettings.
  ///
  /// In en, this message translates to:
  /// **'OCR Settings'**
  String get aiPlatformOcrSettings;

  /// No description provided for @aiPlatformFormulaOcr.
  ///
  /// In en, this message translates to:
  /// **'Formula OCR'**
  String get aiPlatformFormulaOcr;

  /// No description provided for @aiPlatformFormulaOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable OCR for mathematical formulas'**
  String get aiPlatformFormulaOcrSubtitle;

  /// No description provided for @aiPlatformTableOcr.
  ///
  /// In en, this message translates to:
  /// **'Table OCR'**
  String get aiPlatformTableOcr;

  /// No description provided for @aiPlatformTableOcrSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable OCR for tables'**
  String get aiPlatformTableOcrSubtitle;

  /// No description provided for @settingsFontEditSizeTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit Font Size'**
  String get settingsFontEditSizeTitle;

  /// No description provided for @settingsFontEditSizeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Font size when editing translated segments'**
  String get settingsFontEditSizeSubtitle;

  /// No description provided for @settingsTranslationTitle.
  ///
  /// In en, this message translates to:
  /// **'Translation Settings'**
  String get settingsTranslationTitle;

  /// No description provided for @settingsTranslationNotice.
  ///
  /// In en, this message translates to:
  /// **'These settings will apply to new translation tasks only.'**
  String get settingsTranslationNotice;

  /// No description provided for @settingsTargetLanguageTitle.
  ///
  /// In en, this message translates to:
  /// **'Default Target Language'**
  String get settingsTargetLanguageTitle;

  /// No description provided for @settingsTargetLanguageNotice.
  ///
  /// In en, this message translates to:
  /// **'Sets the default target language for new translation tasks. You can still change it per task in Quick Settings.'**
  String get settingsTargetLanguageNotice;

  /// No description provided for @settingsTranslationParamsTitle.
  ///
  /// In en, this message translates to:
  /// **'Translation Parameters'**
  String get settingsTranslationParamsTitle;

  /// No description provided for @settingsTranslationConcurrentTitle.
  ///
  /// In en, this message translates to:
  /// **'Concurrent Requests'**
  String get settingsTranslationConcurrentTitle;

  /// No description provided for @settingsTranslationConcurrentHint.
  ///
  /// In en, this message translates to:
  /// **'Recommended: 3 (adjust 1–8 based on model and quota)'**
  String get settingsTranslationConcurrentHint;

  /// No description provided for @settingsTranslationChunkRetryTitle.
  ///
  /// In en, this message translates to:
  /// **'Chunk retry (per request)'**
  String get settingsTranslationChunkRetryTitle;

  /// No description provided for @settingsTranslationChunkRetryHint.
  ///
  /// In en, this message translates to:
  /// **'Recommended: 3–5 (retries when a translation chunk or API call fails)'**
  String get settingsTranslationChunkRetryHint;

  /// No description provided for @settingsTranslationSegmentAutoRetryTitle.
  ///
  /// In en, this message translates to:
  /// **'Queue mode: failed-segment auto rounds'**
  String get settingsTranslationSegmentAutoRetryTitle;

  /// No description provided for @settingsTranslationSegmentAutoRetryHint.
  ///
  /// In en, this message translates to:
  /// **'Recommended: 3 (1–10 batch retranslate rounds after main translation; queued mode only)'**
  String get settingsTranslationSegmentAutoRetryHint;

  /// No description provided for @settingsTranslationChunkSizeTitle.
  ///
  /// In en, this message translates to:
  /// **'Chunk Size (tokens)'**
  String get settingsTranslationChunkSizeTitle;

  /// No description provided for @settingsTranslationChunkSizeHint.
  ///
  /// In en, this message translates to:
  /// **'Recommended: 3000 tokens per request (adjust by model context size)'**
  String get settingsTranslationChunkSizeHint;

  /// No description provided for @settingsExclusionTitle.
  ///
  /// In en, this message translates to:
  /// **'Default Exclusion Rules'**
  String get settingsExclusionTitle;

  /// No description provided for @settingsExclusionNotice.
  ///
  /// In en, this message translates to:
  /// **'Toggle ON = auto-exclude during Extract; Toggle OFF = detect only (user decides per segment).'**
  String get settingsExclusionNotice;

  /// No description provided for @settingsExclusionImageTitle.
  ///
  /// In en, this message translates to:
  /// **'Image'**
  String get settingsExclusionImageTitle;

  /// No description provided for @settingsExclusionImageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Image placeholders and pure-image content'**
  String get settingsExclusionImageSubtitle;

  /// No description provided for @settingsExclusionFormulaTitle.
  ///
  /// In en, this message translates to:
  /// **'Formula'**
  String get settingsExclusionFormulaTitle;

  /// No description provided for @settingsExclusionFormulaSubtitle.
  ///
  /// In en, this message translates to:
  /// **'LaTeX / MathML formulas'**
  String get settingsExclusionFormulaSubtitle;

  /// No description provided for @settingsExclusionReferenceTitle.
  ///
  /// In en, this message translates to:
  /// **'Reference'**
  String get settingsExclusionReferenceTitle;

  /// No description provided for @settingsExclusionReferenceSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Citations and bibliographic references'**
  String get settingsExclusionReferenceSubtitle;

  /// No description provided for @settingsExclusionIdentifierTitle.
  ///
  /// In en, this message translates to:
  /// **'Identifier'**
  String get settingsExclusionIdentifierTitle;

  /// No description provided for @settingsExclusionIdentifierSubtitle.
  ///
  /// In en, this message translates to:
  /// **'URLs, emails, serial numbers, code snippets'**
  String get settingsExclusionIdentifierSubtitle;

  /// No description provided for @settingsExclusionStructuralTitle.
  ///
  /// In en, this message translates to:
  /// **'Structural'**
  String get settingsExclusionStructuralTitle;

  /// No description provided for @settingsExclusionStructuralSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Headers, footers, footnotes, page numbers'**
  String get settingsExclusionStructuralSubtitle;

  /// No description provided for @settingsExclusionTableTitle.
  ///
  /// In en, this message translates to:
  /// **'Table'**
  String get settingsExclusionTableTitle;

  /// No description provided for @settingsExclusionTableSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Table content (markdown / PDF tables)'**
  String get settingsExclusionTableSubtitle;

  /// No description provided for @settingsExclusionChartTitle.
  ///
  /// In en, this message translates to:
  /// **'Chart'**
  String get settingsExclusionChartTitle;

  /// No description provided for @settingsExclusionChartSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Chart content (Figure, chart blocks)'**
  String get settingsExclusionChartSubtitle;

  /// No description provided for @settingsExclusionLanguageMatchTitle.
  ///
  /// In en, this message translates to:
  /// **'Language Match'**
  String get settingsExclusionLanguageMatchTitle;

  /// No description provided for @settingsExclusionLanguageMatchSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Source language matches target language'**
  String get settingsExclusionLanguageMatchSubtitle;

  /// No description provided for @settingsTranslateOutputSuffixTitle.
  ///
  /// In en, this message translates to:
  /// **'Translation Output Suffix'**
  String get settingsTranslateOutputSuffixTitle;

  /// No description provided for @settingsTranslateOutputSuffixHint.
  ///
  /// In en, this message translates to:
  /// **'Appended to translated filenames (leave empty for no suffix)'**
  String get settingsTranslateOutputSuffixHint;

  /// No description provided for @settingsConvertOutputSuffixTitle.
  ///
  /// In en, this message translates to:
  /// **'Conversion Output Suffix'**
  String get settingsConvertOutputSuffixTitle;

  /// No description provided for @settingsConvertOutputSuffixHint.
  ///
  /// In en, this message translates to:
  /// **'Appended to converted filenames (leave empty for no suffix)'**
  String get settingsConvertOutputSuffixHint;

  /// No description provided for @settingsLanguageDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get settingsLanguageDialogTitle;

  /// No description provided for @settingsUnitPt.
  ///
  /// In en, this message translates to:
  /// **'pt'**
  String get settingsUnitPt;

  /// No description provided for @glossaryGeneratedTabTitle.
  ///
  /// In en, this message translates to:
  /// **'Generated Glossary'**
  String get glossaryGeneratedTabTitle;

  /// No description provided for @glossaryErrorRefresh.
  ///
  /// In en, this message translates to:
  /// **'Failed to refresh glossaries: {error}'**
  String glossaryErrorRefresh(Object error);

  /// No description provided for @glossaryWarningNoGenerated.
  ///
  /// In en, this message translates to:
  /// **'No generated glossary available'**
  String get glossaryWarningNoGenerated;

  /// No description provided for @glossaryPanelView.
  ///
  /// In en, this message translates to:
  /// **'View'**
  String get glossaryPanelView;

  /// No description provided for @glossaryPanelAddToPersonal.
  ///
  /// In en, this message translates to:
  /// **'Add to Personal'**
  String get glossaryPanelAddToPersonal;

  /// No description provided for @glossaryPanelNoGlobalGlossaries.
  ///
  /// In en, this message translates to:
  /// **'No global glossaries available'**
  String get glossaryPanelNoGlobalGlossaries;

  /// No description provided for @glossaryPanelSelectTitle.
  ///
  /// In en, this message translates to:
  /// **'Select Glossary'**
  String get glossaryPanelSelectTitle;

  /// No description provided for @glossaryPanelSelectHint.
  ///
  /// In en, this message translates to:
  /// **'Select glossary...'**
  String get glossaryPanelSelectHint;

  /// No description provided for @glossaryPanelSelected.
  ///
  /// In en, this message translates to:
  /// **'Selected: {name}'**
  String glossaryPanelSelected(Object name);

  /// No description provided for @glossaryPanelSelectConfirm.
  ///
  /// In en, this message translates to:
  /// **'Select'**
  String get glossaryPanelSelectConfirm;

  /// No description provided for @glossaryPanelMergeToCurrent.
  ///
  /// In en, this message translates to:
  /// **'Merge to Current Glossary'**
  String get glossaryPanelMergeToCurrent;

  /// No description provided for @glossaryPanelLoadedGlossary.
  ///
  /// In en, this message translates to:
  /// **'Loaded glossary: {name}'**
  String glossaryPanelLoadedGlossary(Object name);

  /// No description provided for @glossaryPanelLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load glossary: {error}'**
  String glossaryPanelLoadFailed(Object error);

  /// No description provided for @glossaryPanelMergedIntoCurrent.
  ///
  /// In en, this message translates to:
  /// **'Merged \"{glossaryName}\" into current glossary'**
  String glossaryPanelMergedIntoCurrent(Object glossaryName);

  /// No description provided for @glossaryPanelMergeFailed.
  ///
  /// In en, this message translates to:
  /// **'Merge failed: {error}'**
  String glossaryPanelMergeFailed(Object error);

  /// No description provided for @glossaryPanelEnterName.
  ///
  /// In en, this message translates to:
  /// **'Enter a name for the glossary'**
  String get glossaryPanelEnterName;

  /// No description provided for @glossaryPanelSaveDialogHint.
  ///
  /// In en, this message translates to:
  /// **'Enter a name for the glossary or select an existing one to replace:'**
  String get glossaryPanelSaveDialogHint;

  /// No description provided for @glossaryPanelReplaceTitle.
  ///
  /// In en, this message translates to:
  /// **'Replace Global Glossary'**
  String get glossaryPanelReplaceTitle;

  /// No description provided for @glossaryPanelReplaceBody.
  ///
  /// In en, this message translates to:
  /// **'This will replace all entries in \"{glossaryName}\" with current glossary entries. Continue?'**
  String glossaryPanelReplaceBody(Object glossaryName);

  /// No description provided for @glossaryPanelReplaceConfirm.
  ///
  /// In en, this message translates to:
  /// **'Replace'**
  String get glossaryPanelReplaceConfirm;

  /// No description provided for @glossaryPanelReplacedGlobal.
  ///
  /// In en, this message translates to:
  /// **'Replaced global glossary: {name}'**
  String glossaryPanelReplacedGlobal(Object name);

  /// No description provided for @glossaryPanelSavedAsNewGlobal.
  ///
  /// In en, this message translates to:
  /// **'Saved as new global glossary: {name}'**
  String glossaryPanelSavedAsNewGlobal(Object name);

  /// No description provided for @glossaryPanelSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'Save failed: {error}'**
  String glossaryPanelSaveFailed(Object error);

  /// No description provided for @glossaryPanelDetect.
  ///
  /// In en, this message translates to:
  /// **'Detect Glossary'**
  String get glossaryPanelDetect;

  /// No description provided for @glossaryPanelEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get glossaryPanelEdit;

  /// No description provided for @glossaryPanelCreate.
  ///
  /// In en, this message translates to:
  /// **'Create Glossary'**
  String get glossaryPanelCreate;

  /// No description provided for @glossaryPanelSelect.
  ///
  /// In en, this message translates to:
  /// **'Select'**
  String get glossaryPanelSelect;

  /// No description provided for @glossaryPanelImport.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get glossaryPanelImport;

  /// No description provided for @glossaryPanelExport.
  ///
  /// In en, this message translates to:
  /// **'Export'**
  String get glossaryPanelExport;

  /// No description provided for @glossaryPanelSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get glossaryPanelSave;

  /// No description provided for @glossaryPanelAddEntry.
  ///
  /// In en, this message translates to:
  /// **'Add Entry'**
  String get glossaryPanelAddEntry;

  /// No description provided for @glossaryPanelClear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get glossaryPanelClear;

  /// No description provided for @glossaryPanelApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get glossaryPanelApply;

  /// No description provided for @glossaryPanelColumnSource.
  ///
  /// In en, this message translates to:
  /// **'Source'**
  String get glossaryPanelColumnSource;

  /// No description provided for @glossaryPanelColumnTarget.
  ///
  /// In en, this message translates to:
  /// **'Target'**
  String get glossaryPanelColumnTarget;

  /// No description provided for @glossaryPanelColumnActions.
  ///
  /// In en, this message translates to:
  /// **'Actions'**
  String get glossaryPanelColumnActions;

  /// No description provided for @translationStepsUploadTooltipReady.
  ///
  /// In en, this message translates to:
  /// **'File selected'**
  String get translationStepsUploadTooltipReady;

  /// No description provided for @translationStepsUploadTooltipNotReady.
  ///
  /// In en, this message translates to:
  /// **'Select a file to start'**
  String get translationStepsUploadTooltipNotReady;

  /// No description provided for @translationStepsExtractTooltipReady.
  ///
  /// In en, this message translates to:
  /// **'View extracted source'**
  String get translationStepsExtractTooltipReady;

  /// No description provided for @translationStepsExtractTooltipNotReady.
  ///
  /// In en, this message translates to:
  /// **'Extract will be ready after import'**
  String get translationStepsExtractTooltipNotReady;

  /// No description provided for @translationStepsGlossaryTooltipSkipped.
  ///
  /// In en, this message translates to:
  /// **'Glossary skipped'**
  String get translationStepsGlossaryTooltipSkipped;

  /// No description provided for @translationStepsGlossaryTooltipEnabled.
  ///
  /// In en, this message translates to:
  /// **'Glossary enabled'**
  String get translationStepsGlossaryTooltipEnabled;

  /// No description provided for @translationStepsGlossaryTooltipDisabled.
  ///
  /// In en, this message translates to:
  /// **'Generate or select a glossary to enable'**
  String get translationStepsGlossaryTooltipDisabled;

  /// No description provided for @translationStepsTranslateTooltipReady.
  ///
  /// In en, this message translates to:
  /// **'Translation completed'**
  String get translationStepsTranslateTooltipReady;

  /// No description provided for @translationStepsTranslateTooltipNotReady.
  ///
  /// In en, this message translates to:
  /// **'Run translation to enable'**
  String get translationStepsTranslateTooltipNotReady;

  /// No description provided for @glossaryDialogAddTitle.
  ///
  /// In en, this message translates to:
  /// **'Add to Personal Glossary'**
  String get glossaryDialogAddTitle;

  /// No description provided for @glossaryDialogAddBody.
  ///
  /// In en, this message translates to:
  /// **'This will add {termCount} terms to your personal glossary.'**
  String glossaryDialogAddBody(Object termCount);

  /// No description provided for @glossaryDialogAddPreviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Preview (first 5 terms):'**
  String get glossaryDialogAddPreviewTitle;

  /// No description provided for @glossaryDialogAddMoreTerms.
  ///
  /// In en, this message translates to:
  /// **'... and {remainingCount} more terms'**
  String glossaryDialogAddMoreTerms(Object remainingCount);

  /// No description provided for @glossaryDialogMergeStrategyTitle.
  ///
  /// In en, this message translates to:
  /// **'Merge Strategy:'**
  String get glossaryDialogMergeStrategyTitle;

  /// No description provided for @glossaryDialogMergeUpdateTitle.
  ///
  /// In en, this message translates to:
  /// **'Update (Recommended)'**
  String get glossaryDialogMergeUpdateTitle;

  /// No description provided for @glossaryDialogMergeUpdateSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Update existing terms, add new ones'**
  String get glossaryDialogMergeUpdateSubtitle;

  /// No description provided for @glossaryDialogMergeAppendTitle.
  ///
  /// In en, this message translates to:
  /// **'Append'**
  String get glossaryDialogMergeAppendTitle;

  /// No description provided for @glossaryDialogMergeAppendSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Only add new terms, skip existing ones'**
  String get glossaryDialogMergeAppendSubtitle;

  /// No description provided for @glossaryDialogMergeReplaceTitle.
  ///
  /// In en, this message translates to:
  /// **'Replace'**
  String get glossaryDialogMergeReplaceTitle;

  /// No description provided for @glossaryDialogMergeReplaceSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Replace entire glossary with these terms'**
  String get glossaryDialogMergeReplaceSubtitle;

  /// No description provided for @glossaryDialogCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get glossaryDialogCancel;

  /// No description provided for @glossaryDialogReviewAndAdd.
  ///
  /// In en, this message translates to:
  /// **'Review & Add'**
  String get glossaryDialogReviewAndAdd;

  /// No description provided for @glossaryConfirmAddTitle.
  ///
  /// In en, this message translates to:
  /// **'Confirm Add to Personal Glossary'**
  String get glossaryConfirmAddTitle;

  /// No description provided for @glossaryConfirmAddBody.
  ///
  /// In en, this message translates to:
  /// **'Add {termCount} terms to your personal glossary?'**
  String glossaryConfirmAddBody(Object termCount);

  /// No description provided for @glossaryConfirmAddStrategyUpdate.
  ///
  /// In en, this message translates to:
  /// **'Strategy: Update existing terms, add new ones'**
  String get glossaryConfirmAddStrategyUpdate;

  /// No description provided for @glossaryConfirmAddStrategyAppend.
  ///
  /// In en, this message translates to:
  /// **'Strategy: Only add new terms, skip existing ones'**
  String get glossaryConfirmAddStrategyAppend;

  /// No description provided for @glossaryConfirmAddStrategyReplace.
  ///
  /// In en, this message translates to:
  /// **'Strategy: Replace entire glossary'**
  String get glossaryConfirmAddStrategyReplace;

  /// No description provided for @glossaryConfirmAddAutoCreateHint.
  ///
  /// In en, this message translates to:
  /// **'If your personal glossary doesn\'t exist, it will be created automatically.'**
  String get glossaryConfirmAddAutoCreateHint;

  /// No description provided for @glossaryConfirmAddButton.
  ///
  /// In en, this message translates to:
  /// **'Add'**
  String get glossaryConfirmAddButton;

  /// No description provided for @glossaryExportDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Save Glossary'**
  String get glossaryExportDialogTitle;

  /// No description provided for @glossaryExportSuccess.
  ///
  /// In en, this message translates to:
  /// **'Glossary exported: {filename}'**
  String glossaryExportSuccess(Object filename);

  /// No description provided for @glossaryExportFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to export glossary: {error}'**
  String glossaryExportFailed(Object error);

  /// No description provided for @glossaryCsvValidationFailed.
  ///
  /// In en, this message translates to:
  /// **'CSV file validation failed:\n\n{errors}'**
  String glossaryCsvValidationFailed(Object errors);

  /// No description provided for @glossaryCsvNoValidEntries.
  ///
  /// In en, this message translates to:
  /// **'CSV file contains no valid entries.'**
  String get glossaryCsvNoValidEntries;

  /// No description provided for @glossaryImportDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Import Glossary'**
  String get glossaryImportDialogTitle;

  /// No description provided for @glossaryImportDialogBodyEmpty.
  ///
  /// In en, this message translates to:
  /// **'Found {count} entries in the file.\n\nThe current glossary is empty. Imported entries will be added.'**
  String glossaryImportDialogBodyEmpty(Object count);

  /// No description provided for @glossaryImportDialogBody.
  ///
  /// In en, this message translates to:
  /// **'Found {count} entries in the file.\n\nChoose how to import:'**
  String glossaryImportDialogBody(Object count);

  /// No description provided for @glossaryImportButtonImport.
  ///
  /// In en, this message translates to:
  /// **'Import'**
  String get glossaryImportButtonImport;

  /// No description provided for @glossaryImportButtonReplace.
  ///
  /// In en, this message translates to:
  /// **'Replace'**
  String get glossaryImportButtonReplace;

  /// No description provided for @glossaryImportButtonMerge.
  ///
  /// In en, this message translates to:
  /// **'Merge'**
  String get glossaryImportButtonMerge;

  /// No description provided for @glossaryImportResult.
  ///
  /// In en, this message translates to:
  /// **'Imported {count} entries ({mode})'**
  String glossaryImportResult(Object count, Object mode);

  /// No description provided for @glossaryErrorImport.
  ///
  /// In en, this message translates to:
  /// **'Failed to import glossary: {error}'**
  String glossaryErrorImport(Object error);

  /// No description provided for @glossaryErrorFileData.
  ///
  /// In en, this message translates to:
  /// **'Failed to read file data. Please try again.'**
  String get glossaryErrorFileData;

  /// No description provided for @glossaryErrorFilePath.
  ///
  /// In en, this message translates to:
  /// **'File path is not available. Please try again.'**
  String get glossaryErrorFilePath;

  /// No description provided for @glossaryErrorOnlyCsv.
  ///
  /// In en, this message translates to:
  /// **'Only CSV and TBX files are supported for glossary import.'**
  String get glossaryErrorOnlyCsv;

  /// No description provided for @glossaryExportFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Export format'**
  String get glossaryExportFormatLabel;

  /// No description provided for @glossaryExportFormatTbxSubtitle.
  ///
  /// In en, this message translates to:
  /// **'TermBase eXchange (ISO 12620)'**
  String get glossaryExportFormatTbxSubtitle;

  /// No description provided for @glossaryExportSourceLanguage.
  ///
  /// In en, this message translates to:
  /// **'Source language'**
  String get glossaryExportSourceLanguage;

  /// No description provided for @glossaryExportButtonExport.
  ///
  /// In en, this message translates to:
  /// **'Export'**
  String get glossaryExportButtonExport;

  /// No description provided for @extractFormatConversionFailed.
  ///
  /// In en, this message translates to:
  /// **'Format conversion failed.'**
  String get extractFormatConversionFailed;

  /// No description provided for @fileUploadDisabledMessage.
  ///
  /// In en, this message translates to:
  /// **'File selection disabled (processing in progress)'**
  String get fileUploadDisabledMessage;

  /// No description provided for @fileUploadSupportedFormats.
  ///
  /// In en, this message translates to:
  /// **'Supported: Word (DOCX), PowerPoint (PPTX), Excel (XLSX/CSV), PDF, Markdown, TXT, HTML, SRT, JSON, EPUB, MOBI, Qt TS, PNG, JPEG'**
  String get fileUploadSupportedFormats;

  /// No description provided for @fileUploadDropHere.
  ///
  /// In en, this message translates to:
  /// **'Drop file here'**
  String get fileUploadDropHere;

  /// No description provided for @fileUploadHint.
  ///
  /// In en, this message translates to:
  /// **'Drag & drop file here or click to select'**
  String get fileUploadHint;

  /// No description provided for @fileUploadCancelTask.
  ///
  /// In en, this message translates to:
  /// **'Cancel Current Task'**
  String get fileUploadCancelTask;

  /// No description provided for @exclusionPanelExcludeAll.
  ///
  /// In en, this message translates to:
  /// **'Exclude All'**
  String get exclusionPanelExcludeAll;

  /// No description provided for @exclusionPanelCancelUserExclusion.
  ///
  /// In en, this message translates to:
  /// **'Restore Auto Exclusions'**
  String get exclusionPanelCancelUserExclusion;

  /// No description provided for @exclusionPanelClearAllExclusions.
  ///
  /// In en, this message translates to:
  /// **'Clear All Exclusions'**
  String get exclusionPanelClearAllExclusions;

  /// No description provided for @exclusionPanelExclusionByType.
  ///
  /// In en, this message translates to:
  /// **'Exclusion By Type:'**
  String get exclusionPanelExclusionByType;

  /// No description provided for @exclusionPanelStructuralHeader.
  ///
  /// In en, this message translates to:
  /// **'Structural (Header)'**
  String get exclusionPanelStructuralHeader;

  /// No description provided for @exclusionPanelStructuralFooter.
  ///
  /// In en, this message translates to:
  /// **'Structural (Footer)'**
  String get exclusionPanelStructuralFooter;

  /// No description provided for @exclusionPanelUserExcluded.
  ///
  /// In en, this message translates to:
  /// **'User Excluded'**
  String get exclusionPanelUserExcluded;

  /// No description provided for @exclusionPanelExcluded.
  ///
  /// In en, this message translates to:
  /// **'Excluded'**
  String get exclusionPanelExcluded;

  /// No description provided for @exclusionPanelFilterDisplayMode.
  ///
  /// In en, this message translates to:
  /// **'Filter Display Mode:'**
  String get exclusionPanelFilterDisplayMode;

  /// No description provided for @exclusionPanelRebuild.
  ///
  /// In en, this message translates to:
  /// **'Rebuild'**
  String get exclusionPanelRebuild;

  /// No description provided for @exclusionPanelPage.
  ///
  /// In en, this message translates to:
  /// **'Page'**
  String get exclusionPanelPage;

  /// No description provided for @exclusionPanelRebuildTooltip.
  ///
  /// In en, this message translates to:
  /// **'Show only matching segments in new pagination'**
  String get exclusionPanelRebuildTooltip;

  /// No description provided for @exclusionPanelPageTooltip.
  ///
  /// In en, this message translates to:
  /// **'Filter within current page'**
  String get exclusionPanelPageTooltip;

  /// No description provided for @exclusionPanelSegmentTypeFilters.
  ///
  /// In en, this message translates to:
  /// **'Segment Type Filters:'**
  String get exclusionPanelSegmentTypeFilters;

  /// No description provided for @exclusionPanelCollapsePanelTooltip.
  ///
  /// In en, this message translates to:
  /// **'Collapse panel'**
  String get exclusionPanelCollapsePanelTooltip;

  /// No description provided for @exclusionPanelExclusionControls.
  ///
  /// In en, this message translates to:
  /// **'Exclusion Controls:'**
  String get exclusionPanelExclusionControls;

  /// No description provided for @exclusionPanelExcludeCategory.
  ///
  /// In en, this message translates to:
  /// **'Exclude {name} ({count})'**
  String exclusionPanelExcludeCategory(Object count, Object name);

  /// No description provided for @exclusionPanelChangeReasonTitle.
  ///
  /// In en, this message translates to:
  /// **'Change Exclusion Reason'**
  String get exclusionPanelChangeReasonTitle;

  /// No description provided for @exclusionPanelCurrentLabel.
  ///
  /// In en, this message translates to:
  /// **'Current: '**
  String get exclusionPanelCurrentLabel;

  /// No description provided for @exclusionPanelSelectNewReason.
  ///
  /// In en, this message translates to:
  /// **'Select new reason:'**
  String get exclusionPanelSelectNewReason;

  /// No description provided for @exclusionPanelNoneRemoveExclusion.
  ///
  /// In en, this message translates to:
  /// **'None (Remove Exclusion)'**
  String get exclusionPanelNoneRemoveExclusion;

  /// No description provided for @exclusionPanelApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get exclusionPanelApply;

  /// No description provided for @exclusionPanelExpandFilterPanel.
  ///
  /// In en, this message translates to:
  /// **'Expand Filter Panel'**
  String get exclusionPanelExpandFilterPanel;

  /// No description provided for @exclusionPanelCollapseFilterPanel.
  ///
  /// In en, this message translates to:
  /// **'Collapse Filter Panel'**
  String get exclusionPanelCollapseFilterPanel;

  /// No description provided for @extractToolbarSegments.
  ///
  /// In en, this message translates to:
  /// **'Segments ({start}-{end} of {total})'**
  String extractToolbarSegments(Object end, Object start, Object total);

  /// No description provided for @extractToolbarCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get extractToolbarCancel;

  /// No description provided for @extractCancelExtractionTitle.
  ///
  /// In en, this message translates to:
  /// **'Cancel Extraction'**
  String get extractCancelExtractionTitle;

  /// No description provided for @extractCancelExtractionContent.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to cancel the extraction? This cannot be undone.'**
  String get extractCancelExtractionContent;

  /// No description provided for @extractCancelExtractionNo.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get extractCancelExtractionNo;

  /// No description provided for @extractCancelExtractionYes.
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get extractCancelExtractionYes;

  /// No description provided for @extractExtractionCancelled.
  ///
  /// In en, this message translates to:
  /// **'Extraction cancelled'**
  String get extractExtractionCancelled;

  /// No description provided for @extractMineruConfigRequiredTitle.
  ///
  /// In en, this message translates to:
  /// **'MinerU Configuration Required'**
  String get extractMineruConfigRequiredTitle;

  /// No description provided for @extractMineruConfigRequiredContent.
  ///
  /// In en, this message translates to:
  /// **'Failed to connect to MinerU API. Please configure MinerU settings in the Settings page.\n\nError details:\n{error}'**
  String extractMineruConfigRequiredContent(Object error);

  /// No description provided for @extractOpenSettings.
  ///
  /// In en, this message translates to:
  /// **'Open Settings'**
  String get extractOpenSettings;

  /// No description provided for @extractErrorLabel.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String extractErrorLabel(Object error);

  /// No description provided for @extractRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get extractRetry;

  /// No description provided for @extractTaskTypeDetectIdentifier.
  ///
  /// In en, this message translates to:
  /// **'Detect Identifier'**
  String get extractTaskTypeDetectIdentifier;

  /// No description provided for @extractTaskTypeDetectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Detect Language'**
  String get extractTaskTypeDetectLanguage;

  /// No description provided for @extractTaskTypeDetectExclusions.
  ///
  /// In en, this message translates to:
  /// **'Detect Exclusions'**
  String get extractTaskTypeDetectExclusions;

  /// No description provided for @translationStatsTitle.
  ///
  /// In en, this message translates to:
  /// **'Translation Statistics'**
  String get translationStatsTitle;

  /// No description provided for @translationStatsDocuments.
  ///
  /// In en, this message translates to:
  /// **'Documents'**
  String get translationStatsDocuments;

  /// No description provided for @translationStatsPages.
  ///
  /// In en, this message translates to:
  /// **'Pages'**
  String get translationStatsPages;

  /// No description provided for @translationStatsLastUpdated.
  ///
  /// In en, this message translates to:
  /// **'Last updated: {date}'**
  String translationStatsLastUpdated(Object date);

  /// No description provided for @translationStatsLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load statistics'**
  String get translationStatsLoadFailed;

  /// No description provided for @translationStatsJustNow.
  ///
  /// In en, this message translates to:
  /// **'Just now'**
  String get translationStatsJustNow;

  /// No description provided for @translationStatsOneMinuteAgo.
  ///
  /// In en, this message translates to:
  /// **'1 minute ago'**
  String get translationStatsOneMinuteAgo;

  /// No description provided for @translationStatsMinutesAgo.
  ///
  /// In en, this message translates to:
  /// **'{count} minutes ago'**
  String translationStatsMinutesAgo(Object count);

  /// No description provided for @translationStatsOneHourAgo.
  ///
  /// In en, this message translates to:
  /// **'1 hour ago'**
  String get translationStatsOneHourAgo;

  /// No description provided for @translationStatsHoursAgo.
  ///
  /// In en, this message translates to:
  /// **'{count} hours ago'**
  String translationStatsHoursAgo(Object count);

  /// No description provided for @translationStatsYesterday.
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get translationStatsYesterday;

  /// No description provided for @translationStatsDaysAgo.
  ///
  /// In en, this message translates to:
  /// **'{count} days ago'**
  String translationStatsDaysAgo(Object count);

  /// No description provided for @aiPlatformDisplayName.
  ///
  /// In en, this message translates to:
  /// **'Display Name'**
  String get aiPlatformDisplayName;

  /// No description provided for @aiPlatformParserSubtype.
  ///
  /// In en, this message translates to:
  /// **'Parser Subtype'**
  String get aiPlatformParserSubtype;

  /// No description provided for @aiPlatformParserSubtypeCloud.
  ///
  /// In en, this message translates to:
  /// **'Cloud'**
  String get aiPlatformParserSubtypeCloud;

  /// No description provided for @aiPlatformParserSubtypeLocal.
  ///
  /// In en, this message translates to:
  /// **'Local'**
  String get aiPlatformParserSubtypeLocal;

  /// No description provided for @translationQueueEdit.
  ///
  /// In en, this message translates to:
  /// **'Labeled Edit'**
  String get translationQueueEdit;

  /// No description provided for @translationQueueSelectFormats.
  ///
  /// In en, this message translates to:
  /// **'Select'**
  String get translationQueueSelectFormats;

  /// No description provided for @translationQueueSelectFormatsTitle.
  ///
  /// In en, this message translates to:
  /// **'Select Download Formats'**
  String get translationQueueSelectFormatsTitle;

  /// No description provided for @translationQueueSelectFormatsFormatLabel.
  ///
  /// In en, this message translates to:
  /// **'Format'**
  String get translationQueueSelectFormatsFormatLabel;

  /// No description provided for @translationQueueSelectFormatsDownload.
  ///
  /// In en, this message translates to:
  /// **'Download'**
  String get translationQueueSelectFormatsDownload;

  /// No description provided for @translationQueueBatchLabelHint.
  ///
  /// In en, this message translates to:
  /// **'Batch label (for task queue grouping)'**
  String get translationQueueBatchLabelHint;

  /// No description provided for @translationQueueBatchCreateFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to create upload batch'**
  String get translationQueueBatchCreateFailed;

  /// No description provided for @translationQueueUngroupedSection.
  ///
  /// In en, this message translates to:
  /// **'Ungrouped'**
  String get translationQueueUngroupedSection;

  /// No description provided for @translationQueueBatchProgress.
  ///
  /// In en, this message translates to:
  /// **'{completed}/{total} completed'**
  String translationQueueBatchProgress(int completed, int total);

  /// No description provided for @translationQueueBatchSelectAll.
  ///
  /// In en, this message translates to:
  /// **'Select batch'**
  String get translationQueueBatchSelectAll;

  /// No description provided for @translationQueueBatchDownload.
  ///
  /// In en, this message translates to:
  /// **'Download batch'**
  String get translationQueueBatchDownload;

  /// No description provided for @translationQueueBatchDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete batch'**
  String get translationQueueBatchDelete;

  /// No description provided for @translationQueueBatchDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete this batch?'**
  String get translationQueueBatchDeleteTitle;

  /// No description provided for @translationQueueBatchDeleteMessage.
  ///
  /// In en, this message translates to:
  /// **'All tasks in this batch will be removed from the queue and their cached results deleted.'**
  String get translationQueueBatchDeleteMessage;

  /// No description provided for @reeditTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit Translation'**
  String get reeditTitle;

  /// No description provided for @reeditSaveExport.
  ///
  /// In en, this message translates to:
  /// **'Save && Export'**
  String get reeditSaveExport;

  /// No description provided for @reeditFetchError.
  ///
  /// In en, this message translates to:
  /// **'Failed to load translation segments.'**
  String get reeditFetchError;

  /// No description provided for @reeditSaveSuccess.
  ///
  /// In en, this message translates to:
  /// **'Changes saved successfully.'**
  String get reeditSaveSuccess;

  /// No description provided for @reeditSaveError.
  ///
  /// In en, this message translates to:
  /// **'Failed to save changes.'**
  String get reeditSaveError;

  /// No description provided for @workspaceCloseFlowTitle.
  ///
  /// In en, this message translates to:
  /// **'Close this flow?'**
  String get workspaceCloseFlowTitle;

  /// No description provided for @workspaceCloseFlowMessage.
  ///
  /// In en, this message translates to:
  /// **'Closing this flow will discard any unsaved changes.'**
  String get workspaceCloseFlowMessage;

  /// No description provided for @workspaceCloseFlowSaveToQueue.
  ///
  /// In en, this message translates to:
  /// **'Save and close'**
  String get workspaceCloseFlowSaveToQueue;

  /// No description provided for @workspaceCloseFlowDestroy.
  ///
  /// In en, this message translates to:
  /// **'Destroy and close'**
  String get workspaceCloseFlowDestroy;

  /// No description provided for @workspaceCloseFlowCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get workspaceCloseFlowCancel;

  /// No description provided for @fetchUrlCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get fetchUrlCancel;

  /// Button label to fetch content from a URL
  ///
  /// In en, this message translates to:
  /// **'Fetch URL'**
  String get fetchUrl;

  /// Button label to close the URL input field
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get fetchUrlClose;

  /// No description provided for @loginSubtitleFeatures.
  ///
  /// In en, this message translates to:
  /// **'Document Translation\nFormat Conversion\nURL Fetch'**
  String get loginSubtitleFeatures;

  /// No description provided for @loginSubtitleTagline.
  ///
  /// In en, this message translates to:
  /// **'AI Document Processing System'**
  String get loginSubtitleTagline;

  /// No description provided for @loginUsernameLabel.
  ///
  /// In en, this message translates to:
  /// **'Username'**
  String get loginUsernameLabel;

  /// No description provided for @loginUsernameHint.
  ///
  /// In en, this message translates to:
  /// **'Please enter username'**
  String get loginUsernameHint;

  /// No description provided for @loginUsernameRequiredError.
  ///
  /// In en, this message translates to:
  /// **'Please enter your username'**
  String get loginUsernameRequiredError;

  /// No description provided for @loginUsernameMinLengthError.
  ///
  /// In en, this message translates to:
  /// **'Username must be at least 3 characters'**
  String get loginUsernameMinLengthError;

  /// No description provided for @loginPasswordLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get loginPasswordLabel;

  /// No description provided for @loginPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Please enter password'**
  String get loginPasswordHint;

  /// No description provided for @loginPasswordRequiredError.
  ///
  /// In en, this message translates to:
  /// **'Please enter your password'**
  String get loginPasswordRequiredError;

  /// No description provided for @loginForgotPassword.
  ///
  /// In en, this message translates to:
  /// **'Forgot Password?'**
  String get loginForgotPassword;

  /// No description provided for @loginPasswordRecoveryTitle.
  ///
  /// In en, this message translates to:
  /// **'Password Recovery'**
  String get loginPasswordRecoveryTitle;

  /// No description provided for @loginPasswordRecoveryContactAdmin.
  ///
  /// In en, this message translates to:
  /// **'Please contact your administrator to reset your password.'**
  String get loginPasswordRecoveryContactAdmin;

  /// No description provided for @loginPasswordRecoveryAdminHint.
  ///
  /// In en, this message translates to:
  /// **'Administrators can reset passwords through the user management page after logging in.'**
  String get loginPasswordRecoveryAdminHint;

  /// No description provided for @loginAuthMethodDefault.
  ///
  /// In en, this message translates to:
  /// **'Using Default Authentication'**
  String get loginAuthMethodDefault;

  /// No description provided for @loginCopyErrorLabel.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get loginCopyErrorLabel;

  /// No description provided for @loginErrorCopiedMessage.
  ///
  /// In en, this message translates to:
  /// **'Error message copied to clipboard'**
  String get loginErrorCopiedMessage;

  /// No description provided for @loginWelcomeBack.
  ///
  /// In en, this message translates to:
  /// **'Welcome back'**
  String get loginWelcomeBack;

  /// No description provided for @loginFeatureFormats.
  ///
  /// In en, this message translates to:
  /// **'PDF, DOCX, XLSX, HTML, EPUB, MOBI\nand 15+ more formats'**
  String get loginFeatureFormats;

  /// No description provided for @loginFeatureLayout.
  ///
  /// In en, this message translates to:
  /// **'Layout-preserving translation\nwith high fidelity'**
  String get loginFeatureLayout;

  /// No description provided for @loginFeaturePlatforms.
  ///
  /// In en, this message translates to:
  /// **'20+ LLM platforms supported\nincluding OpenAI, Claude, Ollama'**
  String get loginFeaturePlatforms;

  /// No description provided for @loginPasswordRecoveryAdminGuide.
  ///
  /// In en, this message translates to:
  /// **'If you are an administrator, please follow the password recovery process.'**
  String get loginPasswordRecoveryAdminGuide;

  /// No description provided for @commonDarkMode.
  ///
  /// In en, this message translates to:
  /// **'Dark Mode'**
  String get commonDarkMode;

  /// No description provided for @commonLightMode.
  ///
  /// In en, this message translates to:
  /// **'Light Mode'**
  String get commonLightMode;

  /// No description provided for @segmentPdfFontSizeAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto ({sizePt}pt)'**
  String segmentPdfFontSizeAuto(String sizePt);

  /// No description provided for @segmentPdfFontSizeAutoUnknown.
  ///
  /// In en, this message translates to:
  /// **'Auto'**
  String get segmentPdfFontSizeAutoUnknown;

  /// No description provided for @segmentPdfFontSizeManual.
  ///
  /// In en, this message translates to:
  /// **'{sizePt}pt'**
  String segmentPdfFontSizeManual(String sizePt);

  /// No description provided for @segmentRotationLabel.
  ///
  /// In en, this message translates to:
  /// **'{degrees}°'**
  String segmentRotationLabel(int degrees);

  /// No description provided for @segmentRotationOff.
  ///
  /// In en, this message translates to:
  /// **'Rotate'**
  String get segmentRotationOff;

  /// No description provided for @segmentRotationNone.
  ///
  /// In en, this message translates to:
  /// **'No rotation'**
  String get segmentRotationNone;

  /// No description provided for @segmentRotationMenuTitle.
  ///
  /// In en, this message translates to:
  /// **'Angle'**
  String get segmentRotationMenuTitle;

  /// No description provided for @segmentTableStrokeLabel.
  ///
  /// In en, this message translates to:
  /// **'{strokePt} pt'**
  String segmentTableStrokeLabel(String strokePt);

  /// No description provided for @segmentTableStrokeOff.
  ///
  /// In en, this message translates to:
  /// **'Grid'**
  String get segmentTableStrokeOff;

  /// No description provided for @segmentTableStrokeNone.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get segmentTableStrokeNone;

  /// No description provided for @segmentTableStrokeMenuTitle.
  ///
  /// In en, this message translates to:
  /// **'Border weight'**
  String get segmentTableStrokeMenuTitle;

  /// No description provided for @segmentItemExclude.
  ///
  /// In en, this message translates to:
  /// **'Exclude'**
  String get segmentItemExclude;

  /// No description provided for @segmentItemEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get segmentItemEdit;

  /// No description provided for @segmentItemRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get segmentItemRetry;

  /// No description provided for @segmentItemMarkedRetry.
  ///
  /// In en, this message translates to:
  /// **'Marked Retry'**
  String get segmentItemMarkedRetry;

  /// No description provided for @segmentItemClear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get segmentItemClear;

  /// No description provided for @segmentItemCleared.
  ///
  /// In en, this message translates to:
  /// **'Cleared'**
  String get segmentItemCleared;

  /// No description provided for @segmentItemFix.
  ///
  /// In en, this message translates to:
  /// **'Fix'**
  String get segmentItemFix;

  /// No description provided for @segmentItemExclusionBadge.
  ///
  /// In en, this message translates to:
  /// **'EX: {reason}'**
  String segmentItemExclusionBadge(String reason);

  /// No description provided for @segmentItemExclusionRemoveTooltip.
  ///
  /// In en, this message translates to:
  /// **'Click to remove exclusion'**
  String get segmentItemExclusionRemoveTooltip;

  /// No description provided for @segmentItemExclusionLockedTooltip.
  ///
  /// In en, this message translates to:
  /// **'This segment is automatically excluded and cannot be unexcluded'**
  String get segmentItemExclusionLockedTooltip;

  /// No description provided for @segmentItemExclusionEditTooltip.
  ///
  /// In en, this message translates to:
  /// **'Click to edit exclusion reason'**
  String get segmentItemExclusionEditTooltip;

  /// No description provided for @segmentItemExclusionRemoved.
  ///
  /// In en, this message translates to:
  /// **'Exclusion removed'**
  String get segmentItemExclusionRemoved;

  /// No description provided for @segmentItemExclusionReasonUpdated.
  ///
  /// In en, this message translates to:
  /// **'Exclusion reason updated'**
  String get segmentItemExclusionReasonUpdated;

  /// No description provided for @segmentItemExclusionUpdateFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to update exclusion reason: {error}'**
  String segmentItemExclusionUpdateFailed(String error);

  /// No description provided for @segmentItemUndoEditTooltip.
  ///
  /// In en, this message translates to:
  /// **'Undo (Edit)'**
  String get segmentItemUndoEditTooltip;

  /// No description provided for @segmentItemRedoEditTooltip.
  ///
  /// In en, this message translates to:
  /// **'Redo (Edit)'**
  String get segmentItemRedoEditTooltip;

  /// No description provided for @segmentItemUndoSaveTooltip.
  ///
  /// In en, this message translates to:
  /// **'Undo (Save)'**
  String get segmentItemUndoSaveTooltip;

  /// No description provided for @segmentItemRedoSaveTooltip.
  ///
  /// In en, this message translates to:
  /// **'Redo (Save)'**
  String get segmentItemRedoSaveTooltip;

  /// No description provided for @segmentItemCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get segmentItemCancel;

  /// No description provided for @segmentItemSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get segmentItemSave;

  /// No description provided for @segmentItemEditShortcutHint.
  ///
  /// In en, this message translates to:
  /// **'Press Ctrl+Enter to save, Esc to cancel'**
  String get segmentItemEditShortcutHint;

  /// No description provided for @segmentItemTranslationHint.
  ///
  /// In en, this message translates to:
  /// **'Enter translation...'**
  String get segmentItemTranslationHint;

  /// No description provided for @segmentItemSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to save: {error}'**
  String segmentItemSaveFailed(String error);

  /// No description provided for @segmentPdfFontSizeTitle.
  ///
  /// In en, this message translates to:
  /// **'PDF font size'**
  String get segmentPdfFontSizeTitle;

  /// No description provided for @segmentPdfTypographyTitle.
  ///
  /// In en, this message translates to:
  /// **'PDF typography'**
  String get segmentPdfTypographyTitle;

  /// No description provided for @segmentPdfTypographyFontTitle.
  ///
  /// In en, this message translates to:
  /// **'PDF font'**
  String get segmentPdfTypographyFontTitle;

  /// No description provided for @segmentPdfTypographyLeadingTitle.
  ///
  /// In en, this message translates to:
  /// **'Line spacing'**
  String get segmentPdfTypographyLeadingTitle;

  /// No description provided for @segmentPdfTypographyPreviewLabel.
  ///
  /// In en, this message translates to:
  /// **'Preview'**
  String get segmentPdfTypographyPreviewLabel;

  /// No description provided for @segmentPdfTypographyBold.
  ///
  /// In en, this message translates to:
  /// **'Bold'**
  String get segmentPdfTypographyBold;

  /// No description provided for @segmentPdfTypographyItalic.
  ///
  /// In en, this message translates to:
  /// **'Italic'**
  String get segmentPdfTypographyItalic;

  /// No description provided for @segmentPdfTypographyFontSizeLabel.
  ///
  /// In en, this message translates to:
  /// **'Font size: {sizePt} pt'**
  String segmentPdfTypographyFontSizeLabel(String sizePt);

  /// No description provided for @segmentPdfTypographyLeadingLabel.
  ///
  /// In en, this message translates to:
  /// **'Line spacing: {leadingEm} em'**
  String segmentPdfTypographyLeadingLabel(String leadingEm);

  /// No description provided for @segmentPdfFontSizeReset.
  ///
  /// In en, this message translates to:
  /// **'Reset to auto'**
  String get segmentPdfFontSizeReset;

  /// No description provided for @segmentPdfTypographyResetFont.
  ///
  /// In en, this message translates to:
  /// **'Reset font to auto'**
  String get segmentPdfTypographyResetFont;

  /// No description provided for @segmentPdfTypographyResetLeading.
  ///
  /// In en, this message translates to:
  /// **'Reset line spacing to auto'**
  String get segmentPdfTypographyResetLeading;

  /// No description provided for @segmentPdfFontSizeApply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get segmentPdfFontSizeApply;

  /// No description provided for @translationPreviewPdfRevision.
  ///
  /// In en, this message translates to:
  /// **'Preview revision'**
  String get translationPreviewPdfRevision;

  /// No description provided for @translationPreviewPdfRevisionCompare.
  ///
  /// In en, this message translates to:
  /// **'Compare view'**
  String get translationPreviewPdfRevisionCompare;

  /// No description provided for @translationPreviewLayoutComparePreview.
  ///
  /// In en, this message translates to:
  /// **'Compare preview'**
  String get translationPreviewLayoutComparePreview;

  /// No description provided for @translationPreviewLayoutTranslationRevision.
  ///
  /// In en, this message translates to:
  /// **'Translation revision'**
  String get translationPreviewLayoutTranslationRevision;

  /// No description provided for @translationPreviewLayoutCompareRevision.
  ///
  /// In en, this message translates to:
  /// **'Compare revision'**
  String get translationPreviewLayoutCompareRevision;

  /// No description provided for @translationPreviewAutoRefreshPdf.
  ///
  /// In en, this message translates to:
  /// **'Auto refresh PDF'**
  String get translationPreviewAutoRefreshPdf;

  /// No description provided for @translationPreviewFollowSegmentPage.
  ///
  /// In en, this message translates to:
  /// **'Follow segment page'**
  String get translationPreviewFollowSegmentPage;

  /// No description provided for @translationPreviewFollowSegmentPageDesc.
  ///
  /// In en, this message translates to:
  /// **'When enabled, the translation PDF preview jumps to the page of the focused or checked segment'**
  String get translationPreviewFollowSegmentPageDesc;

  /// No description provided for @translationPreviewMarkSelectedSegment.
  ///
  /// In en, this message translates to:
  /// **'Mark selected segment'**
  String get translationPreviewMarkSelectedSegment;

  /// No description provided for @translationPreviewMarkSelectedSegmentDesc.
  ///
  /// In en, this message translates to:
  /// **'When enabled, show a frame around the selected segment on the translation preview'**
  String get translationPreviewMarkSelectedSegmentDesc;

  /// No description provided for @translationPreviewEditSegmentBbox.
  ///
  /// In en, this message translates to:
  /// **'Edit Bbox'**
  String get translationPreviewEditSegmentBbox;

  /// No description provided for @translationPreviewEditSegmentBboxDesc.
  ///
  /// In en, this message translates to:
  /// **'When enabled, drag handles to adjust bounding box of the selected segment'**
  String get translationPreviewEditSegmentBboxDesc;

  /// No description provided for @translationPreviewStaleSession.
  ///
  /// In en, this message translates to:
  /// **'Preview unavailable. Reopen revision preview from the translation panel.'**
  String get translationPreviewStaleSession;

  /// No description provided for @translationPreviewPdfPageIndicator.
  ///
  /// In en, this message translates to:
  /// **'Page {current} / {total}'**
  String translationPreviewPdfPageIndicator(String current, String total);

  /// No description provided for @translationPreviewRefreshPdf.
  ///
  /// In en, this message translates to:
  /// **'Refresh PDF'**
  String get translationPreviewRefreshPdf;

  /// No description provided for @translationPreviewBatchFont.
  ///
  /// In en, this message translates to:
  /// **'Font'**
  String get translationPreviewBatchFont;

  /// No description provided for @translationPreviewBatchFontTooltip.
  ///
  /// In en, this message translates to:
  /// **'Apply font settings to selected segments'**
  String get translationPreviewBatchFontTooltip;

  /// No description provided for @translationPreviewBatchFontSizeDecreaseTooltip.
  ///
  /// In en, this message translates to:
  /// **'Decrease font size by 0.1 pt for selected segments'**
  String get translationPreviewBatchFontSizeDecreaseTooltip;

  /// No description provided for @translationPreviewBatchFontSizeIncreaseTooltip.
  ///
  /// In en, this message translates to:
  /// **'Increase font size by 0.1 pt for selected segments'**
  String get translationPreviewBatchFontSizeIncreaseTooltip;

  /// No description provided for @translationPreviewBatchLeading.
  ///
  /// In en, this message translates to:
  /// **'Batch line spacing'**
  String get translationPreviewBatchLeading;

  /// No description provided for @translationPreviewBatchLeadingTooltip.
  ///
  /// In en, this message translates to:
  /// **'Apply line spacing to selected segments'**
  String get translationPreviewBatchLeadingTooltip;

  /// No description provided for @translationPreviewPdfRevisionSelectAll.
  ///
  /// In en, this message translates to:
  /// **'Select all'**
  String get translationPreviewPdfRevisionSelectAll;

  /// No description provided for @translationPreviewPdfRevisionInvertSelection.
  ///
  /// In en, this message translates to:
  /// **'Invert selection'**
  String get translationPreviewPdfRevisionInvertSelection;

  /// No description provided for @translationPreviewPdfRevisionPageFilterLabel.
  ///
  /// In en, this message translates to:
  /// **'Page'**
  String get translationPreviewPdfRevisionPageFilterLabel;

  /// No description provided for @translationPreviewPdfRevisionPageFilterAll.
  ///
  /// In en, this message translates to:
  /// **'All pages'**
  String get translationPreviewPdfRevisionPageFilterAll;

  /// No description provided for @translationPreviewPdfRevisionPageFilterSelectAll.
  ///
  /// In en, this message translates to:
  /// **'Select all pages'**
  String get translationPreviewPdfRevisionPageFilterSelectAll;

  /// No description provided for @segmentPdfRevisionFontLabel.
  ///
  /// In en, this message translates to:
  /// **'Font'**
  String get segmentPdfRevisionFontLabel;

  /// No description provided for @segmentPdfRevisionEditLabel.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get segmentPdfRevisionEditLabel;

  /// No description provided for @segmentPdfRevisionClearLabel.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get segmentPdfRevisionClearLabel;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es', 'ja', 'ko', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
    case 'ja':
      return AppLocalizationsJa();
    case 'ko':
      return AppLocalizationsKo();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
