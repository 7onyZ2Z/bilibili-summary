import './styles.css';
import { marked } from 'marked';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// State
const state = {
  activeEventSource: null,
  currentProgress: 0,
  activeJobId: null,
  isSubmitting: false,
  cacheStats: null,
};

// DOM Elements
const elements = {};

// Initialize DOM element references
function initElements() {
  const app = document.querySelector('#app');
  app.innerHTML = getTemplate();

  // Cache all frequently used elements
  elements.apiHealth = document.querySelector('#api-health');
  elements.apiUrl = document.querySelector('.api-url');
  elements.taskArea = document.querySelector('#task-area');
  elements.progressFill = document.querySelector('#progress-fill');
  elements.progressPercent = document.querySelector('#progress-percent');
  elements.progressStage = document.querySelector('#progress-stage');
  elements.markdownPreview = document.querySelector('#markdown-preview');
  elements.downloadActions = document.querySelector('#download-actions');
  elements.downloadMd = document.querySelector('#download-md');
  elements.downloadPdf = document.querySelector('#download-pdf');
  elements.cancelTaskBtn = document.querySelector('#cancel-task');
  elements.clearLogBtn = document.querySelector('#clear-log');
  elements.singleSubmitBtn = document.querySelector('#single-submit');
  elements.batchSubmitBtn = document.querySelector('#batch-submit');
  elements.singleUrlInput = document.querySelector('#single-url');
  elements.batchUrlsTextarea = document.querySelector('#batch-urls');
  elements.toastContainer = document.querySelector('.toast-container');
}

// HTML Template
function getTemplate() {
  return `
    <main class="shell">
      <div class="bg-orb orb-1" aria-hidden="true"></div>
      <div class="bg-orb orb-2" aria-hidden="true"></div>
      <div class="bg-orb orb-3" aria-hidden="true"></div>

      <header class="hero">
        <div class="hero-left">
          <p class="chip">Bilibili 面试知识点提炼</p>
          <h1>面试视频<br/>极速变笔记</h1>
          <p class="sub">
            输入 B 站链接，自动完成下载、转写、总结，输出结构化 Markdown。
            <br/>支持单个视频和批量处理，智能缓存已处理内容。
          </p>
        </div>
        <div class="hero-right">
          <div class="metric">
            <span class="metric-label">接口状态</span>
            <strong id="api-health">待检测</strong>
          </div>
          <div class="metric">
            <span class="metric-label">当前 API</span>
            <strong class="api-url">${API_BASE_URL}</strong>
          </div>
          <div class="metric" id="cache-metric" style="display: none;">
            <span class="metric-label">缓存状态</span>
            <strong id="cache-stats">-</strong>
          </div>
        </div>
      </header>

      <section class="panel">
        <div class="tabs">
          <button class="tab active" data-tab="single">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.18l6.9 3.45L12 11.09 5.1 7.63 12 4.18zM4 8.82l7 3.5v7.36l-7-3.5V8.82zm9 10.86v-7.36l7-3.5v7.36l-7 3.5z"/>
            </svg>
            单视频
          </button>
          <button class="tab" data-tab="batch">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"/>
            </svg>
            批量处理
          </button>
        </div>

        <div class="tab-content active" id="single">
          <div class="input-group">
            <label for="single-url">视频链接</label>
            <div class="input-wrapper">
              <input id="single-url" placeholder="https://www.bilibili.com/video/BV..." />
              <button class="paste-btn" id="paste-url" title="粘贴链接">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm0 4c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm6 12H6v-1.4c0-2 4-3.1 6-3.1s6 1.1 6 3.1V19z"/>
                </svg>
                粘贴
              </button>
            </div>
          </div>
          <button class="action" id="single-submit">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="display: inline-block; vertical-align: middle; margin-right: 6px;">
              <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.18l6.9 3.45L12 11.09 5.1 7.63 12 4.18z"/>
            </svg>
            生成总结
          </button>
        </div>

        <div class="tab-content" id="batch">
          <div class="input-group">
            <label for="batch-urls">批量链接（每行一个）</label>
            <div class="input-wrapper">
              <textarea id="batch-urls" rows="7" placeholder="https://www.bilibili.com/video/BV...\nhttps://www.bilibili.com/video/BV..."></textarea>
              <button class="paste-btn" id="paste-batch" style="top: 32px; right: 8px;" title="粘贴链接">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
                </svg>
                粘贴
              </button>
            </div>
          </div>
          <button class="action" id="batch-submit">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="display: inline-block; vertical-align: middle; margin-right: 6px;">
              <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"/>
            </svg>
            批量生成
          </button>
        </div>

        <section class="task-area" id="task-area" hidden>
          <div class="result-head">
            <h2>执行进度</h2>
            <div class="actions-inline">
              <button id="cancel-task" class="ghost danger" hidden>取消任务</button>
              <button id="clear-log" class="ghost">清空</button>
            </div>
          </div>

          <section class="progress-card" aria-live="polite">
            <div class="progress-track">
              <div id="progress-fill" class="progress-fill"></div>
              <span id="progress-percent" class="progress-percent">0%</span>
            </div>
            <p id="progress-stage" class="progress-stage">
              <span class="progress-stage-icon"></span>
              当前阶段：等待任务启动
            </p>
          </section>

          <div class="download-actions" id="download-actions" hidden>
            <a id="download-md" class="action small" href="#" target="_blank" rel="noopener">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
              </svg>
              下载 MD
            </a>
            <a id="download-pdf" class="action small secondary" href="#" target="_blank" rel="noopener">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z"/>
              </svg>
              下载 PDF
            </a>
          </div>

          <article class="markdown-preview" id="markdown-preview" hidden>
            <p class="placeholder">任务完成后，将在这里预览最终 Markdown 文档。</p>
          </article>
        </section>
      </section>

      <div class="toast-container"></div>

      <div class="shortcuts-hint">
        <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 提交 · <kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴
      </div>

      <footer class="footer">
        Made with ❤️ for Bilibili | <a href="https://github.com" target="_blank" rel="noopener">GitHub</a>
      </footer>
    </main>
  `;
}

// Toast Notifications
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icon = document.createElement('div');
  icon.className = 'toast-icon';

  const text = document.createElement('span');
  text.className = 'toast-message';
  text.textContent = message;

  toast.appendChild(icon);
  toast.appendChild(text);

  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// Log Patterns (pre-compiled for performance)
const LOG_PATTERNS = [
  { pattern: /^任务提交中/, percent: 5, stage: '任务已提交', icon: '📤' },
  { pattern: /^开始处理视频/, percent: 10, stage: '开始处理视频', icon: '🎬' },
  { pattern: /^步骤 1\/5/, percent: 20, stage: '解析链接与拉取视频元数据', icon: '🔍' },
  { pattern: /^步骤 2\/5|^下载尝试/, percent: 40, stage: '下载音频中...', icon: '⬇️' },
  { pattern: /^步骤 3\/5/, percent: 60, stage: '音频转写中...', icon: '🎤' },
  { pattern: /^步骤 4\/5/, percent: 80, stage: '生成总结与面试问答...', icon: '🤖' },
  { pattern: /^步骤 5\/5/, percent: 95, stage: '渲染并写入 Markdown...', icon: '📝' },
  { pattern: /^处理完成|^批量任务完成/, percent: 100, stage: '处理完成 ✅', icon: '✅' },
  { pattern: /^批量任务启动/, percent: 10, stage: '批量任务启动', icon: '🚀' },
  { pattern: /^任务开始/, percent: 30, stage: '批量处理中...', icon: '⚙️', useMax: true },
  { pattern: /^任务结束/, percent: 70, stage: '批量处理中...', icon: '⚙️', useMax: true },
  { pattern: /^使用缓存结果/, percent: 100, stage: '使用缓存结果 (极速) ⚡', icon: '⚡' },
];

// Progress Management
function setProgress(percent, stage, icon = null) {
  const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
  state.currentProgress = safePercent;

  elements.progressFill.style.width = `${safePercent}%`;
  elements.progressPercent.textContent = `${safePercent}%`;
  elements.progressPercent.style.left = `${Math.max(4, Math.min(96, safePercent))}%`;

  const iconHtml = icon ? `<span style="margin-right: 4px;">${icon}</span>` : '<span class="progress-stage-icon"></span>';
  elements.progressStage.innerHTML = `${iconHtml}当前阶段：${stage}`;
}

function resetProgress() {
  setProgress(0, '等待任务启动');
}

function shouldDisplayLog(line) {
  if (!line) return false;
  if (line.includes('配置已加载:')) return false;
  return true;
}

function normalizeLogLine(line) {
  return line.replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, '').trim();
}

function updateProgressFromLine(line) {
  if (!shouldDisplayLog(line)) return;

  const plain = normalizeLogLine(line);

  // Check for error conditions first
  if (/失败|错误:|异常/.test(plain)) {
    setProgress(state.currentProgress || 5, '任务失败 ❌', '❌');
    showToast('任务失败，请查看日志', 'error');
    return;
  }

  // Match against pre-compiled patterns
  for (const { pattern, percent, stage, icon, useMax } of LOG_PATTERNS) {
    if (pattern.test(plain)) {
      const finalPercent = useMax ? Math.max(state.currentProgress, percent) : percent;
      setProgress(finalPercent, stage, icon);
      return;
    }
  }
}

// State Management
function setRunningState(running) {
  if (elements.cancelTaskBtn) {
    elements.cancelTaskBtn.hidden = !running;
  }
  if (elements.singleSubmitBtn) {
    elements.singleSubmitBtn.disabled = running;
  }
  if (elements.batchSubmitBtn) {
    elements.batchSubmitBtn.disabled = running;
  }
}

function cleanupEventSource() {
  if (state.activeEventSource) {
    state.activeEventSource.close();
    state.activeEventSource = null;
  }
  state.isSubmitting = false;
}

// UI Updates
function clearPreview() {
  elements.taskArea.hidden = true;
  elements.markdownPreview.innerHTML = '<p class="placeholder">任务完成后，将在这里预览最终 Markdown 文档。</p>';
  elements.markdownPreview.hidden = true;
  elements.downloadActions.hidden = true;
  elements.downloadMd.href = '#';
  elements.downloadPdf.href = '#';
}

function showTaskArea() {
  elements.taskArea.hidden = false;
}

function renderMarkdown(markdown) {
  elements.markdownPreview.innerHTML = marked.parse(markdown);
  elements.markdownPreview.hidden = false;
}

// API Calls
async function callApi(path, body) {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }

  return resp.json();
}

async function checkHealth() {
  elements.apiHealth.textContent = '检测中';
  elements.apiHealth.className = 'checking';

  try {
    const resp = await fetch(`${API_BASE_URL}/health`);
    if (resp.ok) {
      elements.apiHealth.textContent = '在线';
      elements.apiHealth.className = 'ok';
      // Also fetch cache stats
      fetchCacheStats();
      return;
    }
  } catch (_) {
    // ignore
  }
  elements.apiHealth.textContent = '离线';
  elements.apiHealth.className = 'bad';
}

async function fetchCacheStats() {
  try {
    const resp = await fetch(`${API_BASE_URL}/cache/stats`);
    if (resp.ok) {
      const stats = await resp.json();
      state.cacheStats = stats;
      const cacheMetric = document.querySelector('#cache-metric');
      const cacheStatsEl = document.querySelector('#cache-stats');
      if (cacheMetric && cacheStatsEl) {
        cacheMetric.style.display = '';
        cacheStatsEl.textContent = `${stats.entry_count} 项 (${stats.total_size_mb} MB)`;
      }
    }
  } catch (_) {
    // ignore
  }
}

// Task Management
async function submitSingle() {
  if (state.isSubmitting) return;

  const url = elements.singleUrlInput.value.trim();

  if (!url) {
    showToast('请先输入视频链接', 'error');
    elements.singleUrlInput.focus();
    return;
  }

  // Validate URL
  if (!url.includes('bilibili.com/video/') && !url.includes('b23.tv')) {
    showToast('请输入有效的 B 站视频链接', 'error');
    return;
  }

  state.isSubmitting = true;
  resetProgress();
  clearPreview();
  showTaskArea();
  showToast('任务已提交', 'info');

  try {
    const job = await callApi('/jobs/single', { url });
    state.activeJobId = job.job_id;
    setRunningState(true);
    await streamJob(job.job_id, true);
  } catch (err) {
    setProgress(state.currentProgress || 5, '任务失败 ❌', '❌');
    showToast(err.message, 'error');
    setRunningState(false);
  } finally {
    state.isSubmitting = false;
  }
}

async function submitBatch() {
  if (state.isSubmitting) return;

  const raw = elements.batchUrlsTextarea.value;
  const urls = raw
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean);

  if (!urls.length) {
    showToast('请至少输入一个链接', 'error');
    elements.batchUrlsTextarea.focus();
    return;
  }

  state.isSubmitting = true;
  resetProgress();
  clearPreview();
  showTaskArea();
  showToast(`批量任务已提交 (${urls.length} 个视频)`, 'info');

  try {
    const job = await callApi('/jobs/batch', { urls });
    state.activeJobId = job.job_id;
    setRunningState(true);
    await streamJob(job.job_id, false);
  } catch (err) {
    setProgress(state.currentProgress || 5, '任务失败 ❌', '❌');
    showToast(err.message, 'error');
    setRunningState(false);
  } finally {
    state.isSubmitting = false;
  }
}

async function streamJob(jobId, isSingle) {
  cleanupEventSource();

  return new Promise((resolve, reject) => {
    const es = new EventSource(`${API_BASE_URL}/jobs/${jobId}/stream`);
    state.activeEventSource = es;

    es.onmessage = async (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === 'log' && payload.message) {
          updateProgressFromLine(payload.message);
          return;
        }

        if (payload.event === 'error') {
          updateProgressFromLine(`错误: ${payload.message || '未知错误'}`);
          return;
        }

        if (payload.event === 'done') {
          es.close();
          const status = await fetchJobStatus(jobId, isSingle);
          setRunningState(false);
          state.activeJobId = null;
          resolve(status);
        }
      } catch (err) {
        es.close();
        reject(err);
      }
    };

    es.onerror = async () => {
      es.close();
      try {
        setProgress(Math.max(state.currentProgress, 10), '连接波动，正在同步任务状态...', '🔄');
        const status = await waitForTerminalStatus(jobId, isSingle);
        setRunningState(false);
        state.activeJobId = null;
        resolve(status);
      } catch (err) {
        setRunningState(false);
        reject(err);
      }
    };
  });
}

async function waitForTerminalStatus(jobId, isSingle) {
  const terminal = new Set(['completed', 'failed', 'canceled']);
  for (let i = 0; i < 300; i += 1) {
    const status = await fetchJobStatus(jobId, isSingle);
    if (terminal.has(status.status)) {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error('任务状态同步超时，请手动刷新页面后重试');
}

async function fetchJobStatus(jobId, isSingle) {
  const resp = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
  if (!resp.ok) {
    throw new Error(`获取任务状态失败: HTTP ${resp.status}`);
  }

  const status = await resp.json();

  // Replay logs to update progress
  if (status.logs) {
    status.logs.forEach((line) => updateProgressFromLine(line));
  }

  if (status.status === 'failed') {
    setProgress(state.currentProgress || 5, '任务失败 ❌', '❌');
    showToast('任务处理失败', 'error');
  }

  if (status.status === 'canceled') {
    setProgress(state.currentProgress || 5, '任务已取消', '⏹️');
    showToast('任务已取消', 'info');
  }

  if (status.status === 'completed' && status.output_files && status.output_files.length > 0) {
    await loadMarkdownAndDownloads(jobId);
    showToast('任务完成！', 'success');
  }

  return status;
}

async function loadMarkdownAndDownloads(jobId) {
  const resp = await fetch(`${API_BASE_URL}/jobs/${jobId}/markdown`);
  if (!resp.ok) {
    showToast('任务完成，但未获取到 Markdown 预览内容。', 'info');
    return;
  }

  const payload = await resp.json();
  renderMarkdown(payload.content || '');

  elements.downloadMd.href = `${API_BASE_URL}/jobs/${jobId}/download/md`;
  elements.downloadPdf.href = `${API_BASE_URL}/jobs/${jobId}/download/pdf`;
  elements.downloadActions.hidden = false;
}

// Event Handlers
function setupEventListeners() {
  // Tab switching
  document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach((x) => x.classList.remove('active'));
      btn.classList.add('active');
      document.querySelector(`#${btn.dataset.tab}`)?.classList.add('active');
    });
  });

  // Submit buttons
  elements.singleSubmitBtn.addEventListener('click', submitSingle);
  elements.batchSubmitBtn.addEventListener('click', submitBatch);

  // Cancel task
  elements.cancelTaskBtn.addEventListener('click', async () => {
    if (!state.activeJobId) return;
    try {
      await fetch(`${API_BASE_URL}/jobs/${state.activeJobId}/cancel`, { method: 'POST' });
      setProgress(state.currentProgress || 5, '任务取消中...', '⏹️');
      showToast('取消请求已发送', 'info');
    } catch (_) {
      showToast('取消失败，请稍后重试', 'error');
    }
  });

  // Clear log
  elements.clearLogBtn.addEventListener('click', () => {
    cleanupEventSource();
    resetProgress();
    clearPreview();
    setRunningState(false);
    state.activeJobId = null;
    showToast('已清空', 'info');
  });

  // Paste buttons
  document.querySelector('#paste-url')?.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      elements.singleUrlInput.value = text;
      showToast('已粘贴链接', 'success');
    } catch (_) {
      showToast('无法访问剪贴板，请手动粘贴', 'error');
    }
  });

  document.querySelector('#paste-batch')?.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      elements.batchUrlsTextarea.value = text;
      showToast('已粘贴链接', 'success');
    } catch (_) {
      showToast('无法访问剪贴板，请手动粘贴', 'error');
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl+Enter to submit
    if (e.ctrlKey && e.key === 'Enter') {
      const activeTab = document.querySelector('.tab.active');
      if (activeTab?.dataset.tab === 'single') {
        submitSingle();
      } else {
        submitBatch();
      }
      e.preventDefault();
    }
  });

  // Input focus effects
  [elements.singleUrlInput, elements.batchUrlsTextarea].forEach((input) => {
    input?.addEventListener('focus', () => {
      input.parentElement.style.boxShadow = '0 0 0 3px rgba(79, 140, 255, 0.2)';
    });
    input?.addEventListener('blur', () => {
      input.parentElement.style.boxShadow = '';
    });
  });

  // Cleanup handlers
  window.addEventListener('beforeunload', cleanupEventSource);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cleanupEventSource();
    }
  });
}

// Initialize
function init() {
  initElements();
  setupEventListeners();
  checkHealth();
  resetProgress();
  setRunningState(false);

  // Periodic health check
  setInterval(checkHealth, 30000);

  // Periodic cache stats update
  setInterval(fetchCacheStats, 60000);
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
