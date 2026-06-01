// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get settingsGeneralTitle => '通用设置';

  @override
  String get settingsGeneralDarkModeTitle => '深色模式';

  @override
  String get settingsGeneralDarkModeSubtitle => '启用深色主题（立即应用）';

  @override
  String get settingsGeneralLanguageTitle => '语言';

  @override
  String get settingsGeneralNotificationsTitle => '通知';

  @override
  String get settingsGeneralNotificationsSubtitle => '接收任务完成通知（立即应用）';

  @override
  String get settingsGeneralAutoSaveTitle => '自动保存';

  @override
  String get settingsGeneralAutoSaveSubtitle => '自动保存进行中的工作（立即应用）';

  @override
  String get settingsGeneralShowAdsTitle => '显示广告';

  @override
  String get settingsGeneralShowAdsSubtitle =>
      '在主页和流程中显示广告占位符（存储在 system.json 中）';

  @override
  String get settingsGeneralClearStatsButton => '清除统计数据';

  @override
  String get settingsGeneralClearStatsConfirmTitle => '清除统计数据？';

  @override
  String get settingsGeneralClearStatsConfirmMessage =>
      '这将把主页上显示的文档数和页数重置为 0。此操作不可撤销。';

  @override
  String get settingsGeneralClearStatsConfirmButton => '清除';

  @override
  String get settingsGeneralClearStatsSuccess => '统计数据已清除。';

  @override
  String get backToHome => '回到主页';

  @override
  String get settingsFontSectionTitle => '字体设置';

  @override
  String get settingsFontPreviewSizeTitle => '预览字体大小';

  @override
  String get settingsFontPreviewSizeSubtitle => '预览中源文本和目标文本的字体大小';

  @override
  String get translationToolbarFilterAll => '全部';

  @override
  String get translationToolbarFilterFailed => '失败';

  @override
  String get translationToolbarFilterIncluded => '已包含';

  @override
  String get translationToolbarFilterExcluded => '已排除';

  @override
  String get translationToolbarSearchTooltip => '搜索 (Ctrl+F / Cmd+F)';

  @override
  String get translationToolbarPrevRetryTooltip => '上一个重试片段';

  @override
  String get translationToolbarNextRetryTooltip => '下一个重试片段';

  @override
  String get translationToolbarPreviewTooltip => '预览';

  @override
  String get translationToolbarFormatSettingsTooltip => '格式设置';

  @override
  String get translationToolbarExportTooltip => '导出文档';

  @override
  String get translationToolbarPdfPreviewTooltip => 'PDF 预览（调试）';

  @override
  String get translationToolbarCancelButton => '取消';

  @override
  String get translationToolbarExitFullscreenTooltip => '退出全屏';

  @override
  String get translationToolbarEnterFullscreenTooltip => '进入全屏';

  @override
  String get translationToolbarDecreaseFontSize => '缩小字体';

  @override
  String get translationToolbarIncreaseFontSize => '增大字体';

  @override
  String get translationToolbarMergedView => '阅读模式';

  @override
  String get translationToolbarSegmentView => '标签模式';

  @override
  String get translationToolbarUpload => '上传';

  @override
  String get translationToolbarUploading => '上传中...';

  @override
  String get translationToolbarFileUploaded => '文件已上传';

  @override
  String get translationToolbarReextract => '重新提取';

  @override
  String get translationToolbarReextracting => '重新提取中...';

  @override
  String translationToolbarTokensCount(Object count) {
    return '$count 个标记';
  }

  @override
  String get translationToolbarOpenGlossaryTab => '打开术语表标签页';

  @override
  String get translationToolbarHintWaitExtract => '请等待提取完成';

  @override
  String get translationToolbarHintOperationInProgress => '有操作正在进行中';

  @override
  String get translationToolbarGlossary => '术语表';

  @override
  String get translationToolbarConvertHint => '一键：格式转换、全部排除段落并翻译，随后在「转换」标签导出';

  @override
  String get translationToolbarConvert => '转换';

  @override
  String get translationToolbarHintSaveGlossaryFirst => '请先保存术语表（点击应用）';

  @override
  String get translationToolbarHintUpdatingExcluded => '正在更新排除的片段...';

  @override
  String get translationToolbarStartTranslation => '开始翻译';

  @override
  String get translationToolbarTranslateAll => '翻译全部';

  @override
  String get translationToolbarTranslating => '翻译中...';

  @override
  String get translationToolbarRetryInProgress => '重试进行中...';

  @override
  String get translationToolbarRetryTooltip =>
      '重试所有失败或标记的片段。这将使用当前选定的 AI 平台重新翻译在翻译过程中失败的或手动标记为重试的片段。已排除和已清除的片段将被跳过。';

  @override
  String get translationToolbarRetry => '重试';

  @override
  String get translationPersistQueueTooltip =>
      '将当前导出结果写入服务器，更新任务队列中的下载，使其与当前译文一致。';

  @override
  String get translationPersistQueueButton => '保存更新到队列';

  @override
  String get translationPersistQueueAlreadySyncedTooltip =>
      '当前已与任务队列快照一致，无需重复保存。';

  @override
  String get translationPersistQueueSuccess => '已保存最新导出，任务队列将使用此版本。';

  @override
  String translationPersistQueueFailed(Object error) {
    return '保存到队列失败：$error';
  }

  @override
  String get translationCloseTranslateTabTitle => '任务队列中的结果可能仍非最终版本';

  @override
  String get translationCloseTranslateTabMessage =>
      '您在此修改的译文尚未保存到任务队列快照。若现在关闭而不保存，在「任务队列」中下载的文件将不是您在此编辑后的最终版本。\n\n您可以选择先保存更新到队列再关闭，或仍要直接关闭本标签页（不保存到队列）。';

  @override
  String get translationCloseTranslateTabStay => '留在本页';

  @override
  String get translationCloseTranslateTabClose => '仍要关闭';

  @override
  String get translationCloseTranslateTabSaveAndClose => '保存并关闭';

  @override
  String get translationCloseTranslateTabKeepTitle => '保留任务到队列？';

  @override
  String get translationCloseTranslateTabKeepMessage =>
      '翻译任务已完成。是否保留在任务队列中，以便以后查看和编辑？';

  @override
  String get translationCloseTranslateTabKeepInQueue => '保留在队列';

  @override
  String get translationCloseTranslateTabDiscard => '丢弃';

  @override
  String get translationToolbarSwitchToFile => '切换到文件';

  @override
  String get translationToolbarSwitchToText => '输入文本';

  @override
  String get translationStatusCompleted => '翻译完成';

  @override
  String get translationStatusRetry => '翻译重试';

  @override
  String get translationStatusFailed => '翻译失败';

  @override
  String get translationStatusCancelled => '翻译已取消';

  @override
  String get translationStatusTranslating => '翻译中';

  @override
  String get translationStatusTranslatingFallback => '翻译中...';

  @override
  String get translationStatusReady => '就绪';

  @override
  String get translationStatusTaskPending => '任务待处理';

  @override
  String get translationStatusProcessing => '处理中...';

  @override
  String translationStatsSuccessOnly(Object success, Object total) {
    return '成功：$success/$total';
  }

  @override
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total) {
    return '成功：$success/$total，失败：$fail/$total';
  }

  @override
  String translationStatsTotal(Object count) {
    return '总计：$count | ';
  }

  @override
  String translationStatsTranslated(Object count) {
    return '已翻译：$count | ';
  }

  @override
  String translationStatsPending(Object count) {
    return '待处理：$count';
  }

  @override
  String translationStatsExcluded(Object count) {
    return ' | 已排除：$count';
  }

  @override
  String translationStatsRetryCount(Object count) {
    return ' | 重试：$count';
  }

  @override
  String translationStatsCleared(Object count) {
    return ' | 已清除：$count';
  }

  @override
  String translationStatsImages(Object count) {
    return ' | 图片：$count';
  }

  @override
  String translationStatsSegment(Object current, Object total) {
    return '片段：$current / $total';
  }

  @override
  String get translationStatsDoubleClickToEdit => '双击文本进行编辑。';

  @override
  String get translationStatsTranslatedLabel => '已翻译';

  @override
  String get translationStatsPendingLabel => '待翻译';

  @override
  String get translationStatsClearedLabel => '已清除';

  @override
  String get translationStatsImagesLabel => '图片';

  @override
  String get translationStatsLoadingContent => '正在加载内容...';

  @override
  String get translationStatsNoContentAvailable => '无可用内容。';

  @override
  String get translationStatsNoSegmentsAvailable => '无可用片段';

  @override
  String translationStatsTokenIn(Object count) {
    return '输入：$count';
  }

  @override
  String translationStatsTokenOut(Object count) {
    return '输出：$count';
  }

  @override
  String translationStatsTokenTotal(Object count) {
    return '($count)';
  }

  @override
  String get translationLangArabic => '阿拉伯语';

  @override
  String get translationLangBengali => '孟加拉语';

  @override
  String get translationLangCatalan => '加泰罗尼亚语';

  @override
  String get translationLangChinese => '中文';

  @override
  String get translationLangChineseTraditional => '中文（繁体）';

  @override
  String get translationLangCzech => '捷克语';

  @override
  String get translationLangCroatian => '克罗地亚语';

  @override
  String get translationLangDanish => '丹麦语';

  @override
  String get translationLangDutch => '荷兰语';

  @override
  String get translationLangEnglish => '英语';

  @override
  String get translationLangFilipino => '菲律宾语';

  @override
  String get translationLangFinnish => '芬兰语';

  @override
  String get translationLangFrench => '法语';

  @override
  String get translationLangGerman => '德语';

  @override
  String get translationLangGreek => '希腊语';

  @override
  String get translationLangHebrew => '希伯来语';

  @override
  String get translationLangHindi => '印地语';

  @override
  String get translationLangItalian => '意大利语';

  @override
  String get translationLangJapanese => '日语';

  @override
  String get translationLangKorean => '韩语';

  @override
  String get translationLangKhmer => '高棉语';

  @override
  String get translationLangLithuanian => '立陶宛语';

  @override
  String get translationLangMacedonian => '马其顿语';

  @override
  String get translationLangMalay => '马来语';

  @override
  String get translationLangNorwegian => '挪威语（博克马尔）';

  @override
  String get translationLangPolish => '波兰语';

  @override
  String get translationLangPortuguese => '葡萄牙语';

  @override
  String get translationLangRomanian => '罗马尼亚语';

  @override
  String get translationLangRussian => '俄语';

  @override
  String get translationLangSlovenian => '斯洛文尼亚语';

  @override
  String get translationLangSpanish => '西班牙语';

  @override
  String get translationLangSwedish => '瑞典语';

  @override
  String get translationLangThai => '泰语';

  @override
  String get translationLangTurkish => '土耳其语';

  @override
  String get translationLangUkrainian => '乌克兰语';

  @override
  String get translationLangUrdu => '乌尔都语';

  @override
  String get translationLangVietnamese => '越南语';

  @override
  String get translationExportNoFormats => '无可用导出格式';

  @override
  String get translationExportDialogTitle => '导出文档';

  @override
  String get translationExportDocumentType => '文档类型';

  @override
  String get translationExportFormatOptionsTitle => '格式选项（仅限 PDF）';

  @override
  String get translationExportTableFormatLabel => '表格格式：';

  @override
  String get translationExportTableFormatImage => '图片';

  @override
  String get translationExportTableFormatHtml => 'HTML';

  @override
  String get translationExportEquationFormatLabel => '公式格式：';

  @override
  String get translationExportEquationFormatImage => '图片';

  @override
  String get translationExportEquationFormatLatex => 'LaTeX';

  @override
  String get translationExportBilingualExport => '双语导出';

  @override
  String get translationExportBilingualOrderTargetAfter => '原文在前';

  @override
  String get translationExportBilingualOrderTargetAfterSub => '原文在前，译文在后';

  @override
  String get translationExportBilingualOrderTargetBefore => '译文在前';

  @override
  String get translationExportBilingualOrderTargetBeforeSub => '译文在前，原文在后';

  @override
  String get translationExportSourceTextItalic => '原文斜体';

  @override
  String get translationExportSourceTextColor => '原文颜色：';

  @override
  String get translationExportTargetTextItalic => '译文斜体';

  @override
  String get translationExportTargetTextColor => '译文颜色：';

  @override
  String get translationExportColorDefault => '默认';

  @override
  String get translationExportColorGray => '灰色';

  @override
  String get translationExportColorBlue => '蓝色';

  @override
  String get translationExportColorRed => '红色';

  @override
  String get translationExportColorGreen => '绿色';

  @override
  String get translationExportColorOrange => '橙色';

  @override
  String get translationExportColorBlack => '黑色';

  @override
  String get translationExportDownloadButton => '下载';

  @override
  String get translationExportMdEmbeddedImages => 'MD（嵌入图片）';

  @override
  String get translationExportMdWithImagesFolder => 'MD（图片文件夹）';

  @override
  String get translationLeftPanelExpandTooltip => '展开左侧面板';

  @override
  String get translationLeftPanelCollapseTooltip => '折叠左侧面板';

  @override
  String get translationSnackGlossarySaved => '术语表已保存';

  @override
  String get translationSnackTranslationCancelled => '翻译已取消';

  @override
  String get translationSnackNoLlmpSelected => '未选择 LLM 平台';

  @override
  String get translationSnackTextEmpty => '文本输入为空。';

  @override
  String get translationSnackTextConverted => '文本已转换为文件格式';

  @override
  String get translationSnackSourceResplitCompleted => '源文件重新分割完成';

  @override
  String get translationSnackPleaseSelectFileOrText => '请先选择一个文件或输入文本';

  @override
  String get translationSnackPleaseSelectFileOrTextWithDot => '请先选择一个文件或输入文本。';

  @override
  String get translationSnackPleaseSelectFile => '请先选择一个文件';

  @override
  String get translationSnackPleaseSelectDocumentFirst => '请先选择一个文档。';

  @override
  String get translationSnackGlossaryGenerated => '术语表生成成功！';

  @override
  String get translationSnackGlossaryGenerationCancelled => '术语表生成已取消';

  @override
  String get translationSnackGlossaryAppliedToTask => '术语表已应用到翻译任务';

  @override
  String get translationSnackPreviousTranslationCancelled => '之前的翻译已取消';

  @override
  String get translationSnackGlossarySavedAndApplied => '术语表已保存并应用';

  @override
  String get translationDialogMixedLangTitle => '检测到多种语言';

  @override
  String translationDialogMixedLangContent(Object distribution) {
    return '文档中包含多种语言：\n$distribution';
  }

  @override
  String get translationDialogMixedLangPromptTitle => '为了提升翻译质量，你可以添加以下提示：';

  @override
  String get translationDialogMixedLangOption1Title => '仅翻译源语言文本';

  @override
  String translationDialogMixedLangOption1Subtitle(Object languageName) {
    return '仅翻译 $languageName 语言的文本';
  }

  @override
  String get translationDialogMixedLangOption2Title => '保持代码和技术术语不变';

  @override
  String get translationDialogMixedLangOption2Subtitle =>
      '保持代码块、技术术语、函数名及其他语言的文本不变';

  @override
  String get translationDialogMixedLangCancel => '取消';

  @override
  String get translationDialogMixedLangSkip => '跳过';

  @override
  String get translationDialogMixedLangApply => '应用';

  @override
  String get translationSnackExportStarted => '导出任务已启动，请稍候。';

  @override
  String get translationSnackPromptUpdated => '提示指令已更新';

  @override
  String translationSnackFailedToCancel(Object error) {
    return '取消失败：$error';
  }

  @override
  String translationSnackFailedConvertTextFormat(Object error) {
    return '文本格式转换失败：$error';
  }

  @override
  String translationSnackFailedConvertText(Object error) {
    return '文本转换失败：$error';
  }

  @override
  String translationSnackFailedResplit(Object error) {
    return '重新分割失败：$error';
  }

  @override
  String get translationSnackRequestFailed => '请求失败';

  @override
  String translationSnackFileImportFailed(Object error) {
    return '文件导入失败：$error';
  }

  @override
  String translationSnackTaskStatus(Object status) {
    return '任务状态：$status';
  }

  @override
  String translationSnackFileDownloaded(Object filename) {
    return '文件已下载：$filename';
  }

  @override
  String translationSnackFileSaved(Object filename) {
    return '文件已保存：$filename';
  }

  @override
  String translationSnackFailedDownload(Object error, Object fileType) {
    return '下载 $fileType 失败：$error';
  }

  @override
  String translationSnackFailedOpenDownload(Object url) {
    return '打开下载失败：$url';
  }

  @override
  String get translationDialogSwitchToFileTitle => '切换到文件模式';

  @override
  String get translationDialogSwitchToFileBody => '切换到文件模式将清除您当前的文本输入。是否继续？';

  @override
  String get translationDialogSwitchToTextTitle => '切换到文本模式';

  @override
  String get translationDialogSwitchToTextBody => '切换到文本模式将清除当前的文件选择。是否继续？';

  @override
  String get translationSnackAllSegmentsExcludedSkipped =>
      '所有片段被排除，将跳过翻译，您可以通过导出，进行格式转换。';

  @override
  String get translationDialogCancelButton => '取消';

  @override
  String get translationDialogContinueButton => '继续';

  @override
  String get translationNoLlmAvailableTitle => '暂无可用 LLM 平台';

  @override
  String get translationNoLlmAvailableMessage =>
      '当前没有已配置且可用的 LLM 平台，无法进行翻译。如需翻译，请先到设置中配置 LLM 的 API Key；若仅需格式转换，可继续。';

  @override
  String get translationNoLlmConfigureButton => '去配置 LLM';

  @override
  String get translationNoLlmContinueFormatOnlyButton => '仅做格式转换';

  @override
  String get languageMatchWarningTitle => '语言匹配提示';

  @override
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName) {
    return '检测到的文档语言（$detectedName）与目标语言（$targetName）相同，目标语言可能选择有误。是否仍继续执行术语表检测？';
  }

  @override
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName) {
    return '检测到的文档语言（$detectedName）与目标语言（$targetName）相同，目标语言可能选择有误。是否仍继续翻译？';
  }

  @override
  String get translationDialogCancelTaskTitle => '取消当前任务';

  @override
  String get translationDialogCancelTaskBody => '这将取消当前的提取/翻译任务并清除选定的文件。是否继续？';

  @override
  String get translationDialogCancelTaskNo => '否';

  @override
  String get translationDialogCancelTaskYesCancel => '是，取消';

  @override
  String get translationQuickSettingsTitle => '快速设置';

  @override
  String get quickSettingsTargetLanguage => '目标语言';

  @override
  String get quickSettingsSourceLanguage => '源语言 (MinerU OCR)';

  @override
  String get quickSettingsLanguageSwitchDisabled =>
      '翻译期间语言切换被禁用。请切换到提取标签页以更改目标语言。';

  @override
  String get quickSettingsParsingPlatform => '解析平台';

  @override
  String get quickSettingsTestMineru => '测试 MinerU 连接';

  @override
  String get quickSettingsNotConfigured => '未配置';

  @override
  String get quickSettingsApiOk => 'API 正常';

  @override
  String get quickSettingsApiUnavailable => 'API 不可用';

  @override
  String get quickSettingsNotTestedYet => '尚未测试';

  @override
  String get quickSettingsConnectionSuccessful => '连接成功';

  @override
  String get quickSettingsMineruConnectionFailed => 'MinerU 连接失败';

  @override
  String get quickSettingsOpenMineruSettings => '打开 MinerU 设置';

  @override
  String get quickSettingsMineruLabel => 'MinerU (mineru)';

  @override
  String get quickSettingsLlmPlatform => 'LLM 平台';

  @override
  String get quickSettingsTestLlmPlatform => '测试当前 LLM 平台';

  @override
  String get quickSettingsTestFailed => '测试失败';

  @override
  String get quickSettingsOpenAiPlatformsSettings => '打开 AI 平台设置';

  @override
  String get quickSettingsTemperature => '温度';

  @override
  String get quickSettingsTemperatureHint => '控制随机性：较低 = 更专注，较高 = 更具创造性';

  @override
  String get quickSettingsQtTsOptions => 'Qt .ts 翻译选项';

  @override
  String get quickSettingsQtTsSkipExisting => '跳过现有翻译';

  @override
  String get quickSettingsQtTsSkipExistingSubtitle => '跳过已有翻译的消息';

  @override
  String get quickSettingsQtTsTranslateUnfinished => '翻译未完成的条目';

  @override
  String get quickSettingsQtTsTranslateUnfinishedSubtitle =>
      '翻译标记为未完成的消息 (type=\"unfinished\")';

  @override
  String get quickSettingsQtTsTranslateVanished => '翻译已消失的条目';

  @override
  String get quickSettingsQtTsTranslateVanishedSubtitle =>
      '翻译标记为已消失的消息 (type=\"vanished\")';

  @override
  String get quickSettingsQtTsTranslateObsolete => '翻译过时的条目';

  @override
  String get quickSettingsQtTsTranslateObsoleteSubtitle =>
      '翻译标记为过时的消息 (type=\"obsolete\")';

  @override
  String get quickSettingsPrompt => '提示';

  @override
  String get quickSettingsPromptMode => '提示模式';

  @override
  String get quickSettingsPromptModeOff => '关闭（无提示）';

  @override
  String get quickSettingsPromptModeSimple => '简单（仅风格）';

  @override
  String get quickSettingsPromptModeAdvanced => '高级（风格 + 备注）';

  @override
  String get quickSettingsStyle => '风格';

  @override
  String get quickSettingsStyleLiteral => '直译';

  @override
  String get quickSettingsStyleFluent => '流畅';

  @override
  String get quickSettingsStyleAcademic => '学术';

  @override
  String get quickSettingsStyleBusiness => '商务';

  @override
  String get quickSettingsStyleTechnical => '技术';

  @override
  String get quickSettingsStyleNone => '无';

  @override
  String get quickSettingsTaskNoteLabel => '任务备注（简短指令）';

  @override
  String get quickSettingsTaskNoteHint => '例如：保持公式不变；标注专有名词';

  @override
  String get quickSettingsAdRegionF => '区域 F：快速设置底部\n（中等矩形 300×250）';

  @override
  String quickSettingsPlatformMessage(Object label, Object message) {
    return '$label：$message';
  }

  @override
  String quickSettingsPlatformTestFailed(Object error, Object label) {
    return '$label：测试失败 — $error';
  }

  @override
  String get homeTagline => '基于 AI，沉浸式\n私有，安全（开发中）\n团队共享，可定制\n';

  @override
  String get homeIntro => '上传文档并使用 AI 驱动的准确性将其翻译成多种语言。\n';

  @override
  String get homeHowItWorks =>
      '工作原理\n翻译：导入 -> 解析文档 -> 术语表 -> 翻译 -> 导出\n文件格式转换：导入 -> 解析文档 -> 转换 -> 导出\n网页抓取：输入网址 -> 抓取网页 -> 解析内容 -> 提取正文 -> 翻译/导出';

  @override
  String get homeSnackDonorExpired => '您的注册码已过期。请重新注册以继续享受 Pro 版权益。';

  @override
  String get commonCancel => '取消';

  @override
  String get commonOk => '确定';

  @override
  String get homeAuthErrorTitle => '认证错误';

  @override
  String get homeAuthRetryLogin => '重试登录';

  @override
  String homeAiPlatformsAvailable(Object platforms) {
    return '可用 AI 平台：$platforms';
  }

  @override
  String get homeAiPlatformsConfigureNotice => '在使用应用之前，请在设置面板中配置您的 AI 平台。';

  @override
  String get homeBackendStatusStarting => '后端正在启动...';

  @override
  String get homeBackendStatusConnecting => '正在连接到后端...';

  @override
  String get homeBackendStatusConnected => '后端已连接';

  @override
  String get homeBackendStatusDisconnected => '后端已断开连接。请重试。';

  @override
  String get homeBackendStatusUnknown => '正在连接到后端...';

  @override
  String get homeBackendRetry => '重试';

  @override
  String get homeNewTask => '新建任务';

  @override
  String get homeNewTaskImmersiveTooltip => '在界面内即时对照原文与译文';

  @override
  String get homeNewTaskQueuedTooltip => '批量导入文件，加入队列按序自动翻译';

  @override
  String get homeNavTranslate => '沉浸式任务';

  @override
  String get homeNavTranslationQueue => '任务';

  @override
  String get homeNavAnonymize => '匿名化';

  @override
  String get homeNavSettings => '设置';

  @override
  String get homeNavDonateHelp => '帮助';

  @override
  String get homeNavDonate => '捐赠';

  @override
  String get homeNavHome => '主页';

  @override
  String get homeNavBatchUpload => '批量上传';

  @override
  String get homeNavTooltipNewTask => '开始新的翻译任务——沉浸式逐句对照，或队列式批量处理';

  @override
  String get homeNavTooltipTasks => '查看和管理所有翻译任务，下载已完成的译文';

  @override
  String get homeNavTooltipAnonymize => '对文档内容进行匿名化处理，保护敏感信息';

  @override
  String get homeNavTooltipSettings => '配置语言、主题、通知等应用选项';

  @override
  String get homeNavTooltipSetupWizard => '引导式设置向导，快速完成翻译环境配置';

  @override
  String get homeNavTooltipHelp => '获取使用帮助和技术支持';

  @override
  String get homeNavTooltipDonate => '支持我们的开源项目';

  @override
  String get homeNavTooltipHome => '返回应用首页';

  @override
  String get homeNavTooltipGitHub => '查看项目源码，欢迎给我们 Star！';

  @override
  String get batchUploadTitle => '批量文件上传';

  @override
  String get batchUploadFormatConvert => '格式转换';

  @override
  String get batchUploadSelectSourceHint => '选择要翻译的支持文件。每个文件将成为一个队列任务。';

  @override
  String get batchUploadSelectFolder => '选择文件夹';

  @override
  String get batchUploadFolderDescription => '选择包含待翻译文件的文件夹';

  @override
  String get batchUploadSelectZip => '选择 ZIP 压缩包';

  @override
  String get batchUploadZipDescription => '选择包含待翻译文件的 ZIP 压缩包';

  @override
  String get batchUploadSelectSingleFile => '选择文件';

  @override
  String batchUploadFilesFound(Object count) {
    return '找到 $count 个支持的文件';
  }

  @override
  String get batchUploadSelectAll => '全选';

  @override
  String get batchUploadDeselectAll => '取消全选';

  @override
  String get batchUploadStartTranslation => '开始翻译';

  @override
  String get batchUploadSubmitting => '正在提交文件...';

  @override
  String batchUploadProgress(Object completed, Object total) {
    return '已提交 $completed / $total 个文件';
  }

  @override
  String get batchUploadCompleteTitle => '批量完成';

  @override
  String batchUploadComplete(Object success, Object failed) {
    return '$success 个成功，$failed 个失败';
  }

  @override
  String get batchUploadNoSupportedFiles => '未找到支持的文件';

  @override
  String batchUploadSelectedCount(Object count) {
    return '已选 $count 个文件';
  }

  @override
  String batchUploadLegacyFormatsFound(Object files) {
    return '$files 无法直接翻译。请先将 .doc 转换为 .docx，.ppt 转换为 .pptx，.xls 转换为 .xlsx 后再提交。';
  }

  @override
  String batchUploadLegacyFormatsSkipped(Object count) {
    return '已跳过 $count 个文件（旧版格式不支持直接翻译）。请将 .doc 转换为 .docx，.ppt 转换为 .pptx，.xls 转换为 .xlsx 后重试。';
  }

  @override
  String get batchUploadSettingsToggle => '快速设置';

  @override
  String get batchUploadSaveDefaults => '保存为默认';

  @override
  String batchUploadTemperature(Object value) {
    return '温度：$value';
  }

  @override
  String batchUploadGlossaryHint(Object count) {
    return '已选 $count 个术语表';
  }

  @override
  String get batchUploadGlossaryNone => '未选择术语表';

  @override
  String get batchUploadConfirmLangTitle => '确认目标语言';

  @override
  String batchUploadConfirmLangMessage(Object lang) {
    return '目标语言为“$lang”。是否继续？';
  }

  @override
  String get batchUploadConvert => '转换';

  @override
  String get batchUploadTranslate => '翻译';

  @override
  String get batchUploadFolderPickerTitle => '选择包含待翻译文件的文件夹';

  @override
  String get batchUploadZipPickerTitle => '选择包含待翻译文件的 ZIP 压缩包';

  @override
  String batchUploadScanFolderError(Object error) {
    return '扫描文件夹失败：$error';
  }

  @override
  String batchUploadReadZipError(Object error) {
    return '读取 ZIP 压缩包失败：$error';
  }

  @override
  String get batchUploadGlossarySection => '术语表';

  @override
  String batchUploadGlossaryMore(Object count) {
    return '+$count';
  }

  @override
  String batchUploadGlossaryLoadError(Object error) {
    return '错误：$error';
  }

  @override
  String get batchUploadNoGlossaries => '暂无可用术语表';

  @override
  String get batchUploadMineru => 'MinerU';

  @override
  String get batchUploadMineruLocal => 'MinerU 本地';

  @override
  String get commonClose => '关闭';

  @override
  String get translationQueueTitle => '任务队列';

  @override
  String get translationQueueHint => '列表会自动刷新，完成后可下载译文。';

  @override
  String get translationQueueCancelExitHint =>
      '排队中或进行中的任务可点击「取消任务」中止；确认后将返回首页。';

  @override
  String get translationQueueCancelDialogTitle => '取消该翻译任务？';

  @override
  String get translationQueueCancelDialogMessage =>
      '排队中的任务将从队列移除；进行中的任务将被中止。确认后将返回首页。';

  @override
  String get translationQueueCancelDialogKeep => '保留';

  @override
  String get translationQueueCancelDialogConfirm => '确认取消';

  @override
  String get translationQueueEmpty => '暂无翻译任务。';

  @override
  String get translationQueueNewQueuedTask => '队列式任务';

  @override
  String get translationQueueBackToQueueTooltip => '返回任务队列';

  @override
  String get translationQueuedStarted => '任务已加入队列，可在此查看进度。';

  @override
  String get translationQueueRefresh => '刷新';

  @override
  String get translationQueueCancel => '取消任务';

  @override
  String get translationQueueRelease => '从列表移除';

  @override
  String get translationQueueDownloads => '下载';

  @override
  String get translationQueueDownloadMdEmbedded => 'MD（内嵌图片）';

  @override
  String get translationQueueDownloadMdZip => 'MD（ZIP 图片包）';

  @override
  String get translationQueueExecutionModeQueued => '队列';

  @override
  String get translationQueueExecutionModeImmediate => '即时';

  @override
  String get translationQueueTaskTypeTranslation => '翻译';

  @override
  String get translationQueueTaskTypeConversion => '转换';

  @override
  String translationQueuePositionLabel(Object position) {
    return '排队位置 #$position';
  }

  @override
  String translationQueueLoadFailed(Object error) {
    return '加载任务失败：$error';
  }

  @override
  String translationQueueActionFailed(Object error) {
    return '操作失败：$error';
  }

  @override
  String translationQueueSubmittedBy(Object user) {
    return '发起人：$user';
  }

  @override
  String translationQueueStartedAt(Object time) {
    return '发起：$time';
  }

  @override
  String translationQueueCompletedAt(Object time) {
    return '完成：$time';
  }

  @override
  String get translationQueueTimeUnknown => '—';

  @override
  String get translationQueueGuestUser => '访客';

  @override
  String get translationQueueClearAllTooltip => '清空服务器任务队列与磁盘缓存结果（仅管理员）';

  @override
  String get translationQueueClearAllButton => '清空队列';

  @override
  String get translationQueueClearAllTitle => '清空任务队列';

  @override
  String get translationQueueClearAllMessage =>
      '将取消排队与进行中的任务，移除全部内存中的任务，并删除磁盘上的队列快照。此操作不可撤销。';

  @override
  String get translationQueueClearAllConfirm => '清空';

  @override
  String get translationQueueClearAllCancel => '取消';

  @override
  String get translationQueueClearAllSuccess => '已清空任务队列。';

  @override
  String translationQueueClearAllFailed(Object error) {
    return '清空失败：$error';
  }

  @override
  String get translationQueueClearMyQueueTooltip => '清空我的队列';

  @override
  String get translationQueueClearMyQueueTitle => '清空我的队列';

  @override
  String get translationQueueClearMyQueueMessage => '从队列中移除您的所有任务？';

  @override
  String get translationQueueClearMyQueueConfirm => '清空';

  @override
  String get translationQueueClearMyQueueCancel => '取消';

  @override
  String get translationQueueClearMyQueueSuccess => '已清空我的队列。';

  @override
  String translationQueueClearMyQueueFailed(Object error) {
    return '清空您的队列失败：$error';
  }

  @override
  String get translationQueueSelected => '已选';

  @override
  String get translationQueueSelectMode => '选择';

  @override
  String get translationQueueClearSelection => '清除选择';

  @override
  String translationQueueBatchDownloadFailed(Object error) {
    return '批量下载失败：$error';
  }

  @override
  String translationQueueBatchDownloadSuccess(Object fileType) {
    return '批量下载：$fileType 已就绪';
  }

  @override
  String get translationQueueView => '阅读编辑模式';

  @override
  String get homeFeatureUnderDevelopment => '此功能正在开发中。';

  @override
  String homeAnonymizeNotSupportedVersion(Object version) {
    return '尚未支持。将在 v$version 版本中提供。';
  }

  @override
  String get homeAnonymizeInDevelopment => '匿名化功能正在开发中，尚不可用。';

  @override
  String get homeScrollLeft => '向左滚动';

  @override
  String get homeScrollRight => '向右滚动';

  @override
  String get homeTabHome => '主页';

  @override
  String get homeToolbarAdBanner => '工具栏广告横幅\n（728×90 横幅 / 320×50 移动端）';

  @override
  String get homeSteps => '步骤';

  @override
  String get homePhaseUpload => '上传';

  @override
  String get homePhaseExtract => '提取';

  @override
  String get homePhaseGlossary => '术语表';

  @override
  String get homePhaseTranslate => '翻译';

  @override
  String get homePhaseViewer => '修订';

  @override
  String get homePhaseAnonymize => '匿名化';

  @override
  String get homePhaseDeAnonymize => '去匿名化';

  @override
  String get homePhaseExport => '导出';

  @override
  String get taskDefaultTitleTranslate => '任务';

  @override
  String get taskDefaultTitleAnonymize => '匿名化';

  @override
  String get homeReleaseNotesTitle => '更新说明';

  @override
  String get homeReleaseNotesViewOnGitHub => '在 GitHub 查看';

  @override
  String get homeEditionEnterprise => '企业版';

  @override
  String get homeEditionEnterpriseStatusActivated => '已激活';

  @override
  String get homeEditionActivateEnterprise => '激活企业版';

  @override
  String get homeEditionPro => '专业版';

  @override
  String get homeEditionStandard => '标准版';

  @override
  String get homeEditionStandardStatus => '永远可用';

  @override
  String homeEditionProStatusTrialRemaining(Object days) {
    return '剩余 $days 天';
  }

  @override
  String get homeEditionProStatusNotActivated => '未激活';

  @override
  String get homeEditionProStatusActivated => '已激活';

  @override
  String get homeWelcomeDearPro =>
      '沉浸式翻译：在界面内即时对照原文与译文。\n队列式翻译：将文档加入任务队列，按顺序完成整条流水线。';

  @override
  String get homeWelcomeDearStandard =>
      '沉浸式翻译：在界面内即时对照原文与译文。\n队列式翻译：将文档加入任务队列，按顺序完成整条流水线。';

  @override
  String get homeWelcomeDearProNoUser =>
      '沉浸式翻译：在界面内即时对照原文与译文。\n队列式翻译：将文档加入任务队列，按顺序完成整条流水线。';

  @override
  String get homeWelcomeDearStandardNoUser =>
      '沉浸式翻译：在界面内即时对照原文与译文。\n队列式翻译：将文档加入任务队列，按顺序完成整条流水线。';

  @override
  String get homeWelcomeHello =>
      '沉浸式翻译：在界面内即时对照原文与译文。\n队列式翻译：将文档加入任务队列，按顺序完成整条流水线。';

  @override
  String get homeLoading => '加载中...';

  @override
  String get homeWelcomeGuest => '欢迎！';

  @override
  String homeFileNotFound(Object fileName) {
    return '未找到文件：$fileName。文件可能已被移动或删除。';
  }

  @override
  String homeFileSelectedMismatch(Object expected, Object selected) {
    return '选定的文件名不匹配：$selected。预期：$expected';
  }

  @override
  String homeFileLoaded(Object fileName) {
    return '文件已加载：$fileName';
  }

  @override
  String get homeFileSelectionCancelled => '文件选择已取消。';

  @override
  String homeFileLoadFailed(Object error) {
    return '加载文件失败：$error';
  }

  @override
  String homeFlowCreateFailed(Object error) {
    return '创建流程失败：$error';
  }

  @override
  String commonPageNotFound(Object uri) {
    return '页面未找到：$uri';
  }

  @override
  String get commonGoHome => '返回主页';

  @override
  String get commonLogin => '登录';

  @override
  String get commonLogout => '退出登录';

  @override
  String get userMenuChangePassword => '修改密码';

  @override
  String get changePasswordCurrentPasswordLabel => '当前密码';

  @override
  String get changePasswordNewPasswordLabel => '新密码';

  @override
  String get changePasswordConfirmPasswordLabel => '确认新密码';

  @override
  String get changePasswordRequiredError => '当前密码和新密码不能为空。';

  @override
  String get changePasswordConfirmMismatchError => '两次输入的新密码不一致。';

  @override
  String get changePasswordSuccessMessage => '密码修改成功。';

  @override
  String get changePasswordRequirementsTitle => '密码要求';

  @override
  String get changePasswordRequirementLength => '8-128 个字符';

  @override
  String get changePasswordRequirementUppercase => '至少 1 个大写字母';

  @override
  String get changePasswordRequirementLowercase => '至少 1 个小写字母';

  @override
  String get changePasswordRequirementDigit => '至少 1 个数字';

  @override
  String get settingsTabsGeneral => '通用';

  @override
  String get settingsTabsAiPlatforms => 'AI 平台';

  @override
  String get settingsTabsParsingEngine => '解析引擎';

  @override
  String get settingsParsingEngineTitle => '解析引擎';

  @override
  String get settingsParsingEngineSubtitle => '选择用于文本提取和处理的文档解析引擎。';

  @override
  String get settingsParsingEngineLabel => '解析引擎';

  @override
  String get settingsParsingEngineMineru => 'MinerU (云端)';

  @override
  String get settingsParsingEngineMineruDesc => '支持 OCR 的高级文档解析';

  @override
  String get settingsParsingEngineMineruLocal => 'MinerU (本地)';

  @override
  String get settingsParsingEngineMineruLocalDesc => '本地部署 MinerU，API Key 可选';

  @override
  String get settingsParsingEnginePdfplumber => 'PDFPlumber';

  @override
  String get settingsParsingEnginePdfplumberDesc => '快速 PDF 文本提取';

  @override
  String get settingsParsingEngineTesseract => 'Tesseract OCR';

  @override
  String get settingsParsingEngineTesseractDesc => '基于OCR的文本提取';

  @override
  String get settingsFormulaOcr => '公式OCR';

  @override
  String get settingsFormulaOcrSubtitle => '为数学公式启用OCR';

  @override
  String get settingsTableOcr => '表格OCR';

  @override
  String get settingsTableOcrSubtitle => '为表格启用OCR';

  @override
  String get settingsAnonymizationNewTaskNotice => '更改仅对新任务生效';

  @override
  String get settingsParsingEngineNewTaskNotice => '更改仅对新任务生效';

  @override
  String get settingsPdfSplitMaxPages => 'PDF分片页数';

  @override
  String get settingsPdfSplitMaxWorkers => 'PDF分片并行数';

  @override
  String get settingsRequestRetryCount => '请求重试次数';

  @override
  String get settingsOcrLanguageTitle => 'OCR语言';

  @override
  String get settingsOcrLanguageSubtitle => '为图像和扫描文档中的文本识别配置OCR语言。';

  @override
  String get settingsOcrLanguageLabel => 'OCR语言';

  @override
  String get settingsOcrLangEnglish => '英语';

  @override
  String get settingsOcrLangChineseSimplified => '中文（简体）';

  @override
  String get settingsOcrLangChineseTraditional => '中文（繁体）';

  @override
  String get settingsOcrLangJapanese => '日语';

  @override
  String get settingsOcrLangKorean => '韩语';

  @override
  String get settingsOcrLangFrench => '法语';

  @override
  String get settingsOcrLangGerman => '德语';

  @override
  String get settingsOcrLangSpanish => '西班牙语';

  @override
  String get settingsOcrLangRussian => '俄语';

  @override
  String get settingsOcrLangArabic => '阿拉伯语';

  @override
  String get settingsOcrLangAuto => '自动检测';

  @override
  String get mineruLangAuto => '自动检测';

  @override
  String get mineruLangChServer => '中文（服务器版）';

  @override
  String get mineruLangChLite => '中文（精简版）';

  @override
  String get mineruLangTamil => '泰米尔语';

  @override
  String get mineruLangTelugu => '泰卢固语';

  @override
  String get mineruLangKannada => '卡纳达语';

  @override
  String get mineruLangLatinScript => '拉丁字母';

  @override
  String get mineruLangArabicScript => '阿拉伯字母';

  @override
  String get mineruLangEastSlavic => '东斯拉夫语';

  @override
  String get mineruLangCyrillicScript => '西里尔字母';

  @override
  String get mineruLangDevanagariScript => '天城文';

  @override
  String get settingsTabsGlossary => '术语表';

  @override
  String get settingsGlossaryManagementTitle => '术语表管理';

  @override
  String get settingsGlossaryManagementSubtitle => '管理您的术语条目以确保翻译质量的一致性。';

  @override
  String get settingsGlossarySelectGlossary => '选择术语表';

  @override
  String get settingsGlossaryCreateGlossary => '创建';

  @override
  String get settingsGlossaryImportCsv => '导入';

  @override
  String get settingsGlossaryExport => '导出';

  @override
  String get settingsGlossaryExportAll => '导出全部';

  @override
  String get settingsGlossaryDeleteGlossary => '删除';

  @override
  String get settingsGlossarySaveZip => '保存ZIP';

  @override
  String settingsGlossaryEntriesTitle(Object count) {
    return '术语表条目（$count）';
  }

  @override
  String get settingsGlossaryAddEntry => '添加条目';

  @override
  String get settingsGlossaryNoEntriesYet => '尚无术语表条目。\n添加您的第一个条目以开始使用。';

  @override
  String get settingsGlossaryFilterLabel => '筛选：';

  @override
  String get settingsGlossaryFilterAll => '全部';

  @override
  String get settingsGlossaryFilterUncategorized => '未分类';

  @override
  String get settingsGlossaryTableSource => '源文本';

  @override
  String get settingsGlossaryTableTarget => '目标文本';

  @override
  String get settingsGlossaryTableCategory => '类别（可选）';

  @override
  String get settingsGlossaryTableTargetLang => '目标语言';

  @override
  String get settingsGlossaryCategoryHint => '类别';

  @override
  String get settingsGlossaryUncategorizedDisplay => '（未分类）';

  @override
  String get settingsGlossaryCopyAction => '复制';

  @override
  String get settingsGlossaryCopiedToClipboard => '已复制到剪贴板';

  @override
  String get settingsGlossaryDeleteDialogTitle => '删除术语表';

  @override
  String settingsGlossaryDeleteDialogMessage(Object id) {
    return '确定要删除此术语表吗？\nID：$id';
  }

  @override
  String get settingsGlossaryCancel => '取消';

  @override
  String get settingsGlossaryDelete => '删除';

  @override
  String get settingsGlossaryCreateDialogTitle => '创建术语表';

  @override
  String get settingsGlossaryNameLabel => '名称';

  @override
  String get settingsGlossaryDescriptionLabel => '描述（可选）';

  @override
  String get settingsGlossaryGlobalGlossary => '全局术语表';

  @override
  String get settingsGlossaryGlobalGlossarySubtitle => '如果关闭，它将是您的个人术语表';

  @override
  String get settingsGlossaryCreate => '创建';

  @override
  String get settingsGlossaryNameRequired => '名称是必填项';

  @override
  String settingsGlossaryCreatedSnack(Object name) {
    return '已创建：$name';
  }

  @override
  String settingsGlossaryCreateFailedSnack(Object error) {
    return '创建失败：$error';
  }

  @override
  String get settingsGlossaryAddEntryDialogTitle => '向术语表添加条目';

  @override
  String get settingsGlossarySourceTextLabel => '源文本';

  @override
  String get settingsGlossaryTargetTextLabel => '目标文本';

  @override
  String get settingsGlossaryCategoryOptionalLabel => '类别（可选）';

  @override
  String get settingsGlossaryCategoryOptionalHint => '留空表示未分类';

  @override
  String get settingsGlossaryAdd => '添加';

  @override
  String get settingsGlossarySourceTargetRequired => '源文本和目标文本是必填项';

  @override
  String get settingsGlossaryEntryAddedSnack => '条目已添加';

  @override
  String settingsGlossaryAddFailedSnack(Object error) {
    return '失败：$error';
  }

  @override
  String get settingsGlossaryImportDialogTitle => '导入CSV/TBX到术语表';

  @override
  String get settingsGlossaryMergeModeLabel => '合并模式';

  @override
  String get settingsGlossaryMergeUpdate => '更新（插入/更新）';

  @override
  String get settingsGlossaryMergeAppend => '追加（仅新增）';

  @override
  String get settingsGlossaryMergeReplace => '替换（覆盖全部）';

  @override
  String get settingsGlossaryImport => '导入';

  @override
  String get settingsGlossaryUnableToReadFile => '无法读取文件';

  @override
  String settingsGlossaryImportedSnack(Object count) {
    return '已导入：$count 项';
  }

  @override
  String settingsGlossaryImportFailedSnack(Object error) {
    return '失败：$error';
  }

  @override
  String get settingsGlossaryExportDialogTitle => '导出术语表';

  @override
  String get settingsGlossarySaveCsv => '保存CSV/TBX';

  @override
  String get settingsGlossaryDownload => '下载';

  @override
  String settingsGlossaryDownloadedSnack(Object info) {
    return '已下载：$info';
  }

  @override
  String settingsGlossaryExportFailedSnack(Object error) {
    return '失败：$error';
  }

  @override
  String settingsGlossaryLoadedSnack(Object count) {
    return '已加载 $count 个条目';
  }

  @override
  String settingsGlossaryLoadFailedSnack(Object error) {
    return '加载失败：$error';
  }

  @override
  String settingsGlossaryDeletedSnack(Object id) {
    return '术语表已删除：$id';
  }

  @override
  String settingsGlossaryDeleteFailedSnack(Object error) {
    return '删除失败：$error';
  }

  @override
  String settingsGlossaryExportAllFailedSnack(Object error) {
    return '导出全部失败：$error';
  }

  @override
  String get settingsGlossaryEntryUpdatedSnack => '条目已更新';

  @override
  String settingsGlossaryUpdateFailedSnack(Object error) {
    return '更新失败：$error';
  }

  @override
  String get settingsGlossaryEntryDeletedSnack => '条目已删除';

  @override
  String settingsGlossaryDeleteEntryFailedSnack(Object error) {
    return '删除失败：$error';
  }

  @override
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type) {
    return '$name ($type) · $count 项';
  }

  @override
  String settingsGlossaryErrorPrefix(Object error) {
    return '错误：$error';
  }

  @override
  String settingsGlossaryExportedAllSnack(Object info) {
    return '已导出：$info';
  }

  @override
  String settingsGlossaryEntryCount(Object count) {
    return '条目数量：$count';
  }

  @override
  String get settingsGlossaryEdit => '编辑';

  @override
  String get settingsGlossaryConfirmDeleteEntryTitle => '确认删除';

  @override
  String settingsGlossaryConfirmDeleteEntryMessage(Object source) {
    return '确定要删除条目「$source」吗？';
  }

  @override
  String get settingsGlossaryEditEntryDialogTitle => '编辑条目';

  @override
  String get settingsGlossaryUpdate => '更新';

  @override
  String get settingsGlossaryEntryDeleteFailedSnack => '删除条目失败';

  @override
  String get settingsGlossaryEmptyStateTitle => '暂无术语表。请先创建您的第一个术语表。';

  @override
  String get settingsGlossaryTooltipCreate => '创建新术语表';

  @override
  String get settingsGlossaryTooltipImport => '从 CSV 或 TBX 格式导入条目';

  @override
  String get settingsGlossaryTooltipExport => '将选中的术语表导出为 CSV 或 TBX 格式';

  @override
  String get settingsGlossaryTooltipExportAll => '将所有术语表导出为 ZIP 压缩包';

  @override
  String get settingsGlossaryTooltipDeleteGlossary => '永久删除选中的术语表';

  @override
  String get settingsGlossaryBatchEditCategory => '编辑分类';

  @override
  String get settingsGlossaryBatchDelete => '删除';

  @override
  String get settingsGlossaryBatchDeselect => '取消选择';

  @override
  String settingsGlossaryBatchSelectedCount(Object count) {
    return '已选 $count 项';
  }

  @override
  String get settingsGlossaryExportFormatLabel => '导出格式';

  @override
  String get settingsGlossaryExportFormatCsv => 'CSV';

  @override
  String get settingsGlossaryExportFormatTbx => 'TBX（TermBase eXchange）';

  @override
  String get settingsGlossaryExportSourceLanguage => '源语言';

  @override
  String get settingsGlossaryExportSaveTbxTitle => '保存 TBX 文件';

  @override
  String get settingsGlossaryDeleteEntriesTitle => '删除条目';

  @override
  String settingsGlossaryDeleteEntriesBody(Object count) {
    return '删除已选的 $count 条条目？此操作不可撤销。';
  }

  @override
  String get settingsGlossaryDeleteEntriesConfirm => '删除';

  @override
  String get settingsGlossaryEditCategoryTitle => '编辑分类';

  @override
  String settingsGlossaryEditCategoryBody(Object count) {
    return '为已选的 $count 条条目设置分类：';
  }

  @override
  String get settingsGlossaryEditCategoryLabel => '分类';

  @override
  String get settingsGlossaryEditCategoryHint => '输入分类名称';

  @override
  String get settingsGlossaryEditCategoryApply => '应用';

  @override
  String get glossaryPanelSaveNameHint => '输入名称或选择已有术语表...';

  @override
  String get glossaryPanelClearSelection => '清除选择';

  @override
  String get glossaryPanelListTitle => '术语表';

  @override
  String get glossaryPanelNoEntries => '无条目';

  @override
  String get glossaryPanelOneEntry => '1 条';

  @override
  String glossaryPanelEntriesCount(Object count) {
    return '$count 条';
  }

  @override
  String get glossaryPanelProcessing => '处理中...';

  @override
  String get glossaryPanelDropCsvHere => '将 CSV 或 TBX 文件拖放到此处';

  @override
  String get glossaryPanelNoEntriesHint =>
      '暂无术语表条目。\n点击「识别术语表」开始，或从列表选择术语表查看条目，也可拖放 CSV 或 TBX 文件到此。';

  @override
  String get glossaryPanelSelectBody => '选择一个术语表进行操作：';

  @override
  String get glossaryPanelSaveDialogTitleReplace => '替换术语表';

  @override
  String get glossaryPanelSaveDialogTitleSave => '保存术语表';

  @override
  String glossaryPanelSaveReplaceInfo(Object name) {
    return '这将替换现有术语表 \"$name\"';
  }

  @override
  String get glossaryPanelSaveButtonSaveAs => '另存为';

  @override
  String get glossaryPanelGenerating => '正在生成术语表...';

  @override
  String get glossaryPanelDeleteEntry => '删除条目';

  @override
  String get glossaryPanelInvertSelection => '反向选择';

  @override
  String get glossaryWidgetTitle => '术语表';

  @override
  String get glossaryWidgetRefreshTooltip => '刷新术语表列表';

  @override
  String glossaryWidgetGlossariesSelected(Object count) {
    return '已选 $count 个术语表';
  }

  @override
  String glossaryWidgetGlossariesSelectedPlural(Object count) {
    return '已选 $count 个术语表';
  }

  @override
  String get glossaryWidgetSelectGlossaries => '选择术语表';

  @override
  String glossaryWidgetLoadFailed(Object error) {
    return '加载术语表失败：$error';
  }

  @override
  String get glossaryWidgetNoGlossariesHint => '暂无术语表。请在设置 -> 术语表中创建。';

  @override
  String glossaryWidgetTypeCountItems(Object type, Object count) {
    return '$type · $count 条';
  }

  @override
  String glossaryWidgetTermsExtracted(Object count) {
    return '从翻译中提取 $count 个术语';
  }

  @override
  String glossaryWidgetPersonalCreated(Object count) {
    return '个人术语表创建成功！\n已添加 $count 个术语。';
  }

  @override
  String glossaryWidgetPersonalReplaced(Object total) {
    return '个人术语表替换成功！\n共 $total 个术语。';
  }

  @override
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total) {
    return '已向个人术语表添加 $newCount 个新术语。\n跳过 $skipped 个已存在术语。\n共 $total 个术语。';
  }

  @override
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total) {
    return '个人术语表更新成功！\n新增 $newCount 个，更新 $updatedCount 个。\n共 $total 个术语。';
  }

  @override
  String glossaryWidgetAddToPersonalFailed(Object error) {
    return '添加到个人术语表失败：$error';
  }

  @override
  String get settingsTabsTranslation => '翻译';

  @override
  String get settingsTabsAnonymization => '匿名化';

  @override
  String get settingsTabsUserManagement => '用户管理';

  @override
  String get settingsUserManagementTitle => '用户管理模式';

  @override
  String get settingsUserManagementSubtitle =>
      '选择 Web 部署下的登录与权限策略。设置和配置向导仅管理员可用。';

  @override
  String get settingsUserManagementModeNoLogin => '用户免登录';

  @override
  String get settingsUserManagementModeNoLoginDesc =>
      '无需登录即可使用；设置与配置向导仅管理员登录后可用。';

  @override
  String get settingsUserManagementModeLdap => 'LDAP 登录';

  @override
  String get settingsUserManagementModeLdapDesc =>
      '使用 LDAP/AD 域账号登录；设置与配置向导仅管理员（域内指定组）可用。';

  @override
  String get settingsUserManagementModeLocal => '本地用户登录';

  @override
  String get settingsUserManagementModeLocalDesc => '使用服务器本地用户列表验证登录。';

  @override
  String get settingsUserManagementInDevelopment => '开发中';

  @override
  String get settingsUserManagementSaveSuccess => '用户管理模式已保存';

  @override
  String settingsUserManagementSaveFailed(Object message) {
    return '保存失败：$message';
  }

  @override
  String get settingsLdapEnabled => '启用 LDAP 登录';

  @override
  String get settingsLdapEnableHint => '启用前需先通过「测试 LDAP 连接」';

  @override
  String get settingsLdapProtocol => '协议';

  @override
  String get settingsLdapProtocolLdap => 'LDAP';

  @override
  String get settingsLdapProtocolLdaps => 'LDAPS';

  @override
  String get settingsLdapHost => 'LDAP 服务器（与证书 CN/SAN 匹配）';

  @override
  String get settingsLdapHostPlaceholder => 'ad.example.com 或 192.168.x.x';

  @override
  String get settingsLdapPort => '端口';

  @override
  String get settingsLdapPortPlaceholder => '389';

  @override
  String get settingsLdapBaseDn => '用户搜索 Base DN';

  @override
  String get settingsLdapBaseDnPlaceholder => 'OU=Users,DC=example,DC=com';

  @override
  String get settingsLdapBindDnTemplate => '绑定 DN 模板';

  @override
  String settingsLdapBindDnPlaceholder(Object username) {
    return 'EXAMPLE\\$username 或 $username@example.com';
  }

  @override
  String get settingsLdapUserFilter => '用户过滤';

  @override
  String settingsLdapUserFilterPlaceholder(Object username) {
    return '(sAMAccountName=$username)';
  }

  @override
  String get settingsLdapAdminGroupEnabled => '启用管理员组查询';

  @override
  String get settingsLdapAdminGroup => '管理员组名';

  @override
  String get settingsLdapAdminGroupPlaceholder => 'Owlangs-Admins';

  @override
  String get settingsLdapGroupBaseDn => '组搜索 Base DN';

  @override
  String get settingsLdapGroupBaseDnPlaceholder =>
      'OU=Groups,DC=example,DC=com';

  @override
  String get settingsLdapTlsVerify => '验证 TLS 证书';

  @override
  String get settingsLdapTlsCacertfile => 'TLS CA 证书文件路径';

  @override
  String get settingsLdapTlsCacertfilePlaceholder => '/path/to/ca.crt';

  @override
  String get settingsLdapTestConnection => '测试 LDAP 连接';

  @override
  String get settingsLdapSaveConfig => '保存 LDAP 配置';

  @override
  String get settingsLdapTestDialogTitle => '测试 LDAP 连接';

  @override
  String get settingsLdapTestUsername => '用户名（不含域）';

  @override
  String get settingsLdapTestUsernamePlaceholder => 'testuser';

  @override
  String get settingsLdapTestPassword => '密码';

  @override
  String get settingsLdapTestPasswordPlaceholder => '********';

  @override
  String get settingsLdapTestStart => '开始测试';

  @override
  String get settingsLdapTestSuccess => 'LDAP 连接测试成功，可以启用 LDAP。';

  @override
  String get settingsLdapTestFailed => 'LDAP 连接测试失败';

  @override
  String get settingsLdapConfigSaved => 'LDAP 配置已保存';

  @override
  String get settingsLdapEnableRequireTest => '请先测试 LDAP 连接通过后再启用 LDAP。';

  @override
  String get settingsAdminOnlyDialogTitle => '仅管理员可访问';

  @override
  String get settingsAdminOnlyDialogMessage => '设置与配置向导仅对管理员开放。请登录管理员账号后再进行设置。';

  @override
  String get settingsAdminOnlyDialogGoToLogin => '去登录';

  @override
  String get settingsAdminOnlyDialogClose => '关闭';

  @override
  String get aiPlatformOverview => '平台概览';

  @override
  String aiPlatformConfiguredCount(Object configured, Object total) {
    return '已配置 $configured/$total 个平台';
  }

  @override
  String get aiPlatformTestApiStatus => '测试API状态';

  @override
  String get aiPlatformTesting => '测试中...';

  @override
  String get aiPlatformCategoryLanguageModels => '语言模型';

  @override
  String get aiPlatformCategoryParsingEngines => '解析引擎';

  @override
  String aiPlatformConfiguredDragReorder(Object configured, Object total) {
    return '已配置 $configured/$total 个平台（拖动以重新排序）';
  }

  @override
  String get aiPlatformNotConfigured => '未配置';

  @override
  String get aiPlatformNotTested => '未测试';

  @override
  String get aiPlatformApiAvailable => 'API可用';

  @override
  String get aiPlatformAvailable => '可用';

  @override
  String get aiPlatformUnavailable => '不可用';

  @override
  String get aiPlatformConfigure => '配置';

  @override
  String aiPlatformConfigureTitle(Object name) {
    return '配置 $name';
  }

  @override
  String get aiPlatformBasicInformation => '基本信息';

  @override
  String get aiPlatformPlatformName => '平台名称';

  @override
  String get aiPlatformPlatformNameHint => '例如，豆包（DeepSeek / Volcano Ark）';

  @override
  String get aiPlatformApiUrl => 'API URL';

  @override
  String get aiPlatformApiUrlHint =>
      'e.g., https://ark.cn-beijing.volces.com/api/v3';

  @override
  String get aiPlatformMaxTokens => '最大词元数';

  @override
  String get aiPlatformMaxTokensHint => '例如，4096';

  @override
  String get aiPlatformChunkSize => '分块大小（词元）';

  @override
  String get aiPlatformChunkSizeHint => '例如，3000';

  @override
  String get aiPlatformConcurrent => '并发请求数';

  @override
  String get aiPlatformConcurrentHint => '例如，5';

  @override
  String get aiPlatformModel => '模型';

  @override
  String get aiPlatformModelHint => '例如，deepseek-v3 / llama3.1-70b';

  @override
  String get aiPlatformApiKey => 'API密钥';

  @override
  String get aiPlatformApiConfiguration => 'API配置';

  @override
  String get aiPlatformGetApiKey => '获取API密钥';

  @override
  String get aiPlatformCancel => '取消';

  @override
  String get aiPlatformTestConnection => '测试连接';

  @override
  String get aiPlatformTestConnectionHint => '配置完成后，请点击下方“测试连接”，检查该平台是否可用。';

  @override
  String get setupWizardConfigureApiKeyAndTest =>
      '当前连接不可用，请配置 API Key 并点击「测试连接」以确认平台可用。';

  @override
  String get setupWizardSaveAndExit => '保存并退出';

  @override
  String get setupWizardTitle => '配置向导';

  @override
  String get setupWizardStepWelcome => '欢迎';

  @override
  String get setupWizardStepMineru => 'PDF / MinerU 配置';

  @override
  String get setupWizardWelcomeIntro => '本向导将帮助你完成两个关键配置：';

  @override
  String get setupWizardWelcomeBody =>
      '1. 选择并配置主用的大语言模型平台。\n2. 若需要翻译 PDF/PNG 等文件格式，需配置解析引擎 MinerU（可选）。\n\n注意：在配置完成后，请使用「测试连接」确认配置可用。';

  @override
  String get setupWizardUiLanguageLabel => '界面语言';

  @override
  String get setupWizardMineruQuestion => '是否需要在本机翻译 PDF / 图片等文档？';

  @override
  String get setupWizardMineruYes => '需要（推荐，启用 MinerU 文档解析能力）';

  @override
  String get setupWizardMineruNo => '暂时不需要（仅使用大语言模型翻译纯文本等）';

  @override
  String get setupWizardMineruDescription =>
      'MinerU 负责 PDF / 图片等文档的版面解析与切分。\n请在下方填写 MinerU 的 API Key 和接口地址，并点击「测试连接」确认可用。';

  @override
  String get setupWizardMineruSkipped =>
      '你选择了暂时不配置 MinerU，后续仍可在设置中随时开启 PDF 翻译能力。';

  @override
  String get setupWizardMineruConfigTitle => 'MinerU 配置（解析引擎）';

  @override
  String get setupWizardSelectMineruPlatform => '选择 MinerU 平台';

  @override
  String get setupWizardMineruCloudOption => 'MinerU (云端) - 官方云服务';

  @override
  String get setupWizardMineruLocalOption => 'MinerU (本地) - 自托管部署';

  @override
  String get setupWizardSelectLlmPlatform => '选择大语言模型平台';

  @override
  String get setupWizardNoLlmPlatforms =>
      '当前未在「AI 平台设置」中配置任何大语言模型平台，请先前往设置中添加平台。';

  @override
  String get setupWizardMineruSaved => 'MinerU 配置已保存';

  @override
  String get setupWizardPrevStep => '上一步';

  @override
  String get setupWizardNextStep => '下一步';

  @override
  String get aiPlatformSave => '保存';

  @override
  String get aiPlatformList => '列表';

  @override
  String get aiPlatformTemperature => '温度';

  @override
  String get aiPlatformThinkingMode => '思考模式';

  @override
  String get aiPlatformThinkingDisable => '禁用（推荐）';

  @override
  String get aiPlatformThinkingEnable => '启用';

  @override
  String get aiPlatformThinkingDefault => '默认';

  @override
  String get aiPlatformThinkingHint => '启用AI推理过程以获得更好的翻译质量';

  @override
  String get aiPlatformPleaseEnterApiKeyFirst => '请先输入API密钥';

  @override
  String get aiPlatformPleaseEnterApiUrlFirst => '请先输入API URL';

  @override
  String get aiPlatformHasApiKey => '需要API密钥';

  @override
  String get aiPlatformHasApiKeyHint => '本地部署无需认证时请取消勾选';

  @override
  String get aiPlatformApiKeyOptionalHint => '如无需验证可留空';

  @override
  String get optional => '可选';

  @override
  String get aiPlatformConnectionTestSucceeded => '连接测试成功';

  @override
  String aiPlatformConnectionTestFailed(Object message) {
    return '连接测试失败：$message';
  }

  @override
  String get aiPlatformNoModelsFound => '未找到模型';

  @override
  String get aiPlatformFailedToLoadModels => '加载模型失败';

  @override
  String aiPlatformErrorLoadingModels(Object error) {
    return '加载模型错误：$error';
  }

  @override
  String get aiPlatformSelectModel => '选择模型';

  @override
  String get aiPlatformNoModelsAvailable => '无可用模型';

  @override
  String get aiPlatformMineruSettings => 'MinerU设置';

  @override
  String get aiPlatformEnterMineruApiKey => '输入MinerU API密钥';

  @override
  String get aiPlatformGetMineruApiKey => '获取MinerU API密钥';

  @override
  String get aiPlatformModelVersion => '模型版本';

  @override
  String get aiPlatformModelVersionHint => 'vlm';

  @override
  String get aiPlatformMineruApiUrlHint => 'https://mineru.net/api/v4';

  @override
  String get aiPlatformOcrSettings => 'OCR设置';

  @override
  String get aiPlatformFormulaOcr => '公式OCR';

  @override
  String get aiPlatformFormulaOcrSubtitle => '为数学公式启用OCR';

  @override
  String get aiPlatformTableOcr => '表格OCR';

  @override
  String get aiPlatformTableOcrSubtitle => '为表格启用OCR';

  @override
  String get settingsFontEditSizeTitle => '编辑字体大小';

  @override
  String get settingsFontEditSizeSubtitle => '编辑翻译片段时的字体大小';

  @override
  String get settingsTranslationTitle => '翻译设置';

  @override
  String get settingsTranslationNotice => '这些设置仅适用于新的翻译任务。';

  @override
  String get settingsTranslationAutoGlossaryTitle => '自动生成术语表';

  @override
  String get settingsTranslationAutoGlossarySubtitle => '翻译后自动生成术语表（适用于新任务）';

  @override
  String get settingsTranslationParamsTitle => '翻译参数';

  @override
  String get settingsTranslationConcurrentTitle => '并发请求数';

  @override
  String get settingsTranslationConcurrentHint => '推荐：3（根据模型和配额调整1–8）';

  @override
  String get settingsTranslationTimeoutTitle => '超时（秒）';

  @override
  String get settingsTranslationTimeoutHint => '120（推荐：120-300秒）';

  @override
  String get settingsTranslationChunkRetryTitle => '分块/API 重试次数';

  @override
  String get settingsTranslationChunkRetryHint => '推荐：3–5（单次分块翻译或接口失败时的重试）';

  @override
  String get settingsTranslationSegmentAutoRetryTitle => '队列模式：译后失败片段自动重试轮数';

  @override
  String get settingsTranslationSegmentAutoRetryHint =>
      '推荐：3（主翻译结束后批量补译失败片段，共 1–10 轮；仅队列模式）';

  @override
  String get settingsTranslationChunkSizeTitle => '分块大小（词元）';

  @override
  String get settingsTranslationChunkSizeHint => '推荐：每个请求3000词元（根据模型上下文大小调整）';

  @override
  String get settingsExclusionTitle => '默认排除规则';

  @override
  String get settingsExclusionNotice => '切换开启 = 提取时自动排除；切换关闭 = 仅检测（用户决定每个片段）。';

  @override
  String get settingsExclusionImageTitle => '图像';

  @override
  String get settingsExclusionImageSubtitle => '图像占位符和纯图像内容';

  @override
  String get settingsExclusionFormulaTitle => '公式';

  @override
  String get settingsExclusionFormulaSubtitle => 'LaTeX / MathML公式';

  @override
  String get settingsExclusionReferenceTitle => '参考文献';

  @override
  String get settingsExclusionReferenceSubtitle => '引用和参考文献';

  @override
  String get settingsExclusionIdentifierTitle => '标识符';

  @override
  String get settingsExclusionIdentifierSubtitle => 'URL、电子邮件、序列号、代码片段';

  @override
  String get settingsExclusionStructuralTitle => '结构';

  @override
  String get settingsExclusionStructuralSubtitle => '页眉、页脚、脚注、页码';

  @override
  String get settingsExclusionTableTitle => '表格';

  @override
  String get settingsExclusionTableSubtitle => '表格内容（markdown / PDF表格）';

  @override
  String get settingsExclusionLanguageMatchTitle => '语言匹配';

  @override
  String get settingsExclusionLanguageMatchSubtitle => '源语言与目标语言匹配';

  @override
  String get settingsLanguageDialogTitle => '选择语言';

  @override
  String get settingsUnitPt => 'pt';

  @override
  String get glossaryGeneratedTabTitle => '生成的术语表';

  @override
  String glossaryErrorRefresh(Object error) {
    return '刷新术语表失败：$error';
  }

  @override
  String get glossaryWarningNoGenerated => '无可用生成的术语表';

  @override
  String get glossaryPanelView => '查看';

  @override
  String get glossaryPanelAddToPersonal => '添加到个人';

  @override
  String get glossaryPanelNoGlobalGlossaries => '没有可用的全局术语表';

  @override
  String get glossaryPanelSelectTitle => '选择术语表';

  @override
  String get glossaryPanelSelectHint => '请选择术语表...';

  @override
  String glossaryPanelSelected(Object name) {
    return '已选择：$name';
  }

  @override
  String get glossaryPanelSelectConfirm => '选择';

  @override
  String get glossaryPanelMergeToCurrent => '合并到当前术语表';

  @override
  String glossaryPanelLoadedGlossary(Object name) {
    return '已加载术语表：$name';
  }

  @override
  String glossaryPanelLoadFailed(Object error) {
    return '加载术语表失败：$error';
  }

  @override
  String glossaryPanelMergedIntoCurrent(Object glossaryName) {
    return '已将“$glossaryName”合并到当前术语表';
  }

  @override
  String glossaryPanelMergeFailed(Object error) {
    return '合并失败：$error';
  }

  @override
  String get glossaryPanelEnterName => '请输入术语表名称';

  @override
  String get glossaryPanelSaveDialogHint => '输入术语表名称，或选择一个已有术语表进行替换：';

  @override
  String get glossaryPanelReplaceTitle => '替换全局术语表';

  @override
  String glossaryPanelReplaceBody(Object glossaryName) {
    return '这将用当前术语表条目替换“$glossaryName”中的全部条目。是否继续？';
  }

  @override
  String get glossaryPanelReplaceConfirm => '替换';

  @override
  String glossaryPanelReplacedGlobal(Object name) {
    return '已替换全局术语表：$name';
  }

  @override
  String glossaryPanelSavedAsNewGlobal(Object name) {
    return '已保存为新的全局术语表：$name';
  }

  @override
  String glossaryPanelSaveFailed(Object error) {
    return '保存失败：$error';
  }

  @override
  String get glossaryPanelDetect => '识别术语表';

  @override
  String get glossaryPanelEdit => '编辑';

  @override
  String get glossaryPanelCreate => '创建术语表';

  @override
  String get glossaryPanelSelect => '选择';

  @override
  String get glossaryPanelImport => '导入';

  @override
  String get glossaryPanelExport => '导出';

  @override
  String get glossaryPanelSave => '保存';

  @override
  String get glossaryPanelAddEntry => '添加条目';

  @override
  String get glossaryPanelClear => '清空';

  @override
  String get glossaryPanelApply => '应用';

  @override
  String get glossaryPanelColumnSource => '源文本';

  @override
  String get glossaryPanelColumnTarget => '目标文本';

  @override
  String get glossaryPanelColumnActions => '操作';

  @override
  String get translationStepsUploadTooltipReady => '已选择文件';

  @override
  String get translationStepsUploadTooltipNotReady => '请选择文件以开始';

  @override
  String get translationStepsExtractTooltipReady => '查看提取结果';

  @override
  String get translationStepsExtractTooltipNotReady => '导入后可进行提取';

  @override
  String get translationStepsGlossaryTooltipSkipped => '已跳过术语表';

  @override
  String get translationStepsGlossaryTooltipEnabled => '术语表已启用';

  @override
  String get translationStepsGlossaryTooltipDisabled => '生成或选择术语表以启用';

  @override
  String get translationStepsTranslateTooltipReady => '翻译已完成';

  @override
  String get translationStepsTranslateTooltipNotReady => '运行翻译以启用';

  @override
  String get glossaryDialogAddTitle => '添加到个人术语表';

  @override
  String glossaryDialogAddBody(Object termCount) {
    return '这将添加 $termCount 个术语到您的个人术语表。';
  }

  @override
  String get glossaryDialogAddPreviewTitle => '预览（前5个术语）：';

  @override
  String glossaryDialogAddMoreTerms(Object remainingCount) {
    return '... 以及另外 $remainingCount 个术语';
  }

  @override
  String get glossaryDialogMergeStrategyTitle => '合并策略：';

  @override
  String get glossaryDialogMergeUpdateTitle => '更新（推荐）';

  @override
  String get glossaryDialogMergeUpdateSubtitle => '更新现有术语，添加新术语';

  @override
  String get glossaryDialogMergeAppendTitle => '追加';

  @override
  String get glossaryDialogMergeAppendSubtitle => '仅添加新术语，跳过现有术语';

  @override
  String get glossaryDialogMergeReplaceTitle => '替换';

  @override
  String get glossaryDialogMergeReplaceSubtitle => '用这些术语替换整个术语表';

  @override
  String get glossaryDialogCancel => '取消';

  @override
  String get glossaryDialogReviewAndAdd => '审阅并添加';

  @override
  String get glossaryConfirmAddTitle => '确认添加到个人术语表';

  @override
  String glossaryConfirmAddBody(Object termCount) {
    return '将 $termCount 个术语添加到您的个人术语表？';
  }

  @override
  String get glossaryConfirmAddStrategyUpdate => '策略：更新现有术语，添加新术语';

  @override
  String get glossaryConfirmAddStrategyAppend => '策略：仅添加新术语，跳过现有术语';

  @override
  String get glossaryConfirmAddStrategyReplace => '策略：替换整个术语表';

  @override
  String get glossaryConfirmAddAutoCreateHint => '如果您的个人术语表不存在，它将自动创建。';

  @override
  String get glossaryConfirmAddButton => '添加';

  @override
  String get glossaryExportDialogTitle => '将术语表另存为';

  @override
  String glossaryExportSuccess(Object filename) {
    return '术语表已导出：$filename';
  }

  @override
  String glossaryExportFailed(Object error) {
    return '导出术语表失败：$error';
  }

  @override
  String glossaryCsvValidationFailed(Object errors) {
    return 'CSV文件验证失败：\n\n$errors';
  }

  @override
  String get glossaryCsvNoValidEntries => 'CSV文件不包含有效条目。';

  @override
  String get glossaryImportDialogTitle => '导入术语表';

  @override
  String glossaryImportDialogBodyEmpty(Object count) {
    return '在文件中找到 $count 个条目。\n\n当前术语表为空。导入的条目将被添加。';
  }

  @override
  String glossaryImportDialogBody(Object count) {
    return '在文件中找到 $count 个条目。\n\n选择导入方式：';
  }

  @override
  String get glossaryImportButtonImport => '导入';

  @override
  String get glossaryImportButtonReplace => '替换';

  @override
  String get glossaryImportButtonMerge => '合并';

  @override
  String glossaryImportResult(Object count, Object mode) {
    return '已导入 $count 个条目（$mode）';
  }

  @override
  String glossaryErrorImport(Object error) {
    return '导入术语表失败：$error';
  }

  @override
  String get glossaryErrorFileData => '无法读取文件数据。请重试。';

  @override
  String get glossaryErrorFilePath => '文件路径不可用。请重试。';

  @override
  String get glossaryErrorOnlyCsv => '仅支持CSV和TBX文件进行术语表导入。';

  @override
  String get glossaryExportFormatLabel => '导出格式';

  @override
  String get glossaryExportFormatTbxSubtitle => 'TermBase eXchange（ISO 12620）';

  @override
  String get glossaryExportSourceLanguage => '源语言';

  @override
  String get glossaryExportButtonExport => '导出';

  @override
  String get extractFormatConversionFailed => '格式转换失败。';

  @override
  String get fileUploadDisabledMessage => '文件选择已禁用（处理进行中）';

  @override
  String get fileUploadSupportedFormats =>
      '支持：Word (DOCX)、PowerPoint (PPTX)、Excel (XLSX/CSV)、PDF、Markdown、TXT、HTML、SRT、JSON、EPUB、MOBI、Qt TS、PNG、JPEG';

  @override
  String get fileUploadDropHere => '将文件拖放到此处';

  @override
  String get fileUploadHint => '拖放文件到此处或点击选择';

  @override
  String get fileUploadCancelTask => '取消当前任务';

  @override
  String get exclusionPanelExcludeAll => '全部排除';

  @override
  String get exclusionPanelCancelUserExclusion => '恢复自动排除';

  @override
  String get exclusionPanelClearAllExclusions => '清除所有排除';

  @override
  String get exclusionPanelExclusionByType => '按类型排除：';

  @override
  String get exclusionPanelStructuralHeader => '结构（页眉）';

  @override
  String get exclusionPanelStructuralFooter => '结构（页脚）';

  @override
  String get exclusionPanelUserExcluded => '用户已排除';

  @override
  String get exclusionPanelExcluded => '已排除';

  @override
  String get exclusionPanelFilterDisplayMode => '筛选显示模式：';

  @override
  String get exclusionPanelRebuild => '重建';

  @override
  String get exclusionPanelPage => '页面';

  @override
  String get exclusionPanelRebuildTooltip => '仅在新分页中显示匹配的片段';

  @override
  String get exclusionPanelPageTooltip => '在当前页面内筛选';

  @override
  String get exclusionPanelSegmentTypeFilters => '片段类型筛选器：';

  @override
  String get exclusionPanelCollapsePanelTooltip => '折叠面板';

  @override
  String get exclusionPanelExclusionControls => '排除控制：';

  @override
  String exclusionPanelExcludeCategory(Object count, Object name) {
    return '排除 $name ($count)';
  }

  @override
  String get exclusionPanelChangeReasonTitle => '更改排除原因';

  @override
  String get exclusionPanelCurrentLabel => '当前：';

  @override
  String get exclusionPanelSelectNewReason => '选择新原因：';

  @override
  String get exclusionPanelNoneRemoveExclusion => '无（移除排除）';

  @override
  String get exclusionPanelApply => '应用';

  @override
  String get exclusionPanelExpandFilterPanel => '展开筛选面板';

  @override
  String get exclusionPanelCollapseFilterPanel => '折叠筛选面板';

  @override
  String extractToolbarSegments(Object end, Object start, Object total) {
    return '片段（$start-$end，共 $total）';
  }

  @override
  String get extractToolbarCancel => '取消';

  @override
  String get extractCancelExtractionTitle => '取消提取';

  @override
  String get extractCancelExtractionContent => '确定要取消提取吗？此操作无法撤销。';

  @override
  String get extractCancelExtractionNo => '否';

  @override
  String get extractCancelExtractionYes => '是';

  @override
  String get extractExtractionCancelled => '提取已取消';

  @override
  String get extractMineruConfigRequiredTitle => '需要配置MinerU';

  @override
  String extractMineruConfigRequiredContent(Object error) {
    return '连接到MinerU API失败。请在设置页面配置MinerU设置。\n\n错误详情：\n$error';
  }

  @override
  String get extractOpenSettings => '打开设置';

  @override
  String extractErrorLabel(Object error) {
    return '错误：$error';
  }

  @override
  String get extractRetry => '重试';

  @override
  String get extractTaskTypeDetectIdentifier => '标识符检测';

  @override
  String get extractTaskTypeDetectLanguage => '语言检测';

  @override
  String get extractTaskTypeDetectExclusions => '排除项检测';

  @override
  String get translationStatsTitle => '翻译统计';

  @override
  String get translationStatsDocuments => '文档';

  @override
  String get translationStatsPages => '页面';

  @override
  String translationStatsLastUpdated(Object date) {
    return '最后更新：$date';
  }

  @override
  String get translationStatsLoadFailed => '加载统计失败';

  @override
  String get translationStatsJustNow => '刚刚';

  @override
  String get translationStatsOneMinuteAgo => '1分钟前';

  @override
  String translationStatsMinutesAgo(Object count) {
    return '$count 分钟前';
  }

  @override
  String get translationStatsOneHourAgo => '1小时前';

  @override
  String translationStatsHoursAgo(Object count) {
    return '$count 小时前';
  }

  @override
  String get translationStatsYesterday => '昨天';

  @override
  String translationStatsDaysAgo(Object count) {
    return '$count 天前';
  }

  @override
  String get aiPlatformDisplayName => '显示名称';

  @override
  String get aiPlatformParserSubtype => '解析器类型';

  @override
  String get aiPlatformParserSubtypeCloud => '云端';

  @override
  String get aiPlatformParserSubtypeLocal => '本地';

  @override
  String get translationQueueEdit => '标签编辑模式';

  @override
  String get reeditTitle => '编辑译文';

  @override
  String get reeditSaveExport => '保存并导出';

  @override
  String get reeditFetchError => '加载翻译片段失败。';

  @override
  String get reeditSaveSuccess => '修改已保存。';

  @override
  String get reeditSaveError => '保存修改失败。';

  @override
  String get workspaceCloseFlowTitle => '关闭此流程？';

  @override
  String get workspaceCloseFlowMessage => '关闭此流程将丢弃所有未保存的更改。';

  @override
  String get workspaceCloseFlowSaveToQueue => '保存并关闭';

  @override
  String get workspaceCloseFlowDestroy => '销毁并关闭';

  @override
  String get workspaceCloseFlowCancel => '取消';

  @override
  String get fetchUrlCancel => '取消';

  @override
  String get fetchUrl => '网址抓取';

  @override
  String get fetchUrlClose => '关闭';

  @override
  String get loginSubtitleFeatures => '文档翻译\n格式转换\n网址抓取';

  @override
  String get loginSubtitleTagline => 'AI 文档处理系统';

  @override
  String get loginUsernameLabel => '用户名';

  @override
  String get loginUsernameHint => '请输入用户名';

  @override
  String get loginUsernameRequiredError => '请输入您的用户名';

  @override
  String get loginUsernameMinLengthError => '用户名至少需要 3 个字符';

  @override
  String get loginPasswordLabel => '密码';

  @override
  String get loginPasswordHint => '请输入密码';

  @override
  String get loginPasswordRequiredError => '请输入您的密码';

  @override
  String get loginForgotPassword => '忘记密码？';

  @override
  String get loginPasswordRecoveryTitle => '密码恢复';

  @override
  String get loginPasswordRecoveryContactAdmin => '请联系您的管理员重置密码。';

  @override
  String get loginPasswordRecoveryAdminHint => '管理员登录后可在用户管理页面重置密码。';

  @override
  String get loginAuthMethodDefault => '使用默认认证方式';

  @override
  String get loginCopyErrorLabel => '复制';

  @override
  String get loginErrorCopiedMessage => '错误信息已复制到剪贴板';

  @override
  String get loginWelcomeBack => '欢迎回来';

  @override
  String get loginFeatureFormats => 'PDF、DOCX、XLSX、HTML、EPUB、MOBI\n及 15 种以上格式';

  @override
  String get loginFeatureLayout => '高保真排版翻译\n保留原文格式';

  @override
  String get loginFeaturePlatforms => '支持 20+ LLM 平台\n包括 OpenAI、Claude、Ollama';

  @override
  String get loginPasswordRecoveryAdminGuide => '如果您是管理员，请按照密码恢复流程进行处理。';

  @override
  String get commonDarkMode => '深色模式';

  @override
  String get commonLightMode => '浅色模式';
}
