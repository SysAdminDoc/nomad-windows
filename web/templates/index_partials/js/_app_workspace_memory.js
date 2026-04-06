const WORKSPACE_RESUME_STORAGE_KEY = 'nomad-workspace-resume-v2';
const WORKSPACE_RESUME_LEGACY_STORAGE_KEY = 'nomad-workspace-resume-v1';
const WORKSPACE_RESUME_SETTINGS_KEY = 'workspace_memory';
const WORKSPACE_RESUME_LIMIT = 6;
const WORKSPACE_RESUME_SYNC_DEBOUNCE_MS = 280;
const WORKSPACE_TAB_META = {
  'situation-room': {label: 'Situation Room', icon: '&#127760;', summary: 'Global briefing, map, watchlists, and analyst posture.'},
  services: {label: 'Home', icon: '&#127968;', summary: 'Snapshot, work modes, services, and printable documents.'},
  readiness: {label: 'Readiness', icon: '&#128202;', summary: 'Score risk, review gaps, and decide what to do next.'},
  preparedness: {label: 'Preparedness', icon: '&#9878;', summary: 'Work checklists, incidents, supplies, and field lanes.'},
  maps: {label: 'Maps', icon: '&#128506;', summary: 'Manage regional downloads, routes, and atlas work.'},
  'kiwix-library': {label: 'Library', icon: '&#128214;', summary: 'Open offline reference, documents, and shelf management.'},
  notes: {label: 'Notes', icon: '&#9997;', summary: 'Capture working notes, templates, and backlinks.'},
  media: {label: 'Media', icon: '&#9654;', summary: 'Manage channels, downloads, books, and offline media.'},
  'ai-chat': {label: 'Copilot', icon: '&#129302;', summary: 'Draft, synthesize, and work with the local assistant.'},
  tools: {label: 'Tools', icon: '&#128295;', summary: 'Open drills, scenarios, utilities, and off-grid comms.'},
  settings: {label: 'Settings', icon: '&#9881;', summary: 'Tune models, tasks, backups, and platform behavior.'},
  benchmark: {label: 'Diagnostics', icon: '&#128200;', summary: 'Measure performance, run tests, and review trends.'},
};
const MEDIA_SUB_META = {
  videos: {label: 'Video Library'},
  audio: {label: 'Audio Library'},
  books: {label: 'Book Reader'},
  torrents: {label: 'Torrent Queue'},
  channels: {label: 'Channel Browser'},
};
const WORKSPACE_GROUP_LABELS = {
  'situation-room': 'Briefing',
  services: 'Briefing',
  readiness: 'Briefing',
  preparedness: 'Operations',
  maps: 'Operations',
  tools: 'Operations',
  'kiwix-library': 'Knowledge',
  notes: 'Knowledge',
  media: 'Knowledge',
  'ai-chat': 'Assistant',
  settings: 'System',
  benchmark: 'System',
};
let _workspaceContextActionItems = [];
let _workspaceInspectorActionItems = [];
let _workspaceInspectorTarget = '';
let _workspaceResumeStateCache = null;
let _workspaceResumeHydrationPromise = null;
let _workspaceResumeSyncTimer = null;
let _workspaceResumeSyncForce = false;
let _workspaceResumeHasServerState = false;
let _commandPalettePreviewActions = [];

function humanizeWorkspaceSlug(value) {
  return String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function getPreparednessResumeMeta(sub) {
  try {
    if (typeof getPrepWorkspaceMeta === 'function') return getPrepWorkspaceMeta(sub);
  } catch (error) {
    // Preparedness metadata may still be initializing later in the shared bundle.
  }
  return {
    id: sub,
    laneLabel: 'Preparedness',
    label: humanizeWorkspaceSlug(sub),
    icon: '&#9878;',
    summary: 'Resume preparedness work.',
  };
}

function getWorkspaceGroupLabel(tab) {
  return WORKSPACE_GROUP_LABELS[tab] || 'Workspace';
}

function buildWorkspaceResumeEntry() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'situation-room';
  if (activeTab === 'services') return null;

  const tabMeta = WORKSPACE_TAB_META[activeTab] || {label: humanizeWorkspaceSlug(activeTab), icon: '&#8250;', summary: 'Resume workspace.'};

  if (activeTab === 'preparedness') {
    const prepSub = document.querySelector('.prep-sub.active')?.id?.replace('psub-', '') || 'checklists';
    const prepMeta = getPreparednessResumeMeta(prepSub);
    return {
      key: `preparedness:${prepSub}`,
      tab: 'preparedness',
      prep: prepSub,
      title: `Preparedness · ${prepMeta.label}`,
      subtitle: `${prepMeta.laneLabel} · ${prepMeta.summary}`,
      icon: prepMeta.icon || tabMeta.icon,
      badge: prepMeta.laneLabel,
    };
  }

  if (activeTab === 'media' && typeof _mediaSub !== 'undefined') {
    const mediaSub = _mediaSub || 'videos';
    const mediaMeta = MEDIA_SUB_META[mediaSub] || {label: humanizeWorkspaceSlug(mediaSub)};
    return {
      key: `media:${mediaSub}`,
      tab: 'media',
      media: mediaSub,
      title: `Media · ${mediaMeta.label}`,
      subtitle: tabMeta.summary,
      icon: tabMeta.icon,
      badge: 'Media',
    };
  }

  if (activeTab === 'situation-room') {
    try {
      const desk = (typeof _sitroomDeskPreset !== 'undefined' && _sitroomDeskPreset) ? _sitroomDeskPreset : 'executive';
      const view = (typeof _sitroomView !== 'undefined' && _sitroomView) ? _sitroomView : 'topline';
      const region = (typeof _sitroomRegionPreset !== 'undefined' && _sitroomRegionPreset) ? _sitroomRegionPreset : 'global';
      return {
        key: `situation-room:${view}:${desk}:${region}`,
        tab: 'situation-room',
        sr_view: view,
        sr_desk: desk,
        sr_region: region,
        sr_news: (typeof _sitroomNewsGroup !== 'undefined' && _sitroomNewsGroup) ? _sitroomNewsGroup : 'all',
        sr_layers: (typeof _sitroomLayerPreset !== 'undefined' && _sitroomLayerPreset) ? _sitroomLayerPreset : 'crisis',
        sr_brief: (typeof _sitroomBriefMode !== 'undefined' && _sitroomBriefMode) ? _sitroomBriefMode : 'morning',
        title: `Situation Room · ${humanizeWorkspaceSlug(view)}`,
        subtitle: `${humanizeWorkspaceSlug(desk)} desk · ${humanizeWorkspaceSlug(region)}`,
        icon: tabMeta.icon,
        badge: 'Briefing',
      };
    } catch (_e) {
      return { key: 'situation-room:topline:executive:global', tab: 'situation-room', title: 'Situation Room', subtitle: 'Executive desk', icon: tabMeta.icon, badge: 'Briefing' };
    }
  }

  return {
    key: activeTab,
    tab: activeTab,
    title: tabMeta.label,
    subtitle: tabMeta.summary,
    icon: tabMeta.icon,
    badge: activeTab === 'ai-chat' ? 'Assistant' : activeTab === 'benchmark' ? 'System' : 'Workspace',
  };
}

function buildWorkspaceContextDescriptor() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'situation-room';
  const tabMeta = WORKSPACE_TAB_META[activeTab] || {label: humanizeWorkspaceSlug(activeTab), summary: 'Resume workspace.'};
  const descriptor = {
    group: getWorkspaceGroupLabel(activeTab),
    title: tabMeta.label,
    detail: tabMeta.label,
    summary: tabMeta.summary,
    trackableEntry: buildWorkspaceResumeEntry(),
  };

  if (activeTab === 'services') {
    descriptor.detail = 'Home · Snapshot and work modes';
    descriptor.summary = 'Re-enter work, launch services, and keep documents, activity, and quick-return paths close.';
    descriptor.trackableEntry = null;
    return descriptor;
  }

  if (activeTab === 'preparedness') {
    const prepSub = document.querySelector('.prep-sub.active')?.id?.replace('psub-', '') || 'checklists';
    const prepMeta = getPreparednessResumeMeta(prepSub);
    descriptor.detail = `${prepMeta.laneLabel} · ${prepMeta.label}`;
    descriptor.summary = prepMeta.summary || tabMeta.summary;
    return descriptor;
  }

  if (activeTab === 'media' && typeof _mediaSub !== 'undefined') {
    const mediaMeta = MEDIA_SUB_META[_mediaSub] || {label: humanizeWorkspaceSlug(_mediaSub)};
    descriptor.detail = `Media · ${mediaMeta.label}`;
    descriptor.summary = `${mediaMeta.label} inside the offline media workspace.`;
    return descriptor;
  }

  if (activeTab === 'situation-room') {
    try {
      const view = (typeof _sitroomView !== 'undefined' && _sitroomView) ? _sitroomView : 'topline';
      const desk = (typeof _sitroomDeskPreset !== 'undefined' && _sitroomDeskPreset) ? _sitroomDeskPreset : 'executive';
      const region = (typeof _sitroomRegionPreset !== 'undefined' && _sitroomRegionPreset) ? _sitroomRegionPreset : 'global';
      const brief = (typeof _sitroomBriefMode !== 'undefined' && _sitroomBriefMode) ? _sitroomBriefMode : 'morning';
      descriptor.detail = `${humanizeWorkspaceSlug(view)} · ${humanizeWorkspaceSlug(desk)} desk · ${humanizeWorkspaceSlug(region)}`;
      descriptor.summary = `${humanizeWorkspaceSlug(brief)} briefing mode with live map, watchlists, and analyst posture.`;
    } catch (_e) {
      descriptor.detail = 'Situation Room · Executive desk';
      descriptor.summary = 'Morning briefing mode with live map, watchlists, and analyst posture.';
    }
    return descriptor;
  }

  if (activeTab === 'ai-chat') {
    descriptor.detail = 'Copilot · Local drafting and analysis';
    return descriptor;
  }

  if (activeTab === 'benchmark') {
    descriptor.detail = 'Diagnostics · Performance and system health';
    return descriptor;
  }

  if (activeTab === 'settings') {
    descriptor.detail = 'System · Models, sync, backup, and desk memory';
    return descriptor;
  }

  return descriptor;
}

function getActiveWorkspaceGuideKey() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'situation-room';
  return activeTab;
}

function focusWorkspaceElement(id) {
  const element = document.getElementById(id);
  if (!element) return;
  if (typeof element.focus === 'function') element.focus();
  if (typeof element.select === 'function' && /input|textarea/i.test(element.tagName)) element.select();
}

function activateWorkspaceGuideAction(run) {
  closeWorkspaceInspector();
  setTimeout(() => {
    if (typeof run === 'function') run();
  }, 40);
}

function buildWorkspaceGuideBodyHtml(guide) {
  const sections = Array.isArray(guide?.sections) ? guide.sections : [];
  const spotlight = guide?.spotlight
    ? `<div class="workspace-inspector-spotlight">${escapeHtml(guide.spotlight)}</div>`
    : '';
  if (!sections.length) return `${spotlight}<div class="workspace-inspector-section"><div class="workspace-inspector-list"><div class="workspace-inspector-item"><span class="workspace-inspector-item-dot" aria-hidden="true"></span><span>Use the quick actions above to move directly into the next useful step.</span></div></div></div>`;
  return spotlight + sections.map(section => {
    const items = Array.isArray(section?.items) ? section.items : [];
    return `
      <section class="workspace-inspector-section">
        <h3 class="workspace-inspector-section-title">${escapeHtml(section.title || 'Guide')}</h3>
        <div class="workspace-inspector-list">
          ${items.map(item => `<div class="workspace-inspector-item"><span class="workspace-inspector-item-dot" aria-hidden="true"></span><span>${escapeHtml(String(item))}</span></div>`).join('')}
        </div>
      </section>
    `;
  }).join('');
}

function buildWorkspaceGuideConfig(target = '') {
  const key = target || getActiveWorkspaceGuideKey();
  const descriptor = buildWorkspaceContextDescriptor();
  const contextActions = getWorkspaceContextActions();
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'situation-room';
  const baseGuide = {
    target: key,
    kicker: 'WORKSPACE GUIDE',
    title: descriptor.title,
    meta: descriptor.detail || descriptor.title,
    summary: descriptor.summary || 'Use this workspace to orient, act, and return without losing context.',
    spotlight: '',
    sections: [],
    actions: contextActions.slice(0, 3).map((item, index) => ({
      label: item.label,
      run: item.run,
      primary: index === 0,
    })),
  };

  if (key === 'services') {
    return {
      ...baseGuide,
      title: 'Home · Mission Control',
      meta: 'Briefing · Launch deck · Resume work',
      summary: 'Use Home to re-enter real work quickly, not to browse the whole product again.',
      spotlight: 'Best first move: reopen a live desk from Continue Working before scanning the rest of the shell.',
      sections: [
        {
          title: 'Look Here First',
          items: [
            'Continue Working brings back the desks and sub-workspaces you were actually using.',
            'Work Modes are the fastest way to pick a lane when you know the kind of task but not the exact tool.',
            'The live dashboard is for status and drift, not for deep work.',
          ],
        },
        {
          title: 'Use Home When',
          items: [
            'You need to resume a task after stepping away.',
            'You are orienting before deciding whether the next move is Briefing, Operations, Knowledge, Assistant, or System.',
            'You need printable documents, recent activity, or a fast path back into the desk.',
          ],
        },
      ],
      actions: [
        {
          label: 'Open Continue Working',
          run: () => scrollToSection('home-continue-panel'),
          primary: true,
        },
        ...baseGuide.actions.slice(0, 2),
      ],
    };
  }

  if (key === 'readiness') {
    return {
      ...baseGuide,
      title: 'Readiness · Decide What Breaks First',
      meta: 'Briefing · Gap review · Next moves',
      summary: 'Readiness is where you decide what needs attention next, then jump into the operating lane that resolves it.',
      spotlight: 'Use Readiness when you need prioritization, not when you already know the tool you want.',
      sections: [
        {
          title: 'What This Space Does',
          items: [
            'Shows where posture is weak enough to matter.',
            'Frames next moves so you can go from score to action without a second navigation pass.',
            'Keeps the readiness conversation focused on risk, not inventory trivia.',
          ],
        },
        {
          title: 'Best Next Moves',
          items: [
            'Jump into Preparedness if the gap needs execution.',
            'Use Copilot when you need a plan or a decision aid before acting.',
            'Come back here after changes to confirm the posture improved.',
          ],
        },
      ],
    };
  }

  if (key === 'preparedness') {
    const prepSub = document.querySelector('.prep-sub.active')?.id?.replace('psub-', '') || 'checklists';
    const prepMeta = getPreparednessResumeMeta(prepSub);
    return {
      ...baseGuide,
      title: `Preparedness · ${prepMeta.label}`,
      meta: `${prepMeta.laneLabel} lane`,
      summary: prepMeta.summary || 'Operate inside the lane that matches the situation you are managing.',
      spotlight: `Stay inside ${prepMeta.laneLabel} until the problem changes. The lane is the filter that keeps this workspace from becoming a warehouse.`,
      sections: [
        {
          title: 'Stay Oriented',
          items: [
            'Resume Work and Pinned Workspaces are the fastest way back into the sub-workspace that matters.',
            'Lane copy explains why these tools belong together, so you can move by situation instead of feature history.',
            'Use the shell context bar when you need to hop sideways without losing the current desk.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Coordinate when work needs sequencing, ownership, and handoff.',
            'Sustain when the main question is stock, power, weather, or capability endurance.',
            'Reference & Planning when you need a procedure, calculator, or guide before acting.',
          ],
        },
      ],
      actions: [
        {
          label: 'Resume Last Workspace',
          run: () => document.querySelector('[data-prep-nav-action="resume-last"]')?.click(),
          primary: true,
        },
        {
          label: 'Toggle Pin for Current Workspace',
          run: () => document.querySelector('[data-prep-nav-action="toggle-current-favorite"]')?.click(),
        },
        ...baseGuide.actions.slice(0, 1),
      ],
    };
  }

  if (key === 'maps') {
    return {
      ...baseGuide,
      title: 'Maps · Offline Navigation',
      meta: 'Operations · Download, navigate, print',
      summary: 'Treat Maps like a command room: orient on the live map, then manage regions, routes, and atlas output from the same desk.',
      spotlight: 'The map is the primary workspace. Regional downloads and sources are supporting tools, not separate products.',
      sections: [
        {
          title: 'Start Here',
          items: [
            'Use the live map when you need bearings, routes, waypoints, or overlays right now.',
            'Use Download Regional Maps when you are staging terrain for offline use before the network disappears.',
            'Use Alternative Map Sources when the default regional set is not the right fit.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Search first, then save waypoints, routes, or bookmarks once the location matters.',
            'Keep Atlas for deliberate print output rather than routine navigation.',
            'Use the layer controls to reduce noise instead of turning every overlay on at once.',
          ],
        },
      ],
      actions: [
        {
          label: 'Focus Map Search',
          run: () => focusWorkspaceElement('map-search-input'),
          primary: true,
        },
        {
          label: 'Open Regional Downloads',
          run: () => scrollToSection('region-grid'),
        },
        {
          label: 'Browse Map Sources',
          run: () => {
            const catalog = document.getElementById('map-sources-catalog');
            if (catalog?.hidden) document.querySelector('[data-map-action="toggle-map-sources"]')?.click();
            setTimeout(() => scrollToSection('map-sources-catalog'), 160);
          },
        },
      ],
    };
  }

  if (key === 'kiwix-library') {
    return {
      ...baseGuide,
      title: 'Library · Offline Reference Shelf',
      meta: 'Knowledge · Reference, documents, updates',
      summary: 'Use Library to stage durable knowledge: core reference packs, updated ZIM content, and your own field documents.',
      spotlight: 'Think of this as the shelf you trust when connectivity is gone, not a general downloads page.',
      sections: [
        {
          title: 'Look Here First',
          items: [
            'Wikipedia tiers are the fastest way to get useful coverage without overcommitting storage.',
            'Document Library is where your local PDFs, ePubs, and text references stay close at hand.',
            'Check Updates when you want freshness without re-downloading your whole shelf blindly.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Start with Essentials, then add larger shelves only when they solve a real offline need.',
            'Upload the few documents you truly rely on in the field instead of recreating a general filing cabinet.',
            'Use Documents for owned material and ZIM content for broad reference.',
          ],
        },
      ],
      actions: [
        {
          label: 'Get Essentials',
          run: () => {
            if (typeof downloadAllZimsByTier === 'function') downloadAllZimsByTier('essential');
          },
          primary: true,
        },
        {
          label: 'Check Updates',
          run: () => {
            if (typeof checkContentUpdates === 'function') checkContentUpdates();
          },
        },
        {
          label: 'Add Documents',
          run: () => document.getElementById('pdf-upload')?.click(),
        },
      ],
    };
  }

  if (key === 'notes') {
    return {
      ...baseGuide,
      title: 'Notes · Working Memory',
      meta: 'Knowledge · Capture, link, brief',
      summary: 'Use Notes for the active record: decisions, observations, handoff context, and the narrative behind what changed.',
      spotlight: 'A good note here should reduce the amount of explanation needed later, especially under pressure.',
      sections: [
        {
          title: 'Start Here',
          items: [
            'Create a fresh note when the task deserves its own thread.',
            'Use templates when the note needs structure before it needs prose.',
            'Search and backlinks make this a working graph, not a pile of drafts.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Capture decisions and why they were made, not just outcomes.',
            'Keep one note per active thread so later updates have a stable place to land.',
            'Export when something needs to leave the app as a field document or handoff artifact.',
          ],
        },
      ],
      actions: [
        {
          label: 'New Note',
          run: () => {
            if (typeof createNote === 'function') createNote();
          },
          primary: true,
        },
        {
          label: 'Use Template',
          run: () => {
            if (typeof toggleNoteTemplates === 'function') toggleNoteTemplates();
          },
        },
        {
          label: 'Search Notes',
          run: () => focusWorkspaceElement('notes-search'),
        },
      ],
    };
  }

  if (key === 'media') {
    return {
      ...baseGuide,
      title: 'Media · Offline Library Operations',
      meta: 'Knowledge · Collect, organize, resume',
      summary: 'Use Media to turn content intake into an organized local library instead of a queue you keep re-sorting by hand.',
      spotlight: 'Channels are for acquisition, folders are for organization, and downloads are the short-lived state in between.',
      sections: [
        {
          title: 'Look Here First',
          items: [
            'Channels are the best place to pull recurring content into the library.',
            'Books and the reader are for calm long-form use, not queue management.',
            'Downloads are temporary posture; the real win is where content ends up after intake.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Paste a URL when you know exactly what you need.',
            'Use folders and categories so later retrieval is easy without search gymnastics.',
            'Treat catalog and queue as staging areas, not the final home of the content.',
          ],
        },
      ],
      actions: [
        {
          label: 'Browse Channels',
          run: () => openMediaWorkspace('channels'),
          primary: true,
        },
        {
          label: 'Open Books',
          run: () => openMediaWorkspace('books'),
        },
        {
          label: 'View Downloads',
          run: () => {
            openMediaWorkspace('videos');
            setTimeout(() => document.querySelector('[data-media-action="toggle-queue"]')?.click(), 180);
          },
        },
      ],
    };
  }

  if (key === 'ai-chat') {
    return {
      ...baseGuide,
      title: 'Copilot · Local Analysis Desk',
      meta: 'Assistant · Draft, analyze, decide',
      summary: 'Use Copilot when the right move is clearer after planning, synthesis, or a fast local analysis pass.',
      spotlight: 'The strongest use of Copilot is to shorten decision time, not to replace the operating workspaces around it.',
      sections: [
        {
          title: 'Best Use',
          items: [
            'Start a fresh conversation when the task deserves a clean thread.',
            'Use memory, presets, and your local documents when the answer should reflect your actual setup.',
            'Bring a question here after Readiness or Preparedness has already narrowed the problem.',
          ],
        },
        {
          title: 'Avoid',
          items: [
            'Using Copilot as the first stop when the workspace already has a direct action.',
            'Keeping unrelated threads in one conversation when handoff clarity matters.',
            'Treating the model picker as routine workflow; it is setup, not the work itself.',
          ],
        },
      ],
      actions: [
        {
          label: 'New Conversation',
          run: () => document.querySelector('[data-chat-action="new-conversation"]')?.click(),
          primary: true,
        },
        {
          label: 'Focus Prompt',
          run: () => focusWorkspaceElement('chat-input'),
        },
        {
          label: 'Open Memory',
          run: () => document.getElementById('ai-memory-toggle-btn')?.click(),
        },
      ],
    };
  }

  if (key === 'tools') {
    return {
      ...baseGuide,
      title: 'Tools · Active Utilities',
      meta: 'Operations · Drills, scenarios, field utilities',
      summary: 'Use Tools when the task is an active exercise, simulation, or field utility run rather than a long-lived operating record.',
      spotlight: 'This workspace is best when you need to run something live and then get back out with a clear result.',
      sections: [
        {
          title: 'What Belongs Here',
          items: [
            'Drills and scenarios when you are practicing or pressure-testing a response.',
            'Quick utility actions when you need speed more than record-keeping.',
            'Comms and traffic consoles when the work is live, tactical, or time-bound.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Run a drill, finish it, then capture durable takeaways elsewhere if they matter later.',
            'Treat scenario history as training memory, not as your incident log.',
            'Keep live utility use short so this space stays focused on execution.',
          ],
        },
      ],
      actions: [
        {
          label: 'Jump to Drills',
          run: () => scrollToSection('drill-cards'),
          primary: true,
        },
        {
          label: 'Jump to Scenarios',
          run: () => scrollToSection('scenario-selector'),
        },
        {
          label: 'Open Timers',
          run: () => {
            if (typeof toggleTimerPanel === 'function') toggleTimerPanel();
          },
        },
      ],
    };
  }

  if (key === 'settings') {
    return {
      ...baseGuide,
      title: 'Settings · System Control',
      meta: 'System · Modes, health, backup, desk memory',
      summary: 'Use Settings to harden and tune the desk without losing your place in the operating picture.',
      spotlight: 'Treat this as configuration and maintenance, not a place to live while operating.',
      sections: [
        {
          title: 'Start Here',
          items: [
            'Desk Memory is the control room for return paths, launch posture, and pinned desks.',
            'Models, backups, tasks, and system health are the high-value controls that affect daily use.',
            'Preferences should change how the workspace behaves, not become another workspace to manage.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Make a launch desk once you know your routine.',
            'Check health and backups before a deployment, field trip, or heavy change.',
            'Use Settings to reduce friction elsewhere, then get back to the working desk.',
          ],
        },
      ],
      actions: [
        {
          label: 'Open Desk Memory',
          run: () => scrollToSection('settings-memory-current'),
          primary: true,
        },
        {
          label: 'Open Backups',
          run: () => scrollToSection('backup-restore-panel'),
        },
        {
          label: 'Open Models',
          run: () => scrollToSection('model-manager'),
        },
      ],
    };
  }

  if (key === 'benchmark') {
    return {
      ...baseGuide,
      title: 'Diagnostics · Trust Under Load',
      meta: 'System · Performance, trend history',
      summary: 'Use Diagnostics to verify what this machine can actually sustain before you depend on it in the field.',
      spotlight: 'A benchmark is most useful before the machine matters, not after it has already disappointed you.',
      sections: [
        {
          title: 'Best Use',
          items: [
            'Run full diagnostics after hardware changes, major updates, or new model installs.',
            'Use storage and AI-only tests when you need to isolate one performance concern quickly.',
            'Track the history to catch degradation early instead of treating each run as a one-off score.',
          ],
        },
        {
          title: 'Look Here First',
          items: [
            'The hero area is for starting the test and naming the machine.',
            'History matters more than a single score when reliability is the real question.',
            'Send concerns to System Health when the issue looks like operational drift instead of raw performance.',
          ],
        },
      ],
      actions: [
        {
          label: 'Run Full Benchmark',
          run: () => document.querySelector('[data-benchmark-mode="full"]')?.click(),
          primary: true,
        },
        {
          label: 'Storage I/O Test',
          run: () => document.querySelector('[data-benchmark-action="run-storage"]')?.click(),
        },
        {
          label: 'View History',
          run: () => scrollToSection('bench-history'),
        },
      ],
    };
  }

  if (key === 'situation-room') {
    return {
      ...baseGuide,
      title: 'Situation Room · Analyst Desk',
      meta: descriptor.detail || 'Briefing · Live intelligence posture',
      summary: descriptor.summary,
      spotlight: 'Use Situation Room to narrow the picture, not to stare at every signal at once. Pick a desk, a region, and a briefing mode, then work from there.',
      sections: [
        {
          title: 'What To Trust First',
          items: [
            'Topline is for orientation, News Desk is for narrative work, and Map is for geographic posture.',
            'Desk presets are faster than rebuilding context by hand every time.',
            'Watch source freshness and confidence before treating a signal like a decision input.',
          ],
        },
        {
          title: 'Best Use',
          items: [
            'Start with a desk preset or saved watchlist before scrolling the whole canvas.',
            'Use the analyst inspector to stay in context while drilling into a story or country.',
            'Copy or send a desk snapshot when the goal is handoff, not just awareness.',
          ],
        },
      ],
      actions: [
        {
          label: 'Open News Desk',
          run: () => {
            if (typeof _setSitroomView === 'function') _setSitroomView('news');
          },
          primary: true,
        },
        {
          label: 'Run Morning Brief',
          run: () => {
            if (typeof _setSitroomBriefMode === 'function') _setSitroomBriefMode('morning');
            if (typeof _setSitroomView === 'function') _setSitroomView('news');
          },
        },
        {
          label: 'Copy Desk Snapshot',
          run: () => {
            if (typeof _copySitroomDeskSnapshot === 'function') _copySitroomDeskSnapshot();
          },
        },
      ],
    };
  }

  return {
    ...baseGuide,
    spotlight: `Use ${descriptor.title} as the primary workspace and let the shell carry navigation, memory, and quick-return duties.`,
    sections: [
      {
        title: 'How To Use This Space',
        items: [
          'Start with the strongest suggested next move instead of scanning every control.',
          'Use the shell context bar for fast sideways jumps and stable return paths.',
          'Pin desks you revisit often so re-entry gets faster over time.',
        ],
      },
    ],
  };
}

function renderWorkspaceInspector() {
  const inspector = document.getElementById('workspace-inspector');
  const kickerEl = document.getElementById('workspace-inspector-kicker');
  const titleEl = document.getElementById('workspace-inspector-title');
  const metaEl = document.getElementById('workspace-inspector-meta');
  const summaryEl = document.getElementById('workspace-inspector-summary');
  const bodyEl = document.getElementById('workspace-inspector-body');
  const actionsEl = document.getElementById('workspace-inspector-actions');
  const contextGuideBtn = document.getElementById('workspace-context-guide-btn');
  if (!inspector || !kickerEl || !titleEl || !metaEl || !summaryEl || !bodyEl || !actionsEl) return;

  const activeTarget = getActiveWorkspaceGuideKey();
  if (!inspector.hidden && _workspaceInspectorTarget && _workspaceInspectorTarget !== activeTarget) {
    _workspaceInspectorTarget = activeTarget;
  }
  const guide = buildWorkspaceGuideConfig(_workspaceInspectorTarget || activeTarget);
  const isOpen = !inspector.hidden;
  _workspaceInspectorActionItems = Array.isArray(guide?.actions) ? guide.actions : [];

  kickerEl.textContent = guide?.kicker || 'WORKSPACE GUIDE';
  titleEl.textContent = guide?.title || 'Workspace Guide';
  metaEl.textContent = guide?.meta || '';
  summaryEl.textContent = guide?.summary || 'Use this panel for quick orientation and the next best actions in the current workspace.';
  bodyEl.innerHTML = buildWorkspaceGuideBodyHtml(guide);
  actionsEl.innerHTML = _workspaceInspectorActionItems.length
    ? _workspaceInspectorActionItems.map((item, index) => `<button type="button" class="workspace-inspector-action${item.primary ? ' is-primary' : ''}" data-workspace-inspector-action-index="${index}">${escapeHtml(item.label)}</button>`).join('')
    : '';

  if (contextGuideBtn) {
    contextGuideBtn.textContent = isOpen ? 'Hide Guide' : 'Workspace Guide';
    contextGuideBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
  document.querySelectorAll('[data-workspace-guide-target]').forEach(button => {
    button.setAttribute('aria-expanded', isOpen && button.dataset.workspaceGuideTarget === guide.target ? 'true' : 'false');
  });
}

function openWorkspaceInspector(target = '') {
  const inspector = document.getElementById('workspace-inspector');
  if (!inspector) return;
  _workspaceInspectorTarget = target || getActiveWorkspaceGuideKey();
  inspector.hidden = false;
  renderWorkspaceInspector();
}

function closeWorkspaceInspector() {
  const inspector = document.getElementById('workspace-inspector');
  if (!inspector) return;
  inspector.hidden = true;
  renderWorkspaceInspector();
}

function getWorkspaceContextActions() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'situation-room';
  if (activeTab === 'situation-room') {
    return [
      {
        label: 'News Desk',
        run: () => {
          openWorkspaceTab('situation-room');
          setTimeout(() => {
            if (typeof _setSitroomView === 'function') _setSitroomView('news');
          }, 120);
        },
      },
      {
        label: 'Executive Desk',
        run: () => {
          openWorkspaceTab('situation-room');
          setTimeout(() => {
            if (typeof _setSitroomDeskPreset === 'function') _setSitroomDeskPreset('executive');
          }, 120);
        },
      },
      {
        label: 'Morning Brief',
        run: () => {
          openWorkspaceTab('situation-room');
          setTimeout(() => {
            if (typeof _setSitroomBriefMode === 'function') _setSitroomBriefMode('morning');
            if (typeof _setSitroomView === 'function') _setSitroomView('news');
          }, 120);
        },
      },
    ];
  }
  if (activeTab === 'services') {
    return [
      {label: 'Situation Room', run: () => openWorkspaceTab('situation-room')},
      {label: 'Run Operations', run: () => openPreparednessWorkspace('checklists')},
      {label: 'Ask Copilot', run: () => openWorkspaceTab('ai-chat')},
    ];
  }
  if (activeTab === 'readiness') {
    return [
      {label: 'Run Operations', run: () => openPreparednessWorkspace('checklists')},
      {label: 'Review Supplies', run: () => openPreparednessWorkspace('inventory')},
      {label: 'Ask Copilot', run: () => openWorkspaceTab('ai-chat')},
    ];
  }
  if (activeTab === 'preparedness') {
    const prepSub = document.querySelector('.prep-sub.active')?.id?.replace('psub-', '') || 'checklists';
    const actionMap = {
      checklists: [
        {label: 'Incident Log', run: () => openPreparednessWorkspace('incidents')},
        {label: 'Inventory', run: () => openPreparednessWorkspace('inventory')},
        {label: 'Medical', run: () => openPreparednessWorkspace('medical')},
      ],
      inventory: [
        {label: 'Checklists', run: () => openPreparednessWorkspace('checklists')},
        {label: 'Medical', run: () => openPreparednessWorkspace('medical')},
        {label: 'Security', run: () => openPreparednessWorkspace('security')},
      ],
      medical: [
        {label: 'Contacts', run: () => openPreparednessWorkspace('contacts')},
        {label: 'Inventory', run: () => openPreparednessWorkspace('inventory')},
        {label: 'Guides', run: () => openPreparednessWorkspace('guides')},
      ],
      security: [
        {label: 'Checklists', run: () => openPreparednessWorkspace('checklists')},
        {label: 'Inventory', run: () => openPreparednessWorkspace('inventory')},
        {label: 'Guides', run: () => openPreparednessWorkspace('guides')},
      ],
    };
    return actionMap[prepSub] || [
      {label: 'Checklists', run: () => openPreparednessWorkspace('checklists')},
      {label: 'Inventory', run: () => openPreparednessWorkspace('inventory')},
      {label: 'Medical', run: () => openPreparednessWorkspace('medical')},
    ];
  }
  if (activeTab === 'maps') {
    return [
      {label: 'Regional Maps', run: () => scrollToSection('region-grid')},
      {label: 'Map Sources', run: () => scrollToSection('map-sources-catalog')},
      {
        label: 'Search Map',
        run: () => {
          const input = document.getElementById('map-search-input');
          if (input) input.focus();
        },
      },
    ];
  }
  if (activeTab === 'kiwix-library') {
    return [
      {label: 'Wikipedia', run: () => openLibraryWorkspace('wiki-tier-selector')},
      {label: 'Documents', run: () => openLibraryWorkspace('doc-library')},
      {label: 'Catalog', run: () => openLibraryWorkspace('zim-catalog')},
    ];
  }
  if (activeTab === 'notes') {
    return [
      {
        label: 'New Note',
        run: () => {
          if (typeof createNote === 'function') createNote();
        },
      },
      {
        label: 'Templates',
        run: () => {
          if (typeof toggleNoteTemplates === 'function') toggleNoteTemplates();
        },
      },
      {
        label: 'Search Notes',
        run: () => {
          const input = document.getElementById('notes-search');
          if (input) input.focus();
        },
      },
    ];
  }
  if (activeTab === 'media') {
    return [
      {label: 'Channels', run: () => openMediaWorkspace('channels')},
      {
        label: 'Downloads',
        run: () => {
          openMediaWorkspace('videos');
          setTimeout(() => document.querySelector('[data-media-action="toggle-queue"]')?.click(), 220);
        },
      },
      {label: 'Books', run: () => openMediaWorkspace('books')},
    ];
  }
  if (activeTab === 'ai-chat') {
    return [
      {
        label: 'New Conversation',
        run: () => {
          document.querySelector('[data-chat-action="new-conversation"]')?.click();
        },
      },
      {
        label: 'Focus Prompt',
        run: () => {
          const input = document.getElementById('chat-input');
          if (input) input.focus();
        },
      },
      {label: 'Open Notes', run: () => openWorkspaceTab('notes')},
    ];
  }
  if (activeTab === 'tools') {
    return [
      {label: 'Open Timers', run: () => { if (typeof toggleTimerPanel === 'function') toggleTimerPanel(); }},
      {label: 'Quick Actions', run: () => { if (typeof toggleQuickActions === 'function') toggleQuickActions(); }},
      {label: 'Open Readiness', run: () => openWorkspaceTab('readiness')},
    ];
  }
  if (activeTab === 'settings') {
    return [
      {label: 'Desk Memory', run: () => scrollToSection('settings-memory-current')},
      {label: 'Backups', run: () => scrollToSection('backup-restore-panel')},
      {label: 'System Health', run: () => scrollToSection('system-health-panel')},
    ];
  }
  if (activeTab === 'benchmark') {
    return [
      {
        label: 'Run Benchmark',
        run: () => {
          if (typeof runBenchmark === 'function') runBenchmark('full');
        },
      },
      {label: 'History', run: () => scrollToSection('bench-history')},
      {label: 'System Health', run: () => { openWorkspaceTab('settings'); setTimeout(() => scrollToSection('system-health-panel'), 220); }},
    ];
  }
  return [];
}

function normalizeWorkspaceResumeState(raw) {
  const recent = Array.isArray(raw?.recent) ? raw.recent.filter(item => item && item.key && item.tab) : [];
  const pinned = Array.isArray(raw?.pinned) ? raw.pinned.filter(item => item && item.key && item.tab) : [];
  const current = raw?.current && raw.current.key && raw.current.tab ? raw.current : null;
  const launch = raw?.launch && raw.launch.key && raw.launch.tab ? raw.launch : null;
  const updatedAt = Number(raw?.updatedAt) > 0 ? Number(raw.updatedAt) : 0;
  return {
    current,
    launch,
    updatedAt,
    pinned: pinned.slice(0, 5),
    recent: recent.slice(0, WORKSPACE_RESUME_LIMIT),
  };
}

function parseWorkspaceResumeSettingValue(value) {
  if (!value) return normalizeWorkspaceResumeState({});
  if (typeof value === 'string') return normalizeWorkspaceResumeState(safeJsonParse(value, {}));
  if (typeof value === 'object') return normalizeWorkspaceResumeState(value);
  return normalizeWorkspaceResumeState({});
}

function getLocalWorkspaceResumeState() {
  const currentValue = localStorage.getItem(WORKSPACE_RESUME_STORAGE_KEY);
  if (currentValue) {
    return normalizeWorkspaceResumeState(readJsonStorage(localStorage, WORKSPACE_RESUME_STORAGE_KEY, {}));
  }
  return normalizeWorkspaceResumeState(readJsonStorage(localStorage, WORKSPACE_RESUME_LEGACY_STORAGE_KEY, {}));
}

function writeLocalWorkspaceResumeState(state) {
  try {
    localStorage.setItem(WORKSPACE_RESUME_STORAGE_KEY, JSON.stringify(normalizeWorkspaceResumeState(state)));
    localStorage.removeItem(WORKSPACE_RESUME_LEGACY_STORAGE_KEY);
  } catch (error) {
    console.warn('Unable to save workspace resume state', error);
  }
}

function getWorkspaceResumeStateScore(state) {
  return (state?.current ? 4 : 0)
    + (state?.launch ? 3 : 0)
    + ((state?.pinned || []).length * 2)
    + ((state?.recent || []).length);
}

function pickPreferredWorkspaceResumeState(localState, serverState) {
  const localUpdatedAt = Number(localState?.updatedAt || 0);
  const serverUpdatedAt = Number(serverState?.updatedAt || 0);
  if (localUpdatedAt !== serverUpdatedAt) {
    return localUpdatedAt > serverUpdatedAt ? localState : serverState;
  }
  return getWorkspaceResumeStateScore(localState) >= getWorkspaceResumeStateScore(serverState)
    ? localState
    : serverState;
}

function refreshWorkspaceResumeUi() {
  if (typeof renderHomeContinueWorking === 'function') {
    renderHomeContinueWorking();
    if (typeof renderWorkspaceInspector === 'function') renderWorkspaceInspector();
    return;
  }
  if (typeof renderSidebarWorkspaceShelf === 'function') renderSidebarWorkspaceShelf();
  if (typeof renderWorkspaceMemoryPanel === 'function') renderWorkspaceMemoryPanel();
  if (typeof renderWorkspaceContextBar === 'function') renderWorkspaceContextBar();
  if (typeof renderWorkspaceInspector === 'function') renderWorkspaceInspector();
}

async function persistWorkspaceResumeStateToServer(force = false) {
  if (!_workspaceResumeHasServerState && !force) return false;
  try {
    const state = getWorkspaceResumeState();
    await fetch('/api/settings', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({[WORKSPACE_RESUME_SETTINGS_KEY]: JSON.stringify(state)}),
    });
    return true;
  } catch (error) {
    console.warn('Unable to persist workspace memory', error);
    return false;
  }
}

function queueWorkspaceResumeStateSync(force = false) {
  _workspaceResumeSyncForce = _workspaceResumeSyncForce || force;
  clearTimeout(_workspaceResumeSyncTimer);
  _workspaceResumeSyncTimer = setTimeout(() => {
    const useForce = _workspaceResumeSyncForce;
    _workspaceResumeSyncForce = false;
    persistWorkspaceResumeStateToServer(useForce);
  }, WORKSPACE_RESUME_SYNC_DEBOUNCE_MS);
}

async function hydrateWorkspaceResumeState(force = false) {
  if (_workspaceResumeHydrationPromise && !force) return _workspaceResumeHydrationPromise;

  const localState = getLocalWorkspaceResumeState();
  _workspaceResumeStateCache = localState;

  _workspaceResumeHydrationPromise = (async () => {
    try {
      const response = await fetch('/api/settings');
      if (!response.ok) throw new Error(`settings ${response.status}`);
      const settings = await response.json();
      const serverState = parseWorkspaceResumeSettingValue(settings?.[WORKSPACE_RESUME_SETTINGS_KEY]);
      const chosenState = pickPreferredWorkspaceResumeState(localState, serverState);
      const serverSerialized = JSON.stringify(serverState);
      const chosenSerialized = JSON.stringify(chosenState);

      _workspaceResumeHasServerState = true;
      _workspaceResumeStateCache = chosenState;
      writeLocalWorkspaceResumeState(chosenState);

      if (serverSerialized !== chosenSerialized) {
        queueWorkspaceResumeStateSync(true);
      }

      refreshWorkspaceResumeUi();
      return chosenState;
    } catch (error) {
      console.warn('Unable to hydrate workspace memory', error);
      _workspaceResumeHasServerState = false;
      _workspaceResumeStateCache = localState;
      refreshWorkspaceResumeUi();
      return localState;
    }
  })();

  return _workspaceResumeHydrationPromise;
}

function getWorkspaceResumeState() {
  if (_workspaceResumeStateCache) return _workspaceResumeStateCache;
  _workspaceResumeStateCache = getLocalWorkspaceResumeState();
  return _workspaceResumeStateCache;
}

function saveWorkspaceResumeState(state) {
  const normalized = normalizeWorkspaceResumeState({
    ...state,
    updatedAt: Date.now(),
  });
  _workspaceResumeStateCache = normalized;
  writeLocalWorkspaceResumeState(normalized);
  queueWorkspaceResumeStateSync(_workspaceResumeHasServerState);
}

function updateWorkspaceResumeCollection(list, entry, limit) {
  return [entry, ...list.filter(item => item.key !== entry.key)].slice(0, limit);
}

function isPinnedWorkspaceEntry(key) {
  return getWorkspaceResumeState().pinned.some(item => item.key === key);
}

function isLaunchWorkspaceEntry(key) {
  return getWorkspaceResumeState().launch?.key === key;
}

function togglePinnedWorkspaceEntry(key) {
  const state = getWorkspaceResumeState();
  const sourceEntry = [state.current, ...(state.pinned || []), ...(state.recent || [])].find(item => item?.key === key);
  if (!sourceEntry) return false;
  const alreadyPinned = state.pinned.some(item => item.key === key);
  state.pinned = alreadyPinned
    ? state.pinned.filter(item => item.key !== key)
    : updateWorkspaceResumeCollection(state.pinned || [], sourceEntry, 5);
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
  return !alreadyPinned;
}

function getPrimaryWorkspaceResumeEntry(state) {
  return state.current || state.recent[0] || state.pinned[0] || null;
}

function getPreviousWorkspaceResumeEntry(state, currentKey = '') {
  const recentMatch = (state.recent || []).find(item => item.key !== currentKey);
  if (recentMatch) return recentMatch;
  return (state.pinned || []).find(item => item.key !== currentKey) || null;
}

function getLaunchWorkspaceResumeEntry(state) {
  if (!state?.launch?.key) return null;
  const updated = [state.current, ...(state.pinned || []), ...(state.recent || [])].find(item => item?.key === state.launch.key);
  return updated || state.launch;
}

function clearWorkspaceRecentContexts() {
  const state = getWorkspaceResumeState();
  state.recent = [];
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
}

function clearPinnedWorkspaceContexts() {
  const state = getWorkspaceResumeState();
  state.pinned = [];
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
}

function setLaunchWorkspaceEntry(key) {
  const state = getWorkspaceResumeState();
  const sourceEntry = [state.current, ...(state.pinned || []), ...(state.recent || [])].find(item => item?.key === key);
  if (!sourceEntry) return false;
  if (!state.pinned.some(item => item.key === key)) {
    state.pinned = updateWorkspaceResumeCollection(state.pinned || [], sourceEntry, 5);
  }
  state.launch = sourceEntry;
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
  return true;
}

function clearLaunchWorkspaceEntry() {
  const state = getWorkspaceResumeState();
  state.launch = null;
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
}

function recordWorkspaceResumeEntry() {
  const entry = buildWorkspaceResumeEntry();
  const state = getWorkspaceResumeState();
  if (!entry) {
    renderHomeContinueWorking();
    return;
  }
  state.current = entry;
  state.recent = updateWorkspaceResumeCollection(state.recent || [], entry, WORKSPACE_RESUME_LIMIT);
  if (state.pinned.some(item => item.key === entry.key)) {
    state.pinned = updateWorkspaceResumeCollection(state.pinned || [], entry, 5);
  }
  if (state.launch?.key === entry.key) {
    state.launch = entry;
  }
  saveWorkspaceResumeState(state);
  renderHomeContinueWorking();
}

function buildHomeContinueCard(entry, options = {}) {
  const classes = [
    'home-continue-card',
    options.isCurrent ? 'is-current' : '',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const badgeText = options.isLaunch ? 'Launch' : options.isCurrent ? 'Current' : options.isPinned ? 'Pinned' : (entry.badge || 'Recent');
  const badgeClass = [
    'home-continue-badge',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const meta = options.isLaunch
    ? options.isCurrent ? 'Launch + active context' : 'Launch context'
    : options.isCurrent ? 'Latest active context'
      : options.isPinned ? 'Pinned for fast return'
        : 'One click to return';
  return `<button type="button" class="${classes}" data-workspace-resume-key="${escapeAttr(entry.key)}">
    <span class="home-continue-icon" aria-hidden="true">${entry.icon || '&#8250;'}</span>
    <span class="home-continue-body">
      <span class="home-continue-topline">
        <span class="home-continue-title">${escapeHtml(entry.title)}</span>
        <span class="${badgeClass}">${escapeHtml(badgeText)}</span>
      </span>
      <span class="home-continue-copy">${escapeHtml(entry.subtitle || 'Resume workspace')}</span>
      <span class="home-continue-meta">${escapeHtml(meta)}</span>
    </span>
  </button>`;
}

function buildSidebarContextCard(entry, options = {}) {
  const classes = [
    'sidebar-context-card',
    options.isCurrent ? 'is-current' : '',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const badgeText = options.isLaunch ? 'Launch' : options.isCurrent ? 'Current' : options.isPinned ? 'Pinned' : (entry.badge || 'Context');
  const badgeClass = [
    'sidebar-context-badge',
    options.isCurrent ? 'is-current' : '',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const meta = options.isLaunch
    ? options.isCurrent ? 'Launch + live desk' : 'Launch context'
    : options.isCurrent
      ? 'Return to your live desk'
      : options.isPinned
        ? 'Pinned for fast re-entry'
        : 'Saved context';
  return `<button type="button" class="${classes}" data-workspace-resume-key="${escapeAttr(entry.key)}">
    <span class="sidebar-context-topline">
      <span class="sidebar-context-titleline">
        <span class="sidebar-context-icon" aria-hidden="true">${entry.icon || '&#8250;'}</span>
        <span class="sidebar-context-title">${escapeHtml(entry.title)}</span>
      </span>
      <span class="${badgeClass}">${escapeHtml(badgeText)}</span>
    </span>
    <span class="sidebar-context-subtitle">${escapeHtml(entry.subtitle || 'Resume workspace')}</span>
    <span class="sidebar-context-meta">${escapeHtml(meta)}</span>
  </button>`;
}

function buildSettingsMemoryCard(entry, options = {}) {
  const classes = [
    'settings-memory-card-item',
    options.isCurrent ? 'is-current' : '',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const badgeText = options.isLaunch ? 'Launch' : options.isCurrent ? 'Current' : options.isPinned ? 'Pinned' : (entry.badge || 'Context');
  const badgeClass = [
    'settings-memory-item-badge',
    options.isCurrent ? 'is-current' : '',
    options.isPinned ? 'is-pinned' : '',
    options.isLaunch ? 'is-launch' : '',
  ].filter(Boolean).join(' ');
  const meta = options.isLaunch
    ? options.isCurrent ? 'Launch + active return point' : 'Launch context'
    : options.isCurrent
      ? 'Active return point'
      : options.isPinned
        ? 'Pinned for fast re-entry'
        : 'Recent working context';
  return `<button type="button" class="${classes}" data-workspace-resume-key="${escapeAttr(entry.key)}">
    <span class="settings-memory-item-topline">
      <span class="settings-memory-item-titleline">
        <span class="settings-memory-item-icon" aria-hidden="true">${entry.icon || '&#8250;'}</span>
        <span class="settings-memory-item-title">${escapeHtml(entry.title)}</span>
      </span>
      <span class="${badgeClass}">${escapeHtml(badgeText)}</span>
    </span>
    <span class="settings-memory-item-copy">${escapeHtml(entry.subtitle || 'Resume workspace')}</span>
    <span class="settings-memory-item-meta">${escapeHtml(meta)}</span>
  </button>`;
}

function buildWorkspaceContextStateMarkup(current, descriptor, previous) {
  const pills = [];
  if (current?.key) pills.push({label: 'Live Desk', tone: 'current'});
  if (current?.key && isPinnedWorkspaceEntry(current.key)) pills.push({label: 'Pinned', tone: 'pinned'});
  if (current?.key && isLaunchWorkspaceEntry(current.key)) pills.push({label: 'Launch', tone: 'launch'});
  if (!current?.key && descriptor?.group) pills.push({label: `${descriptor.group} Lane`, tone: 'group'});
  if (previous?.key) pills.push({label: 'Previous Ready', tone: 'muted'});
  return pills.map(pill => `<span class="workspace-context-state-pill is-${pill.tone}">${escapeHtml(pill.label)}</span>`).join('');
}

function renderSidebarWorkspaceShelf() {
  const currentEl = document.getElementById('sidebar-context-current');
  const pinnedEl = document.getElementById('sidebar-context-pinned');
  if (!currentEl || !pinnedEl) return;
  const state = getWorkspaceResumeState();
  const current = getPrimaryWorkspaceResumeEntry(state);
  const pinned = (state.pinned || [])
    .filter(item => item.key !== current?.key)
    .slice(0, 3);
  currentEl.innerHTML = current
    ? buildSidebarContextCard(current, {isCurrent: true, isPinned: isPinnedWorkspaceEntry(current.key), isLaunch: isLaunchWorkspaceEntry(current.key)})
    : '<div class="sidebar-empty-state">Your current desk will appear here once you start moving through the workspace.</div>';
  pinnedEl.innerHTML = pinned.length
    ? pinned.map(item => buildSidebarContextCard(item, {isPinned: true, isLaunch: isLaunchWorkspaceEntry(item.key)})).join('')
    : '<div class="sidebar-empty-state">Pin contexts from Home to keep them parked here.</div>';
}

function renderWorkspaceMemoryPanel() {
  const launchLabelEl = document.getElementById('settings-memory-launch-label');
  const currentLabelEl = document.getElementById('settings-memory-current-label');
  const currentCountEl = document.getElementById('settings-memory-pinned-count');
  const recentCountEl = document.getElementById('settings-memory-recent-count');
  const launchEl = document.getElementById('settings-memory-launch');
  const currentEl = document.getElementById('settings-memory-current');
  const pinnedEl = document.getElementById('settings-memory-pinned');
  const recentEl = document.getElementById('settings-memory-recent');
  const pinCurrentBtn = document.getElementById('settings-pin-current-context-btn');
  const launchCurrentBtn = document.getElementById('settings-launch-current-context-btn');
  const openLaunchBtn = document.getElementById('settings-open-launch-context-btn');
  const clearLaunchBtn = document.getElementById('settings-clear-launch-context-btn');
  if (!launchLabelEl || !currentLabelEl || !currentCountEl || !recentCountEl || !launchEl || !currentEl || !pinnedEl || !recentEl || !pinCurrentBtn || !launchCurrentBtn || !openLaunchBtn || !clearLaunchBtn) return;
  const state = getWorkspaceResumeState();
  const current = getPrimaryWorkspaceResumeEntry(state);
  const launch = getLaunchWorkspaceResumeEntry(state);
  const pinned = (state.pinned || []).slice(0, 5);
  const recent = (state.recent || [])
    .filter(item => item.key !== current?.key && !pinned.some(pin => pin.key === item.key))
    .slice(0, 5);
  const currentPinned = current ? pinned.some(item => item.key === current.key) : false;
  const currentLaunch = current && launch ? current.key === launch.key : false;

  launchLabelEl.textContent = launch ? launch.title : 'No launch context';
  currentLabelEl.textContent = current ? current.title : 'No active context yet';
  currentCountEl.textContent = String(pinned.length);
  recentCountEl.textContent = String(state.recent.length);
  launchEl.innerHTML = launch
    ? buildSettingsMemoryCard(launch, {isPinned: true, isCurrent: currentLaunch, isLaunch: true})
    : '<div class="settings-empty-state">Set a launch context to reopen directly into the desk you use most.</div>';
  currentEl.innerHTML = current
    ? buildSettingsMemoryCard(current, {isCurrent: true, isPinned: currentPinned, isLaunch: currentLaunch})
    : '<div class="settings-empty-state">Your active context will appear here as soon as you move beyond Home.</div>';
  pinnedEl.innerHTML = pinned.length
    ? pinned.map(item => buildSettingsMemoryCard(item, {isPinned: true, isCurrent: current?.key === item.key, isLaunch: isLaunchWorkspaceEntry(item.key)})).join('')
    : '<div class="settings-empty-state">Pinned contexts from Home will show up here.</div>';
  recentEl.innerHTML = recent.length
    ? recent.map(item => buildSettingsMemoryCard(item, {isLaunch: isLaunchWorkspaceEntry(item.key)})).join('')
    : '<div class="settings-empty-state">Recent contexts will appear here as you work across tabs and sub-workspaces.</div>';
  pinCurrentBtn.disabled = !current;
  pinCurrentBtn.textContent = currentPinned ? 'Unpin Current Context' : 'Pin Current Context';
  launchCurrentBtn.disabled = !current;
  launchCurrentBtn.textContent = currentLaunch ? 'Current Is Launch Context' : 'Set Launch Context';
  openLaunchBtn.disabled = !launch?.key;
  clearLaunchBtn.disabled = !launch?.key;
}

function renderWorkspaceContextBar() {
  const groupEl = document.getElementById('workspace-context-group');
  const detailEl = document.getElementById('workspace-context-detail');
  const stateEl = document.getElementById('workspace-context-state');
  const previousBtn = document.getElementById('workspace-context-previous-btn');
  const titleEl = document.getElementById('workspace-context-title');
  const summaryEl = document.getElementById('workspace-context-summary');
  const guideBtn = document.getElementById('workspace-context-guide-btn');
  const launchBtn = document.getElementById('workspace-context-launch-btn');
  const pinBtn = document.getElementById('workspace-context-pin-btn');
  const quickActionsEl = document.getElementById('workspace-context-quick-actions');
  if (!groupEl || !detailEl || !stateEl || !previousBtn || !titleEl || !summaryEl || !launchBtn || !pinBtn || !quickActionsEl) return;
  const descriptor = buildWorkspaceContextDescriptor();
  const current = descriptor.trackableEntry;
  const state = getWorkspaceResumeState();
  const previous = getPreviousWorkspaceResumeEntry(state, current?.key || '');
  const launch = getLaunchWorkspaceResumeEntry(state);
  const currentPinned = current ? isPinnedWorkspaceEntry(current.key) : false;
  const currentLaunch = current && launch ? current.key === launch.key : false;
  _workspaceContextActionItems = getWorkspaceContextActions();
  groupEl.textContent = descriptor.group;
  detailEl.textContent = descriptor.detail || descriptor.title;
  stateEl.innerHTML = buildWorkspaceContextStateMarkup(current, descriptor, previous);
  previousBtn.hidden = !previous;
  if (previous) previousBtn.textContent = `Back to ${previous.title}`;
  titleEl.textContent = descriptor.title;
  summaryEl.textContent = descriptor.summary || 'Move through the desk with clear context and stable return paths.';
  quickActionsEl.innerHTML = _workspaceContextActionItems.length
    ? _workspaceContextActionItems
      .map((item, index) => `<button type="button" class="workspace-context-quick-action" data-workspace-context-command-index="${index}">${escapeHtml(item.label)}</button>`)
      .join('')
    : '<span class="workspace-context-actions-empty">Use the command palette or the Home shelf when you need a broader jump.</span>';
  launchBtn.disabled = !current;
  launchBtn.textContent = currentLaunch ? 'Launch Context' : 'Make Launch Desk';
  launchBtn.setAttribute('aria-pressed', current && currentLaunch ? 'true' : 'false');
  pinBtn.disabled = !current;
  pinBtn.textContent = current ? (currentPinned ? 'Unpin Current Context' : 'Pin Current Context') : 'Pin Current Context';
  pinBtn.setAttribute('aria-pressed', current && currentPinned ? 'true' : 'false');
  if (guideBtn) {
    const inspector = document.getElementById('workspace-inspector');
    const guideOpen = !!inspector && !inspector.hidden;
    guideBtn.textContent = guideOpen ? 'Hide Guide' : 'Workspace Guide';
    guideBtn.setAttribute('aria-expanded', guideOpen ? 'true' : 'false');
  }
}

function renderHomeContinueWorking() {
  const summaryEl = document.getElementById('home-continue-summary');
  const gridEl = document.getElementById('home-continue-grid');
  const pinnedEl = document.getElementById('home-pinned-grid');
  const pinCurrentBtn = document.getElementById('home-pin-current-context-btn');
  if (!summaryEl || !gridEl || !pinnedEl || !pinCurrentBtn) return;
  const state = getWorkspaceResumeState();
  if (!state.current && !state.recent.length && !state.pinned.length) {
    summaryEl.textContent = 'Pick up where you left off without rebuilding your mental map.';
    pinnedEl.innerHTML = '<div class="home-continue-empty">Pin your current context to build a personal shelf.</div>';
    gridEl.innerHTML = '<div class="home-continue-empty">Recent workspaces and saved context will appear here as you use the desk.</div>';
    pinCurrentBtn.disabled = true;
    pinCurrentBtn.textContent = 'Pin Current Context';
    pinCurrentBtn.setAttribute('aria-pressed', 'false');
    renderSidebarWorkspaceShelf();
    renderWorkspaceMemoryPanel();
    renderWorkspaceContextBar();
    return;
  }

  const current = getPrimaryWorkspaceResumeEntry(state);
  const pinned = (state.pinned || []).slice(0, 5);
  const others = state.recent.filter(item => item.key !== current?.key && !pinned.some(pin => pin.key === item.key)).slice(0, 5);
  const currentPinned = current ? pinned.some(item => item.key === current.key) : false;
  summaryEl.textContent = current
    ? `Last active context: ${current.title}. Keep frequently used desks pinned so return paths stay stable under pressure.`
    : 'Your recent working contexts are ready to reopen.';
  pinnedEl.innerHTML = pinned.length
    ? pinned.map(item => buildHomeContinueCard(item, {isPinned: true, isCurrent: current?.key === item.key})).join('')
    : '<div class="home-continue-empty">Pin your current context to build a personal shelf.</div>';
  gridEl.innerHTML = [
    current && !currentPinned ? buildHomeContinueCard(current, {isCurrent: true}) : '',
    ...others.map(item => buildHomeContinueCard(item)),
  ].filter(Boolean).join('');
  if (!gridEl.innerHTML) {
    gridEl.innerHTML = '<div class="home-continue-empty">Recent contexts will collect here once you branch out from your pinned desks.</div>';
  }
  pinCurrentBtn.disabled = !current;
  pinCurrentBtn.textContent = currentPinned ? 'Unpin Current Context' : 'Pin Current Context';
  pinCurrentBtn.setAttribute('aria-pressed', currentPinned ? 'true' : 'false');
  renderSidebarWorkspaceShelf();
  renderWorkspaceMemoryPanel();
  renderWorkspaceContextBar();
}

function resumeWorkspaceEntry(key) {
  const state = getWorkspaceResumeState();
  const entry = [state.current, ...(state.pinned || []), ...(state.recent || [])].find(item => item?.key === key);
  if (!entry) return;

  if (entry.tab === 'preparedness' && entry.prep) {
    openPreparednessWorkspace(entry.prep);
    return;
  }
  if (entry.tab === 'media' && entry.media) {
    openMediaWorkspace(entry.media);
    return;
  }
  if (entry.tab === 'situation-room') {
    openWorkspaceTab('situation-room');
    setTimeout(() => {
      if (entry.sr_desk && typeof _setSitroomDeskPreset === 'function') _setSitroomDeskPreset(entry.sr_desk);
      if (entry.sr_view && typeof _setSitroomView === 'function') _setSitroomView(entry.sr_view);
      if (entry.sr_news && typeof _setSitroomNewsGroup === 'function') _setSitroomNewsGroup(entry.sr_news);
      if (entry.sr_region && typeof _setSitroomRegionPreset === 'function') _setSitroomRegionPreset(entry.sr_region);
      if (entry.sr_layers && typeof _setSitroomLayerPreset === 'function') _setSitroomLayerPreset(entry.sr_layers);
      if (entry.sr_brief && typeof _setSitroomBriefMode === 'function') _setSitroomBriefMode(entry.sr_brief);
    }, 220);
    return;
  }
  openWorkspaceTab(entry.tab);
}

function getWorkspaceResumePaletteCommands() {
  const state = getWorkspaceResumeState();
  const current = getPrimaryWorkspaceResumeEntry(state);
  const previous = getPreviousWorkspaceResumeEntry(state, current?.key || '');
  const launch = getLaunchWorkspaceResumeEntry(state);
  const pinned = (state.pinned || []).slice(0, 5).map((entry, index) => ({
    id: `pinned-${entry.key}`,
    section: 'Pinned Contexts',
    title: `Open ${entry.title}`,
    subtitle: entry.subtitle || 'Pinned workspace context',
    keywords: `pinned favorite context ${entry.title} ${entry.subtitle || ''}`,
    icon: entry.icon || '&#8250;',
    meta: 'Pinned',
    priority: 95 - index,
    run: () => resumeWorkspaceEntry(entry.key),
  }));
  const recent = (state.recent || [])
    .filter(entry => !(state.pinned || []).some(pin => pin.key === entry.key))
    .slice(0, 5)
    .map((entry, index) => ({
      id: `resume-${entry.key}`,
      section: 'Continue Working',
      title: `Resume ${entry.title}`,
      subtitle: entry.subtitle || 'Return to your last active context',
      keywords: `resume recent ${entry.title} ${entry.subtitle || ''}`,
      icon: entry.icon || '&#8250;',
      meta: index === 0 ? 'Latest' : 'Recent',
      priority: 89 - index,
      run: () => resumeWorkspaceEntry(entry.key),
    }));
  const controls = [];
  if (previous?.key) {
    controls.push({
      id: `previous-${previous.key}`,
      section: 'Desk Memory',
      title: `Return to ${previous.title}`,
      subtitle: previous.subtitle || 'Jump back to the desk you were using just before this one',
      keywords: `previous back return context ${previous.title} ${previous.subtitle || ''}`,
      icon: previous.icon || '&#8630;',
      meta: 'Previous',
      priority: 96,
      run: () => resumeWorkspaceEntry(previous.key),
    });
  }
  if (launch?.key) {
    controls.push({
      id: `launch-${launch.key}`,
      section: 'Desk Memory',
      title: `Open Launch Context: ${launch.title}`,
      subtitle: launch.subtitle || 'Open the desk that launches by default for this app',
      keywords: `launch context default startup ${launch.title} ${launch.subtitle || ''}`,
      icon: launch.icon || '&#127968;',
      meta: 'Launch',
      priority: 95,
      run: () => resumeWorkspaceEntry(launch.key),
    });
  }
  if (current?.key) {
    const currentPinned = (state.pinned || []).some(entry => entry.key === current.key);
    const currentLaunch = launch ? launch.key === current.key : false;
    controls.push({
      id: `pin-current-${current.key}`,
      section: 'Desk Memory',
      title: currentPinned ? `Unpin ${current.title}` : `Pin ${current.title}`,
      subtitle: currentPinned ? 'Remove the current desk from your pinned contexts' : 'Keep the current desk in your quick-return shelf',
      keywords: `pin unpin current context desk ${current.title}`,
      icon: current.icon || '&#8250;',
      meta: currentPinned ? 'Unpin' : 'Pin',
      priority: 93,
      run: () => {
        const isPinned = togglePinnedWorkspaceEntry(current.key);
        if (typeof toast === 'function') {
          toast(
            isPinned ? `Pinned ${current.title}` : `Unpinned ${current.title}`,
            isPinned ? 'success' : 'info'
          );
        }
      },
    });
    controls.push({
      id: `launch-current-${current.key}`,
      section: 'Desk Memory',
      title: currentLaunch ? `${current.title} Is Launch Context` : `Make ${current.title} the Launch Context`,
      subtitle: currentLaunch ? 'This desk already opens by default when the app starts' : 'Open this desk automatically when no URL overrides startup',
      keywords: `launch default startup context ${current.title}`,
      icon: current.icon || '&#127968;',
      meta: currentLaunch ? 'Launch' : 'Set',
      priority: 92,
      run: () => {
        if (!currentLaunch) {
          setLaunchWorkspaceEntry(current.key);
          if (typeof toast === 'function') toast(`Set ${current.title} as the launch context`, 'success');
        }
      },
    });
  }
  if ((state.recent || []).length) {
    controls.push({
      id: 'clear-recent-contexts',
      section: 'Desk Memory',
      title: 'Clear Recent Contexts',
      subtitle: 'Reset the recent-work history without touching pinned desks',
      keywords: 'clear recent contexts history desk memory',
      icon: '&#128465;',
      meta: 'Reset',
      priority: 72,
      run: () => {
        clearWorkspaceRecentContexts();
        if (typeof toast === 'function') toast('Cleared recent contexts', 'info');
      },
    });
  }
  if ((state.pinned || []).length) {
    controls.push({
      id: 'clear-pinned-contexts',
      section: 'Desk Memory',
      title: 'Clear Pinned Contexts',
      subtitle: 'Remove pinned desks from the quick-return shelf',
      keywords: 'clear pinned contexts favorites desk memory',
      icon: '&#128204;',
      meta: 'Reset',
      priority: 71,
      run: () => {
        clearPinnedWorkspaceContexts();
        if (typeof toast === 'function') toast('Cleared pinned contexts', 'info');
      },
    });
  }
  if (launch?.key) {
    controls.push({
      id: 'clear-launch-context',
      section: 'Desk Memory',
      title: 'Clear Launch Context',
      subtitle: 'Return app startup to the standard default workspace behavior',
      keywords: 'clear launch context default startup',
      icon: '&#128683;',
      meta: 'Reset',
      priority: 70,
      run: () => {
        clearLaunchWorkspaceEntry();
        if (typeof toast === 'function') toast('Cleared launch context', 'info');
      },
    });
  }
  return [...controls, ...pinned, ...recent];
}

function buildCommandPalettePreviewAction(action, index) {
  return `<button type="button" class="command-palette-preview-action${action.tone ? ` is-${escapeAttr(action.tone)}` : ''}" data-command-palette-preview-action="${index}">${escapeHtml(action.label)}</button>`;
}

function renderCommandPalettePreview(query = '') {
  const previewEl = document.getElementById('command-palette-preview');
  if (!previewEl) return;
  const descriptor = buildWorkspaceContextDescriptor();
  const state = getWorkspaceResumeState();
  const current = descriptor.trackableEntry || getPrimaryWorkspaceResumeEntry(state) || getLaunchWorkspaceResumeEntry(state);
  const previous = getPreviousWorkspaceResumeEntry(state, current?.key || '');
  const launch = getLaunchWorkspaceResumeEntry(state);
  const contextualActions = getWorkspaceContextActions().slice(0, 2);
  const currentPinned = current?.key ? isPinnedWorkspaceEntry(current.key) : false;
  const currentLaunch = current?.key ? isLaunchWorkspaceEntry(current.key) : false;
  const title = current?.title || descriptor.title;
  const text = query.trim()
    ? `Search is scanning workspaces, pinned desks, and records while you stay anchored in ${descriptor.title}.`
    : current?.subtitle || descriptor.summary || 'Find the right desk, record, or next move without leaving your current posture.';
  const badges = [
    {label: descriptor.group, tone: 'group'},
    descriptor.detail && descriptor.detail !== descriptor.title ? {label: descriptor.detail, tone: 'detail'} : null,
    currentPinned ? {label: 'Pinned', tone: 'pinned'} : null,
    currentLaunch ? {label: 'Launch', tone: 'launch'} : null,
    query.trim() ? {label: 'Live Search', tone: 'search'} : null,
  ].filter(Boolean);

  const previewActions = [];
  if (previous?.key) {
    previewActions.push({label: `Back to ${previous.title}`, tone: 'secondary', run: () => resumeWorkspaceEntry(previous.key)});
  }
  if (launch?.key && launch.key !== current?.key) {
    previewActions.push({label: `Open ${launch.title}`, tone: 'secondary', run: () => resumeWorkspaceEntry(launch.key)});
  }
  if (current?.key) {
    previewActions.push({
      label: currentPinned ? 'Unpin Current Desk' : 'Pin Current Desk',
      tone: currentPinned ? 'secondary' : 'accent',
      run: () => {
        const isPinned = togglePinnedWorkspaceEntry(current.key);
        if (typeof toast === 'function') {
          toast(isPinned ? `Pinned ${current.title}` : `Unpinned ${current.title}`, isPinned ? 'success' : 'info');
        }
      },
    });
  }
  contextualActions.forEach(action => previewActions.push({label: action.label, tone: 'accent', run: action.run}));
  _commandPalettePreviewActions = previewActions.slice(0, 5);

  previewEl.innerHTML = `
    <div class="command-palette-preview-card">
      <div class="command-palette-preview-kicker">Current Desk</div>
      <div class="command-palette-preview-title">${escapeHtml(title)}</div>
      <div class="command-palette-preview-text">${escapeHtml(text)}</div>
      <div class="command-palette-preview-badges">${badges.map(badge => `<span class="command-palette-preview-badge is-${escapeAttr(badge.tone)}">${escapeHtml(badge.label)}</span>`).join('')}</div>
    </div>
    <div class="command-palette-preview-rail">
      <div class="command-palette-preview-block">
        <span class="command-palette-preview-label">Launch Desk</span>
        <span class="command-palette-preview-value">${escapeHtml(launch?.title || 'Not set yet')}</span>
      </div>
      <div class="command-palette-preview-block">
        <span class="command-palette-preview-label">Previous Context</span>
        <span class="command-palette-preview-value">${escapeHtml(previous?.title || 'No prior desk to return to yet')}</span>
      </div>
      <div class="command-palette-preview-block command-palette-preview-block-actions">
        <span class="command-palette-preview-label">Quick Moves</span>
        <div class="command-palette-preview-actions">
          ${_commandPalettePreviewActions.length
            ? _commandPalettePreviewActions.map((action, index) => buildCommandPalettePreviewAction(action, index)).join('')
            : '<span class="command-palette-preview-value">Search and results will take over here as you branch deeper.</span>'}
        </div>
      </div>
    </div>
  `;
}

function syncWorkspaceUrlState() {
  const activeTab = document.querySelector('.tab.active')?.dataset.tab || getWorkspacePageTab?.() || 'situation-room';
  const url = new URL(window.location.href);
  const params = url.searchParams;

  params.set('tab', activeTab);

  if (activeTab === 'preparedness') {
    const prepSub = document.querySelector('.prep-sub.active')?.id?.replace('psub-', '') || 'checklists';
    params.set('prep', prepSub);
  } else {
    params.delete('prep');
  }

  if (activeTab === 'media' && typeof _mediaSub !== 'undefined') {
    params.set('media', _mediaSub);
  } else {
    params.delete('media');
  }

  if (activeTab === 'situation-room') {
    if (typeof _sitroomView !== 'undefined') params.set('sr_view', _sitroomView);
    if (typeof _sitroomNewsGroup !== 'undefined') params.set('sr_news', _sitroomNewsGroup);
    if (typeof _sitroomRegionPreset !== 'undefined') params.set('sr_region', _sitroomRegionPreset);
    if (typeof _sitroomDeskPreset !== 'undefined') params.set('sr_desk', _sitroomDeskPreset);
    if (typeof _sitroomLayerPreset !== 'undefined') params.set('sr_layers', _sitroomLayerPreset);
    if (typeof _sitroomBriefMode !== 'undefined') params.set('sr_brief', _sitroomBriefMode);
  } else {
    ['sr_view', 'sr_news', 'sr_region', 'sr_desk', 'sr_layers', 'sr_brief'].forEach(key => params.delete(key));
  }

  const nextQuery = params.toString();
  const nextUrl = `${url.pathname}${nextQuery ? `?${nextQuery}` : ''}${url.hash}`;
  history.replaceState(null, '', nextUrl);
  recordWorkspaceResumeEntry();
}

function restoreWorkspaceUrlState() {
  const params = new URLSearchParams(window.location.search);
  const explicitPageTab = typeof getWorkspacePageTab === 'function' ? getWorkspacePageTab() : (window.NOMAD_ACTIVE_TAB || '');
  const targetTab = params.get('tab') || explicitPageTab;
  if (!targetTab) {
    const launch = getLaunchWorkspaceResumeEntry(getWorkspaceResumeState());
    if (window.NOMAD_ALLOW_LAUNCH_RESTORE && launch?.key) {
      resumeWorkspaceEntry(launch.key);
    }
    return;
  }

  const applyTabState = () => {
    if (targetTab === 'preparedness') {
      const prepSub = params.get('prep');
      if (prepSub && typeof switchPrepSub === 'function') switchPrepSub(prepSub);
      const checklistFocus = params.get('checklist_focus');
      if (checklistFocus && typeof selectChecklist === 'function') {
        setTimeout(() => selectChecklist(Number(checklistFocus)), 120);
      }
      if (params.get('show_inv_form') === '1' && typeof showInvForm === 'function') {
        setTimeout(() => showInvForm(), 120);
      }
      const guideStart = params.get('guide_start');
      if (guideStart && typeof startGuide === 'function') {
        setTimeout(() => startGuide(guideStart), 220);
      }
      return;
    }
    if (targetTab === 'media') {
      const mediaSub = params.get('media');
      if (mediaSub && typeof switchMediaSub === 'function') switchMediaSub(mediaSub);
      return;
    }
    if (targetTab === 'situation-room') {
      const desk = params.get('sr_desk');
      const view = params.get('sr_view');
      const news = params.get('sr_news');
      const region = params.get('sr_region');
      const layers = params.get('sr_layers');
      const brief = params.get('sr_brief');
      if (desk && typeof _setSitroomDeskPreset === 'function') _setSitroomDeskPreset(desk);
      if (view && typeof _setSitroomView === 'function') _setSitroomView(view);
      if (news && typeof _setSitroomNewsGroup === 'function') _setSitroomNewsGroup(news);
      if (region && typeof _setSitroomRegionPreset === 'function') _setSitroomRegionPreset(region);
      if (layers && typeof _setSitroomLayerPreset === 'function') _setSitroomLayerPreset(layers);
      if (brief && typeof _setSitroomBriefMode === 'function') _setSitroomBriefMode(brief);
    }
  };

  if (document.querySelector(`.tab[data-tab="${targetTab}"]`)) {
    openWorkspaceTab(targetTab);
    setTimeout(applyTabState, 220);
    const scrollTarget = window.location.hash ? window.location.hash.replace(/^#/, '') : '';
    if (scrollTarget && typeof scrollToSection === 'function') {
      setTimeout(() => scrollToSection(scrollTarget), 280);
    }
  }
}

function openPreparednessWorkspace(sub) {
  openWorkspaceTab('preparedness');
  setTimeout(() => { if (typeof switchPrepSub === 'function') switchPrepSub(sub); }, 160);
}

function openMediaWorkspace(sub) {
  openWorkspaceTab('media');
  setTimeout(() => {
    const button = document.querySelector(`[data-media-sub-switch="${sub}"]`);
    if (button) button.click();
  }, 160);
}

function openLibraryWorkspace(anchorId = '') {
  openWorkspaceTab('kiwix-library');
  if (!anchorId) return;
  setTimeout(() => document.getElementById(anchorId)?.scrollIntoView({behavior: 'smooth', block: 'start'}), 220);
}

function getCommandPaletteCommands() {
  const descriptor = buildWorkspaceContextDescriptor();
  const staticCommands = [
    {id: 'nav-sitroom', section: 'Workspaces', title: 'Open Situation Room', subtitle: 'Global briefing, live map, watchlists, and analyst desk', keywords: 'situation room briefing intel news map', icon: '&#127760;', priority: 120, run: () => openWorkspaceTab('situation-room')},
    {id: 'nav-home', section: 'Workspaces', title: 'Open Home', subtitle: 'Snapshot, work modes, services, and printable documents', keywords: 'home dashboard services documents activity', icon: '&#127968;', priority: 116, run: () => openWorkspaceTab('services')},
    {id: 'nav-readiness', section: 'Workspaces', title: 'Open Readiness', subtitle: 'Score, gaps, and best next moves', keywords: 'readiness score priorities status', icon: '&#128202;', priority: 114, run: () => openWorkspaceTab('readiness')},
    {id: 'nav-preparedness', section: 'Workspaces', title: 'Open Preparedness', subtitle: 'Checklists, incidents, inventory, and response lanes', keywords: 'preparedness operations checklists incidents inventory', icon: '&#9878;', priority: 112, run: () => openWorkspaceTab('preparedness')},
    {id: 'nav-maps', section: 'Workspaces', title: 'Open Maps', subtitle: 'Regional downloads, waypoints, routing, and atlas tools', keywords: 'maps atlas waypoints routing region', icon: '&#128506;', priority: 108, run: () => openWorkspaceTab('maps')},
    {id: 'nav-library', section: 'Workspaces', title: 'Open Library', subtitle: 'Offline knowledge, Wikipedia tiers, and documents', keywords: 'library documents wikipedia zim knowledge', icon: '&#128214;', priority: 106, run: () => openWorkspaceTab('kiwix-library')},
    {id: 'nav-notes', section: 'Workspaces', title: 'Open Notes', subtitle: 'Working notes, templates, backlinks, and local archive', keywords: 'notes markdown backlinks templates', icon: '&#9997;', priority: 104, run: () => openWorkspaceTab('notes')},
    {id: 'nav-media', section: 'Workspaces', title: 'Open Media', subtitle: 'Channels, downloads, books, and offline library management', keywords: 'media channels books videos audio torrents', icon: '&#9654;', priority: 102, run: () => openWorkspaceTab('media')},
    {id: 'nav-copilot', section: 'Workspaces', title: 'Open Copilot', subtitle: 'Local AI workspace for drafting, analysis, and decisions', keywords: 'copilot ai assistant chat models', icon: '&#129302;', priority: 100, run: () => openWorkspaceTab('ai-chat')},
    {id: 'nav-tools', section: 'Workspaces', title: 'Open Tools', subtitle: 'Field utilities, drills, scenarios, and off-grid comms', keywords: 'tools drills scenarios utilities meshtastic', icon: '&#128295;', priority: 98, run: () => openWorkspaceTab('tools')},
    {id: 'nav-settings', section: 'Workspaces', title: 'Open Settings', subtitle: 'Theme, modes, backups, sync, and system control', keywords: 'settings theme backup sync models system', icon: '&#9881;', priority: 96, run: () => openWorkspaceTab('settings')},
    {id: 'nav-diagnostics', section: 'Workspaces', title: 'Open Diagnostics', subtitle: 'Benchmarks, run history, and machine health', keywords: 'diagnostics benchmark performance history', icon: '&#128200;', priority: 94, run: () => openWorkspaceTab('benchmark')},
    {id: 'prep-coordinate', section: 'Preparedness Lanes', title: 'Preparedness: Coordinate', subtitle: 'Checklists, incidents, and command-post workflow', keywords: 'preparedness coordinate checklist incidents command post', icon: '&#9876;', priority: 92, run: () => openPreparednessWorkspace('checklists')},
    {id: 'prep-sustain', section: 'Preparedness Lanes', title: 'Preparedness: Sustain', subtitle: 'Inventory, weather, fuel, power, and equipment', keywords: 'preparedness sustain inventory weather fuel power equipment', icon: '&#127793;', priority: 90, run: () => openPreparednessWorkspace('inventory')},
    {id: 'prep-care', section: 'Preparedness Lanes', title: 'Preparedness: Care & People', subtitle: 'Medical, contacts, family plans, and community', keywords: 'preparedness care people medical contacts family community', icon: '&#10010;', priority: 88, run: () => openPreparednessWorkspace('medical')},
    {id: 'prep-protect', section: 'Preparedness Lanes', title: 'Preparedness: Protect & Secure', subtitle: 'Security, comms, vault, and exposure threats', keywords: 'preparedness protect security comms vault secure', icon: '&#128737;', priority: 86, run: () => openPreparednessWorkspace('security')},
    {id: 'prep-learn', section: 'Preparedness Lanes', title: 'Preparedness: Reference & Planning', subtitle: 'Guides, calculators, and procedures', keywords: 'preparedness guides calculators planning procedures', icon: '&#128214;', priority: 84, run: () => openPreparednessWorkspace('guides')},
    {id: 'act-new-note', section: 'Quick Actions', title: 'Create New Note', subtitle: 'Start a fresh working note in the notes workspace', keywords: 'new note write scratchpad journal', icon: '&#10010;', priority: 82, run: () => { openWorkspaceTab('notes'); setTimeout(() => { if (typeof createNote === 'function') createNote(); }, 180); }},
    {id: 'act-new-conversation', section: 'Quick Actions', title: 'Start New Copilot Conversation', subtitle: 'Open Copilot and begin a fresh thread', keywords: 'new conversation chat copilot ai', icon: '&#9998;', priority: 80, run: () => { openWorkspaceTab('ai-chat'); setTimeout(() => { document.querySelector('[data-chat-action="new-conversation"]')?.click(); }, 180); }},
    {id: 'act-open-timers', section: 'Quick Actions', title: 'Open Timers', subtitle: 'Bring up quick timers without changing workspace', keywords: 'timers countdown reminders', icon: '&#9202;', priority: 78, run: () => { if (typeof toggleTimerPanel === 'function') toggleTimerPanel(); }},
    {id: 'act-open-lan', section: 'Quick Actions', title: 'Open LAN Chat', subtitle: 'Open the local handoff and coordination panel', keywords: 'lan chat handoff local network messages', icon: '&#9993;', priority: 76, run: () => { if (typeof toggleLanChat === 'function') toggleLanChat(); }},
    {id: 'act-open-quick', section: 'Quick Actions', title: 'Open Quick Actions', subtitle: 'Launch the compact action tray for rapid logging', keywords: 'quick actions tray incident note weather', icon: '&#43;', priority: 74, run: () => { if (typeof toggleQuickActions === 'function') toggleQuickActions(); }},
    {id: 'act-open-docs', section: 'Quick Actions', title: 'Open Keyboard Shortcuts', subtitle: 'Review navigation and command shortcuts', keywords: 'shortcuts help keyboard', icon: '&#63;', priority: 70, run: () => { if (typeof toggleShortcutsHelp === 'function') toggleShortcutsHelp(); }},
    {id: 'act-library-docs', section: 'Quick Actions', title: 'Open Document Shelf', subtitle: 'Jump directly to uploaded field documents', keywords: 'documents pdf epub library shelf', icon: '&#128206;', priority: 68, run: () => openLibraryWorkspace('doc-library')},
    {id: 'act-shell-health', section: 'Quick Actions', title: 'Open Shell Health', subtitle: 'Inspect active timers, fetches, and workspace runtime', keywords: 'shell health debug intervals fetch runtime', icon: '&#128202;', priority: 67, run: () => { if (typeof toggleShellHealth === 'function') toggleShellHealth(true); }},
    {id: 'act-media-downloads', section: 'Quick Actions', title: 'Open Media Downloads', subtitle: 'Jump into the download queue and library state', keywords: 'media downloads queue yt-dlp', icon: '&#11015;', priority: 66, run: () => { openMediaWorkspace('videos'); setTimeout(() => document.querySelector('[data-media-action="toggle-queue"]')?.click(), 220); }},
  ];
  const prepCommands = typeof getPrepWorkspacePaletteCommands === 'function'
    ? getPrepWorkspacePaletteCommands()
    : [];
  const resumeCommands = getWorkspaceResumePaletteCommands();
  return [...staticCommands, ...resumeCommands, ...prepCommands];
}

function normalizePaletteQuery(value) {
  return String(value || '').trim().toLowerCase();
}

function fetchUnifiedSearchPayload(q) {
  return fetch(`/api/search/all?q=${encodeURIComponent(q)}`).then(resp => resp.ok ? resp.json() : null).catch(() => null);
}

function flattenUnifiedSearchPayload(payload) {
  if (!payload) return [];
  return [
    ...(payload.conversations || []).map(item => ({...item, type: 'conversation'})),
    ...(payload.notes || []).map(item => ({...item, type: 'note'})),
    ...(payload.documents || []).map(item => ({...item, type: 'document'})),
    ...(payload.inventory || []).map(item => ({...item, type: 'inventory'})),
    ...(payload.contacts || []).map(item => ({...item, type: 'contact'})),
    ...(payload.checklists || []).map(item => ({...item, type: 'checklist'})),
    ...(payload.skills || []).map(item => ({...item, type: 'skill'})),
    ...(payload.ammo || []).map(item => ({...item, type: 'ammo'})),
    ...(payload.equipment || []).map(item => ({...item, type: 'equipment'})),
    ...(payload.waypoints || []).map(item => ({...item, type: 'waypoint'})),
    ...(payload.frequencies || []).map(item => ({...item, type: 'frequency'})),
    ...(payload.patients || []).map(item => ({...item, type: 'patient'})),
    ...(payload.incidents || []).map(item => ({...item, type: 'incident'})),
    ...(payload.fuel || []).map(item => ({...item, type: 'fuel'})),
  ];
}

function debounceSearch() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(doUnifiedSearch, 300);
}

function highlightMatch(text, query) {
  if (!query) return escapeHtml(text);
  const escaped = escapeHtml(text);
  const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return escaped.replace(re, '<mark class="search-highlight">$1</mark>');
}

async function doUnifiedSearch() {
  const searchInput = document.getElementById('unified-search');
  if (!searchInput) return;
  const q = searchInput.value.trim();
  const el = document.getElementById('search-results');
  if (!el) return;
  if (!q) { el.classList.remove('active'); return; }
  try {
    const payload = await fetchUnifiedSearchPayload(q);
    if (!payload) { el.classList.remove('active'); return; }
    const items = flattenUnifiedSearchPayload(payload);
    if (!items.length) {
      el.innerHTML = '<div class="search-result-empty">No results for "' + escapeHtml(q) + '" across ' + Object.keys(payload).length + ' modules</div>';
    } else {
      // Group by type
      const groups = {};
      items.forEach(i => { if (!groups[i.type]) groups[i.type] = []; groups[i.type].push(i); });
      let html = '';
      for (const [type, list] of Object.entries(groups)) {
        html += `<div class="search-result-group-head"><span>${UNIFIED_SEARCH_TYPE_ICONS[type]||''} ${UNIFIED_SEARCH_TYPE_LABELS[type]||escapeHtml(type)}</span><span class="search-result-count">${list.length}</span></div>`;
        html += list.map(i => `
          <div class="search-result-item" data-shell-action="open-search-result" data-result-type="${escapeAttr(i.type)}" data-result-id="${parseInt(i.id)||0}" data-prevent-mousedown role="button" tabindex="0">
            <span class="search-result-title">${highlightMatch(i.title, q)}</span>
          </div>
        `).join('');
      }
      el.innerHTML = html;
    }
    el.classList.add('active');
  } catch(e) { el.classList.remove('active'); }
}

function showSearchResults() {
  const searchInput = document.getElementById('unified-search');
  const el = document.getElementById('search-results');
  if (!searchInput || !el) return;
  const q = searchInput.value.trim();
  if (q) el.classList.add('active');
}
function hideSearchResults() {
  const el = document.getElementById('search-results');
  if (el) el.classList.remove('active');
}

function openSearchResult(type, id) {
  hideSearchResults();
  const _uSearch = document.getElementById('unified-search');
  if (_uSearch) _uSearch.value = '';
  if (type === 'conversation') {
    document.querySelector('[data-tab="ai-chat"]')?.click();
    setTimeout(() => selectConvo(id), 200);
  } else if (type === 'note') {
    document.querySelector('[data-tab="notes"]')?.click();
    setTimeout(() => { loadNotes().then(() => selectNote(id)); }, 200);
  } else if (type === 'document') {
    document.querySelector('[data-tab="kiwix-library"]')?.click();
    setTimeout(() => { loadPDFList(); toast('Document found in library', 'info'); }, 200);
  } else if (type === 'inventory') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('inventory'), 200);
  } else if (type === 'contact') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('contacts'), 200);
  } else if (type === 'checklist') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => { switchPrepSub('checklists'); selectChecklist(id); }, 200);
  } else if (type === 'skill') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('skills'), 200);
  } else if (type === 'ammo') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('ammo'), 200);
  } else if (type === 'equipment') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('equipment'), 200);
  } else if (type === 'waypoint') {
    document.querySelector('[data-tab="maps"]')?.click();
    toast('Waypoint: navigate to it on the map', 'info');
  } else if (type === 'frequency') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('radio'), 200);
  } else if (type === 'patient') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('medical'), 200);
  } else if (type === 'incident') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('incidents'), 200);
  } else if (type === 'fuel') {
    document.querySelector('[data-tab="preparedness"]')?.click();
    setTimeout(() => switchPrepSub('fuel'), 200);
  }
}

/* ─── Content Summary ─── */
async function loadContentSummary() {
  const el = document.getElementById('content-summary');
  if (!el) return;
  try {
    const _csResp = await fetch('/api/content-summary');
    if (!_csResp.ok) throw new Error('content-summary failed');
    const s = await _csResp.json();
    el.innerHTML = `
      <div>
        <div class="cs-total">${escapeHtml(String(s.total_size || '0 B'))}</div>
        <div class="cs-label">Offline Knowledge</div>
      </div>
      <div class="cs-stat"><div class="cs-val">${escapeHtml(String(s.ai_models ?? '0'))}</div><div class="cs-label">AI Models</div></div>
      <div class="cs-stat"><div class="cs-val">${escapeHtml(String(s.zim_files ?? '0'))}</div><div class="cs-label">Content Packs</div></div>
      <div class="cs-stat"><div class="cs-val">${escapeHtml(String(s.documents ?? '0'))}</div><div class="cs-label">Documents</div></div>
      <div class="cs-stat"><div class="cs-val">${escapeHtml(String(s.conversations ?? '0'))}</div><div class="cs-label">Conversations</div></div>
      <div class="cs-stat"><div class="cs-val">${escapeHtml(String(s.notes ?? '0'))}</div><div class="cs-label">Notes</div></div>
    `;
  } catch(e) {
    el.innerHTML = '<div class="cs-label content-summary-empty">Content summary unavailable</div>';
  }
}

/* ─── Log Viewer ─── */
async function loadLogViewer() {
  const levelEl = document.getElementById('log-level-filter');
  if (!levelEl) return;
  const level = levelEl.value;
  try {
    const lines = document.getElementById('log-lines-select')?.value || 100;
    const _logResp = await fetch('/api/activity?limit=' + parseInt(lines));
    if (!_logResp.ok) throw new Error('activity log failed');
    const items = await _logResp.json();
    const filtered = level ? items.filter(a => a.level === level) : items;
    const el = document.getElementById('log-viewer');
    if (!filtered.length) { el.innerHTML = '<span class="settings-empty-state log-viewer-empty">No log entries.</span>'; return; }
    el.innerHTML = filtered.map(a => {
      const t = new Date(a.created_at);
      const ts = t.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
      const badge = a.level === 'error' ? 'ERR' : a.level === 'warning' ? 'WRN' : 'INF';
      const badgeClass = a.level === 'error' ? 'settings-log-badge-error' : a.level === 'warning' ? 'settings-log-badge-warning' : 'settings-log-badge-info';
      return `<div class="settings-log-row">
        <span class="settings-log-time">${ts}</span>
        <span class="settings-log-badge ${badgeClass}">${badge}</span>
        <span class="settings-log-service">${escapeHtml(a.service||'-')}</span>
        <span>${escapeHtml(a.event.replace(/_/g,' '))}${a.detail ? ' — '+escapeHtml(a.detail) : ''}</span>
      </div>`;
    }).join('');
  } catch(e) {}
}

/* ─── Disk Monitor ─── */
async function loadDataSummary() {
  try {
    const _dsResp = await fetch('/api/data-summary');
    if (!_dsResp.ok) return;
    const d = await _dsResp.json();
    const el = document.getElementById('data-summary');
    if (!d?.tables?.length) {
      el.innerHTML = '<div class="settings-empty-state">No data yet. Start adding inventory, contacts, and notes to see your data summary.</div>';
      return;
    }
    el.innerHTML = `
      <div class="settings-summary-total"><strong>${d.total_records.toLocaleString()}</strong> total records across ${d.tables.length} tables</div>
      <div class="utility-summary-result settings-summary-grid">
        ${d.tables.map(t => `<div class="prep-summary-card utility-summary-card">
          <div class="prep-summary-meta">${escapeHtml(t.label)}</div>
          <div class="prep-summary-value prep-summary-value-compact">${t.count.toLocaleString()}</div>
        </div>`).join('')}
      </div>`;
  } catch(e) {}
}

async function loadDiskMonitor() {
  try {
    const [sys, summary] = await Promise.all([
      fetch('/api/system').then(r => { if(!r.ok) throw new Error(); return r.json(); }),
      fetch('/api/content-summary').then(r => { if(!r.ok) throw new Error(); return r.json(); })
    ]);
    const el = document.getElementById('disk-monitor');

    // Calculate usage breakdown
    const totalBytes = summary.total_bytes || 0;
    const freeStr = sys.disk_free || 'Unknown';
    const totalStr = sys.disk_total || 'Unknown';

    let warn = '';
    const devices = sys.disk_devices || [];
    const criticalDisk = devices.find(d => d.percent > 90);
    if (criticalDisk) {
      warn = `<div class="prep-reference-callout prep-reference-callout-danger settings-summary-alert">
        Drive ${escapeHtml(String(criticalDisk.mountpoint))} is ${escapeHtml(String(criticalDisk.percent))}% full. Consider freeing space or moving data.
      </div>`;
    }

    el.innerHTML = `${warn}
      <div class="utility-summary-result settings-summary-grid">
        <div class="prep-summary-card utility-summary-card">
<div class="prep-summary-meta">NOMAD Data</div>
          <div class="prep-summary-value prep-summary-value-compact">${escapeHtml(String(summary.total_size || '0 B'))}</div>
        </div>
        <div class="prep-summary-card utility-summary-card">
          <div class="prep-summary-meta">ZIM Content</div>
          <div class="prep-summary-value prep-summary-value-compact">${escapeHtml(String(summary.zim_size || '0 B'))}</div>
        </div>
        <div class="prep-summary-card utility-summary-card">
          <div class="prep-summary-meta">Disk Free</div>
          <div class="prep-summary-value prep-summary-value-compact">${freeStr}</div>
        </div>
        <div class="prep-summary-card utility-summary-card">
          <div class="prep-summary-meta">Disk Total</div>
          <div class="prep-summary-value prep-summary-value-compact">${totalStr}</div>
        </div>
      </div>
      <div class="settings-summary-note">
        Tip: Large ZIM files (Wikipedia Full, Stack Overflow) can be deleted from the Library tab when not needed.
      </div>`;
  } catch(e) {}
}

/* ─── Mission Readiness ─── */
async function loadReadiness(servicesData = null) {
  const el = document.getElementById('readiness-bar');
  if (!el) return;
  try {
    const services = Array.isArray(servicesData)
      ? servicesData
      : await fetch('/api/services').then(r => { if(!r.ok) throw new Error(); return r.json(); });
    const caps = [
      {id:'ollama', label:'AI Chat', need:['ollama']},
      {id:'kiwix', label:'Library', need:['kiwix']},
      {id:'cyberchef', label:'Data Tools', need:['cyberchef']},
      {id:'kolibri', label:'Education', need:['kolibri']},
      {id:'qdrant', label:'Knowledge Base', need:['qdrant','ollama']},
      {id:'stirling', label:'PDF Tools', need:['stirling']},
    ];
    const svcMap = {};
    services.forEach(s => svcMap[s.id] = s);

    el.innerHTML = caps.map(c => {
      const allInstalled = c.need.every(n => svcMap[n]?.installed);
      const allRunning = c.need.every(n => svcMap[n]?.running);
      const cls = allRunning ? 'ready' : allInstalled ? 'partial' : 'offline';
      const label = allRunning ? 'Ready' : allInstalled ? 'Stopped' : 'Not Installed';
      return `<div class="readiness-pill ${cls}"><span class="rdot"></span>${c.label}: ${label}</div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '';
  }
}

/* ─── Activity Feed ─── */
async function loadActivity() {
  const el = document.getElementById('activity-feed');
  if (!el) return;
  try {
    const filter = document.getElementById('activity-filter')?.value || '';
    const url = filter ? `/api/activity?limit=30&filter=${encodeURIComponent(filter)}` : '/api/activity?limit=30';
    const _actResp = await fetch(url);
    if (!_actResp.ok) throw new Error('activity failed');
    const items = await _actResp.json();
    if (!items.length) { el.innerHTML = '<span class="text-muted">No activity yet.</span>'; return; }
    el.innerHTML = items.map(a => {
      const t = new Date(a.created_at);
      const time = t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      const date = t.toLocaleDateString([], {month:'short',day:'numeric'});
      const event = a.event.replace(/_/g, ' ');
      const eventToneClass = a.level === 'error' ? 'activity-event-error' : a.level === 'warning' ? 'activity-event-warning' : 'activity-event-info';
      return `<div class="activity-item">
        <span class="activity-time">${date} ${time}</span>
        <span class="activity-event ${eventToneClass}">${event}</span>
        ${a.service ? `<span class="activity-service-tag">${escapeHtml(a.service)}</span>` : ''}
        ${a.detail ? `<span class="activity-detail">${escapeHtml(a.detail)}</span>` : ''}
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<span class="text-muted">Activity unavailable</span>';
  }
}

/* ─── Update Checker ─── */
async function checkForUpdate() {
  const banner = document.getElementById('update-banner');
  const dlBtn = document.getElementById('update-download-btn');
  const statusEl = document.getElementById('update-status-text');
  if (!banner && !dlBtn && !statusEl) return;
  try {
    const _ucResp = await fetch('/api/update-check');
    if (!_ucResp.ok) return;
    const u = await _ucResp.json();
    if (u.update_available) {
      if (banner) {
        banner.style.display = 'inline-flex';
        banner.textContent = `Update: v${u.latest}`;
        banner.href = u.download_url;
      }
      // Show download button in Settings About section
      if (dlBtn) { dlBtn.style.display = 'inline-flex'; }
      if (statusEl) { statusEl.textContent = `v${u.latest} available`; statusEl.style.color = 'var(--green)'; }
    }
  } catch(e) {}
}

/* ─── Self-Update Download ─── */
async function downloadUpdate() {
  const btn = document.getElementById('update-download-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Downloading…'; }
  const pbar = document.getElementById('update-progress-bar');
  if (pbar) pbar.style.display = 'block';
  await fetch('/api/update-download', {method:'POST'});
  pollUpdateProgress();
}

let _updateDownloadPoll = null;
function stopUpdateProgressPoll() {
  if (_updateDownloadPoll) {
    clearInterval(_updateDownloadPoll);
    _updateDownloadPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('settings.update-download');
}

function pollUpdateProgress() {
  stopUpdateProgressPoll();
  const runner = async () => {
    try {
      const _udResp = await fetch('/api/update-download/status');
      if (!_udResp.ok) { stopUpdateProgressPoll(); return; }
      const s = await _udResp.json();
      document.getElementById('update-progress-pct').textContent = s.progress + '%';
      document.getElementById('update-progress-fill').style.width = s.progress + '%';
      document.getElementById('update-progress-label').textContent =
        s.status === 'checking' ? 'Checking for update…' :
        s.status === 'downloading' ? 'Downloading update…' : s.status;
      if (s.status === 'complete') {
        stopUpdateProgressPoll();
        document.getElementById('update-progress-bar').style.display = 'none';
        document.getElementById('update-complete-msg').style.display = 'block';
        document.getElementById('update-download-btn').style.display = 'none';
        toast('Update downloaded successfully', 'success');
      } else if (s.status === 'error') {
        stopUpdateProgressPoll();
        document.getElementById('update-progress-bar').style.display = 'none';
        document.getElementById('update-download-btn').disabled = false;
        document.getElementById('update-download-btn').textContent = 'Retry Download';
        toast('Update failed: ' + (s.error || 'Unknown error'), 'error');
      }
    } catch(e) { stopUpdateProgressPoll(); }
  };
  if (window.NomadShellRuntime) {
    _updateDownloadPoll = window.NomadShellRuntime.startInterval('settings.update-download', runner, 1000, {
      tabId: 'settings',
      requireVisible: true,
    });
    return;
  }
  _updateDownloadPoll = setInterval(runner, 1000);
}

async function openUpdateFolder() {
  await fetch('/api/update-download/open', {method:'POST'});
}

/* ─── Startup Toggle ─── */
async function loadStartupState() {
  const toggle = document.getElementById('startup-toggle');
  if (!toggle) return;
  try {
    const _suResp = await fetch('/api/startup');
    if (!_suResp.ok) return;
    const s = await _suResp.json();
    toggle.checked = s.enabled;
  } catch(e) {}
}

async function toggleStartup() {
  const toggleEl = document.getElementById('startup-toggle');
  if (!toggleEl) return;
  const enabled = toggleEl.checked;
  await fetch('/api/startup', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled})});
  toast(enabled ? 'Will start at login' : 'Removed from startup', enabled ? 'success' : 'info');
}

/* ─── Unified Download Queue ─── */
async function pollDownloadQueue() {
  const banner = document.getElementById('download-queue-banner');
  const itemsEl = document.getElementById('download-queue-items');
  if (!banner || !itemsEl) return;
  try {
    const _dlResp = await fetch('/api/downloads/active');
    if (!_dlResp.ok) return;
    const downloads = await _dlResp.json();
    if (!downloads.length) { banner.style.display = 'none'; return; }
    banner.style.display = 'block';
    itemsEl.innerHTML = downloads.map(d => {
      const icon = d.type === 'service' ? '&#9881;' : d.type === 'content' ? '&#128218;' : d.type === 'model' ? '&#129302;' : d.type === 'map' ? '&#127758;' : '&#128229;';
      return '<div class="download-banner-entry">' +
        '<span class="download-banner-icon">' + icon + '</span>' +
        '<div class="download-banner-body">' +
          '<div class="download-banner-head">' +
            '<span class="download-banner-label">' + escapeHtml(d.label) + '</span>' +
            '<span class="download-banner-meta">' + escapeHtml(String(d.percent || 0)) + '% ' + escapeHtml(d.speed || '') + '</span>' +
          '</div>' +
          '<div class="utility-progress">' +
            '<div class="utility-progress-bar" style="--utility-progress-width:' + d.percent + '%;"></div>' +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) {}
}

/* ─── Service Process Logs ─── */
async function loadServiceLogs() {
  const svcSelect = document.getElementById('svc-log-select');
  if (!svcSelect) return;
  const svc = svcSelect.value;
  const el = document.getElementById('svc-log-viewer');
  if (!svc) { el.innerHTML = '<span class="settings-console-hint">Select a service above to view its process output.</span>'; return; }
  try {
    const _slResp = await fetch('/api/services/' + svc + '/logs?tail=200');
    if (!_slResp.ok) throw new Error('logs failed');
    const data = await _slResp.json();
    if (!data?.lines || !data.lines.length) {
      el.innerHTML = '<span class="settings-console-hint">No log output captured for ' + svc + '. Logs appear when the service is running.</span>';
      return;
    }
    el.innerHTML = data.lines.map(line => {
      const tone = /error|fail|exception/i.test(line) ? ' settings-console-line-danger' : /warn/i.test(line) ? ' settings-console-line-warn' : '';
      return '<div class="settings-console-line' + tone + '">' + escapeHtml(line) + '</div>';
    }).join('');
    el.scrollTop = el.scrollHeight;
  } catch(e) {
    el.innerHTML = '<span class="settings-console-line-danger">Failed to load service logs.</span>';
  }
}

/* ─── Content Update Checker ─── */
async function checkContentUpdates() {
  try {
    const _cuResp = await fetch('/api/kiwix/check-updates');
    if (!_cuResp.ok) throw new Error('check-updates failed');
    const updates = await _cuResp.json();
    const panel = document.getElementById('content-updates-panel');
    const itemsEl = document.getElementById('content-update-items');
    if (!updates.length) { panel.style.display = 'none'; toast('All content is up to date', 'success'); return; }
    panel.style.display = 'block';
    itemsEl.innerHTML = updates.map(u =>
      '<div class="library-update-row">' +
        '<div class="library-update-copy">' +
          '<div class="library-update-title">' + escapeHtml(u.name) + '</div>' +
          '<div class="library-update-meta">' + escapeHtml(u.installed) + ' &#8594; ' + escapeHtml(u.available) + ' (' + escapeHtml(u.size) + ')</div>' +
        '</div>' +
        '<button class="btn btn-sm btn-primary" type="button" data-library-action="update-zim-content" data-zim-url="' + escapeAttr(u.url) + '" data-zim-filename="' + escapeAttr(u.available) + '">Update</button>' +
      '</div>'
    ).join('');
  } catch(e) { toast('Failed to check for updates', 'error'); }
}

async function updateZimContent(url, filename) {
  await fetch('/api/kiwix/download-zim', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, filename})});
  toast('Downloading updated content...', 'info');
  loadZimDownloads();
}

/* ─── Wikipedia Tier Selector ─── */
async function loadWikipediaTiers() {
  try {
    const [options, installed] = await Promise.all([
      fetch('/api/kiwix/wikipedia-options').then(r => r.json()),
      fetch('/api/kiwix/zims').then(r => r.json())
    ]);
    const installedNames = new Set(installed.map(z => typeof z === 'string' ? z : z.name || ''));
    const el = document.getElementById('wiki-tier-options');
    if (!options.length) { el.innerHTML = '<div class="settings-empty-state">Install Kiwix first to download Wikipedia.</div>'; return; }
    el.innerHTML = options.map(o => {
      const isInstalled = installedNames.has(o.filename);
      const tierColor = o.tier === 'essential' ? 'var(--green)' : o.tier === 'standard' ? 'var(--accent)' : 'var(--orange)';
      return '<div class="contact-card wiki-tier-card" style="--wiki-tier-tone:' + tierColor + ';">' +
        '<div class="wiki-tier-topline"></div>' +
        '<div class="wiki-tier-title">' + escapeHtml(o.name) + '</div>' +
        '<div class="wiki-tier-copy">' + escapeHtml(o.desc) + '</div>' +
        '<div class="wiki-tier-footer">' +
          '<span class="wiki-tier-size">' + escapeHtml(o.size) + '</span>' +
          (isInstalled
            ? '<span class="wiki-tier-installed">&#10003; Installed</span>'
            : '<button class="btn btn-sm btn-primary" type="button" data-library-action="download-wiki-tier" data-zim-url="' + escapeAttr(o.url) + '" data-zim-filename="' + escapeAttr(o.filename) + '">Download</button>') +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) {}
}

async function downloadWikiTier(url, filename) {
  await fetch('/api/kiwix/download-zim', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, filename})});
  toast('Downloading Wikipedia...', 'info');
  loadZimDownloads();
}

/* ─── Export / Import Config ─── */
function exportConfig() {
  window.location='/api/export-config';
  toast('Config exported');
}
function doFullBackup() {
  window.location='/api/export-all';
  localStorage.setItem('nomad-last-backup', new Date().toISOString());
  updateLastBackup();
  toast('Backup downloaded', 'success');
}
function doExportConfig() {
  exportConfig();
  localStorage.setItem('nomad-last-backup', new Date().toISOString());
  updateLastBackup();
}
async function showBackupList() {
  try {
    const backups = await safeFetch('/api/backups', {}, []);
    if (!Array.isArray(backups)) throw new Error('invalid backups payload');
    if (!backups.length) { toast('No automatic backups found', 'info'); return; }
    const html = backups.map(b => {
      const d = new Date(b.modified * 1000);
      const ts = d.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
      return '<div class="settings-action-row">'
        + '<div class="settings-stack">'
        + '<div class="settings-row-title">' + escapeHtml(b.filename) + '</div>'
        + '<div class="settings-row-detail">' + ts + ' — ' + escapeHtml(b.size) + '</div></div>'
        + '<span class="settings-row-spacer"></span>'
        + '<button class="btn btn-sm btn-primary" type="button" data-shell-action="restore-legacy-backup" data-backup-filename="' + escapeAttr(b.filename) + '">Restore</button>'
        + '</div>';
    }).join('');
    const modal = document.createElement('div');
    modal.className = 'generated-modal-overlay';
    modal.dataset.backdropClose = 'generated-modal';
    modal.innerHTML = '<div class="modal-card settings-modal-card settings-modal-card-md generated-modal-card">'
      + '<div class="generated-modal-head">'
      + '<h3>Restore from Backup</h3>'
      + '<button class="btn btn-sm btn-ghost" type="button" data-shell-action="close-generated-modal" aria-label="Close restore backup modal">x</button></div>'
      + '<div class="generated-modal-copy">Current database will be backed up first. Restart the app after restoring.</div>'
      + '<div class="generated-modal-list">' + html + '</div></div>';
    document.body.appendChild(modal);
  } catch(e) { toast('Failed to load backups', 'error'); }
}
async function restoreBackup(filename) {
  if (!confirm('Restore database from ' + filename + '? Current data will be backed up first.')) return;
  try {
    const r = await fetch('/api/backups/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename})});
    const d = await r.json();
    if (r.ok) {
      toast(d.message || 'Database restored', 'success');
      document.querySelectorAll('.generated-modal-overlay').forEach(m => m.remove());
    } else {
      toast(d.error || 'Restore failed', 'error');
    }
  } catch(e) { toast('Restore failed', 'error'); }
}
function updateLastBackup() {
  const el = document.getElementById('last-backup-time');
  if (!el) return;
  const ts = localStorage.getItem('nomad-last-backup');
  if (ts) {
    const d = new Date(ts);
    const ago = Math.round((Date.now() - d.getTime()) / (1000*60*60*24));
    const toneClass = ago > 30 ? 'text-red' : ago > 7 ? 'text-orange' : 'text-green';
    el.innerHTML = `Last: ${d.toLocaleDateString()} <span class="${toneClass}">(${ago === 0 ? 'today' : ago + 'd ago'})</span>`;
  } else {
    el.innerHTML = '<span class="text-orange">Never backed up</span>';
  }
}

function getCommandPaletteMatches(query) {
  const q = normalizePaletteQuery(query);
  const commands = getCommandPaletteCommands()
    .filter(item => {
      if (!q) return true;
      const haystack = normalizePaletteQuery(`${item.title} ${item.subtitle} ${item.keywords} ${item.section}`);
      return haystack.includes(q);
    })
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  return q ? commands : commands.slice(0, 14);
}

function groupCommandPaletteItems(items) {
  const grouped = {};
  items.forEach(item => {
    if (!grouped[item.section]) grouped[item.section] = [];
    grouped[item.section].push(item);
  });
  return grouped;
}

function buildCommandPaletteButton(item, index, query) {
  const title = highlightMatch(item.title || 'Untitled', query);
  const subtitle = highlightMatch(item.subtitle || '', query);
  return `
    <button type="button" class="command-palette-item${index === _commandPaletteActiveIndex ? ' is-active' : ''}" data-command-palette-index="${index}" role="option" aria-selected="${index === _commandPaletteActiveIndex ? 'true' : 'false'}">
      <span class="command-palette-item-icon" aria-hidden="true">${item.icon || '&#8250;'}</span>
      <span class="command-palette-item-body">
        <span class="command-palette-item-title">${title}</span>
        <span class="command-palette-item-subtitle">${subtitle}</span>
      </span>
      <span class="command-palette-item-meta">${escapeHtml(item.meta || item.section || '')}</span>
    </button>
  `;
}

function setCommandPaletteActive(index) {
  const items = Array.from(document.querySelectorAll('[data-command-palette-index]'));
  if (!items.length) {
    _commandPaletteActiveIndex = -1;
    return;
  }
  const safeIndex = Math.max(0, Math.min(index, items.length - 1));
  _commandPaletteActiveIndex = safeIndex;
  items.forEach((item, itemIndex) => {
    const active = itemIndex === safeIndex;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  items[safeIndex]?.scrollIntoView({block: 'nearest'});
}

function moveCommandPaletteActive(delta) {
  if (!_commandPaletteItems.length) return;
  const baseIndex = _commandPaletteActiveIndex < 0 ? 0 : _commandPaletteActiveIndex;
  setCommandPaletteActive(baseIndex + delta);
}

function executeCommandPaletteItem(index) {
  const item = _commandPaletteItems[index];
  if (!item) return;
  toggleCommandPalette(false);
  if (item.kind === 'command') {
    item.run?.();
    return;
  }
  openSearchResult(item.resultType, item.resultId);
}

async function renderCommandPalette(query = '') {
  const resultsEl = document.getElementById('command-palette-results');
  if (!resultsEl) return;
  const q = query.trim();
  renderCommandPalettePreview(q);
  const commandMatches = getCommandPaletteMatches(q).map(item => ({...item, kind: 'command'}));
  let searchMatches = [];
  if (q) {
    const payload = await fetchUnifiedSearchPayload(q);
    searchMatches = flattenUnifiedSearchPayload(payload).map(item => ({
      kind: 'search',
      section: 'Search Results',
      title: item.title || 'Untitled',
      subtitle: `${UNIFIED_SEARCH_TYPE_LABELS[item.type] || item.type} · Open matching record`,
      meta: UNIFIED_SEARCH_TYPE_LABELS[item.type] || item.type,
      icon: UNIFIED_SEARCH_TYPE_ICONS[item.type] || '&#128269;',
      resultType: item.type,
      resultId: Number(item.id) || 0,
    }));
  }

  const sections = [];
  _commandPaletteItems = [];

  if (commandMatches.length) {
    const grouped = groupCommandPaletteItems(commandMatches);
    Object.entries(grouped).forEach(([sectionName, sectionItems]) => {
      const startIndex = _commandPaletteItems.length;
      _commandPaletteItems.push(...sectionItems);
      const html = sectionItems.map((item, itemIndex) => buildCommandPaletteButton(item, startIndex + itemIndex, q)).join('');
      sections.push(`
        <div class="command-palette-section">
          <div class="command-palette-section-head">
            <span>${escapeHtml(sectionName)}</span>
            <span class="command-palette-count">${sectionItems.length}</span>
          </div>
          <div class="command-palette-list">${html}</div>
        </div>
      `);
    });
  }

  if (searchMatches.length) {
    const startIndex = _commandPaletteItems.length;
    _commandPaletteItems.push(...searchMatches);
    sections.push(`
      <div class="command-palette-section">
        <div class="command-palette-section-head">
          <span>Search Results</span>
          <span class="command-palette-count">${searchMatches.length}</span>
        </div>
        <div class="command-palette-list">${searchMatches.map((item, itemIndex) => buildCommandPaletteButton(item, startIndex + itemIndex, q)).join('')}</div>
      </div>
    `);
  }

  if (!sections.length) {
    resultsEl.innerHTML = `<div class="command-palette-empty">No matches for <strong>${escapeHtml(q)}</strong>. Try a workspace name, a preparedness lane, or a record like a note, contact, or checklist.</div>`;
    _commandPaletteActiveIndex = -1;
    return;
  }

  resultsEl.innerHTML = sections.join('');
  setCommandPaletteActive(0);
}

function toggleCommandPalette(force) {
  const overlay = document.getElementById('command-palette-overlay');
  const input = document.getElementById('command-palette-input');
  if (!overlay || !input) return;
  const show = typeof force === 'boolean' ? force : overlay.hidden;
  if (show) {
    const shortcuts = document.getElementById('shortcuts-overlay');
    if (shortcuts && !shortcuts.hidden) shortcuts.hidden = true;
    _commandPaletteReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setShellVisibility(overlay, true);
    input.value = '';
    clearTimeout(_commandPaletteTimer);
    renderCommandPalette('');
    requestAnimationFrame(() => input.focus());
    return;
  }
  setShellVisibility(overlay, false);
  _commandPaletteItems = [];
  _commandPaletteActiveIndex = -1;
  _commandPalettePreviewActions = [];
  if (_commandPaletteReturnFocus && typeof _commandPaletteReturnFocus.focus === 'function') {
    requestAnimationFrame(() => _commandPaletteReturnFocus.focus());
  }
}

document.getElementById('command-palette-input')?.addEventListener('input', event => {
  const value = event.target.value;
  clearTimeout(_commandPaletteTimer);
  _commandPaletteTimer = setTimeout(() => renderCommandPalette(value), value.trim() ? 120 : 0);
});

document.getElementById('command-palette-input')?.addEventListener('keydown', event => {
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    moveCommandPaletteActive(1);
    return;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    moveCommandPaletteActive(-1);
    return;
  }
  if (event.key === 'Enter') {
    event.preventDefault();
    executeCommandPaletteItem(_commandPaletteActiveIndex);
    return;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    toggleCommandPalette(false);
  }
});

document.getElementById('command-palette-results')?.addEventListener('mousemove', event => {
  const button = event.target.closest('[data-command-palette-index]');
  if (!button) return;
  setCommandPaletteActive(Number(button.dataset.commandPaletteIndex) || 0);
});

document.getElementById('command-palette-results')?.addEventListener('click', event => {
  const button = event.target.closest('[data-command-palette-index]');
  if (!button) return;
  executeCommandPaletteItem(Number(button.dataset.commandPaletteIndex) || 0);
});

document.getElementById('command-palette-preview')?.addEventListener('click', event => {
  const button = event.target.closest('[data-command-palette-preview-action]');
  if (!button) return;
  const action = _commandPalettePreviewActions[Number(button.dataset.commandPalettePreviewAction)];
  if (!action?.run) return;
  toggleCommandPalette(false);
  action.run();
});

document.addEventListener('click', event => {
  const guideContextButton = event.target.closest('[data-workspace-context-action="open-guide"]');
  if (guideContextButton) {
    event.preventDefault();
    const inspector = document.getElementById('workspace-inspector');
    if (inspector && !inspector.hidden) {
      closeWorkspaceInspector();
    } else {
      openWorkspaceInspector();
    }
    return;
  }
  const guideTargetButton = event.target.closest('[data-workspace-guide-target]');
  if (guideTargetButton) {
    event.preventDefault();
    openWorkspaceInspector(guideTargetButton.dataset.workspaceGuideTarget || '');
    return;
  }
  const guideCloseButton = event.target.closest('[data-workspace-guide-action="close"]');
  if (guideCloseButton) {
    event.preventDefault();
    closeWorkspaceInspector();
    return;
  }
  const guideActionButton = event.target.closest('[data-workspace-inspector-action-index]');
  if (guideActionButton) {
    event.preventDefault();
    const action = _workspaceInspectorActionItems[Number(guideActionButton.dataset.workspaceInspectorActionIndex)];
    if (action?.run) activateWorkspaceGuideAction(action.run);
    return;
  }
  const launchButton = event.target.closest('[data-workspace-context-action="set-launch"]');
  if (launchButton) {
    event.preventDefault();
    const state = getWorkspaceResumeState();
    const current = getPrimaryWorkspaceResumeEntry(state);
    if (!current?.key) return;
    if (!isLaunchWorkspaceEntry(current.key) && setLaunchWorkspaceEntry(current.key) && typeof toast === 'function') {
      toast(`Set ${current.title} as the launch context`, 'success');
    }
    return;
  }
  const previousButton = event.target.closest('[data-workspace-context-action="resume-previous"]');
  if (previousButton) {
    event.preventDefault();
    const state = getWorkspaceResumeState();
    const current = getPrimaryWorkspaceResumeEntry(state);
    const previous = getPreviousWorkspaceResumeEntry(state, current?.key || '');
    if (previous?.key) resumeWorkspaceEntry(previous.key);
    return;
  }
  const contextCommandButton = event.target.closest('[data-workspace-context-command-index]');
  if (contextCommandButton) {
    event.preventDefault();
    const index = Number(contextCommandButton.dataset.workspaceContextCommandIndex);
    const command = _workspaceContextActionItems[index];
    if (command && typeof command.run === 'function') command.run();
    return;
  }
  const contextPinButton = event.target.closest('[data-workspace-context-action="toggle-pin"]');
  if (contextPinButton) {
    event.preventDefault();
    const descriptor = buildWorkspaceContextDescriptor();
    const current = descriptor.trackableEntry;
    if (!current?.key) return;
    const isPinned = togglePinnedWorkspaceEntry(current.key);
    if (typeof toast === 'function') {
      toast(
        isPinned ? `Pinned ${current.title}` : `Unpinned ${current.title}`,
        isPinned ? 'success' : 'info'
      );
    }
    return;
  }
  const memoryButton = event.target.closest('[data-workspace-memory-action]');
  if (memoryButton) {
    event.preventDefault();
    const action = memoryButton.dataset.workspaceMemoryAction;
    if (action === 'set-launch-current') {
      const state = getWorkspaceResumeState();
      const current = getPrimaryWorkspaceResumeEntry(state);
      if (!current?.key) return;
      if (setLaunchWorkspaceEntry(current.key) && typeof toast === 'function') {
        toast(`Set ${current.title} as the launch context`, 'success');
      }
      return;
    }
    if (action === 'open-launch') {
      const launch = getLaunchWorkspaceResumeEntry(getWorkspaceResumeState());
      if (launch?.key) resumeWorkspaceEntry(launch.key);
      return;
    }
    if (action === 'clear-launch') {
      clearLaunchWorkspaceEntry();
      if (typeof toast === 'function') toast('Cleared launch context', 'info');
      return;
    }
    if (action === 'toggle-current-pin') {
      const state = getWorkspaceResumeState();
      const current = getPrimaryWorkspaceResumeEntry(state);
      if (!current?.key) return;
      const isPinned = togglePinnedWorkspaceEntry(current.key);
      if (typeof toast === 'function') {
        toast(
          isPinned ? `Pinned ${current.title}` : `Unpinned ${current.title}`,
          isPinned ? 'success' : 'info'
        );
      }
      return;
    }
    if (action === 'clear-recent') {
      clearWorkspaceRecentContexts();
      if (typeof toast === 'function') toast('Cleared recent contexts', 'info');
      return;
    }
    if (action === 'clear-pinned') {
      clearPinnedWorkspaceContexts();
      if (typeof toast === 'function') toast('Cleared pinned contexts', 'info');
      return;
    }
  }
  const pinButton = event.target.closest('[data-home-context-action="toggle-pin-current"]');
  if (pinButton) {
    event.preventDefault();
    const state = getWorkspaceResumeState();
    const current = getPrimaryWorkspaceResumeEntry(state);
    if (!current?.key) return;
    const isPinned = togglePinnedWorkspaceEntry(current.key);
    if (typeof toast === 'function') {
      toast(
        isPinned ? `Pinned ${current.title}` : `Unpinned ${current.title}`,
        isPinned ? 'success' : 'info'
      );
    }
    return;
  }
  const button = event.target.closest('[data-workspace-resume-key]');
  if (!button) return;
  event.preventDefault();
  resumeWorkspaceEntry(button.dataset.workspaceResumeKey);
});

document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  const inspector = document.getElementById('workspace-inspector');
  if (inspector && !inspector.hidden) closeWorkspaceInspector();
});

window.addEventListener('storage', event => {
  if (event.key !== WORKSPACE_RESUME_STORAGE_KEY) return;
  _workspaceResumeStateCache = getLocalWorkspaceResumeState();
  refreshWorkspaceResumeUi();
});

renderHomeContinueWorking();
renderWorkspaceInspector();

