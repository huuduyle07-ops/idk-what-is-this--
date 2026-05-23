// keybindings.js — central keyboard shortcut system for CATTUS
(function () {
  'use strict';

  const STORAGE_KEY = 'cattus_keybindings';

  // Default keymap: action_id -> { key, ctrl, shift, alt, label }
  const DEFAULT_MAP = {
    tab_chat:        { key: '1',     ctrl: true,  shift: false, alt: false, label: 'Chat / Patch' },
    tab_benchmarks:  { key: 'k',     ctrl: true,  shift: false, alt: false, label: 'Benchmarks' },
    tab_dream:       { key: '2',     ctrl: true,  shift: false, alt: false, label: 'Dream' },
    tab_memory:      { key: 'm',     ctrl: true,  shift: false, alt: false, label: 'Memory' },
    tab_graph:       { key: 'g',     ctrl: true,  shift: false, alt: false, label: 'Graph' },
    tab_settings:    { key: ',',     ctrl: true,  shift: false, alt: false, label: 'Settings' },
    run_submit:      { key: 'Enter', ctrl: true,  shift: false, alt: false, label: 'Submit / Run' },
    new_session:     { key: 'n',     ctrl: true,  shift: true,  alt: false, label: 'New Session' },
    focus_repo:      { key: 'p',     ctrl: true,  shift: true,  alt: false, label: 'Focus Repo Path' },
  };

  // Browser-reserved combos — warn if user tries to bind these
  const BROWSER_RESERVED = new Set([
    'ctrl+a','ctrl+c','ctrl+v','ctrl+x','ctrl+z','ctrl+y',
    'ctrl+f','ctrl+n','ctrl+t','ctrl+w','ctrl+r','ctrl+s',
    'ctrl+p','ctrl+l','ctrl+b','ctrl+h','ctrl+j','ctrl+u',
    'ctrl+d','ctrl+e','ctrl+o','ctrl+i',
    'ctrl+shift+i','ctrl+shift+j','f5','f12',
  ]);

  function comboKey(binding) {
    const parts = [];
    if (binding.ctrl)  parts.push('ctrl');
    if (binding.shift) parts.push('shift');
    if (binding.alt)   parts.push('alt');
    parts.push(binding.key.toLowerCase());
    return parts.join('+');
  }

  function isReserved(binding) {
    return BROWSER_RESERVED.has(comboKey(binding));
  }

  function loadUserMap() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  }

  function saveUserMap(overrides) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  }

  function activeMap() {
    const overrides = loadUserMap();
    return Object.assign({}, DEFAULT_MAP, overrides);
  }

  function handleKey(e) {
    // Don't fire when typing in inputs/textareas (except Ctrl+Enter for submit)
    const tag = document.activeElement?.tagName;
    const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
    if (inInput && !(e.ctrlKey && e.key === 'Enter')) return;

    const map = activeMap();
    for (const [action, binding] of Object.entries(map)) {
      if (
        e.key.toLowerCase() === binding.key.toLowerCase() &&
        !!e.ctrlKey  === !!binding.ctrl  &&
        !!e.shiftKey === !!binding.shift &&
        !!e.altKey   === !!binding.alt
      ) {
        e.preventDefault();
        dispatch(action);
        return;
      }
    }
  }

  function dispatch(action) {
    const tabMap = {
      tab_chat:       'chat',
      tab_benchmarks: 'benchmarks',
      tab_dream:      'dream',
      tab_memory:     'memory',
      tab_graph:      'graph',
      tab_settings:   'settings',
    };
    if (tabMap[action]) {
      if (typeof showWorkspaceTab === 'function') showWorkspaceTab(tabMap[action]);
      return;
    }
    if (action === 'run_submit') {
      document.getElementById('primarySubmit')?.click();
    }
    if (action === 'new_session') {
      document.getElementById('newSessionLink')?.click();
    }
    if (action === 'focus_repo') {
      document.getElementById('repoPathInput')?.focus();
    }
  }

  document.addEventListener('keydown', handleKey);

  // Public API — used by the keybinding editor in the Settings tab
  window.CATTUS_KB = {
    DEFAULT_MAP,
    BROWSER_RESERVED,
    comboKey,
    isReserved,
    activeMap,
    loadUserMap,
    saveUserMap,
    resetAll() {
      localStorage.removeItem(STORAGE_KEY);
    },
  };
})();
