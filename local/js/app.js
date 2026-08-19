/**
 * AI Image Editor - Client Application Logic
 * Manages UI interactions, drag & drop, prompt preview, before/after slider,
 * sequential editing (Edit Again), history drawer, RunPod health & live cost counters.
 */

// Application State
const appState = {
  currentInputBase64: null,
  currentResultBase64: null,
  isProcessing: false,
  sliderPos: 50,
  activeViewMode: 'split', // 'split' or 'side'
  liveTimerInterval: null,
  healthPollingInterval: null,
  lastMetadata: null
};

// DOM Elements
const elements = {
  // Header / Status
  statusCapsule: document.getElementById('statusCapsule'),
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText'),
  uptimeCounter: document.getElementById('uptimeCounter'),
  costCounter: document.getElementById('costCounter'),
  btnReconnect: document.getElementById('btnReconnect'),
  btnOpenHistory: document.getElementById('btnOpenHistory'),
  btnOpenSettings: document.getElementById('btnOpenSettings'),
  historyCountBadge: document.getElementById('historyCountBadge'),
  offlineBanner: document.getElementById('offlineBanner'),
  offlineMsg: document.getElementById('offlineMsg'),
  btnBannerReconnect: document.getElementById('btnBannerReconnect'),

  // Dropzone / Image Input
  dropZone: document.getElementById('dropZone'),
  fileInput: document.getElementById('fileInput'),
  dropEmptyState: document.getElementById('dropEmptyState'),
  dropPreviewState: document.getElementById('dropPreviewState'),
  imagePreview: document.getElementById('imagePreview'),
  imageDimPill: document.getElementById('imageDimPill'),
  btnClearImage: document.getElementById('btnClearImage'),

  // Prompt & Controls
  promptInput: document.getElementById('promptInput'),
  langBadge: document.getElementById('langBadge'),
  btnAnalyzePrompt: document.getElementById('btnAnalyzePrompt'),
  modelSelect: document.getElementById('modelSelect'),
  identitySelect: document.getElementById('identitySelect'),
  qualitySelect: document.getElementById('qualitySelect'),
  seedInput: document.getElementById('seedInput'),
  btnRandomSeed: document.getElementById('btnRandomSeed'),
  btnGenerate: document.getElementById('btnGenerate'),

  // Viewport / Results
  viewportWrapper: document.getElementById('viewportWrapper'),
  viewerEmpty: document.getElementById('viewerEmpty'),
  viewerLoading: document.getElementById('viewerLoading'),
  loadingStatusText: document.getElementById('loadingStatusText'),
  liveTimer: document.getElementById('liveTimer'),
  sliderContainer: document.getElementById('sliderContainer'),
  imgBefore: document.getElementById('imgBefore'),
  imgAfter: document.getElementById('imgAfter'),
  afterWrapper: document.getElementById('afterWrapper'),
  sliderHandle: document.getElementById('sliderHandle'),
  sideContainer: document.getElementById('sideContainer'),
  imgBeforeSide: document.getElementById('imgBeforeSide'),
  imgAfterSide: document.getElementById('imgAfterSide'),
  viewerToolbar: document.getElementById('viewerToolbar'),
  tabSplit: document.getElementById('tabSplit'),
  tabSideBySide: document.getElementById('tabSideBySide'),
  viewerMetaPill: document.getElementById('viewerMetaPill'),
  genTimeBadge: document.getElementById('genTimeBadge'),
  genSeedBadge: document.getElementById('genSeedBadge'),

  // Action Buttons
  btnEditAgain: document.getElementById('btnEditAgain'),
  btnDownload: document.getElementById('btnDownload'),
  btnNewSession: document.getElementById('btnNewSession'),
  btnToggleDevMode: document.getElementById('btnToggleDevMode'),

  // Developer Mode Drawer
  devDrawer: document.getElementById('devDrawer'),
  btnCloseDev: document.getElementById('btnCloseDev'),
  devRawPrompt: document.getElementById('devRawPrompt'),
  devCategories: document.getElementById('devCategories'),
  devChangeTargets: document.getElementById('devChangeTargets'),
  devPreserveTargets: document.getElementById('devPreserveTargets'),
  devEnhancedPrompt: document.getElementById('devEnhancedPrompt'),
  btnCopyEnhanced: document.getElementById('btnCopyEnhanced'),
  devModelName: document.getElementById('devModelName'),
  devSeed: document.getElementById('devSeed'),
  devTime: document.getElementById('devTime'),
  devVram: document.getElementById('devVram'),

  // History Drawer
  historyDrawer: document.getElementById('historyDrawer'),
  btnCloseHistory: document.getElementById('btnCloseHistory'),
  historyList: document.getElementById('historyList'),

  // Settings Modal
  settingsModal: document.getElementById('settingsModal'),
  btnCloseSettings: document.getElementById('btnCloseSettings'),
  btnCancelSettings: document.getElementById('btnCancelSettings'),
  btnSaveSettings: document.getElementById('btnSaveSettings'),
  settingProviderType: document.getElementById('settingProviderType'),
  settingServerlessId: document.getElementById('settingServerlessId'),
  rowServerlessId: document.getElementById('rowServerlessId'),
  rowPodUrl: document.getElementById('rowPodUrl'),
  settingRunpodUrl: document.getElementById('settingRunpodUrl'),
  settingHourlyCost: document.getElementById('settingHourlyCost'),
  settingApiKey: document.getElementById('settingApiKey'),
  settingPodId: document.getElementById('settingPodId'),
  settingAutoStop: document.getElementById('settingAutoStop'),
  btnStartPod: document.getElementById('btnStartPod'),
  btnStopPod: document.getElementById('btnStopPod'),
  btnResetTimer: document.getElementById('btnResetTimer'),
  podControlMsg: document.getElementById('podControlMsg'),

  // Toast Container
  toastContainer: document.getElementById('toastContainer')
};

// ==========================================================================
// Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  initSliderDrag();
  loadConfig();
  fetchHealth();
  fetchHistory();

  // Health check polling every 5s
  appState.healthPollingInterval = setInterval(fetchHealth, 5000);
});

// ==========================================================================
// Event Listeners
// ==========================================================================
function initEventListeners() {
  // Dropzone & File Input
  elements.dropZone.addEventListener('click', () => elements.fileInput.click());
  elements.fileInput.addEventListener('change', handleFileSelect);

  elements.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.dropZone.classList.add('dragover');
  });

  elements.dropZone.addEventListener('dragleave', () => {
    elements.dropZone.classList.remove('dragover');
  });

  elements.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      processImageFile(e.dataTransfer.files[0]);
    }
  });

  // Global Clipboard Paste (Ctrl+V)
  window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let item of items) {
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        const file = item.getAsFile();
        processImageFile(file);
        showToast('تم لصق الصورة من الحافظة بنجاح', 'success');
        break;
      }
    }
  });

  elements.btnClearImage.addEventListener('click', clearInputImage);

  // Prompt input suggestions & language detector
  elements.promptInput.addEventListener('input', () => {
    const text = elements.promptInput.value.trim();
    const isArabic = /[\u0600-\u06FF]/.test(text);
    elements.langBadge.textContent = isArabic ? 'العربية' : 'English';
  });

  document.querySelectorAll('.suggestion-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      elements.promptInput.value = chip.getAttribute('data-prompt');
      elements.promptInput.dispatchEvent(new Event('input'));
      elements.promptInput.focus();
    });
  });

  // Prompt preview button
  elements.btnAnalyzePrompt.addEventListener('click', analyzePromptLocally);

  // Seed randomizer
  elements.btnRandomSeed.addEventListener('click', () => {
    elements.seedInput.value = Math.floor(100000 + Math.random() * 900000);
  });

  // Generate button & shortcut (Ctrl+Enter)
  elements.btnGenerate.addEventListener('click', executeGeneration);
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      executeGeneration();
    }
  });

  // View Mode Tabs (Slider vs Side-by-Side)
  elements.tabSplit.addEventListener('click', () => setViewMode('split'));
  elements.tabSideBySide.addEventListener('click', () => setViewMode('side'));

  // Result Toolbar Actions
  elements.btnEditAgain.addEventListener('click', handleEditAgain);
  elements.btnDownload.addEventListener('click', handleDownload);
  elements.btnNewSession.addEventListener('click', handleNewSession);
  elements.btnToggleDevMode.addEventListener('click', () => {
    elements.devDrawer.classList.toggle('hidden');
  });
  elements.btnCloseDev.addEventListener('click', () => {
    elements.devDrawer.classList.add('hidden');
  });
  elements.btnCopyEnhanced.addEventListener('click', () => {
    navigator.clipboard.writeText(elements.devEnhancedPrompt.textContent);
    showToast('تم نسخ الـ Enhanced Prompt بنجاح', 'success');
  });

  // History Drawer
  elements.btnOpenHistory.addEventListener('click', () => {
    elements.historyDrawer.classList.add('open');
    fetchHistory();
  });
  elements.btnCloseHistory.addEventListener('click', () => {
    elements.historyDrawer.classList.remove('open');
  });

  // Settings Modal
  elements.btnOpenSettings.addEventListener('click', openSettingsModal);
  elements.btnCloseSettings.addEventListener('click', closeSettingsModal);
  elements.btnCancelSettings.addEventListener('click', closeSettingsModal);
  elements.btnSaveSettings.addEventListener('click', saveSettings);
  elements.settingProviderType.addEventListener('change', updateSettingsVisibility);
  elements.btnReconnect.addEventListener('click', fetchHealth);
  elements.btnBannerReconnect.addEventListener('click', fetchHealth);

  // Pod Direct Action buttons
  elements.btnStartPod.addEventListener('click', handleStartPod);
  elements.btnStopPod.addEventListener('click', handleStopPod);
  elements.btnResetTimer.addEventListener('click', handleResetTimer);
}

// ==========================================================================
// Image Processing & Loading
// ==========================================================================
function handleFileSelect(e) {
  if (e.target.files.length > 0) {
    processImageFile(e.target.files[0]);
  }
}

function processImageFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('يرجى اختيار ملف صورة صالح (JPG, PNG, WEBP)', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target.result;
    setInputImage(base64);
  };
  reader.readAsDataURL(file);
}

function setInputImage(base64Str) {
  appState.currentInputBase64 = base64Str;
  elements.imagePreview.src = base64Str;

  const tempImg = new Image();
  tempImg.onload = () => {
    elements.imageDimPill.textContent = `${tempImg.naturalWidth} x ${tempImg.naturalHeight}`;
    elements.dropEmptyState.style.display = 'none';
    elements.dropPreviewState.style.display = 'flex';
    elements.btnClearImage.style.display = 'inline-block';
  };
  tempImg.src = base64Str;
}

function clearInputImage() {
  appState.currentInputBase64 = null;
  elements.imagePreview.src = '';
  elements.fileInput.value = '';
  elements.dropEmptyState.style.display = 'block';
  elements.dropPreviewState.style.display = 'none';
  elements.btnClearImage.style.display = 'none';
}

// ==========================================================================
// Local Prompt Engine Preview
// ==========================================================================
async function analyzePromptLocally() {
  const prompt = elements.promptInput.value.trim();
  if (!prompt) {
    showToast('اكتب وصف التعديل أولاً لمعاينته', 'info');
    return;
  }

  try {
    const resp = await fetch('/api/prompt/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        identity_strength: elements.identitySelect.value,
        quality: elements.qualitySelect.value
      })
    });

    if (!resp.ok) throw new Error('فشل تحليل الـ Prompt');
    const data = await resp.json();

    // Populate developer mode drawer and show it
    populateDevDrawer(data, null);
    elements.devDrawer.classList.remove('hidden');
    showToast('تم توسيع الـ Prompt محلياً وفق قواعد Preserve vs Change', 'info');
  } catch (err) {
    showToast(`خطأ أثناء تحليل النص: ${err.message}`, 'error');
  }
}

// ==========================================================================
// Generation Execution
// ==========================================================================
async function executeGeneration() {
  if (appState.isProcessing) return;

  if (!appState.currentInputBase64) {
    showToast('يرجى رفع صورة أولاً', 'error');
    return;
  }

  const prompt = elements.promptInput.value.trim();
  if (!prompt) {
    showToast('يرجى كتابة وصف التعديل المطلوب', 'error');
    elements.promptInput.focus();
    return;
  }

  // Set loading state
  appState.isProcessing = true;
  setGeneratingUI(true);

  const startTime = performance.now();
  let timerSec = 0;
  elements.liveTimer.textContent = '0.0s';
  appState.liveTimerInterval = setInterval(() => {
    timerSec += 0.1;
    elements.liveTimer.textContent = `${timerSec.toFixed(1)}s`;
  }, 100);

  const seedVal = parseInt(elements.seedInput.value);
  const payload = {
    image_base64: appState.currentInputBase64,
    prompt: prompt,
    model_name: elements.modelSelect.value,
    seed: isNaN(seedVal) ? null : seedVal,
    quality: elements.qualitySelect.value,
    identity_strength: elements.identitySelect.value
  };

  try {
    const resp = await fetch('/api/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json().catch(() => ({ detail: 'تعذر قراءة رد السيرفر' }));

    if (!resp.ok || !data.edit_response || !data.edit_response.success) {
      const errMsg = (data.edit_response && data.edit_response.error) || data.error || data.detail || 'حدث خطأ أثناء التوليد';
      throw new Error(errMsg);
    }

    // Success! Display results
    const editRes = data.edit_response;
    appState.currentResultBase64 = editRes.image_base64;
    appState.lastMetadata = data;

    renderResults(appState.currentInputBase64, appState.currentResultBase64, editRes.processing_time, editRes.seed);
    populateDevDrawer(data.prompt_analysis, editRes);
    fetchHistory();
    fetchHealth();
    showToast(`تم التعديل بنجاح في ${editRes.processing_time} ثانية!`, 'success');

  } catch (err) {
    console.error(err);
    showToast(`فشل التعديل: ${err.message}`, 'error');
    elements.viewerLoading.style.display = 'none';
    elements.viewerEmpty.style.display = 'block';
  } finally {
    appState.isProcessing = false;
    clearInterval(appState.liveTimerInterval);
    setGeneratingUI(false);
  }
}

function setGeneratingUI(isGenerating) {
  elements.btnGenerate.disabled = isGenerating;
  elements.btnGenerate.style.opacity = isGenerating ? '0.7' : '1';

  if (isGenerating) {
    elements.viewerEmpty.style.display = 'none';
    elements.sliderContainer.style.display = 'none';
    elements.sideContainer.style.display = 'none';
    elements.viewerToolbar.style.display = 'none';
    elements.viewerLoading.style.display = 'block';
  } else {
    elements.viewerLoading.style.display = 'none';
  }
}

function renderResults(beforeBase64, afterBase64, procTime, seed) {
  elements.imgBefore.src = beforeBase64;
  elements.imgAfter.src = afterBase64;
  elements.imgBeforeSide.src = beforeBase64;
  elements.imgAfterSide.src = afterBase64;

  elements.genTimeBadge.textContent = `⏱️ ${procTime}s`;
  elements.genSeedBadge.textContent = `🌱 Seed: ${seed}`;
  elements.viewerMetaPill.style.display = 'flex';

  setViewMode(appState.activeViewMode);
  elements.viewerToolbar.style.display = 'flex';
}

function setViewMode(mode) {
  appState.activeViewMode = mode;
  elements.tabSplit.classList.toggle('active', mode === 'split');
  elements.tabSideBySide.classList.toggle('active', mode === 'side');

  if (appState.currentResultBase64) {
    elements.sliderContainer.style.display = (mode === 'split') ? 'block' : 'none';
    elements.sideContainer.style.display = (mode === 'side') ? 'grid' : 'none';
  }
}

// ==========================================================================
// Split Comparison Slider Drag Logic
// ==========================================================================
function initSliderDrag() {
  let isDragging = false;

  const updateSlider = (clientX) => {
    const rect = elements.sliderContainer.getBoundingClientRect();
    let x = clientX - rect.left;
    x = Math.max(0, Math.min(x, rect.width));
    const percent = (x / rect.width) * 100;
    
    // For RTL layout or standard visual slider
    elements.afterWrapper.style.width = `${100 - percent}%`;
    elements.sliderHandle.style.left = `${percent}%`;
  };

  const onStart = (e) => {
    isDragging = true;
    updateSlider(e.touches ? e.touches[0].clientX : e.clientX);
  };

  const onMove = (e) => {
    if (!isDragging) return;
    updateSlider(e.touches ? e.touches[0].clientX : e.clientX);
  };

  const onEnd = () => {
    isDragging = false;
  };

  elements.sliderContainer.addEventListener('mousedown', onStart);
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onEnd);

  elements.sliderContainer.addEventListener('touchstart', onStart, { passive: true });
  window.addEventListener('touchmove', onMove, { passive: true });
  window.addEventListener('touchend', onEnd);
}

// ==========================================================================
// Result Actions: Edit Again & Download
// ==========================================================================
function handleEditAgain() {
  if (!appState.currentResultBase64) return;

  // Use current result as input image for sequential editing
  setInputImage(appState.currentResultBase64);
  elements.promptInput.value = '';
  elements.promptInput.focus();

  // Reset viewer to show new input
  elements.sliderContainer.style.display = 'none';
  elements.sideContainer.style.display = 'none';
  elements.viewerToolbar.style.display = 'none';
  elements.viewerEmpty.style.display = 'block';

  showToast('تم تعيين النتيجة كصورة مدخلة للتعديل التالي (Sequential Editing)', 'info');
}

function handleDownload() {
  if (!appState.currentResultBase64) return;

  const link = document.createElement('a');
  link.download = `edited_image_${Date.now()}.png`;
  link.href = appState.currentResultBase64;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('تم تحميل الصورة بنجاح', 'success');
}

function handleNewSession() {
  clearInputImage();
  elements.promptInput.value = '';
  elements.sliderContainer.style.display = 'none';
  elements.sideContainer.style.display = 'none';
  elements.viewerToolbar.style.display = 'none';
  elements.viewerEmpty.style.display = 'block';
  appState.currentResultBase64 = null;
}

// ==========================================================================
// Developer Mode Inspection Drawer
// ==========================================================================
function populateDevDrawer(promptAnalysis, editResponse) {
  if (promptAnalysis) {
    elements.devRawPrompt.textContent = promptAnalysis.original_prompt || '-';
    
    // Categories badges
    elements.devCategories.innerHTML = '';
    (promptAnalysis.categories || []).forEach(cat => {
      const tag = document.createElement('span');
      tag.className = 'tag tag-cat';
      tag.textContent = cat;
      elements.devCategories.appendChild(tag);
    });

    // Change vs Preserve
    elements.devChangeTargets.textContent = `Change: ${(promptAnalysis.change_targets || []).join(', ') || 'None'}`;
    elements.devPreserveTargets.textContent = `Preserve: ${(promptAnalysis.preserve_targets || []).slice(0, 3).join('; ') || 'Standard'}`;

    elements.devEnhancedPrompt.textContent = promptAnalysis.enhanced_prompt || '-';
  }

  if (editResponse) {
    elements.devModelName.textContent = editResponse.model_name || '-';
    elements.devSeed.textContent = editResponse.seed || '-';
    elements.devTime.textContent = `${editResponse.processing_time}s`;
    
    const meta = editResponse.metadata || {};
    elements.devVram.textContent = meta.engine || 'VRAM OK';
  }
}

// ==========================================================================
// History Drawer Logic
// ==========================================================================
async function fetchHistory() {
  try {
    const resp = await fetch('/api/history');
    if (!resp.ok) return;
    const items = await resp.json();

    elements.historyCountBadge.textContent = items.length;
    renderHistoryList(items);
  } catch (e) {
    console.warn('Failed to load history:', e);
  }
}

function renderHistoryList(items) {
  elements.historyList.innerHTML = '';
  if (items.length === 0) {
    elements.historyList.innerHTML = '<p style="color: var(--text-subtle); text-align: center; padding: 20px;">لا توجد تعديلات سابقة بعد.</p>';
    return;
  }

  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'history-card';
    card.innerHTML = `
      <div class="hist-header">
        <span>${item.date_str}</span>
        <span>⏱️ ${item.processing_time}s</span>
      </div>
      <div class="hist-images">
        <img src="${item.original_image_path}" alt="Before" title="الصورة الأصلية" />
        <img src="${item.result_image_path}" alt="After" title="النتيجة المعدلة" />
      </div>
      <div class="hist-prompt" title="${item.user_prompt}">"${item.user_prompt}"</div>
      <div class="hist-footer">
        <span>🌱 ${item.seed} | ${item.model_name}</span>
        <button class="btn-text-sm btn-delete-hist" data-id="${item.id}">حذف</button>
      </div>
    `;

    card.addEventListener('click', (e) => {
      if (e.target.classList.contains('btn-delete-hist')) {
        e.stopPropagation();
        deleteHistoryItem(item.id);
        return;
      }
      loadHistoryIntoEditor(item);
    });

    elements.historyList.appendChild(card);
  });
}

function loadHistoryIntoEditor(item) {
  setInputImage(item.original_image_path);
  appState.currentResultBase64 = item.result_image_path;
  elements.promptInput.value = item.user_prompt;
  renderResults(item.original_image_path, item.result_image_path, item.processing_time, item.seed);
  elements.historyDrawer.classList.remove('open');
  showToast('تم تحميل التعديل السابق في مساحة العمل', 'info');
}

async function deleteHistoryItem(id) {
  try {
    const resp = await fetch(`/api/history/${id}`, { method: 'DELETE' });
    if (resp.ok) {
      showToast('تم حذف العنصر من السجل', 'info');
      fetchHistory();
    }
  } catch (err) {
    showToast('فشل حذف العنصر', 'error');
  }
}

// ==========================================================================
// RunPod Health, Uptime, & Live Cost Tracking
// ==========================================================================
async function fetchHealth() {
  try {
    const resp = await fetch('/api/health');
    if (!resp.ok) throw new Error('Health check error');
    const data = await resp.json();

    const health = data.health;
    const isMock = (data.provider_type === 'mock');
    const isServerless = (data.provider_type === 'serverless');
    const isReady = (health.status === 'ready');

    elements.uptimeCounter.textContent = data.session_uptime_formatted;
    elements.costCounter.textContent = `$${data.estimated_cost_usd.toFixed(3)}`;

    if (isMock) {
      elements.statusDot.className = 'status-dot mock';
      elements.statusText.textContent = '⚡ Mock Mode (مجاني)';
      elements.offlineBanner.classList.add('hidden');
    } else if (isServerless) {
      if (isReady) {
        elements.statusDot.className = 'status-dot ready';
        elements.statusText.textContent = '☁️ Serverless Ready (Scale-to-Zero)';
        elements.offlineBanner.classList.add('hidden');
      } else {
        elements.statusDot.className = 'status-dot';
        elements.statusText.textContent = `○ Serverless (${health.gpu_name || 'Not Configured'})`;
        elements.offlineBanner.classList.remove('hidden');
      }
    } else if (isReady) {
      elements.statusDot.className = 'status-dot ready';
      elements.statusText.textContent = `● GPU Ready (${health.gpu_name || 'CUDA'})`;
      elements.offlineBanner.classList.add('hidden');
    } else {
      elements.statusDot.className = 'status-dot';
      elements.statusText.textContent = '○ RunPod Offline';
      elements.offlineBanner.classList.remove('hidden');
    }
  } catch (err) {
    elements.statusDot.className = 'status-dot';
    elements.statusText.textContent = '○ Server Offline';
    elements.offlineBanner.classList.remove('hidden');
  }
}

// ==========================================================================
// Settings Modal & Pod Management
// ==========================================================================
function updateSettingsVisibility() {
  const pType = elements.settingProviderType.value;
  if (pType === 'serverless') {
    elements.rowServerlessId.style.display = 'flex';
    elements.rowPodUrl.style.display = 'none';
  } else if (pType === 'runpod') {
    elements.rowServerlessId.style.display = 'none';
    elements.rowPodUrl.style.display = 'flex';
  } else {
    elements.rowServerlessId.style.display = 'none';
    elements.rowPodUrl.style.display = 'none';
  }
}

async function loadConfig() {
  try {
    const resp = await fetch('/api/config');
    if (!resp.ok) return;
    const cfg = await resp.json();

    elements.settingProviderType.value = cfg.provider_type || 'mock';
    elements.settingServerlessId.value = cfg.runpod_serverless_endpoint_id || '';
    elements.settingRunpodUrl.value = cfg.runpod_endpoint_url || 'http://127.0.0.1:8000';
    elements.settingHourlyCost.value = cfg.gpu_hourly_cost || 0.33;
    elements.settingApiKey.value = cfg.runpod_api_key || '';
    elements.settingPodId.value = cfg.runpod_pod_id || '';
    elements.settingAutoStop.value = cfg.auto_stop_minutes || 30;
    elements.modelSelect.value = cfg.default_model || 'FireRed-Image-Edit-1.1';
    elements.qualitySelect.value = cfg.default_quality || 'high';
    elements.identitySelect.value = cfg.default_identity_strength || 'high';

    updateSettingsVisibility();
  } catch (e) {
    console.warn('Failed to load config:', e);
  }
}

function openSettingsModal() {
  loadConfig();
  elements.podControlMsg.textContent = '';
  elements.settingsModal.classList.remove('hidden');
}

function closeSettingsModal() {
  elements.settingsModal.classList.add('hidden');
}

async function saveSettings() {
  const autoStopMin = parseInt(elements.settingAutoStop.value);
  const newConfig = {
    provider_type: elements.settingProviderType.value,
    runpod_serverless_endpoint_id: elements.settingServerlessId.value.trim(),
    runpod_endpoint_url: elements.settingRunpodUrl.value.trim(),
    gpu_hourly_cost: parseFloat(elements.settingHourlyCost.value) || 0.33,
    runpod_api_key: elements.settingApiKey.value.trim(),
    runpod_pod_id: elements.settingPodId.value.trim(),
    auto_stop_minutes: autoStopMin,
    auto_stop_enabled: autoStopMin > 0,
    default_model: elements.modelSelect.value,
    default_quality: elements.qualitySelect.value,
    default_identity_strength: elements.identitySelect.value,
    developer_mode: false
  };

  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    });

    if (resp.ok) {
      showToast('تم حفظ الإعدادات بنجاح', 'success');
      closeSettingsModal();
      fetchHealth();
    } else {
      throw new Error('فشل حفظ الإعدادات');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleStartPod() {
  elements.podControlMsg.textContent = 'جاري إرسال أمر التشغيل للـ Pod...';
  try {
    const resp = await fetch('/api/pod/start', { method: 'POST' });
    const data = await resp.json();
    elements.podControlMsg.textContent = data.message || 'تم إرسال الأمر.';
    showToast('تم طلب تشغيل الـ Pod', 'info');
  } catch (err) {
    elements.podControlMsg.textContent = `خطأ: ${err.message}`;
  }
}

async function handleStopPod() {
  elements.podControlMsg.textContent = 'جاري إرسال أمر الإيقاف للـ Pod...';
  try {
    const resp = await fetch('/api/pod/stop', { method: 'POST' });
    const data = await resp.json();
    elements.podControlMsg.textContent = data.message || 'تم إرسال الأمر.';
    showToast('تم طلب إيقاف الـ Pod', 'info');
  } catch (err) {
    elements.podControlMsg.textContent = `خطأ: ${err.message}`;
  }
}

async function handleResetTimer() {
  try {
    await fetch('/api/session/reset-timer', { method: 'POST' });
    fetchHealth();
    showToast('تم تصفير عداد الوقت والتكلفة', 'info');
  } catch (e) {
    console.warn(e);
  }
}

// ==========================================================================
// Toast Notification Utility
// ==========================================================================
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = (type === 'success') ? '✅' : (type === 'error') ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  
  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
