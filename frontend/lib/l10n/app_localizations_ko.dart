// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Korean (`ko`).
class AppLocalizationsKo extends AppLocalizations {
  AppLocalizationsKo([String locale = 'ko']) : super(locale);

  @override
  String get settingsGeneralTitle => '일반 설정';

  @override
  String get settingsGeneralDarkModeTitle => '다크 모드';

  @override
  String get settingsGeneralDarkModeSubtitle => '다크 테마 사용 (즉시 적용됨)';

  @override
  String get settingsGeneralLanguageTitle => '언어';

  @override
  String get settingsGeneralNotificationsTitle => '알림';

  @override
  String get settingsGeneralNotificationsSubtitle =>
      '완료된 작업에 대한 알림 수신 (즉시 적용됨)';

  @override
  String get settingsGeneralAutoSaveTitle => '자동 저장';

  @override
  String get settingsGeneralAutoSaveSubtitle => '진행 중인 작업 자동 저장 (즉시 적용됨)';

  @override
  String get settingsGeneralShowAdsTitle => '광고 표시';

  @override
  String get settingsGeneralShowAdsSubtitle =>
      '홈 및 플로우에서 광고 자리 표시자 표시 (system.json에 저장됨)';

  @override
  String get settingsGeneralClearStatsButton => '통계 지우기';

  @override
  String get settingsGeneralClearStatsConfirmTitle => '통계를 지우시겠습니까?';

  @override
  String get settingsGeneralClearStatsConfirmMessage =>
      '홈 페이지에 표시된 문서 수와 페이지 수가 0으로 재설정됩니다. 이 작업은 되돌릴 수 없습니다.';

  @override
  String get settingsGeneralClearStatsConfirmButton => '지우기';

  @override
  String get settingsGeneralClearStatsSuccess => '통계가 지워졌습니다.';

  @override
  String get backToHome => '홈으로 돌아가기';

  @override
  String get settingsFontSectionTitle => '글꼴 설정';

  @override
  String get settingsFontPreviewSizeTitle => '미리보기 글꼴 크기';

  @override
  String get settingsFontPreviewSizeSubtitle => '미리보기에서 원본 및 대상 텍스트의 글꼴 크기';

  @override
  String get translationToolbarFilterAll => '전체';

  @override
  String get translationToolbarFilterFailed => '실패';

  @override
  String get translationToolbarFilterIncluded => '포함됨';

  @override
  String get translationToolbarFilterExcluded => '제외됨';

  @override
  String get translationToolbarSearchTooltip => '검색 (Ctrl+F / Cmd+F)';

  @override
  String get translationToolbarPrevRetryTooltip => '이전 재시도 세그먼트';

  @override
  String get translationToolbarNextRetryTooltip => '다음 재시도 세그먼트';

  @override
  String get translationToolbarPreviewTooltip => '미리보기';

  @override
  String get translationToolbarFormatSettingsTooltip => '형식 설정';

  @override
  String get translationToolbarExportTooltip => '문서 내보내기';

  @override
  String get translationToolbarPdfPreviewTooltip => 'PDF 미리보기 (디버그)';

  @override
  String get translationToolbarCancelButton => '취소';

  @override
  String get translationToolbarExitFullscreenTooltip => '전체 화면 종료';

  @override
  String get translationToolbarEnterFullscreenTooltip => '전체 화면 시작';

  @override
  String get translationToolbarDecreaseFontSize => '글꼴 크기 줄이기';

  @override
  String get translationToolbarIncreaseFontSize => '글꼴 크기 늘리기';

  @override
  String get translationToolbarMergedView => '병합 단락 보기';

  @override
  String get translationToolbarSegmentView => '세그먼트 보기';

  @override
  String get translationToolbarUpload => '업로드';

  @override
  String get translationToolbarUploading => '업로드 중...';

  @override
  String get translationToolbarFileUploaded => '파일 업로드됨';

  @override
  String get translationToolbarReextract => '재추출';

  @override
  String get translationToolbarReextracting => '재추출 중...';

  @override
  String translationToolbarTokensCount(Object count) {
    return '$count 토큰';
  }

  @override
  String get translationToolbarOpenGlossaryTab => '용어집 탭 열기';

  @override
  String get translationToolbarHintWaitExtract => '추출이 완료될 때까지 기다려 주세요';

  @override
  String get translationToolbarHintOperationInProgress => '작업이 진행 중입니다';

  @override
  String get translationToolbarGlossary => '용어집';

  @override
  String get translationToolbarConvertHint =>
      '형식 변환 후 전체 제외·번역을 실행하고 「변환」 탭에서 내보내기';

  @override
  String get translationToolbarConvert => '변환';

  @override
  String get translationToolbarHintSaveGlossaryFirst => '먼저 용어집을 저장하세요 (적용 클릭)';

  @override
  String get translationToolbarHintUpdatingExcluded => '제외된 세그먼트 업데이트 중...';

  @override
  String get translationToolbarStartTranslation => '번역 시작';

  @override
  String get translationToolbarTranslateAll => '전체 번역';

  @override
  String get translationToolbarTranslating => '번역 중...';

  @override
  String get translationToolbarRetryInProgress => '재시도 진행 중...';

  @override
  String get translationToolbarRetryTooltip =>
      '실패했거나 표시된 모든 세그먼트를 재시도합니다. 이는 번역 중 실패했거나 수동으로 재시도 표시된 세그먼트를 현재 선택된 AI 플랫폼을 사용하여 재번역합니다. 제외 및 지워진 세그먼트는 건너뜁니다.';

  @override
  String get translationToolbarRetry => '재시도';

  @override
  String get translationPersistQueueTooltip =>
      '현재 내보낸 결과를 서버에 기록해 작업 대기열 다운로드가 이 화면의 최신 편집과 일치하도록 합니다.';

  @override
  String get translationPersistQueueButton => '대기열 업데이트';

  @override
  String get translationPersistQueueAlreadySyncedTooltip =>
      '이미 대기열 스냅샷과 일치합니다. 추가 저장이 필요 없습니다.';

  @override
  String get translationPersistQueueSuccess => '작업 대기열용 최신 내보내기를 저장했습니다.';

  @override
  String translationPersistQueueFailed(Object error) {
    return '대기열에 저장하지 못했습니다: $error';
  }

  @override
  String get translationCloseTranslateTabTitle => '작업 대기열이 최종 결과와 다를 수 있음';

  @override
  String get translationCloseTranslateTabMessage =>
      '이 탭에서의 편집이 아직 작업 대기열 스냅샷에 저장되지 않았습니다. 저장 없이 닫으면 「작업 대기열」에서 받는 파일이 이 탭의 최종 버전과 다를 수 있습니다.\n\n대기열을 먼저 업데이트한 뒤 닫거나, 대기열에 저장하지 않고 이 탭을 닫을 수 있습니다.';

  @override
  String get translationCloseTranslateTabStay => '머무르기';

  @override
  String get translationCloseTranslateTabClose => '저장 없이 닫기';

  @override
  String get translationCloseTranslateTabSaveAndClose => '저장 후 닫기';

  @override
  String get translationCloseTranslateTabKeepTitle => '작업을 대기열에 유지할까요?';

  @override
  String get translationCloseTranslateTabKeepMessage =>
      '번역이 완료되었습니다. 나중에 검토 및 편집을 위해 대기열에 유지하시겠습니까?';

  @override
  String get translationCloseTranslateTabKeepInQueue => '대기열에 유지';

  @override
  String get translationCloseTranslateTabDiscard => '폐기';

  @override
  String get translationToolbarSwitchToFile => '파일로 전환';

  @override
  String get translationToolbarSwitchToText => '텍스트로 전환';

  @override
  String get translationStatusCompleted => '번역 완료';

  @override
  String get translationStatusRetry => '번역 재시도';

  @override
  String get translationStatusFailed => '번역 실패';

  @override
  String get translationStatusCancelled => '번역 취소됨';

  @override
  String get translationStatusTranslating => '번역 중';

  @override
  String get translationStatusTranslatingFallback => '번역 중...';

  @override
  String get translationStatusReady => '준비됨';

  @override
  String get translationStatusTaskPending => '작업 대기 중';

  @override
  String get translationStatusProcessing => '처리 중...';

  @override
  String translationStatsSuccessOnly(Object success, Object total) {
    return '성공: $success/$total';
  }

  @override
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total) {
    return '성공: $success/$total, 실패: $fail/$total';
  }

  @override
  String translationStatsTotal(Object count) {
    return '전체: $count | ';
  }

  @override
  String translationStatsTranslated(Object count) {
    return '번역됨: $count | ';
  }

  @override
  String translationStatsPending(Object count) {
    return '대기 중: $count';
  }

  @override
  String translationStatsExcluded(Object count) {
    return ' | 제외됨: $count';
  }

  @override
  String translationStatsRetryCount(Object count) {
    return ' | 재시도: $count';
  }

  @override
  String translationStatsCleared(Object count) {
    return ' | 지워짐: $count';
  }

  @override
  String translationStatsImages(Object count) {
    return ' | 이미지: $count';
  }

  @override
  String translationStatsSegment(Object current, Object total) {
    return '세그먼트: $current / $total';
  }

  @override
  String get translationStatsDoubleClickToEdit => '텍스트를 더블 클릭하여 편집하세요.';

  @override
  String get translationStatsTranslatedLabel => '번역됨';

  @override
  String get translationStatsLoadingContent => '콘텐츠 로딩 중...';

  @override
  String get translationStatsNoContentAvailable => '사용 가능한 콘텐츠가 없습니다.';

  @override
  String get translationStatsNoSegmentsAvailable => '사용 가능한 세그먼트가 없습니다';

  @override
  String translationStatsTokenIn(Object count) {
    return '입력: $count';
  }

  @override
  String translationStatsTokenOut(Object count) {
    return '출력: $count';
  }

  @override
  String translationStatsTokenTotal(Object count) {
    return '($count)';
  }

  @override
  String get translationLangArabic => '아랍어';

  @override
  String get translationLangBengali => '벵골어';

  @override
  String get translationLangCatalan => '카탈루냐어';

  @override
  String get translationLangChinese => '중국어';

  @override
  String get translationLangChineseTraditional => '중국어(번체)';

  @override
  String get translationLangCzech => '체코어';

  @override
  String get translationLangCroatian => '크로아티아어';

  @override
  String get translationLangDanish => '덴마크어';

  @override
  String get translationLangDutch => '네덜란드어';

  @override
  String get translationLangEnglish => '영어';

  @override
  String get translationLangFilipino => '필리핀어';

  @override
  String get translationLangFinnish => '핀란드어';

  @override
  String get translationLangFrench => '프랑스어';

  @override
  String get translationLangGerman => '독일어';

  @override
  String get translationLangGreek => '그리스어';

  @override
  String get translationLangHebrew => '히브리어';

  @override
  String get translationLangHindi => '힌디어';

  @override
  String get translationLangItalian => '이탈리아어';

  @override
  String get translationLangJapanese => '일본어';

  @override
  String get translationLangKorean => '한국어';

  @override
  String get translationLangKhmer => '크메르어';

  @override
  String get translationLangLithuanian => '리투아니아어';

  @override
  String get translationLangMacedonian => '마케도니아어';

  @override
  String get translationLangMalay => '말레이어';

  @override
  String get translationLangNorwegian => '노르웨이어 보크몰';

  @override
  String get translationLangPolish => '폴란드어';

  @override
  String get translationLangPortuguese => '포르투갈어';

  @override
  String get translationLangRomanian => '루마니아어';

  @override
  String get translationLangRussian => '러시아어';

  @override
  String get translationLangSlovenian => '슬로베니아어';

  @override
  String get translationLangSpanish => '스페인어';

  @override
  String get translationLangSwedish => '스웨덴어';

  @override
  String get translationLangThai => '태국어';

  @override
  String get translationLangTurkish => '터키어';

  @override
  String get translationLangUkrainian => '우크라이나어';

  @override
  String get translationLangUrdu => '우르두어';

  @override
  String get translationLangVietnamese => '베트남어';

  @override
  String get translationExportNoFormats => '사용 가능한 내보내기 형식이 없습니다';

  @override
  String get translationExportDialogTitle => '문서 내보내기';

  @override
  String get translationExportFormatOptionsTitle => '형식 옵션 (PDF만)';

  @override
  String get translationExportTableFormatLabel => '표 형식:';

  @override
  String get translationExportTableFormatImage => '이미지';

  @override
  String get translationExportTableFormatHtml => 'HTML';

  @override
  String get translationExportEquationFormatLabel => '수식 형식:';

  @override
  String get translationExportEquationFormatImage => '이미지';

  @override
  String get translationExportEquationFormatLatex => 'LaTeX';

  @override
  String get translationLeftPanelExpandTooltip => '왼쪽 패널 확장';

  @override
  String get translationLeftPanelCollapseTooltip => '왼쪽 패널 축소';

  @override
  String get translationSnackGlossarySaved => '용어집 저장됨';

  @override
  String get translationSnackTranslationCancelled => '번역 취소됨';

  @override
  String get translationSnackNoLlmpSelected => 'LLM 플랫폼이 선택되지 않았습니다';

  @override
  String get translationSnackTextEmpty => '텍스트 입력이 비어 있습니다.';

  @override
  String get translationSnackTextConverted => '텍스트가 파일 형식으로 변환됨';

  @override
  String get translationSnackSourceResplitCompleted => '원본 재분할 완료';

  @override
  String get translationSnackPleaseSelectFileOrText =>
      '먼저 파일을 선택하거나 텍스트를 입력하세요';

  @override
  String get translationSnackPleaseSelectFileOrTextWithDot =>
      '먼저 파일을 선택하거나 텍스트를 입력하세요.';

  @override
  String get translationSnackPleaseSelectFile => '먼저 파일을 선택하세요';

  @override
  String get translationSnackPleaseSelectDocumentFirst => '먼저 문서를 선택하세요.';

  @override
  String get translationSnackGlossaryGenerated => '용어집이 성공적으로 생성되었습니다!';

  @override
  String get translationSnackGlossaryGenerationCancelled => '용어집 생성 취소됨';

  @override
  String get translationSnackGlossaryAppliedToTask => '용어집이 번역 작업에 적용됨';

  @override
  String get translationSnackPreviousTranslationCancelled => '이전 번역 취소됨';

  @override
  String get translationSnackGlossarySavedAndApplied => '용어집 저장 및 적용됨';

  @override
  String get translationDialogMixedLangTitle => '여러 언어가 감지되었습니다';

  @override
  String translationDialogMixedLangContent(Object distribution) {
    return '문서에 여러 언어가 포함되어 있습니다:\n$distribution';
  }

  @override
  String get translationDialogMixedLangPromptTitle =>
      '번역 품질을 향상시키기 위해 다음 프롬프트 지침을 추가할 수 있습니다:';

  @override
  String get translationDialogMixedLangOption1Title => '소스 언어 텍스트만 번역';

  @override
  String translationDialogMixedLangOption1Subtitle(Object languageName) {
    return '$languageName 언어의 텍스트만 번역합니다';
  }

  @override
  String get translationDialogMixedLangOption2Title => '코드와 기술 용어는 변경하지 않음';

  @override
  String get translationDialogMixedLangOption2Subtitle =>
      '코드 블록, 기술 용어, 함수 이름 및 다른 언어의 텍스트는 변경하지 않고 유지합니다';

  @override
  String get translationDialogMixedLangCancel => '취소';

  @override
  String get translationDialogMixedLangSkip => '건너뛰기';

  @override
  String get translationDialogMixedLangApply => '적용';

  @override
  String get translationSnackExportStarted => '내보내기 작업이 시작되었습니다. 잠시 기다려 주세요.';

  @override
  String get translationSnackPromptUpdated => '프롬프트 지침 업데이트됨';

  @override
  String translationSnackFailedToCancel(Object error) {
    return '취소 실패: $error';
  }

  @override
  String translationSnackFailedConvertTextFormat(Object error) {
    return '텍스트 형식 변환 실패: $error';
  }

  @override
  String translationSnackFailedConvertText(Object error) {
    return '텍스트 변환 실패: $error';
  }

  @override
  String translationSnackFailedResplit(Object error) {
    return '재분할 실패: $error';
  }

  @override
  String get translationSnackRequestFailed => '요청 실패';

  @override
  String translationSnackFileImportFailed(Object error) {
    return '파일 가져오기 실패: $error';
  }

  @override
  String translationSnackTaskStatus(Object status) {
    return '작업 상태: $status';
  }

  @override
  String translationSnackFileDownloaded(Object filename) {
    return '파일 다운로드됨: $filename';
  }

  @override
  String translationSnackFileSaved(Object filename) {
    return '파일 저장됨: $filename';
  }

  @override
  String translationSnackFailedDownload(Object error, Object fileType) {
    return '$fileType 다운로드 실패: $error';
  }

  @override
  String translationSnackFailedOpenDownload(Object url) {
    return '다운로드 열기 실패: $url';
  }

  @override
  String get translationDialogSwitchToFileTitle => '파일 모드로 전환';

  @override
  String get translationDialogSwitchToFileBody =>
      '파일 모드로 전환하면 현재 텍스트 입력이 지워집니다. 계속하시겠습니까?';

  @override
  String get translationDialogSwitchToTextTitle => '텍스트 모드로 전환';

  @override
  String get translationDialogSwitchToTextBody =>
      '텍스트 모드로 전환하면 현재 파일 선택이 지워집니다. 계속하시겠습니까?';

  @override
  String get translationSnackAllSegmentsExcludedSkipped =>
      '모든 세그먼트가 제외되었습니다. 번역은 건너뛰며, 내보내기를 통해 형식 변환을 수행할 수 있습니다.';

  @override
  String get translationDialogCancelButton => '취소';

  @override
  String get translationDialogContinueButton => '계속';

  @override
  String get translationNoLlmAvailableTitle => '사용 가능한 LLM이 없습니다';

  @override
  String get translationNoLlmAvailableMessage =>
      '설정된 사용 가능한 LLM 플랫폼이 없습니다. 번역하려면 설정에서 LLM API Key를 구성하세요. 형식 변환만 필요하면 계속할 수 있습니다.';

  @override
  String get translationNoLlmConfigureButton => 'LLM 설정';

  @override
  String get translationNoLlmContinueFormatOnlyButton => '형식 변환만';

  @override
  String get languageMatchWarningTitle => '언어 일치 안내';

  @override
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName) {
    return '검출된 문서 언어($detectedName)가 대상 언어($targetName)와 같습니다. 대상 언어 선택이 잘못되었을 수 있습니다. 용어집 자동 검출을 계속하시겠습니까?';
  }

  @override
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName) {
    return '검출된 문서 언어($detectedName)가 대상 언어($targetName)와 같습니다. 대상 언어 선택이 잘못되었을 수 있습니다. 번역을 계속하시겠습니까?';
  }

  @override
  String get translationDialogCancelTaskTitle => '현재 작업 취소';

  @override
  String get translationDialogCancelTaskBody =>
      '현재 추출/번역 작업을 취소하고 선택된 파일을 지웁니다. 계속하시겠습니까?';

  @override
  String get translationDialogCancelTaskNo => '아니오';

  @override
  String get translationDialogCancelTaskYesCancel => '예, 취소합니다';

  @override
  String get translationQuickSettingsTitle => '번역 빠른 설정';

  @override
  String get quickSettingsTargetLanguage => '대상 언어';

  @override
  String get quickSettingsSourceLanguage => '원본 언어 (MinerU OCR)';

  @override
  String get quickSettingsLanguageSwitchDisabled =>
      '번역 중에는 언어 전환이 비활성화됩니다. 대상 언어를 변경하려면 추출 탭으로 전환하세요.';

  @override
  String get quickSettingsParsingPlatform => '파싱 플랫폼';

  @override
  String get quickSettingsTestMineru => 'MinerU 연결 테스트';

  @override
  String get quickSettingsNotConfigured => '구성되지 않음';

  @override
  String get quickSettingsApiOk => 'API 정상';

  @override
  String get quickSettingsApiUnavailable => 'API 사용 불가';

  @override
  String get quickSettingsNotTestedYet => '아직 테스트되지 않음';

  @override
  String get quickSettingsConnectionSuccessful => '연결 성공';

  @override
  String get quickSettingsMineruConnectionFailed => 'MinerU 연결 실패';

  @override
  String get quickSettingsOpenMineruSettings => 'MinerU 설정 열기';

  @override
  String get quickSettingsMineruLabel => 'MinerU (mineru)';

  @override
  String get quickSettingsLlmPlatform => 'LLM 플랫폼';

  @override
  String get quickSettingsTestLlmPlatform => '현재 LLM 플랫폼 테스트';

  @override
  String get quickSettingsTestFailed => '테스트 실패';

  @override
  String get quickSettingsOpenAiPlatformsSettings => 'AI 플랫폼 설정 열기';

  @override
  String get quickSettingsTemperature => '온도';

  @override
  String get quickSettingsTemperatureHint => '무작위성 제어: 낮음 = 더 집중적, 높음 = 더 창의적';

  @override
  String get quickSettingsQtTsOptions => 'Qt .ts 번역 옵션';

  @override
  String get quickSettingsQtTsSkipExisting => '기존 번역 건너뛰기';

  @override
  String get quickSettingsQtTsSkipExistingSubtitle => '이미 번역이 있는 메시지 건너뛰기';

  @override
  String get quickSettingsQtTsTranslateUnfinished => '미완성 항목 번역';

  @override
  String get quickSettingsQtTsTranslateUnfinishedSubtitle =>
      '미완성으로 표시된 메시지 번역 (type=\"unfinished\")';

  @override
  String get quickSettingsQtTsTranslateVanished => '사라진 항목 번역';

  @override
  String get quickSettingsQtTsTranslateVanishedSubtitle =>
      '사라진 것으로 표시된 메시지 번역 (type=\"vanished\")';

  @override
  String get quickSettingsQtTsTranslateObsolete => '구식 항목 번역';

  @override
  String get quickSettingsQtTsTranslateObsoleteSubtitle =>
      '구식으로 표시된 메시지 번역 (type=\"obsolete\")';

  @override
  String get quickSettingsPrompt => '프롬프트';

  @override
  String get quickSettingsPromptMode => '프롬프트 모드';

  @override
  String get quickSettingsPromptModeOff => '끔 (프롬프트 없음)';

  @override
  String get quickSettingsPromptModeSimple => '간단 (스타일만)';

  @override
  String get quickSettingsPromptModeAdvanced => '고급 (스타일 + 참고)';

  @override
  String get quickSettingsStyle => '스타일';

  @override
  String get quickSettingsStyleLiteral => '직역';

  @override
  String get quickSettingsStyleFluent => '유창함';

  @override
  String get quickSettingsStyleAcademic => '학술적';

  @override
  String get quickSettingsStyleBusiness => '비즈니스';

  @override
  String get quickSettingsStyleTechnical => '기술적';

  @override
  String get quickSettingsTaskNoteLabel => '작업 참고 (짧은 지침)';

  @override
  String get quickSettingsTaskNoteHint => '예: 수식 수정하지 않음; 고유 명사 주석 달기';

  @override
  String get quickSettingsAdRegionF => '영역 F: 빠른 설정 하단\n(중간 직사각형 300×250)';

  @override
  String quickSettingsPlatformMessage(Object label, Object message) {
    return '$label: $message';
  }

  @override
  String quickSettingsPlatformTestFailed(Object error, Object label) {
    return '$label: 테스트 실패 — $error';
  }

  @override
  String get homeTagline => 'AI 기반, 몰입형\n개인적, 안전함(개발 중)\n팀 공유, 사용자 정의 가능\n';

  @override
  String get homeIntro => '문서를 업로드하고 AI 기반 정확도로 여러 언어로 번역하세요.\n';

  @override
  String get homeHowItWorks =>
      '작동 방식\n번역: 가져오기 -> 문서 분석 -> 용어집 -> 번역 -> 내보내기\n파일 형식 변환: 가져오기 -> 문서 분석 -> 변환 -> 내보내기\nURL 가져오기: URL 입력 -> 페이지 가져오기 -> 콘텐츠 분석 -> 본문 추출 -> 번역/내보내기';

  @override
  String get homeSnackDonorExpired =>
      '귀하의 등록 코드가 만료되었습니다. Pro 혜택을 계속 이용하려면 다시 등록하세요.';

  @override
  String get commonCancel => '취소';

  @override
  String get commonOk => '확인';

  @override
  String get homeAuthErrorTitle => '인증 오류';

  @override
  String get homeAuthRetryLogin => '로그인 재시도';

  @override
  String homeAiPlatformsAvailable(Object platforms) {
    return '사용 가능한 AI 플랫폼: $platforms';
  }

  @override
  String get homeAiPlatformsConfigureNotice => '앱 사용 전 설정 패널에서 AI 플랫폼을 구성하세요.';

  @override
  String get homeBackendStatusStarting => '백엔드가 시작 중입니다...';

  @override
  String get homeBackendStatusConnecting => '백엔드에 연결 중...';

  @override
  String get homeBackendStatusConnected => '백엔드가 연결되었습니다';

  @override
  String get homeBackendStatusDisconnected => '백엔드 연결이 끊어졌습니다. 다시 시도하세요.';

  @override
  String get homeBackendStatusUnknown => '백엔드에 연결 중...';

  @override
  String get homeBackendRetry => '재시도';

  @override
  String get homeNavTranslate => '몰입형 번역';

  @override
  String get homeNavTranslationQueue => '작업 대기열';

  @override
  String get homeNavAnonymize => '익명화';

  @override
  String get homeNavSettings => '설정';

  @override
  String get homeNavDonateHelp => '기부 및 도움말';

  @override
  String get homeNavHome => '홈';

  @override
  String get translationQueueTitle => '작업 대기열';

  @override
  String get translationQueueHint => '작업이 자동으로 새로 고칩니다. 완료 후 다운로드할 수 있습니다.';

  @override
  String get translationQueueCancelExitHint =>
      '대기 중이거나 실행 중인 작업은 «작업 취소»로 중단할 수 있습니다. 확인 후 홈으로 돌아갑니다.';

  @override
  String get translationQueueCancelDialogTitle => '이 번역 작업을 취소할까요?';

  @override
  String get translationQueueCancelDialogMessage =>
      '대기 중인 작업은 대기열에서 제거되고, 실행 중인 작업은 중단됩니다. 확인 후 홈으로 이동합니다.';

  @override
  String get translationQueueCancelDialogKeep => '유지';

  @override
  String get translationQueueCancelDialogConfirm => '취소 확인';

  @override
  String get translationQueueEmpty => '번역 작업이 없습니다.';

  @override
  String get translationQueueNewQueuedTask => '큐 방식 번역';

  @override
  String get translationQueueBackToQueueTooltip => '작업 대기열로 돌아가기';

  @override
  String get translationQueuedStarted => '대기열에 추가되었습니다. 여기서 진행 상황을 확인하세요.';

  @override
  String get translationQueueRefresh => '새로 고침';

  @override
  String get translationQueueCancel => '작업 취소';

  @override
  String get translationQueueRelease => '목록에서 제거';

  @override
  String get translationQueueDownloads => '다운로드';

  @override
  String get translationQueueDownloadMdEmbedded => 'MD(임베드)';

  @override
  String get translationQueueDownloadMdZip => 'MD(ZIP)';

  @override
  String get translationQueueExecutionModeQueued => '대기열';

  @override
  String get translationQueueExecutionModeImmediate => '즉시';

  @override
  String get translationQueueTaskTypeTranslation => '번역';

  @override
  String get translationQueueTaskTypeConversion => '변환';

  @override
  String translationQueuePositionLabel(Object position) {
    return '대기 순번 #$position';
  }

  @override
  String translationQueueLoadFailed(Object error) {
    return '작업을 불러오지 못했습니다: $error';
  }

  @override
  String translationQueueActionFailed(Object error) {
    return '작업 실패: $error';
  }

  @override
  String translationQueueSubmittedBy(Object user) {
    return '시작 사용자: $user';
  }

  @override
  String translationQueueStartedAt(Object time) {
    return '시작: $time';
  }

  @override
  String translationQueueCompletedAt(Object time) {
    return '완료: $time';
  }

  @override
  String get translationQueueTimeUnknown => '—';

  @override
  String get translationQueueGuestUser => '게스트';

  @override
  String get translationQueueClearAllTooltip => '작업 대기열 및 서버 캐시 삭제(관리자만)';

  @override
  String get translationQueueClearAllButton => '대기열 비우기';

  @override
  String get translationQueueClearAllTitle => '작업 대기열 비우기';

  @override
  String get translationQueueClearAllMessage =>
      '대기 및 진행 중 작업을 취소하고 메모리 작업과 디스크 스냅샷을 삭제합니다. 되돌릴 수 없습니다.';

  @override
  String get translationQueueClearAllConfirm => '비우기';

  @override
  String get translationQueueClearAllCancel => '취소';

  @override
  String get translationQueueClearAllSuccess => '작업 대기열을 비웠습니다.';

  @override
  String translationQueueClearAllFailed(Object error) {
    return '비우기 실패: $error';
  }

  @override
  String get homeFeatureUnderDevelopment => '이 기능은 개발 중입니다.';

  @override
  String homeAnonymizeNotSupportedVersion(Object version) {
    return '아직 지원되지 않습니다. v$version에서 사용 가능할 예정입니다.';
  }

  @override
  String get homeAnonymizeInDevelopment => '익명화는 개발 중이며 아직 사용할 수 없습니다.';

  @override
  String get homeScrollLeft => '왼쪽으로 스크롤';

  @override
  String get homeScrollRight => '오른쪽으로 스크롤';

  @override
  String get homeTabHome => '홈';

  @override
  String get homeToolbarAdBanner => '도구 모음 광고 배너\n(728×90 리더보드 / 320×50 모바일)';

  @override
  String get homeSteps => '단계';

  @override
  String get homePhaseUpload => '업로드';

  @override
  String get homePhaseExtract => '추출';

  @override
  String get homePhaseGlossary => '용어집';

  @override
  String get homePhaseTranslate => '번역';

  @override
  String get homePhaseViewer => '뷰어';

  @override
  String get homePhaseAnonymize => '익명화';

  @override
  String get homePhaseDeAnonymize => '익명화 해제';

  @override
  String get homePhaseExport => '내보내기';

  @override
  String get homeReleaseNotesTitle => '릴리스 노트';

  @override
  String get homeReleaseNotesViewOnGitHub => 'GitHub에서 보기';

  @override
  String get homeEditionEnterprise => '엔터프라이즈';

  @override
  String get homeEditionEnterpriseStatusActivated => '활성화됨';

  @override
  String get homeEditionActivateEnterprise => '엔터프라이즈 활성화';

  @override
  String get homeEditionPro => '프로';

  @override
  String get homeEditionStandard => '스탠다드';

  @override
  String get homeEditionStandardStatus => '항상 사용 가능';

  @override
  String homeEditionProStatusTrialRemaining(Object days) {
    return '$days일 남음';
  }

  @override
  String get homeEditionProStatusNotActivated => '미활성화';

  @override
  String get homeEditionProStatusActivated => '활성화됨';

  @override
  String get homeWelcomeDearPro =>
      '몰입 번역: 화면에서 원문과 번역문을 바로 대조합니다.\n큐 번역: 문서를 작업 큐에 넣어 순서대로 파이프라인을 실행합니다.';

  @override
  String get homeWelcomeDearStandard =>
      '몰입 번역: 화면에서 원문과 번역문을 바로 대조합니다.\n큐 번역: 문서를 작업 큐에 넣어 순서대로 파이프라인을 실행합니다.';

  @override
  String get homeWelcomeDearProNoUser =>
      '몰입 번역: 화면에서 원문과 번역문을 바로 대조합니다.\n큐 번역: 문서를 작업 큐에 넣어 순서대로 파이프라인을 실행합니다.';

  @override
  String get homeWelcomeDearStandardNoUser =>
      '몰입 번역: 화면에서 원문과 번역문을 바로 대조합니다.\n큐 번역: 문서를 작업 큐에 넣어 순서대로 파이프라인을 실행합니다.';

  @override
  String get homeWelcomeHello =>
      '몰입 번역: 화면에서 원문과 번역문을 바로 대조합니다.\n큐 번역: 문서를 작업 큐에 넣어 순서대로 파이프라인을 실행합니다.';

  @override
  String get homeLoading => '로딩 중...';

  @override
  String get homeWelcomeGuest => '환영합니다!';

  @override
  String homeFileNotFound(Object fileName) {
    return '파일을 찾을 수 없음: $fileName. 파일이 이동되었거나 삭제되었을 수 있습니다.';
  }

  @override
  String homeFileSelectedMismatch(Object expected, Object selected) {
    return '선택된 파일 이름이 일치하지 않음: $selected. 예상: $expected';
  }

  @override
  String homeFileLoaded(Object fileName) {
    return '파일 로드됨: $fileName';
  }

  @override
  String get homeFileSelectionCancelled => '파일 선택 취소됨.';

  @override
  String homeFileLoadFailed(Object error) {
    return '파일 로드 실패: $error';
  }

  @override
  String homeFlowCreateFailed(Object error) {
    return '플로우 생성 실패: $error';
  }

  @override
  String commonPageNotFound(Object uri) {
    return '페이지를 찾을 수 없음: $uri';
  }

  @override
  String get commonGoHome => '홈으로 이동';

  @override
  String get commonLogin => '로그인';

  @override
  String get commonLogout => '로그아웃';

  @override
  String get userMenuChangePassword => '비밀번호 변경';

  @override
  String get changePasswordCurrentPasswordLabel => '현재 비밀번호';

  @override
  String get changePasswordNewPasswordLabel => '새 비밀번호';

  @override
  String get changePasswordConfirmPasswordLabel => '새 비밀번호 확인';

  @override
  String get changePasswordRequiredError => '현재 비밀번호와 새 비밀번호는 필수입니다.';

  @override
  String get changePasswordConfirmMismatchError => '새 비밀번호가 서로 일치하지 않습니다.';

  @override
  String get changePasswordSuccessMessage => '비밀번호가 성공적으로 변경되었습니다.';

  @override
  String get changePasswordRequirementsTitle => '비밀번호 요구사항';

  @override
  String get changePasswordRequirementLength => '8~128자';

  @override
  String get changePasswordRequirementUppercase => '대문자 1자 이상';

  @override
  String get changePasswordRequirementLowercase => '소문자 1자 이상';

  @override
  String get changePasswordRequirementDigit => '숫자 1자 이상';

  @override
  String get settingsTabsGeneral => '일반';

  @override
  String get settingsTabsAiPlatforms => 'AI 플랫폼';

  @override
  String get settingsTabsParsingEngine => '파싱 엔진';

  @override
  String get settingsParsingEngineTitle => '파싱 엔진';

  @override
  String get settingsParsingEngineSubtitle =>
      '텍스트 추출 및 처리를 위한 문서 파싱 엔진을 선택하세요.';

  @override
  String get settingsParsingEngineLabel => '파싱 엔진';

  @override
  String get settingsParsingEngineMineru => 'MinerU (클리우드)';

  @override
  String get settingsParsingEngineMineruDesc => 'OCR 지원 고급 문서 파싱';

  @override
  String get settingsParsingEngineMineruLocal => 'MinerU (로컬)';

  @override
  String get settingsParsingEngineMineruLocalDesc => '자체 호스팅 MinerU, API 키 선택';

  @override
  String get settingsParsingEnginePdfplumber => 'PDFPlumber';

  @override
  String get settingsParsingEnginePdfplumberDesc => '빠른 PDF 텍스트 추출';

  @override
  String get settingsParsingEngineTesseract => 'Tesseract OCR';

  @override
  String get settingsParsingEngineTesseractDesc => 'OCR 기반 텍스트 추출';

  @override
  String get settingsFormulaOcr => '수식 OCR';

  @override
  String get settingsFormulaOcrSubtitle => '수학적 수식에 대한 OCR 활성화';

  @override
  String get settingsTableOcr => '표 OCR';

  @override
  String get settingsTableOcrSubtitle => '표에 대한 OCR 활성화';

  @override
  String get settingsAnonymizationNewTaskNotice => '변경 사항은 새 작업에만 적용됩니다';

  @override
  String get settingsParsingEngineNewTaskNotice => '변경 사항은 새 작업에만 적용됩니다';

  @override
  String get settingsPdfSplitMaxPages => 'PDF 분할 최대 페이지';

  @override
  String get settingsPdfSplitMaxWorkers => 'PDF 분할 병렬 수';

  @override
  String get settingsRequestRetryCount => '요청 재시도 횟수';

  @override
  String get settingsOcrLanguageTitle => 'OCR 언어';

  @override
  String get settingsOcrLanguageSubtitle =>
      '이미지 및 스캔 문서에서 텍스트 인식을 위한 OCR 언어를 구성합니다.';

  @override
  String get settingsOcrLanguageLabel => 'OCR 언어';

  @override
  String get settingsOcrLangEnglish => '영어';

  @override
  String get settingsOcrLangChineseSimplified => '중국어(간체)';

  @override
  String get settingsOcrLangChineseTraditional => '중국어(번체)';

  @override
  String get settingsOcrLangJapanese => '일본어';

  @override
  String get settingsOcrLangKorean => '한국어';

  @override
  String get settingsOcrLangFrench => '프랑스어';

  @override
  String get settingsOcrLangGerman => '독일어';

  @override
  String get settingsOcrLangSpanish => '스페인어';

  @override
  String get settingsOcrLangRussian => '러시아어';

  @override
  String get settingsOcrLangArabic => '아랍어';

  @override
  String get settingsTabsGlossary => '용어집';

  @override
  String get settingsGlossaryManagementTitle => '용어집 관리';

  @override
  String get settingsGlossaryManagementSubtitle =>
      '일관된 번역 품질을 위한 용어 항목을 관리합니다.';

  @override
  String get settingsGlossarySelectGlossary => '용어집 선택';

  @override
  String get settingsGlossaryCreateGlossary => '생성';

  @override
  String get settingsGlossaryImportCsv => 'CSV 가져오기';

  @override
  String get settingsGlossaryExport => '내보내기';

  @override
  String get settingsGlossaryExportAll => '모두 내보내기';

  @override
  String get settingsGlossaryDeleteGlossary => '삭제';

  @override
  String get settingsGlossarySaveZip => 'ZIP 저장';

  @override
  String settingsGlossaryEntriesTitle(Object count) {
    return '용어집 항목 ($count)';
  }

  @override
  String get settingsGlossaryAddEntry => '항목 추가';

  @override
  String get settingsGlossaryNoEntriesYet =>
      '아직 용어집 항목이 없습니다.\n첫 번째 항목을 추가하여 시작하세요.';

  @override
  String get settingsGlossaryFilterLabel => '필터:';

  @override
  String get settingsGlossaryFilterAll => '전체';

  @override
  String get settingsGlossaryFilterUncategorized => '미분류';

  @override
  String get settingsGlossaryTableSource => '원문';

  @override
  String get settingsGlossaryTableTarget => '번역문';

  @override
  String get settingsGlossaryTableCategory => '범주 (선택사항)';

  @override
  String get settingsGlossaryTableTargetLang => '대상 언어';

  @override
  String get settingsGlossaryCategoryHint => '범주';

  @override
  String get settingsGlossaryUncategorizedDisplay => '(미분류)';

  @override
  String get settingsGlossaryCopyAction => '복사';

  @override
  String get settingsGlossaryCopiedToClipboard => '클립보드에 복사됨';

  @override
  String get settingsGlossaryDeleteDialogTitle => '용어집 삭제';

  @override
  String settingsGlossaryDeleteDialogMessage(Object id) {
    return '이 용어집을 삭제하시겠습니까?\nID: $id';
  }

  @override
  String get settingsGlossaryCancel => '취소';

  @override
  String get settingsGlossaryDelete => '삭제';

  @override
  String get settingsGlossaryCreateDialogTitle => '용어집 생성';

  @override
  String get settingsGlossaryNameLabel => '이름';

  @override
  String get settingsGlossaryDescriptionLabel => '설명 (선택사항)';

  @override
  String get settingsGlossaryGlobalGlossary => '전역 용어집';

  @override
  String get settingsGlossaryGlobalGlossarySubtitle => '끄면 개인 용어집이 됩니다';

  @override
  String get settingsGlossaryCreate => '생성';

  @override
  String get settingsGlossaryNameRequired => '이름은 필수입니다';

  @override
  String settingsGlossaryCreatedSnack(Object name) {
    return '생성됨: $name';
  }

  @override
  String settingsGlossaryCreateFailedSnack(Object error) {
    return '생성 실패: $error';
  }

  @override
  String get settingsGlossaryAddEntryDialogTitle => '용어집에 항목 추가';

  @override
  String get settingsGlossarySourceTextLabel => '원문 텍스트';

  @override
  String get settingsGlossaryTargetTextLabel => '번역 텍스트';

  @override
  String get settingsGlossaryCategoryOptionalLabel => '범주 (선택사항)';

  @override
  String get settingsGlossaryCategoryOptionalHint => '미분류로 남기려면 비워두세요';

  @override
  String get settingsGlossaryAdd => '추가';

  @override
  String get settingsGlossarySourceTargetRequired => '원문 텍스트와 번역 텍스트는 필수입니다';

  @override
  String get settingsGlossaryEntryAddedSnack => '항목 추가됨';

  @override
  String settingsGlossaryAddFailedSnack(Object error) {
    return '실패: $error';
  }

  @override
  String get settingsGlossaryImportDialogTitle => 'CSV를 용어집으로 가져오기';

  @override
  String get settingsGlossaryMergeModeLabel => '병합 모드';

  @override
  String get settingsGlossaryMergeUpdate => '업데이트 (Upsert)';

  @override
  String get settingsGlossaryMergeAppend => '추가 (신규만)';

  @override
  String get settingsGlossaryMergeReplace => '교체 (모두 덮어쓰기)';

  @override
  String get settingsGlossaryImport => '가져오기';

  @override
  String get settingsGlossaryUnableToReadFile => '파일을 읽을 수 없습니다';

  @override
  String settingsGlossaryImportedSnack(Object count) {
    return '가져옴: $count개 항목';
  }

  @override
  String settingsGlossaryImportFailedSnack(Object error) {
    return '실패: $error';
  }

  @override
  String get settingsGlossaryExportDialogTitle => '용어집 CSV 다운로드';

  @override
  String get settingsGlossarySaveCsv => 'CSV 저장';

  @override
  String get settingsGlossaryDownload => '다운로드';

  @override
  String settingsGlossaryDownloadedSnack(Object info) {
    return '다운로드됨: $info';
  }

  @override
  String settingsGlossaryExportFailedSnack(Object error) {
    return '실패: $error';
  }

  @override
  String settingsGlossaryLoadedSnack(Object count) {
    return '$count개 항목 로드됨';
  }

  @override
  String settingsGlossaryLoadFailedSnack(Object error) {
    return '로드 실패: $error';
  }

  @override
  String settingsGlossaryDeletedSnack(Object id) {
    return '용어집 삭제됨: $id';
  }

  @override
  String settingsGlossaryDeleteFailedSnack(Object error) {
    return '삭제 실패: $error';
  }

  @override
  String settingsGlossaryExportAllFailedSnack(Object error) {
    return '모두 내보내기 실패: $error';
  }

  @override
  String get settingsGlossaryEntryUpdatedSnack => '항목 업데이트됨';

  @override
  String settingsGlossaryUpdateFailedSnack(Object error) {
    return '업데이트 실패: $error';
  }

  @override
  String get settingsGlossaryEntryDeletedSnack => '항목 삭제됨';

  @override
  String settingsGlossaryDeleteEntryFailedSnack(Object error) {
    return '삭제 실패: $error';
  }

  @override
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type) {
    return '$name ($type) · $count개 항목';
  }

  @override
  String settingsGlossaryErrorPrefix(Object error) {
    return '오류: $error';
  }

  @override
  String settingsGlossaryExportedAllSnack(Object info) {
    return '내보냄: $info';
  }

  @override
  String settingsGlossaryEntryCount(Object count) {
    return '항목 수: $count';
  }

  @override
  String get settingsGlossaryEdit => '편집';

  @override
  String get settingsGlossaryConfirmDeleteEntryTitle => '삭제 확인';

  @override
  String settingsGlossaryConfirmDeleteEntryMessage(Object source) {
    return '항목 \"$source\"을(를) 삭제하시겠습니까?';
  }

  @override
  String get settingsGlossaryEditEntryDialogTitle => '항목 편집';

  @override
  String get settingsGlossaryUpdate => '업데이트';

  @override
  String get settingsGlossaryEntryDeleteFailedSnack => '항목 삭제 실패';

  @override
  String get glossaryPanelSaveNameHint => '이름을 입력하거나 기존 용어집 선택...';

  @override
  String get glossaryPanelClearSelection => '선택 지우기';

  @override
  String get glossaryPanelListTitle => '용어집';

  @override
  String get glossaryPanelNoEntries => '항목 없음';

  @override
  String get glossaryPanelOneEntry => '1개';

  @override
  String glossaryPanelEntriesCount(Object count) {
    return '$count개';
  }

  @override
  String get glossaryPanelProcessing => '처리 중...';

  @override
  String get glossaryPanelDropCsvHere => 'CSV 파일을 여기에 놓으세요';

  @override
  String get glossaryPanelNoEntriesHint =>
      '용어집 항목이 없습니다.\n「용어집 감지」 버튼을 클릭하여 시작하거나, 목록에서 용어집을 선택하여 항목을 보거나, CSV 파일을 여기에 끌어다 놓으세요.';

  @override
  String get glossaryWidgetTitle => '용어집';

  @override
  String get glossaryWidgetRefreshTooltip => '용어집 목록 새로 고침';

  @override
  String glossaryWidgetGlossariesSelected(Object count) {
    return '용어집 $count개 선택됨';
  }

  @override
  String glossaryWidgetGlossariesSelectedPlural(Object count) {
    return '용어집 $count개 선택됨';
  }

  @override
  String get glossaryWidgetSelectGlossaries => '용어집 선택';

  @override
  String glossaryWidgetLoadFailed(Object error) {
    return '용어집 로드 실패: $error';
  }

  @override
  String get glossaryWidgetNoGlossariesHint =>
      '사용 가능한 용어집이 없습니다. 설정 -> 용어집에서 만드세요.';

  @override
  String glossaryWidgetTypeCountItems(Object type, Object count) {
    return '$type · $count개';
  }

  @override
  String glossaryWidgetTermsExtracted(Object count) {
    return '번역에서 $count개 용어 추출';
  }

  @override
  String glossaryWidgetPersonalCreated(Object count) {
    return '개인 용어집이 생성되었습니다!\n$count개 용어를 추가했습니다.';
  }

  @override
  String glossaryWidgetPersonalReplaced(Object total) {
    return '개인 용어집이 교체되었습니다!\n총 $total개 용어.';
  }

  @override
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total) {
    return '개인 용어집에 $newCount개 새 용어를 추가했습니다.\n$skipped개 기존 용어 건너뜀.\n총 $total개 용어.';
  }

  @override
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total) {
    return '개인 용어집이 업데이트되었습니다!\n$newCount개 추가, $updatedCount개 업데이트.\n총 $total개 용어.';
  }

  @override
  String glossaryWidgetAddToPersonalFailed(Object error) {
    return '개인 용어집에 추가 실패: $error';
  }

  @override
  String get settingsTabsTranslation => '번역';

  @override
  String get settingsTabsAnonymization => '익명화';

  @override
  String get settingsTabsUserManagement => '사용자 관리';

  @override
  String get settingsUserManagementTitle => '사용자 관리 모드';

  @override
  String get settingsUserManagementSubtitle =>
      'Web 배포 시 로그인 및 권한 정책을 선택합니다. 설정과 설정 마법사는 관리자 전용입니다.';

  @override
  String get settingsUserManagementModeNoLogin => '로그인 불필요';

  @override
  String get settingsUserManagementModeNoLoginDesc =>
      '로그인 없이 사용. 설정 및 설정 마법사는 관리자 로그인 후에만 사용 가능.';

  @override
  String get settingsUserManagementModeLdap => 'LDAP 로그인';

  @override
  String get settingsUserManagementModeLdapDesc =>
      'LDAP/AD로 로그인. 설정 및 설정 마법사는 관리자(도메인 그룹) 전용.';

  @override
  String get settingsUserManagementModeLocal => '로컬 사용자 로그인';

  @override
  String get settingsUserManagementModeLocalDesc => '서버 로컬 사용자 목록으로 인증.';

  @override
  String get settingsUserManagementInDevelopment => '개발 중';

  @override
  String get settingsUserManagementSaveSuccess => '사용자 관리 모드가 저장되었습니다';

  @override
  String settingsUserManagementSaveFailed(Object message) {
    return '저장 실패: $message';
  }

  @override
  String get settingsLdapEnabled => 'LDAP 로그인 사용';

  @override
  String get settingsLdapEnableHint => '사용 전에「LDAP 연결 테스트」를 먼저 실행하세요.';

  @override
  String get settingsLdapProtocol => '프로토콜';

  @override
  String get settingsLdapProtocolLdap => 'LDAP';

  @override
  String get settingsLdapProtocolLdaps => 'LDAPS';

  @override
  String get settingsLdapHost => 'LDAP 서버(인증서 CN/SAN 일치)';

  @override
  String get settingsLdapHostPlaceholder => 'ad.example.com 또는 192.168.x.x';

  @override
  String get settingsLdapPort => '포트';

  @override
  String get settingsLdapPortPlaceholder => '389';

  @override
  String get settingsLdapBaseDn => '사용자 검색 Base DN';

  @override
  String get settingsLdapBaseDnPlaceholder => 'OU=Users,DC=example,DC=com';

  @override
  String get settingsLdapBindDnTemplate => '바인드 DN 템플릿';

  @override
  String settingsLdapBindDnPlaceholder(Object username) {
    return 'EXAMPLE\\$username 또는 $username@example.com';
  }

  @override
  String get settingsLdapUserFilter => '사용자 필터';

  @override
  String settingsLdapUserFilterPlaceholder(Object username) {
    return '(sAMAccountName=$username)';
  }

  @override
  String get settingsLdapAdminGroupEnabled => '관리자 그룹 조회 사용';

  @override
  String get settingsLdapAdminGroup => '관리자 그룹 이름';

  @override
  String get settingsLdapAdminGroupPlaceholder => 'Owlangs-Admins';

  @override
  String get settingsLdapGroupBaseDn => '그룹 검색 Base DN';

  @override
  String get settingsLdapGroupBaseDnPlaceholder =>
      'OU=Groups,DC=example,DC=com';

  @override
  String get settingsLdapTlsVerify => 'TLS 인증서 검증';

  @override
  String get settingsLdapTlsCacertfile => 'TLS CA 인증서 파일 경로';

  @override
  String get settingsLdapTlsCacertfilePlaceholder => '/path/to/ca.crt';

  @override
  String get settingsLdapTestConnection => 'LDAP 연결 테스트';

  @override
  String get settingsLdapSaveConfig => 'LDAP 설정 저장';

  @override
  String get settingsLdapTestDialogTitle => 'LDAP 연결 테스트';

  @override
  String get settingsLdapTestUsername => '사용자명(도메인 제외)';

  @override
  String get settingsLdapTestUsernamePlaceholder => 'testuser';

  @override
  String get settingsLdapTestPassword => '비밀번호';

  @override
  String get settingsLdapTestPasswordPlaceholder => '********';

  @override
  String get settingsLdapTestStart => '테스트 시작';

  @override
  String get settingsLdapTestSuccess => 'LDAP 연결 테스트 성공. LDAP을 사용할 수 있습니다.';

  @override
  String get settingsLdapTestFailed => 'LDAP 연결 테스트 실패';

  @override
  String get settingsLdapConfigSaved => 'LDAP 설정이 저장되었습니다';

  @override
  String get settingsLdapEnableRequireTest =>
      'LDAP 사용 전에 LDAP 연결 테스트를 먼저 실행하세요.';

  @override
  String get settingsAdminOnlyDialogTitle => '관리자 전용';

  @override
  String get settingsAdminOnlyDialogMessage =>
      '설정 및 설정 마법사는 관리자만 사용할 수 있습니다. 관리자 계정으로 로그인하세요.';

  @override
  String get settingsAdminOnlyDialogGoToLogin => '로그인';

  @override
  String get settingsAdminOnlyDialogClose => '닫기';

  @override
  String get aiPlatformOverview => '플랫폼 개요';

  @override
  String aiPlatformConfiguredCount(Object configured, Object total) {
    return '$configured/$total개 플랫폼 구성됨';
  }

  @override
  String get aiPlatformTestApiStatus => 'API 상태 테스트';

  @override
  String get aiPlatformTesting => '테스트 중...';

  @override
  String get aiPlatformCategoryLanguageModels => '언어 모델';

  @override
  String get aiPlatformCategoryParsingEngines => '파싱 엔진';

  @override
  String aiPlatformConfiguredDragReorder(Object configured, Object total) {
    return '$configured/$total개 플랫폼 구성됨 (드래그하여 재정렬)';
  }

  @override
  String get aiPlatformNotConfigured => '구성되지 않음';

  @override
  String get aiPlatformNotTested => '테스트되지 않음';

  @override
  String get aiPlatformApiAvailable => 'API 사용 가능';

  @override
  String get aiPlatformAvailable => '사용 가능';

  @override
  String get aiPlatformUnavailable => '사용 불가';

  @override
  String get aiPlatformConfigure => '구성';

  @override
  String aiPlatformConfigureTitle(Object name) {
    return '$name 구성';
  }

  @override
  String get aiPlatformBasicInformation => '기본 정보';

  @override
  String get aiPlatformPlatformName => '플랫폼 이름';

  @override
  String get aiPlatformPlatformNameHint => '예: Doubao (DeepSeek / Volcano Ark)';

  @override
  String get aiPlatformApiUrl => 'API URL';

  @override
  String get aiPlatformApiUrlHint =>
      'e.g., https://ark.cn-beijing.volces.com/api/v3';

  @override
  String get aiPlatformMaxTokens => '최대 토큰';

  @override
  String get aiPlatformMaxTokensHint => '예: 4096';

  @override
  String get aiPlatformChunkSize => '청크 크기';

  @override
  String get aiPlatformChunkSizeHint => '예: 3000';

  @override
  String get aiPlatformConcurrent => '동시 요청 수';

  @override
  String get aiPlatformConcurrentHint => '예: 5';

  @override
  String get aiPlatformModel => '모델';

  @override
  String get aiPlatformModelHint => '예: deepseek-v3 / llama3.1-70b';

  @override
  String get aiPlatformApiKey => 'API 키';

  @override
  String get aiPlatformApiConfiguration => 'API 구성';

  @override
  String get aiPlatformGetApiKey => 'API 키 가져오기';

  @override
  String get aiPlatformCancel => '취소';

  @override
  String get aiPlatformTestConnection => '연결 테스트';

  @override
  String get aiPlatformTestConnectionHint =>
      '설정을 저장한 후 아래의 \"연결 테스트\" 버튼을 눌러 플랫폼 구성이 정상인지 확인하세요.';

  @override
  String get setupWizardConfigureApiKeyAndTest =>
      '연결 불가. API Key를 설정하고 \"연결 테스트\"를 클릭하여 확인하세요.';

  @override
  String get setupWizardSaveAndExit => '저장 후 종료';

  @override
  String get setupWizardTitle => '설정 마법사';

  @override
  String get setupWizardStepWelcome => '환영';

  @override
  String get setupWizardStepMineru => 'PDF / MinerU';

  @override
  String get setupWizardWelcomeIntro => '이 마법사는 두 가지 주요 설정을 도와줍니다.';

  @override
  String get setupWizardWelcomeBody =>
      '1. 기본 LLM 플랫폼을 선택하고 설정합니다.\n2. PDF/PNG 등을 번역하려면 MinerU 파싱 엔진을 설정합니다(선택).\n\n참고: 설정 후 \"연결 테스트\"로 확인하세요.';

  @override
  String get setupWizardUiLanguageLabel => 'UI 언어';

  @override
  String get setupWizardMineruQuestion => 'PDF/이미지 등 문서를 이 기기에서 번역하시겠습니까?';

  @override
  String get setupWizardMineruYes => '예(권장, MinerU 문서 파싱 사용)';

  @override
  String get setupWizardMineruNo => '아니오(LLM만으로 텍스트 번역 등)';

  @override
  String get setupWizardMineruDescription =>
      'MinerU는 PDF/이미지의 레이아웃 파싱과 분할을 담당합니다.\n아래에 API Key와 URL을 입력한 뒤 \"연결 테스트\"로 확인하세요.';

  @override
  String get setupWizardMineruSkipped =>
      'MinerU를 설정하지 않았습니다. 설정에서 나중에 PDF 번역을 켤 수 있습니다.';

  @override
  String get setupWizardMineruConfigTitle => 'MinerU(파싱 엔진)';

  @override
  String get setupWizardSelectMineruPlatform => 'MinerU 플랫폼 선택';

  @override
  String get setupWizardMineruCloudOption => 'MinerU (클리우드) - 공식 클라우드 서비스';

  @override
  String get setupWizardMineruLocalOption => 'MinerU (로컬) - 자체 호스팅';

  @override
  String get setupWizardSelectLlmPlatform => 'LLM 플랫폼 선택';

  @override
  String get setupWizardNoLlmPlatforms =>
      'AI 플랫폼 설정에 LLM이 없습니다. 설정에서 플랫폼을 추가하세요.';

  @override
  String get setupWizardMineruSaved => 'MinerU 설정이 저장되었습니다';

  @override
  String get setupWizardPrevStep => '이전';

  @override
  String get setupWizardNextStep => '다음';

  @override
  String get aiPlatformSave => '저장';

  @override
  String get aiPlatformList => '목록';

  @override
  String get aiPlatformTemperature => '온도';

  @override
  String get aiPlatformThinkingMode => '사고 모드';

  @override
  String get aiPlatformThinkingDisable => '비활성화 (권장)';

  @override
  String get aiPlatformThinkingEnable => '활성화';

  @override
  String get aiPlatformThinkingDefault => '기본값';

  @override
  String get aiPlatformThinkingHint => '더 나은 번역 품질을 위한 AI 추론 과정 활성화';

  @override
  String get aiPlatformPleaseEnterApiKeyFirst => '먼저 API 키를 입력하세요';

  @override
  String get aiPlatformPleaseEnterApiUrlFirst => '먼저 API URL을 입력하세요';

  @override
  String get aiPlatformHasApiKey => 'API 키 필요함';

  @override
  String get aiPlatformHasApiKeyHint => '인증이 필요 없는 로컬 환경에서는 해제하세요';

  @override
  String get aiPlatformApiKeyOptionalHint => '필요 없으면 비워두세요';

  @override
  String get optional => '선택';

  @override
  String get aiPlatformConnectionTestSucceeded => '연결 테스트 성공';

  @override
  String aiPlatformConnectionTestFailed(Object message) {
    return '연결 테스트 실패: $message';
  }

  @override
  String get aiPlatformNoModelsFound => '모델을 찾을 수 없습니다';

  @override
  String get aiPlatformFailedToLoadModels => '모델 로드 실패';

  @override
  String aiPlatformErrorLoadingModels(Object error) {
    return '모델 로드 오류: $error';
  }

  @override
  String get aiPlatformSelectModel => '모델 선택';

  @override
  String get aiPlatformNoModelsAvailable => '사용 가능한 모델이 없습니다';

  @override
  String get aiPlatformMineruSettings => 'MinerU 설정';

  @override
  String get aiPlatformEnterMineruApiKey => 'MinerU API 키 입력';

  @override
  String get aiPlatformGetMineruApiKey => 'MinerU API 키 가져오기';

  @override
  String get aiPlatformModelVersion => '모델 버전';

  @override
  String get aiPlatformModelVersionHint => 'vlm';

  @override
  String get aiPlatformMineruApiUrlHint => 'https://mineru.net/api/v4';

  @override
  String get aiPlatformOcrSettings => 'OCR 설정';

  @override
  String get aiPlatformFormulaOcr => '수식 OCR';

  @override
  String get aiPlatformFormulaOcrSubtitle => '수학적 수식에 대한 OCR 활성화';

  @override
  String get aiPlatformTableOcr => '표 OCR';

  @override
  String get aiPlatformTableOcrSubtitle => '표에 대한 OCR 활성화';

  @override
  String get settingsFontEditSizeTitle => '글꼴 크기 편집';

  @override
  String get settingsFontEditSizeSubtitle => '번역된 세그먼트 편집 시 글꼴 크기';

  @override
  String get settingsTranslationTitle => '번역 설정';

  @override
  String get settingsTranslationNotice => '이 설정은 새로운 번역 작업에만 적용됩니다.';

  @override
  String get settingsTranslationAutoGlossaryTitle => '용어집 자동 생성';

  @override
  String get settingsTranslationAutoGlossarySubtitle =>
      '번역 후 자동으로 용어집 생성 (새 작업에 적용)';

  @override
  String get settingsTranslationParamsTitle => '번역 매개변수';

  @override
  String get settingsTranslationConcurrentTitle => '동시 요청';

  @override
  String get settingsTranslationConcurrentHint => '권장: 3 (모델 및 할당량에 따라 1–8 조정)';

  @override
  String get settingsTranslationTimeoutTitle => '시간 초과 (초)';

  @override
  String get settingsTranslationTimeoutHint => '120 (권장: 120-300초)';

  @override
  String get settingsTranslationChunkRetryTitle => '청크/API 재시도';

  @override
  String get settingsTranslationChunkRetryHint =>
      '권장: 3–5 (청크 번역 또는 API 호출 실패 시 재시도)';

  @override
  String get settingsTranslationSegmentAutoRetryTitle =>
      '큐 모드: 실패 세그먼트 자동 재시도 라운드';

  @override
  String get settingsTranslationSegmentAutoRetryHint =>
      '권장: 3 (본 번역 후 일괄 재번역, 1–10 라운드; 큐 모드만)';

  @override
  String get settingsTranslationChunkSizeTitle => '청크 크기 (토큰)';

  @override
  String get settingsTranslationChunkSizeHint =>
      '권장: 요청당 3000 토큰 (모델 컨텍스트 크기에 따라 조정)';

  @override
  String get settingsExclusionTitle => '기본 제외 규칙';

  @override
  String get settingsExclusionNotice =>
      '켜기 = 추출 중 자동 제외; 끄기 = 감지만 (사용자가 세그먼트별 결정).';

  @override
  String get settingsExclusionImageTitle => '이미지';

  @override
  String get settingsExclusionImageSubtitle => '이미지 자리 표시자 및 순수 이미지 콘텐츠';

  @override
  String get settingsExclusionFormulaTitle => '수식';

  @override
  String get settingsExclusionFormulaSubtitle => 'LaTeX / MathML 수식';

  @override
  String get settingsExclusionReferenceTitle => '참조';

  @override
  String get settingsExclusionReferenceSubtitle => '인용 및 서지 참조';

  @override
  String get settingsExclusionIdentifierTitle => '식별자';

  @override
  String get settingsExclusionIdentifierSubtitle => 'URL, 이메일, 일련번호, 코드 스니펫';

  @override
  String get settingsExclusionStructuralTitle => '구조적';

  @override
  String get settingsExclusionStructuralSubtitle => '머리글, 바닥글, 각주, 페이지 번호';

  @override
  String get settingsExclusionTableTitle => '표';

  @override
  String get settingsExclusionTableSubtitle => '표 콘텐츠 (마크다운 / PDF 표)';

  @override
  String get settingsExclusionLanguageMatchTitle => '언어 일치';

  @override
  String get settingsExclusionLanguageMatchSubtitle => '원본 언어가 대상 언어와 일치함';

  @override
  String get settingsLanguageDialogTitle => '언어 선택';

  @override
  String get settingsUnitPt => 'pt';

  @override
  String get glossaryGeneratedTabTitle => '생성된 용어집';

  @override
  String glossaryErrorRefresh(Object error) {
    return '용어집 새로 고침 실패: $error';
  }

  @override
  String get glossaryWarningNoGenerated => '사용 가능한 생성된 용어집이 없습니다';

  @override
  String get glossaryPanelView => '보기';

  @override
  String get glossaryPanelAddToPersonal => '개인 용어집에 추가';

  @override
  String get glossaryPanelNoGlobalGlossaries => '사용 가능한 전역 용어집이 없습니다';

  @override
  String get glossaryPanelSelectTitle => '용어집 선택';

  @override
  String get glossaryPanelSelectHint => '용어집 선택...';

  @override
  String glossaryPanelSelected(Object name) {
    return '선택됨: $name';
  }

  @override
  String get glossaryPanelSelectConfirm => '선택';

  @override
  String get glossaryPanelMergeToCurrent => '현재 용어집에 병합';

  @override
  String glossaryPanelLoadedGlossary(Object name) {
    return '용어집 로드됨: $name';
  }

  @override
  String glossaryPanelLoadFailed(Object error) {
    return '용어집 로드 실패: $error';
  }

  @override
  String glossaryPanelMergedIntoCurrent(Object glossaryName) {
    return '\"$glossaryName\"을(를) 현재 용어집에 병합했습니다';
  }

  @override
  String glossaryPanelMergeFailed(Object error) {
    return '병합 실패: $error';
  }

  @override
  String get glossaryPanelEnterName => '용어집 이름을 입력하세요';

  @override
  String get glossaryPanelSaveDialogHint => '용어집 이름을 입력하거나 교체할 기존 용어집을 선택하세요:';

  @override
  String get glossaryPanelReplaceTitle => '전역 용어집 교체';

  @override
  String glossaryPanelReplaceBody(Object glossaryName) {
    return '현재 용어집 항목으로 \"$glossaryName\"의 모든 항목을 교체합니다. 계속하시겠습니까?';
  }

  @override
  String get glossaryPanelReplaceConfirm => '교체';

  @override
  String glossaryPanelReplacedGlobal(Object name) {
    return '전역 용어집 교체됨: $name';
  }

  @override
  String glossaryPanelSavedAsNewGlobal(Object name) {
    return '새 전역 용어집으로 저장됨: $name';
  }

  @override
  String glossaryPanelSaveFailed(Object error) {
    return '저장 실패: $error';
  }

  @override
  String get glossaryPanelDetect => '용어집 감지';

  @override
  String get glossaryPanelEdit => '편집';

  @override
  String get glossaryPanelCreate => '용어집 만들기';

  @override
  String get glossaryPanelSelect => '선택';

  @override
  String get glossaryPanelImport => '가져오기';

  @override
  String get glossaryPanelExport => '내보내기';

  @override
  String get glossaryPanelSave => '저장';

  @override
  String get glossaryPanelAddEntry => '항목 추가';

  @override
  String get glossaryPanelClear => '비우기';

  @override
  String get glossaryPanelApply => '적용';

  @override
  String get glossaryPanelColumnSource => '원문';

  @override
  String get glossaryPanelColumnTarget => '번역';

  @override
  String get glossaryPanelColumnActions => '작업';

  @override
  String get translationStepsUploadTooltipReady => '파일 선택됨';

  @override
  String get translationStepsUploadTooltipNotReady => '시작하려면 파일을 선택하세요';

  @override
  String get translationStepsExtractTooltipReady => '추출 결과 보기';

  @override
  String get translationStepsExtractTooltipNotReady => '가져오기 후 추출 가능';

  @override
  String get translationStepsGlossaryTooltipSkipped => '용어집 건너뜀';

  @override
  String get translationStepsGlossaryTooltipEnabled => '용어집 사용 설정됨';

  @override
  String get translationStepsGlossaryTooltipDisabled => '용어집을 생성하거나 선택하여 사용';

  @override
  String get translationStepsTranslateTooltipReady => '번역 완료';

  @override
  String get translationStepsTranslateTooltipNotReady => '번역을 실행하여 사용';

  @override
  String get glossaryDialogAddTitle => '개인 용어집에 추가';

  @override
  String glossaryDialogAddBody(Object termCount) {
    return '이 작업은 $termCount개 용어를 개인 용어집에 추가합니다.';
  }

  @override
  String get glossaryDialogAddPreviewTitle => '미리보기 (첫 5개 용어):';

  @override
  String glossaryDialogAddMoreTerms(Object remainingCount) {
    return '... 및 $remainingCount개 추가 용어';
  }

  @override
  String get glossaryDialogMergeStrategyTitle => '병합 전략:';

  @override
  String get glossaryDialogMergeUpdateTitle => '업데이트 (권장)';

  @override
  String get glossaryDialogMergeUpdateSubtitle => '기존 용어 업데이트, 새 용어 추가';

  @override
  String get glossaryDialogMergeAppendTitle => '추가';

  @override
  String get glossaryDialogMergeAppendSubtitle => '새 용어만 추가, 기존 용어 건너뛰기';

  @override
  String get glossaryDialogMergeReplaceTitle => '교체';

  @override
  String get glossaryDialogMergeReplaceSubtitle => '전체 용어집을 이 용어들로 교체';

  @override
  String get glossaryDialogCancel => '취소';

  @override
  String get glossaryDialogReviewAndAdd => '검토 및 추가';

  @override
  String get glossaryConfirmAddTitle => '개인 용어집에 추가 확인';

  @override
  String glossaryConfirmAddBody(Object termCount) {
    return '$termCount개 용어를 개인 용어집에 추가하시겠습니까?';
  }

  @override
  String get glossaryConfirmAddStrategyUpdate => '전략: 기존 용어 업데이트, 새 용어 추가';

  @override
  String get glossaryConfirmAddStrategyAppend => '전략: 새 용어만 추가, 기존 용어 건너뛰기';

  @override
  String get glossaryConfirmAddStrategyReplace => '전략: 전체 용어집 교체';

  @override
  String get glossaryConfirmAddAutoCreateHint => '개인 용어집이 존재하지 않으면 자동으로 생성됩니다.';

  @override
  String get glossaryConfirmAddButton => '추가';

  @override
  String get glossaryExportDialogTitle => '용어집을 CSV로 저장';

  @override
  String glossaryExportSuccess(Object filename) {
    return '용어집 내보냄: $filename';
  }

  @override
  String glossaryExportFailed(Object error) {
    return '용어집 내보내기 실패: $error';
  }

  @override
  String glossaryCsvValidationFailed(Object errors) {
    return 'CSV 파일 유효성 검사 실패:\n\n$errors';
  }

  @override
  String get glossaryCsvNoValidEntries => 'CSV 파일에 유효한 항목이 없습니다.';

  @override
  String get glossaryImportDialogTitle => '용어집 가져오기';

  @override
  String glossaryImportDialogBodyEmpty(Object count) {
    return '파일에서 $count개 항목을 찾았습니다.\n\n현재 용어집이 비어 있습니다. 가져온 항목이 추가됩니다.';
  }

  @override
  String glossaryImportDialogBody(Object count) {
    return '파일에서 $count개 항목을 찾았습니다.\n\n가져오기 방법 선택:';
  }

  @override
  String get glossaryImportButtonImport => '가져오기';

  @override
  String get glossaryImportButtonReplace => '교체';

  @override
  String get glossaryImportButtonMerge => '병합';

  @override
  String glossaryImportResult(Object count, Object mode) {
    return '$count개 항목 가져옴 ($mode)';
  }

  @override
  String glossaryErrorImport(Object error) {
    return '용어집 가져오기 실패: $error';
  }

  @override
  String get glossaryErrorFileData => '파일 데이터를 읽을 수 없습니다. 다시 시도하세요.';

  @override
  String get glossaryErrorFilePath => '파일 경로를 사용할 수 없습니다. 다시 시도하세요.';

  @override
  String get glossaryErrorOnlyCsv => '용어집 가져오기는 CSV 파일만 지원됩니다.';

  @override
  String get extractFormatConversionFailed => '형식 변환 실패.';

  @override
  String get fileUploadDisabledMessage => '파일 선택 비활성화 (처리 중)';

  @override
  String get fileUploadSupportedFormats =>
      '지원: Word (DOCX), PowerPoint (PPTX), Excel (XLSX/CSV), PDF, Markdown, TXT, HTML, SRT, JSON, EPUB, MOBI, Qt TS, PNG, JPEG';

  @override
  String get fileUploadDropHere => '여기에 파일 놓기';

  @override
  String get fileUploadHint => '파일을 여기에 끌어다 놓거나 클릭하여 선택';

  @override
  String get fileUploadCancelTask => '현재 작업 취소';

  @override
  String get exclusionPanelExcludeAll => '모두 제외';

  @override
  String get exclusionPanelCancelUserExclusion => '자동 제외 복원';

  @override
  String get exclusionPanelClearAllExclusions => '모든 제외 지우기';

  @override
  String get exclusionPanelExclusionByType => '유형별 제외:';

  @override
  String get exclusionPanelStructuralHeader => '구조적 (머리글)';

  @override
  String get exclusionPanelStructuralFooter => '구조적 (바닥글)';

  @override
  String get exclusionPanelUserExcluded => '사용자 제외됨';

  @override
  String get exclusionPanelExcluded => '제외됨';

  @override
  String get exclusionPanelFilterDisplayMode => '필터 표시 모드:';

  @override
  String get exclusionPanelRebuild => '재구성';

  @override
  String get exclusionPanelPage => '페이지';

  @override
  String get exclusionPanelRebuildTooltip => '새 페이지에서 일치하는 세그먼트만 표시';

  @override
  String get exclusionPanelPageTooltip => '현재 페이지 내에서 필터링';

  @override
  String get exclusionPanelSegmentTypeFilters => '세그먼트 유형 필터:';

  @override
  String get exclusionPanelCollapsePanelTooltip => '패널 접기';

  @override
  String get exclusionPanelExclusionControls => '제외 컨트롤:';

  @override
  String exclusionPanelExcludeCategory(Object count, Object name) {
    return '$name 제외 ($count)';
  }

  @override
  String get exclusionPanelChangeReasonTitle => '제외 사유 변경';

  @override
  String get exclusionPanelCurrentLabel => '현재: ';

  @override
  String get exclusionPanelSelectNewReason => '새 사유 선택:';

  @override
  String get exclusionPanelNoneRemoveExclusion => '없음 (제외 제거)';

  @override
  String get exclusionPanelApply => '적용';

  @override
  String get exclusionPanelExpandFilterPanel => '필터 패널 확장';

  @override
  String get exclusionPanelCollapseFilterPanel => '필터 패널 접기';

  @override
  String extractToolbarSegments(Object end, Object start, Object total) {
    return '세그먼트 ($start-$end / $total)';
  }

  @override
  String get extractToolbarCancel => '취소';

  @override
  String get extractCancelExtractionTitle => '추출 취소';

  @override
  String get extractCancelExtractionContent =>
      '추출을 취소하시겠습니까? 이 작업은 되돌릴 수 없습니다.';

  @override
  String get extractCancelExtractionNo => '아니오';

  @override
  String get extractCancelExtractionYes => '예';

  @override
  String get extractExtractionCancelled => '추출 취소됨';

  @override
  String get extractMineruConfigRequiredTitle => 'MinerU 구성 필요';

  @override
  String extractMineruConfigRequiredContent(Object error) {
    return 'MinerU API에 연결하지 못했습니다. 설정 페이지에서 MinerU 설정을 구성하세요.\n\n오류 세부 정보:\n$error';
  }

  @override
  String get extractOpenSettings => '설정 열기';

  @override
  String extractErrorLabel(Object error) {
    return '오류: $error';
  }

  @override
  String get extractRetry => '다시 시도';

  @override
  String get extractTaskTypeDetectIdentifier => '식별자 감지';

  @override
  String get extractTaskTypeDetectLanguage => '언어 감지';

  @override
  String get extractTaskTypeDetectExclusions => '제외 항목 감지';

  @override
  String get translationStatsTitle => '번역 통계';

  @override
  String get translationStatsDocuments => '문서';

  @override
  String get translationStatsPages => '페이지';

  @override
  String translationStatsLastUpdated(Object date) {
    return '마지막 업데이트: $date';
  }

  @override
  String get translationStatsLoadFailed => '통계 로드 실패';

  @override
  String get translationStatsJustNow => '방금';

  @override
  String get translationStatsOneMinuteAgo => '1분 전';

  @override
  String translationStatsMinutesAgo(Object count) {
    return '$count분 전';
  }

  @override
  String get translationStatsOneHourAgo => '1시간 전';

  @override
  String translationStatsHoursAgo(Object count) {
    return '$count시간 전';
  }

  @override
  String get translationStatsYesterday => '어제';

  @override
  String translationStatsDaysAgo(Object count) {
    return '$count일 전';
  }

  @override
  String get aiPlatformDisplayName => '표시 이름';

  @override
  String get aiPlatformParserSubtype => '파서 유형';

  @override
  String get aiPlatformParserSubtypeCloud => '클�?�드';

  @override
  String get aiPlatformParserSubtypeLocal => '로컬';

  @override
  String get translationQueueEdit => '편집';

  @override
  String get reeditTitle => '번역 편집';

  @override
  String get reeditSaveExport => '저장 및 내보내기';

  @override
  String get reeditFetchError => '번역 세그먼트를 불러오지 못했습니다.';

  @override
  String get reeditSaveSuccess => '변경사항이 저장되었습니다.';

  @override
  String get reeditSaveError => '변경사항 저장에 실패했습니다.';

  @override
  String get workspaceCloseFlowTitle => '이 플로우를 닫으시겠습니까?';

  @override
  String get workspaceCloseFlowMessage => '이 플로우를 닫으면 저장되지 않은 변경 사항이 폐기됩니다.';

  @override
  String get workspaceCloseFlowSaveToQueue => '저장 후 닫기';

  @override
  String get workspaceCloseFlowDestroy => '파기 후 닫기';

  @override
  String get workspaceCloseFlowCancel => '취소';

  @override
  String get fetchUrlCancel => '취소';

  @override
  String get loginSubtitleFeatures => '파일 번역\n형식 변환\nURL 가져오기';

  @override
  String get loginSubtitleTagline => 'AI 문서 처리 시스템';

  @override
  String get loginUsernameLabel => '사용자 이름';

  @override
  String get loginUsernameHint => '사용자 이름을 입력하세요';

  @override
  String get loginUsernameRequiredError => '사용자 이름을 입력하세요';

  @override
  String get loginUsernameMinLengthError => '사용자 이름은 최소 3자 이상이어야 합니다';

  @override
  String get loginPasswordLabel => '비밀번호';

  @override
  String get loginPasswordHint => '비밀번호를 입력하세요';

  @override
  String get loginPasswordRequiredError => '비밀번호를 입력하세요';

  @override
  String get loginForgotPassword => '비밀번호를 잊으셨나요?';

  @override
  String get loginPasswordRecoveryTitle => '비밀번호 복구';

  @override
  String get loginPasswordRecoveryContactAdmin => '관리자에게 문의하여 비밀번호를 재설정하세요.';

  @override
  String get loginPasswordRecoveryAdminHint =>
      '관리자는 로그인 후 사용자 관리 페이지에서 비밀번호를 재설정할 수 있습니다.';

  @override
  String get loginAuthMethodDefault => '기본 인증 사용';

  @override
  String get loginCopyErrorLabel => '복사';

  @override
  String get loginErrorCopiedMessage => '오류 메시지가 클립보드에 복사되었습니다';

  @override
  String get loginWelcomeBack => '돌아오신 것을 환영합니다';

  @override
  String get loginFeatureFormats =>
      'PDF, DOCX, XLSX, HTML, EPUB, MOBI\n및 15개 이상의 형식';

  @override
  String get loginFeatureLayout => '레이아웃을 보존하는 번역\n높은 충실도';

  @override
  String get loginFeaturePlatforms =>
      '20+ LLM 플랫폼 지원\nOpenAI, Claude, Ollama 포함';

  @override
  String get loginPasswordRecoveryAdminGuide => '관리자라면 비밀번호 복구 절차를 따라주세요.';
}
