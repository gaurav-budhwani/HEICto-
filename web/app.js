/**
 * app.js - Minimalist, high-performance controller for HEICto-
 * Supports both full-stack server API and client-side static deployment.
 */

(function () {
  'use strict';

  // DOM Elements
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const formatSegmented = document.getElementById('formatSegmented');
  const colorProfileSelect = document.getElementById('colorProfileSelect');
  const qualitySlider = document.getElementById('qualitySlider');
  const qualityLabel = document.getElementById('qualityLabel');
  const qualityGroup = document.getElementById('qualityGroup');
  const dimensionSelect = document.getElementById('dimensionSelect');
  const queueSection = document.getElementById('queueSection');
  const queueList = document.getElementById('queueList');
  const queueCount = document.getElementById('queueCount');
  const zipBtn = document.getElementById('zipBtn');
  const clearBtn = document.getElementById('clearBtn');
  const linearProgress = document.getElementById('linearProgress');
  const linearProgressBar = document.getElementById('linearProgressBar');
  const themeToggle = document.getElementById('themeToggle');

  // Floating summary bar
  const floatingBar = document.getElementById('floatingBar');
  const floatingSummaryText = document.getElementById('floatingSummaryText');
  const floatingZipBtn = document.getElementById('floatingZipBtn');
  const floatingClearBtn = document.getElementById('floatingClearBtn');

  // Native Accessible Modal (<dialog>)
  const previewModal = document.getElementById('previewModal');
  const modalPreviewImg = document.getElementById('modalPreviewImg');
  const modalMetaGrid = document.getElementById('modalMetaGrid');
  const modalDownloadLink = document.getElementById('modalDownloadLink');

  // State
  const state = {
    targetFormat: 'png',
    quality: 100,
    colorProfile: 'srgb',
    maxDimension: 0,
    queue: [],
    completedJobs: [],
    activeWorkers: 0,
    maxConcurrent: 2,
    totalQueued: 0,
    totalFinished: 0,
    totalOriginalBytes: 0,
    totalConvertedBytes: 0,
  };

  /* ==========================================================================
     Theme Controller
     ========================================================================== */
  function initTheme() {
    const saved = localStorage.getItem('heic_studio_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('heic_studio_theme', next);
    });
  }

  /* ==========================================================================
     Controls and Settings
     ========================================================================== */
  function initControls() {
    // Format Segmented Buttons
    formatSegmented.addEventListener('click', (e) => {
      const btn = e.target.closest('.segment-btn');
      if (!btn) return;

      formatSegmented.querySelectorAll('.segment-btn').forEach((b) => {
        b.classList.remove('active');
        b.setAttribute('aria-checked', 'false');
      });

      btn.classList.add('active');
      btn.setAttribute('aria-checked', 'true');
      state.targetFormat = btn.dataset.format;

      if (state.targetFormat === 'png') {
        qualityGroup.style.opacity = '0.35';
        qualityGroup.style.pointerEvents = 'none';
      } else {
        qualityGroup.style.opacity = '1';
        qualityGroup.style.pointerEvents = 'auto';
      }
    });

    qualitySlider.addEventListener('input', (e) => {
      state.quality = parseInt(e.target.value, 10);
      qualityLabel.textContent = `${state.quality}%`;
    });

    colorProfileSelect.addEventListener('change', (e) => {
      state.colorProfile = e.target.value;
    });

    dimensionSelect.addEventListener('change', (e) => {
      state.maxDimension = parseInt(e.target.value, 10);
    });

    // Default PNG has quality inactive
    qualityGroup.style.opacity = '0.35';
    qualityGroup.style.pointerEvents = 'none';
  }

  /* ==========================================================================
     Dropzone & Clipboard Paste
     ========================================================================== */
  function initDropzone() {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    ['dragenter', 'dragover'].forEach((evt) => {
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'dragend', 'drop'].forEach((evt) => {
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files) {
        handleFiles(Array.from(e.dataTransfer.files));
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files) {
        handleFiles(Array.from(e.target.files));
      }
      fileInput.value = '';
    });

    // Support Cmd+V / Ctrl+V Paste anywhere on the page
    window.addEventListener('paste', (e) => {
      if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
        handleFiles(Array.from(e.clipboardData.files));
      }
    });
  }

  /* ==========================================================================
     Queue & Conversion Engine
     ========================================================================== */
  function handleFiles(files) {
    if (!files || files.length === 0) return;

    queueSection.style.display = 'flex';
    state.totalQueued += files.length;
    updateProgress();

    files.forEach((file) => {
      const item = {
        id: 'job_' + Math.random().toString(36).substr(2, 9),
        file: file,
        filename: file.name,
        size: formatBytes(file.size),
        originalBytes: file.size,
        format: state.targetFormat,
        quality: state.quality,
        colorProfile: state.colorProfile,
        maxDimension: state.maxDimension,
        status: 'queued',
        cardEl: null,
      };

      state.totalOriginalBytes += file.size;
      item.cardEl = createCardElement(item);
      queueList.prepend(item.cardEl);
      state.queue.push(item);
    });

    updateQueueCount();
    processQueue();
  }

  function processQueue() {
    while (state.activeWorkers < state.maxConcurrent && state.queue.length > 0) {
      const item = state.queue.shift();
      convertItem(item);
    }
  }

  async function convertItem(item) {
    state.activeWorkers++;
    item.status = 'converting';
    updateCardStatus(item);

    try {
      let result = null;

      // Check if we are on a static host (GitHub Pages, Cloudflare Pages, etc.)
      const isStaticHost = window.location.hostname.endsWith('github.io') ||
                           window.location.hostname.endsWith('pages.dev');

      // 1. Try Backend API first if NOT on static host
      if (!isStaticHost) {
        try {
          const formData = new FormData();
          formData.append('file', item.file, item.filename);
          formData.append('format', item.format);
          formData.append('quality', item.quality.toString());
          formData.append('color_profile', item.colorProfile);
          formData.append('max_dimension', item.maxDimension.toString());

          const res = await fetch('/api/convert', { method: 'POST', body: formData });
          if (res.ok) {
            result = await res.json();
          }
        } catch (networkErr) {
          // Backend not reachable, fall through to client-side decoder
        }
      }

      // 2. Client-side multi-strategy decoder
      if (!result || !result.success) {
        result = await convertClientSide(item);
      }

      if (!result || !result.success) {
        throw new Error((result && result.error) || 'Failed to decode image');
      }

      item.status = 'ready';
      item.result = result;
      state.completedJobs.push(result);

      if (result.converted_info && result.converted_info.size_bytes) {
        state.totalConvertedBytes += result.converted_info.size_bytes;
      }

      updateCardSuccess(item, result);
      zipBtn.disabled = false;
      updateFloatingBar();
    } catch (err) {
      console.error('Conversion failed for', item.filename, err);
      item.status = 'failed';
      item.error = err.message || 'Decoding error';
      updateCardError(item, item.error);
    } finally {
      state.activeWorkers--;
      state.totalFinished++;
      updateProgress();
      updateQueueCount();
      processQueue();
    }
  }

  /**
   * Multi-strategy client-side decoder for static hosting (GitHub Pages).
   * Strategy 1: Native browser ImageBitmap (Safari 17+ on Mac & iOS — hardware accelerated)
   * Strategy 2: Modern heic-to (WASM libheif build tracking modern iOS formats)
   * Strategy 3: heic2any fallback
   */
  async function convertClientSide(item) {
    const isJpeg = item.format === 'jpeg' || item.format === 'jpg';
    const mimeType = isJpeg ? 'image/jpeg' : (item.format === 'webp' ? 'image/webp' : 'image/png');
    const quality = item.quality / 100.0;

    // Strategy 1: Native ImageBitmap (Instant on Safari 17+ / macOS / iOS)
    try {
      const bitmap = await createImageBitmap(item.file, { imageOrientation: 'from-image' });
      let targetW = bitmap.width;
      let targetH = bitmap.height;
      if (item.maxDimension > 0 && Math.max(targetW, targetH) > item.maxDimension) {
        const scale = item.maxDimension / Math.max(targetW, targetH);
        targetW = Math.round(targetW * scale);
        targetH = Math.round(targetH * scale);
      }
      const canvas = document.createElement('canvas');
      canvas.width = targetW;
      canvas.height = targetH;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap, 0, 0, targetW, targetH);
      bitmap.close();

      const blob = await new Promise((res, rej) => {
        canvas.toBlob((b) => (b ? res(b) : rej(new Error('Canvas export error'))), mimeType, quality);
      });
      if (blob && blob.size > 0) {
        return makeClientResult(item, blob, targetW, targetH, 'Native Apple Engine');
      }
    } catch (nativeErr) {
      console.info('Native browser decoder unavailable, trying modern WASM decoder...');
    }

    // Strategy 2: Modern heic-to (dynamically loaded via ESM)
    try {
      const mod = await import('https://cdn.jsdelivr.net/npm/heic-to@1.6.7/+esm');
      if (mod && mod.heicTo) {
        const blob = await mod.heicTo({
          blob: item.file,
          type: mimeType,
          quality: quality,
        });
        if (blob && blob.size > 0) {
          return makeClientResult(item, blob, 0, 0, 'WASM Engine');
        }
      }
    } catch (heicToErr) {
      console.warn('heic-to error, trying legacy fallback...', heicToErr);
    }

    // Strategy 3: heic2any fallback
    if (typeof window.heic2any === 'function') {
      try {
        const res = await window.heic2any({
          blob: item.file,
          toType: mimeType,
          quality: quality,
        });
        const finalBlob = Array.isArray(res) ? res[0] : res;
        if (finalBlob && finalBlob.size > 0) {
          return makeClientResult(item, finalBlob, 0, 0, 'WASM Fallback');
        }
      } catch (heic2anyErr) {
        console.warn('heic2any error:', heic2anyErr);
      }
    }

    throw new Error('This browser could not decode this HEIC file. Try Safari or run locally.');
  }

  function makeClientResult(item, blob, width, height, engineLabel) {
    const isJpeg = item.format === 'jpeg' || item.format === 'jpg';
    const ext = isJpeg ? '.jpg' : (item.format === 'webp' ? '.webp' : '.png');
    const base = item.filename.replace(/\.[^/.]+$/, '');
    const convertedFilename = `${base}${ext}`;
    const url = URL.createObjectURL(blob);

    return {
      success: true,
      job_id: item.id,
      original_filename: item.filename,
      converted_filename: convertedFilename,
      download_url: url,
      thumbnail_url: url,
      duration_ms: 100,
      color_profile_used: item.colorProfile,
      original_info: {
        format: 'HEIC',
        size_bytes: item.file.size,
        size_formatted: formatBytes(item.file.size),
        width: width || 0,
        height: height || 0,
      },
      converted_info: {
        format: item.format.toUpperCase(),
        size_bytes: blob.size,
        size_formatted: formatBytes(blob.size),
        width: width || 0,
        height: height || 0,
        profile: engineLabel || 'sRGB (Display)',
      },
      is_client_blob: true,
      blob: blob,
    };
  }

  /* ==========================================================================
     UI Card Elements
     ========================================================================== */
  function createCardElement(item) {
    const card = document.createElement('div');
    card.className = 'queue-card';
    card.id = `card_${item.id}`;

    card.innerHTML = `
      <div class="card-main">
        <div class="card-thumb-box" title="Thumbnail preview">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="opacity:0.4;">
            <rect x="3" y="3" width="18" height="18" rx="3"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <path d="M21 15l-5-5L5 21"></path>
          </svg>
        </div>
        <div class="card-details">
          <span class="card-title" title="${item.filename}">${item.filename}</span>
          <div class="card-pills">
            <span class="pill-tag">${item.size}</span>
            <span class="pill-tag">→ ${item.format.toUpperCase()}</span>
            <span class="pill-tag">${item.colorProfile === 'srgb' ? 'sRGB' : 'Display P3'}</span>
          </div>
        </div>
      </div>
      <div class="card-actions">
        <span class="status-indicator converting">
          <span class="spin"></span>
          <span>Converting</span>
        </span>
      </div>
    `;

    return card;
  }

  function updateCardStatus(item) {
    const card = document.getElementById(`card_${item.id}`);
    if (!card) return;
    const actions = card.querySelector('.card-actions');
    if (actions) {
      actions.innerHTML = `
        <span class="status-indicator converting">
          <span class="spin"></span>
          <span>Converting</span>
        </span>
      `;
    }
  }

  function updateCardSuccess(item, result) {
    const card = document.getElementById(`card_${item.id}`);
    if (!card) return;

    // Thumbnail
    const thumbBox = card.querySelector('.card-thumb-box');
    if (thumbBox && result.thumbnail_url) {
      thumbBox.innerHTML = `<img src="${result.thumbnail_url}" alt="" class="card-thumb-img">`;
      thumbBox.addEventListener('click', () => openPreviewModal(result));
    }

    // Details
    const origInfo = result.original_info || {};
    const convInfo = result.converted_info || {};
    const origBytes = origInfo.size_bytes || item.originalBytes || 0;
    const convBytes = convInfo.size_bytes || 0;

    let savedTag = '';
    if (origBytes > 0 && convBytes > 0 && convBytes < origBytes) {
      const pct = Math.round(((origBytes - convBytes) / origBytes) * 100);
      savedTag = `<span class="pill-tag saved">-${pct}%</span>`;
    }

    const details = card.querySelector('.card-details');
    if (details) {
      const dim = convInfo.width ? `${convInfo.width}×${convInfo.height}` : '';
      details.innerHTML = `
        <span class="card-title" title="${result.converted_filename}">${result.converted_filename}</span>
        <div class="card-pills">
          <span class="pill-tag">${origInfo.size_formatted || item.size} → <strong>${convInfo.size_formatted || ''}</strong></span>
          ${savedTag}
          ${dim ? `<span class="pill-tag">${dim}</span>` : ''}
          <span class="pill-tag">${convInfo.profile || 'sRGB'}</span>
        </div>
      `;
    }

    // Actions
    const actions = card.querySelector('.card-actions');
    if (actions) {
      actions.innerHTML = `
        <span class="status-indicator ready">Ready</span>
        <a href="${result.download_url}" class="btn-solid" download="${result.converted_filename}">
          Download
        </a>
      `;
    }
  }

  function updateCardError(item, errorMsg) {
    const card = document.getElementById(`card_${item.id}`);
    if (!card) return;
    const details = card.querySelector('.card-details');
    if (details) {
      const errEl = document.createElement('div');
      errEl.style.fontSize = '11px';
      errEl.style.color = 'var(--accent-danger)';
      errEl.style.fontFamily = 'var(--font-mono)';
      errEl.style.marginTop = '2px';
      errEl.textContent = errorMsg || 'Decoding error';
      details.appendChild(errEl);
    }
    const actions = card.querySelector('.card-actions');
    if (actions) {
      actions.innerHTML = `
        <span class="status-indicator failed" title="${errorMsg}">Failed</span>
      `;
    }
  }

  function updateQueueCount() {
    const total = state.totalQueued;
    const finished = state.totalFinished;
    const remaining = state.queue.length + state.activeWorkers;

    if (remaining > 0) {
      queueCount.textContent = `Processing ${finished + 1} of ${total}...`;
    } else {
      queueCount.textContent = `${total} items`;
    }
  }

  function updateProgress() {
    if (state.totalQueued === 0) {
      linearProgress.style.display = 'none';
      return;
    }

    const pct = Math.round((state.totalFinished / state.totalQueued) * 100);
    linearProgressBar.style.width = `${pct}%`;

    if (pct >= 100) {
      setTimeout(() => {
        linearProgress.style.display = 'none';
      }, 600);
    } else {
      linearProgress.style.display = 'block';
    }
  }

  function updateFloatingBar() {
    const count = state.completedJobs.length;
    if (count > 0) {
      floatingBar.style.display = 'block';
      let savedText = '';
      if (state.totalOriginalBytes > state.totalConvertedBytes && state.totalConvertedBytes > 0) {
        const savedMb = (state.totalOriginalBytes - state.totalConvertedBytes) / (1024 * 1024);
        savedText = ` • Saved ${savedMb.toFixed(1)} MB`;
      }
      floatingSummaryText.textContent = `${count} ${count === 1 ? 'photo' : 'photos'} ready${savedText}`;
    } else {
      floatingBar.style.display = 'none';
    }
  }

  /* ==========================================================================
     Batch ZIP Export & Reset
     ========================================================================== */
  async function downloadBatchZip() {
    if (state.completedJobs.length === 0) return;

    // If using client-side fallback with JSZip or server API
    const hasClientBlobs = state.completedJobs.some((j) => j.is_client_blob);

    if (!hasClientBlobs) {
      try {
        const jobIds = state.completedJobs.map((j) => j.job_id);
        const res = await fetch('/api/download-zip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_ids: jobIds }),
        });
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `heicto_export_${new Date().toISOString().slice(0, 10)}.zip`;
          a.click();
          URL.revokeObjectURL(url);
          return;
        }
      } catch (err) {
        // Fall back to client-side zip
      }
    }

    // Client-side JSZip bundling (perfect for GitHub Pages static hosting)
    if (typeof window.JSZip === 'function') {
      const zip = new window.JSZip();
      for (const job of state.completedJobs) {
        if (job.blob) {
          zip.file(job.converted_filename, job.blob);
        } else if (job.download_url) {
          try {
            const resp = await fetch(job.download_url);
            const b = await resp.blob();
            zip.file(job.converted_filename, b);
          } catch (e) {}
        }
      }
      const zipContent = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipContent);
      const a = document.createElement('a');
      a.href = url;
      a.download = `heicto_export_${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      // Fallback: individual downloads
      state.completedJobs.forEach((job, idx) => {
        setTimeout(() => {
          const a = document.createElement('a');
          a.href = job.download_url;
          a.download = job.converted_filename;
          a.click();
        }, idx * 150);
      });
    }
  }

  zipBtn.addEventListener('click', downloadBatchZip);
  floatingZipBtn.addEventListener('click', downloadBatchZip);

  function clearAll() {
    queueList.innerHTML = '';
    state.queue = [];
    state.completedJobs = [];
    state.totalQueued = 0;
    state.totalFinished = 0;
    state.totalOriginalBytes = 0;
    state.totalConvertedBytes = 0;

    zipBtn.disabled = true;
    queueSection.style.display = 'none';
    floatingBar.style.display = 'none';
    linearProgress.style.display = 'none';

    fetch('/api/clear', { method: 'POST' }).catch(() => {});
  }

  clearBtn.addEventListener('click', clearAll);
  floatingClearBtn.addEventListener('click', clearAll);

  /* ==========================================================================
     Native Accessible Dialog Modal (<dialog>)
     ========================================================================== */
  function openPreviewModal(job) {
    modalPreviewImg.src = job.download_url;
    modalDownloadLink.href = job.download_url;
    modalDownloadLink.download = job.converted_filename;

    const orig = job.original_info || {};
    const conv = job.converted_info || {};

    modalMetaGrid.innerHTML = `
      <div class="meta-item">
        <span class="meta-item-label">Original</span>
        <span class="meta-item-val">${orig.format || 'HEIC'} (${orig.size_formatted || 'N/A'})</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-label">Converted</span>
        <span class="meta-item-val">${conv.format || 'PNG'} (${conv.size_formatted || 'N/A'})</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-label">Dimensions</span>
        <span class="meta-item-val">${conv.width || orig.width || '—'} × ${conv.height || orig.height || '—'}</span>
      </div>
      <div class="meta-item">
        <span class="meta-item-label">Color Space</span>
        <span class="meta-item-val">${conv.profile || 'sRGB'}</span>
      </div>
    `;

    // Modern Native Modal Invocation
    previewModal.showModal();
  }

  // Light-Dismiss Fallback as required by modern-web-guidance for browsers lacking closedBy
  if (!('closedBy' in HTMLDialogElement.prototype)) {
    previewModal.addEventListener('click', (event) => {
      if (event.target !== previewModal) return;
      const rect = previewModal.getBoundingClientRect();
      const isInside = (
        rect.top <= event.clientY &&
        event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX &&
        event.clientX <= rect.left + rect.width
      );
      if (!isInside) {
        previewModal.close();
      }
    });
  }

  /* ==========================================================================
     Utilities
     ========================================================================== */
  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initControls();
    initDropzone();
  });
})();
