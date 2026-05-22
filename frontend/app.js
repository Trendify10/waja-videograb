// --- DOM refs ---
const urlInput = document.getElementById('url-input');
const fetchBtn = document.getElementById('fetch-btn');
const errorArea = document.getElementById('error-area');
const previewCard = document.getElementById('preview-card');
const previewThumb = document.getElementById('preview-thumb');
const previewTitle = document.getElementById('preview-title');
const previewAuthor = document.getElementById('preview-author');
const previewDuration = document.getElementById('preview-duration');
const previewPlatform = document.getElementById('preview-platform');
const formatSection = document.getElementById('format-section');
const downloadBtn = document.getElementById('download-btn');
const cookiesToggle = document.getElementById('cookies-toggle');
const browserSelectWrap = document.getElementById('browser-select-wrap');
const browserSelect = document.getElementById('browser-select');
const progressArea = document.getElementById('progress-area');
const progressLabel = document.getElementById('progress-label');
const progressPct = document.getElementById('progress-pct');
const progressBar = document.getElementById('progress-bar');
const progressSpeed = document.getElementById('progress-speed');
const progressEta = document.getElementById('progress-eta');
const doneArea = document.getElementById('done-area');
const doneText = document.getElementById('done-text');
const historyToggle = document.getElementById('history-toggle');
const historyArrow = document.getElementById('history-arrow');
const historyList = document.getElementById('history-list');
const settingsToggle = document.getElementById('settings-toggle');
const settingsArrow = document.getElementById('settings-arrow');
const settingsPanel = document.getElementById('settings-panel');
const downloadFolder = document.getElementById('download-folder');
const pickFolderBtn = document.getElementById('pick-folder-btn');
const folderSaved = document.getElementById('folder-saved');
const defaultFormat = document.getElementById('default-format');
const openFolderBtn = document.getElementById('open-folder-btn');

let currentUrl = '';
let pollTimer = null;

// --- Helpers ---

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function showError(msg) {
  errorArea.textContent = msg;
  show(errorArea);
}

function clearError() { hide(errorArea); }

function formatDuration(seconds) {
  if (!seconds) return 'Unknown length';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatTimestamp(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function resetUI() {
  clearError();
  hide(previewCard);
  hide(formatSection);
  hide(progressArea);
  hide(doneArea);
  currentUrl = '';
}

// --- Load config on startup ---

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    downloadFolder.value = cfg.download_folder || '';
    defaultFormat.value = cfg.default_format || 'best';
    const radio = document.querySelector(`input[name="format"][value="${cfg.default_format || 'best'}"]`);
    if (radio) radio.checked = true;
  } catch { /* ignore */ }
}

loadConfig();

// --- Fetch Info ---

fetchBtn.addEventListener('click', fetchInfo);
urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') fetchInfo();
});

async function fetchInfo() {
  const url = urlInput.value.trim();
  if (!url) return;

  resetUI();
  fetchBtn.disabled = true;
  fetchBtn.querySelector('.btn-text').textContent = 'Fetching…';

  // Pass cookies_browser if manually toggled
  const body = { url };
  if (cookiesToggle.checked) {
    body.cookies_browser = browserSelect.value;
  }

  try {
    const res = await fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to fetch video info');
    }

    const info = await res.json();
    currentUrl = url;

    // Populate preview
    const thumbWrap = previewThumb.parentElement;
    if (info.thumbnail) {
      previewThumb.src = info.thumbnail;
      thumbWrap.style.display = 'block';
    } else {
      thumbWrap.style.display = 'none';
    }
    previewTitle.textContent = info.title;
    previewAuthor.textContent = info.author;
    previewDuration.textContent = formatDuration(info.duration);
    previewPlatform.textContent = info.platform;

    show(previewCard);
    show(formatSection);
  } catch (e) {
    showError(e.message);
  } finally {
    fetchBtn.disabled = false;
    fetchBtn.querySelector('.btn-text').textContent = 'Fetch';
  }
}

// --- Browser Login Toggle ---

cookiesToggle.addEventListener('change', () => {
  if (cookiesToggle.checked) {
    show(browserSelectWrap);
  } else {
    hide(browserSelectWrap);
  }
});

// --- Download ---

downloadBtn.addEventListener('click', startDownload);

async function startDownload() {
  if (!currentUrl) return;

  clearError();
  hide(doneArea);
  downloadBtn.disabled = true;

  const fmt = document.querySelector('input[name="format"]:checked').value;
  const body = { url: currentUrl, format: fmt };

  if (cookiesToggle.checked) {
    body.cookies_browser = browserSelect.value;
  }

  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    show(progressArea);
    progressBar.style.width = '0%';
    progressPct.textContent = '0%';
    progressSpeed.textContent = '';
    progressEta.textContent = '';
    progressLabel.textContent = 'Downloading…';

    pollProgress(data.job_id);
  } catch (e) {
    showError('Failed to start download: ' + e.message);
    downloadBtn.disabled = false;
  }
}

function pollProgress(jobId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const job = await res.json();

      if (job.state === 'downloading') {
        const pct = job.percent || 0;
        progressBar.style.width = pct + '%';
        progressPct.textContent = pct + '%';
        progressSpeed.textContent = job.speed || '';
        progressEta.textContent = job.eta ? 'ETA ' + job.eta : '';
      } else if (job.state === 'done') {
        clearInterval(pollTimer);
        pollTimer = null;
        progressBar.style.width = '100%';
        progressPct.textContent = '100%';
        progressSpeed.textContent = '';
        progressEta.textContent = '';

        setTimeout(() => {
          hide(progressArea);
          doneText.textContent = 'Download complete!';
          show(doneArea);
          downloadBtn.disabled = false;
          loadHistory();
        }, 400);
      } else if (job.state === 'error') {
        clearInterval(pollTimer);
        pollTimer = null;
        hide(progressArea);
        showError('Download failed: ' + (job.error || 'Unknown error'));
        downloadBtn.disabled = false;
      }
    } catch {
      // Network hiccup — keep polling
    }
  }, 500);
}

// --- History ---

historyToggle.addEventListener('click', () => {
  historyList.classList.toggle('hidden');
  historyArrow.classList.toggle('open');
  if (!historyList.classList.contains('hidden')) {
    loadHistory();
  }
});

async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const history = await res.json();

    if (history.length === 0) {
      historyList.innerHTML = '<div class="history-empty">No downloads yet.</div>';
      return;
    }

    historyList.innerHTML = history.map(item => `
      <div class="history-item">
        <div class="history-item-info">
          <div class="history-item-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
          <div class="history-item-meta">${escapeHtml(item.platform)} &middot; ${formatTimestamp(item.timestamp)}</div>
        </div>
        <span class="history-item-format">${escapeHtml(item.format)}</span>
      </div>
    `).join('');
  } catch {
    historyList.innerHTML = '<div class="history-empty">Could not load history.</div>';
  }
}

// --- Settings ---

settingsToggle.addEventListener('click', () => {
  settingsPanel.classList.toggle('hidden');
  settingsArrow.classList.toggle('open');
});

pickFolderBtn.addEventListener('click', async () => {
  pickFolderBtn.disabled = true;
  pickFolderBtn.textContent = 'Choosing…';
  try {
    const res = await fetch('/api/pick-folder', { method: 'POST' });
    const data = await res.json();
    if (data.folder) {
      downloadFolder.value = data.folder;
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ download_folder: data.folder }),
      });
      show(folderSaved);
      setTimeout(() => hide(folderSaved), 2000);
    }
  } catch {
    showError('Failed to open folder picker.');
  } finally {
    pickFolderBtn.disabled = false;
    pickFolderBtn.textContent = 'Choose Folder…';
  }
});

defaultFormat.addEventListener('change', async () => {
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ default_format: defaultFormat.value }),
    });
  } catch { /* ignore */ }
});

openFolderBtn.addEventListener('click', async () => {
  try {
    await fetch('/api/open-folder', { method: 'POST' });
  } catch { /* ignore */ }
});

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
