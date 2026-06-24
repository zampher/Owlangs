// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get settingsGeneralTitle => 'Configuración General';

  @override
  String get settingsGeneralDarkModeTitle => 'Modo Oscuro';

  @override
  String get settingsGeneralDarkModeSubtitle =>
      'Activar tema oscuro (se aplica inmediatamente)';

  @override
  String get settingsGeneralLanguageTitle => 'Idioma';

  @override
  String get settingsGeneralNotificationsTitle => 'Notificaciones';

  @override
  String get settingsGeneralNotificationsSubtitle =>
      'Recibir notificaciones para tareas completadas (se aplica inmediatamente)';

  @override
  String get settingsGeneralAutoSaveTitle => 'Guardado Automático';

  @override
  String get settingsGeneralAutoSaveSubtitle =>
      'Guardar automáticamente el trabajo en progreso (se aplica inmediatamente)';

  @override
  String get settingsGeneralShowAdsTitle => 'Mostrar Anuncios';

  @override
  String get settingsGeneralShowAdsSubtitle =>
      'Mostrar marcadores de posición de anuncios en Inicio y en Flujo (almacenado en system.json)';

  @override
  String get settingsGeneralClearStatsButton => 'Limpiar Estadísticas';

  @override
  String get settingsGeneralClearStatsConfirmTitle => '¿Limpiar Estadísticas?';

  @override
  String get settingsGeneralClearStatsConfirmMessage =>
      'Esto restablecerá a 0 el recuento de documentos y páginas mostrado en la página de inicio. Esta acción no se puede deshacer.';

  @override
  String get settingsGeneralClearStatsConfirmButton => 'Limpiar';

  @override
  String get settingsGeneralClearStatsSuccess =>
      'Estadísticas limpiadas correctamente.';

  @override
  String get backToHome => 'Volver a Inicio';

  @override
  String get settingsFontSectionTitle => 'Configuración de Fuente';

  @override
  String get settingsFontPreviewSizeTitle => 'Tamaño de Fuente de Vista Previa';

  @override
  String get settingsFontPreviewSizeSubtitle =>
      'Tamaño de fuente para el texto fuente y objetivo en la vista previa';

  @override
  String get translationToolbarFilterAll => 'Todos';

  @override
  String get translationToolbarFilterFailed => 'Fallido';

  @override
  String get translationToolbarFilterIncluded => 'Incluido';

  @override
  String get translationToolbarFilterExcluded => 'Excluido';

  @override
  String get translationToolbarSearchTooltip => 'Buscar (Ctrl+F / Cmd+F)';

  @override
  String get translationToolbarPrevRetryTooltip =>
      'Segmento de Reintento Anterior';

  @override
  String get translationToolbarNextRetryTooltip =>
      'Segmento de Reintento Siguiente';

  @override
  String get translationToolbarPreviewTooltip => 'Vista Previa';

  @override
  String get translationToolbarFormatSettingsTooltip =>
      'Configuración de Formato';

  @override
  String get translationToolbarExportTooltip => 'Exportar Documento';

  @override
  String get translationToolbarPdfPreviewTooltip =>
      'Vista Previa PDF (Depuración)';

  @override
  String get translationToolbarCancelButton => 'Cancelar';

  @override
  String get translationToolbarExitFullscreenTooltip =>
      'Salir de Pantalla Completa';

  @override
  String get translationToolbarEnterFullscreenTooltip =>
      'Entrar en Pantalla Completa';

  @override
  String get translationToolbarDecreaseFontSize => 'Reducir tamaño de fuente';

  @override
  String get translationToolbarIncreaseFontSize => 'Aumentar tamaño de fuente';

  @override
  String get translationToolbarMergedView => 'Modo lectura';

  @override
  String get translationToolbarSegmentView => 'Modo etiquetado';

  @override
  String get translationToolbarUpload => 'Subir';

  @override
  String get translationToolbarUploading => 'Subiendo...';

  @override
  String get translationToolbarFileUploaded => 'Archivo Subido';

  @override
  String get translationToolbarReextract => 'Re-extraer';

  @override
  String get translationToolbarReextracting => 'Re-extracción en curso...';

  @override
  String translationToolbarTokensCount(Object count) {
    return '$count tokens';
  }

  @override
  String get translationToolbarOpenGlossaryTab => 'Abrir pestaña de glosario';

  @override
  String get translationToolbarHintWaitExtract =>
      'Por favor, espere a que la Extracción se complete';

  @override
  String get translationToolbarHintOperationInProgress =>
      'Una operación está en progreso';

  @override
  String get translationToolbarGlossary => 'Glosario';

  @override
  String get translationToolbarPrompt => 'Prompt';

  @override
  String get translationToolbarOpenPromptTab => 'Abrir pestaña de prompt';

  @override
  String get translationToolbarConvertHint =>
      'Convierte formato, excluye todos los segmentos, traduce y exporta desde la pestaña Convertir';

  @override
  String get translationToolbarConvert => 'Convertir';

  @override
  String get translationToolbarHintSaveGlossaryFirst =>
      'Por favor, guarde el glosario primero (haga clic en Aplicar)';

  @override
  String get translationToolbarHintUpdatingExcluded =>
      'Actualizando segmentos excluidos...';

  @override
  String get translationToolbarStartTranslation => 'Iniciar traducción';

  @override
  String get translationToolbarTranslateAll => 'Traducir Todo';

  @override
  String get translationToolbarTranslating => 'Traduciendo...';

  @override
  String get translationToolbarRetryInProgress => 'Reintento en progreso...';

  @override
  String get translationToolbarRetryTooltip =>
      'Reintentar todos los segmentos fallidos o marcados. Esto retraducirá los segmentos que fallaron durante la traducción o fueron marcados manualmente para reintento, usando la plataforma de IA actualmente seleccionada. Los segmentos excluidos y borrados se omitirán.';

  @override
  String get translationToolbarRetry => 'Reintentar';

  @override
  String get translationPersistQueueTooltip =>
      'Escribe las exportaciones actuales en el servidor y actualiza la cola para que las descargas coincidan con tus últimos cambios aquí.';

  @override
  String get translationPersistQueueButton => 'Actualizar cola';

  @override
  String get translationPersistQueueAlreadySyncedTooltip =>
      'Ya coincide con la instantánea de la cola. No hace falta guardar de nuevo.';

  @override
  String get translationPersistQueueSuccess =>
      'Exportaciones guardadas para la cola de tareas.';

  @override
  String translationPersistQueueFailed(Object error) {
    return 'No se pudo guardar para la cola: $error';
  }

  @override
  String get translationCloseTranslateTabTitle =>
      'La cola de tareas puede no tener el resultado final';

  @override
  String get translationCloseTranslateTabMessage =>
      'Tus ediciones aquí aún no están guardadas en la instantánea de la cola de tareas. Si cierras sin guardar, los archivos que descargues desde la cola pueden no ser la versión final que ves en esta pestaña.\n\nPuedes actualizar la cola y cerrar, o cerrar esta pestaña sin guardar en la cola.';

  @override
  String get translationCloseTranslateTabStay => 'Permanecer';

  @override
  String get translationCloseTranslateTabClose => 'Cerrar sin guardar';

  @override
  String get translationCloseTranslateTabSaveAndClose =>
      'Guardar en la cola y cerrar';

  @override
  String get translationCloseTranslateTabKeepTitle =>
      '¿Mantener tarea en la cola?';

  @override
  String get translationCloseTranslateTabKeepMessage =>
      'La tarea ha finalizado. ¿Mantenerla en la cola para revisarla y editarla más tarde?';

  @override
  String get translationCloseTranslateTabKeepInQueue => 'Mantener en cola';

  @override
  String get translationCloseTranslateTabDiscard => 'Descartar';

  @override
  String get translationToolbarSwitchToFile => 'Cambiar a Archivo';

  @override
  String get translationToolbarSwitchToText => 'Ingresar Texto';

  @override
  String get translationStatusCompleted => 'Traducción Completada';

  @override
  String get translationStatusRetry => 'Reintento de Traducción';

  @override
  String get translationStatusFailed => 'Traducción Fallida';

  @override
  String get translationStatusCancelled => 'Traducción Cancelada';

  @override
  String get translationStatusTranslating => 'Traduciendo';

  @override
  String get translationStatusTranslatingFallback => 'Traduciendo...';

  @override
  String get translationStatusReady => 'Listo';

  @override
  String get translationStatusTaskPending => 'Tarea Pendiente';

  @override
  String get translationStatusProcessing => 'Procesando...';

  @override
  String translationStatsSuccessOnly(Object success, Object total) {
    return 'Éxito: $success/$total';
  }

  @override
  String translationStatsSuccessFailed(
      Object fail, Object success, Object total) {
    return 'Éxito: $success/$total, Fallido: $fail/$total';
  }

  @override
  String translationStatsTotal(Object count) {
    return 'Total: $count | ';
  }

  @override
  String translationStatsTranslated(Object count) {
    return 'Traducido: $count | ';
  }

  @override
  String translationStatsPending(Object count) {
    return 'Pendiente: $count';
  }

  @override
  String translationStatsExcluded(Object count) {
    return ' | Excluido: $count';
  }

  @override
  String translationStatsRetryCount(Object count) {
    return ' | Reintentar: $count';
  }

  @override
  String translationStatsCleared(Object count) {
    return ' | Borrado: $count';
  }

  @override
  String translationStatsImages(Object count) {
    return ' | Imágenes: $count';
  }

  @override
  String translationStatsSegment(Object current, Object total) {
    return 'Segmento: $current / $total';
  }

  @override
  String get translationStatsDoubleClickToEdit =>
      'Haga doble clic en el texto para editar.';

  @override
  String get translationStatsTranslatedLabel => 'Traducido';

  @override
  String get translationStatsPendingLabel => 'Pendiente';

  @override
  String get translationStatsClearedLabel => 'Borrado';

  @override
  String get translationStatsImagesLabel => 'Imágenes';

  @override
  String get translationStatsLoadingContent => 'Cargando contenido...';

  @override
  String get translationStatsNoContentAvailable =>
      'No hay contenido disponible.';

  @override
  String get translationStatsNoSegmentsAvailable =>
      'No hay segmentos disponibles';

  @override
  String translationStatsTokenIn(Object count) {
    return 'Entrada: $count';
  }

  @override
  String translationStatsTokenOut(Object count) {
    return 'Salida: $count';
  }

  @override
  String translationStatsTokenTotal(Object count) {
    return '($count)';
  }

  @override
  String get translationLangArabic => 'Árabe';

  @override
  String get translationLangBengali => 'Bengalí';

  @override
  String get translationLangCatalan => 'Catalán';

  @override
  String get translationLangChinese => 'Chino';

  @override
  String get translationLangChineseTraditional => 'Chino (Tradicional)';

  @override
  String get translationLangCzech => 'Checo';

  @override
  String get translationLangCroatian => 'Croata';

  @override
  String get translationLangDanish => 'Danés';

  @override
  String get translationLangDutch => 'Neerlandés';

  @override
  String get translationLangEnglish => 'Inglés';

  @override
  String get translationLangFilipino => 'Filipino';

  @override
  String get translationLangFinnish => 'Finés';

  @override
  String get translationLangFrench => 'Francés';

  @override
  String get translationLangGerman => 'Alemán';

  @override
  String get translationLangGreek => 'Griego';

  @override
  String get translationLangHebrew => 'Hebreo';

  @override
  String get translationLangHindi => 'Hindi';

  @override
  String get translationLangItalian => 'Italiano';

  @override
  String get translationLangJapanese => 'Japonés';

  @override
  String get translationLangKorean => 'Coreano';

  @override
  String get translationLangKhmer => 'Jemer';

  @override
  String get translationLangLithuanian => 'Lituano';

  @override
  String get translationLangMacedonian => 'Macedonio';

  @override
  String get translationLangMalay => 'Malayo';

  @override
  String get translationLangNorwegian => 'Noruego Bokmål';

  @override
  String get translationLangPolish => 'Polaco';

  @override
  String get translationLangPortuguese => 'Portugués';

  @override
  String get translationLangRomanian => 'Rumano';

  @override
  String get translationLangRussian => 'Ruso';

  @override
  String get translationLangSlovenian => 'Esloveno';

  @override
  String get translationLangSpanish => 'Español';

  @override
  String get translationLangSwedish => 'Sueco';

  @override
  String get translationLangThai => 'Tailandés';

  @override
  String get translationLangTurkish => 'Turco';

  @override
  String get translationLangUkrainian => 'Ucraniano';

  @override
  String get translationLangUrdu => 'Urdu';

  @override
  String get translationLangVietnamese => 'Vietnamita';

  @override
  String get translationExportNoFormats =>
      'No hay formatos de exportación disponibles';

  @override
  String get translationExportDialogTitle => 'Exportar Documento';

  @override
  String get translationExportDocumentType => 'Tipo de Documento';

  @override
  String get translationExportFormatOptionsTitle =>
      'Opciones de Formato (solo PDF)';

  @override
  String get translationExportTableFormatLabel => 'Formato de Tabla:';

  @override
  String get translationExportTableFormatImage => 'Imagen';

  @override
  String get translationExportTableFormatHtml => 'HTML';

  @override
  String get translationExportEquationFormatLabel => 'Formato de Ecuación:';

  @override
  String get translationExportEquationFormatImage => 'Imagen';

  @override
  String get translationExportEquationFormatLatex => 'LaTeX';

  @override
  String get translationExportChartFormatLabel => 'Formato de Gráfico:';

  @override
  String get translationExportChartFormatImage => 'Imagen';

  @override
  String get translationExportChartFormatHtml => 'HTML';

  @override
  String get translationImageCoverColorModeLabel => 'Borrar fondo:';

  @override
  String get translationImageCoverColorModeMax => 'Píxel más claro (máx)';

  @override
  String get translationImageCoverColorModeMin => 'Píxel más oscuro (mín)';

  @override
  String get translationImageCoverColorModeAvg => 'Píxel promedio (media)';

  @override
  String get translationExportBilingualExport => 'Exportación Bilingüe';

  @override
  String get translationExportBilingualOrderTargetAfter => 'Origen Primero';

  @override
  String get translationExportBilingualOrderTargetAfterSub =>
      'Origen primero, destino después';

  @override
  String get translationExportBilingualOrderTargetBefore =>
      'Destino Antes de Origen';

  @override
  String get translationExportBilingualOrderTargetBeforeSub =>
      'Destino primero, origen después';

  @override
  String get translationExportSourceTextItalic => 'Texto original en cursiva';

  @override
  String get translationExportSourceTextColor => 'Color del texto original:';

  @override
  String get translationExportTargetTextItalic => 'Texto traducido en cursiva';

  @override
  String get translationExportTargetTextColor => 'Color del texto traducido:';

  @override
  String get translationExportSourceFontSizeDelta =>
      'Desplazamiento de tamaño de fuente original:';

  @override
  String get translationExportTargetFontSizeDelta =>
      'Desplazamiento de tamaño de fuente traducida:';

  @override
  String get translationExportColorDefault => 'Predeterminado';

  @override
  String get translationExportColorGray => 'Gris';

  @override
  String get translationExportColorBlue => 'Azul';

  @override
  String get translationExportColorRed => 'Rojo';

  @override
  String get translationExportColorGreen => 'Verde';

  @override
  String get translationExportColorOrange => 'Naranja';

  @override
  String get translationExportColorBlack => 'Negro';

  @override
  String get translationExportDownloadButton => 'Descargar';

  @override
  String get translationExportMdEmbeddedImages =>
      'MD (con imágenes incrustadas)';

  @override
  String get translationExportMdWithImagesFolder =>
      'MD (con carpeta de imágenes)';

  @override
  String get translationExportPdfPreserveLayout => 'PDF diseño original';

  @override
  String get translationExportPdfPreserveLayoutDesc =>
      'Superpone la traducción sobre el diseño PDF original';

  @override
  String get translationExportImageOriginalLayout =>
      'Imagen con diseño original';

  @override
  String get translationExportImageOriginalLayoutDesc =>
      'Borra el texto OCR y escribe la traducción sobre la imagen original';

  @override
  String get translationExportPdfReflow => 'PDF recompuesto';

  @override
  String get translationExportPdfReflowDesc =>
      'Recompuesto desde Markdown traducido; el diseño puede diferir del original';

  @override
  String get translationPreviewDialogTitle => 'Configuración de vista previa';

  @override
  String get translationPreviewStart => 'Iniciar vista previa';

  @override
  String get translationPreviewModeSectionTitle => 'Vista previa de traducción';

  @override
  String get translationPreviewModeHtml => 'HTML / Markdown';

  @override
  String get translationPreviewModeHtmlDesc =>
      'Ver la traducción renderizada en el navegador (predeterminado)';

  @override
  String get translationPreviewFullDocumentCompare =>
      'Comparación de documento completo';

  @override
  String get translationPreviewFullDocumentCompareDesc =>
      'Ver original y traducción lado a lado (formato de exportación; compatible con cualquier modo de vista previa anterior)';

  @override
  String get translationPreviewSyncScroll =>
      'Vincular barras de desplazamiento';

  @override
  String get translationPreviewSyncScrollDesc =>
      'Al activarlo, oculta las barras de desplazamiento de ambos paneles y usa una barra compartida a la derecha para controlar original y traducción (solo comparación PDF)';

  @override
  String get translationPreviewRevisionSyncScrollDesc =>
      'Al activarlo, oculta las barras de desplazamiento separadas de las vistas previas de original y traducción; muestra una barra compartida entre ambas con desplazamiento vinculado';

  @override
  String get translationPreviewPanelSource => 'Original';

  @override
  String get translationPreviewPanelTarget => 'Traducción';

  @override
  String get translationPreviewNoExtraOptions =>
      'No hay opciones adicionales para este modo de vista previa';

  @override
  String get translationPreviewReopenSettings =>
      'Configuración de vista previa';

  @override
  String get translationPreviewZoomIn => 'Acercar';

  @override
  String get translationPreviewZoomOut => 'Alejar';

  @override
  String get translationPreviewZoomReset => 'Restablecer zoom';

  @override
  String get translationLeftPanelExpandTooltip => 'Expandir panel izquierdo';

  @override
  String get translationLeftPanelCollapseTooltip => 'Contraer panel izquierdo';

  @override
  String get translationSnackGlossarySaved => 'Glosario guardado';

  @override
  String get translationSnackTranslationCancelled => 'Traducción cancelada';

  @override
  String get translationSnackNoLlmpSelected =>
      'No se seleccionó ninguna Plataforma LLM';

  @override
  String get translationSnackTextEmpty => 'La entrada de texto está vacía.';

  @override
  String get translationSnackTextConverted =>
      'Texto convertido a formato de archivo';

  @override
  String get translationSnackSourceResplitCompleted =>
      'Re-división de fuente completada';

  @override
  String get translationSnackPleaseSelectFileOrText =>
      'Por favor, seleccione un archivo o ingrese texto primero';

  @override
  String get translationSnackPleaseSelectFileOrTextWithDot =>
      'Por favor, seleccione un archivo o ingrese texto primero.';

  @override
  String get translationSnackPleaseSelectFile =>
      'Por favor, seleccione un archivo primero';

  @override
  String get translationSnackPleaseSelectDocumentFirst =>
      'Por favor, seleccione un documento primero.';

  @override
  String get translationSnackGlossaryGenerated =>
      '¡Glosario generado con éxito!';

  @override
  String get translationSnackGlossaryGenerationCancelled =>
      'Generación de glosario cancelada';

  @override
  String get translationSnackGlossaryAppliedToTask =>
      'Glosario aplicado a la tarea de traducción';

  @override
  String get translationSnackPreviousTranslationCancelled =>
      'Traducción anterior cancelada';

  @override
  String get translationSnackGlossarySavedAndApplied =>
      'Glosario guardado y aplicado';

  @override
  String get translationDialogMixedLangTitle => 'Idioma Mixto Detectado';

  @override
  String translationDialogMixedLangContent(Object distribution) {
    return 'El documento contiene múltiples idiomas:\n$distribution';
  }

  @override
  String get translationDialogMixedLangPromptTitle =>
      'Para mejorar la calidad de la traducción, puede agregar instrucciones de prompt:';

  @override
  String get translationDialogMixedLangOption1Title =>
      'Solo traducir texto en idioma fuente';

  @override
  String translationDialogMixedLangOption1Subtitle(Object languageName) {
    return 'Solo traducir texto en idioma $languageName';
  }

  @override
  String get translationDialogMixedLangOption2Title =>
      'Mantener código y términos técnicos sin cambios';

  @override
  String get translationDialogMixedLangOption2Subtitle =>
      'Mantener bloques de código, términos técnicos, nombres de funciones y texto en otros idiomas sin cambios';

  @override
  String get translationDialogMixedLangCancel => 'Cancelar';

  @override
  String get translationDialogMixedLangSkip => 'Omitir';

  @override
  String get translationDialogMixedLangApply => 'Aplicar';

  @override
  String get translationSnackExportStarted =>
      'La tarea de exportación ha comenzado, por favor espere.';

  @override
  String get translationSnackPromptUpdated =>
      'Instrucciones de prompt actualizadas';

  @override
  String translationSnackFailedToCancel(Object error) {
    return 'Error al cancelar: $error';
  }

  @override
  String translationSnackFailedConvertTextFormat(Object error) {
    return 'Error al convertir formato de texto: $error';
  }

  @override
  String translationSnackFailedConvertText(Object error) {
    return 'Error al convertir texto: $error';
  }

  @override
  String translationSnackFailedResplit(Object error) {
    return 'Error al re-dividir: $error';
  }

  @override
  String get translationSnackRequestFailed => 'Solicitud fallida';

  @override
  String translationSnackFileImportFailed(Object error) {
    return 'Error al importar archivo: $error';
  }

  @override
  String translationSnackTaskStatus(Object status) {
    return 'Estado de la tarea: $status';
  }

  @override
  String translationSnackFileDownloaded(Object filename) {
    return 'Archivo descargado: $filename';
  }

  @override
  String translationSnackFileSaved(Object filename) {
    return 'Archivo guardado: $filename';
  }

  @override
  String translationSnackFailedDownload(Object error, Object fileType) {
    return 'Error al descargar $fileType: $error';
  }

  @override
  String translationSnackFailedOpenDownload(Object url) {
    return 'Error al abrir descarga: $url';
  }

  @override
  String get translationDialogSwitchToFileTitle => 'Cambiar a Modo Archivo';

  @override
  String get translationDialogSwitchToFileBody =>
      'Cambiar al modo archivo borrará su entrada de texto actual. ¿Desea continuar?';

  @override
  String get translationDialogSwitchToTextTitle => 'Cambiar a Modo Texto';

  @override
  String get translationDialogSwitchToTextBody =>
      'Cambiar al modo texto borrará la selección de archivo actual. ¿Desea continuar?';

  @override
  String get translationSnackAllSegmentsExcludedSkipped =>
      'Todos los segmentos están excluidos. La traducción se omitirá. Puede exportar el archivo para conversión de formato.';

  @override
  String get translationDialogCancelButton => 'Cancelar';

  @override
  String get translationDialogContinueButton => 'Continuar';

  @override
  String get translationNoLlmAvailableTitle =>
      'No hay plataforma LLM disponible';

  @override
  String get translationNoLlmAvailableMessage =>
      'No hay plataforma LLM configurada y disponible. Para traducir, por favor configure una Clave API de LLM en Configuración primero; si solo necesita conversión de formato, puede continuar.';

  @override
  String get translationNoLlmConfigureButton => 'Configurar LLM';

  @override
  String get translationNoLlmContinueFormatOnlyButton =>
      'Solo conversión de formato';

  @override
  String get languageMatchWarningTitle =>
      'Advertencia de Coincidencia de Idioma';

  @override
  String languageMatchWarningGlossaryBody(
      Object detectedName, Object targetName) {
    return 'El idioma fuente detectado ($detectedName) es el mismo que el idioma objetivo ($targetName). ¿Está seguro de que desea continuar con la generación del glosario?';
  }

  @override
  String languageMatchWarningTranslationBody(
      Object detectedName, Object targetName) {
    return 'El idioma fuente detectado ($detectedName) es el mismo que el idioma objetivo ($targetName). ¿Está seguro de que desea continuar con la traducción?';
  }

  @override
  String get translationDialogCancelTaskTitle => 'Cancelar Tarea Actual';

  @override
  String get translationDialogCancelTaskBody =>
      'Esto cancelará la tarea de extracción/traducción actual y borrará el archivo seleccionado. ¿Desea continuar?';

  @override
  String get translationDialogCancelTaskNo => 'No';

  @override
  String get translationDialogCancelTaskYesCancel => 'Sí, Cancelar';

  @override
  String get translationQuickSettingsTitle => 'Configuración Rápida';

  @override
  String get quickSettingsTargetLanguage => 'Idioma Objetivo';

  @override
  String get quickSettingsSourceLanguage => 'Idioma de origen (MinerU OCR)';

  @override
  String get quickSettingsLanguageSwitchDisabled =>
      'El cambio de idioma está deshabilitado durante la traducción. Por favor, cambie a la pestaña Extraer para cambiar el idioma objetivo.';

  @override
  String get quickSettingsParsingPlatform => 'Plataforma de Análisis';

  @override
  String get quickSettingsTestMineru => 'Probar conexión MinerU';

  @override
  String get quickSettingsNotConfigured => 'No configurado';

  @override
  String get quickSettingsApiOk => 'API OK';

  @override
  String get quickSettingsApiUnavailable => 'API no disponible';

  @override
  String get quickSettingsNotTestedYet => 'Aún no probado';

  @override
  String get quickSettingsConnectionSuccessful => 'Conexión exitosa';

  @override
  String get quickSettingsMineruConnectionFailed => 'Conexión MinerU fallida';

  @override
  String get quickSettingsOpenMineruSettings => 'Abrir configuración de MinerU';

  @override
  String get quickSettingsTableOcr => 'OCR de tablas';

  @override
  String get quickSettingsTableOcrSubtitle =>
      'Reconocer tablas durante el análisis de documentos';

  @override
  String get quickSettingsFormulaOcr => 'OCR de fórmulas';

  @override
  String get quickSettingsFormulaOcrSubtitle =>
      'Reconocer fórmulas durante el análisis de documentos';

  @override
  String get quickSettingsPaddleUseDocOrientationClassify =>
      'Detección Automática de Orientación';

  @override
  String get quickSettingsPaddleUseDocOrientationClassifySubtitle =>
      'Detectar y corregir automáticamente la orientación del documento antes del OCR';

  @override
  String get quickSettingsPaddleRestructurePages => 'Reestructurar Páginas';

  @override
  String get quickSettingsPaddleRestructurePagesSubtitle =>
      'Reestructurar el diseño de página para mejor orden de lectura';

  @override
  String get quickSettingsMineruLabel => 'MinerU (mineru)';

  @override
  String get quickSettingsLlmPlatform => 'Plataforma LLM';

  @override
  String get quickSettingsTestLlmPlatform => 'Probar plataforma LLM actual';

  @override
  String get quickSettingsTestFailed => 'Prueba fallida';

  @override
  String get quickSettingsOpenAiPlatformsSettings =>
      'Abrir configuración de Plataformas AI';

  @override
  String get quickSettingsTemperature => 'Temperatura';

  @override
  String get quickSettingsTemperatureHint =>
      'Controla la aleatoriedad: Más bajo = más enfocado, Más alto = más creativo';

  @override
  String get quickSettingsQtTsOptions => 'Opciones de Traducción Qt .ts';

  @override
  String get quickSettingsQtTsSkipExisting => 'Omitir traducciones existentes';

  @override
  String get quickSettingsQtTsSkipExistingSubtitle =>
      'Omitir mensajes que ya tienen traducciones';

  @override
  String get quickSettingsQtTsTranslateUnfinished =>
      'Traducir entradas no terminadas';

  @override
  String get quickSettingsQtTsTranslateUnfinishedSubtitle =>
      'Traducir mensajes marcados como no terminados (type=\"unfinished\")';

  @override
  String get quickSettingsQtTsTranslateVanished =>
      'Traducir entradas desaparecidas';

  @override
  String get quickSettingsQtTsTranslateVanishedSubtitle =>
      'Traducir mensajes marcados como desaparecidos (type=\"vanished\")';

  @override
  String get quickSettingsQtTsTranslateObsolete =>
      'Traducir entradas obsoletas';

  @override
  String get quickSettingsQtTsTranslateObsoleteSubtitle =>
      'Traducir mensajes marcados como obsoletos (type=\"obsolete\")';

  @override
  String get quickSettingsPrompt => 'Prompt';

  @override
  String get quickSettingsPromptMode => 'Modo de Prompt';

  @override
  String get quickSettingsPromptModeOff => 'Apagado (Sin prompt)';

  @override
  String get quickSettingsPromptModeSimple => 'Simple (Solo estilo)';

  @override
  String get quickSettingsPromptModeAdvanced => 'Avanzado (Estilo + Nota)';

  @override
  String get quickSettingsStyle => 'Estilo';

  @override
  String get quickSettingsStyleLiteral => 'Literal';

  @override
  String get quickSettingsStyleFluent => 'Fluido';

  @override
  String get quickSettingsStyleAcademic => 'Académico';

  @override
  String get quickSettingsStyleBusiness => 'Empresarial';

  @override
  String get quickSettingsStyleTechnical => 'Técnico';

  @override
  String get quickSettingsStyleNone => 'Ninguno';

  @override
  String get quickSettingsTaskNoteLabel => 'Nota de tarea (instrucción breve)';

  @override
  String get quickSettingsTaskNoteHint =>
      'ej. Mantener fórmulas sin modificar; anotar nombres propios';

  @override
  String get promptTabDescription =>
      'Seleccione el modo de prompt y el estilo de traducción. Cuando esté activo, agregue instrucciones personalizadas detalladas abajo.';

  @override
  String get promptTabLongInstructionLabel => 'Instrucción personalizada';

  @override
  String get promptTabLongInstructionHint =>
      'Guía extensa para la traducción: tono, terminología, reglas de formato o requisitos del dominio.';

  @override
  String get quickSettingsAdRegionF =>
      'Región F: Parte inferior de Configuración Rápida\n(Rectángulo Mediano 300×250)';

  @override
  String quickSettingsPlatformMessage(Object label, Object message) {
    return '$label: $message';
  }

  @override
  String quickSettingsPlatformTestFailed(Object error, Object label) {
    return '$label: Prueba fallida — $error';
  }

  @override
  String get homeTagline =>
      'Basado en IA, Inmersión\nPrivado, Seguro (En desarrollo)\nCompartido en Equipo, Personalizable\n';

  @override
  String get homeIntro =>
      'Suba documentos y tradúzcalos a múltiples idiomas con precisión impulsada por IA.\n';

  @override
  String get homeHowItWorks =>
      'Cómo funciona\nTraducción: Importar -> Analizar documento -> Glosario -> Traducir -> Exportar\nConversión de formato: Importar -> Analizar documento -> Convertir -> Exportar\nExtracción de URL: Ingresar URL -> Obtener página -> Analizar contenido -> Extraer texto -> Traducir/Exportar';

  @override
  String get homeSnackDonorExpired =>
      'Su código de registro ha expirado. Por favor, regístrese nuevamente para continuar con los beneficios Pro.';

  @override
  String get commonCancel => 'Cancelar';

  @override
  String get commonOk => 'Aceptar';

  @override
  String get homeAuthErrorTitle => 'Error de Autenticación';

  @override
  String get homeAuthRetryLogin => 'Reintentar Inicio de Sesión';

  @override
  String homeAiPlatformsAvailable(Object platforms) {
    return 'Plataformas de IA disponibles: $platforms';
  }

  @override
  String get homeAiPlatformsConfigureNotice =>
      'Por favor, configure sus plataformas de IA en el panel de configuración antes de usar la aplicación.';

  @override
  String get homeBackendStatusStarting => 'El backend está iniciándose...';

  @override
  String get homeBackendStatusConnecting => 'Conectando al backend...';

  @override
  String get homeBackendStatusConnected => 'Backend conectado';

  @override
  String get homeBackendStatusDisconnected =>
      'El backend está desconectado. Por favor, reintente.';

  @override
  String get homeBackendStatusUnknown => 'Conectando al backend...';

  @override
  String get homeBackendRetry => 'Reintentar';

  @override
  String get homeNewTask => 'Nueva tarea';

  @override
  String get homeNewTaskImmersiveTooltip =>
      'Comparar original y traducción lado a lado en la interfaz';

  @override
  String get homeNewTaskQueuedTooltip =>
      'Importar archivos por lote y ejecutar en orden';

  @override
  String get homeNavTranslate => 'Tarea inmersiva';

  @override
  String get homeNavTranslationQueue => 'Tareas';

  @override
  String get homeNavAnonymize => 'Anonimizar';

  @override
  String get homeNavSettings => 'Configuración';

  @override
  String get homeNavDonateHelp => 'Ayuda';

  @override
  String get homeNavDonate => 'Donar';

  @override
  String get homeNavHome => 'Inicio';

  @override
  String get homeNavBatchUpload => 'Subida por lotes';

  @override
  String get homeNavTooltipNewTask =>
      'Iniciar una nueva traducción — comparación lado a lado, o procesamiento por lotes';

  @override
  String get homeNavTooltipTasks =>
      'Ver y gestionar todas las tareas, descargar traducciones completadas';

  @override
  String get homeNavTooltipAnonymize =>
      'Anonimizar el contenido del documento para proteger información confidencial';

  @override
  String get homeNavTooltipSettings =>
      'Configurar idioma, tema, notificaciones y más';

  @override
  String get homeNavTooltipSetupWizard =>
      'Asistente de configuración guiada para tu entorno de traducción';

  @override
  String get homeNavTooltipHelp => 'Obtener ayuda y soporte técnico';

  @override
  String get homeNavTooltipDonate =>
      'Apoyar nuestro proyecto de código abierto';

  @override
  String get homeNavTooltipHome => 'Volver a la página de inicio';

  @override
  String get homeNavTooltipGitHub =>
      'Ver código fuente en GitHub — ¡danos una estrella si te resulta útil!';

  @override
  String get batchUploadTitle => 'Subida de archivos por lotes';

  @override
  String get batchUploadFormatConvert => 'Conversión de formato';

  @override
  String get batchUploadSelectSourceHint =>
      'Elija los archivos compatibles para traducir. Cada archivo se convierte en una tarea en cola.';

  @override
  String get batchUploadSelectFolder => 'Seleccionar carpeta';

  @override
  String get batchUploadFolderDescription =>
      'Elija una carpeta con archivos para traducir';

  @override
  String get batchUploadSelectZip => 'Seleccionar archivo ZIP';

  @override
  String get batchUploadZipDescription =>
      'Elija un archivo ZIP con archivos para traducir';

  @override
  String get batchUploadSelectSingleFile => 'Seleccionar archivo';

  @override
  String get batchUploadSingleFileDescription =>
      'Elija un solo archivo para traducir';

  @override
  String get batchUploadAddFiles => 'Agregar archivos';

  @override
  String batchUploadFilesFound(Object count) {
    return '$count archivos compatibles encontrados';
  }

  @override
  String get batchUploadSelectAll => 'Seleccionar todo';

  @override
  String get batchUploadDeselectAll => 'Deseleccionar todo';

  @override
  String get batchUploadStartTranslation => 'Iniciar traducción';

  @override
  String get batchUploadSubmitting => 'Enviando archivos...';

  @override
  String batchUploadProgress(Object completed, Object total) {
    return 'Enviados $completed de $total archivos';
  }

  @override
  String get batchUploadCompleteTitle => 'Lote completado';

  @override
  String batchUploadComplete(Object success, Object failed) {
    return '$success exitosos, $failed fallidos';
  }

  @override
  String get batchUploadNoSupportedFiles =>
      'No se encontraron archivos compatibles';

  @override
  String batchUploadSelectedCount(Object count) {
    return '$count archivos seleccionados';
  }

  @override
  String batchUploadLegacyFormatsFound(Object files) {
    return '$files no se puede traducir directamente. Convierta .doc a .docx, .ppt a .pptx, .xls a .xlsx antes de enviar.';
  }

  @override
  String batchUploadLegacyFormatsSkipped(Object count) {
    return '$count archivo(s) omitido(s) — formato antiguo no compatible. Convierta .doc a .docx, .ppt a .pptx, .xls a .xlsx e intente de nuevo.';
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
  String get batchUploadConfirmLangTitle => 'Confirmar idioma de destino';

  @override
  String batchUploadConfirmLangMessage(Object lang) {
    return 'El idioma de destino es \"$lang\". ¿Desea continuar?';
  }

  @override
  String get batchUploadConvert => 'Convertir';

  @override
  String get batchUploadTranslate => 'Traducir';

  @override
  String get batchUploadFolderPickerTitle =>
      'Seleccionar carpeta con archivos para traducir';

  @override
  String get batchUploadZipPickerTitle =>
      'Seleccionar archivo ZIP con archivos para traducir';

  @override
  String batchUploadScanFolderError(Object error) {
    return 'Error al escanear la carpeta: $error';
  }

  @override
  String batchUploadReadZipError(Object error) {
    return 'Error al leer el archivo ZIP: $error';
  }

  @override
  String get batchUploadGlossarySection => 'Glosario';

  @override
  String batchUploadGlossaryMore(Object count) {
    return '+$count';
  }

  @override
  String batchUploadGlossaryLoadError(Object error) {
    return 'Error: $error';
  }

  @override
  String get batchUploadNoGlossaries => 'No hay glosarios disponibles';

  @override
  String get batchUploadMineru => 'MinerU';

  @override
  String get batchUploadMineruLocal => 'MinerU Local';

  @override
  String get batchUploadPaddle => 'PaddleOCR';

  @override
  String get batchUploadPaddleLocal => 'PaddleOCR Local';

  @override
  String get commonClose => 'Cerrar';

  @override
  String get translationQueueTitle => 'Cola de tareas';

  @override
  String get translationQueueHint =>
      'Las tareas se actualizan automáticamente. Descargue cuando finalicen.';

  @override
  String get translationQueueCancelExitHint =>
      'Para tareas en cola o en ejecución, use Cancelar tarea; al confirmar, volverá al inicio.';

  @override
  String get translationQueueCancelDialogTitle =>
      '¿Cancelar esta tarea de traducción?';

  @override
  String get translationQueueCancelDialogMessage =>
      'Las tareas en cola se eliminan de la cola; las que están en ejecución se detienen. Al confirmar, volverá al inicio.';

  @override
  String get translationQueueCancelDialogKeep => 'Conservar';

  @override
  String get translationQueueCancelDialogConfirm => 'Cancelar tarea';

  @override
  String get translationQueueEmpty => 'Aún no hay tareas de traducción.';

  @override
  String get translationQueueNewQueuedTask => 'Tarea en cola';

  @override
  String get translationQueueImport => 'Importar';

  @override
  String get translationQueueBackToQueueTooltip => 'Volver a la cola de tareas';

  @override
  String get translationQueuedStarted =>
      'Tarea añadida a la cola. Consulte el progreso aquí.';

  @override
  String get translationQueueRefresh => 'Actualizar';

  @override
  String get translationQueueCancel => 'Cancelar tarea';

  @override
  String get translationQueueRelease => 'Quitar de la lista';

  @override
  String get translationQueueDownloads => 'Descargas';

  @override
  String get translationQueueDownloadMdEmbedded => 'MD (incrustado)';

  @override
  String get translationQueueDownloadMdZip => 'MD (ZIP)';

  @override
  String get translationQueueExecutionModeQueued => 'En cola';

  @override
  String get translationQueueExecutionModeImmediate => 'Inmediato';

  @override
  String get translationQueueTaskTypeTranslation => 'Traducción';

  @override
  String get translationQueueTaskTypeConversion => 'Conversión';

  @override
  String translationQueuePositionLabel(Object position) {
    return 'Posición en cola #$position';
  }

  @override
  String translationQueueLoadFailed(Object error) {
    return 'Error al cargar tareas: $error';
  }

  @override
  String translationQueueActionFailed(Object error) {
    return 'Error en la acción: $error';
  }

  @override
  String translationQueueSubmittedBy(Object user) {
    return 'Enviado por: $user';
  }

  @override
  String translationQueueStartedAt(Object time) {
    return 'Inicio: $time';
  }

  @override
  String translationQueueCompletedAt(Object time) {
    return 'Finalizado: $time';
  }

  @override
  String get translationQueueTimeUnknown => '—';

  @override
  String get translationQueueGuestUser => 'Invitado';

  @override
  String get translationQueueClearAllTooltip =>
      'Vaciar cola de tareas y caché del servidor (solo admin)';

  @override
  String get translationQueueClearAllButton => 'Vaciar cola';

  @override
  String get translationQueueClearAllTitle => 'Vaciar cola de tareas';

  @override
  String get translationQueueClearAllMessage =>
      'Cancela trabajos en cola y en curso, elimina tareas en memoria y instantáneas en disco. No se puede deshacer.';

  @override
  String get translationQueueClearAllConfirm => 'Vaciar';

  @override
  String get translationQueueClearAllCancel => 'Cancelar';

  @override
  String get translationQueueClearAllSuccess => 'Cola de tareas vaciada.';

  @override
  String translationQueueClearAllFailed(Object error) {
    return 'No se pudo vaciar la cola: $error';
  }

  @override
  String get translationQueueClearMyQueueTooltip => 'Vaciar mi cola';

  @override
  String get translationQueueClearMyQueueTitle => 'Vaciar mi cola';

  @override
  String get translationQueueClearMyQueueMessage =>
      '¿Eliminar todas tus tareas de la cola?';

  @override
  String get translationQueueClearMyQueueConfirm => 'Vaciar';

  @override
  String get translationQueueClearMyQueueCancel => 'Cancelar';

  @override
  String get translationQueueClearMyQueueSuccess => 'Mi cola ha sido vaciada.';

  @override
  String translationQueueClearMyQueueFailed(Object error) {
    return 'No se pudo vaciar tu cola: $error';
  }

  @override
  String get translationQueueErrorMessageCopied => 'Mensaje de error copiado';

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
  String get translationQueueView => 'Edición lectura';

  @override
  String get translationQueueViewSourcePath => 'Ver ruta original del archivo';

  @override
  String get translationQueueSourcePathTitle => 'Ruta del archivo fuente';

  @override
  String get translationQueueFileNameLabel => 'Nombre del archivo';

  @override
  String get translationQueueRelativePathLabel => 'Ruta relativa';

  @override
  String get homeFeatureUnderDevelopment =>
      'Esta característica está en desarrollo.';

  @override
  String homeAnonymizeNotSupportedVersion(Object version) {
    return 'Aún no compatible. Estará disponible en v$version.';
  }

  @override
  String get homeAnonymizeInDevelopment =>
      'La anonimización está en desarrollo y aún no está disponible.';

  @override
  String get homeScrollLeft => 'Desplazar a la izquierda';

  @override
  String get homeScrollRight => 'Desplazar a la derecha';

  @override
  String get homeTabHome => 'Inicio';

  @override
  String get homeToolbarAdBanner =>
      'Banner Publicitario de Barra de Herramientas\n(728×90 Leaderboard / 320×50 Móvil)';

  @override
  String get homeSteps => 'Pasos';

  @override
  String get homePhaseUpload => 'Subir';

  @override
  String get homePhaseExtract => 'Extraer';

  @override
  String get homePhaseGlossary => 'Glosario';

  @override
  String get homePhasePrompt => 'Prompt';

  @override
  String get homePhaseTranslate => 'Traducir';

  @override
  String get homePhaseViewer => 'Revisar';

  @override
  String get homePhaseAnonymize => 'Anonimizar';

  @override
  String get homePhaseDeAnonymize => 'Des-anonimizar';

  @override
  String get homePhaseExport => 'Exportar';

  @override
  String get taskDefaultTitleTranslate => 'Tarea';

  @override
  String get taskDefaultTitleAnonymize => 'Anonimización';

  @override
  String get homeReleaseNotesTitle => 'Notas de la Versión';

  @override
  String get homeReleaseNotesViewOnGitHub => 'Ver en GitHub';

  @override
  String get homeEditionEnterprise => 'Empresa';

  @override
  String get homeEditionEnterpriseStatusActivated => 'Activado';

  @override
  String get homeEditionActivateEnterprise => 'Activar Empresa';

  @override
  String get homeEditionPro => 'Pro';

  @override
  String get homeEditionStandard => 'Estándar';

  @override
  String get homeEditionStandardStatus => 'Siempre disponible';

  @override
  String homeEditionProStatusTrialRemaining(Object days) {
    return '$days días restantes';
  }

  @override
  String get homeEditionProStatusNotActivated => 'No activado';

  @override
  String get homeEditionProStatusActivated => 'Activado';

  @override
  String get homeWelcomeDearPro =>
      'Traducción inmersiva: contrasta el original y la traducción en la interfaz.\nTraducción en cola: encola documentos y ejecuta el flujo completo en orden.';

  @override
  String get homeWelcomeDearStandard =>
      'Traducción inmersiva: contrasta el original y la traducción en la interfaz.\nTraducción en cola: encola documentos y ejecuta el flujo completo en orden.';

  @override
  String get homeWelcomeDearProNoUser =>
      'Traducción inmersiva: contrasta el original y la traducción en la interfaz.\nTraducción en cola: encola documentos y ejecuta el flujo completo en orden.';

  @override
  String get homeWelcomeDearStandardNoUser =>
      'Traducción inmersiva: contrasta el original y la traducción en la interfaz.\nTraducción en cola: encola documentos y ejecuta el flujo completo en orden.';

  @override
  String get homeWelcomeHello =>
      'Traducción inmersiva: contrasta el original y la traducción en la interfaz.\nTraducción en cola: encola documentos y ejecuta el flujo completo en orden.';

  @override
  String get homeLoading => 'Cargando...';

  @override
  String get homeWelcomeGuest => '¡Bienvenido!';

  @override
  String homeFileNotFound(Object fileName) {
    return 'Archivo no encontrado: $fileName. Es posible que el archivo haya sido movido o eliminado.';
  }

  @override
  String homeFileSelectedMismatch(Object expected, Object selected) {
    return 'El nombre del archivo seleccionado no coincide: $selected. Esperado: $expected';
  }

  @override
  String homeFileLoaded(Object fileName) {
    return 'Archivo cargado: $fileName';
  }

  @override
  String get homeFileSelectionCancelled => 'Selección de archivo cancelada.';

  @override
  String homeFileLoadFailed(Object error) {
    return 'Error al cargar el archivo: $error';
  }

  @override
  String homeFlowCreateFailed(Object error) {
    return 'Error al crear el flujo: $error';
  }

  @override
  String commonPageNotFound(Object uri) {
    return 'Página no encontrada: $uri';
  }

  @override
  String get commonGoHome => 'Ir al Inicio';

  @override
  String get commonLogin => 'Iniciar sesión';

  @override
  String get commonLogout => 'Cerrar sesión';

  @override
  String get userMenuChangePassword => 'Cambiar contraseña';

  @override
  String get changePasswordCurrentPasswordLabel => 'Contraseña actual';

  @override
  String get changePasswordNewPasswordLabel => 'Nueva contraseña';

  @override
  String get changePasswordConfirmPasswordLabel => 'Confirmar nueva contraseña';

  @override
  String get changePasswordRequiredError =>
      'Se requieren la contraseña actual y la nueva contraseña.';

  @override
  String get changePasswordConfirmMismatchError =>
      'Las dos nuevas contraseñas no coinciden.';

  @override
  String get changePasswordSuccessMessage =>
      'Contraseña cambiada exitosamente.';

  @override
  String get changePasswordRequirementsTitle => 'Requisitos de la contraseña';

  @override
  String get changePasswordRequirementLength => '8–128 caracteres';

  @override
  String get changePasswordRequirementUppercase => 'Al menos 1 letra mayúscula';

  @override
  String get changePasswordRequirementLowercase => 'Al menos 1 letra minúscula';

  @override
  String get changePasswordRequirementDigit => 'Al menos 1 dígito';

  @override
  String get settingsTabsGeneral => 'General';

  @override
  String get settingsTabsAiPlatforms => 'Plataformas de IA';

  @override
  String get settingsTabsParsingEngine => 'Motor de Análisis';

  @override
  String get settingsParsingEngineTitle => 'Motor de Análisis';

  @override
  String get settingsParsingEngineSubtitle =>
      'Seleccione el motor de análisis de documentos para la extracción y procesamiento de texto.';

  @override
  String get settingsParsingEngineLabel => 'Motor de Análisis';

  @override
  String get settingsParsingEngineMineru => 'MinerU (Nube)';

  @override
  String get settingsParsingEngineMineruDesc =>
      'Análisis avanzado de documentos con soporte OCR';

  @override
  String get settingsParsingEngineMineruLocal => 'MinerU (Local)';

  @override
  String get settingsParsingEngineMineruLocalDesc =>
      'MinerU autoalojado; clave API opcional';

  @override
  String get settingsParsingEnginePaddle => 'PaddleOCR (Nube)';

  @override
  String get settingsParsingEnginePaddleDesc =>
      'OCR de alta precisión con análisis de diseño para títulos, tablas y fórmulas';

  @override
  String get settingsParsingEnginePaddleLocal => 'PaddleOCR (Local)';

  @override
  String get settingsParsingEnginePaddleLocalDesc =>
      'PaddleOCR autoalojado; requiere GPU NVIDIA (~8.5 GB VRAM)';

  @override
  String get settingsParsingEnginePdfplumber => 'PDFPlumber';

  @override
  String get settingsParsingEnginePdfplumberDesc =>
      'Extracción rápida de texto de PDF';

  @override
  String get settingsParsingEngineTesseract => 'Tesseract OCR';

  @override
  String get settingsParsingEngineTesseractDesc =>
      'Extracción de texto basada en OCR';

  @override
  String get settingsFormulaOcr => 'OCR de Fórmulas';

  @override
  String get settingsFormulaOcrSubtitle =>
      'Habilitar OCR para fórmulas matemáticas';

  @override
  String get settingsTableOcr => 'OCR de Tablas';

  @override
  String get settingsTableOcrSubtitle => 'Habilitar OCR para tablas';

  @override
  String get settingsMineruModelVersion => 'Versión del Modelo';

  @override
  String get settingsMineruModelVersionSubtitle =>
      'Seleccionar el modo de análisis de MinerU (pipeline para velocidad, vlm para precisión, hybrid para ambos)';

  @override
  String get settingsAnonymizationNewTaskNotice =>
      'Los cambios solo se aplican a tareas nuevas';

  @override
  String get settingsParsingEngineNewTaskNotice =>
      'Los cambios solo se aplican a tareas nuevas';

  @override
  String get settingsPaddleOcrModelLabel => 'Modelo PaddleOCR';

  @override
  String get settingsPaddleUseDocOrientationClassify =>
      'Detección Automática de Orientación';

  @override
  String get settingsPaddleUseDocOrientationClassifySubtitle =>
      'Detectar y corregir automáticamente la orientación del documento antes del OCR';

  @override
  String get settingsPaddleRestructurePages => 'Reestructurar Páginas';

  @override
  String get settingsPaddleRestructurePagesSubtitle =>
      'Reestructurar el diseño de página para mejor orden de lectura';

  @override
  String get settingsPdfSplitMaxPages => 'Páginas máximas por división PDF';

  @override
  String get settingsPdfSplitMaxWorkers =>
      'Trabajadores máximos para división PDF';

  @override
  String get settingsRequestRetryCount => 'Número de reintentos de solicitud';

  @override
  String get settingsOcrLanguageTitle => 'Idioma del OCR';

  @override
  String get settingsOcrLanguageSubtitle =>
      'Configure el idioma del OCR para el reconocimiento de texto en imágenes y documentos escaneados.';

  @override
  String get settingsOcrLanguageLabel => 'Idioma del OCR';

  @override
  String get settingsOcrLangEnglish => 'Inglés';

  @override
  String get settingsOcrLangChineseSimplified => 'Chino (Simplificado)';

  @override
  String get settingsOcrLangChineseTraditional => 'Chino (Tradicional)';

  @override
  String get settingsOcrLangJapanese => 'Japonés';

  @override
  String get settingsOcrLangKorean => 'Coreano';

  @override
  String get settingsOcrLangFrench => 'Francés';

  @override
  String get settingsOcrLangGerman => 'Alemán';

  @override
  String get settingsOcrLangSpanish => 'Español';

  @override
  String get settingsOcrLangRussian => 'Ruso';

  @override
  String get settingsOcrLangArabic => 'Árabe';

  @override
  String get settingsOcrLangAuto => 'Auto detectar';

  @override
  String get mineruLangAuto => 'Auto detectar';

  @override
  String get mineruLangChServer => 'Chino (Servidor)';

  @override
  String get mineruLangChLite => 'Chino (Ligero)';

  @override
  String get mineruLangTamil => 'Tamil';

  @override
  String get mineruLangTelugu => 'Telugu';

  @override
  String get mineruLangKannada => 'Canarés';

  @override
  String get mineruLangLatinScript => 'Escritura Latina';

  @override
  String get mineruLangArabicScript => 'Escritura Árabe';

  @override
  String get mineruLangEastSlavic => 'Eslavo Oriental';

  @override
  String get mineruLangCyrillicScript => 'Escritura Cirílica';

  @override
  String get mineruLangDevanagariScript => 'Escritura Devanagari';

  @override
  String get settingsTabsGlossary => 'Glosario';

  @override
  String get settingsGlossaryManagementTitle => 'Gestión de Glosarios';

  @override
  String get settingsGlossaryManagementSubtitle =>
      'Administre sus entradas de terminología para una calidad de traducción consistente.';

  @override
  String get settingsGlossarySelectGlossary => 'Seleccionar Glosario';

  @override
  String get settingsGlossaryCreateGlossary => 'Crear';

  @override
  String get settingsGlossaryImportCsv => 'Importar';

  @override
  String get settingsGlossaryExport => 'Exportar';

  @override
  String get settingsGlossaryExportAll => 'Exportar Todo';

  @override
  String get settingsGlossaryDeleteGlossary => 'Eliminar';

  @override
  String get settingsGlossarySaveZip => 'Guardar ZIP';

  @override
  String settingsGlossaryEntriesTitle(Object count) {
    return 'Entradas del Glosario ($count)';
  }

  @override
  String get settingsGlossaryAddEntry => 'Agregar Entrada';

  @override
  String get settingsGlossaryNoEntriesYet =>
      'Aún no hay entradas en el glosario.\nAgregue su primera entrada para comenzar.';

  @override
  String get settingsGlossaryFilterLabel => 'Filtrar:';

  @override
  String get settingsGlossaryFilterAll => 'Todo';

  @override
  String get settingsGlossaryFilterUncategorized => 'Sin categoría';

  @override
  String get settingsGlossaryTableSource => 'Origen';

  @override
  String get settingsGlossaryTableTarget => 'Destino';

  @override
  String get settingsGlossaryTableCategory => 'Categoría (Opcional)';

  @override
  String get settingsGlossaryTableTargetLang => 'Idioma de Destino';

  @override
  String get settingsGlossaryCategoryHint => 'Categoría';

  @override
  String get settingsGlossaryUncategorizedDisplay => '(Sin categoría)';

  @override
  String get settingsGlossaryCopyAction => 'Copiar';

  @override
  String get settingsGlossaryCopiedToClipboard => 'Copiado al portapapeles';

  @override
  String get settingsGlossaryDeleteDialogTitle => 'Eliminar Glosario';

  @override
  String settingsGlossaryDeleteDialogMessage(Object id) {
    return '¿Está seguro de eliminar este glosario?\nID: $id';
  }

  @override
  String get settingsGlossaryCancel => 'Cancelar';

  @override
  String get settingsGlossaryDelete => 'Eliminar';

  @override
  String get settingsGlossaryCreateDialogTitle => 'Crear Glosario';

  @override
  String get settingsGlossaryNameLabel => 'Nombre';

  @override
  String get settingsGlossaryDescriptionLabel => 'Descripción (opcional)';

  @override
  String get settingsGlossaryGlobalGlossary => 'Glosario Global';

  @override
  String get settingsGlossaryGlobalGlossarySubtitle =>
      'Si está desactivado, será su glosario personal';

  @override
  String get settingsGlossaryCreate => 'Crear';

  @override
  String get settingsGlossaryNameRequired => 'El nombre es obligatorio';

  @override
  String settingsGlossaryCreatedSnack(Object name) {
    return 'Creado: $name';
  }

  @override
  String settingsGlossaryCreateFailedSnack(Object error) {
    return 'Error al crear: $error';
  }

  @override
  String get settingsGlossaryAddEntryDialogTitle =>
      'Agregar Entrada al Glosario';

  @override
  String get settingsGlossarySourceTextLabel => 'Texto de Origen';

  @override
  String get settingsGlossaryTargetTextLabel => 'Texto de Destino';

  @override
  String get settingsGlossaryCategoryOptionalLabel => 'Categoría (opcional)';

  @override
  String get settingsGlossaryCategoryOptionalHint =>
      'Dejar vacío para no clasificar';

  @override
  String get settingsGlossaryAdd => 'Agregar';

  @override
  String get settingsGlossarySourceTargetRequired =>
      'El texto de origen y el texto de destino son obligatorios';

  @override
  String get settingsGlossaryEntryAddedSnack => 'Entrada agregada';

  @override
  String settingsGlossaryAddFailedSnack(Object error) {
    return 'Error: $error';
  }

  @override
  String get settingsGlossaryImportDialogTitle =>
      'Importar CSV/TBX al Glosario';

  @override
  String get settingsGlossaryMergeModeLabel => 'Modo de Fusión';

  @override
  String get settingsGlossaryMergeUpdate => 'Actualizar (Upsert)';

  @override
  String get settingsGlossaryMergeAppend => 'Anexar (Solo Nuevos)';

  @override
  String get settingsGlossaryMergeReplace => 'Reemplazar (Sobrescribir Todo)';

  @override
  String get settingsGlossaryImport => 'Importar';

  @override
  String get settingsGlossaryUnableToReadFile => 'No se puede leer el archivo';

  @override
  String settingsGlossaryImportedSnack(Object count) {
    return 'Importado: $count elementos';
  }

  @override
  String settingsGlossaryImportFailedSnack(Object error) {
    return 'Error: $error';
  }

  @override
  String get settingsGlossaryExportDialogTitle => 'Exportar Glosario';

  @override
  String get settingsGlossarySaveCsv => 'Guardar CSV/TBX';

  @override
  String get settingsGlossaryDownload => 'Descargar';

  @override
  String settingsGlossaryDownloadedSnack(Object info) {
    return 'Descargado: $info';
  }

  @override
  String settingsGlossaryExportFailedSnack(Object error) {
    return 'Error: $error';
  }

  @override
  String settingsGlossaryLoadedSnack(Object count) {
    return 'Cargadas $count entradas';
  }

  @override
  String settingsGlossaryLoadFailedSnack(Object error) {
    return 'Error al cargar: $error';
  }

  @override
  String settingsGlossaryDeletedSnack(Object id) {
    return 'Glosario eliminado: $id';
  }

  @override
  String settingsGlossaryDeleteFailedSnack(Object error) {
    return 'Error al eliminar: $error';
  }

  @override
  String settingsGlossaryExportAllFailedSnack(Object error) {
    return 'Error al exportar todo: $error';
  }

  @override
  String get settingsGlossaryEntryUpdatedSnack => 'Entrada actualizada';

  @override
  String settingsGlossaryUpdateFailedSnack(Object error) {
    return 'Error al actualizar: $error';
  }

  @override
  String get settingsGlossaryEntryDeletedSnack => 'Entrada eliminada';

  @override
  String settingsGlossaryDeleteEntryFailedSnack(Object error) {
    return 'Error al eliminar: $error';
  }

  @override
  String settingsGlossaryGlossaryDropdownItem(
      Object count, Object name, Object type) {
    return '$name ($type) · $count elementos';
  }

  @override
  String settingsGlossaryErrorPrefix(Object error) {
    return 'Error: $error';
  }

  @override
  String settingsGlossaryExportedAllSnack(Object info) {
    return 'Exportado: $info';
  }

  @override
  String settingsGlossaryEntryCount(Object count) {
    return 'Cantidad de entradas: $count';
  }

  @override
  String get settingsGlossaryEdit => 'Editar';

  @override
  String get settingsGlossaryConfirmDeleteEntryTitle => 'Confirmar Eliminación';

  @override
  String settingsGlossaryConfirmDeleteEntryMessage(Object source) {
    return '¿Eliminar la entrada \"$source\"?';
  }

  @override
  String get settingsGlossaryEditEntryDialogTitle => 'Editar Entrada';

  @override
  String get settingsGlossaryUpdate => 'Actualizar';

  @override
  String get settingsGlossaryEntryDeleteFailedSnack =>
      'Error al eliminar la entrada';

  @override
  String get settingsGlossaryEmptyStateTitle =>
      'Aún no hay glosarios. Crea tu primer glosario para comenzar.';

  @override
  String get settingsGlossaryTooltipCreate => 'Crear un nuevo glosario';

  @override
  String get settingsGlossaryTooltipImport =>
      'Importar entradas desde formato CSV o TBX';

  @override
  String get settingsGlossaryTooltipExport =>
      'Exportar glosario seleccionado a formato CSV o TBX';

  @override
  String get settingsGlossaryTooltipExportAll =>
      'Exportar todos los glosarios como archivo ZIP';

  @override
  String get settingsGlossaryTooltipDeleteGlossary =>
      'Eliminar permanentemente el glosario seleccionado';

  @override
  String get settingsGlossaryExportTemplate => 'Exportar plantilla';

  @override
  String get settingsGlossaryTooltipExportTemplate =>
      'Descargar plantilla CSV con encabezado y una fila de ejemplo';

  @override
  String get settingsGlossarySaveTemplateCsv =>
      'Guardar plantilla CSV del glosario';

  @override
  String get settingsGlossaryTemplateExportedSnack =>
      'Plantilla del glosario descargada';

  @override
  String get settingsGlossaryTooltipFormatHelp =>
      'Ver requisitos del formato de archivo del glosario';

  @override
  String get settingsGlossaryFormatHelpTitle =>
      'Formato de archivo del glosario';

  @override
  String get settingsGlossaryFormatHelpContent =>
      'Formato CSV (recomendado para edición masiva):\n\nCodificación: UTF-8 (se recomienda UTF-8 con BOM)\n\nColumnas:\n• src — texto de origen (obligatorio)\n• dst — texto traducido (obligatorio)\n• category — etiqueta de grupo (opcional)\n• target_lang — código de idioma destino (opcional, ver lista abajo)\n\nReglas:\n• La fila de encabezado debe incluir src y dst\n• Las filas con src o dst vacíos se omiten al importar\n• También se admite importación en formato TBX\n\nUse \"Exportar plantilla\" para descargar un CSV de ejemplo con una fila.';

  @override
  String get settingsGlossaryFormatHelpTargetLangListTitle =>
      'Valores disponibles de target_lang:';

  @override
  String get settingsGlossaryBatchEditCategory => 'Editar categoría';

  @override
  String get settingsGlossaryBatchDelete => 'Eliminar';

  @override
  String get settingsGlossaryBatchDeselect => 'Deseleccionar';

  @override
  String settingsGlossaryBatchSelectedCount(Object count) {
    return '$count seleccionados';
  }

  @override
  String get settingsGlossaryExportFormatLabel => 'Formato de exportación';

  @override
  String get settingsGlossaryExportFormatCsv => 'CSV';

  @override
  String get settingsGlossaryExportFormatTbx => 'TBX (TermBase eXchange)';

  @override
  String get settingsGlossaryExportSourceLanguage => 'Idioma de origen';

  @override
  String get settingsGlossaryExportSaveTbxTitle => 'Guardar archivo TBX';

  @override
  String get settingsGlossaryDeleteEntriesTitle => 'Eliminar entradas';

  @override
  String settingsGlossaryDeleteEntriesBody(Object count) {
    return '¿Eliminar $count entradas seleccionadas? Esta acción no se puede deshacer.';
  }

  @override
  String get settingsGlossaryDeleteEntriesConfirm => 'Eliminar';

  @override
  String get settingsGlossaryEditCategoryTitle => 'Editar Categoría';

  @override
  String settingsGlossaryEditCategoryBody(Object count) {
    return 'Establecer categoría para $count entradas seleccionadas:';
  }

  @override
  String get settingsGlossaryEditCategoryLabel => 'Categoría';

  @override
  String get settingsGlossaryEditCategoryHint =>
      'Ingrese nombre de la categoría';

  @override
  String get settingsGlossaryEditCategoryApply => 'Aplicar';

  @override
  String get glossaryPanelSaveNameHint =>
      'Ingrese nombre o seleccione existente...';

  @override
  String get glossaryPanelClearSelection => 'Limpiar selección';

  @override
  String get glossaryPanelListTitle => 'Glosario';

  @override
  String get glossaryPanelNoEntries => 'Sin entradas';

  @override
  String get glossaryPanelOneEntry => '1 entrada';

  @override
  String glossaryPanelEntriesCount(Object count) {
    return '$count entradas';
  }

  @override
  String get glossaryPanelProcessing => 'Procesando...';

  @override
  String get glossaryPanelDropCsvHere => 'Suelte el archivo CSV o TBX aquí';

  @override
  String get glossaryPanelNoEntriesHint =>
      'No hay entradas en el glosario.\nHaga clic en el botón Detectar Glosario para comenzar.\nO seleccione un glosario de la lista para ver sus entradas.\nO arrastre y suelte un archivo CSV o TBX aquí.';

  @override
  String get glossaryPanelSelectBody => 'Seleccione un glosario para trabajar:';

  @override
  String get glossaryPanelSaveDialogTitleReplace => 'Reemplazar Glosario';

  @override
  String get glossaryPanelSaveDialogTitleSave => 'Guardar Glosario';

  @override
  String glossaryPanelSaveReplaceInfo(Object name) {
    return 'Esto reemplazará el glosario existente \"$name\"';
  }

  @override
  String get glossaryPanelSaveButtonSaveAs => 'Guardar como';

  @override
  String get glossaryPanelGenerating => 'Generando glosario...';

  @override
  String get glossaryPanelDeleteEntry => 'Eliminar entrada';

  @override
  String get glossaryPanelInvertSelection => 'Invertir selección';

  @override
  String get glossaryWidgetTitle => 'Glosario';

  @override
  String get glossaryWidgetRefreshTooltip => 'Actualizar lista de glosarios';

  @override
  String glossaryWidgetGlossariesSelected(Object count) {
    return '$count glosario seleccionado';
  }

  @override
  String glossaryWidgetGlossariesSelectedPlural(Object count) {
    return '$count glosarios seleccionados';
  }

  @override
  String get glossaryWidgetSelectGlossaries => 'Seleccionar Glosarios';

  @override
  String glossaryWidgetLoadFailed(Object error) {
    return 'Error al cargar glosarios: $error';
  }

  @override
  String get glossaryWidgetNoGlossariesHint =>
      'No hay glosarios disponibles. Cree uno en Configuración -> Glosario';

  @override
  String glossaryWidgetTypeCountItems(Object type, Object count) {
    return '$type · $count elementos';
  }

  @override
  String glossaryWidgetTermsExtracted(Object count) {
    return '$count términos extraídos de la traducción';
  }

  @override
  String glossaryWidgetPersonalCreated(Object count) {
    return '¡Glosario personal creado exitosamente!\nSe agregaron $count términos.';
  }

  @override
  String glossaryWidgetPersonalReplaced(Object total) {
    return '¡Glosario personal reemplazado exitosamente!\nTotal de términos: $total';
  }

  @override
  String glossaryWidgetPersonalAppended(
      Object newCount, Object skipped, Object total) {
    return 'Se agregaron $newCount términos nuevos al glosario personal.\nSe omitieron $skipped términos existentes.\nTotal de términos: $total';
  }

  @override
  String glossaryWidgetPersonalUpdated(
      Object newCount, Object updatedCount, Object total) {
    return '¡Glosario personal actualizado exitosamente!\nSe agregaron $newCount términos nuevos, se actualizaron $updatedCount términos existentes.\nTotal de términos: $total';
  }

  @override
  String glossaryWidgetAddToPersonalFailed(Object error) {
    return 'Error al agregar al glosario personal: $error';
  }

  @override
  String get settingsTabsTranslation => 'Traducción';

  @override
  String get settingsTabsAnonymization => 'Anonimización';

  @override
  String get settingsTabsUserManagement => 'Gestión de Usuarios';

  @override
  String get settingsUserManagementTitle => 'Modo de Gestión de Usuarios';

  @override
  String get settingsUserManagementSubtitle =>
      'Elija la política de inicio de sesión y permisos para el despliegue web. Configuración y Asistente de Configuración son solo para administradores.';

  @override
  String get settingsUserManagementModeNoLogin =>
      'No se requiere inicio de sesión';

  @override
  String get settingsUserManagementModeNoLoginDesc =>
      'Usar sin iniciar sesión; Configuración y Asistente de Configuración disponibles solo después del inicio de sesión del administrador.';

  @override
  String get settingsUserManagementModeLdap => 'Inicio de sesión LDAP';

  @override
  String get settingsUserManagementModeLdapDesc =>
      'Iniciar sesión con LDAP/AD; Configuración y Asistente de Configuración solo para administrador (grupo de dominio).';

  @override
  String get settingsUserManagementModeLocal =>
      'Inicio de sesión de usuario local';

  @override
  String get settingsUserManagementModeLocalDesc =>
      'Autenticar contra la lista de usuarios locales en el servidor.';

  @override
  String get settingsUserManagementInDevelopment => 'En desarrollo';

  @override
  String get settingsUserManagementSaveSuccess =>
      'Modo de gestión de usuarios guardado';

  @override
  String settingsUserManagementSaveFailed(Object message) {
    return 'Error al guardar: $message';
  }

  @override
  String get settingsLocalUsersTitle => 'Usuarios locales';

  @override
  String get settingsLocalUsersAddUser => 'Agregar usuario';

  @override
  String get settingsLocalUsersNoUsers => 'No se encontraron usuarios locales.';

  @override
  String get settingsLocalUsersDialogAddTitle => 'Agregar usuario local';

  @override
  String get settingsLocalUsersDialogEditTitle => 'Editar usuario local';

  @override
  String get settingsLocalUsersFieldUsername => 'Nombre de usuario';

  @override
  String get settingsLocalUsersFieldDisplayName =>
      'Nombre para mostrar (opcional)';

  @override
  String get settingsLocalUsersFieldEmail => 'Correo electrónico (opcional)';

  @override
  String get settingsLocalUsersFieldRole => 'Rol';

  @override
  String get settingsLocalUsersRoleUser => 'Usuario';

  @override
  String get settingsLocalUsersRoleAdmin => 'Administrador';

  @override
  String get settingsLocalUsersFieldPassword => 'Contraseña';

  @override
  String get settingsLocalUsersPasswordHelper =>
      '8-128 caracteres, mayúscula, minúscula, dígito';

  @override
  String get settingsLocalUsersValidationUsernameRequired =>
      'Se requiere nombre de usuario';

  @override
  String get settingsLocalUsersValidationPasswordRequired =>
      'Se requiere contraseña';

  @override
  String get settingsLocalUsersValidationPasswordTooShort =>
      'La contraseña debe tener al menos 8 caracteres';

  @override
  String get settingsLocalUsersValidationPasswordTooLong =>
      'La contraseña debe tener como máximo 128 caracteres';

  @override
  String get settingsLocalUsersValidationPasswordComplexity =>
      'La contraseña debe contener mayúsculas, minúsculas y dígitos';

  @override
  String get settingsLocalUsersOperationFailed => 'Operación fallida';

  @override
  String get settingsLocalUsersResetPassword => 'Restablecer contraseña';

  @override
  String settingsLocalUsersResetPasswordTitle(Object username) {
    return 'Restablecer contraseña: $username';
  }

  @override
  String get settingsLocalUsersFieldNewPassword => 'Nueva contraseña';

  @override
  String get settingsLocalUsersPasswordResetSuccess =>
      'Contraseña restablecida con éxito';

  @override
  String get settingsLocalUsersPasswordResetFailed =>
      'Error al restablecer la contraseña';

  @override
  String get settingsLocalUsersDeleteUser => 'Eliminar';

  @override
  String settingsLocalUsersDeleteUserTitle(Object username) {
    return 'Eliminar usuario: $username';
  }

  @override
  String get settingsLocalUsersDeleteConfirmation =>
      'Esta acción eliminará permanentemente al usuario del almacén local de usuarios. Esto no se puede deshacer.';

  @override
  String get settingsLocalUsersDeleteSuccess => 'Usuario eliminado';

  @override
  String get settingsLocalUsersDeleteFailed => 'Error al eliminar usuario';

  @override
  String get settingsLocalUsersEdit => 'Editar';

  @override
  String get settingsLocalUsersCancel => 'Cancelar';

  @override
  String get settingsLocalUsersSave => 'Guardar';

  @override
  String get settingsLocalUsersConfirm => 'Confirmar';

  @override
  String get settingsLocalUsersTableUsername => 'Nombre de usuario';

  @override
  String get settingsLocalUsersTableDisplayName => 'Nombre para mostrar';

  @override
  String get settingsLocalUsersTableEmail => 'Correo electrónico';

  @override
  String get settingsLocalUsersTableRole => 'Rol';

  @override
  String get settingsLdapEnabled => 'Habilitar inicio de sesión LDAP';

  @override
  String get settingsLdapEnableHint =>
      'Pruebe la conexión LDAP primero antes de habilitar.';

  @override
  String get settingsLdapProtocol => 'Protocolo';

  @override
  String get settingsLdapProtocolLdap => 'LDAP';

  @override
  String get settingsLdapProtocolLdaps => 'LDAPS';

  @override
  String get settingsLdapHost =>
      'Servidor LDAP (coincidir CN/SAN del certificado)';

  @override
  String get settingsLdapHostPlaceholder => 'ad.ejemplo.com o 192.168.x.x';

  @override
  String get settingsLdapPort => 'Puerto';

  @override
  String get settingsLdapPortPlaceholder => '389';

  @override
  String get settingsLdapBaseDn => 'DN Base de búsqueda de usuarios';

  @override
  String get settingsLdapBaseDnPlaceholder => 'OU=Usuarios,DC=ejemplo,DC=com';

  @override
  String get settingsLdapBindDnTemplate => 'Plantilla de DN de enlace';

  @override
  String settingsLdapBindDnPlaceholder(Object username) {
    return 'EJEMPLO\\$username o $username@ejemplo.com';
  }

  @override
  String get settingsLdapUserFilter => 'Filtro de usuario';

  @override
  String settingsLdapUserFilterPlaceholder(Object username) {
    return '(sAMAccountName=$username)';
  }

  @override
  String get settingsLdapAdminGroupEnabled =>
      'Habilitar consulta de grupo de administradores';

  @override
  String get settingsLdapAdminGroup => 'Nombre del grupo de administradores';

  @override
  String get settingsLdapAdminGroupPlaceholder => 'Owlangs-Admins';

  @override
  String get settingsLdapGroupBaseDn => 'DN Base de búsqueda de grupos';

  @override
  String get settingsLdapGroupBaseDnPlaceholder =>
      'OU=Grupos,DC=ejemplo,DC=com';

  @override
  String get settingsLdapTlsVerify => 'Verificar certificado TLS';

  @override
  String get settingsLdapTlsCacertfile =>
      'Ruta del archivo del certificado CA de TLS';

  @override
  String get settingsLdapTlsCacertfilePlaceholder => '/ruta/a/ca.crt';

  @override
  String get settingsLdapTestConnection => 'Probar conexión LDAP';

  @override
  String get settingsLdapSaveConfig => 'Guardar configuración LDAP';

  @override
  String get settingsLdapTestDialogTitle => 'Probar conexión LDAP';

  @override
  String get settingsLdapTestUsername => 'Nombre de usuario (sin dominio)';

  @override
  String get settingsLdapTestUsernamePlaceholder => 'usuarioprueba';

  @override
  String get settingsLdapTestPassword => 'Contraseña';

  @override
  String get settingsLdapTestPasswordPlaceholder => '********';

  @override
  String get settingsLdapTestStart => 'Iniciar prueba';

  @override
  String get settingsLdapTestSuccess =>
      'Prueba de conexión LDAP exitosa. Ahora puede habilitar LDAP.';

  @override
  String get settingsLdapTestFailed => 'Prueba de conexión LDAP fallida';

  @override
  String get settingsLdapConfigSaved => 'Configuración LDAP guardada';

  @override
  String get settingsLdapEnableRequireTest =>
      'Por favor, pruebe la conexión LDAP primero antes de habilitar LDAP.';

  @override
  String get settingsAdminOnlyDialogTitle => 'Solo Administrador';

  @override
  String get settingsAdminOnlyDialogMessage =>
      'Configuración y Asistente de Configuración están disponibles solo para administradores. Por favor, inicie sesión con una cuenta de administrador para continuar.';

  @override
  String get settingsAdminOnlyDialogGoToLogin => 'Ir a Iniciar Sesión';

  @override
  String get settingsAdminOnlyDialogClose => 'Cerrar';

  @override
  String get aiPlatformOverview => 'Resumen de Plataformas';

  @override
  String aiPlatformConfiguredCount(Object configured, Object total) {
    return 'Configuradas $configured/$total plataformas';
  }

  @override
  String get aiPlatformTestApiStatus => 'Probar Estado de la API';

  @override
  String get aiPlatformTesting => 'Probando...';

  @override
  String get aiPlatformCategoryLanguageModels => 'Modelos de Lenguaje';

  @override
  String get aiPlatformCategoryParsingEngines => 'Motores de Análisis';

  @override
  String aiPlatformConfiguredDragReorder(Object configured, Object total) {
    return 'Configuradas $configured/$total plataformas (arrastrar para reordenar)';
  }

  @override
  String get aiPlatformNotConfigured => 'No configurado';

  @override
  String get aiPlatformNotTested => 'No probado';

  @override
  String get aiPlatformApiAvailable => 'API disponible';

  @override
  String get aiPlatformAvailable => 'Disponible';

  @override
  String get aiPlatformUnavailable => 'No disponible';

  @override
  String get aiPlatformConfigure => 'Configurar';

  @override
  String aiPlatformConfigureTitle(Object name) {
    return 'Configurar $name';
  }

  @override
  String get aiPlatformBasicInformation => 'Información Básica';

  @override
  String get aiPlatformPlatformName => 'Nombre de la Plataforma';

  @override
  String get aiPlatformPlatformNameHint =>
      'ej., Doubao (DeepSeek / Volcano Ark)';

  @override
  String get aiPlatformApiUrl => 'URL de la API';

  @override
  String get aiPlatformApiUrlHint =>
      'ej., https://ark.cn-beijing.volces.com/api/v3';

  @override
  String get aiPlatformMaxTokens => 'Tokens Máximos';

  @override
  String get aiPlatformMaxTokensHint => 'ej., 4096';

  @override
  String get aiPlatformChunkSize => 'Tamaño de Fragmento';

  @override
  String get aiPlatformChunkSizeHint => 'ej., 3000';

  @override
  String get aiPlatformConcurrent => 'Solicitudes Concurrentes';

  @override
  String get aiPlatformConcurrentHint => 'ej., 5';

  @override
  String get aiPlatformModel => 'Modelo';

  @override
  String get aiPlatformModelHint => 'ej., deepseek-v3 / llama3.1-70b';

  @override
  String get aiPlatformApiKey => 'Clave de la API';

  @override
  String get aiPlatformApiConfiguration => 'Configuración de la API';

  @override
  String get aiPlatformGetApiKey => 'Obtener Clave de la API';

  @override
  String get aiPlatformCancel => 'Cancelar';

  @override
  String get aiPlatformTestConnection => 'Probar Conexión';

  @override
  String get aiPlatformTestConnectionHint =>
      'Después de actualizar la configuración, haga clic en \"Probar Conexión\" a continuación para verificar que la plataforma esté disponible.';

  @override
  String get setupWizardConfigureApiKeyAndTest =>
      'Conexión no disponible. Por favor, configure la Clave de la API y haga clic en \"Probar Conexión\" para verificar.';

  @override
  String get setupWizardSaveAndExit => 'Guardar y salir';

  @override
  String get setupWizardTitle => 'Asistente de Configuración';

  @override
  String get setupWizardStepWelcome => 'Bienvenido';

  @override
  String get setupWizardStepMineru => 'PDF / MinerU';

  @override
  String get setupWizardWelcomeIntro =>
      'Este asistente le ayudará a completar dos configuraciones clave:';

  @override
  String get setupWizardWelcomeBody =>
      '1. Seleccionar y configurar su plataforma LLM principal.\n2. Si necesita traducir PDF/PNG, etc., configurar el motor de análisis MinerU (opcional).\n\nNota: Después de configurar, use \"Probar Conexión\" para verificar.';

  @override
  String get setupWizardUiLanguageLabel => 'Idioma de la Interfaz';

  @override
  String get setupWizardMineruDescription =>
      'MinerU maneja el análisis de diseño y segmentación para PDF / imágenes.\nIngrese la Clave de la API y la URL de MinerU a continuación, luego haga clic en \"Probar Conexión\" para verificar.';

  @override
  String get setupWizardMineruConfigTitle => 'MinerU (motor de análisis)';

  @override
  String get setupWizardSelectMineruPlatform => 'Seleccionar Plataforma MinerU';

  @override
  String get setupWizardMineruCloudOption =>
      'MinerU (Nube) - Servicio en la nube oficial';

  @override
  String get setupWizardMineruLocalOption =>
      'MinerU (Local) - Despliegue autoalojado';

  @override
  String get setupWizardSelectLlmPlatform => 'Seleccionar plataforma LLM';

  @override
  String get setupWizardNoLlmPlatforms =>
      'No hay plataformas LLM en la Configuración de la Plataforma de IA. Agrega una plataforma primero en Configuración.';

  @override
  String get setupWizardMineruSaved => 'Configuración de MinerU guardada';

  @override
  String get setupWizardPrevStep => 'Anterior';

  @override
  String get setupWizardNextStep => 'Siguiente';

  @override
  String get aiPlatformSave => 'Guardar';

  @override
  String get aiPlatformList => 'Lista';

  @override
  String get aiPlatformTemperature => 'Temperatura';

  @override
  String get aiPlatformThinkingMode => 'Modo de Pensamiento';

  @override
  String get aiPlatformThinkingDisable => 'Deshabilitar (Recomendado)';

  @override
  String get aiPlatformThinkingEnable => 'Habilitar';

  @override
  String get aiPlatformThinkingDefault => 'Predeterminado';

  @override
  String get aiPlatformThinkingHint =>
      'Habilita el proceso de razonamiento de IA para una mejor calidad de traducción';

  @override
  String get aiPlatformThinkingModeSupported => 'Soportar Modo de Pensamiento';

  @override
  String get aiPlatformThinkingModeSupportedHint =>
      'Habilite esto si la plataforma soporta modo de pensamiento (ej., Ollama con Qwen3)';

  @override
  String get aiPlatformSegmentLimitLabel => 'Límite de Segmentos';

  @override
  String get aiPlatformSegmentLimitHint =>
      'Máximo de segmentos por lote de traducción. Se aplica junto con chunk_size. 0 = ilimitado (nube), 10 = recomendado para LLMs locales';

  @override
  String get aiPlatformSegmentLimitUnlimited => 'Ilimitado';

  @override
  String get aiPlatformPleaseEnterApiKeyFirst =>
      'Por favor, ingresa primero una clave API';

  @override
  String get aiPlatformPleaseEnterApiUrlFirst =>
      'Por favor, ingresa primero la URL de la API';

  @override
  String get aiPlatformHasApiKey => 'Requiere Clave API';

  @override
  String get aiPlatformHasApiKeyHint =>
      'Desmarcar para implementaciones locales sin autenticación API';

  @override
  String get aiPlatformApiKeyOptionalHint => 'Dejar vacío si no es requerido';

  @override
  String get optional => 'opcional';

  @override
  String get aiPlatformConnectionTestSucceeded => 'Prueba de conexión exitosa';

  @override
  String mineruConnectionSuccessWithVersion(String version) {
    return 'Prueba de conexión exitosa. Versión de MinerU: $version';
  }

  @override
  String mineruConnectionSuccessWithApiVersion(String version) {
    return 'Prueba de conexión exitosa. MinerU API $version';
  }

  @override
  String mineruConnectionSuccessWithModelVersion(String modelVersion) {
    return 'Prueba de conexión exitosa. Motor MinerU: $modelVersion';
  }

  @override
  String mineruConnectionSuccessCloudWithApi(String apiVersion) {
    return 'Prueba de conexión exitosa. MinerU en la nube (API $apiVersion; la API en la nube no expone la versión del servidor)';
  }

  @override
  String aiPlatformConnectionTestFailed(Object message) {
    return 'Prueba de conexión fallida: $message';
  }

  @override
  String get aiPlatformNoModelsFound => 'No se encontraron modelos';

  @override
  String get aiPlatformFailedToLoadModels => 'Error al cargar modelos';

  @override
  String aiPlatformErrorLoadingModels(Object error) {
    return 'Error al cargar modelos: $error';
  }

  @override
  String get aiPlatformSelectModel => 'Seleccionar Modelo';

  @override
  String get aiPlatformNoModelsAvailable => 'No hay modelos disponibles';

  @override
  String get aiPlatformMineruSettings => 'Configuración de MinerU';

  @override
  String get aiPlatformEnterMineruApiKey => 'Ingresa la Clave API de MinerU';

  @override
  String get aiPlatformGetMineruApiKey => 'Obtener Clave API de MinerU';

  @override
  String get aiPlatformModelVersion => 'Versión del Modelo';

  @override
  String get aiPlatformModelVersionHint => 'hybrid-auto-engine';

  @override
  String get aiPlatformTimeout => 'Timeout de lectura (segundos)';

  @override
  String get aiPlatformTimeoutHint =>
      '200 (nube) o 300 (local). Tiempo máximo de espera para respuesta LLM.';

  @override
  String get aiPlatformWriteTimeout => 'Timeout de escritura (segundos)';

  @override
  String get aiPlatformWriteTimeoutHint =>
      '300 (predeterminado). Tiempo máximo de espera para enviar datos al LLM.';

  @override
  String get aiPlatformTestConnectTimeout =>
      'Timeout de prueba de conexión (segundos)';

  @override
  String get aiPlatformTestConnectTimeoutHint =>
      '30 (predeterminado). Tiempo máximo de espera para la prueba de conectividad antes de iniciar la traducción.';

  @override
  String get aiPlatformTestRequestTimeout =>
      'Timeout de solicitud de prueba (segundos)';

  @override
  String get aiPlatformTestRequestTimeoutHint =>
      '10 (predeterminado). Tiempo máximo de espera para cada solicitud de prueba durante la prueba de conectividad.';

  @override
  String get aiPlatformMineruApiUrlHint => 'https://mineru.net/api/v4';

  @override
  String get aiPlatformOcrSettings => 'Configuración de OCR';

  @override
  String get aiPlatformFormulaOcr => 'OCR de Fórmulas';

  @override
  String get aiPlatformFormulaOcrSubtitle =>
      'Habilitar OCR para fórmulas matemáticas';

  @override
  String get aiPlatformTableOcr => 'OCR de Tablas';

  @override
  String get aiPlatformTableOcrSubtitle => 'Habilitar OCR para tablas';

  @override
  String get settingsFontEditSizeTitle => 'Editar Tamaño de Fuente';

  @override
  String get settingsFontEditSizeSubtitle =>
      'Tamaño de fuente al editar segmentos traducidos';

  @override
  String get settingsTranslationTitle => 'Configuración de Traducción';

  @override
  String get settingsTranslationNotice =>
      'Estos ajustes se aplicarán solo a nuevas tareas de traducción.';

  @override
  String get settingsTargetLanguageTitle => 'Default Target Language';

  @override
  String get settingsTargetLanguageNotice =>
      'Sets the default target language for new translation tasks. You can still change it per task in Quick Settings.';

  @override
  String get settingsTranslationParamsTitle => 'Parámetros de Traducción';

  @override
  String get settingsTranslationConcurrentTitle => 'Solicitudes Concurrentes';

  @override
  String get settingsTranslationConcurrentHint =>
      'Recomendado: 3 (ajustar 1–8 según el modelo y la cuota)';

  @override
  String get settingsTranslationChunkRetryTitle =>
      'Reintentos por fragmento/API';

  @override
  String get settingsTranslationChunkRetryHint =>
      'Recomendado: 3–5 (si falla un fragmento o la llamada a la API)';

  @override
  String get settingsTranslationSegmentAutoRetryTitle =>
      'Cola: rondas automáticas para segmentos fallidos';

  @override
  String get settingsTranslationSegmentAutoRetryHint =>
      'Recomendado: 3 (1–10 rondas de retraducción por lotes tras la traducción principal; solo modo cola)';

  @override
  String get settingsTranslationChunkSizeTitle =>
      'Tamaño del Fragmento (tokens)';

  @override
  String get settingsTranslationChunkSizeHint =>
      'Recomendado: 3000 tokens por solicitud (ajustar según el tamaño de contexto del modelo)';

  @override
  String get settingsExclusionTitle => 'Reglas de Exclusión Predeterminadas';

  @override
  String get settingsExclusionNotice =>
      'Activar = excluir automáticamente durante la Extracción; Desactivar = solo detectar (el usuario decide por segmento).';

  @override
  String get settingsExclusionImageTitle => 'Imagen';

  @override
  String get settingsExclusionImageSubtitle =>
      'Marcadores de posición de imagen y contenido de solo imagen';

  @override
  String get settingsExclusionFormulaTitle => 'Fórmula';

  @override
  String get settingsExclusionFormulaSubtitle => 'Fórmulas LaTeX / MathML';

  @override
  String get settingsExclusionReferenceTitle => 'Referencia';

  @override
  String get settingsExclusionReferenceSubtitle =>
      'Citas y referencias bibliográficas';

  @override
  String get settingsExclusionIdentifierTitle => 'Identificador';

  @override
  String get settingsExclusionIdentifierSubtitle =>
      'URLs, correos electrónicos, números de serie, fragmentos de código';

  @override
  String get settingsExclusionStructuralTitle => 'Estructural';

  @override
  String get settingsExclusionStructuralSubtitle =>
      'Encabezados, pies de página, notas al pie, números de página';

  @override
  String get settingsExclusionTableTitle => 'Tabla';

  @override
  String get settingsExclusionTableSubtitle =>
      'Contenido de tabla (tablas markdown / PDF)';

  @override
  String get settingsExclusionChartTitle => 'Gráfico';

  @override
  String get settingsExclusionChartSubtitle =>
      'Contenido de gráfico (Figure, bloques chart)';

  @override
  String get settingsExclusionLanguageMatchTitle => 'Coincidencia de Idioma';

  @override
  String get settingsExclusionLanguageMatchSubtitle =>
      'El idioma de origen coincide con el idioma de destino';

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
  String get settingsLanguageDialogTitle => 'Seleccionar Idioma';

  @override
  String get settingsUnitPt => 'pt';

  @override
  String get glossaryGeneratedTabTitle => 'Glosario Generado';

  @override
  String glossaryErrorRefresh(Object error) {
    return 'Error al actualizar glosarios: $error';
  }

  @override
  String get glossaryWarningNoGenerated =>
      'No hay glosario generado disponible';

  @override
  String get glossaryPanelView => 'Ver';

  @override
  String get glossaryPanelAddToPersonal => 'Agregar a Personal';

  @override
  String get glossaryPanelNoGlobalGlossaries =>
      'No hay glosarios globales disponibles';

  @override
  String get glossaryPanelSelectTitle => 'Seleccionar Glosario';

  @override
  String get glossaryPanelSelectHint => 'Seleccionar glosario...';

  @override
  String glossaryPanelSelected(Object name) {
    return 'Seleccionado: $name';
  }

  @override
  String get glossaryPanelSelectConfirm => 'Seleccionar';

  @override
  String get glossaryPanelMergeToCurrent => 'Fusionar al Glosario Actual';

  @override
  String glossaryPanelLoadedGlossary(Object name) {
    return 'Glosario cargado: $name';
  }

  @override
  String glossaryPanelLoadFailed(Object error) {
    return 'Error al cargar glosario: $error';
  }

  @override
  String glossaryPanelMergedIntoCurrent(Object glossaryName) {
    return 'Glosario \"$glossaryName\" fusionado al glosario actual';
  }

  @override
  String glossaryPanelMergeFailed(Object error) {
    return 'Fusión fallida: $error';
  }

  @override
  String get glossaryPanelEnterName => 'Ingresa un nombre para el glosario';

  @override
  String get glossaryPanelSaveDialogHint =>
      'Ingresa un nombre para el glosario o selecciona uno existente para reemplazar:';

  @override
  String get glossaryPanelReplaceTitle => 'Reemplazar Glosario Global';

  @override
  String glossaryPanelReplaceBody(Object glossaryName) {
    return 'Esto reemplazará todas las entradas en \"$glossaryName\" con las entradas del glosario actual. ¿Continuar?';
  }

  @override
  String get glossaryPanelReplaceConfirm => 'Reemplazar';

  @override
  String glossaryPanelReplacedGlobal(Object name) {
    return 'Glosario global reemplazado: $name';
  }

  @override
  String glossaryPanelSavedAsNewGlobal(Object name) {
    return 'Guardado como nuevo glosario global: $name';
  }

  @override
  String glossaryPanelSaveFailed(Object error) {
    return 'Error al guardar: $error';
  }

  @override
  String get glossaryPanelDetect => 'Detectar Glosario';

  @override
  String get glossaryPanelEdit => 'Editar';

  @override
  String get glossaryPanelCreate => 'Crear Glosario';

  @override
  String get glossaryPanelSelect => 'Seleccionar';

  @override
  String get glossaryPanelImport => 'Importar';

  @override
  String get glossaryPanelExport => 'Exportar';

  @override
  String get glossaryPanelSave => 'Guardar';

  @override
  String get glossaryPanelAddEntry => 'Agregar Entrada';

  @override
  String get glossaryPanelClear => 'Limpiar';

  @override
  String get glossaryPanelApply => 'Aplicar';

  @override
  String get glossaryPanelColumnSource => 'Origen';

  @override
  String get glossaryPanelColumnTarget => 'Destino';

  @override
  String get glossaryPanelColumnActions => 'Acciones';

  @override
  String get translationStepsUploadTooltipReady => 'Archivo seleccionado';

  @override
  String get translationStepsUploadTooltipNotReady =>
      'Selecciona un archivo para comenzar';

  @override
  String get translationStepsExtractTooltipReady => 'Ver origen extraído';

  @override
  String get translationStepsExtractTooltipNotReady =>
      'La extracción estará lista después de la importación';

  @override
  String get translationStepsGlossaryTooltipSkipped => 'Glosario omitido';

  @override
  String get translationStepsGlossaryTooltipEnabled => 'Glosario habilitado';

  @override
  String get translationStepsGlossaryTooltipDisabled =>
      'Genera o selecciona un glosario para habilitar';

  @override
  String get translationStepsTranslateTooltipReady => 'Traducción completada';

  @override
  String get translationStepsTranslateTooltipNotReady =>
      'Ejecuta la traducción para habilitar';

  @override
  String get glossaryDialogAddTitle => 'Agregar al Glosario Personal';

  @override
  String glossaryDialogAddBody(Object termCount) {
    return 'Esto agregará $termCount términos a tu glosario personal.';
  }

  @override
  String get glossaryDialogAddPreviewTitle =>
      'Vista previa (primeros 5 términos):';

  @override
  String glossaryDialogAddMoreTerms(Object remainingCount) {
    return '... y $remainingCount términos más';
  }

  @override
  String get glossaryDialogMergeStrategyTitle => 'Estrategia de Fusión:';

  @override
  String get glossaryDialogMergeUpdateTitle => 'Actualizar (Recomendado)';

  @override
  String get glossaryDialogMergeUpdateSubtitle =>
      'Actualizar términos existentes, agregar nuevos';

  @override
  String get glossaryDialogMergeAppendTitle => 'Anexar';

  @override
  String get glossaryDialogMergeAppendSubtitle =>
      'Solo agregar nuevos términos, omitir los existentes';

  @override
  String get glossaryDialogMergeReplaceTitle => 'Reemplazar';

  @override
  String get glossaryDialogMergeReplaceSubtitle =>
      'Reemplazar todo el glosario con estos términos';

  @override
  String get glossaryDialogCancel => 'Cancelar';

  @override
  String get glossaryDialogReviewAndAdd => 'Revisar y Agregar';

  @override
  String get glossaryConfirmAddTitle =>
      'Confirmar Agregar al Glosario Personal';

  @override
  String glossaryConfirmAddBody(Object termCount) {
    return '¿Agregar $termCount términos a tu glosario personal?';
  }

  @override
  String get glossaryConfirmAddStrategyUpdate =>
      'Estrategia: Actualizar términos existentes, agregar nuevos';

  @override
  String get glossaryConfirmAddStrategyAppend =>
      'Estrategia: Solo agregar nuevos términos, omitir los existentes';

  @override
  String get glossaryConfirmAddStrategyReplace =>
      'Estrategia: Reemplazar todo el glosario';

  @override
  String get glossaryConfirmAddAutoCreateHint =>
      'Si tu glosario personal no existe, se creará automáticamente.';

  @override
  String get glossaryConfirmAddButton => 'Agregar';

  @override
  String get glossaryExportDialogTitle => 'Guardar Glosario';

  @override
  String glossaryExportSuccess(Object filename) {
    return 'Glosario exportado: $filename';
  }

  @override
  String glossaryExportFailed(Object error) {
    return 'Error al exportar glosario: $error';
  }

  @override
  String glossaryCsvValidationFailed(Object errors) {
    return 'Validación del archivo CSV fallida:\n\n$errors';
  }

  @override
  String get glossaryCsvNoValidEntries =>
      'El archivo CSV no contiene entradas válidas.';

  @override
  String get glossaryImportDialogTitle => 'Importar Glosario';

  @override
  String glossaryImportDialogBodyEmpty(Object count) {
    return 'Se encontraron $count entradas en el archivo.\n\nEl glosario actual está vacío. Las entradas importadas se agregarán.';
  }

  @override
  String glossaryImportDialogBody(Object count) {
    return 'Se encontraron $count entradas en el archivo.\n\nElige cómo importar:';
  }

  @override
  String get glossaryImportButtonImport => 'Importar';

  @override
  String get glossaryImportButtonReplace => 'Reemplazar';

  @override
  String get glossaryImportButtonMerge => 'Fusionar';

  @override
  String glossaryImportResult(Object count, Object mode) {
    return 'Importadas $count entradas ($mode)';
  }

  @override
  String glossaryErrorImport(Object error) {
    return 'Error al importar glosario: $error';
  }

  @override
  String get glossaryErrorFileData =>
      'Error al leer los datos del archivo. Por favor, inténtalo de nuevo.';

  @override
  String get glossaryErrorFilePath =>
      'La ruta del archivo no está disponible. Por favor, inténtalo de nuevo.';

  @override
  String get glossaryErrorOnlyCsv =>
      'Solo se admiten archivos CSV y TBX para la importación de glosarios.';

  @override
  String get glossaryExportFormatLabel => 'Formato de exportación';

  @override
  String get glossaryExportFormatTbxSubtitle => 'TermBase eXchange (ISO 12620)';

  @override
  String get glossaryExportSourceLanguage => 'Idioma de origen';

  @override
  String get glossaryExportButtonExport => 'Exportar';

  @override
  String get extractFormatConversionFailed => 'La conversión de formato falló.';

  @override
  String get fileUploadDisabledMessage =>
      'Selección de archivo deshabilitada (procesamiento en curso)';

  @override
  String get fileUploadSupportedFormats =>
      'Soportados: Word (DOCX), PowerPoint (PPTX), Excel (XLSX/CSV), PDF, Markdown, TXT, HTML, SRT, JSON, EPUB, MOBI, Qt TS, PNG, JPEG';

  @override
  String get fileUploadDropHere => 'Soltar archivo aquí';

  @override
  String get fileUploadHint =>
      'Arrastra y suelta el archivo aquí o haz clic para seleccionar';

  @override
  String get fileUploadCancelTask => 'Cancelar Tarea Actual';

  @override
  String get exclusionPanelExcludeAll => 'Excluir Todo';

  @override
  String get exclusionPanelCancelUserExclusion =>
      'Restaurar Exclusiones Automáticas';

  @override
  String get exclusionPanelClearAllExclusions =>
      'Limpiar Todas las Exclusiones';

  @override
  String get exclusionPanelExclusionByType => 'Exclusión por Tipo:';

  @override
  String get exclusionPanelStructuralHeader => 'Estructural (Encabezado)';

  @override
  String get exclusionPanelStructuralFooter => 'Estructural (Pie de página)';

  @override
  String get exclusionPanelUserExcluded => 'Excluido por el Usuario';

  @override
  String get exclusionPanelExcluded => 'Excluido';

  @override
  String get exclusionPanelFilterDisplayMode =>
      'Modo de Visualización del Filtro:';

  @override
  String get exclusionPanelRebuild => 'Reconstruir';

  @override
  String get exclusionPanelPage => 'Página';

  @override
  String get exclusionPanelRebuildTooltip =>
      'Mostrar solo segmentos coincidentes en la nueva paginación';

  @override
  String get exclusionPanelPageTooltip => 'Filtrar dentro de la página actual';

  @override
  String get exclusionPanelSegmentTypeFilters => 'Filtros de Tipo de Segmento:';

  @override
  String get exclusionPanelCollapsePanelTooltip => 'Contraer panel';

  @override
  String get exclusionPanelExclusionControls => 'Controles de Exclusión:';

  @override
  String exclusionPanelExcludeCategory(Object count, Object name) {
    return 'Excluir $name ($count)';
  }

  @override
  String get exclusionPanelChangeReasonTitle => 'Cambiar Motivo de Exclusión';

  @override
  String get exclusionPanelCurrentLabel => 'Actual: ';

  @override
  String get exclusionPanelSelectNewReason => 'Seleccionar nuevo motivo:';

  @override
  String get exclusionPanelNoneRemoveExclusion =>
      'Ninguno (Eliminar Exclusión)';

  @override
  String get exclusionPanelApply => 'Aplicar';

  @override
  String get exclusionPanelExpandFilterPanel => 'Expandir Panel de Filtros';

  @override
  String get exclusionPanelCollapseFilterPanel => 'Contraer Panel de Filtros';

  @override
  String extractToolbarSegments(Object end, Object start, Object total) {
    return 'Segmentos ($start-$end de $total)';
  }

  @override
  String get extractToolbarCancel => 'Cancelar';

  @override
  String get extractCancelExtractionTitle => 'Cancelar Extracción';

  @override
  String get extractCancelExtractionContent =>
      '¿Estás seguro de que quieres cancelar la extracción? Esto no se puede deshacer.';

  @override
  String get extractCancelExtractionNo => 'No';

  @override
  String get extractCancelExtractionYes => 'Sí';

  @override
  String get extractExtractionCancelled => 'Extracción cancelada';

  @override
  String get extractMineruConfigRequiredTitle =>
      'Configuración de MinerU Requerida';

  @override
  String extractMineruConfigRequiredContent(Object error) {
    return 'Error al conectar con la API de MinerU. Por favor, configura los ajustes de MinerU en la página de Configuración.\n\nDetalles del error:\n$error';
  }

  @override
  String get extractOpenSettings => 'Abrir Configuración';

  @override
  String extractErrorLabel(Object error) {
    return 'Error: $error';
  }

  @override
  String get extractRetry => 'Reintentar';

  @override
  String get extractTaskTypeDetectIdentifier => 'Detectar Identificador';

  @override
  String get extractTaskTypeDetectLanguage => 'Detectar Idioma';

  @override
  String get extractTaskTypeDetectExclusions => 'Detectar Exclusiones';

  @override
  String get translationStatsTitle => 'Estadísticas de Traducción';

  @override
  String get translationStatsDocuments => 'Documentos';

  @override
  String get translationStatsPages => 'Páginas';

  @override
  String translationStatsLastUpdated(Object date) {
    return 'Última actualización: $date';
  }

  @override
  String get translationStatsLoadFailed => 'Error al cargar estadísticas';

  @override
  String get translationStatsJustNow => 'Justo ahora';

  @override
  String get translationStatsOneMinuteAgo => 'Hace 1 minuto';

  @override
  String translationStatsMinutesAgo(Object count) {
    return 'Hace $count minutos';
  }

  @override
  String get translationStatsOneHourAgo => 'Hace 1 hora';

  @override
  String translationStatsHoursAgo(Object count) {
    return 'Hace $count horas';
  }

  @override
  String get translationStatsYesterday => 'Ayer';

  @override
  String translationStatsDaysAgo(Object count) {
    return 'Hace $count días';
  }

  @override
  String get aiPlatformDisplayName => 'Nombre para Mostrar';

  @override
  String get aiPlatformParserSubtype => 'Subtipo del Analizador';

  @override
  String get aiPlatformParserSubtypeCloud => 'Nube';

  @override
  String get aiPlatformParserSubtypeLocal => 'Local';

  @override
  String get translationQueueEdit => 'Edición etiquetada';

  @override
  String get translationQueueSelectFormats => 'Seleccionar';

  @override
  String get translationQueueSelectFormatsTitle =>
      'Seleccionar formatos de descarga';

  @override
  String get translationQueueSelectFormatsFormatLabel => 'Formato';

  @override
  String get translationQueueSelectFormatsDownload => 'Descargar';

  @override
  String get translationQueueBatchLabelHint =>
      'Etiqueta del lote (para agrupar en la cola)';

  @override
  String get translationQueueBatchCreateFailed =>
      'Error al crear el lote de carga';

  @override
  String get translationQueueUngroupedSection => 'Sin agrupar';

  @override
  String translationQueueBatchProgress(int completed, int total) {
    return '$completed/$total completados';
  }

  @override
  String get translationQueueBatchSelectAll => 'Seleccionar lote';

  @override
  String get translationQueueBatchDownload => 'Descargar lote';

  @override
  String get translationQueueBatchDelete => 'Eliminar lote';

  @override
  String get translationQueueBatchDeleteTitle => '¿Eliminar este lote?';

  @override
  String get translationQueueBatchDeleteMessage =>
      'Se eliminarán todas las tareas del lote y sus resultados en caché.';

  @override
  String get reeditTitle => 'Editar traducción';

  @override
  String get reeditSaveExport => 'Guardar y exportar';

  @override
  String get reeditFetchError => 'Error al cargar segmentos de traducción.';

  @override
  String get reeditSaveSuccess => 'Cambios guardados correctamente.';

  @override
  String get reeditSaveError => 'Error al guardar los cambios.';

  @override
  String get workspaceCloseFlowTitle => '¿Cerrar este flujo?';

  @override
  String get workspaceCloseFlowMessage =>
      'Cerrar este flujo descartará los cambios no guardados.';

  @override
  String get workspaceCloseFlowSaveToQueue => 'Guardar y cerrar';

  @override
  String get workspaceCloseFlowDestroy => 'Destruir y cerrar';

  @override
  String get workspaceCloseFlowCancel => 'Cancelar';

  @override
  String get fetchUrlCancel => 'Cancelar';

  @override
  String get fetchUrl => 'Extraer URL';

  @override
  String get fetchUrlClose => 'Cerrar';

  @override
  String get loginSubtitleFeatures =>
      'Traducción de archivos\nConversión de formato\nExtracción de URL';

  @override
  String get loginSubtitleTagline =>
      'Sistema de procesamiento de documentos con IA';

  @override
  String get loginUsernameLabel => 'Nombre de usuario';

  @override
  String get loginUsernameHint => 'Ingrese su nombre de usuario';

  @override
  String get loginUsernameRequiredError => 'Ingrese su nombre de usuario';

  @override
  String get loginUsernameMinLengthError =>
      'El nombre de usuario debe tener al menos 3 caracteres';

  @override
  String get loginPasswordLabel => 'Contraseña';

  @override
  String get loginPasswordHint => 'Ingrese su contraseña';

  @override
  String get loginPasswordRequiredError => 'Ingrese su contraseña';

  @override
  String get loginForgotPassword => '¿Olvidó su contraseña?';

  @override
  String get loginPasswordRecoveryTitle => 'Recuperación de contraseña';

  @override
  String get loginPasswordRecoveryContactAdmin =>
      'Comuníquese con su administrador para restablecer la contraseña.';

  @override
  String get loginPasswordRecoveryAdminHint =>
      'Los administradores pueden restablecer contraseñas desde la página de gestión de usuarios después de iniciar sesión.';

  @override
  String get loginAuthMethodDefault => 'Usando autenticación predeterminada';

  @override
  String get loginCopyErrorLabel => 'Copiar';

  @override
  String get loginErrorCopiedMessage =>
      'Mensaje de error copiado al portapapeles';

  @override
  String get loginWelcomeBack => 'Bienvenido de nuevo';

  @override
  String get loginFeatureFormats =>
      'PDF, DOCX, XLSX, HTML, EPUB, MOBI\ny más de 15 formatos';

  @override
  String get loginFeatureLayout =>
      'Traducción con preservación del diseño\nde alta fidelidad';

  @override
  String get loginFeaturePlatforms =>
      'Más de 20 plataformas LLM compatibles\nincluyendo OpenAI, Claude, Ollama';

  @override
  String get loginPasswordRecoveryAdminGuide =>
      'Si es administrador, siga el procedimiento de recuperación de contraseña.';

  @override
  String get commonDarkMode => 'Modo oscuro';

  @override
  String get commonLightMode => 'Modo claro';

  @override
  String segmentPdfFontSizeAuto(String sizePt) {
    return 'Auto ($sizePt pt)';
  }

  @override
  String get segmentPdfFontSizeAutoUnknown => 'Auto';

  @override
  String segmentPdfFontSizeManual(String sizePt) {
    return '$sizePt pt';
  }

  @override
  String segmentRotationLabel(int degrees) {
    return '$degrees°';
  }

  @override
  String get segmentRotationOff => 'Rotar';

  @override
  String get segmentRotationNone => 'Sin rotación';

  @override
  String get segmentRotationMenuTitle => 'Ángulo';

  @override
  String segmentTableStrokeLabel(String strokePt) {
    return '$strokePt pt';
  }

  @override
  String get segmentTableStrokeOff => 'Cuadrícula';

  @override
  String get segmentTableStrokeNone => 'Ninguna';

  @override
  String get segmentTableStrokeMenuTitle => 'Grosor del borde';

  @override
  String get segmentItemExclude => 'Excluir';

  @override
  String get segmentItemEdit => 'Editar';

  @override
  String get segmentItemRetry => 'Reintentar';

  @override
  String get segmentItemMarkedRetry => 'Marcado para reintentar';

  @override
  String get segmentItemClear => 'Borrar';

  @override
  String get segmentItemCleared => 'Borrado';

  @override
  String get segmentItemFix => 'Corregir';

  @override
  String segmentItemExclusionBadge(String reason) {
    return 'EX: $reason';
  }

  @override
  String get segmentItemExclusionRemoveTooltip =>
      'Haga clic para quitar la exclusión';

  @override
  String get segmentItemExclusionLockedTooltip =>
      'Este segmento se excluyó automáticamente y no se puede revertir';

  @override
  String get segmentItemExclusionEditTooltip =>
      'Haga clic para editar el motivo de exclusión';

  @override
  String get segmentItemExclusionRemoved => 'Exclusión eliminada';

  @override
  String get segmentItemExclusionReasonUpdated =>
      'Motivo de exclusión actualizado';

  @override
  String segmentItemExclusionUpdateFailed(String error) {
    return 'Error al actualizar el motivo de exclusión: $error';
  }

  @override
  String get segmentItemUndoEditTooltip => 'Deshacer (edición)';

  @override
  String get segmentItemRedoEditTooltip => 'Rehacer (edición)';

  @override
  String get segmentItemUndoSaveTooltip => 'Deshacer (guardado)';

  @override
  String get segmentItemRedoSaveTooltip => 'Rehacer (guardado)';

  @override
  String get segmentItemCancel => 'Cancelar';

  @override
  String get segmentItemSave => 'Guardar';

  @override
  String get segmentItemEditShortcutHint =>
      'Pulse Ctrl+Enter para guardar, Esc para cancelar';

  @override
  String get segmentItemTranslationHint => 'Introduzca la traducción...';

  @override
  String segmentItemSaveFailed(String error) {
    return 'Error al guardar: $error';
  }

  @override
  String get segmentPdfFontSizeTitle => 'Tamaño de fuente PDF';

  @override
  String get segmentPdfTypographyTitle => 'Tipografía PDF';

  @override
  String get segmentPdfTypographyFontTitle => 'Fuente PDF';

  @override
  String get segmentPdfTypographyLeadingTitle => 'Interlineado';

  @override
  String get segmentPdfTypographyPreviewLabel => 'Vista previa';

  @override
  String get segmentPdfTypographyBold => 'Negrita';

  @override
  String get segmentPdfTypographyItalic => 'Cursiva';

  @override
  String segmentPdfTypographyFontSizeLabel(String sizePt) {
    return 'Tamaño de fuente: $sizePt pt';
  }

  @override
  String segmentPdfTypographyLeadingLabel(String leadingEm) {
    return 'Interlineado: $leadingEm em';
  }

  @override
  String get segmentPdfFontSizeReset => 'Restablecer a automático';

  @override
  String get segmentPdfTypographyResetFont => 'Restablecer fuente a automático';

  @override
  String get segmentPdfTypographyResetLeading =>
      'Restablecer interlineado a automático';

  @override
  String get segmentPdfFontSizeApply => 'Aplicar';

  @override
  String get translationPreviewPdfRevision => 'Revisión en vista previa';

  @override
  String get translationPreviewPdfRevisionCompare => 'Vista comparativa';

  @override
  String get translationPreviewLayoutComparePreview =>
      'Vista previa comparativa';

  @override
  String get translationPreviewLayoutTranslationRevision =>
      'Revisión de traducción';

  @override
  String get translationPreviewLayoutCompareRevision => 'Revisión comparativa';

  @override
  String get translationPreviewAutoRefreshPdf =>
      'Actualizar PDF automáticamente';

  @override
  String get translationPreviewFollowSegmentPage =>
      'Seguir página del segmento';

  @override
  String get translationPreviewFollowSegmentPageDesc =>
      'Al activarlo, la vista previa del PDF de traducción salta a la página del segmento seleccionado o marcado';

  @override
  String get translationPreviewMarkSelectedSegment =>
      'Marcar segmento seleccionado';

  @override
  String get translationPreviewMarkSelectedSegmentDesc =>
      'Al activarlo, muestra un marco alrededor del segmento seleccionado en la vista previa de la traducción';

  @override
  String get translationPreviewEditSegmentBbox => 'Edit Bbox';

  @override
  String get translationPreviewEditSegmentBboxDesc =>
      'When enabled, drag handles to adjust bounding box of the selected segment';

  @override
  String get translationPreviewStaleSession =>
      'Vista previa no disponible. Vuelva a abrir la revisión de vista previa desde el panel de traducción.';

  @override
  String translationPreviewPdfPageIndicator(String current, String total) {
    return 'Página $current / $total';
  }

  @override
  String get translationPreviewRefreshPdf => 'Actualizar PDF';

  @override
  String get translationPreviewBatchFont => 'Fuente';

  @override
  String get translationPreviewBatchFontTooltip =>
      'Aplicar configuración de fuente a los segmentos seleccionados';

  @override
  String get translationPreviewBatchFontSizeDecreaseTooltip =>
      'Reducir el tamaño de fuente 0.1 pt en los segmentos seleccionados';

  @override
  String get translationPreviewBatchFontSizeIncreaseTooltip =>
      'Aumentar el tamaño de fuente 0.1 pt en los segmentos seleccionados';

  @override
  String get translationPreviewBatchLeading => 'Interlineado en lote';

  @override
  String get translationPreviewBatchLeadingTooltip =>
      'Aplicar interlineado a los segmentos seleccionados';

  @override
  String get translationPreviewPdfRevisionSelectAll => 'Seleccionar todo';

  @override
  String get translationPreviewPdfRevisionInvertSelection =>
      'Invertir selección';

  @override
  String get translationPreviewPdfRevisionPageFilterLabel => 'Página';

  @override
  String get translationPreviewPdfRevisionPageFilterAll => 'Todas las páginas';

  @override
  String get translationPreviewPdfRevisionPageFilterSelectAll =>
      'Seleccionar todas las páginas';

  @override
  String get segmentPdfRevisionFontLabel => 'Fuente';

  @override
  String get segmentPdfRevisionEditLabel => 'Editar';

  @override
  String get segmentPdfRevisionClearLabel => 'Borrar';
}
