/* ─── Tab Navigation Helper ─── */
function switchToTab(tab) {
  if (typeof openWorkspaceRouteAware === 'function') {
    return openWorkspaceRouteAware(tab);
  }
  const el = document.querySelector(`.tab[data-tab="${tab}"]`);
  if (el) el.click();
  return !!el;
}

function handleShellNavigation(target) {
  const tabTarget = target.dataset.tabTarget;
  if (target.dataset.closeNeedsDetail !== undefined) {
    closeNeedsDetail();
  }
  if (!tabTarget) return;
  const navigationOptions = {
    prepSub: target.dataset.prepSub,
    mediaSub: target.dataset.mediaSub,
    scrollTarget: target.dataset.scrollTarget,
    checklistFocus: target.dataset.checklistFocus ? Number(target.dataset.checklistFocus) : undefined,
    showInvForm: target.dataset.showInvForm !== undefined,
    guideStart: target.dataset.guideStart,
  };
  if (!hasWorkspaceTabContent(tabTarget)) {
    navigateToWorkspace(tabTarget, navigationOptions);
    return;
  }
  switchToTab(tabTarget);
  if (target.dataset.prepSub) {
    const prepDelay = Number(target.dataset.prepDelay || 150);
    setTimeout(() => {
      switchPrepSub(target.dataset.prepSub);
      if (target.dataset.checklistFocus) {
        selectChecklist(Number(target.dataset.checklistFocus));
      }
      if (target.dataset.showInvForm !== undefined) {
        showInvForm();
      }
      if (target.dataset.guideStart) {
        setTimeout(() => startGuide(target.dataset.guideStart), Number(target.dataset.guideDelay || 300));
      }
    }, prepDelay);
  }
  if (target.dataset.mediaSub) {
    setTimeout(() => switchMediaSub(target.dataset.mediaSub), 100);
  }
  if (target.dataset.scrollTarget) {
    scrollToSection(target.dataset.scrollTarget);
  }
}

document.addEventListener('mousedown', e => {
  const control = e.target.closest('[data-prevent-mousedown]');
  if (control) e.preventDefault();
});

document.addEventListener('click', e => {
  const control = e.target.closest('[data-shell-action], [data-stop-propagation], [data-tab-target], [data-help], [data-theme-select], [data-customize-theme], [data-zoom-level], [data-density-level], [data-garden-tab], [data-protocol-toggle], [data-protocol-bulk], [data-mode-select], [data-prep-category], [data-prep-sub-switch], [data-checklist-template], [data-checklist-id], [data-checklist-delete], [data-check-item], [data-app-frame-url], [data-backdrop-close], [data-click-target], [data-chat-action], [data-starter-prompt], [data-media-sub-switch], [data-media-action], [data-torrent-cat], [data-branch-switch], [data-library-action], [data-zim-tier], [data-map-action], [data-map-download-url], [data-note-action], [data-benchmark-mode], [data-benchmark-action], [data-tool-action], [data-drill-type], [data-prep-action], [data-sit-domain], [data-security-tab], [data-power-tab], [data-med-ref], [data-dtmf-key]');
  if (!control) return;
  if (control.dataset.backdropClose !== undefined) {
    if (e.target !== control) return;
    if (control.dataset.backdropClose === 'needs-detail') closeNeedsDetail();
    if (control.dataset.backdropClose === 'widget-config') closeWidgetManager();
    if (control.dataset.backdropClose === 'shell-health') toggleShellHealth(false);
    if (control.dataset.backdropClose === 'fuel-modal') closeFuelForm();
    if (control.dataset.backdropClose === 'equip-modal') closeEquipForm();
    if (control.dataset.backdropClose === 'csv-import-modal') closeCSVImportModal();
    if (control.dataset.backdropClose === 'ai-sitrep-modal') {
      const modal = document.getElementById('ai-sitrep-modal');
      if (modal) modal.style.display = 'none';
    }
    if (control.dataset.backdropClose === 'generated-modal') {
      control.remove();
    }
    return;
  }
  if (control.dataset.stopPropagation !== undefined) {
    e.stopPropagation();
  }
  if (control.tagName === 'A') {
    e.preventDefault();
  }
  const action = control.dataset.shellAction;
  if (action === 'print-app-frame') { printAppFrame(); return; }
  if (action === 'close-app-frame') { closeAppFrame(); return; }
  if (action === 'toggle-command-palette') { toggleCommandPalette(); return; }
  if (action === 'toggle-shortcuts') { toggleCommandPalette(false); toggleShortcutsHelp(); return; }
  if (action === 'toggle-alert-bar') { toggleAlertBar(); return; }
  if (action === 'toggle-customize-panel') { toggleCustomizePanel(); return; }
  if (action === 'toggle-shell-health') { toggleShellHealth(); return; }
  if (action === 'open-widget-manager') { openWidgetManager(); return; }
  if (action === 'close-widget-manager') { closeWidgetManager(); return; }
  if (action === 'reset-widget-config') { resetWidgetConfig(); return; }
  if (action === 'save-widget-config') { saveWidgetConfig(); return; }
  if (action === 'dismiss-broadcast') { dismissBroadcast(); return; }
  if (action === 'dismiss-all-alerts') { dismissAllAlerts(); return; }
  if (action === 'generate-alert-summary') { generateAlertSummary(); return; }
  if (action === 'reset-customization') { resetCustomization(); return; }
  if (action === 'start-all-services') { startAllServices(); return; }
  if (action === 'stop-all-services') { stopAllServices(); return; }
  if (action === 'install-service') { installService(control.dataset.serviceId); return; }
  if (action === 'start-service') { startService(control.dataset.serviceId); return; }
  if (action === 'stop-service') { stopService(control.dataset.serviceId); return; }
  if (action === 'restart-service') { restartService(control.dataset.serviceId); return; }
  if (action === 'uninstall-service') { uninstallService(control.dataset.serviceId); return; }
  if (action === 'reload-services') { loadServices(); return; }
  if (action === 'pull-all-models') { pullAllModels(); return; }
  if (action === 'create-training-dataset') { createTrainingDataset(); return; }
  if (action === 'create-training-job') { createTrainingJob(); return; }
  if (action === 'save-ollama-host') { saveOllamaHost(); return; }
  if (action === 'set-auth-password') { setAuthPassword(); return; }
  if (action === 'clear-auth-password') { clearAuthPassword(); return; }
  if (action === 'rerun-setup-wizard') {
    setShellVisibility(document.getElementById('wizard'), true);
    wizGoPage(1);
    return;
  }
  if (action === 'show-lan-qr') { showLanQR(); return; }
  if (action === 'full-backup') { doFullBackup(); return; }
  if (action === 'show-backup-list') { showBackupList(); return; }
  if (action === 'export-config') { doExportConfig(); return; }
  if (action === 'delete-model') { deleteModel(control.dataset.modelName, control); return; }
  if (action === 'pull-settings-model') { pullFromSettings(control.dataset.modelName); return; }
  if (action === 'show-model-info') { showModelInfo(control.dataset.modelName, document.getElementById(control.dataset.modelInfoId)); return; }
  if (action === 'pull-model') { pullModel(control.dataset.modelName); return; }
  if (action === 'open-search-result') { openSearchResult(control.dataset.resultType, Number(control.dataset.resultId)); return; }
  if (action === 'close-modal-overlay') {
    const overlay = control.closest('.modal-overlay');
    if (overlay) overlay.remove();
    return;
  }
  if (action === 'restore-legacy-backup') { restoreBackup(control.dataset.backupFilename); return; }
  if (action === 'close-generated-modal') {
    if (typeof NomadModal !== 'undefined' && NomadModal.isOpen()) NomadModal.close();
    const modal = control.closest('.generated-modal-overlay');
    if (modal) modal.remove();
    return;
  }
  if (action === 'show-csv-import') { showCSVImportModal(); return; }
  if (action === 'export-sync-pack') { exportSyncPack(); return; }
  if (action === 'confirm-host-power') { confirmPower(control, control.dataset.hostPower); return; }
  if (action === 'save-node-name') { saveNodeName(); return; }
  if (action === 'discover-peers') { discoverPeers(); return; }
  if (action === 'sync-manual-peer') {
    const input = document.getElementById('manual-peer-ip');
    syncToPeer(input?.value?.trim());
    return;
  }
  if (action === 'sync-to-peer') {
    syncToPeer(control.dataset.peerIp, Number(control.dataset.peerPort || 8080), control.dataset.peerName);
    return;
  }
  if (action === 'load-sync-log') { loadSyncLog(); return; }
  if (action === 'load-conflicts') { loadConflicts(); return; }
  if (action === 'resolve-conflict') {
    resolveConflict(Number(control.dataset.conflictId), control.dataset.conflictResolution);
    return;
  }
  if (action === 'show-merge-editor') {
    showMergeEditor(Number(control.dataset.conflictId), control.dataset.conflictDetail);
    return;
  }
  if (action === 'close-merge-editor') {
    const overlay = document.getElementById('merge-editor-overlay');
    if (overlay) overlay.hidden = true;
    return;
  }
  if (action === 'submit-merge') { submitMerge(); return; }
  if (action === 'compose-dead-drop') { composeDeadDrop(); return; }
  if (action === 'create-group-exercise') { createGroupExercise(); return; }
  if (action === 'join-group-exercise') { joinGroupExercise(control.dataset.exerciseId); return; }
  if (action === 'advance-group-exercise') { advanceGroupExercise(control.dataset.exerciseId); return; }
  if (action === 'complete-group-exercise') { completeGroupExercise(control.dataset.exerciseId); return; }
  if (action === 'load-log-viewer') { loadLogViewer(); return; }
  if (action === 'show-task-form') { showTaskForm(); return; }
  if (action === 'hide-task-form') { hideTaskForm(); return; }
  if (action === 'save-task') { saveTask(); return; }
  if (action === 'complete-task') { completeTask(Number(control.dataset.taskId)); return; }
  if (action === 'delete-task') { deleteTask(Number(control.dataset.taskId)); return; }
  if (action === 'show-watch-form') { showWatchForm(); return; }
  if (action === 'hide-watch-form') { hideWatchForm(); return; }
  if (action === 'create-watch-schedule') { createWatchSchedule(); return; }
  if (action === 'hide-watch-detail') {
    const detail = document.getElementById('watch-detail');
    if (detail) detail.style.display = 'none';
    return;
  }
  if (action === 'view-watch-schedule') { viewWatchSchedule(Number(control.dataset.watchId)); return; }
  if (action === 'delete-watch-schedule') { deleteWatchSchedule(Number(control.dataset.watchId)); return; }
  if (action === 'load-service-logs') { loadServiceLogs(); return; }
  if (action === 'run-self-test') { runSelfTest(); return; }
  if (action === 'run-db-check') { runDBCheck(); return; }
  if (action === 'run-db-vacuum') { runDBVacuum(); return; }
  if (action === 'refresh-health') { loadHealthDashboard(); return; }
  if (action === 'create-backup') { createBackup(); return; }
  if (action === 'restore-backup') { restoreScheduledBackup(control.dataset.backupFilename, control.dataset.backupEncrypted === 'true'); return; }
  if (action === 'delete-backup') { deleteBackup(control.dataset.backupFilename); return; }
  if (action === 'offline-full-sync') { offlineFullSync(); return; }
  if (action === 'offline-status') { offlineStatus(); return; }
  if (action === 'offline-clear') { offlineClear(); return; }
  if (action === 'scan-serial-ports') { scanSerialPorts(); return; }
  if (action === 'download-pdf') { downloadPdf(control.dataset.pdfUrl, control.dataset.pdfFilename); return; }
  if (action === 'download-update') { downloadUpdate(); return; }
  if (action === 'open-update-folder') { openUpdateFolder(); return; }
  if (action === 'restore-wizard') { wizRestore(); return; }
  if (action === 'dismiss-copilot-answer') { dismissCopilotAnswer(); return; }
  if (action === 'voice-input') { voiceInput(control.dataset.voiceTarget); return; }
  if (action === 'toggle-handsfree') {
    if (typeof window.NomadVoiceCopilot !== 'undefined') window.NomadVoiceCopilot.toggle();
    return;
  }
  if (action === 'save-home-location') { saveHomeLocation(); return; }
  if (action === 'detect-home-location') { detectHomeLocation(); return; }
  if (action === 'open-emergency-modal') { openEmergencyEnterModal(); return; }
  if (action === 'open-add-family-member') { openAddFamilyMember(); return; }
  if (action === 'close-add-family-member') { closeAddFamilyMember(); return; }
  if (action === 'submit-add-family-member') { submitAddFamilyMember(); return; }
  if (action === 'reset-family-checkins') { resetFamilyCheckins(); return; }
  if (action === 'generate-daily-brief') { generateDailyBrief(); return; }
  if (action === 'update-family-status') {
    updateFamilyStatus(Number(control.dataset.memberId), control.dataset.status);
    return;
  }
  if (action === 'delete-family-member') {
    deleteFamilyMember(Number(control.dataset.memberId), control.dataset.memberName);
    return;
  }
  if (action === 'close-emergency-modal') { closeEmergencyEnterModal(); return; }
  if (action === 'confirm-emergency-enter') { confirmEmergencyEnter(); return; }
  if (action === 'open-emergency-exit-modal') { openEmergencyExitModal(); return; }
  if (action === 'close-emergency-exit-modal') { closeEmergencyExitModal(); return; }
  if (action === 'confirm-emergency-exit') { confirmEmergencyExit(); return; }
  if (action === 'ask-copilot') { askCopilot(control.dataset.copilotQuestion); return; }
  if (action === 'close-csv-import') { closeCSVImportModal(); return; }
  if (action === 'execute-csv-import') { executeCSVImport(); return; }
  if (action === 'print-window') { window.print(); return; }
  if (action === 'close-ai-sitrep') {
    if (typeof NomadModal !== 'undefined' && NomadModal.isOpen()) { NomadModal.close(); return; }
    const modal = document.getElementById('ai-sitrep-modal');
    if (modal) modal.style.display = 'none';
    return;
  }
  if (action === 'wiz-go-page') { wizGoPage(Number(control.dataset.wizPage)); return; }
  if (action === 'skip-wizard') { skipWizard(); return; }
  if (action === 'wiz-set-custom-path') { wizSetCustomPath(); return; }
  if (action === 'wiz-custom-select-all') { wizCustomSelectAll(); return; }
  if (action === 'wiz-custom-deselect-all') { wizCustomDeselectAll(); return; }
  if (action === 'wiz-start-setup') { wizStartSetup(); return; }
  if (action === 'wiz-minimize') { wizMinimize(); return; }
  if (action === 'wiz-skip-to-complete') { wizSkipToComplete(); return; }
  if (action === 'start-tour') { startTour(); return; }
  if (action === 'close-tour-wizard') { closeTourWizard(); return; }
  if (action === 'tour-next') { tourNext(); return; }
  if (action === 'tour-skip') { tourSkip(); return; }
  if (action === 'toggle-lan-chat') { toggleLanChat(); return; }
  if (action === 'toggle-lan-chat-compact') { toggleLanChatCompact(); return; }
  if (action === 'send-lan-msg') { sendLanMsg(); return; }
  if (action === 'toggle-quick-actions') { toggleQuickActions(); return; }
  if (action === 'quick-log-incident') { quickLogIncident(); return; }
  if (action === 'quick-start-timer') {
    toggleTimerPanel();
    toggleQuickActions();
    return;
  }
  if (action === 'quick-add-inventory') { quickAddInventory(); return; }
  if (action === 'quick-weather-obs') { quickWeatherObs(); return; }
  if (action === 'quick-new-note') { quickNewNote(); return; }
  if (action === 'toggle-timer-panel') { toggleTimerPanel(); return; }
  if (action === 'create-timer') { createTimer(); return; }
  if (action === 'create-timer-quick') {
    createTimerQuick(control.dataset.timerName, Number(control.dataset.timerMins));
    return;
  }
  if (action === 'delete-timer') { deleteTimer(Number(control.dataset.timerId)); return; }
  if (action === 'lookup-barcode') { lookupBarcode(); return; }
  if (action === 'barcode-to-inventory') { barcodeToInventory(control.dataset.barcodeCode); return; }
  if (action === 'open-wiki-link') { openWikiLink(control.dataset.wikiTitle); return; }
  if (action === 'copy-code') { copyCode(control); return; }
  if (action === 'copy-text') {
    navigator.clipboard.writeText(control.dataset.copyText || '').then(() => toast('Copied', 'success'));
    return;
  }
  if (action === 'snooze-alert') { snoozeAlert(Number(control.dataset.alertId)); return; }
  if (action === 'dismiss-alert') { dismissAlert(Number(control.dataset.alertId)); return; }
  if (action === 'close-needs-detail') { closeNeedsDetail(); return; }
  if (action === 'open-needs-detail') { openNeedsDetail(control.dataset.needId); return; }
  if (action === 'refresh-activity') { loadActivity(); return; }
  if (action === 'toggle-widget-expand') { toggleWidgetExpand(control.dataset.widgetId); return; }
  if (action === 'wiz-select-drive') { wizSelectDrive(control.dataset.drivePath); return; }
  if (action === 'wiz-select-tier') { wizSelectTier(control.dataset.tierId); return; }
  if (action === 'run-training-job') { runTrainingJob(Number(control.dataset.trainingJobId)); return; }
  if (action === 'close-add-item-form') {
    const form = document.getElementById('add-item-form');
    if (form) form.remove();
    return;
  }
  if (action === 'close-preservation-form') {
    const form = document.getElementById('add-pres-form');
    if (form) form.remove();
    return;
  }
  if (action === 'close-wound-photo-modal') { closeWoundPhotoModal(); return; }
  if (action === 'close-triage-picker') {
    const picker = document.getElementById('triage-picker');
    if (picker) picker.remove();
    return;
  }
  if (action === 'close-lan-qr') {
    const modal = document.getElementById('lan-qr-modal');
    if (modal) modal.remove();
    return;
  }
  if (action === 'open-active-patient-card') {
    if (_activePatientId) {
      openAppFrame('Patient Card', `/api/patients/${_activePatientId}/card`);
    }
    return;
  }
  if (action === 'close-waypoint-panel') {
    const panel = document.getElementById('waypoint-form-panel');
    if (panel) panel.remove();
    return;
  }
  if (action === 'close-zone-panel') {
    const panel = document.getElementById('zone-form-panel');
    if (panel) panel.remove();
    _zonePoints = [];
    return;
  }
  if (control.dataset.clickTarget) {
    const target = document.getElementById(control.dataset.clickTarget);
    if (target) target.click();
    return;
  }
  if (control.dataset.hideTarget) {
    const target = document.getElementById(control.dataset.hideTarget);
    if (target) target.style.display = 'none';
    return;
  }
  if (control.dataset.installService) {
    installService(control.dataset.installService);
    return;
  }
  if (control.dataset.zimTier) {
    downloadAllZimsByTier(control.dataset.zimTier);
    return;
  }
  if (control.dataset.libraryAction) {
    switch (control.dataset.libraryAction) {
      case 'check-content-updates': checkContentUpdates(); break;
      case 'refresh-offline-content': loadZimList(); loadZimCatalog(); loadZimDownloads(); break;
      case 'close-pdf-viewer': closePDFViewer(); break;
      case 'switch-tier': switchTier(Number(control.dataset.zimCategoryIndex), control.dataset.zimTierValue, control); break;
      case 'delete-zim': deleteZim(control.dataset.zimFilename); break;
      case 'download-zim-item': downloadZimItem(control, control.dataset.zimUrl, control.dataset.zimFilename); break;
      case 'update-zim-content': updateZimContent(control.dataset.zimUrl, control.dataset.zimFilename); break;
      case 'download-wiki-tier': downloadWikiTier(control.dataset.zimUrl, control.dataset.zimFilename); break;
      case 'view-pdf-item': viewPDF(control.dataset.pdfFilename); break;
      case 'delete-pdf-item': deletePDF(control.dataset.pdfFilename); break;
    }
    return;
  }
  if (control.dataset.chatAction) {
    switch (control.dataset.chatAction) {
      case 'view-kb-document': viewKBDocument(Number(control.dataset.docId)); break;
      case 'copy-message': copyMsg(control); break;
      case 'fork-conversation': forkConversation(Number(control.dataset.messageIndex)); break;
      case 'fork-what-if': forkWhatIf(Number(control.dataset.messageIndex)); break;
      case 'delete-kb-doc': deleteKBDoc(Number(control.dataset.docId)); break;
      case 'analyze-kb-doc': analyzeDoc(Number(control.dataset.docId)); break;
      case 'show-doc-details': showDocDetails(Number(control.dataset.docId)); break;
      case 'import-doc-entities': importDocEntities(Number(control.dataset.docId)); break;
      case 'select-conversation': selectConvo(Number(control.dataset.convoId)); break;
      case 'rename-conversation': renameConvo(Number(control.dataset.convoId)); break;
      case 'tag-conversation': tagConversation(Number(control.dataset.convoId)); break;
      case 'delete-conversation': deleteConvo(Number(control.dataset.convoId)); break;
      case 'new-conversation': newConversation(); break;
      case 'delete-all-convos': deleteAllConvos(); break;
      case 'toggle-model-picker': toggleModelPicker(); break;
      case 'export-conversation': exportConversation(); break;
      case 'toggle-branch-panel': toggleBranchPanel(); break;
      case 'pull-all-models': pullAllModels(); break;
      case 'pull-custom-model': pullCustomModel(); break;
      case 'toggle-custom-prompt': toggleCustomPrompt(); break;
      case 'save-custom-prompt': saveCustomPrompt(); break;
      case 'clear-custom-prompt': clearCustomPrompt(); break;
      case 'analyze-all-docs': analyzeAllDocs(); break;
      case 'return-main-conversation': returnToMainConversation(); break;
      case 'clear-chat-file': clearChatFile(); break;
      case 'clear-chat-image': clearChatImage(); break;
      case 'send-chat': sendChat(); break;
      case 'stop-chat': stopChat(); break;
      case 'regenerate-chat': regenerateChat(); break;
    }
    return;
  }
  if (control.dataset.starterPrompt) {
    useStarter(control.dataset.starterPrompt);
    return;
  }
  if (control.dataset.mediaSubSwitch) {
    switchMediaSub(control.dataset.mediaSubSwitch);
    return;
  }
  if (control.dataset.mediaAction) {
    switch (control.dataset.mediaAction) {
      case 'download-url': downloadMediaURL(); break;
      case 'toggle-catalog': toggleMediaCatalog(); break;
      case 'toggle-select': toggleMediaSelect(); break;
      case 'toggle-view': toggleMediaView(); break;
      case 'toggle-queue': toggleDlQueue(); break;
      case 'install-ytdlp': installYtdlp(); break;
      case 'download-all-catalog': downloadAllCatalog(); break;
      case 'download-all-audio-catalog': downloadAllAudioCatalog(); break;
      case 'download-all-books': downloadAllBooks(); break;
      case 'batch-move': batchMoveMedia(); break;
      case 'batch-delete': batchDeleteMedia(); break;
      case 'load-subscriptions': loadSubscriptions(); break;
      case 'filter-channel-list': filterChannels(); break;
      case 'search-youtube': searchYouTube(); break;
      case 'close-yt-watch': closeYtWatch(); break;
      case 'open-torrent-save-dir': openTorrentSaveDir(); break;
      case 'create-folder': createMediaFolder(); break;
      case 'close-media-player': closeMediaPlayer(); break;
      case 'book-prev': bookReaderPrev(); break;
      case 'book-next': bookReaderNext(); break;
      case 'close-book-reader': closeBookReader(); break;
      case 'select-folder': selectMediaFolder(control.dataset.mediaFolder || ''); break;
      case 'play-video': playMediaVideo(Number(control.dataset.mediaId), control.dataset.mediaFilename, control.dataset.mediaTitle); break;
      case 'play-audio': playMediaAudio(Number(control.dataset.mediaId), control.dataset.mediaFilename, control.dataset.mediaTitle); break;
      case 'open-book': openBook(Number(control.dataset.mediaId), control.dataset.mediaFilename, control.dataset.mediaTitle, control.dataset.mediaFormat); break;
      case 'toggle-select-item': toggleMediaItemSelect(Number(control.dataset.mediaId)); break;
      case 'toggle-favorite-item': toggleFavorite(Number(control.dataset.mediaId)); break;
      case 'move-media-item': moveMediaItem(Number(control.dataset.mediaId), control.dataset.mediaKind); break;
      case 'delete-media-item': deleteMediaItem(Number(control.dataset.mediaId), control.dataset.mediaKind); break;
      case 'download-catalog-item': downloadCatalogItem(control, control.dataset.mediaUrl, control.dataset.mediaFolder, control.dataset.mediaCategory); break;
      case 'download-catalog-audio': downloadCatalogAudio(control, control.dataset.mediaUrl, control.dataset.mediaFolder, control.dataset.mediaCategory); break;
      case 'download-ref-book': downloadRefBook(control, {
        url: control.dataset.mediaUrl,
        folder: control.dataset.mediaFolder,
        category: control.dataset.mediaCategory,
        title: control.dataset.mediaTitle,
        author: control.dataset.mediaAuthor,
        format: control.dataset.mediaFormat,
        description: control.dataset.mediaDescription,
      }); break;
      case 'browse-channel-videos': browseChannelVideos(control.dataset.channelUrl, control.dataset.channelName); break;
      case 'download-channel-video': downloadChannelVideo(control.dataset.channelUrl, control.dataset.channelName, control.dataset.channelCategory); break;
      case 'subscribe-channel': subscribeChannel(control.dataset.channelUrl, control.dataset.channelName, control.dataset.channelCategory); break;
      case 'back-to-channels': backToChannels(); break;
      case 'reset-channel-browser': backToChannels(); loadChannelBrowser(); break;
      case 'install-ytdlp-browse': autoInstallYtdlp(control.dataset.channelUrl, control.dataset.channelName); break;
      case 'watch-download-yt': watchAndDownload(control.dataset.mediaUrl, control.dataset.mediaTitle, control.dataset.mediaVideoId); break;
      case 'download-yt-video': downloadYtVideo(control.dataset.mediaUrl, control.dataset.mediaTitle); break;
      case 'download-yt-audio': downloadYtAudio(control.dataset.mediaUrl, control.dataset.mediaTitle); break;
      case 'crosssearch-input': mediaCrossSearchInput(control); break;
      case 'crosssearch-clear': mediaCrossSearchClear(); break;
      case 'crosssearch-open': mediaCrossSearchOpen(control.dataset.resultType, control.dataset.resultId); break;
      case 'load-more-results': loadMoreResults(); break;
      case 'torrent-open-folder': torrentOpenFolder(control.dataset.torrentHash); break;
      case 'torrent-resume': torrentResume(control.dataset.torrentHash); break;
      case 'torrent-pause': torrentPause(control.dataset.torrentHash); break;
      case 'torrent-remove': torrentRemove(control.dataset.torrentHash, false); break;
      case 'copy-torrent-magnet': copyTorrentMagnet(control.dataset.torrentId); break;
      case 'download-torrent': downloadTorrent(control.dataset.torrentId); break;
      case 'seek-audio-chapter': seekAudioTo(Number(control.dataset.audioTime || 0)); break;
      case 'unsubscribe-channel': unsubscribeChannel(Number(control.dataset.subscriptionId), control.dataset.channelName); break;
      case 'resume-media': resumeMedia(control.dataset.mediaKind, Number(control.dataset.mediaId)); break;
    }
    return;
  }
  if (control.dataset.torrentCat) {
    filterTorrentCat(control.dataset.torrentCat);
    return;
  }
  if (control.dataset.mapDownloadUrl) {
    const input = document.getElementById('map-url-input');
    if (input) input.value = control.dataset.mapDownloadUrl;
    downloadMapFromUrl();
    return;
  }
  if (control.dataset.mapAction) {
    switch (control.dataset.mapAction) {
      case 'delete-map': deleteMap(control.dataset.mapFilename, control); break;
      case 'delete-waypoint': deleteWaypoint(Number(control.dataset.waypointId)); break;
      case 'goto-bookmark': gotoBookmark(Number(control.dataset.bookmarkIndex)); break;
      case 'delete-bookmark': deleteBookmark(Number(control.dataset.bookmarkIndex)); break;
      case 'load-elevation-profile': loadElevationProfile(Number(control.dataset.routeId)); break;
      case 'show-elevation-profile': showElevationProfile(Number(control.dataset.routeId)); break;
      case 'plan-route': openRoutePlanner(Number(control.dataset.routeId)); break;
      case 'close-route-planner': closeRoutePlanner(); break;
      case 'run-route-plan': runRoutePlan(); break;
      case 'delete-saved-route': deleteSavedRoute(Number(control.dataset.routeId)); break;
      case 'download-region': downloadMapRegion(control.dataset.mapRegion); break;
      case 'toggle-map-view': toggleMapView(); break;
      case 'drop-pin': dropPin(); break;
      case 'toggle-measure': toggleMeasure(); break;
      case 'save-waypoint': saveWaypoint(); break;
      case 'start-draw-zone': startDrawZone(); break;
      case 'start-draw-property': startDrawProperty(); break;
      case 'clear-pins': clearPins(); break;
      case 'print-map-view': printMapView(); break;
      case 'print-map': printMap(); break;
      case 'save-map-bookmark': saveMapBookmark(); break;
      case 'calc-bearing-distance': calcBearingDistance(); break;
      case 'toggle-map-measure': toggleMapMeasure(); break;
      case 'cycle-map-style': cycleMapStyle(); break;
      case 'toggle-garden-overlay': toggleGardenOverlay(); break;
      case 'toggle-supply-chain-overlay': toggleSupplyChainOverlay(); break;
      case 'generate-map-atlas': generateMapAtlas(); break;
      case 'submit-waypoint': submitWaypoint(Number(control.dataset.wpLat), Number(control.dataset.wpLng)); break;
      case 'submit-drawn-zone': submitDrawnZone(); break;
      case 'geocode-go': {
        geocodeGo(Number(control.dataset.geocodeLat), Number(control.dataset.geocodeLng), control.dataset.geocodeName);
        const results = document.getElementById('geocode-results');
        if (results) results.style.display = 'none';
        break;
      }
      case 'toggle-contour-overlay': toggleContourOverlay(); break;
      case 'search-map': searchMap(); break;
      case 'clear-measure': clearMeasure(); break;
      case 'download-all-maps': downloadAllMaps(); break;
      case 'download-map-url': downloadMapFromUrl(); break;
      case 'import-map-file': importMapFile(); break;
      case 'refresh-waypoint-distances': loadWPDistances(); break;
      case 'load-saved-routes': loadSavedRoutes(); break;
      case 'hide-elevation-profile': hideElevationProfile(); break;
      case 'render-map-bookmarks': renderMapBookmarks(); break;
      case 'toggle-map-sources': {
        const catalog = document.getElementById('map-sources-catalog');
        if (catalog) catalog.hidden = !catalog.hidden;
        break;
      }
    }
    return;
  }
  if (control.dataset.noteAction) {
    switch (control.dataset.noteAction) {
      case 'select-note': selectNote(Number(control.dataset.noteId)); break;
      case 'apply-note-template': applyNoteTemplateByIndex(Number(control.dataset.noteTemplateIndex)); break;
      case 'create-note': createNote(); break;
      case 'toggle-note-templates': toggleNoteTemplates(); break;
      case 'toggle-note-pin': toggleNotePin(); break;
      case 'toggle-note-preview': toggleNotePreview(); break;
      case 'export-current-note': exportCurrentNote(); break;
      case 'delete-note': deleteNote(); break;
    }
    return;
  }
  if (control.dataset.benchmarkMode) {
    runBenchmark(control.dataset.benchmarkMode);
    return;
  }
  if (control.dataset.benchmarkAction) {
    switch (control.dataset.benchmarkAction) {
      case 'run-ai': runAIBenchmark(); break;
      case 'run-storage': runStorageBenchmark(); break;
    }
    return;
  }
  if (control.dataset.drillType) {
    startDrill(control.dataset.drillType);
    return;
  }
  if (control.dataset.toolAction) {
    switch (control.dataset.toolAction) {
      case 'start-compass': startCompass(); break;
      case 'scan-meshtastic': scanMeshtastic(); break;
      case 'send-mesh-msg': sendMeshMsg(); break;
      case 'complete-drill': completeDrill(); break;
      case 'cancel-drill': cancelDrill(); break;
      case 'load-drill-history': loadDrillHistory(); break;
      case 'load-scenario-history': loadScenarioHistory(); break;
    }
    return;
  }
  if (control.dataset.prepAction) {
    switch (control.dataset.prepAction) {
      case 'print-full-card': printFullCard(); break;
      case 'generate-status-report': generateStatusReport(); break;
      case 'play-morse': playMorse(); break;
      case 'abandon-scenario': abandonScenario(); break;
      case 'scenario-choose': scenarioChoose(Number(control.dataset.scenarioPhase), Number(control.dataset.scenarioChoiceIndex), control.dataset.scenarioChoiceLabel); break;
      case 'scenario-complication-respond': complicationRespond(Number(control.dataset.scenarioAfterPhase), Number(control.dataset.scenarioChoiceIndex), control.dataset.scenarioChoiceLabel); break;
      case 'complete-tccc-action': completeTCCCAction(Number(control.dataset.tcccActionIndex), control); break;
      case 'tccc-step-prev': _tcccStep--; renderTCCCStep(_tcccProtocol); break;
      case 'tccc-step-next': _tcccStep++; renderTCCCStep(_tcccProtocol); break;
      case 'tccc-quiz-answer': tcccAnswer(control.dataset.tcccAnswer === 'yes'); break;
      case 'tccc-quiz-next': tcccNext(Number(control.dataset.tcccNext)); break;
      case 'show-forage-month': showForageMonth(Number(control.dataset.forageMonth)); break;
      case 'send-broadcast': sendBroadcast(); break;
      case 'clear-broadcast': clearBroadcast(); break;
      case 'add-vehicle': addVehicle(); break;
      case 'cycle-vehicle-status': cycleVehicleStatus(Number(control.dataset.vehicleId)); break;
      case 'delete-vehicle': deleteVehicle(Number(control.dataset.vehicleId)); break;
      case 'generate-sitrep': generateSitrep(); break;
      case 'copy-sitrep': copySitrep(); break;
      case 'fill-sitrep-dtg': fillSitrepDTG(); break;
      case 'generate-ai-sitrep': generateAISitrep(); break;
      case 'copy-cipher-output': copyCipherOutput(); break;
      case 'generate-aar': generateAAR(); break;
      case 'copy-aar': copyAAR(); break;
      case 'add-cal-entry': addCalEntry(); break;
      case 'add-fep-member': addFEPMember(); break;
      case 'delete-fep-member': deleteFEPMember(Number(control.dataset.fepMemberId)); break;
      case 'open-skill-form': openSkillForm(); break;
      case 'close-skill-form': closeSkillForm(); break;
      case 'save-skill': saveSkill(); break;
      case 'seed-default-skills': seedDefaultSkills(); break;
      case 'filter-skills': renderSkills(control.dataset.skillCategory || null); break;
      case 'edit-skill': editSkill(Number(control.dataset.skillId)); break;
      case 'delete-skill': deleteSkill(Number(control.dataset.skillId)); break;
      case 'open-ammo-form': openAmmoForm(); break;
      case 'close-ammo-form': closeAmmoForm(); break;
      case 'save-ammo': saveAmmo(); break;
      case 'edit-ammo': editAmmo(Number(control.dataset.ammoId)); break;
      case 'delete-ammo': deleteAmmo(Number(control.dataset.ammoId)); break;
      case 'open-community-form': openCommunityForm(); break;
      case 'close-community-form': closeCommunityForm(); break;
      case 'save-community': saveCommunity(); break;
      case 'edit-community': editCommunity(Number(control.dataset.communityId)); break;
      case 'delete-community': deleteCommunity(Number(control.dataset.communityId)); break;
      case 'show-add-peer-form': showAddPeerForm(); break;
      case 'hide-add-peer-form': hideAddPeerForm(); break;
      case 'submit-add-peer': submitAddPeer(); break;
      case 'load-federation-peers': loadFederationPeers(); break;
      case 'load-federation-marketplace': loadFederationMarketplace(); break;
      case 'remove-peer': removePeer(control.dataset.nodeId); break;
      case 'post-federation-offer': postOffer(); break;
      case 'post-federation-request': postRequest(); break;
      case 'log-radiation': logRadiation(); break;
      case 'clear-radiation': clearRadiation(); break;
      case 'open-fuel-form': openFuelForm(); break;
      case 'close-fuel-form': closeFuelForm(); break;
      case 'save-fuel': saveFuel(); break;
      case 'edit-fuel': editFuel(Number(control.dataset.fuelId)); break;
      case 'delete-fuel': deleteFuel(Number(control.dataset.fuelId)); break;
      case 'open-equip-form': openEquipForm(); break;
      case 'close-equip-form': closeEquipForm(); break;
      case 'save-equip': saveEquip(); break;
      case 'edit-equip': editEquip(Number(control.dataset.equipId)); break;
      case 'mark-equip-serviced': markServiced(Number(control.dataset.equipId)); break;
      case 'delete-equip': deleteEquip(Number(control.dataset.equipId)); break;
      case 'load-analytics-dashboard': loadAnalyticsDashboard(); break;
      case 'clear-cal-log': {
        _calLog = [];
        localStorage.removeItem('nomad-cal-log');
        updateCalTracker();
        break;
      }
      case 'load-comms-status-board': loadCommsStatusBoard(); break;
      case 'show-add-freq-form': showAddFreqForm(); break;
      case 'export-chirp-csv': exportChirpCSV(); break;
      case 'play-dtmf-sequence': playDTMFSequence(); break;
      case 'start-phonetic-quiz': startPhoneticQuiz(); break;
      case 'load-propagation': loadPropagation(); break;
      case 'add-ki-person': addKIPerson(); break;
      case 'remove-ki-person': removeKIPerson(Number(control.dataset.kiIndex)); break;
      case 'add-shelter-layer': addShelterLayer(); break;
      case 'remove-shelter-layer': removeShelterLayer(Number(control.dataset.shelterIndex)); break;
      case 'add-crop-row': addCropRow(); break;
      case 'remove-crop-row': removeCropRow(Number(control.dataset.cropIndex)); break;
      case 'create-custom-checklist': createCustomChecklist(); break;
      case 'export-current-checklist': exportCurrentChecklist(); break;
      case 'add-checklist-item': addChecklistItem(); break;
      case 'log-incident': logIncident(); break;
      case 'clear-incidents': clearIncidents(); break;
      case 'show-inv-form': showInvForm(); break;
      case 'voice-add-inventory': voiceAddInventory(); break;
      case 'open-barcode-scanner': openBarcodeScanner(); break;
      case 'open-receipt-scanner': openReceiptScanner(); break;
      case 'open-vision-scanner': openVisionScanner(); break;
      case 'adjust-inv-qty': adjustQty(Number(control.dataset.invId), Number(control.dataset.delta)); break;
      case 'edit-inv-item': editInvItem(Number(control.dataset.invId)); break;
      case 'delete-inv-item': deleteInvItem(Number(control.dataset.invId)); break;
      case 'scan-receipt': scanReceipt(); break;
      case 'clear-receipt-preview': clearReceiptPreview(); break;
      case 'import-receipt-items': importReceiptItems(); break;
      case 'scan-vision-image': scanVisionImage(); break;
      case 'clear-vision-preview': clearVisionPreview(); break;
      case 'import-vision-items': importVisionItems(); break;
      case 'start-barcode-camera': startBarcodeCamera(); break;
      case 'stop-barcode-camera': stopBarcodeCamera(); break;
      case 'show-barcode-db-form': {
        const form = document.getElementById('barcode-add-db-form');
        if (form) form.style.display = 'block';
        break;
      }
      case 'hide-barcode-db-form': {
        const form = document.getElementById('barcode-add-db-form');
        if (form) form.style.display = 'none';
        break;
      }
      case 'add-upc-database': addToUpcDatabase(); break;
      case 'add-barcode-to-inventory': addBarcodeToInventory(control.dataset.upc); break;
      case 'show-inv-quick-add': showInvQuickAdd(); break;
      case 'toggle-template-dropdown': toggleTemplateDropdown(); break;
      case 'show-shopping-list': showShoppingList(); break;
      case 'open-kit-builder': openKitBuilder(); break;
      case 'close-kit-builder': closeKitBuilder(); break;
      case 'generate-kit-plan': generateKitPlan(); break;
      case 'apply-kit-filter': applyKitFilter(); break;
      case 'commit-kit-to-shopping': commitKitToShopping(); break;
      case 'reset-kit-builder': resetKitBuilder(); break;
      case 'quick-add-inv-item': quickAddInvItem({
        name: control.dataset.itemName,
        cat: control.dataset.itemCat,
        unit: control.dataset.itemUnit,
        qty: Number(control.dataset.itemQty),
        daily: Number(control.dataset.itemDaily || 0),
      }, control); break;
      case 'daily-consume': dailyConsume(); break;
      case 'save-inv-item': saveInvItem(); break;
      case 'hide-inv-form': hideInvForm(); break;
      case 'show-contact-form': showContactForm(); break;
      case 'edit-contact': editContact(Number(control.dataset.contactId)); break;
      case 'delete-contact': deleteContact(Number(control.dataset.contactId)); break;
      case 'submit-custom-checklist': submitCustomChecklist(); break;
      case 'submit-checklist-item': submitChecklistItem(); break;
      case 'apply-inventory-template': applyInventoryTemplate(control.dataset.templateName); break;
      case 'add-emergency-numbers': addEmergencyNumbers(); break;
      case 'save-contact': saveContact(); break;
      case 'hide-contact-form': hideContactForm(); break;
      case 'delete-incident': deleteIncident(Number(control.dataset.incidentId)); break;
      case 'delete-journal-entry': deleteJournalEntry(Number(control.dataset.journalEntryId)); break;
      case 'close-scenario': closeScenario(); break;
      case 'cycle-threat': cycleThreat(Number(control.dataset.threatIndex), control.dataset.threatAxis); break;
      case 'cycle-shelter': cycleShelter(Number(control.dataset.shelterIndex)); break;
      case 'cycle-infra': cycleInfra(control.dataset.infraKey); break;
      case 'gs-navigate': gsNavigate(Number(control.dataset.gsStepIndex)); break;
      case 'load-skills-matrix': loadSkillsMatrix(); break;
      case 'add-camera': addCamera(); break;
      case 'toggle-motion-settings-panel': toggleMotionSettingsPanel(); break;
      case 'configure-motion-detection': configureMotionDetection(); break;
      case 'log-access': logAccess(); break;
      case 'clear-access-log': clearAccessLog(); break;
      case 'create-perimeter-zone': createPerimeterZone(); break;
      case 'add-power-device': addPowerDevice(); break;
      case 'log-power-reading': logPowerReading(); break;
      case 'load-sensor-devices': loadSensorDevices(); break;
      case 'load-solar-forecast': loadSolarForecast(); break;
      case 'update-solar-config': updateSolarConfig(); break;
      case 'lookup-garden-zone': lookupZone(); break;
      case 'use-garden-location': {
        if (!navigator.geolocation) {
          toast('Geolocation is unavailable on this device.', 'warning');
          break;
        }
        navigator.geolocation.getCurrentPosition(
          position => {
            const input = document.getElementById('garden-lat');
            if (input) input.value = position.coords.latitude.toFixed(1);
            lookupZone();
          },
          () => toast('Could not get current location.', 'warning'),
          { maximumAge: 60000, timeout: 8000 }
        );
        break;
      }
      case 'show-add-preservation-form': showAddPreservationForm(); break;
      case 'submit-preservation': submitPreservation(); break;
      case 'delete-preservation': deletePreservation(Number(control.dataset.preservationId)); break;
      case 'add-plot': addPlot(); break;
      case 'add-seed': addSeed(); break;
      case 'log-harvest': logHarvest(); break;
      case 'add-livestock': addLivestock(); break;
      case 'load-triage-board': loadTriageBoard(); break;
      case 'start-tccc-flow': startTCCCFlow(); break;
      case 'tccc-prev': tcccPrev(); break;
      case 'tccc-reset': tcccReset(); break;
      case 'load-medical-supplies': loadMedicalSupplies(); break;
      case 'show-patient-form': showPatientForm(); break;
      case 'add-patient-from-contacts': addPatientFromContacts(); break;
      case 'save-patient': savePatient(); break;
      case 'hide-patient-form': hidePatientForm(); break;
      case 'check-drug-interactions': checkDrugInteractions(); break;
      case 'calculate-dosage': calculateDosage(); break;
      case 'close-vitals-panel': closeVitalsPanel(); break;
      case 'log-vitals': logVitals(); break;
      case 'show-wound-form': showWoundForm(); break;
      case 'log-wound': logWound(); break;
      case 'hide-wound-form': hideWoundForm(); break;
      case 'guide-back': guideBack(); break;
      case 'guide-ask-ai': guideAskAI(); break;
      case 'guide-print': guidePrint(); break;
      case 'guide-close': guideClose(); break;
      case 'guide-start-over': if (_currentGuide) startGuide(_currentGuide.id); break;
      case 'start-guide': startGuide(control.dataset.guideId); break;
      case 'start-scenario': startScenario(control.dataset.scenarioId); break;
      case 'choose-guide-node': guideChoose(control.dataset.guideNode); break;
      case 'print-wallet-card': printWalletCard(); break;
      case 'toggle-vault-password': {
        const input = document.getElementById('vault-pw');
        if (!input) break;
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        control.textContent = show ? 'Hide' : 'Show';
        control.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} vault password`);
        break;
      }
      case 'unlock-vault': unlockVault(); break;
      case 'lock-vault': lockVault(); break;
      case 'new-vault-entry': newVaultEntry(); break;
      case 'generate-password': generatePassword(); break;
      case 'save-vault-entry': saveVaultEntry(); break;
      case 'hide-vault-form': hideVaultForm(); break;
      case 'view-vault-entry': viewVaultEntry(Number(control.dataset.vaultId)); break;
      case 'edit-vault-entry': editVaultEntry(Number(control.dataset.vaultId)); break;
      case 'delete-vault-entry': deleteVaultEntry(Number(control.dataset.vaultId), control); break;
      case 'load-zambretti': loadZambretti(); break;
      case 'load-pressure-graph': loadPressureGraph(); break;
      case 'log-weather': logWeather(); break;
      case 'evaluate-weather-rules': evaluateWeatherRules(); break;
      case 'toggle-weather-rule-form': {
        const form = document.getElementById('wx-rule-form');
        if (form) form.style.display = form.style.display === 'none' ? 'block' : 'none';
        break;
      }
      case 'hide-weather-rule-form': {
        const form = document.getElementById('wx-rule-form');
        if (form) form.style.display = 'none';
        break;
      }
      case 'create-weather-rule': createWeatherRule(); break;
      case 'toggle-weather-rule': toggleWeatherRule(Number(control.dataset.weatherRuleId)); break;
      case 'delete-weather-rule': deleteWeatherRule(Number(control.dataset.weatherRuleId)); break;
      case 'add-signal-schedule': addSignalSchedule(); break;
      case 'delete-signal-entry': deleteSignalEntry(Number(control.dataset.signalId)); break;
      case 'load-comms-log': loadCommsLog(); break;
      case 'log-comms': logComms(); break;
      case 'show-ics-tab': showICSTab(control.dataset.icsTab); break;
      case 'print-ics213': printICS213(); break;
      case 'clear-ics213': clearICS213(); break;
      case 'add-ics309-entry': addICS309Entry(); break;
      case 'remove-ics309-entry': removeICS309Entry(Number(control.dataset.ics309Index)); break;
      case 'print-ics309': printICS309(); break;
      case 'clear-ics309': clearICS309(); break;
      case 'add-ics214-entry': addICS214Entry(); break;
      case 'remove-ics214-entry': removeICS214Entry(Number(control.dataset.ics214Index)); break;
      case 'print-ics214': printICS214(); break;
      case 'clear-ics214': clearICS214(); break;
      case 'export-journal': exportJournal(); break;
      case 'submit-journal': submitJournal(); break;
      case 'delete-comms-log': deleteCommsLog(Number(control.dataset.commsLogId)); break;
      case 'delete-freq': deleteFreq(Number(control.dataset.freqId)); break;
      case 'submit-add-freq': submitAddFreq(); break;
      case 'cancel-add-freq-form': document.getElementById('add-freq-form')?.remove(); break;
      case 'delete-perimeter-zone': deletePerimeterZone(Number(control.dataset.zoneId)); break;
      case 'toggle-motion-detection': toggleMotionDetection(Number(control.dataset.cameraId)); break;
      case 'delete-camera': deleteCamera(Number(control.dataset.cameraId)); break;
      case 'delete-power-device': deletePowerDevice(Number(control.dataset.powerDeviceId)); break;
      case 'delete-plot': deletePlot(Number(control.dataset.plotId)); break;
      case 'delete-seed': deleteSeed(Number(control.dataset.seedId)); break;
      case 'log-health-event': logHealthEvent(Number(control.dataset.livestockId)); break;
      case 'submit-health-event': submitHealthEvent(Number(control.dataset.livestockId)); break;
      case 'view-wound-photos': viewWoundPhotos(Number(control.dataset.patientId), Number(control.dataset.woundId)); break;
      case 'prompt-wound-photo': promptWoundPhoto(Number(control.dataset.patientId), Number(control.dataset.woundId)); break;
      case 'add-wound-photo-close': {
        promptWoundPhoto(Number(control.dataset.patientId), Number(control.dataset.woundId));
        closeWoundPhotoModal();
        break;
      }
      case 'delete-livestock': deleteLivestock(Number(control.dataset.livestockId)); break;
      case 'open-vitals-panel': openVitalsPanel(Number(control.dataset.patientId)); break;
      case 'start-tccc': startTCCC(Number(control.dataset.patientId)); break;
      case 'generate-handoff': generateHandoff(Number(control.dataset.patientId)); break;
      case 'edit-patient': editPatient(Number(control.dataset.patientId)); break;
      case 'delete-patient': deletePatient(Number(control.dataset.patientId)); break;
      case 'change-triage-category': changeTriageCategory(Number(control.dataset.patientId), control.dataset.triageCategory); break;
      case 'set-triage-category': setTriageCategory(Number(control.dataset.patientId), control.dataset.triageCategory); break;
      case 'generate-handoff-close-tccc': {
        const patientId = Number(control.dataset.patientId) || _tcccPatientId;
        if (patientId) generateHandoff(patientId);
        closeTCCCModal();
        break;
      }
      case 'close-tccc-modal': closeTCCCModal(); break;
      case 'calc-solar-today': {
        const input = document.getElementById('solar-date');
        if (input) input.value = new Date().toISOString().slice(0, 10);
        calcSolar();
        break;
      }
      case 'get-solar-location': getSolarLocation(); break;
      case 'calc-moon-today': {
        const input = document.getElementById('moon-date');
        if (input) input.value = new Date().toISOString().slice(0, 10);
        calcMoon();
        break;
      }
    }
    return;
  }
  if (control.dataset.sitDomain) {
    cycleSitLevel(control);
    return;
  }
  if (control.dataset.dtmfKey) {
    playDTMF(control.dataset.dtmfKey);
    return;
  }
  if (control.dataset.securityTab) {
    showSecurityTab(control.dataset.securityTab);
    return;
  }
  if (control.dataset.powerTab) {
    showPowerTab(control.dataset.powerTab);
    return;
  }
  if (control.dataset.medRef) {
    loadMedRef(control.dataset.medRef);
    return;
  }
  if (control.dataset.branchSwitch) {
    switchToBranch(Number(control.dataset.branchSwitch), Number(control.dataset.branchConvo || 0) || undefined);
    return;
  }
  if (control.dataset.help !== undefined) { showHelp(control.dataset.help || undefined); return; }
  if (control.dataset.themeSelect) { setTheme(control.dataset.themeSelect); return; }
  if (control.dataset.customizeTheme) { setTheme(control.dataset.customizeTheme); return; }
  if (control.dataset.zoomLevel) { setUIZoom(control.dataset.zoomLevel); return; }
  if (control.dataset.densityLevel) { setDensity(control.dataset.densityLevel); return; }
  if (control.dataset.appFrameUrl) { openAppFrame(control.dataset.appFrameTitle || 'Document', control.dataset.appFrameUrl); return; }
  if (control.dataset.gardenTab) { showGardenTab(control.dataset.gardenTab); return; }
  if (control.dataset.protocolToggle !== undefined) { toggleProtocol(control); return; }
  if (control.dataset.protocolBulk) { toggleAllProtocols(control.dataset.protocolBulk === 'expand'); return; }
  if (control.dataset.modeSelect) { setMode(control.dataset.modeSelect); if (control.dataset.customizeMode !== undefined) updateCustomizeMode(); return; }
  if (control.dataset.prepCategory) { showPrepCategory(control.dataset.prepCategory); return; }
  if (control.dataset.prepSubSwitch) { switchPrepSub(control.dataset.prepSubSwitch); return; }
  if (control.dataset.checklistTemplate) { createChecklist(control.dataset.checklistTemplate); return; }
  if (control.dataset.checklistDelete) { e.stopPropagation(); deleteChecklist(Number(control.dataset.checklistDelete)); return; }
  if (control.dataset.checklistId) { selectChecklist(Number(control.dataset.checklistId)); return; }
  if (control.dataset.checkItem) { toggleCheckItem(Number(control.dataset.checkItem)); return; }
  handleShellNavigation(control);
});

document.addEventListener('keydown', e => {
  if (e.defaultPrevented) return;
  const renameControl = e.target.closest('[data-convo-rename-id]');
  if (renameControl) {
    if (e.key === 'Enter') {
      e.preventDefault();
      renameControl.blur();
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      renameControl.value = '';
      renameControl.blur();
      return;
    }
  }
  if (e.key === 'Enter' && e.ctrlKey) {
    const ctrlEnterControl = e.target.closest('[data-ctrl-enter-action]');
    if (ctrlEnterControl) {
      e.preventDefault();
      if (ctrlEnterControl.dataset.ctrlEnterAction === 'submit-journal') submitJournal();
      return;
    }
  }
  if (e.key === 'Enter') {
    const enterControl = e.target.closest('[data-enter-action]');
    if (enterControl) {
      e.preventDefault();
      if (enterControl.dataset.enterAction === 'sync-manual-peer') syncToPeer(enterControl.value.trim());
      if (enterControl.dataset.enterAction === 'ask-copilot') askCopilot();
      if (enterControl.dataset.enterAction === 'search-youtube') searchYouTube();
      if (enterControl.dataset.enterAction === 'send-broadcast') sendBroadcast();
      if (enterControl.dataset.enterAction === 'add-vehicle') addVehicle();
      if (enterControl.dataset.enterAction === 'check-phonetic') checkPhonetic();
      if (enterControl.dataset.enterAction === 'play-dtmf-sequence') playDTMFSequence();
      if (enterControl.dataset.enterAction === 'unlock-vault') unlockVault();
      if (enterControl.dataset.enterAction === 'add-signal-schedule') addSignalSchedule();
      if (enterControl.dataset.enterAction === 'add-ics309-entry') addICS309Entry();
      if (enterControl.dataset.enterAction === 'add-ics214-entry') addICS214Entry();
      if (enterControl.dataset.enterAction === 'log-radiation') logRadiation();
      if (enterControl.dataset.enterAction === 'log-comms') logComms();
      if (enterControl.dataset.enterAction === 'send-lan-msg') sendLanMsg();
      if (enterControl.dataset.enterAction === 'lookup-barcode') lookupBarcode();
      return;
    }
  }
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const keyboardControl = e.target.closest('[data-checklist-id], [data-mode-select][role="button"], [data-tab-target][role="button"], [data-app-frame-url][role="button"], [data-shell-action][role="button"], [data-chat-action][role="button"], [data-note-action][role="button"], [data-media-action][role="button"], [data-library-action][role="button"], [data-map-action][role="button"], [data-branch-switch][role="button"], [data-click-target][role="button"], [data-prep-action][role="button"]');
  if (!keyboardControl) return;
  e.preventDefault();
  keyboardControl.click();
});

document.addEventListener('focusout', e => {
  const renameControl = e.target.closest('[data-convo-rename-id]');
  if (!renameControl) return;
  finishRename(Number(renameControl.dataset.convoRenameId), renameControl);
});

document.addEventListener('dblclick', e => {
  const control = e.target.closest('[data-chat-dblclick]');
  if (!control) return;
  if (control.dataset.chatDblclick === 'rename-conversation') {
    e.preventDefault();
    renameConvo(Number(control.dataset.convoId));
  }
});

document.addEventListener('change', e => {
  const control = e.target.closest('[data-change-action]');
  if (!control) return;
  switch (control.dataset.changeAction) {
    case 'apply-preset': applyPreset(); break;
    case 'filter-convo-tag': _convoTagFilter = control.value || ''; renderConvoList(); break;
    case 'toggle-kb': toggleKB(); break;
    case 'upload-kb-file': uploadKBFile(); break;
    case 'handle-chat-file-select': handleChatFileSelect(); break;
    case 'preview-chat-image': previewChatImage(); break;
    case 'toggle-sidebar-item': toggleSidebarItem(control); break;
    case 'toggle-home-section': toggleHomeSection(control); break;
    case 'upload-media-files': uploadMediaFiles(); break;
    case 'upload-pdf': uploadPDF(); break;
    case 'set-language': NomadI18n.setLanguage(control.value); break;
    case 'load-activity': loadActivity(); break;
    case 'change-media-sort': changeMediaSort(); break;
    case 'filter-channels': filterChannels(); break;
    case 'set-media-speed': setMediaSpeed(control.value); break;
    case 'import-gpx-file': importGpxFile(control); break;
    case 'map-tile-source': setMapTileSource(control.value); break;
    case 'import-checklist-json': importChecklistJSON(); break;
    case 'load-incidents': loadIncidents(); break;
    case 'load-inventory': loadInventory(); break;
    case 'import-inv-csv': importInvCSV(); break;
    case 'handle-receipt-file-select': handleReceiptFileSelect(control); break;
    case 'toggle-receipt-items': toggleAllReceiptItems(control.checked); break;
    case 'handle-vision-file-select': handleVisionFileSelect(control); break;
    case 'import-contacts-csv': importContactsCSV(); break;
    case 'filter-freq-table': filterFreqTable(); break;
    case 'update-power-spec-fields': updatePowerSpecFields(); break;
    case 'load-sensor-chart': loadSensorChart(); break;
    case 'save-auto-backup': saveAutoBackup(); break;
    case 'save-voice-prefs': saveVoicePrefs(); break;
    case 'toggle-startup': toggleStartup(); break;
    case 'toggle-notifications': toggleNotifications(); break;
    case 'import-config': importConfig(); break;
    case 'import-sync-pack': importSyncPack(); break;
    case 'update-peer-trust': updatePeerTrust(control.dataset.nodeId, control.value); break;
    case 'import-dead-drop': importDeadDrop(); break;
    case 'load-log-viewer': loadLogViewer(); break;
    case 'load-service-logs': loadServiceLogs(); break;
    case 'configure-auto-backup': configureAutoBackup(); break;
    case 'toggle-backup-encryption': {
      const wrap = document.getElementById('ab-pw-wrap');
      if (wrap) wrap.style.display = control.checked ? 'block' : 'none';
      configureAutoBackup();
      break;
    }
    case 'restore-upload': restoreFromUpload(); break;
    case 'preview-csv-import': previewCSVImport(); break;
    case 'switch-lan-channel': switchLanChannel(); break;
    case 'run-cipher': runCipher(); break;
    case 'calc-bleach': calcBleach(); break;
    case 'calc-water': calcWater(); break;
    case 'calc-travel': calcTravel(); break;
    case 'calc-battery': calcBattery(); break;
    case 'calc-ballistics': calcBallistics(); break;
    case 'calc-pasture-rotation': calcPastureRotation(); break;
    case 'calc-natural-building': calcNaturalBuilding(); break;
    case 'calc-fallout': calcFallout(); break;
    case 'calc-canning': calcCanning(); break;
    case 'calc-burn-area': calcBurnArea(); break;
    case 'calc-iv-drip': calcIVDrip(); break;
    case 'calc-shelter-pf': calcShelterPF(); break;
    case 'calc-nvis': calcNVIS(); break;
    case 'calc-weight-dose': calcWeightDose(); break;
    case 'calc-hypothermia': calcHypothermia(); break;
    case 'calc-ort': calcORT(); break;
    case 'calc-abx-inventory': calcAbxInventory(); break;
    case 'calc-rad-dose': calcRadDose(); break;
    case 'calc-water-needs': calcWaterNeeds(); break;
    case 'calc-generator': calcGenerator(); break;
    case 'calc-dehydration': calcDehydration(); break;
    case 'calc-vitals': calcVitals(); break;
    case 'calc-antenna': calcAntenna(); break;
    case 'convert-unit': convertUnit(); break;
    case 'show-plant-zone': showPlantZone(); break;
    case 'show-phrases': showPhrases(); break;
    case 'calc-bob': calcBOB(); break;
    case 'wiz-toggle-custom': wizToggleCustom(control.dataset.wizCustomType, control.dataset.wizCustomValue, control.checked); break;
    case 'toggle-home-security': toggleHomeSecurity(control.dataset.homeSecurityKey, control.checked); break;
    case 'update-widget-field': updateWidgetField(control.dataset.widgetId, control.dataset.widgetField, control.type === 'checkbox' ? control.checked : control.value); break;
    case 'calc-plan': calcPlan(); break;
    case 'calc-food-storage': calcFoodStorage(); break;
    case 'calc-gen-fuel': calcGenFuel(); break;
    case 'calc-rainwater': calcRainwater(); break;
    case 'calc-radio-range': calcRadioRange(); break;
    case 'calc-med-dose': calcMedDose(); break;
    case 'calc-solar-size': calcSolarSize(); break;
    case 'update-ki-person': {
      const index = Number(control.dataset.kiIndex);
      const field = control.dataset.kiField;
      if (Number.isNaN(index) || !field || !_kiPersons[index]) break;
      _kiPersons[index][field] = control.value;
      calcKIDosage();
      break;
    }
    case 'update-shelter-layer': {
      const index = Number(control.dataset.shelterIndex);
      const field = control.dataset.shelterField;
      if (Number.isNaN(index) || !field || !_shelterLayers[index]) break;
      _shelterLayers[index][field] = field === 'thickness' ? (parseFloat(control.value) || 1) : control.value;
      calcShelterPF();
      break;
    }
    case 'update-crop-row': {
      const index = Number(control.dataset.cropIndex);
      const field = control.dataset.cropField;
      if (Number.isNaN(index) || !field || !_cropRows[index]) break;
      _cropRows[index][field] = field === 'sqft' ? (parseFloat(control.value) || 0) : control.value;
      calcCropCalories();
      break;
    }
  }
});

document.addEventListener('input', e => {
  const control = e.target.closest('[data-input-action]');
  if (!control) return;
  if (control.dataset.inputAction === 'filter-convos') {
    filterConvos();
    return;
  }
  if (control.dataset.inputAction === 'debounce-search') {
    debounceSearch();
    return;
  }
  if (control.dataset.inputAction === 'geocode-search') {
    geocodeSearch(control.value);
    return;
  }
  if (control.dataset.inputAction === 'save-fep') {
    saveFEP();
    return;
  }
  if (control.dataset.inputAction === 'filter-notes') {
    filterNotes();
    return;
  }
  if (control.dataset.inputAction === 'filter-media-list') {
    filterMediaList();
    return;
  }
  if (control.dataset.inputAction === 'filter-channels') {
    filterChannels();
    return;
  }
  if (control.dataset.inputAction === 'filter-torrents') {
    filterTorrents();
    return;
  }
  if (control.dataset.inputAction === 'load-inventory') {
    loadInventory();
    return;
  }
  if (control.dataset.inputAction === 'load-contacts') {
    loadContacts();
    return;
  }
  if (control.dataset.inputAction === 'filter-freq-table') {
    filterFreqTable();
    return;
  }
  if (control.dataset.inputAction === 'filter-companions') {
    filterCompanions();
    return;
  }
  if (control.dataset.inputAction === 'run-cipher') {
    runCipher();
    return;
  }
  if (control.dataset.inputAction === 'calc-bleach') {
    calcBleach();
    return;
  }
  if (control.dataset.inputAction === 'update-vehicle-fuel') {
    updateVehicleFuel(Number(control.dataset.vehicleId), control.value);
    return;
  }
  if (control.dataset.inputAction === 'save-ai-name') {
    saveAIName();
    return;
  }
  if (control.dataset.inputAction === 'update-ab-keep-display') {
    const valueEl = document.getElementById('ab-keep-val');
    if (valueEl) valueEl.textContent = control.value;
    return;
  }
  if (control.dataset.inputAction === 'save-lan-chat-name') {
    localStorage.setItem('nomad-lan-name', control.value);
    return;
  }
  if (control.dataset.inputAction === 'update-fep-member') {
    updateFEPMember(Number(control.dataset.fepMemberId), control.dataset.fepMemberField, control.value);
    return;
  }
  if (control.dataset.inputAction === 'calc-horizon') {
    calcHorizon();
    return;
  }
  if (control.dataset.inputAction === 'update-cal-tracker') {
    updateCalTracker();
    return;
  }
  if (control.dataset.inputAction === 'filter-calcs') {
    filterCalcs();
    return;
  }
  if (control.dataset.inputAction === 'filter-protocols') {
    filterProtocols();
    return;
  }
  if (control.dataset.inputAction === 'calc-water') {
    calcWater();
    return;
  }
  if (control.dataset.inputAction === 'calc-food') {
    calcFood();
    return;
  }
  if (control.dataset.inputAction === 'calc-power') {
    calcPower();
    return;
  }
  if (control.dataset.inputAction === 'calc-watch') {
    calcWatch();
    return;
  }
  if (control.dataset.inputAction === 'calc-solar') {
    calcSolar();
    return;
  }
  if (control.dataset.inputAction === 'calc-moon') {
    calcMoon();
    return;
  }
  if (control.dataset.inputAction === 'convert-coords') {
    convertCoords();
    return;
  }
  if (control.dataset.inputAction === 'calc-travel') {
    calcTravel();
    return;
  }
  if (control.dataset.inputAction === 'calc-battery') {
    calcBattery();
    return;
  }
  if (control.dataset.inputAction === 'calc-bob') {
    calcBOB();
    return;
  }
  if (control.dataset.inputAction === 'calc-ballistics') {
    calcBallistics();
    return;
  }
  if (control.dataset.inputAction === 'calc-compost') {
    calcCompost();
    return;
  }
  if (control.dataset.inputAction === 'calc-pasture-rotation') {
    calcPastureRotation();
    return;
  }
  if (control.dataset.inputAction === 'calc-natural-building') {
    calcNaturalBuilding();
    return;
  }
  if (control.dataset.inputAction === 'calc-fallout') {
    calcFallout();
    return;
  }
  if (control.dataset.inputAction === 'calc-canning') {
    calcCanning();
    return;
  }
  if (control.dataset.inputAction === 'calc-burn-area') {
    calcBurnArea();
    return;
  }
  if (control.dataset.inputAction === 'calc-iv-drip') {
    calcIVDrip();
    return;
  }
  if (control.dataset.inputAction === 'calc-dead-reckoning') {
    calcDeadReckoning();
    return;
  }
  if (control.dataset.inputAction === 'calc-crop-calories') {
    calcCropCalories();
    return;
  }
  if (control.dataset.inputAction === 'calc-nvis') {
    calcNVIS();
    return;
  }
  if (control.dataset.inputAction === 'calc-weight-dose') {
    calcWeightDose();
    return;
  }
  if (control.dataset.inputAction === 'calc-hypothermia') {
    calcHypothermia();
    return;
  }
  if (control.dataset.inputAction === 'calc-ort') {
    calcORT();
    return;
  }
  if (control.dataset.inputAction === 'calc-abx-inventory') {
    calcAbxInventory();
    return;
  }
  if (control.dataset.inputAction === 'calc-rad-dose') {
    calcRadDose();
    return;
  }
  if (control.dataset.inputAction === 'calc-water-needs') {
    calcWaterNeeds();
    return;
  }
  if (control.dataset.inputAction === 'calc-generator') {
    calcGenerator();
    return;
  }
  if (control.dataset.inputAction === 'calc-dehydration') {
    calcDehydration();
    return;
  }
  if (control.dataset.inputAction === 'calc-vitals') {
    calcVitals();
    return;
  }
  if (control.dataset.inputAction === 'calc-antenna') {
    calcAntenna();
    return;
  }
  if (control.dataset.inputAction === 'convert-unit') {
    convertUnit();
    return;
  }
  if (control.dataset.inputAction === 'text-to-morse') {
    textToMorse();
    return;
  }
  if (control.dataset.inputAction === 'morse-to-text') {
    morseToText();
    return;
  }
  if (control.dataset.inputAction === 'save-pace') {
    savePace();
    return;
  }
  if (control.dataset.inputAction === 'calc-plan') {
    calcPlan();
    return;
  }
  if (control.dataset.inputAction === 'calc-food-storage') {
    calcFoodStorage();
    return;
  }
  if (control.dataset.inputAction === 'calc-gen-fuel') {
    calcGenFuel();
    return;
  }
  if (control.dataset.inputAction === 'calc-rainwater') {
    calcRainwater();
    return;
  }
  if (control.dataset.inputAction === 'calc-radio-range') {
    calcRadioRange();
    return;
  }
  if (control.dataset.inputAction === 'calc-med-dose') {
    calcMedDose();
    return;
  }
  if (control.dataset.inputAction === 'calc-solar-size') {
    calcSolarSize();
    return;
  }
  if (control.dataset.inputAction === 'update-ki-person') {
    const index = Number(control.dataset.kiIndex);
    const field = control.dataset.kiField;
    if (!Number.isNaN(index) && field && _kiPersons[index]) {
      _kiPersons[index][field] = control.value;
      calcKIDosage();
    }
    return;
  }
  if (control.dataset.inputAction === 'update-shelter-layer') {
    const index = Number(control.dataset.shelterIndex);
    const field = control.dataset.shelterField;
    if (!Number.isNaN(index) && field && _shelterLayers[index]) {
      _shelterLayers[index][field] = field === 'thickness' ? (parseFloat(control.value) || 1) : control.value;
      calcShelterPF();
    }
    return;
  }
  if (control.dataset.inputAction === 'update-crop-row') {
    const index = Number(control.dataset.cropIndex);
    const field = control.dataset.cropField;
    if (!Number.isNaN(index) && field && _cropRows[index]) {
      _cropRows[index][field] = field === 'sqft' ? (parseFloat(control.value) || 0) : control.value;
      calcCropCalories();
    }
    return;
  }
  if (control.dataset.inputAction === 'note-title') {
    autoSaveNote();
    return;
  }
  if (control.dataset.inputAction === 'note-tags') {
    autoSaveNoteTags();
    return;
  }
  if (control.dataset.inputAction === 'note-content') {
    autoSaveNote();
    updateNotePreview();
    updateNoteWordCount();
    return;
  }
  if (control.dataset.inputAction === 'save-builder-tag') {
    saveBuilderTag();
  }
});

function _isVisibleForLayout(el) {
  if (typeof isShellVisible === 'function') return isShellVisible(el);
  return !!el && getComputedStyle(el).display !== 'none';
}

function _visibleLayoutHeight(el) {
  if (!_isVisibleForLayout(el)) return 0;
  return el.getBoundingClientRect().height;
}

function syncViewportChrome() {
  const root = document.documentElement;
  const broadcast = document.getElementById('broadcast-banner');
  const alertBar = document.getElementById('alert-bar');
  const statusStrip = document.getElementById('status-strip');
  let topOffset = 0;
  const broadcastHeight = _visibleLayoutHeight(broadcast);

  if (broadcast && broadcastHeight > 0) {
    broadcast.style.top = '0px';
    topOffset += broadcastHeight;
  }
  root.style.setProperty('--alert-bar-offset', `${broadcastHeight}px`);

  if (alertBar) {
    alertBar.style.top = `${topOffset}px`;
    topOffset += _visibleLayoutHeight(alertBar);
  }

  if (statusStrip) statusStrip.style.top = `${topOffset}px`;
  root.style.setProperty('--stacked-top-offset', `${topOffset}px`);

  const copilotDock = document.getElementById('copilot-dock');
  const copilotHeight = _visibleLayoutHeight(copilotDock);

  if (copilotDock) {
    copilotDock.style.bottom = '0px';
  }

  const bottomClearance = Math.max(88, copilotHeight + 28);
  root.style.setProperty('--app-bottom-clearance', `${bottomClearance}px`);
  root.style.setProperty('--floating-fab-bottom', `${copilotHeight + 20}px`);
  root.style.setProperty('--floating-panel-bottom', `${copilotHeight + 80}px`);
}

let _viewportChromeSyncQueued = false;

function scheduleViewportChromeSync() {
  if (_viewportChromeSyncQueued) return;
  _viewportChromeSyncQueued = true;
  requestAnimationFrame(() => {
    _viewportChromeSyncQueued = false;
    syncViewportChrome();
  });
}

const _chromeObserver = new MutationObserver(() => {
  scheduleViewportChromeSync();
});

['broadcast-banner', 'alert-bar', 'status-strip', 'copilot-dock'].forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    _chromeObserver.observe(el, {
      attributes: true,
      attributeFilter: ['class', 'style', 'hidden'],
      childList: true,
      subtree: true,
      characterData: true,
    });
  }
});

window.addEventListener('resize', scheduleViewportChromeSync);
scheduleViewportChromeSync();

document.addEventListener('focusin', e => {
  if (e.target.id === 'copilot-input') {
    document.getElementById('copilot-dock')?.classList.add('focused');
  }
  if (e.target.id === 'unified-search') {
    showSearchResults();
  }
});

document.addEventListener('focusout', e => {
  if (e.target.id === 'copilot-input') {
    document.getElementById('copilot-dock')?.classList.remove('focused');
  }
  if (e.target.id === 'unified-search') {
    setTimeout(() => hideSearchResults(), 200);
  }
});

const chatInput = document.getElementById('chat-input');
if (chatInput) {
  chatInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendChat();
    }
  });
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });
}

const chatInputArea = document.getElementById('chat-input-area');
if (chatInputArea) {
  chatInputArea.addEventListener('dragover', event => event.preventDefault());
  chatInputArea.addEventListener('drop', handleChatDrop);
}

const mapSearchInput = document.getElementById('map-search-input');
if (mapSearchInput) {
  mapSearchInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      searchMap();
    }
  });
}

const incidentDescInput = document.getElementById('inc-desc');
if (incidentDescInput) {
  incidentDescInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      logIncident();
    }
  });
}
