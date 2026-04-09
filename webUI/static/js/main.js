/* ══════════════════════════════════════════════════════════════════════
   茵蒂克丝.skill WebUI — Main JavaScript
   ══════════════════════════════════════════════════════════════════════ */

/* ── Constants ───────────────────────────────────────────────────────── */

const TYPE_LABELS = {
    idea: '想法', project: '项目', book: '书籍',
    paper: '论文', webinfo: '网页', webnews: '新闻',
};

const TYPE_COLORS = {
    idea: '#7c3aed', project: '#2563eb', book: '#059669',
    paper: '#d97706', webinfo: '#0891b2', webnews: '#dc2626',
};

/* ── Obsidian Markdown Renderer ──────────────────────────────────────── */

function renderObsidianMarkdown(text) {
    if (!text) return '';

    // 1. Extract math blocks to placeholders
    const mathBlocks = [];
    text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, formula) => {
        mathBlocks.push({ type: 'block', formula: formula.trim() });
        return `%%MATHBLOCK${mathBlocks.length - 1}%%`;
    });
    text = text.replace(/(?<!\$)\$([^\$\n]+?)\$(?!\$)/g, (_, formula) => {
        mathBlocks.push({ type: 'inline', formula: formula.trim() });
        return `%%MATHINLINE${mathBlocks.length - 1}%%`;
    });

    // 2. Convert callouts before marked
    text = convertCallouts(text);

    // 3. Convert image embeds: ![[filename|width]] -> HTML
    text = text.replace(/!\[\[([^\]|]+?)(?:\|(\d+))?\]\]/g, (_, filename, width) => {
        const w = width ? ` width="${width}"` : '';
        return `<img src="/vault/images/${filename}"${w} class="obsidian-image" alt="${filename}">`;
    });

    // 4. Convert wikilinks: [[Target|Display]] -> styled span
    text = text.replace(/\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]/g, (_, target, display) => {
        return `<span class="wikilink" title="${target}">${display || target}</span>`;
    });

    // 5. Run marked.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({ gfm: true, breaks: false, headerIds: false, mangle: false });
        text = marked.parse(text);
    }

    // 6. Restore math blocks with KaTeX
    text = text.replace(/%%MATHBLOCK(\d+)%%/g, (_, idx) => {
        const m = mathBlocks[parseInt(idx)];
        if (!m) return '';
        try { return katex.renderToString(m.formula, { displayMode: true, throwOnError: false }); }
        catch (e) { return `<div class="math-error">$$${m.formula}$$</div>`; }
    });
    text = text.replace(/%%MATHINLINE(\d+)%%/g, (_, idx) => {
        const m = mathBlocks[parseInt(idx)];
        if (!m) return '';
        try { return katex.renderToString(m.formula, { displayMode: false, throwOnError: false }); }
        catch (e) { return `<code>$${m.formula}$</code>`; }
    });

    return text;
}

function convertCallouts(text) {
    const lines = text.split('\n');
    const result = [];
    let i = 0;

    while (i < lines.length) {
        const calloutMatch = lines[i].match(/^>\s*\[!(\w+)\]\s*(.*)/);
        if (calloutMatch) {
            const type = calloutMatch[1].toLowerCase();
            const title = calloutMatch[2] || type.charAt(0).toUpperCase() + type.slice(1);
            const contentLines = [];
            i++;

            while (i < lines.length) {
                if (lines[i].startsWith('> ')) {
                    contentLines.push(lines[i].substring(2));
                    i++;
                } else if (lines[i].trim() === '>') {
                    contentLines.push('');
                    i++;
                } else {
                    break;
                }
            }

            const content = contentLines.join('\n');
            result.push(`<div class="callout callout-${type}">`);
            result.push(`<div class="callout-title">${title}</div>`);
            result.push(`<div class="callout-content">${content}</div>`);
            result.push(`</div>`);
        } else {
            result.push(lines[i]);
            i++;
        }
    }

    return result.join('\n');
}

/* ── Utility ─────────────────────────────────────────────────────────── */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ── App Initialization ──────────────────────────────────────────────── */

let currentView = 'new';
let notesCache = { new: null, read: null, archived: null };
let activeFilters = { new: 'all', read: 'all', archived: 'all' };

function initApp() {
    loadStats();
    loadNotes('new');
    setupFileUpload();
    setupChatInput();
}

/* ── Sidebar Navigation ──────────────────────────────────────────────── */

function switchView(view) {
    currentView = view;

    // Update nav active state
    document.querySelectorAll('.nav-item[data-view]').forEach(el => {
        el.classList.toggle('active', el.dataset.view === view);
    });

    // Show/hide views
    document.querySelectorAll('.view').forEach(el => {
        el.classList.toggle('active', el.id === `view-${view}`);
    });

    // Load data for the view
    if (view === 'new' || view === 'read' || view === 'archived') {
        loadNotes(view);
    }
    if (view === 'update') {
        loadUpdateStats();
    }
    if (view === 'persona') {
        loadPersona();
    }

    // Close mobile sidebar
    closeSidebar();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
}

/* ── Stats / Badges ──────────────────────────────────────────────────── */

async function loadStats() {
    try {
        const resp = await fetch('/api/stats');
        const data = await resp.json();
        const badgeNew = document.getElementById('badge-new');
        const badgeRead = document.getElementById('badge-read');
        const badgeArchived = document.getElementById('badge-archived');
        if (badgeNew) badgeNew.textContent = data.new || '';
        if (badgeRead) badgeRead.textContent = data.read || '';
        if (badgeArchived) badgeArchived.textContent = data.archived || '';
    } catch (e) { /* ignore */ }
}

/* ── Notes Loading ───────────────────────────────────────────────────── */

async function loadNotes(status) {
    const grid = document.getElementById(`notes-${status}`);
    const empty = document.getElementById(`empty-${status}`);
    if (!grid) return;

    // Show loading
    grid.innerHTML = '<div class="loading-state"><div class="spinner-border spinner-border-sm"></div> 加载中...</div>';
    if (empty) empty.classList.add('d-none');

    try {
        const resp = await fetch(`/api/notes?status=${status}`);
        const notes = await resp.json();
        notesCache[status] = notes;

        // Build filter bar
        buildFilterBar(status, notes);

        // Render
        renderNoteGrid(status, notes);
    } catch (e) {
        grid.innerHTML = '<div class="loading-state" style="color:#dc2626">加载失败</div>';
    }
}

function buildFilterBar(status, notes) {
    const bar = document.getElementById(`filter-bar-${status}`);
    if (!bar) return;

    // Count types
    const typeCounts = {};
    notes.forEach(n => {
        typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
    });

    const types = Object.keys(typeCounts).sort();
    if (types.length <= 1) {
        bar.innerHTML = '';
        return;
    }

    let html = `<button class="filter-btn active" data-filter="all" onclick="filterNotes('${status}','all')">全部 (${notes.length})</button>`;
    types.forEach(t => {
        const color = TYPE_COLORS[t] || '#6b7280';
        html += `<button class="filter-btn" data-filter="${t}" onclick="filterNotes('${status}','${t}')">
            <span class="filter-dot" style="background:${color}"></span>${TYPE_LABELS[t] || t} (${typeCounts[t]})
        </button>`;
    });
    bar.innerHTML = html;
}

function filterNotes(status, type) {
    activeFilters[status] = type;

    // Update buttons
    const bar = document.getElementById(`filter-bar-${status}`);
    if (bar) {
        bar.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === type);
        });
    }

    const notes = notesCache[status] || [];
    const filtered = type === 'all' ? notes : notes.filter(n => n.type === type);
    renderNoteGrid(status, filtered);
}

function renderNoteGrid(status, notes) {
    const grid = document.getElementById(`notes-${status}`);
    const empty = document.getElementById(`empty-${status}`);

    if (notes.length === 0) {
        grid.innerHTML = '';
        if (empty) empty.classList.remove('d-none');
        return;
    }

    if (empty) empty.classList.add('d-none');

    const source = status === 'archived' ? 'archived' : 'new';
    grid.innerHTML = notes.map(note => `
        <div class="note-card type-${note.type}" onclick="window.location='/note/${source}/${note.filename}'">
            <div class="note-card-body">
                <div class="note-card-header">
                    <span class="type-badge type-badge-${note.type}">${TYPE_LABELS[note.type] || note.type}</span>
                    <span class="note-card-date">${escapeHtml(note.date)}</span>
                </div>
                <div class="note-card-title">${escapeHtml(note.title)}</div>
                ${note.tldr ? `<div class="note-card-tldr">${escapeHtml(note.tldr)}</div>` : ''}
            </div>
        </div>
    `).join('');
}

/* ── Note Detail ─────────────────────────────────────────────────────── */

async function loadNoteDetail(source, filename) {
    try {
        const resp = await fetch(`/api/note/${source}/${filename}`);
        if (!resp.ok) throw new Error('Not found');
        const data = await resp.json();

        document.getElementById('note-loading').classList.add('d-none');
        document.getElementById('note-content').classList.remove('d-none');

        // Type badge
        const type = data.metadata.type || 'idea';
        const badge = document.getElementById('note-type-badge');
        badge.textContent = TYPE_LABELS[type] || type;
        badge.className = `note-type-badge type-badge type-badge-${type}`;

        // Date
        document.getElementById('note-date').textContent = data.metadata.date || '';

        // Tags
        let tags = data.metadata.tags || [];
        if (typeof tags === 'string') tags = tags.split(',').map(t => t.trim());
        document.getElementById('note-tags').innerHTML =
            tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');

        // Source badge
        const sourceBadge = document.getElementById('note-source-badge');
        if (source === 'archived') {
            sourceBadge.textContent = '已归档';
            sourceBadge.className = 'note-source-badge source-archived';
        } else {
            sourceBadge.textContent = data.is_read ? '已读' : '新加入';
            sourceBadge.className = `note-source-badge ${data.is_read ? 'source-archived' : 'source-new'}`;
        }

        // Title
        const title = data.metadata.title || filename.replace('.md', '');
        document.getElementById('note-title').textContent = title;

        // Body
        document.getElementById('note-body').innerHTML = renderObsidianMarkdown(data.content);

        // Actions (mark as read button, only for notes in _new/)
        const actionsDiv = document.getElementById('detail-actions');
        if (source === 'new') {
            const readLabel = data.is_read ? '已读' : '标记为已读';
            const readClass = data.is_read ? 'btn-mark-read is-read' : 'btn-mark-read';
            const readIcon = data.is_read ? 'bi-check-circle-fill' : 'bi-circle';
            actionsDiv.innerHTML = `
                <button class="${readClass}" id="btn-toggle-read" onclick="toggleRead('${filename}')">
                    <i class="bi ${readIcon} me-1"></i>${readLabel}
                </button>`;
        } else {
            actionsDiv.innerHTML = '';
        }

    } catch (e) {
        document.getElementById('note-loading').classList.add('d-none');
        document.getElementById('note-error').classList.remove('d-none');
    }
}

async function toggleRead(filename) {
    const btn = document.getElementById('btn-toggle-read');
    if (!btn) return;
    btn.disabled = true;

    try {
        const resp = await fetch('/api/note/toggle-read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename }),
        });
        const data = await resp.json();
        if (data.success) {
            const isRead = data.is_read;
            btn.className = isRead ? 'btn-mark-read is-read' : 'btn-mark-read';
            btn.innerHTML = `<i class="bi ${isRead ? 'bi-check-circle-fill' : 'bi-circle'} me-1"></i>${isRead ? '已读' : '标记为已读'}`;

            // Update source badge
            const sourceBadge = document.getElementById('note-source-badge');
            sourceBadge.textContent = isRead ? '已读' : '新加入';
            sourceBadge.className = `note-source-badge ${isRead ? 'source-archived' : 'source-new'}`;
        }
    } catch (e) { /* ignore */ }

    btn.disabled = false;
}

/* ── Input Panel ─────────────────────────────────────────────────────── */

let currentInputType = 'text';

function setInputType(type) {
    currentInputType = type;

    document.querySelectorAll('.input-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.type === type);
    });

    document.querySelectorAll('.input-area').forEach(area => {
        area.classList.add('d-none');
    });
    document.getElementById(`input-area-${type}`).classList.remove('d-none');
}

function clearFile() {
    const fileInput = document.getElementById('input-file');
    const fileInfo = document.getElementById('file-info');
    if (fileInput) fileInput.value = '';
    if (fileInfo) fileInfo.classList.add('d-none');
}

function setupFileUpload() {
    const zone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('input-file');
    if (!zone || !fileInput) return;

    zone.addEventListener('click', () => fileInput.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            showFileInfo(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            showFileInfo(fileInput.files[0]);
        }
    });
}

function showFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    if (fileInfo && fileName) {
        fileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        fileInfo.classList.remove('d-none');
    }
}

/* ── Processing (New Note) ───────────────────────────────────────────── */

async function startProcessing() {
    const formData = new FormData();
    formData.append('input_type', currentInputType);

    if (currentInputType === 'text') {
        const text = document.getElementById('input-text')?.value?.trim();
        if (!text) { alert('请输入文本内容'); return; }
        formData.append('input_text', text);
    } else if (currentInputType === 'url') {
        const url = document.getElementById('input-url')?.value?.trim();
        if (!url) { alert('请输入 URL'); return; }
        formData.append('input_text', url);
    } else if (currentInputType === 'file') {
        const fileInput = document.getElementById('input-file');
        if (!fileInput?.files?.length) { alert('请选择文件'); return; }
        formData.append('file', fileInput.files[0]);
    }

    const statusDiv = document.getElementById('processing-status');
    const stepsEl = document.getElementById('processing-steps');
    const resultBox = document.getElementById('processing-result');
    const errorBox = document.getElementById('processing-error-box');
    const btn = document.getElementById('btn-process');

    statusDiv.classList.remove('d-none');
    resultBox.classList.add('d-none');
    errorBox.classList.add('d-none');
    stepsEl.innerHTML = '<li class="step-item step-running"><span class="step-icon"><span class="spinner-border spinner-border-sm"></span></span> 正在提交任务...</li>';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/process', { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.error) {
            showProcessingError(data.error);
            btn.disabled = false;
            return;
        }

        pollTask(data.task_id);
    } catch (e) {
        showProcessingError('提交任务失败: ' + e.message);
        btn.disabled = false;
    }
}

function renderSteps(steps) {
    const stepsEl = document.getElementById('processing-steps');
    if (!stepsEl || !steps || !steps.length) return;

    stepsEl.innerHTML = steps.map(s => {
        let iconHtml = '';
        let cls = '';
        if (s.status === 'done') {
            iconHtml = '<i class="bi bi-check-circle-fill"></i>';
            cls = 'step-done';
        } else if (s.status === 'running') {
            iconHtml = '<span class="spinner-border spinner-border-sm text-primary"></span>';
            cls = 'step-running';
        } else {
            iconHtml = '<i class="bi bi-circle text-muted"></i>';
            cls = 'step-pending';
        }
        const detail = s.detail ? `<span class="step-detail">${escapeHtml(s.detail)}</span>` : '';
        return `<li class="step-item ${cls}"><span class="step-icon">${iconHtml}</span> ${escapeHtml(s.label)}${detail}</li>`;
    }).join('');
}

function pollTask(taskId) {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`/api/task/${taskId}`);
            const data = await resp.json();

            if (data.steps && data.steps.length) {
                renderSteps(data.steps);
            }

            if (data.status === 'completed') {
                clearInterval(interval);
                renderSteps(data.steps);
                showProcessingComplete(data.result);
                loadStats(); // Refresh badges
            } else if (data.status === 'error') {
                clearInterval(interval);
                showProcessingError(data.error || '处理过程中出现错误');
            }
        } catch (e) { /* continue polling */ }
    }, 1500);
}

function showProcessingComplete(result) {
    const resultBox = document.getElementById('processing-result');
    const link = document.getElementById('processing-link');
    const btn = document.getElementById('btn-process');
    btn.disabled = false;

    if (result && result.note_path) {
        link.href = `/note/new/${result.note_path}`;
        resultBox.classList.remove('d-none');
    }
}

function showProcessingError(errorMsg) {
    const errorBox = document.getElementById('processing-error-box');
    const errorP = document.getElementById('processing-error');
    const btn = document.getElementById('btn-process');
    errorBox.classList.remove('d-none');
    errorP.textContent = errorMsg;
    if (btn) btn.disabled = false;
}

/* ── Chat ────────────────────────────────────────────────────────────── */

function setupChatInput() {
    const input = document.getElementById('chat-input');
    if (!input) return;

    // Auto-resize
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Enter to send (Shift+Enter for newline)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChat();
        }
    });
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const message = input.value.trim();
    if (!message) return;

    // Add user bubble
    const messages = document.getElementById('chat-messages');
    // Remove welcome if present
    const welcome = messages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    messages.innerHTML += `
        <div class="chat-bubble user">
            <div class="chat-bubble-label">你</div>
            <div class="chat-bubble-content">${escapeHtml(message)}</div>
        </div>
    `;

    // Add typing indicator
    messages.innerHTML += `
        <div class="chat-bubble assistant" id="chat-typing">
            <div class="chat-bubble-label">茵蒂克丝</div>
            <div class="chat-typing">
                <div class="spinner-border spinner-border-sm"></div> 正在思考...
            </div>
        </div>
    `;

    messages.scrollTop = messages.scrollHeight;

    // Clear input
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        const data = await resp.json();

        if (data.error) {
            removeChatTyping();
            addAssistantBubble('出错了: ' + data.error);
            sendBtn.disabled = false;
            return;
        }

        // Poll for result
        pollChatTask(data.task_id);
    } catch (e) {
        removeChatTyping();
        addAssistantBubble('发送失败: ' + e.message);
        sendBtn.disabled = false;
    }
}

function pollChatTask(taskId) {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`/api/task/${taskId}`);
            const data = await resp.json();

            if (data.status === 'completed') {
                clearInterval(interval);
                removeChatTyping();
                const response = data.result?.response || '(无回复)';
                addAssistantBubble(response);
                document.getElementById('chat-send-btn').disabled = false;
            } else if (data.status === 'error') {
                clearInterval(interval);
                removeChatTyping();
                addAssistantBubble('出错了: ' + (data.error || '未知错误'));
                document.getElementById('chat-send-btn').disabled = false;
            }
        } catch (e) { /* continue polling */ }
    }, 2000);
}

function removeChatTyping() {
    const typing = document.getElementById('chat-typing');
    if (typing) typing.remove();
}

function addAssistantBubble(text) {
    const messages = document.getElementById('chat-messages');
    const rendered = renderObsidianMarkdown(text);
    messages.innerHTML += `
        <div class="chat-bubble assistant">
            <div class="chat-bubble-label">茵蒂克丝</div>
            <div class="chat-bubble-content">${rendered}</div>
        </div>
    `;
    messages.scrollTop = messages.scrollHeight;
}

/* ── Update / Archive ────────────────────────────────────────────────── */

async function loadUpdateStats() {
    try {
        const resp = await fetch('/api/stats');
        const data = await resp.json();
        document.getElementById('update-read-count').textContent = data.read || 0;
    } catch (e) { /* ignore */ }
}

async function startUpdate() {
    const btn = document.getElementById('btn-update');
    const statusDiv = document.getElementById('update-status');
    const resultDiv = document.getElementById('update-result');
    const errorDiv = document.getElementById('update-error');

    btn.disabled = true;
    statusDiv.classList.remove('d-none');
    resultDiv.classList.add('d-none');
    errorDiv.classList.add('d-none');

    try {
        const resp = await fetch('/api/update', { method: 'POST' });
        const data = await resp.json();

        if (data.error) {
            statusDiv.classList.add('d-none');
            errorDiv.classList.remove('d-none');
            document.getElementById('update-error-text').textContent = data.error;
            btn.disabled = false;
            return;
        }

        pollUpdateTask(data.task_id);
    } catch (e) {
        statusDiv.classList.add('d-none');
        errorDiv.classList.remove('d-none');
        document.getElementById('update-error-text').textContent = '启动失败: ' + e.message;
        btn.disabled = false;
    }
}

function pollUpdateTask(taskId) {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`/api/task/${taskId}`);
            const data = await resp.json();

            if (data.status === 'completed') {
                clearInterval(interval);
                document.getElementById('update-status').classList.add('d-none');
                document.getElementById('update-result').classList.remove('d-none');
                document.getElementById('update-result-text').textContent = '归档整理完成';
                document.getElementById('btn-update').disabled = false;
                loadStats();
                loadUpdateStats();
            } else if (data.status === 'error') {
                clearInterval(interval);
                document.getElementById('update-status').classList.add('d-none');
                document.getElementById('update-error').classList.remove('d-none');
                document.getElementById('update-error-text').textContent = data.error || '处理出错';
                document.getElementById('btn-update').disabled = false;
            } else if (data.progress) {
                document.getElementById('update-progress-text').textContent = data.progress;
            }
        } catch (e) { /* continue polling */ }
    }, 3000);
}

/* ── Persona View ────────────────────────────────────────────────────── */

let personaRaw = '';
let personaLoaded = false;

async function loadPersona() {
    if (personaLoaded) return;
    const loading = document.getElementById('persona-loading');
    const content = document.getElementById('persona-content');

    try {
        const resp = await fetch('/api/persona');
        const data = await resp.json();

        if (!data.exists) {
            loading.innerHTML = '<p>尚未初始化 persona.md</p>';
            return;
        }

        personaRaw = data.raw || '';
        content.innerHTML = renderObsidianMarkdown(data.content);
        loading.classList.add('d-none');
        content.classList.remove('d-none');
        personaLoaded = true;
    } catch (e) {
        loading.innerHTML = '<p style="color:#dc2626">加载失败</p>';
    }
}

function togglePersonaEdit() {
    const readDiv = document.getElementById('persona-read');
    const editDiv = document.getElementById('persona-edit');
    const btn = document.getElementById('btn-persona-edit');

    if (editDiv.classList.contains('d-none')) {
        // Switch to edit mode
        document.getElementById('persona-editor').value = personaRaw;
        readDiv.classList.add('d-none');
        editDiv.classList.remove('d-none');
        btn.innerHTML = '<i class="bi bi-eye me-1"></i>预览';
    } else {
        // Switch back to read mode
        readDiv.classList.remove('d-none');
        editDiv.classList.add('d-none');
        btn.innerHTML = '<i class="bi bi-pencil me-1"></i>编辑';
    }
}

function cancelPersonaEdit() {
    document.getElementById('persona-read').classList.remove('d-none');
    document.getElementById('persona-edit').classList.add('d-none');
    document.getElementById('btn-persona-edit').innerHTML = '<i class="bi bi-pencil me-1"></i>编辑';
}

async function savePersona() {
    const editor = document.getElementById('persona-editor');
    const raw = editor.value;
    const btn = document.getElementById('btn-persona-save');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>保存中...';

    try {
        const resp = await fetch('/api/persona', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw }),
        });
        const data = await resp.json();

        if (data.success) {
            personaRaw = raw;
            // Re-render read view
            const metadata_body = raw.split('---');
            const body = metadata_body.length >= 3 ? metadata_body.slice(2).join('---').trim() : raw;
            document.getElementById('persona-content').innerHTML = renderObsidianMarkdown(body);

            // Switch back to read mode
            cancelPersonaEdit();
        } else {
            alert('保存失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('保存失败: ' + e.message);
    }

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>保存';
}

/* ── Init Wizard ─────────────────────────────────────────────────────── */

const initWizard = {
    currentStep: 1,
    totalSteps: 6,

    show(step) {
        document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('d-none'));
        const target = document.getElementById(`step-${step}`);
        if (target) target.classList.remove('d-none');

        // Update progress
        document.querySelectorAll('.progress-step').forEach(s => {
            const n = parseInt(s.dataset.step);
            s.classList.remove('active', 'completed');
            if (n < step) s.classList.add('completed');
            if (n === step) s.classList.add('active');
        });

        const fill = document.getElementById('progress-fill');
        if (fill && typeof step === 'number') {
            fill.style.width = `${(step / this.totalSteps) * 100}%`;
        }

        this.currentStep = step;
    },

    next() {
        if (!this.validate()) return;
        if (this.currentStep === 5) this.populateConfirm();
        if (this.currentStep < this.totalSteps) this.show(this.currentStep + 1);
    },

    prev() {
        if (this.currentStep > 1) this.show(this.currentStep - 1);
    },

    validate() {
        if (this.currentStep === 1) {
            if (!document.getElementById('profession')?.value?.trim()) {
                alert('请输入您的职业');
                return false;
            }
        }
        if (this.currentStep >= 2 && this.currentStep <= 5) {
            const dims = ['E_I', 'S_N', 'T_F', 'J_P'];
            const dim = dims[this.currentStep - 2];
            if (!document.querySelector(`input[name="${dim}"]:checked`)) {
                alert('请选择一个选项');
                return false;
            }
        }
        return true;
    },

    populateConfirm() {
        const profession = document.getElementById('profession')?.value?.trim();
        const ei = document.querySelector('input[name="E_I"]:checked')?.value || '?';
        const sn = document.querySelector('input[name="S_N"]:checked')?.value || '?';
        const tf = document.querySelector('input[name="T_F"]:checked')?.value || '?';
        const jp = document.querySelector('input[name="J_P"]:checked')?.value || '?';
        document.getElementById('confirm-profession').textContent = profession;
        document.getElementById('confirm-mbti').textContent = ei + sn + tf + jp;
    },

    async submit() {
        const btn = document.getElementById('btn-init');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>初始化中...';

        const profession = document.getElementById('profession')?.value?.trim();
        const mbti = {
            E_I: document.querySelector('input[name="E_I"]:checked')?.value,
            S_N: document.querySelector('input[name="S_N"]:checked')?.value,
            T_F: document.querySelector('input[name="T_F"]:checked')?.value,
            J_P: document.querySelector('input[name="J_P"]:checked')?.value,
        };

        try {
            const resp = await fetch('/api/init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profession, mbti }),
            });
            const data = await resp.json();

            if (data.success) {
                document.getElementById('result-info').textContent =
                    `MBTI 类型: ${data.mbti_type} (${data.nickname})`;
                this.show('result');
            } else {
                alert('初始化失败: ' + (data.error || '未知错误'));
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-rocket-takeoff me-2"></i>开始初始化';
            }
        } catch (e) {
            alert('初始化失败: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-rocket-takeoff me-2"></i>开始初始化';
        }
    },
};

/* ── Page Init ───────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    // Auto-init if on app page
    if (document.getElementById('main-content')) {
        initApp();
    }
    // Setup file upload if present (for standalone pages)
    if (document.getElementById('upload-zone') && !document.getElementById('main-content')) {
        setupFileUpload();
    }
});
