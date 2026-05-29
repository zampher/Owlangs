// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get settingsGeneralTitle => '一般設定';

  @override
  String get settingsGeneralDarkModeTitle => 'ダークモード';

  @override
  String get settingsGeneralDarkModeSubtitle => 'ダークテーマを有効にする（即時適用）';

  @override
  String get settingsGeneralLanguageTitle => '言語';

  @override
  String get settingsGeneralNotificationsTitle => '通知';

  @override
  String get settingsGeneralNotificationsSubtitle => '完了したタスクの通知を受け取る（即時適用）';

  @override
  String get settingsGeneralAutoSaveTitle => '自動保存';

  @override
  String get settingsGeneralAutoSaveSubtitle => '作業中の内容を自動保存する（即時適用）';

  @override
  String get settingsGeneralShowAdsTitle => '広告を表示';

  @override
  String get settingsGeneralShowAdsSubtitle =>
      'ホームとフローで広告プレースホルダーを表示（system.jsonに保存）';

  @override
  String get settingsGeneralClearStatsButton => '統計をクリア';

  @override
  String get settingsGeneralClearStatsConfirmTitle => '統計をクリアしますか？';

  @override
  String get settingsGeneralClearStatsConfirmMessage =>
      'ホームページに表示されているドキュメント数とページ数が0にリセットされます。この操作は元に戻せません。';

  @override
  String get settingsGeneralClearStatsConfirmButton => 'クリア';

  @override
  String get settingsGeneralClearStatsSuccess => '統計がクリアされました。';

  @override
  String get backToHome => 'ホームに戻る';

  @override
  String get settingsFontSectionTitle => 'フォント設定';

  @override
  String get settingsFontPreviewSizeTitle => 'プレビューフォントサイズ';

  @override
  String get settingsFontPreviewSizeSubtitle => 'プレビューでの原文と訳文のフォントサイズ';

  @override
  String get translationToolbarFilterAll => 'すべて';

  @override
  String get translationToolbarFilterFailed => '失敗';

  @override
  String get translationToolbarFilterIncluded => '含む';

  @override
  String get translationToolbarFilterExcluded => '除外';

  @override
  String get translationToolbarSearchTooltip => '検索 (Ctrl+F / Cmd+F)';

  @override
  String get translationToolbarPrevRetryTooltip => '前の再試行セグメント';

  @override
  String get translationToolbarNextRetryTooltip => '次の再試行セグメント';

  @override
  String get translationToolbarPreviewTooltip => 'プレビュー';

  @override
  String get translationToolbarFormatSettingsTooltip => 'フォーマット設定';

  @override
  String get translationToolbarExportTooltip => 'ドキュメントをエクスポート';

  @override
  String get translationToolbarPdfPreviewTooltip => 'PDFプレビュー（デバッグ）';

  @override
  String get translationToolbarCancelButton => 'キャンセル';

  @override
  String get translationToolbarExitFullscreenTooltip => 'フルスクリーンを終了';

  @override
  String get translationToolbarEnterFullscreenTooltip => 'フルスクリーンにする';

  @override
  String get translationToolbarDecreaseFontSize => 'フォントサイズを縮小';

  @override
  String get translationToolbarIncreaseFontSize => 'フォントサイズを拡大';

  @override
  String get translationToolbarMergedView => '閲覧モード';

  @override
  String get translationToolbarSegmentView => 'ラベルモード';

  @override
  String get translationToolbarUpload => 'アップロード';

  @override
  String get translationToolbarUploading => 'アップロード中...';

  @override
  String get translationToolbarFileUploaded => 'ファイルをアップロードしました';

  @override
  String get translationToolbarReextract => '再抽出';

  @override
  String get translationToolbarReextracting => '再抽出中...';

  @override
  String translationToolbarTokensCount(Object count) {
    return '$count トークン';
  }

  @override
  String get translationToolbarOpenGlossaryTab => '用語集タブを開く';

  @override
  String get translationToolbarHintWaitExtract => '抽出が完了するまでお待ちください';

  @override
  String get translationToolbarHintOperationInProgress => '操作が進行中です';

  @override
  String get translationToolbarGlossary => '用語集';

  @override
  String get translationToolbarConvertHint => '書式変換・全段落除外・翻訳を実行し、「変換」タブから書き出し';

  @override
  String get translationToolbarConvert => '変換';

  @override
  String get translationToolbarHintSaveGlossaryFirst =>
      'まず用語集を保存してください（適用をクリック）';

  @override
  String get translationToolbarHintUpdatingExcluded => '除外セグメントを更新中...';

  @override
  String get translationToolbarStartTranslation => '翻訳を開始';

  @override
  String get translationToolbarTranslateAll => 'すべて翻訳';

  @override
  String get translationToolbarTranslating => '翻訳中...';

  @override
  String get translationToolbarRetryInProgress => '再試行中...';

  @override
  String get translationToolbarRetryTooltip =>
      '失敗した、または再試行マークが付いたすべてのセグメントを再翻訳します。これにより、翻訳中に失敗した、または手動で再試行マークが付けられたセグメントが、現在選択されているAIプラットフォームを使用して再翻訳されます。除外およびクリアされたセグメントはスキップされます。';

  @override
  String get translationToolbarRetry => '再試行';

  @override
  String get translationPersistQueueTooltip =>
      '現在のエクスポートをサーバーに書き込み、タスクキューのダウンロードをこの画面の最新の編集と一致させます。';

  @override
  String get translationPersistQueueButton => 'キューを更新';

  @override
  String get translationPersistQueueAlreadySyncedTooltip =>
      'すでにキューのスナップショットと一致しています。保存は不要です。';

  @override
  String get translationPersistQueueSuccess => 'タスクキュー用に最新のエクスポートを保存しました。';

  @override
  String translationPersistQueueFailed(Object error) {
    return 'キューへの保存に失敗しました: $error';
  }

  @override
  String get translationCloseTranslateTabTitle => 'タスクキューが最終結果と一致しない可能性があります';

  @override
  String get translationCloseTranslateTabMessage =>
      'このタブでの編集はまだタスクキューのスナップショットに保存されていません。保存せずに閉じると、「タスクキュー」からダウンロードするファイルは、このタブで見ている最終版にならない場合があります。\n\n先にキューを更新してから閉じるか、キューに保存せずにこのタブを閉じるかを選べます。';

  @override
  String get translationCloseTranslateTabStay => 'キャンセル';

  @override
  String get translationCloseTranslateTabClose => '保存せずに閉じる';

  @override
  String get translationCloseTranslateTabSaveAndClose => '保存して閉じる';

  @override
  String get translationCloseTranslateTabKeepTitle => 'タスクをキューに保持しますか？';

  @override
  String get translationCloseTranslateTabKeepMessage =>
      '翻訳が完了しました。後で確認・編集するためにタスクをキューに保持しますか？';

  @override
  String get translationCloseTranslateTabKeepInQueue => 'キューに保持';

  @override
  String get translationCloseTranslateTabDiscard => '破棄';

  @override
  String get translationToolbarSwitchToFile => 'ファイルに切り替え';

  @override
  String get translationToolbarSwitchToText => 'テキストを入力';

  @override
  String get translationStatusCompleted => '翻訳完了';

  @override
  String get translationStatusRetry => '翻訳再試行';

  @override
  String get translationStatusFailed => '翻訳失敗';

  @override
  String get translationStatusCancelled => '翻訳キャンセル';

  @override
  String get translationStatusTranslating => '翻訳中';

  @override
  String get translationStatusTranslatingFallback => '翻訳中...';

  @override
  String get translationStatusReady => '準備完了';

  @override
  String get translationStatusTaskPending => 'タスク保留中';

  @override
  String get translationStatusProcessing => '処理中...';

  @override
  String translationStatsSuccessOnly(Object success, Object total) {
    return '成功: $success/$total';
  }

  @override
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total) {
    return '成功: $success/$total, 失敗: $fail/$total';
  }

  @override
  String translationStatsTotal(Object count) {
    return '合計: $count | ';
  }

  @override
  String translationStatsTranslated(Object count) {
    return '翻訳済み: $count | ';
  }

  @override
  String translationStatsPending(Object count) {
    return '保留中: $count';
  }

  @override
  String translationStatsExcluded(Object count) {
    return ' | 除外: $count';
  }

  @override
  String translationStatsRetryCount(Object count) {
    return ' | 再試行: $count';
  }

  @override
  String translationStatsCleared(Object count) {
    return ' | クリア済み: $count';
  }

  @override
  String translationStatsImages(Object count) {
    return ' | 画像: $count';
  }

  @override
  String translationStatsSegment(Object current, Object total) {
    return 'セグメント: $current / $total';
  }

  @override
  String get translationStatsDoubleClickToEdit => 'テキストをダブルクリックして編集。';

  @override
  String get translationStatsTranslatedLabel => '翻訳済み';

  @override
  String get translationStatsLoadingContent => 'コンテンツを読み込み中...';

  @override
  String get translationStatsNoContentAvailable => '利用可能なコンテンツがありません。';

  @override
  String get translationStatsNoSegmentsAvailable => '利用可能なセグメントがありません';

  @override
  String translationStatsTokenIn(Object count) {
    return '入力: $count';
  }

  @override
  String translationStatsTokenOut(Object count) {
    return '出力: $count';
  }

  @override
  String translationStatsTokenTotal(Object count) {
    return '($count)';
  }

  @override
  String get translationLangArabic => 'アラビア語';

  @override
  String get translationLangBengali => 'ベンガル語';

  @override
  String get translationLangCatalan => 'カタルーニャ語';

  @override
  String get translationLangChinese => '中国語';

  @override
  String get translationLangChineseTraditional => '中国語（繁体字）';

  @override
  String get translationLangCzech => 'チェコ語';

  @override
  String get translationLangCroatian => 'クロアチア語';

  @override
  String get translationLangDanish => 'デンマーク語';

  @override
  String get translationLangDutch => 'オランダ語';

  @override
  String get translationLangEnglish => '英語';

  @override
  String get translationLangFilipino => 'フィリピノ語';

  @override
  String get translationLangFinnish => 'フィンランド語';

  @override
  String get translationLangFrench => 'フランス語';

  @override
  String get translationLangGerman => 'ドイツ語';

  @override
  String get translationLangGreek => 'ギリシャ語';

  @override
  String get translationLangHebrew => 'ヘブライ語';

  @override
  String get translationLangHindi => 'ヒンディー語';

  @override
  String get translationLangItalian => 'イタリア語';

  @override
  String get translationLangJapanese => '日本語';

  @override
  String get translationLangKorean => '韓国語';

  @override
  String get translationLangKhmer => 'クメール語';

  @override
  String get translationLangLithuanian => 'リトアニア語';

  @override
  String get translationLangMacedonian => 'マケドニア語';

  @override
  String get translationLangMalay => 'マレー語';

  @override
  String get translationLangNorwegian => 'ノルウェー語（ブークモール）';

  @override
  String get translationLangPolish => 'ポーランド語';

  @override
  String get translationLangPortuguese => 'ポルトガル語';

  @override
  String get translationLangRomanian => 'ルーマニア語';

  @override
  String get translationLangRussian => 'ロシア語';

  @override
  String get translationLangSlovenian => 'スロベニア語';

  @override
  String get translationLangSpanish => 'スペイン語';

  @override
  String get translationLangSwedish => 'スウェーデン語';

  @override
  String get translationLangThai => 'タイ語';

  @override
  String get translationLangTurkish => 'トルコ語';

  @override
  String get translationLangUkrainian => 'ウクライナ語';

  @override
  String get translationLangUrdu => 'ウルドゥー語';

  @override
  String get translationLangVietnamese => 'ベトナム語';

  @override
  String get translationExportNoFormats => '利用可能なエクスポート形式がありません';

  @override
  String get translationExportDialogTitle => 'ドキュメントをエクスポート';

  @override
  String get translationExportFormatOptionsTitle => 'フォーマットオプション（PDFのみ）';

  @override
  String get translationExportTableFormatLabel => '表の形式:';

  @override
  String get translationExportTableFormatImage => '画像';

  @override
  String get translationExportTableFormatHtml => 'HTML';

  @override
  String get translationExportEquationFormatLabel => '数式の形式:';

  @override
  String get translationExportEquationFormatImage => '画像';

  @override
  String get translationExportEquationFormatLatex => 'LaTeX';

  @override
  String get translationLeftPanelExpandTooltip => '左パネルを展開';

  @override
  String get translationLeftPanelCollapseTooltip => '左パネルを折りたたむ';

  @override
  String get translationSnackGlossarySaved => '用語集を保存しました';

  @override
  String get translationSnackTranslationCancelled => '翻訳をキャンセルしました';

  @override
  String get translationSnackNoLlmpSelected => 'LLMプラットフォームが選択されていません';

  @override
  String get translationSnackTextEmpty => 'テキスト入力が空です。';

  @override
  String get translationSnackTextConverted => 'テキストをファイル形式に変換しました';

  @override
  String get translationSnackSourceResplitCompleted => 'ソースの再分割が完了しました';

  @override
  String get translationSnackPleaseSelectFileOrText =>
      'まずファイルを選択するか、テキストを入力してください';

  @override
  String get translationSnackPleaseSelectFileOrTextWithDot =>
      'まずファイルを選択するか、テキストを入力してください。';

  @override
  String get translationSnackPleaseSelectFile => 'まずファイルを選択してください';

  @override
  String get translationSnackPleaseSelectDocumentFirst => 'まずドキュメントを選択してください。';

  @override
  String get translationSnackGlossaryGenerated => '用語集が正常に生成されました！';

  @override
  String get translationSnackGlossaryGenerationCancelled => '用語集の生成がキャンセルされました';

  @override
  String get translationSnackGlossaryAppliedToTask => '用語集が翻訳タスクに適用されました';

  @override
  String get translationSnackPreviousTranslationCancelled => '前回の翻訳がキャンセルされました';

  @override
  String get translationSnackGlossarySavedAndApplied => '用語集を保存して適用しました';

  @override
  String get translationDialogMixedLangTitle => '複数の言語が検出されました';

  @override
  String translationDialogMixedLangContent(Object distribution) {
    return 'このドキュメントには複数の言語が含まれています:\n$distribution';
  }

  @override
  String get translationDialogMixedLangPromptTitle =>
      '翻訳品質を向上させるため、次のプロンプトを追加できます:';

  @override
  String get translationDialogMixedLangOption1Title => 'ソース言語のテキストのみを翻訳';

  @override
  String translationDialogMixedLangOption1Subtitle(Object languageName) {
    return '$languageName のテキストのみを翻訳します';
  }

  @override
  String get translationDialogMixedLangOption2Title => 'コードと技術用語を変更しない';

  @override
  String get translationDialogMixedLangOption2Subtitle =>
      'コードブロック、技術用語、関数名、および他言語のテキストを変更せずに保持します';

  @override
  String get translationDialogMixedLangCancel => 'キャンセル';

  @override
  String get translationDialogMixedLangSkip => 'スキップ';

  @override
  String get translationDialogMixedLangApply => '適用';

  @override
  String get translationSnackExportStarted => 'エクスポートタスクが開始されました。お待ちください。';

  @override
  String get translationSnackPromptUpdated => 'プロンプト指示が更新されました';

  @override
  String translationSnackFailedToCancel(Object error) {
    return 'キャンセルに失敗しました: $error';
  }

  @override
  String translationSnackFailedConvertTextFormat(Object error) {
    return 'テキスト形式の変換に失敗しました: $error';
  }

  @override
  String translationSnackFailedConvertText(Object error) {
    return 'テキストの変換に失敗しました: $error';
  }

  @override
  String translationSnackFailedResplit(Object error) {
    return '再分割に失敗しました: $error';
  }

  @override
  String get translationSnackRequestFailed => 'リクエストが失敗しました';

  @override
  String translationSnackFileImportFailed(Object error) {
    return 'ファイルのインポートに失敗しました: $error';
  }

  @override
  String translationSnackTaskStatus(Object status) {
    return 'タスクステータス: $status';
  }

  @override
  String translationSnackFileDownloaded(Object filename) {
    return 'ファイルをダウンロードしました: $filename';
  }

  @override
  String translationSnackFileSaved(Object filename) {
    return 'ファイルを保存しました: $filename';
  }

  @override
  String translationSnackFailedDownload(Object error, Object fileType) {
    return '$fileTypeのダウンロードに失敗しました: $error';
  }

  @override
  String translationSnackFailedOpenDownload(Object url) {
    return 'ダウンロードを開けませんでした: $url';
  }

  @override
  String get translationDialogSwitchToFileTitle => 'ファイルモードに切り替え';

  @override
  String get translationDialogSwitchToFileBody =>
      'ファイルモードに切り替えると、現在のテキスト入力がクリアされます。続行しますか？';

  @override
  String get translationDialogSwitchToTextTitle => 'テキストモードに切り替え';

  @override
  String get translationDialogSwitchToTextBody =>
      'テキストモードに切り替えると、現在のファイル選択がクリアされます。続行しますか？';

  @override
  String get translationSnackAllSegmentsExcludedSkipped =>
      'すべてのセグメントが除外されました。翻訳はスキップされます。書式変換のためにエクスポートを実行できます。';

  @override
  String get translationDialogCancelButton => 'キャンセル';

  @override
  String get translationDialogContinueButton => '続行';

  @override
  String get translationNoLlmAvailableTitle => '利用可能な LLM がありません';

  @override
  String get translationNoLlmAvailableMessage =>
      '設定済みで利用可能な LLM プラットフォームがありません。翻訳するには、設定で LLM の API Key を設定してください。形式変換のみの場合は続行できます。';

  @override
  String get translationNoLlmConfigureButton => 'LLM を設定';

  @override
  String get translationNoLlmContinueFormatOnlyButton => '形式変換のみ';

  @override
  String get languageMatchWarningTitle => '言語一致の確認';

  @override
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName) {
    return '検出された文書の言語（$detectedName）は目標言語（$targetName）と同じです。目標言語の選択が誤っている可能性があります。用語集の自動検出を続行しますか？';
  }

  @override
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName) {
    return '検出された文書の言語（$detectedName）は目標言語（$targetName）と同じです。目標言語の選択が誤っている可能性があります。翻訳を続行しますか？';
  }

  @override
  String get translationDialogCancelTaskTitle => '現在のタスクをキャンセル';

  @override
  String get translationDialogCancelTaskBody =>
      'これにより、現在の抽出/翻訳タスクがキャンセルされ、選択されたファイルがクリアされます。続行しますか？';

  @override
  String get translationDialogCancelTaskNo => 'いいえ';

  @override
  String get translationDialogCancelTaskYesCancel => 'はい、キャンセルします';

  @override
  String get translationQuickSettingsTitle => '翻訳クイック設定';

  @override
  String get quickSettingsTargetLanguage => 'ターゲット言語';

  @override
  String get quickSettingsSourceLanguage => 'ソース言語 (MinerU OCR)';

  @override
  String get quickSettingsLanguageSwitchDisabled =>
      '翻訳中は言語の切り替えが無効です。ターゲット言語を変更するには、抽出タブに切り替えてください。';

  @override
  String get quickSettingsParsingPlatform => '解析プラットフォーム';

  @override
  String get quickSettingsTestMineru => 'MinerU接続をテスト';

  @override
  String get quickSettingsNotConfigured => '未設定';

  @override
  String get quickSettingsApiOk => 'API OK';

  @override
  String get quickSettingsApiUnavailable => 'API利用不可';

  @override
  String get quickSettingsNotTestedYet => 'まだテストされていません';

  @override
  String get quickSettingsConnectionSuccessful => '接続成功';

  @override
  String get quickSettingsMineruConnectionFailed => 'MinerU接続失敗';

  @override
  String get quickSettingsOpenMineruSettings => 'MinerU設定を開く';

  @override
  String get quickSettingsMineruLabel => 'MinerU (mineru)';

  @override
  String get quickSettingsLlmPlatform => 'LLMプラットフォーム';

  @override
  String get quickSettingsTestLlmPlatform => '現在のLLMプラットフォームをテスト';

  @override
  String get quickSettingsTestFailed => 'テスト失敗';

  @override
  String get quickSettingsOpenAiPlatformsSettings => 'AIプラットフォーム設定を開く';

  @override
  String get quickSettingsTemperature => '温度';

  @override
  String get quickSettingsTemperatureHint => 'ランダム性を制御: 低い = より集中、高い = より創造的';

  @override
  String get quickSettingsQtTsOptions => 'Qt .ts翻訳オプション';

  @override
  String get quickSettingsQtTsSkipExisting => '既存の翻訳をスキップ';

  @override
  String get quickSettingsQtTsSkipExistingSubtitle => 'すでに翻訳があるメッセージをスキップ';

  @override
  String get quickSettingsQtTsTranslateUnfinished => '未完了のエントリを翻訳';

  @override
  String get quickSettingsQtTsTranslateUnfinishedSubtitle =>
      '未完了としてマークされたメッセージを翻訳 (type=\"unfinished\")';

  @override
  String get quickSettingsQtTsTranslateVanished => '消滅したエントリを翻訳';

  @override
  String get quickSettingsQtTsTranslateVanishedSubtitle =>
      '消滅としてマークされたメッセージを翻訳 (type=\"vanished\")';

  @override
  String get quickSettingsQtTsTranslateObsolete => '廃止されたエントリを翻訳';

  @override
  String get quickSettingsQtTsTranslateObsoleteSubtitle =>
      '廃止としてマークされたメッセージを翻訳 (type=\"obsolete\")';

  @override
  String get quickSettingsPrompt => 'プロンプト';

  @override
  String get quickSettingsPromptMode => 'プロンプトモード';

  @override
  String get quickSettingsPromptModeOff => 'オフ（プロンプトなし）';

  @override
  String get quickSettingsPromptModeSimple => 'シンプル（スタイルのみ）';

  @override
  String get quickSettingsPromptModeAdvanced => '詳細（スタイル＋注記）';

  @override
  String get quickSettingsStyle => 'スタイル';

  @override
  String get quickSettingsStyleLiteral => '逐語的';

  @override
  String get quickSettingsStyleFluent => '流暢';

  @override
  String get quickSettingsStyleAcademic => '学術的';

  @override
  String get quickSettingsStyleBusiness => 'ビジネス';

  @override
  String get quickSettingsStyleTechnical => '技術的';

  @override
  String get quickSettingsStyleNone => 'なし';

  @override
  String get quickSettingsTaskNoteLabel => 'タスク注記（短い指示）';

  @override
  String get quickSettingsTaskNoteHint => '例: 数式は変更しない；固有名詞に注釈を付ける';

  @override
  String get quickSettingsAdRegionF => '領域 F: クイック設定の下部\n(中長方形 300×250)';

  @override
  String quickSettingsPlatformMessage(Object label, Object message) {
    return '$label: $message';
  }

  @override
  String quickSettingsPlatformTestFailed(Object error, Object label) {
    return '$label: テスト失敗 — $error';
  }

  @override
  String get homeTagline => 'AIベース、没入型\nプライベート、セキュア（開発中）\nチーム共有、カスタマイズ可能\n';

  @override
  String get homeIntro => 'AIを活用した精度でドキュメントをアップロードし、複数の言語に翻訳します。\n';

  @override
  String get homeHowItWorks =>
      '仕組み\n翻訳: インポート -> ドキュメント解析 -> 用語集 -> 翻訳 -> エクスポート\nファイル形式変換: インポート -> ドキュメント解析 -> 変換 -> エクスポート\nURL取得: URL入力 -> ページ取得 -> コンテンツ解析 -> 本文抽出 -> 翻訳/エクスポート';

  @override
  String get homeSnackDonorExpired =>
      'お客様の登録コードの有効期限が切れています。Pro特典を継続するには、再登録してください。';

  @override
  String get commonCancel => 'キャンセル';

  @override
  String get commonOk => 'OK';

  @override
  String get homeAuthErrorTitle => '認証エラー';

  @override
  String get homeAuthRetryLogin => 'ログインを再試行';

  @override
  String homeAiPlatformsAvailable(Object platforms) {
    return '利用可能なAIプラットフォーム: $platforms';
  }

  @override
  String get homeAiPlatformsConfigureNotice =>
      'アプリを使用する前に、設定パネルでAIプラットフォームを構成してください。';

  @override
  String get homeBackendStatusStarting => 'バックエンドを起動中...';

  @override
  String get homeBackendStatusConnecting => 'バックエンドに接続中...';

  @override
  String get homeBackendStatusConnected => 'バックエンドに接続されました';

  @override
  String get homeBackendStatusDisconnected => 'バックエンドから切断されました。再試行してください。';

  @override
  String get homeBackendStatusUnknown => 'バックエンドに接続中...';

  @override
  String get homeBackendRetry => '再試行';

  @override
  String get homeNavTranslate => 'イマーシブタスク';

  @override
  String get homeNavTranslationQueue => 'タスク管理';

  @override
  String get homeNavAnonymize => '匿名化';

  @override
  String get homeNavSettings => '設定';

  @override
  String get homeNavDonateHelp => 'ヘルプ';

  @override
  String get homeNavDonate => '寄付';

  @override
  String get homeNavHome => 'ホーム';

  @override
  String get homeNavBatchUpload => '一括アップロード';

  @override
  String get batchUploadTitle => '一括ファイルアップロード';

  @override
  String get batchUploadFormatConvert => '形式変換';

  @override
  String get batchUploadSelectSourceHint =>
      '翻訳するファイルを選択してください。各ファイルはキュー内のタスクになります。';

  @override
  String get batchUploadSelectFolder => 'フォルダを選択';

  @override
  String get batchUploadFolderDescription => '翻訳するファイルが入ったフォルダを選択';

  @override
  String get batchUploadSelectZip => 'ZIPアーカイブを選択';

  @override
  String get batchUploadZipDescription => '翻訳するファイルが入ったZIPアーカイブを選択';

  @override
  String get batchUploadSelectSingleFile => 'ファイルを選択';

  @override
  String batchUploadFilesFound(Object count) {
    return '$count 個のサポートされているファイルが見つかりました';
  }

  @override
  String get batchUploadSelectAll => 'すべて選択';

  @override
  String get batchUploadDeselectAll => 'すべて解除';

  @override
  String get batchUploadStartTranslation => '翻訳を開始';

  @override
  String get batchUploadSubmitting => 'ファイルを送信中...';

  @override
  String batchUploadProgress(Object completed, Object total) {
    return '$completed/$total ファイル送信済み';
  }

  @override
  String get batchUploadCompleteTitle => '一括完了';

  @override
  String batchUploadComplete(Object success, Object failed) {
    return '$success 成功、$failed 失敗';
  }

  @override
  String get batchUploadNoSupportedFiles => 'サポートされているファイルが見つかりません';

  @override
  String batchUploadSelectedCount(Object count) {
    return '$count ファイル選択済み';
  }

  @override
  String batchUploadLegacyFormatsFound(Object files) {
    return '$files は直接翻訳できません。.doc を .docx、.ppt を .pptx、.xls を .xlsx に変換してから送信してください。';
  }

  @override
  String batchUploadLegacyFormatsSkipped(Object count) {
    return '$count ファイルをスキップしました（レガシー形式は直接サポートされていません）。.doc→.docx、.ppt→.pptx、.xls→.xlsx に変換してから再試行してください。';
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
  String get batchUploadConfirmLangTitle => '対象言語を確認';

  @override
  String batchUploadConfirmLangMessage(Object lang) {
    return '対象言語は「$lang」です。続行しますか？';
  }

  @override
  String get batchUploadConvert => '変換';

  @override
  String get batchUploadTranslate => '翻訳';

  @override
  String get batchUploadFolderPickerTitle => '翻訳するファイルが入ったフォルダを選択';

  @override
  String get batchUploadZipPickerTitle => '翻訳するファイルが入ったZIPアーカイブを選択';

  @override
  String batchUploadScanFolderError(Object error) {
    return 'フォルダのスキャンに失敗しました：$error';
  }

  @override
  String batchUploadReadZipError(Object error) {
    return 'ZIPアーカイブの読み取りに失敗しました：$error';
  }

  @override
  String get batchUploadGlossarySection => '用語集';

  @override
  String batchUploadGlossaryMore(Object count) {
    return '+$count';
  }

  @override
  String batchUploadGlossaryLoadError(Object error) {
    return 'エラー：$error';
  }

  @override
  String get batchUploadNoGlossaries => '利用可能な用語集がありません';

  @override
  String get batchUploadMineru => 'MinerU';

  @override
  String get batchUploadMineruLocal => 'MinerU ローカル';

  @override
  String get commonClose => '閉じる';

  @override
  String get translationQueueTitle => 'タスクキュー';

  @override
  String get translationQueueHint => 'タスクは自動更新されます。完了後にダウンロードできます。';

  @override
  String get translationQueueCancelExitHint =>
      'キュー待ちまたは実行中は「キャンセル」で停止できます。確認後にホームに戻ります。';

  @override
  String get translationQueueCancelDialogTitle => 'この翻訳タスクをキャンセルしますか？';

  @override
  String get translationQueueCancelDialogMessage =>
      'キュー待ちはキューから削除され、実行中は中止されます。確認後にホームへ戻ります。';

  @override
  String get translationQueueCancelDialogKeep => '維持';

  @override
  String get translationQueueCancelDialogConfirm => 'キャンセルする';

  @override
  String get translationQueueEmpty => '翻訳タスクはありません。';

  @override
  String get translationQueueNewQueuedTask => 'キュー式タスク';

  @override
  String get translationQueueBackToQueueTooltip => 'タスクキューに戻る';

  @override
  String get translationQueuedStarted => 'キューに追加しました。ここで進捗を確認できます。';

  @override
  String get translationQueueRefresh => '更新';

  @override
  String get translationQueueCancel => 'キャンセル';

  @override
  String get translationQueueRelease => '一覧から削除';

  @override
  String get translationQueueDownloads => 'ダウンロード';

  @override
  String get translationQueueDownloadMdEmbedded => 'MD（埋め込み）';

  @override
  String get translationQueueDownloadMdZip => 'MD（ZIP）';

  @override
  String get translationQueueExecutionModeQueued => 'キュー';

  @override
  String get translationQueueExecutionModeImmediate => '即時';

  @override
  String get translationQueueTaskTypeTranslation => '翻訳';

  @override
  String get translationQueueTaskTypeConversion => '変換';

  @override
  String translationQueuePositionLabel(Object position) {
    return 'キュー順 #$position';
  }

  @override
  String translationQueueLoadFailed(Object error) {
    return 'タスクの読み込みに失敗しました: $error';
  }

  @override
  String translationQueueActionFailed(Object error) {
    return '操作に失敗しました: $error';
  }

  @override
  String translationQueueSubmittedBy(Object user) {
    return '開始ユーザー: $user';
  }

  @override
  String translationQueueStartedAt(Object time) {
    return '開始: $time';
  }

  @override
  String translationQueueCompletedAt(Object time) {
    return '完了: $time';
  }

  @override
  String get translationQueueTimeUnknown => '—';

  @override
  String get translationQueueGuestUser => 'ゲスト';

  @override
  String get translationQueueClearAllTooltip => 'タスクキューとサーバー側キャッシュをクリア（管理者のみ）';

  @override
  String get translationQueueClearAllButton => 'キューをクリア';

  @override
  String get translationQueueClearAllTitle => 'タスクキューをクリア';

  @override
  String get translationQueueClearAllMessage =>
      'キュー待ちと実行中のタスクをキャンセルし、メモリ上のタスクとディスクのキュースナップショットを削除します。元に戻せません。';

  @override
  String get translationQueueClearAllConfirm => 'クリア';

  @override
  String get translationQueueClearAllCancel => 'キャンセル';

  @override
  String get translationQueueClearAllSuccess => 'タスクキューをクリアしました。';

  @override
  String translationQueueClearAllFailed(Object error) {
    return 'クリアに失敗しました: $error';
  }

  @override
  String get translationQueueClearMyQueueTooltip => '自分のキューをクリア';

  @override
  String get translationQueueClearMyQueueTitle => '自分のキューをクリア';

  @override
  String get translationQueueClearMyQueueMessage => 'すべてのタスクをキューから削除しますか？';

  @override
  String get translationQueueClearMyQueueConfirm => 'クリア';

  @override
  String get translationQueueClearMyQueueCancel => 'キャンセル';

  @override
  String get translationQueueClearMyQueueSuccess => '自分のキューをクリアしました。';

  @override
  String translationQueueClearMyQueueFailed(Object error) {
    return 'キューのクリアに失敗しました: $error';
  }

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
  String get translationQueueView => '閲覧編集';

  @override
  String get homeFeatureUnderDevelopment => 'この機能は開発中です。';

  @override
  String homeAnonymizeNotSupportedVersion(Object version) {
    return 'まだサポートされていません。v$versionで利用可能になります。';
  }

  @override
  String get homeAnonymizeInDevelopment => '匿名化は開発中で、まだ利用できません。';

  @override
  String get homeScrollLeft => '左にスクロール';

  @override
  String get homeScrollRight => '右にスクロール';

  @override
  String get homeTabHome => 'ホーム';

  @override
  String get homeToolbarAdBanner =>
      'ツールバー広告バナー\n(728×90 リーダーボード / 320×50 モバイル)';

  @override
  String get homeSteps => 'ステップ';

  @override
  String get homePhaseUpload => 'アップロード';

  @override
  String get homePhaseExtract => '抽出';

  @override
  String get homePhaseGlossary => '用語集';

  @override
  String get homePhaseTranslate => '翻訳';

  @override
  String get homePhaseViewer => 'ビューア';

  @override
  String get homePhaseAnonymize => '匿名化';

  @override
  String get homePhaseDeAnonymize => '匿名化解除';

  @override
  String get homePhaseExport => 'エクスポート';

  @override
  String get homeReleaseNotesTitle => 'リリースノート';

  @override
  String get homeReleaseNotesViewOnGitHub => 'GitHubで見る';

  @override
  String get homeEditionEnterprise => 'エンタープライズ';

  @override
  String get homeEditionEnterpriseStatusActivated => 'アクティベート済み';

  @override
  String get homeEditionActivateEnterprise => 'エンタープライズを有効化';

  @override
  String get homeEditionPro => 'プロ';

  @override
  String get homeEditionStandard => 'スタンダード';

  @override
  String get homeEditionStandardStatus => '常に利用可能';

  @override
  String homeEditionProStatusTrialRemaining(Object days) {
    return 'あと$days日';
  }

  @override
  String get homeEditionProStatusNotActivated => '未アクティベート';

  @override
  String get homeEditionProStatusActivated => 'アクティベート済み';

  @override
  String get homeWelcomeDearPro =>
      '没入型翻訳：画面上で原文と訳文をすぐ対照します。\nキュー翻訳：ドキュメントをキューに追加し、順にパイプラインを実行します。';

  @override
  String get homeWelcomeDearStandard =>
      '没入型翻訳：画面上で原文と訳文をすぐ対照します。\nキュー翻訳：ドキュメントをキューに追加し、順にパイプラインを実行します。';

  @override
  String get homeWelcomeDearProNoUser =>
      '没入型翻訳：画面上で原文と訳文をすぐ対照します。\nキュー翻訳：ドキュメントをキューに追加し、順にパイプラインを実行します。';

  @override
  String get homeWelcomeDearStandardNoUser =>
      '没入型翻訳：画面上で原文と訳文をすぐ対照します。\nキュー翻訳：ドキュメントをキューに追加し、順にパイプラインを実行します。';

  @override
  String get homeWelcomeHello =>
      '没入型翻訳：画面上で原文と訳文をすぐ対照します。\nキュー翻訳：ドキュメントをキューに追加し、順にパイプラインを実行します。';

  @override
  String get homeLoading => '読み込み中...';

  @override
  String get homeWelcomeGuest => 'ようこそ！';

  @override
  String homeFileNotFound(Object fileName) {
    return 'ファイルが見つかりません: $fileName。ファイルが移動または削除された可能性があります。';
  }

  @override
  String homeFileSelectedMismatch(Object expected, Object selected) {
    return '選択されたファイル名が一致しません: $selected。期待値: $expected';
  }

  @override
  String homeFileLoaded(Object fileName) {
    return 'ファイルを読み込みました: $fileName';
  }

  @override
  String get homeFileSelectionCancelled => 'ファイル選択がキャンセルされました。';

  @override
  String homeFileLoadFailed(Object error) {
    return 'ファイルの読み込みに失敗しました: $error';
  }

  @override
  String homeFlowCreateFailed(Object error) {
    return 'フローの作成に失敗しました: $error';
  }

  @override
  String commonPageNotFound(Object uri) {
    return 'ページが見つかりません: $uri';
  }

  @override
  String get commonGoHome => 'ホームに戻る';

  @override
  String get commonLogin => 'ログイン';

  @override
  String get commonLogout => 'ログアウト';

  @override
  String get userMenuChangePassword => 'パスワードを変更';

  @override
  String get changePasswordCurrentPasswordLabel => '現在のパスワード';

  @override
  String get changePasswordNewPasswordLabel => '新しいパスワード';

  @override
  String get changePasswordConfirmPasswordLabel => '新しいパスワード（確認）';

  @override
  String get changePasswordRequiredError => '現在のパスワードと新しいパスワードは必須です。';

  @override
  String get changePasswordConfirmMismatchError => '新しいパスワードが一致しません。';

  @override
  String get changePasswordSuccessMessage => 'パスワードを変更しました。';

  @override
  String get changePasswordRequirementsTitle => 'パスワード要件';

  @override
  String get changePasswordRequirementLength => '8〜128文字';

  @override
  String get changePasswordRequirementUppercase => '大文字を1文字以上';

  @override
  String get changePasswordRequirementLowercase => '小文字を1文字以上';

  @override
  String get changePasswordRequirementDigit => '数字を1文字以上';

  @override
  String get settingsTabsGeneral => '一般';

  @override
  String get settingsTabsAiPlatforms => 'AIプラットフォーム';

  @override
  String get settingsTabsParsingEngine => '解析エンジン';

  @override
  String get settingsParsingEngineTitle => '解析エンジン';

  @override
  String get settingsParsingEngineSubtitle =>
      'テキスト抽出と処理のためのドキュメント解析エンジンを選択します。';

  @override
  String get settingsParsingEngineLabel => '解析エンジン';

  @override
  String get settingsParsingEngineMineru => 'MinerU (クラウド)';

  @override
  String get settingsParsingEngineMineruDesc => 'OCRサポート付きの高度なドキュメント解析';

  @override
  String get settingsParsingEngineMineruLocal => 'MinerU (ローカル)';

  @override
  String get settingsParsingEngineMineruLocalDesc => 'セルフホスト MinerU、APIキー任意';

  @override
  String get settingsParsingEnginePdfplumber => 'PDFPlumber';

  @override
  String get settingsParsingEnginePdfplumberDesc => '高速なPDFテキスト抽出';

  @override
  String get settingsParsingEngineTesseract => 'Tesseract OCR';

  @override
  String get settingsParsingEngineTesseractDesc => 'OCRベースのテキスト抽出';

  @override
  String get settingsFormulaOcr => '数式OCR';

  @override
  String get settingsFormulaOcrSubtitle => '数学的数式のOCRを有効にします';

  @override
  String get settingsTableOcr => '表OCR';

  @override
  String get settingsTableOcrSubtitle => '表のOCRを有効にします';

  @override
  String get settingsAnonymizationNewTaskNotice => '変更は新規タスクにのみ適用されます';

  @override
  String get settingsParsingEngineNewTaskNotice => '変更は新規タスクにのみ適用されます';

  @override
  String get settingsPdfSplitMaxPages => 'PDF分割最大ページ数';

  @override
  String get settingsPdfSplitMaxWorkers => 'PDF分割並列数';

  @override
  String get settingsRequestRetryCount => 'リクエスト再試行回数';

  @override
  String get settingsOcrLanguageTitle => 'OCR言語';

  @override
  String get settingsOcrLanguageSubtitle => '画像やスキャン文書内のテキスト認識用のOCR言語を設定します。';

  @override
  String get settingsOcrLanguageLabel => 'OCR言語';

  @override
  String get settingsOcrLangEnglish => '英語';

  @override
  String get settingsOcrLangChineseSimplified => '中国語（簡体字）';

  @override
  String get settingsOcrLangChineseTraditional => '中国語（繁体字）';

  @override
  String get settingsOcrLangJapanese => '日本語';

  @override
  String get settingsOcrLangKorean => '韓国語';

  @override
  String get settingsOcrLangFrench => 'フランス語';

  @override
  String get settingsOcrLangGerman => 'ドイツ語';

  @override
  String get settingsOcrLangSpanish => 'スペイン語';

  @override
  String get settingsOcrLangRussian => 'ロシア語';

  @override
  String get settingsOcrLangArabic => 'アラビア語';

  @override
  String get settingsOcrLangAuto => '自動検出';

  @override
  String get mineruLangAuto => '自動検出';

  @override
  String get mineruLangChServer => '中国語（サーバー）';

  @override
  String get mineruLangChLite => '中国語（ライト）';

  @override
  String get mineruLangTamil => 'タミル語';

  @override
  String get mineruLangTelugu => 'テルグ語';

  @override
  String get mineruLangKannada => 'カンナダ語';

  @override
  String get mineruLangLatinScript => 'ラテン文字';

  @override
  String get mineruLangArabicScript => 'アラビア文字';

  @override
  String get mineruLangEastSlavic => '東スラブ語';

  @override
  String get mineruLangCyrillicScript => 'キリル文字';

  @override
  String get mineruLangDevanagariScript => 'デーヴァナーガリー文字';

  @override
  String get settingsTabsGlossary => '用語集';

  @override
  String get settingsGlossaryManagementTitle => '用語集管理';

  @override
  String get settingsGlossaryManagementSubtitle => '一貫した翻訳品質のための用語エントリを管理します。';

  @override
  String get settingsGlossarySelectGlossary => '用語集を選択';

  @override
  String get settingsGlossaryCreateGlossary => '作成';

  @override
  String get settingsGlossaryImportCsv => 'インポート';

  @override
  String get settingsGlossaryExport => 'エクスポート';

  @override
  String get settingsGlossaryExportAll => 'すべてエクスポート';

  @override
  String get settingsGlossaryDeleteGlossary => '削除';

  @override
  String get settingsGlossarySaveZip => 'ZIPを保存';

  @override
  String settingsGlossaryEntriesTitle(Object count) {
    return '用語集エントリ（$count）';
  }

  @override
  String get settingsGlossaryAddEntry => 'エントリを追加';

  @override
  String get settingsGlossaryNoEntriesYet =>
      '用語集エントリはまだありません。\n最初のエントリを追加して始めましょう。';

  @override
  String get settingsGlossaryFilterLabel => 'フィルター：';

  @override
  String get settingsGlossaryFilterAll => 'すべて';

  @override
  String get settingsGlossaryFilterUncategorized => '未分類';

  @override
  String get settingsGlossaryTableSource => '原文';

  @override
  String get settingsGlossaryTableTarget => '訳文';

  @override
  String get settingsGlossaryTableCategory => 'カテゴリ（オプション）';

  @override
  String get settingsGlossaryTableTargetLang => 'ターゲット言語';

  @override
  String get settingsGlossaryCategoryHint => 'カテゴリ';

  @override
  String get settingsGlossaryUncategorizedDisplay => '（未分類）';

  @override
  String get settingsGlossaryCopyAction => 'コピー';

  @override
  String get settingsGlossaryCopiedToClipboard => 'クリップボードにコピーしました';

  @override
  String get settingsGlossaryDeleteDialogTitle => '用語集を削除';

  @override
  String settingsGlossaryDeleteDialogMessage(Object id) {
    return 'この用語集を削除してもよろしいですか？\nID：$id';
  }

  @override
  String get settingsGlossaryCancel => 'キャンセル';

  @override
  String get settingsGlossaryDelete => '削除';

  @override
  String get settingsGlossaryCreateDialogTitle => '用語集を作成';

  @override
  String get settingsGlossaryNameLabel => '名前';

  @override
  String get settingsGlossaryDescriptionLabel => '説明（オプション）';

  @override
  String get settingsGlossaryGlobalGlossary => 'グローバル用語集';

  @override
  String get settingsGlossaryGlobalGlossarySubtitle => 'オフの場合、個人用語集になります';

  @override
  String get settingsGlossaryCreate => '作成';

  @override
  String get settingsGlossaryNameRequired => '名前は必須です';

  @override
  String settingsGlossaryCreatedSnack(Object name) {
    return '作成しました：$name';
  }

  @override
  String settingsGlossaryCreateFailedSnack(Object error) {
    return '作成失敗：$error';
  }

  @override
  String get settingsGlossaryAddEntryDialogTitle => '用語集にエントリを追加';

  @override
  String get settingsGlossarySourceTextLabel => '原文テキスト';

  @override
  String get settingsGlossaryTargetTextLabel => '訳文テキスト';

  @override
  String get settingsGlossaryCategoryOptionalLabel => 'カテゴリ（オプション）';

  @override
  String get settingsGlossaryCategoryOptionalHint => '未分類の場合は空のままにします';

  @override
  String get settingsGlossaryAdd => '追加';

  @override
  String get settingsGlossarySourceTargetRequired => '原文テキストと訳文テキストは必須です';

  @override
  String get settingsGlossaryEntryAddedSnack => 'エントリを追加しました';

  @override
  String settingsGlossaryAddFailedSnack(Object error) {
    return '失敗：$error';
  }

  @override
  String get settingsGlossaryImportDialogTitle => 'CSV/TBXを用語集にインポート';

  @override
  String get settingsGlossaryMergeModeLabel => 'マージモード';

  @override
  String get settingsGlossaryMergeUpdate => '更新（アップサート）';

  @override
  String get settingsGlossaryMergeAppend => '追加（新規のみ）';

  @override
  String get settingsGlossaryMergeReplace => '置換（すべて上書き）';

  @override
  String get settingsGlossaryImport => 'インポート';

  @override
  String get settingsGlossaryUnableToReadFile => 'ファイルを読み取れません';

  @override
  String settingsGlossaryImportedSnack(Object count) {
    return 'インポートしました：$count項目';
  }

  @override
  String settingsGlossaryImportFailedSnack(Object error) {
    return '失敗：$error';
  }

  @override
  String get settingsGlossaryExportDialogTitle => '用語集をエクスポート';

  @override
  String get settingsGlossarySaveCsv => 'CSV/TBXを保存';

  @override
  String get settingsGlossaryDownload => 'ダウンロード';

  @override
  String settingsGlossaryDownloadedSnack(Object info) {
    return 'ダウンロードしました：$info';
  }

  @override
  String settingsGlossaryExportFailedSnack(Object error) {
    return '失敗：$error';
  }

  @override
  String settingsGlossaryLoadedSnack(Object count) {
    return '$countエントリを読み込みました';
  }

  @override
  String settingsGlossaryLoadFailedSnack(Object error) {
    return '読み込み失敗：$error';
  }

  @override
  String settingsGlossaryDeletedSnack(Object id) {
    return '用語集を削除しました：$id';
  }

  @override
  String settingsGlossaryDeleteFailedSnack(Object error) {
    return '削除失敗：$error';
  }

  @override
  String settingsGlossaryExportAllFailedSnack(Object error) {
    return 'すべてのエクスポート失敗：$error';
  }

  @override
  String get settingsGlossaryEntryUpdatedSnack => 'エントリを更新しました';

  @override
  String settingsGlossaryUpdateFailedSnack(Object error) {
    return '更新失敗：$error';
  }

  @override
  String get settingsGlossaryEntryDeletedSnack => 'エントリを削除しました';

  @override
  String settingsGlossaryDeleteEntryFailedSnack(Object error) {
    return '削除失敗：$error';
  }

  @override
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type) {
    return '$name（$type）・$count項目';
  }

  @override
  String settingsGlossaryErrorPrefix(Object error) {
    return 'エラー：$error';
  }

  @override
  String settingsGlossaryExportedAllSnack(Object info) {
    return 'エクスポートしました：$info';
  }

  @override
  String settingsGlossaryEntryCount(Object count) {
    return 'エントリ数：$count';
  }

  @override
  String get settingsGlossaryEdit => '編集';

  @override
  String get settingsGlossaryConfirmDeleteEntryTitle => '削除の確認';

  @override
  String settingsGlossaryConfirmDeleteEntryMessage(Object source) {
    return 'エントリ「$source」を削除しますか？';
  }

  @override
  String get settingsGlossaryEditEntryDialogTitle => 'エントリを編集';

  @override
  String get settingsGlossaryUpdate => '更新';

  @override
  String get settingsGlossaryEntryDeleteFailedSnack => 'エントリの削除に失敗しました';

  @override
  String get settingsGlossaryEmptyStateTitle => '用語集がまだありません。最初の用語集を作成してください。';

  @override
  String get settingsGlossaryTooltipCreate => '新しい用語集を作成';

  @override
  String get settingsGlossaryTooltipImport => 'CSV または TBX 形式からエントリをインポート';

  @override
  String get settingsGlossaryTooltipExport => '選択した用語集を CSV または TBX 形式でエクスポート';

  @override
  String get settingsGlossaryTooltipExportAll => 'すべての用語集を ZIP アーカイブとしてエクスポート';

  @override
  String get settingsGlossaryTooltipDeleteGlossary => '選択した用語集を完全に削除';

  @override
  String get settingsGlossaryBatchEditCategory => 'カテゴリを編集';

  @override
  String get settingsGlossaryBatchDelete => '削除';

  @override
  String get settingsGlossaryBatchDeselect => '選択解除';

  @override
  String settingsGlossaryBatchSelectedCount(Object count) {
    return '$count 件選択中';
  }

  @override
  String get settingsGlossaryExportFormatLabel => 'エクスポート形式';

  @override
  String get settingsGlossaryExportFormatCsv => 'CSV';

  @override
  String get settingsGlossaryExportFormatTbx => 'TBX（TermBase eXchange）';

  @override
  String get settingsGlossaryExportSourceLanguage => 'ソース言語';

  @override
  String get settingsGlossaryExportSaveTbxTitle => 'TBX ファイルを保存';

  @override
  String get settingsGlossaryDeleteEntriesTitle => 'エントリを削除';

  @override
  String settingsGlossaryDeleteEntriesBody(Object count) {
    return '選択した $count 件のエントリを削除しますか？この操作は元に戻せません。';
  }

  @override
  String get settingsGlossaryDeleteEntriesConfirm => '削除';

  @override
  String get settingsGlossaryEditCategoryTitle => 'カテゴリを編集';

  @override
  String settingsGlossaryEditCategoryBody(Object count) {
    return '選択した $count 件のエントリのカテゴリを設定：';
  }

  @override
  String get settingsGlossaryEditCategoryLabel => 'カテゴリ';

  @override
  String get settingsGlossaryEditCategoryHint => 'カテゴリ名を入力';

  @override
  String get settingsGlossaryEditCategoryApply => '適用';

  @override
  String get glossaryPanelSaveNameHint => '名前を入力するか、既存の用語集を選択...';

  @override
  String get glossaryPanelClearSelection => '選択をクリア';

  @override
  String get glossaryPanelListTitle => '用語集';

  @override
  String get glossaryPanelNoEntries => 'エントリなし';

  @override
  String get glossaryPanelOneEntry => '1 件';

  @override
  String glossaryPanelEntriesCount(Object count) {
    return '$count 件';
  }

  @override
  String get glossaryPanelProcessing => '処理中...';

  @override
  String get glossaryPanelDropCsvHere => 'CSV または TBX ファイルをここにドロップ';

  @override
  String get glossaryPanelNoEntriesHint =>
      '用語集エントリがありません。\n「用語集を検出」ボタンをクリックして開始するか、リストから用語集を選択してエントリを表示するか、CSV または TBX ファイルをここにドラッグ＆ドロップしてください。';

  @override
  String get glossaryPanelSelectBody => '操作する用語集を選択：';

  @override
  String get glossaryPanelSaveDialogTitleReplace => '用語集を置換';

  @override
  String get glossaryPanelSaveDialogTitleSave => '用語集を保存';

  @override
  String glossaryPanelSaveReplaceInfo(Object name) {
    return '既存の用語集 \"$name\" を置換します';
  }

  @override
  String get glossaryPanelSaveButtonSaveAs => '名前を付けて保存';

  @override
  String get glossaryPanelGenerating => '用語集を生成中...';

  @override
  String get glossaryPanelDeleteEntry => 'エントリを削除';

  @override
  String get glossaryPanelInvertSelection => '選択を反転';

  @override
  String get glossaryWidgetTitle => '用語集';

  @override
  String get glossaryWidgetRefreshTooltip => '用語集リストを更新';

  @override
  String glossaryWidgetGlossariesSelected(Object count) {
    return '$count 件の用語集を選択中';
  }

  @override
  String glossaryWidgetGlossariesSelectedPlural(Object count) {
    return '$count 件の用語集を選択中';
  }

  @override
  String get glossaryWidgetSelectGlossaries => '用語集を選択';

  @override
  String glossaryWidgetLoadFailed(Object error) {
    return '用語集の読み込みに失敗：$error';
  }

  @override
  String get glossaryWidgetNoGlossariesHint => '用語集がありません。設定 -> 用語集で作成してください。';

  @override
  String glossaryWidgetTypeCountItems(Object type, Object count) {
    return '$type · $count 件';
  }

  @override
  String glossaryWidgetTermsExtracted(Object count) {
    return '翻訳から $count 用語を抽出';
  }

  @override
  String glossaryWidgetPersonalCreated(Object count) {
    return '個人用語集を作成しました！\n$count 用語を追加しました。';
  }

  @override
  String glossaryWidgetPersonalReplaced(Object total) {
    return '個人用語集を置換しました！\n合計 $total 用語。';
  }

  @override
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total) {
    return '個人用語集に $newCount 件の新規用語を追加しました。\n$skipped 件の既存用語をスキップ。\n合計 $total 用語。';
  }

  @override
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total) {
    return '個人用語集を更新しました！\n$newCount 件を追加、$updatedCount 件を更新。\n合計 $total 用語。';
  }

  @override
  String glossaryWidgetAddToPersonalFailed(Object error) {
    return '個人用語集への追加に失敗：$error';
  }

  @override
  String get settingsTabsTranslation => '翻訳';

  @override
  String get settingsTabsAnonymization => '匿名化';

  @override
  String get settingsTabsUserManagement => 'ユーザー管理';

  @override
  String get settingsUserManagementTitle => 'ユーザー管理モード';

  @override
  String get settingsUserManagementSubtitle =>
      'Web 配備時のログイン・権限ポリシーを選択。設定と設定ウィザードは管理者のみ。';

  @override
  String get settingsUserManagementModeNoLogin => 'ログイン不要';

  @override
  String get settingsUserManagementModeNoLoginDesc =>
      'ログインせずに利用。設定・設定ウィザードは管理者ログイン後のみ。';

  @override
  String get settingsUserManagementModeLdap => 'LDAP ログイン';

  @override
  String get settingsUserManagementModeLdapDesc =>
      'LDAP/AD でログイン。設定・設定ウィザードは管理者（ドメイングループ）のみ。';

  @override
  String get settingsUserManagementModeLocal => 'ローカルユーザー';

  @override
  String get settingsUserManagementModeLocalDesc => 'サーバー上のローカルユーザーリストで認証。';

  @override
  String get settingsUserManagementInDevelopment => '開発中';

  @override
  String get settingsUserManagementSaveSuccess => 'ユーザー管理モードを保存しました';

  @override
  String settingsUserManagementSaveFailed(Object message) {
    return '保存に失敗しました: $message';
  }

  @override
  String get settingsLdapEnabled => 'LDAP ログインを有効にする';

  @override
  String get settingsLdapEnableHint => '有効にする前に「LDAP 接続テスト」を実行してください。';

  @override
  String get settingsLdapProtocol => 'プロトコル';

  @override
  String get settingsLdapProtocolLdap => 'LDAP';

  @override
  String get settingsLdapProtocolLdaps => 'LDAPS';

  @override
  String get settingsLdapHost => 'LDAP サーバー（証明書 CN/SAN に一致）';

  @override
  String get settingsLdapHostPlaceholder => 'ad.example.com または 192.168.x.x';

  @override
  String get settingsLdapPort => 'ポート';

  @override
  String get settingsLdapPortPlaceholder => '389';

  @override
  String get settingsLdapBaseDn => 'ユーザー検索 Base DN';

  @override
  String get settingsLdapBaseDnPlaceholder => 'OU=Users,DC=example,DC=com';

  @override
  String get settingsLdapBindDnTemplate => 'バインド DN テンプレート';

  @override
  String settingsLdapBindDnPlaceholder(Object username) {
    return 'EXAMPLE\\$username または $username@example.com';
  }

  @override
  String get settingsLdapUserFilter => 'ユーザーフィルタ';

  @override
  String settingsLdapUserFilterPlaceholder(Object username) {
    return '(sAMAccountName=$username)';
  }

  @override
  String get settingsLdapAdminGroupEnabled => '管理者グループ検索を有効にする';

  @override
  String get settingsLdapAdminGroup => '管理者グループ名';

  @override
  String get settingsLdapAdminGroupPlaceholder => 'Owlangs-Admins';

  @override
  String get settingsLdapGroupBaseDn => 'グループ検索 Base DN';

  @override
  String get settingsLdapGroupBaseDnPlaceholder =>
      'OU=Groups,DC=example,DC=com';

  @override
  String get settingsLdapTlsVerify => 'TLS 証明書を検証';

  @override
  String get settingsLdapTlsCacertfile => 'TLS CA 証明書ファイルパス';

  @override
  String get settingsLdapTlsCacertfilePlaceholder => '/path/to/ca.crt';

  @override
  String get settingsLdapTestConnection => 'LDAP 接続をテスト';

  @override
  String get settingsLdapSaveConfig => 'LDAP 設定を保存';

  @override
  String get settingsLdapTestDialogTitle => 'LDAP 接続をテスト';

  @override
  String get settingsLdapTestUsername => 'ユーザー名（ドメインなし）';

  @override
  String get settingsLdapTestUsernamePlaceholder => 'testuser';

  @override
  String get settingsLdapTestPassword => 'パスワード';

  @override
  String get settingsLdapTestPasswordPlaceholder => '********';

  @override
  String get settingsLdapTestStart => 'テスト開始';

  @override
  String get settingsLdapTestSuccess => 'LDAP 接続テストに成功しました。LDAP を有効にできます。';

  @override
  String get settingsLdapTestFailed => 'LDAP 接続テストに失敗しました';

  @override
  String get settingsLdapConfigSaved => 'LDAP 設定を保存しました';

  @override
  String get settingsLdapEnableRequireTest =>
      'LDAP を有効にする前に、LDAP 接続テストを実行してください。';

  @override
  String get settingsAdminOnlyDialogTitle => '管理者のみ';

  @override
  String get settingsAdminOnlyDialogMessage =>
      '設定と設定ウィザードは管理者のみ利用できます。管理者アカウントでログインしてください。';

  @override
  String get settingsAdminOnlyDialogGoToLogin => 'ログイン';

  @override
  String get settingsAdminOnlyDialogClose => '閉じる';

  @override
  String get aiPlatformOverview => 'プラットフォーム概要';

  @override
  String aiPlatformConfiguredCount(Object configured, Object total) {
    return '設定済み $configured/$total プラットフォーム';
  }

  @override
  String get aiPlatformTestApiStatus => 'APIステータスをテスト';

  @override
  String get aiPlatformTesting => 'テスト中...';

  @override
  String get aiPlatformCategoryLanguageModels => '言語モデル';

  @override
  String get aiPlatformCategoryParsingEngines => '解析エンジン';

  @override
  String aiPlatformConfiguredDragReorder(Object configured, Object total) {
    return '設定済み $configured/$total プラットフォーム（ドラッグで順序変更）';
  }

  @override
  String get aiPlatformNotConfigured => '未設定';

  @override
  String get aiPlatformNotTested => '未テスト';

  @override
  String get aiPlatformApiAvailable => 'API利用可能';

  @override
  String get aiPlatformAvailable => '利用可能';

  @override
  String get aiPlatformUnavailable => '利用不可';

  @override
  String get aiPlatformConfigure => '設定';

  @override
  String aiPlatformConfigureTitle(Object name) {
    return '$nameを設定';
  }

  @override
  String get aiPlatformBasicInformation => '基本情報';

  @override
  String get aiPlatformPlatformName => 'プラットフォーム名';

  @override
  String get aiPlatformPlatformNameHint => '例：豆包（DeepSeek / Volcano Ark）';

  @override
  String get aiPlatformApiUrl => 'API URL';

  @override
  String get aiPlatformApiUrlHint =>
      'e.g., https://ark.cn-beijing.volces.com/api/v3';

  @override
  String get aiPlatformMaxTokens => '最大トークン数';

  @override
  String get aiPlatformMaxTokensHint => '例：4096';

  @override
  String get aiPlatformChunkSize => 'チャンクサイズ';

  @override
  String get aiPlatformChunkSizeHint => '例：3000';

  @override
  String get aiPlatformConcurrent => '同時リクエスト数';

  @override
  String get aiPlatformConcurrentHint => '例：5';

  @override
  String get aiPlatformModel => 'モデル';

  @override
  String get aiPlatformModelHint => '例：deepseek-v3 / llama3.1-70b';

  @override
  String get aiPlatformApiKey => 'APIキー';

  @override
  String get aiPlatformApiConfiguration => 'API設定';

  @override
  String get aiPlatformGetApiKey => 'APIキーを取得';

  @override
  String get aiPlatformCancel => 'キャンセル';

  @override
  String get aiPlatformTestConnection => '接続テスト';

  @override
  String get aiPlatformTestConnectionHint =>
      '設定を保存した後、下の「接続テスト」をクリックして、このプラットフォームが正常に動作するか確認してください。';

  @override
  String get setupWizardConfigureApiKeyAndTest =>
      '接続不可。API Key を設定し「接続テスト」をクリックして確認してください。';

  @override
  String get setupWizardSaveAndExit => '保存して終了';

  @override
  String get setupWizardTitle => '設定ウィザード';

  @override
  String get setupWizardStepWelcome => 'ようこそ';

  @override
  String get setupWizardStepMineru => 'PDF / MinerU';

  @override
  String get setupWizardWelcomeIntro => 'このウィザードでは、2つの主要設定を行います：';

  @override
  String get setupWizardWelcomeBody =>
      '1. メインのLLMプラットフォームを選択・設定します。\n2. PDF/PNGなどを翻訳する場合は、MinerU解析エンジンを設定します（任意）。\n\n注意：設定後は「接続テスト」で確認してください。';

  @override
  String get setupWizardUiLanguageLabel => 'UI言語';

  @override
  String get setupWizardMineruQuestion => 'PDF・画像などのドキュメントを翻訳しますか？';

  @override
  String get setupWizardMineruYes => 'はい（推奨・MinerUドキュメント解析を有効化）';

  @override
  String get setupWizardMineruNo => 'いいえ（LLMのみでテキスト翻訳など）';

  @override
  String get setupWizardMineruDescription =>
      'MinerUはPDF・画像のレイアウト解析とセグメント化を行います。\n下記にAPI KeyとURLを入力し、「接続テスト」で確認してください。';

  @override
  String get setupWizardMineruSkipped =>
      'MinerUは設定しませんでした。設定からいつでもPDF翻訳を有効にできます。';

  @override
  String get setupWizardMineruConfigTitle => 'MinerU（解析エンジン）';

  @override
  String get setupWizardSelectMineruPlatform => 'MinerU プラットフォームを選択';

  @override
  String get setupWizardMineruCloudOption => 'MinerU (クラウド) - 公式クラウドサービス';

  @override
  String get setupWizardMineruLocalOption => 'MinerU (ローカル) - セルフホスト';

  @override
  String get setupWizardSelectLlmPlatform => 'LLMプラットフォームを選択';

  @override
  String get setupWizardNoLlmPlatforms =>
      'AIプラットフォーム設定にLLMがありません。設定でプラットフォームを追加してください。';

  @override
  String get setupWizardMineruSaved => 'MinerUの設定を保存しました';

  @override
  String get setupWizardPrevStep => '戻る';

  @override
  String get setupWizardNextStep => '次へ';

  @override
  String get aiPlatformSave => '保存';

  @override
  String get aiPlatformList => 'リスト';

  @override
  String get aiPlatformTemperature => '温度';

  @override
  String get aiPlatformThinkingMode => '思考モード';

  @override
  String get aiPlatformThinkingDisable => '無効（推奨）';

  @override
  String get aiPlatformThinkingEnable => '有効';

  @override
  String get aiPlatformThinkingDefault => 'デフォルト';

  @override
  String get aiPlatformThinkingHint => 'より良い翻訳品質のためにAI推論プロセスを有効にします';

  @override
  String get aiPlatformPleaseEnterApiKeyFirst => 'まずAPIキーを入力してください';

  @override
  String get aiPlatformPleaseEnterApiUrlFirst => 'まずAPI URLを入力してください';

  @override
  String get aiPlatformHasApiKey => 'APIキーが必要';

  @override
  String get aiPlatformHasApiKeyHint => '認証が不要なローカル環境ではオフにしてください';

  @override
  String get aiPlatformApiKeyOptionalHint => '不要な場合は空欄可';

  @override
  String get optional => '任意';

  @override
  String get aiPlatformConnectionTestSucceeded => '接続テスト成功';

  @override
  String aiPlatformConnectionTestFailed(Object message) {
    return '接続テスト失敗：$message';
  }

  @override
  String get aiPlatformNoModelsFound => 'モデルが見つかりません';

  @override
  String get aiPlatformFailedToLoadModels => 'モデルの読み込みに失敗しました';

  @override
  String aiPlatformErrorLoadingModels(Object error) {
    return 'モデル読み込みエラー：$error';
  }

  @override
  String get aiPlatformSelectModel => 'モデルを選択';

  @override
  String get aiPlatformNoModelsAvailable => '利用可能なモデルがありません';

  @override
  String get aiPlatformMineruSettings => 'MinerU設定';

  @override
  String get aiPlatformEnterMineruApiKey => 'MinerU APIキーを入力';

  @override
  String get aiPlatformGetMineruApiKey => 'MinerU APIキーを取得';

  @override
  String get aiPlatformModelVersion => 'モデルバージョン';

  @override
  String get aiPlatformModelVersionHint => 'vlm';

  @override
  String get aiPlatformMineruApiUrlHint => 'https://mineru.net/api/v4';

  @override
  String get aiPlatformOcrSettings => 'OCR設定';

  @override
  String get aiPlatformFormulaOcr => '数式OCR';

  @override
  String get aiPlatformFormulaOcrSubtitle => '数学的数式のOCRを有効にします';

  @override
  String get aiPlatformTableOcr => '表OCR';

  @override
  String get aiPlatformTableOcrSubtitle => '表のOCRを有効にします';

  @override
  String get settingsFontEditSizeTitle => '編集フォントサイズ';

  @override
  String get settingsFontEditSizeSubtitle => '翻訳セグメント編集時のフォントサイズ';

  @override
  String get settingsTranslationTitle => '翻訳設定';

  @override
  String get settingsTranslationNotice => 'これらの設定は新しい翻訳タスクにのみ適用されます。';

  @override
  String get settingsTranslationAutoGlossaryTitle => '用語集を自動生成';

  @override
  String get settingsTranslationAutoGlossarySubtitle =>
      '翻訳後に用語集を自動生成します（新しいタスクに適用）';

  @override
  String get settingsTranslationParamsTitle => '翻訳パラメータ';

  @override
  String get settingsTranslationConcurrentTitle => '同時リクエスト数';

  @override
  String get settingsTranslationConcurrentHint => '推奨：3（モデルとクォータに基づき1〜8に調整）';

  @override
  String get settingsTranslationTimeoutTitle => 'タイムアウト（秒）';

  @override
  String get settingsTranslationTimeoutHint => '120（推奨：120-300秒）';

  @override
  String get settingsTranslationChunkRetryTitle => 'チャンク/API リトライ';

  @override
  String get settingsTranslationChunkRetryHint =>
      '推奨：3〜5（チャンク翻訳または API 呼び出し失敗時の再試行）';

  @override
  String get settingsTranslationSegmentAutoRetryTitle => 'キュー：失敗セグメント自動再試行ラウンド';

  @override
  String get settingsTranslationSegmentAutoRetryHint =>
      '推奨：3（本翻訳後の一括再翻訳、1〜10 ラウンド；キューモードのみ）';

  @override
  String get settingsTranslationChunkSizeTitle => 'チャンクサイズ（トークン）';

  @override
  String get settingsTranslationChunkSizeHint =>
      '推奨：リクエストあたり3000トークン（モデルのコンテキストサイズで調整）';

  @override
  String get settingsExclusionTitle => 'デフォルト除外ルール';

  @override
  String get settingsExclusionNotice =>
      'ON = 抽出時に自動除外；OFF = 検出のみ（ユーザーがセグメントごとに決定）。';

  @override
  String get settingsExclusionImageTitle => '画像';

  @override
  String get settingsExclusionImageSubtitle => '画像プレースホルダーと純粋な画像コンテンツ';

  @override
  String get settingsExclusionFormulaTitle => '数式';

  @override
  String get settingsExclusionFormulaSubtitle => 'LaTeX / MathML数式';

  @override
  String get settingsExclusionReferenceTitle => '参照';

  @override
  String get settingsExclusionReferenceSubtitle => '引用と参考文献';

  @override
  String get settingsExclusionIdentifierTitle => '識別子';

  @override
  String get settingsExclusionIdentifierSubtitle => 'URL、メール、シリアル番号、コードスニペット';

  @override
  String get settingsExclusionStructuralTitle => '構造的';

  @override
  String get settingsExclusionStructuralSubtitle => 'ヘッダー、フッター、脚注、ページ番号';

  @override
  String get settingsExclusionTableTitle => '表';

  @override
  String get settingsExclusionTableSubtitle => '表コンテンツ（マークダウン / PDF表）';

  @override
  String get settingsExclusionLanguageMatchTitle => '言語一致';

  @override
  String get settingsExclusionLanguageMatchSubtitle => 'ソース言語がターゲット言語と一致';

  @override
  String get settingsLanguageDialogTitle => '言語を選択';

  @override
  String get settingsUnitPt => 'pt';

  @override
  String get glossaryGeneratedTabTitle => '生成された用語集';

  @override
  String glossaryErrorRefresh(Object error) {
    return '用語集の更新に失敗：$error';
  }

  @override
  String get glossaryWarningNoGenerated => '生成された用語集は利用できません';

  @override
  String get glossaryPanelView => '表示';

  @override
  String get glossaryPanelAddToPersonal => '個人用語集に追加';

  @override
  String get glossaryPanelNoGlobalGlossaries => '利用可能なグローバル用語集がありません';

  @override
  String get glossaryPanelSelectTitle => '用語集を選択';

  @override
  String get glossaryPanelSelectHint => '用語集を選択...';

  @override
  String glossaryPanelSelected(Object name) {
    return '選択中：$name';
  }

  @override
  String get glossaryPanelSelectConfirm => '選択';

  @override
  String get glossaryPanelMergeToCurrent => '現在の用語集にマージ';

  @override
  String glossaryPanelLoadedGlossary(Object name) {
    return '用語集を読み込みました：$name';
  }

  @override
  String glossaryPanelLoadFailed(Object error) {
    return '用語集の読み込みに失敗：$error';
  }

  @override
  String glossaryPanelMergedIntoCurrent(Object glossaryName) {
    return '「$glossaryName」を現在の用語集にマージしました';
  }

  @override
  String glossaryPanelMergeFailed(Object error) {
    return 'マージに失敗：$error';
  }

  @override
  String get glossaryPanelEnterName => '用語集の名前を入力してください';

  @override
  String get glossaryPanelSaveDialogHint => '用語集名を入力するか、置換する既存の用語集を選択してください：';

  @override
  String get glossaryPanelReplaceTitle => 'グローバル用語集を置換';

  @override
  String glossaryPanelReplaceBody(Object glossaryName) {
    return '現在の用語集のエントリで「$glossaryName」の全エントリを置換します。続行しますか？';
  }

  @override
  String get glossaryPanelReplaceConfirm => '置換';

  @override
  String glossaryPanelReplacedGlobal(Object name) {
    return 'グローバル用語集を置換しました：$name';
  }

  @override
  String glossaryPanelSavedAsNewGlobal(Object name) {
    return '新しいグローバル用語集として保存しました：$name';
  }

  @override
  String glossaryPanelSaveFailed(Object error) {
    return '保存に失敗：$error';
  }

  @override
  String get glossaryPanelDetect => '用語集を検出';

  @override
  String get glossaryPanelEdit => '編集';

  @override
  String get glossaryPanelCreate => '用語集を作成';

  @override
  String get glossaryPanelSelect => '選択';

  @override
  String get glossaryPanelImport => 'インポート';

  @override
  String get glossaryPanelExport => 'エクスポート';

  @override
  String get glossaryPanelSave => '保存';

  @override
  String get glossaryPanelAddEntry => 'エントリ追加';

  @override
  String get glossaryPanelClear => 'クリア';

  @override
  String get glossaryPanelApply => '適用';

  @override
  String get glossaryPanelColumnSource => '原文';

  @override
  String get glossaryPanelColumnTarget => '訳文';

  @override
  String get glossaryPanelColumnActions => '操作';

  @override
  String get translationStepsUploadTooltipReady => 'ファイルを選択しました';

  @override
  String get translationStepsUploadTooltipNotReady => '開始するにはファイルを選択';

  @override
  String get translationStepsExtractTooltipReady => '抽出結果を表示';

  @override
  String get translationStepsExtractTooltipNotReady => 'インポート後に抽出できます';

  @override
  String get translationStepsGlossaryTooltipSkipped => '用語集をスキップしました';

  @override
  String get translationStepsGlossaryTooltipEnabled => '用語集が有効です';

  @override
  String get translationStepsGlossaryTooltipDisabled => '用語集を生成または選択して有効化';

  @override
  String get translationStepsTranslateTooltipReady => '翻訳が完了しました';

  @override
  String get translationStepsTranslateTooltipNotReady => '翻訳を実行して有効化';

  @override
  String get glossaryDialogAddTitle => '個人用語集に追加';

  @override
  String glossaryDialogAddBody(Object termCount) {
    return 'これにより$termCount用語が個人用語集に追加されます。';
  }

  @override
  String get glossaryDialogAddPreviewTitle => 'プレビュー（最初の5用語）：';

  @override
  String glossaryDialogAddMoreTerms(Object remainingCount) {
    return '... および$remainingCount以上の用語';
  }

  @override
  String get glossaryDialogMergeStrategyTitle => 'マージ戦略：';

  @override
  String get glossaryDialogMergeUpdateTitle => '更新（推奨）';

  @override
  String get glossaryDialogMergeUpdateSubtitle => '既存の用語を更新し、新しいものを追加';

  @override
  String get glossaryDialogMergeAppendTitle => '追加';

  @override
  String get glossaryDialogMergeAppendSubtitle => '新しい用語のみ追加、既存のものはスキップ';

  @override
  String get glossaryDialogMergeReplaceTitle => '置換';

  @override
  String get glossaryDialogMergeReplaceSubtitle => 'これらの用語で用語集全体を置換';

  @override
  String get glossaryDialogCancel => 'キャンセル';

  @override
  String get glossaryDialogReviewAndAdd => '確認して追加';

  @override
  String get glossaryConfirmAddTitle => '個人用語集への追加を確認';

  @override
  String glossaryConfirmAddBody(Object termCount) {
    return '$termCount用語を個人用語集に追加しますか？';
  }

  @override
  String get glossaryConfirmAddStrategyUpdate => '戦略：既存の用語を更新し、新しいものを追加';

  @override
  String get glossaryConfirmAddStrategyAppend => '戦略：新しい用語のみ追加、既存のものはスキップ';

  @override
  String get glossaryConfirmAddStrategyReplace => '戦略：用語集全体を置換';

  @override
  String get glossaryConfirmAddAutoCreateHint => '個人用語集が存在しない場合は自動的に作成されます。';

  @override
  String get glossaryConfirmAddButton => '追加';

  @override
  String get glossaryExportDialogTitle => '用語集を保存';

  @override
  String glossaryExportSuccess(Object filename) {
    return '用語集をエクスポートしました：$filename';
  }

  @override
  String glossaryExportFailed(Object error) {
    return '用語集のエクスポートに失敗：$error';
  }

  @override
  String glossaryCsvValidationFailed(Object errors) {
    return 'CSVファイルの検証に失敗しました：\n\n$errors';
  }

  @override
  String get glossaryCsvNoValidEntries => 'CSVファイルに有効なエントリが含まれていません。';

  @override
  String get glossaryImportDialogTitle => '用語集をインポート';

  @override
  String glossaryImportDialogBodyEmpty(Object count) {
    return 'ファイル内に$countエントリが見つかりました。\n\n現在の用語集は空です。インポートされたエントリが追加されます。';
  }

  @override
  String glossaryImportDialogBody(Object count) {
    return 'ファイル内に$countエントリが見つかりました。\n\nインポート方法を選択：';
  }

  @override
  String get glossaryImportButtonImport => 'インポート';

  @override
  String get glossaryImportButtonReplace => '置換';

  @override
  String get glossaryImportButtonMerge => 'マージ';

  @override
  String glossaryImportResult(Object count, Object mode) {
    return '$countエントリをインポートしました（$mode）';
  }

  @override
  String glossaryErrorImport(Object error) {
    return '用語集のインポートに失敗：$error';
  }

  @override
  String get glossaryErrorFileData => 'ファイルデータを読み取れませんでした。もう一度お試しください。';

  @override
  String get glossaryErrorFilePath => 'ファイルパスが利用できません。もう一度お試しください。';

  @override
  String get glossaryErrorOnlyCsv => '用語集インポートにはCSVおよびTBXファイルがサポートされています。';

  @override
  String get glossaryExportFormatLabel => 'エクスポート形式';

  @override
  String get glossaryExportFormatTbxSubtitle => 'TermBase eXchange（ISO 12620）';

  @override
  String get glossaryExportSourceLanguage => 'ソース言語';

  @override
  String get glossaryExportButtonExport => 'エクスポート';

  @override
  String get extractFormatConversionFailed => 'フォーマット変換に失敗しました。';

  @override
  String get fileUploadDisabledMessage => 'ファイル選択が無効です（処理中）';

  @override
  String get fileUploadSupportedFormats =>
      '対応：Word（DOCX）、PowerPoint（PPTX）、Excel（XLSX/CSV）、PDF、Markdown、TXT、HTML、SRT、JSON、EPUB、MOBI、Qt TS、PNG、JPEG';

  @override
  String get fileUploadDropHere => 'ファイルをここにドロップ';

  @override
  String get fileUploadHint => 'ファイルをここにドラッグ＆ドロップするか、クリックして選択';

  @override
  String get fileUploadCancelTask => '現在のタスクをキャンセル';

  @override
  String get exclusionPanelExcludeAll => 'すべて除外';

  @override
  String get exclusionPanelCancelUserExclusion => '自動除外を復元';

  @override
  String get exclusionPanelClearAllExclusions => 'すべての除外を解除';

  @override
  String get exclusionPanelExclusionByType => 'タイプ別除外：';

  @override
  String get exclusionPanelStructuralHeader => '構造的（ヘッダー）';

  @override
  String get exclusionPanelStructuralFooter => '構造的（フッター）';

  @override
  String get exclusionPanelUserExcluded => 'ユーザー除外';

  @override
  String get exclusionPanelExcluded => '除外済み';

  @override
  String get exclusionPanelFilterDisplayMode => 'フィルター表示モード：';

  @override
  String get exclusionPanelRebuild => '再構築';

  @override
  String get exclusionPanelPage => 'ページ';

  @override
  String get exclusionPanelRebuildTooltip => '新しいページネーションで一致するセグメントのみ表示';

  @override
  String get exclusionPanelPageTooltip => '現在のページ内でフィルター';

  @override
  String get exclusionPanelSegmentTypeFilters => 'セグメントタイプフィルター：';

  @override
  String get exclusionPanelCollapsePanelTooltip => 'パネルを折りたたむ';

  @override
  String get exclusionPanelExclusionControls => '除外コントロール：';

  @override
  String exclusionPanelExcludeCategory(Object count, Object name) {
    return '$nameを除外（$count）';
  }

  @override
  String get exclusionPanelChangeReasonTitle => '除外理由を変更';

  @override
  String get exclusionPanelCurrentLabel => '現在：';

  @override
  String get exclusionPanelSelectNewReason => '新しい理由を選択：';

  @override
  String get exclusionPanelNoneRemoveExclusion => 'なし（除外を解除）';

  @override
  String get exclusionPanelApply => '適用';

  @override
  String get exclusionPanelExpandFilterPanel => 'フィルターパネルを展開';

  @override
  String get exclusionPanelCollapseFilterPanel => 'フィルターパネルを折りたたむ';

  @override
  String extractToolbarSegments(Object end, Object start, Object total) {
    return 'セグメント（$total中$start-$end）';
  }

  @override
  String get extractToolbarCancel => 'キャンセル';

  @override
  String get extractCancelExtractionTitle => '抽出をキャンセル';

  @override
  String get extractCancelExtractionContent => '抽出をキャンセルしてもよろしいですか？これは元に戻せません。';

  @override
  String get extractCancelExtractionNo => 'いいえ';

  @override
  String get extractCancelExtractionYes => 'はい';

  @override
  String get extractExtractionCancelled => '抽出をキャンセルしました';

  @override
  String get extractMineruConfigRequiredTitle => 'MinerU設定が必要です';

  @override
  String extractMineruConfigRequiredContent(Object error) {
    return 'MinerU APIへの接続に失敗しました。設定ページでMinerU設定を構成してください。\n\nエラー詳細：\n$error';
  }

  @override
  String get extractOpenSettings => '設定を開く';

  @override
  String extractErrorLabel(Object error) {
    return 'エラー：$error';
  }

  @override
  String get extractRetry => '再試行';

  @override
  String get extractTaskTypeDetectIdentifier => '識別子の検出';

  @override
  String get extractTaskTypeDetectLanguage => '言語検出';

  @override
  String get extractTaskTypeDetectExclusions => '除外項目の検出';

  @override
  String get translationStatsTitle => '翻訳統計';

  @override
  String get translationStatsDocuments => 'ドキュメント';

  @override
  String get translationStatsPages => 'ページ';

  @override
  String translationStatsLastUpdated(Object date) {
    return '最終更新：$date';
  }

  @override
  String get translationStatsLoadFailed => '統計の読み込みに失敗しました';

  @override
  String get translationStatsJustNow => 'たった今';

  @override
  String get translationStatsOneMinuteAgo => '1分前';

  @override
  String translationStatsMinutesAgo(Object count) {
    return '$count分前';
  }

  @override
  String get translationStatsOneHourAgo => '1時間前';

  @override
  String translationStatsHoursAgo(Object count) {
    return '$count時間前';
  }

  @override
  String get translationStatsYesterday => '昨日';

  @override
  String translationStatsDaysAgo(Object count) {
    return '$count日前';
  }

  @override
  String get aiPlatformDisplayName => '表示名';

  @override
  String get aiPlatformParserSubtype => 'パーサー種別';

  @override
  String get aiPlatformParserSubtypeCloud => 'クラウド';

  @override
  String get aiPlatformParserSubtypeLocal => 'ローカル';

  @override
  String get translationQueueEdit => 'ラベル編集';

  @override
  String get reeditTitle => '翻訳を編集';

  @override
  String get reeditSaveExport => '保存してエクスポート';

  @override
  String get reeditFetchError => '翻訳セグメントの読み込みに失敗しました。';

  @override
  String get reeditSaveSuccess => '変更が保存されました。';

  @override
  String get reeditSaveError => '変更の保存に失敗しました。';

  @override
  String get workspaceCloseFlowTitle => 'このフローを閉じますか？';

  @override
  String get workspaceCloseFlowMessage => 'このフローを閉じると、保存されていない変更は破棄されます。';

  @override
  String get workspaceCloseFlowSaveToQueue => '保存して閉じる';

  @override
  String get workspaceCloseFlowDestroy => '破棄して閉じる';

  @override
  String get workspaceCloseFlowCancel => 'キャンセル';

  @override
  String get fetchUrlCancel => 'キャンセル';

  @override
  String get fetchUrl => 'URL フェッチ';

  @override
  String get fetchUrlClose => '閉じる';

  @override
  String get loginSubtitleFeatures => 'ファイル翻訳\nフォーマット変換\nURL フェッチ';

  @override
  String get loginSubtitleTagline => 'AI 文書処理システム';

  @override
  String get loginUsernameLabel => 'ユーザー名';

  @override
  String get loginUsernameHint => 'ユーザー名を入力してください';

  @override
  String get loginUsernameRequiredError => 'ユーザー名を入力してください';

  @override
  String get loginUsernameMinLengthError => 'ユーザー名は3文字以上必要です';

  @override
  String get loginPasswordLabel => 'パスワード';

  @override
  String get loginPasswordHint => 'パスワードを入力してください';

  @override
  String get loginPasswordRequiredError => 'パスワードを入力してください';

  @override
  String get loginForgotPassword => 'パスワードをお忘れですか？';

  @override
  String get loginPasswordRecoveryTitle => 'パスワード復旧';

  @override
  String get loginPasswordRecoveryContactAdmin => '管理者に連絡してパスワードをリセットしてください。';

  @override
  String get loginPasswordRecoveryAdminHint =>
      '管理者はログイン後、ユーザー管理ページでパスワードをリセットできます。';

  @override
  String get loginAuthMethodDefault => 'デフォルト認証を使用';

  @override
  String get loginCopyErrorLabel => 'コピー';

  @override
  String get loginErrorCopiedMessage => 'エラーメッセージをクリップボードにコピーしました';

  @override
  String get loginWelcomeBack => 'おかえりなさい';

  @override
  String get loginFeatureFormats =>
      'PDF、DOCX、XLSX、HTML、EPUB、MOBI\nおよび15以上のフォーマット';

  @override
  String get loginFeatureLayout => 'レイアウトを保持した翻訳\n高い忠実度';

  @override
  String get loginFeaturePlatforms =>
      '20+ LLM プラットフォームに対応\nOpenAI、Claude、Ollama を含む';

  @override
  String get loginPasswordRecoveryAdminGuide => '管理者の方は、パスワード復旧手順に従ってください。';

  @override
  String get commonDarkMode => 'ダークモード';

  @override
  String get commonLightMode => 'ライトモード';
}
