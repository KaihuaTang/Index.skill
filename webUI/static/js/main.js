/* ── Obsidian Markdown Renderer ─────────────────────────────────────── */

function renderObsidianMarkdown(text) {
    if (!text) return '';

    // 1. Extract math blocks to placeholders
    const mathBlocks = [];
    // Block math first ($$...$$)
    text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, formula) => {
        mathBlocks.push({ type: 'block', formula: formula.trim() });
        return `%%MATHBLOCK${mathBlocks.length - 1}%%`;
    });
    // Inline math ($...$) - avoid matching $$
    text = text.replace(/(?<!\$)\$([^\$\n]+?)\$(?!\$)/g, (_, formula) => {
        mathBlocks.push({ type: 'inline', formula: formula.trim() });
        return `%%MATHINLINE${mathBlocks.length - 1}%%`;
    });

    // 2. Convert callouts before marked (process raw text)
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
        marked.setOptions({
            gfm: true,
            breaks: false,
            headerIds: false,
            mangle: false,
        });
        text = marked.parse(text);
    }

    // 6. Restore math blocks and render with KaTeX
    text = text.replace(/%%MATHBLOCK(\d+)%%/g, (_, idx) => {
        const m = mathBlocks[parseInt(idx)];
        if (!m) return '';
        try {
            return katex.renderToString(m.formula, { displayMode: true, throwOnError: false });
        } catch (e) {
            return `<div class="math-error">$$${m.formula}$$</div>`;
        }
    });
    text = text.replace(/%%MATHINLINE(\d+)%%/g, (_, idx) => {
        const m = mathBlocks[parseInt(idx)];
        if (!m) return '';
        try {
            return katex.renderToString(m.formula, { displayMode: false, throwOnError: false });
        } catch (e) {
            return `<code>$${m.formula}$</code>`;
        }
    });

    return text;
}

function convertCallouts(text) {
    // Match callout blocks: > [!type] Title\n> content...
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

/* ── Type Labels ───────────────────────────────────────────────────── */
const TYPE_LABELS = {
    idea: '想法', project: '项目', book: '书籍',
    paper: '论文', webinfo: '网页', webnews: '新闻',
};

function getTypeBadgeClass(type) {
    return `badge badge-${type}`;
}

/* ── Vault: Load Notes ─────────────────────────────────────────────── */

let allNotes = [];

async function loadNotes() {
    try {
        const resp = await fetch('/api/notes');
        allNotes = await resp.json();
        renderNotes(allNotes);
    } catch (e) {
        document.getElementById('notes-loading').innerHTML =
            '<p class="text-danger">加载笔记失败</p>';
    }
}

function renderNotes(notes) {
    const container = document.getElementById('notes-list');
    const loading = document.getElementById('notes-loading');
    const empty = document.getElementById('notes-empty');

    if (loading) loading.classList.add('d-none');

    if (notes.length === 0) {
        container.innerHTML = '';
        if (empty) empty.classList.remove('d-none');
        return;
    }

    if (empty) empty.classList.add('d-none');

    container.innerHTML = notes.map(note => `
        <div class="col-md-6 col-lg-4 note-item" data-type="${note.type}">
            <div class="card note-card type-${note.type}" onclick="window.location='/note/${note.filename}'">
                <div class="card-body">
                    <div class="d-flex align-items-center mb-2">
                        <span class="badge ${getTypeBadgeClass(note.type)} me-2">${TYPE_LABELS[note.type] || note.type}</span>
                        <small class="note-meta">${note.date}</small>
                    </div>
                    <h6 class="note-title">${escapeHtml(note.title)}</h6>
                    ${note.tldr ? `<p class="note-tldr">${escapeHtml(note.tldr)}</p>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function filterNotes(type) {
    // Update active button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === type);
    });

    if (type === 'all') {
        renderNotes(allNotes);
    } else {
        renderNotes(allNotes.filter(n => n.type === type));
    }
}

/* ── Note Detail ───────────────────────────────────────────────────── */

async function loadNoteDetail(filename) {
    try {
        const resp = await fetch(`/api/note/${filename}`);
        if (!resp.ok) throw new Error('Not found');
        const data = await resp.json();

        document.getElementById('note-loading').classList.add('d-none');
        document.getElementById('note-content').classList.remove('d-none');

        // Type badge
        const type = data.metadata.type || 'idea';
        const badge = document.getElementById('note-type-badge');
        badge.textContent = TYPE_LABELS[type] || type;
        badge.className = `badge note-type-badge ${getTypeBadgeClass(type)}`;

        // Date
        document.getElementById('note-date').textContent = data.metadata.date || '';

        // Tags
        let tags = data.metadata.tags || [];
        if (typeof tags === 'string') tags = tags.split(',').map(t => t.trim());
        document.getElementById('note-tags').innerHTML =
            tags.map(t => `<span class="badge bg-secondary me-1">${escapeHtml(t)}</span>`).join('');

        // Title
        const title = data.metadata.title || filename.replace('.md', '');
        document.getElementById('note-title').textContent = title;

        // Body (render Obsidian markdown)
        document.getElementById('note-body').innerHTML = renderObsidianMarkdown(data.content);

    } catch (e) {
        document.getElementById('note-loading').classList.add('d-none');
        document.getElementById('note-error').classList.remove('d-none');
    }
}

/* ── Panel Switching (Vault <-> Input) ─────────────────────────────── */

function switchPanel(panel) {
    const vaultPanel = document.getElementById('panel-vault');
    const inputPanel = document.getElementById('panel-input');
    const btnVault = document.getElementById('btn-vault-tab');
    const btnInput = document.getElementById('btn-input-tab');

    if (!vaultPanel || !inputPanel) return;

    if (panel === 'vault') {
        vaultPanel.classList.remove('d-none');
        inputPanel.classList.add('d-none');
        btnVault.classList.add('active');
        btnInput.classList.remove('active');
    } else {
        vaultPanel.classList.add('d-none');
        inputPanel.classList.remove('d-none');
        btnVault.classList.remove('active');
        btnInput.classList.add('active');
    }
}

/* ── Input Form ────────────────────────────────────────────────────── */

let currentInputType = 'text';

function setInputType(type) {
    currentInputType = type;
    // Clear other inputs
    if (type !== 'text') {
        const ta = document.getElementById('input-text');
        if (ta) ta.value = '';
    }
    if (type !== 'file') {
        clearFile();
    }
    if (type !== 'url') {
        const urlInput = document.getElementById('input-url');
        if (urlInput) urlInput.value = '';
    }
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

/* ── Processing ────────────────────────────────────────────────────── */

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
            iconHtml = '<i class="bi bi-check-circle-fill text-success"></i>';
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
            } else if (data.status === 'error') {
                clearInterval(interval);
                showProcessingError(data.error || '处理过程中出现错误');
            }
        } catch (e) {
            // Continue polling on network error
        }
    }, 1500);
}

function showProcessingComplete(result) {
    const resultBox = document.getElementById('processing-result');
    const link = document.getElementById('processing-link');
    const btn = document.getElementById('btn-process');
    btn.disabled = false;

    if (result && result.note_path) {
        link.href = `/note/${result.note_path}`;
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

/* ── Init Wizard ───────────────────────────────────────────────────── */

const initWizard = {
    currentStep: 1,
    totalSteps: 6,

    show(step) {
        // Hide all steps
        document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('d-none'));
        // Show target step
        const target = document.getElementById(`step-${step}`);
        if (target) target.classList.remove('d-none');
        // Update dots
        document.querySelectorAll('.step-dot').forEach(dot => {
            const s = parseInt(dot.dataset.step);
            dot.classList.remove('active', 'completed');
            if (s < step) dot.classList.add('completed');
            if (s === step) dot.classList.add('active');
        });
        this.currentStep = step;
    },

    next() {
        if (!this.validate()) return;
        if (this.currentStep === 5) {
            this.populateConfirm();
        }
        if (this.currentStep < this.totalSteps) {
            this.show(this.currentStep + 1);
        }
    },

    prev() {
        if (this.currentStep > 1) {
            this.show(this.currentStep - 1);
        }
    },

    validate() {
        if (this.currentStep === 1) {
            const prof = document.getElementById('profession')?.value?.trim();
            if (!prof) { alert('请输入您的职业'); return false; }
        }
        if (this.currentStep >= 2 && this.currentStep <= 5) {
            const dims = ['E_I', 'S_N', 'T_F', 'J_P'];
            const dim = dims[this.currentStep - 2];
            const selected = document.querySelector(`input[name="${dim}"]:checked`);
            if (!selected) { alert('请选择一个选项'); return false; }
        }
        return true;
    },

    populateConfirm() {
        const profession = document.getElementById('profession')?.value?.trim();
        const ei = document.querySelector('input[name="E_I"]:checked')?.value || '?';
        const sn = document.querySelector('input[name="S_N"]:checked')?.value || '?';
        const tf = document.querySelector('input[name="T_F"]:checked')?.value || '?';
        const jp = document.querySelector('input[name="J_P"]:checked')?.value || '?';
        const mbti = ei + sn + tf + jp;

        document.getElementById('confirm-profession').textContent = profession;
        document.getElementById('confirm-mbti').textContent = mbti;
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
                btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>开始初始化';
            }
        } catch (e) {
            alert('初始化失败: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>开始初始化';
        }
    },
};

/* ── Utility ───────────────────────────────────────────────────────── */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ── Page Init ─────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    // Auto-load notes if on vault page
    if (document.getElementById('notes-list')) {
        loadNotes();
    }
    // Setup file upload if on input page
    if (document.getElementById('upload-zone')) {
        setupFileUpload();
    }
});
