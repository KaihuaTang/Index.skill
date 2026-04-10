#!/usr/bin/env python3
"""
茵蒂克丝.skill WebUI - Flask application for knowledge management.
Five views: Init wizard, three note categories (new/read/archived),
new note input, chat, and archive trigger.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = PROJECT_ROOT / "IndexVault"
NEW_DIR = VAULT_PATH / "_new"
DEEP_DIR = VAULT_PATH / "deep"
MEMORY_DIR = VAULT_PATH / "memory"
TEMPLATE_DIR = VAULT_PATH / "_template"
IMAGES_DIR = VAULT_PATH / "_images"
DOWNLOADS_DIR = VAULT_PATH / "_downloads"
CHAT_DIR = VAULT_PATH / "_chat"
RESOURCES_DIR = PROJECT_ROOT / "skills" / "index-init" / "resources"
SCRIPTS_DIR = PROJECT_ROOT / "skills" / "index-note" / "scripts"

# ── Flask App ────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB

# ── Background Tasks ────────────────────────────────────────────────────
tasks = {}
tasks_lock = threading.Lock()


def update_task(task_id, **kwargs):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(kwargs)


# ── MBTI Data ────────────────────────────────────────────────────────────
MBTI_TYPES = {
    "INTJ": {"nickname": "策略家/Architect", "traits": "独立、战略性思维、追求效率、重视逻辑深度"},
    "INTP": {"nickname": "逻辑学家/Logician", "traits": "好奇、分析型、追求理论完备性、重视精确"},
    "ENTJ": {"nickname": "指挥官/Commander", "traits": "果断、目标导向、善于组织、追求效率"},
    "ENTP": {"nickname": "辩论家/Debater", "traits": "创新、善于发散、喜欢挑战假设、思维敏捷"},
    "INFJ": {"nickname": "提倡者/Advocate", "traits": "洞察力强、关注意义、善于共情、追求深度"},
    "INFP": {"nickname": "调停者/Mediator", "traits": "理想主义、重视价值、富有创意、善于倾听"},
    "ENFJ": {"nickname": "主人公/Protagonist", "traits": "热情、善于激励、关注他人成长、善于沟通"},
    "ENFP": {"nickname": "竞选者/Campaigner", "traits": "热情洋溢、创意丰富、善于联想、重视可能性"},
    "ISTJ": {"nickname": "物流师/Logistician", "traits": "严谨、可靠、注重细节、系统化思维"},
    "ISFJ": {"nickname": "守卫者/Defender", "traits": "细心、负责、重视实践经验、善于支持"},
    "ESTJ": {"nickname": "总经理/Executive", "traits": "高效、实际、善于执行、注重秩序"},
    "ESFJ": {"nickname": "执政官/Consul", "traits": "热心、合作、注重和谐、善于组织"},
    "ISTP": {"nickname": "鉴赏家/Virtuoso", "traits": "冷静分析、实践导向、善于解决具体问题"},
    "ISFP": {"nickname": "探险家/Adventurer", "traits": "温和、审美敏锐、活在当下、灵活"},
    "ESTP": {"nickname": "企业家/Entrepreneur", "traits": "行动力强、务实、善于应变、重视效率"},
    "ESFP": {"nickname": "表演者/Entertainer", "traits": "活力充沛、乐观、重视体验、善于互动"},
}

DIALOGUE_STYLES = {
    "E": "主动积极，倾向于先给出建议再深入分析，风格开放外放",
    "I": "沉稳内敛，倾向于先深度思考再给出回应，风格专注深入",
    "S": "循序渐进，关注具体事实和细节，重视实证数据支撑",
    "N": "善于跳跃联想，关注整体模式和可能性，重视灵感洞察",
    "T": "理性直接，基于逻辑和客观分析给出建议，重视一致性",
    "F": "温暖共情，基于价值观和人际影响给出建议，重视和谐",
    "J": "结构化表达，追求明确结论和行动步骤，偏好有计划的回答",
    "P": "保持开放灵活，呈现多种可能性，适应变化",
}

THINKING_APPROACHES = {
    "NT": "思维方式兼具战略性和系统性——先建立大框架再填充细节，善于快速抓住本质，在复杂信息中识别关键杠杆点",
    "NF": "思维方式富有洞察力和创造性——善于从多维度理解问题，关注深层意义和人文价值，在信息中寻找模式与联系",
    "ST": "思维方式严谨务实——注重事实和逻辑链条，善于系统化地拆解问题，追求精确可靠的结论",
    "SF": "思维方式细腻实际——注重具体经验和人际感知，善于从实践中总结规律，追求和谐可行的方案",
}


def generate_mbti_description(mbti_type):
    info = MBTI_TYPES.get(mbti_type, {})
    e_i, s_n, t_f, j_p = mbti_type[0], mbti_type[1], mbti_type[2], mbti_type[3]
    traits = info.get("traits", "")
    dial_1 = DIALOGUE_STYLES.get(e_i, "")
    dial_2 = DIALOGUE_STYLES.get(j_p, "")
    think_key = s_n + t_f
    thinking = THINKING_APPROACHES.get(think_key, "")
    return f"{traits}。对话风格{dial_1}，{dial_2}。{thinking}。"


def derive_convergent_divergent(mbti):
    s_n, j_p = mbti[1], mbti[3]
    if s_n == "N" and j_p == "P":
        return "偏向发散思维", "善于产生多种可能性和创意方案，思维开放不拘一格"
    if s_n == "S" and j_p == "J":
        return "偏向收敛思维", "善于聚焦最优解并系统推进，追求确定性和效率"
    if s_n == "N" and j_p == "J":
        return f"发散-收敛兼备({s_n}{j_p})", "先发散探索多种可能方案，再迅速收敛到最优解并推进执行"
    return f"情境驱动({s_n}{j_p})", "根据具体情境灵活切换收敛与发散模式"


def derive_system12(mbti):
    e_i, s_n, j_p = mbti[0], mbti[1], mbti[3]
    if e_i == "E" and s_n == "S" and j_p == "P":
        return "偏向System 1", "快速直觉判断，依赖经验模式匹配，行动力强"
    if e_i == "I" and s_n == "N" and j_p == "J":
        return "偏向System 2", "深度慢思考，依赖逻辑推演，追求严密论证"
    s1 = sum([e_i == "E", s_n == "S", j_p == "P"])
    s2 = sum([e_i == "I", s_n == "N", j_p == "J"])
    t_f = mbti[2]
    if s2 > s1:
        s1_note = f"，但{'外向特质(E)使其也能快速做出直觉判断' if e_i == 'E' else '感觉特质(S)提供经验直觉' if s_n == 'S' else '知觉特质(P)带来灵活应变'}"
        return "混合偏System 2", f"擅长深度逻辑推演({s_n}{t_f}){s1_note}"
    if s1 > s2:
        dims_s1 = [d for d, v in [("E", e_i == "E"), ("S", s_n == "S"), ("P", j_p == "P")] if v]
        return "混合偏System 1", f"倾向快速直觉判断({''.join(dims_s1)})，但也具备深度分析能力"
    return "混合模式", "根据任务类型灵活切换快速直觉与深度分析"


def derive_analytical_holistic(mbti):
    s_n, t_f = mbti[1], mbti[2]
    if s_n == "S" and t_f == "T":
        return "偏向分析型(ST)", "自下而上拆解问题，关注细节和因果链条"
    if s_n == "N" and t_f == "F":
        return "偏向整体型(NF)", "自上而下把握全局，关注关系和模式"
    if s_n == "N" and t_f == "T":
        return f"系统型({s_n}{t_f})", "兼具分析深度和全局视野，自上而下构建框架后再自下而上验证细节"
    return f"经验型({s_n}{t_f})", "基于具体经验和人际感知理解事物，注重实践中的人文关怀"


def derive_bas_bis(mbti):
    e_i, t_f = mbti[0], mbti[2]
    if e_i == "E" and t_f == "T":
        return "偏向趋近(BAS)", f"积极追求目标和挑战({e_i}{t_f})，风险容忍度高，面对不确定性倾向行动"
    if e_i == "I" and t_f == "F":
        return "偏向回避(BIS)", f"谨慎评估风险({e_i}{t_f})，倾向规避不确定性，决策前充分考量影响"
    if e_i == "E" and t_f == "F":
        return "平衡偏趋近", "外向特质驱动积极行动，但情感维度带来对影响的审慎考量"
    return "平衡偏回避", "内向特质带来谨慎深思，但思考维度提供理性决断力"


def derive_exploration_exploitation(mbti):
    s_n, j_p = mbti[1], mbti[3]
    if s_n == "N" and j_p == "P":
        return "偏向探索(NP)", "倾向尝试新方法、新视角，容忍不确定性，享受发现过程"
    if s_n == "S" and j_p == "J":
        return "偏向利用(SJ)", "倾向优化已有方法，追求可靠性和效率，稳步推进"
    if s_n == "N" and j_p == "J":
        return f"情境适应偏利用({s_n}{j_p})", f"虽有直觉驱动的探索能力({s_n})，但判断特质({j_p})使其更倾向优化和执行已验证的路径"
    return f"情境适应偏探索({s_n}{j_p})", f"虽有感觉驱动的务实倾向({s_n})，但知觉特质({j_p})使其乐于尝试新的可能性"


def generate_persona_md(profession, mbti_type, extra_traits=""):
    info = MBTI_TYPES.get(mbti_type, {"nickname": mbti_type, "traits": ""})
    desc = generate_mbti_description(mbti_type)
    t1_label, t1_desc = derive_convergent_divergent(mbti_type)
    t2_label, t2_desc = derive_system12(mbti_type)
    t3_label, t3_desc = derive_analytical_holistic(mbti_type)
    t4_label, t4_desc = derive_bas_bis(mbti_type)
    t5_label, t5_desc = derive_exploration_exploitation(mbti_type)
    today = date.today().isoformat()
    return f"""---
type: persona
created: "{today}"
---

# Agent Persona

## Profession (从事工作与专业)

{profession}

## MBTI Personality (MBTI人格类型)

**类型**: {mbti_type} ({info['nickname']})

{desc}

## Cognitive Traits (认知特质)

| 维度 | 倾向 | 说明 |
|------|------|------|
| 收敛/发散思维 | {t1_label} | {t1_desc} |
| System 1/2 | {t2_label} | {t2_desc} |
| 分析型/整体型 | {t3_label} | {t3_desc} |
| 趋近/回避导向 | {t4_label} | {t4_desc} |
| 探索/利用倾向 | {t5_label} | {t5_desc} |
""" + (f"""
## Extra Traits (额外性格特质)

{extra_traits}
""" if extra_traits else "")


# ── Helpers ──────────────────────────────────────────────────────────────

def parse_note(filepath):
    """Parse a note file, returning metadata dict and body string."""
    text = filepath.read_text(encoding="utf-8")
    metadata = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            for line in fm_text.split("\n"):
                line = line.strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    val = val.strip().strip('"').strip("'")
                    if val.startswith("[") and val.endswith("]"):
                        val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                    metadata[key.strip()] = val
    return metadata, body


def extract_tldr(body):
    """Extract TL;DR from Obsidian callout block."""
    lines = body.split("\n")
    in_tldr = False
    tldr_lines = []
    for line in lines:
        if re.match(r">\s*\[!abstract\]\s*TL;DR", line, re.I):
            in_tldr = True
            continue
        if in_tldr:
            if line.startswith("> "):
                tldr_lines.append(line[2:].strip())
            elif line.strip() == ">":
                continue
            else:
                break
    text = " ".join(tldr_lines).strip()
    if len(text) > 200:
        text = text[:200] + "..."
    return text


def extract_title_from_body(body):
    """Extract first heading from body as title."""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def note_is_read(filepath):
    """Check if a note has the read marker checked."""
    try:
        text = filepath.read_text(encoding="utf-8")
        return bool(re.search(r"-\s*\[x\]\s*<big><big>已读</big></big>", text))
    except Exception:
        return False


def build_note_info(filepath, source):
    """Build note info dict for API response."""
    metadata, body = parse_note(filepath)
    title = metadata.get("title", extract_title_from_body(body) or filepath.stem)
    note_type = metadata.get("type", "idea")
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    note_date = metadata.get("date", "")
    tldr = extract_tldr(body)
    is_read = note_is_read(filepath) if source == "new" else True

    return {
        "filename": filepath.name,
        "title": title,
        "type": note_type,
        "date": note_date,
        "tags": tags,
        "tldr": tldr,
        "source": source,
        "is_read": is_read,
    }


# ── Background Processing (index-note) ──────────────────────────────────

def run_script(script_name, *args):
    """Run a Python script via uv and return stdout."""
    cmd = ["uv", "run", "python", str(SCRIPTS_DIR / script_name)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed: {result.stderr.strip()}")
    return result.stdout.strip()


PIPELINE_STEPS = [
    {"key": "classify", "label": "分类输入类型"},
    {"key": "gen_id", "label": "生成笔记编号"},
    {"key": "download", "label": "提取图片资源"},
    {"key": "template", "label": "加载笔记模板"},
    {"key": "analyze", "label": "AI 分析内容并填充模板"},
    {"key": "write", "label": "写入笔记文件"},
]


def make_steps(current_key, detail=""):
    steps = []
    found_current = False
    for s in PIPELINE_STEPS:
        if s["key"] == current_key:
            found_current = True
            steps.append({"key": s["key"], "label": s["label"], "status": "running", "detail": detail})
        elif not found_current:
            steps.append({"key": s["key"], "label": s["label"], "status": "done", "detail": ""})
        else:
            steps.append({"key": s["key"], "label": s["label"], "status": "pending", "detail": ""})
    return steps


def finish_step(steps, key, detail=""):
    for s in steps:
        if s["key"] == key:
            s["status"] = "done"
            s["detail"] = detail
    return steps


TYPE_ANALYSIS_STRATEGIES = {
    "idea": """- State the core idea in plain language (Feynman Technique)
- Identify the trigger context (what sparked the idea)
- Challenge assumptions explicitly with a table
- Design a "minimum viable experiment" to test the idea
- Assign maturity level: seed / sprout / tree
- Mark connection types: supports, contradicts, analogizes, extends""",
    "project": """- Top-down first: purpose/problem, then architecture, then details
- Read README.md first, then directory structure, then key source files
- Focus on "when to use / when not to use"
- Extract design decisions and their rationale
- Identify entry points for understanding
- Keep tech stack rationale""",
    "book": """- Apply Adler's analytical reading: classify type, state central thesis, identify argument structure
- Extract key concepts using Feynman Technique
- Trace argument flow as structure map (NOT chapter-by-chapter summaries)
- Engage in dialogue: agree, question, disagree
- Identify blind spots and unstated assumptions
- Must have at least one "immediate application" action item""",
    "paper": """- "In My Own Words" section is MANDATORY
- Extract problem -> motivation -> gap -> solution chain
- Focus on innovations: what's genuinely new vs. incremental
- Identify what this paper "opens up"
- Position in field: classify related work as precursor, competitor, or successor
- Score with brief rationale per dimension""",
    "webinfo": """- Apply SIFT method for credibility
- Estimate "information half-life"
- Separate facts from opinions from predictions
- Identify what's NOT said
- Must answer "so what?"—what does this mean for my work""",
    "webnews": """- Apply 5W1H as a compact table
- Separate verifiable facts from media narrative
- Signal vs Noise assessment
- Stakeholder analysis with explicit motivations
- Record a personal prediction""",
}


def build_analysis_prompt(input_text, input_type, note_type, note_id, today, template_content, images_json, prefetched_content=""):
    images_note = ""
    if images_json:
        images_note = f"\n\nExtracted images (use Obsidian embed format ![[filename|600]]):\n{images_json}"

    content_section = ""
    if prefetched_content:
        content_section = f"\n\nPREFETCHED CONTENT (already retrieved, use this directly — do NOT call WebFetch):\n{prefetched_content}"

    strategy = TYPE_ANALYSIS_STRATEGIES.get(note_type, "")

    return f"""You are IndexNote. Analyze the following input and produce a complete Obsidian note.
Output ONLY the raw markdown of the note (starting with --- frontmatter). No explanations, no code fences.

INPUT: {input_text}
INPUT TYPE: {input_type}
CLASSIFIED AS: {note_type}
NOTE ID: {note_id}
DATE: {today}{images_note}{content_section}

TEMPLATE:
{template_content}

COGNITIVE SCIENCE PRINCIPLES (apply to ALL note types):
1. TL;DR first (Cognitive Load Theory): Start with a 1-3 sentence executive summary in a > [!abstract] TL;DR callout.
2. Self-explanation (Chi et al., 1989): Restate key ideas in your own words rather than copying.
3. "So What?" (Elaborative Interrogation): Every note must answer "how does this change what I do?"
4. Typed connections (Zettelkasten): Classify relationships (supports, contradicts, extends, applies).
5. Retrieval cues (Testing Effect): End with specific scenario triggers ("when would I come back to this?").
6. Separate facts from interpretations: Keep verifiable facts distinct from subjective analysis.

TYPE-SPECIFIC ANALYSIS STRATEGY ({note_type}):
{strategy}

FORMATTING RULES:
- YAML frontmatter between --- markers
- Tags: hyphens not spaces (machine-learning not machine learning)
- Wikilinks: [[Target|Display]] with display alias
- Images: ![[filename.png|600]] (Obsidian wikilink format)
- Missing data: -- (not --- which renders as horizontal rule)
- Formulas: inline $...$ and block $$...$$
- Bilingual headers: ## English (中文)

INSTRUCTIONS:
1. Analyze the content thoroughly following the type-specific strategy above.
2. Fill ALL template sections with substantive content. Replace all {{{{PLACEHOLDER}}}} values.
3. Apply ALL 6 cognitive science principles.
4. Output ONLY the completed note as raw markdown starting with --- frontmatter. Do NOT use any tools. Do NOT wrap in code fences."""


def extract_markdown_from_output(output):
    text = output.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    idx = text.find("---")
    if idx >= 0:
        second = text.find("---", idx + 3)
        if second >= 0:
            return text[idx:].strip()
    return text.strip()


def build_fallback_note(input_text, note_type, note_id, today, template_content):
    title = input_text[:80].strip()
    if title.startswith("http"):
        from urllib.parse import urlparse
        parsed = urlparse(title)
        title = parsed.path.split("/")[-1] or parsed.netloc
    elif os.path.isfile(title):
        title = Path(title).stem

    return f"""---
date: "{today}"
type: {note_type}
id: {note_id}
title: "{title}"
tags: [{note_type}]
status: pending
---

# {title}

> [!abstract] TL;DR
> (待 AI 分析填充)

## Source (来源)

{input_text}

## Notes (备注)

本笔记由 WebUI 创建，AI 分析未完成。可使用以下命令重新生成完整内容：

`/index-note {input_text}`

---

- [ ] <big><big>已读</big></big>
"""


def process_note(task_id, input_text, input_type):
    """Run index-note pipeline in background thread."""
    try:
        # Step 1: Classify input
        steps = make_steps("classify")
        update_task(task_id, status="classifying", progress="正在分类输入类型...", steps=steps)
        classify_output = run_script("classify_input.py", "--input", input_text)
        classification = json.loads(classify_output)
        note_type = classification["type"]
        confidence = classification.get("confidence", 0)
        TYPE_LABELS = {"idea": "想法", "project": "项目", "book": "书籍", "paper": "论文", "webinfo": "网页", "webnews": "新闻"}
        type_label = TYPE_LABELS.get(note_type, note_type)

        # Step 2: Generate note ID
        steps = make_steps("gen_id")
        finish_step(steps, "classify", f"{type_label} (置信度 {confidence})")
        update_task(task_id, status="generating_id", progress="正在生成编号...", steps=steps)
        NEW_DIR.mkdir(parents=True, exist_ok=True)
        note_num = run_script("generate_id.py", "--type", note_type, "--vault-new-dir", str(NEW_DIR), "--vault-deep-dir", str(DEEP_DIR))
        today = date.today().isoformat()
        note_id = f"{today}_{note_type}_{note_num}"
        note_filename = f"{note_id}.md"

        # Step 3: Extract images
        images_json = None
        steps = make_steps("download")
        finish_step(steps, "classify", f"{type_label} (置信度 {confidence})")
        finish_step(steps, "gen_id", note_id)

        temp_img_dir = IMAGES_DIR / f"_tmp_{note_id}"
        if note_type in ("paper", "book", "project"):
            update_task(task_id, status="extracting", progress="正在提取图片...", steps=steps)
            try:
                temp_img_dir.mkdir(parents=True, exist_ok=True)
                img_cmd = [
                    "uv", "run", "--with", "pymupdf", "--with", "requests",
                    "python", str(SCRIPTS_DIR / "extract_images.py"),
                    "--type", note_type, "--input", input_text,
                    "--note-id", note_id, "--output-dir", str(temp_img_dir),
                ]
                img_result = subprocess.run(img_cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120)
                if img_result.returncode == 0 and img_result.stdout.strip():
                    images_json = img_result.stdout.strip()
            except Exception:
                pass
            img_detail = "完成" if images_json else "跳过"
        else:
            img_detail = "无需提取"

        # Step 4: Read template
        steps = make_steps("template")
        finish_step(steps, "classify", f"{type_label} (置信度 {confidence})")
        finish_step(steps, "gen_id", note_id)
        finish_step(steps, "download", img_detail)
        update_task(task_id, status="reading_template", progress="正在加载模板...", steps=steps)
        template_path = TEMPLATE_DIR / f"{note_type}_template.md"
        template_content = ""
        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")

        # Step 5: AI analysis
        steps = make_steps("analyze", "这一步耗时较长，请耐心等待...")
        finish_step(steps, "classify", f"{type_label} (置信度 {confidence})")
        finish_step(steps, "gen_id", note_id)
        finish_step(steps, "download", img_detail)
        finish_step(steps, "template", f"{note_type}_template.md")
        update_task(task_id, status="analyzing", progress="AI 分析中...", steps=steps)

        note_path = NEW_DIR / note_filename

        # Pre-fetch content
        prefetched_content = ""
        if classification.get("is_local_path") and os.path.isfile(input_text):
            update_task(task_id, status="analyzing", progress="正在读取文件内容...", steps=steps)
            file_ext = os.path.splitext(input_text)[1].lower()
            try:
                if file_ext == ".pdf":
                    extract_script = "import fitz,sys;doc=fitz.open(sys.argv[1]);t=''.join(p.get_text() for i,p in enumerate(doc) if i<30);doc.close();print(t[:12000])"
                    fetch_result = subprocess.run(
                        ["uv", "run", "--with", "pymupdf", "python", "-c", extract_script, input_text],
                        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
                    )
                    if fetch_result.returncode == 0 and fetch_result.stdout.strip():
                        prefetched_content = fetch_result.stdout.strip()
                elif file_ext in (".txt", ".md", ".rtf"):
                    text = Path(input_text).read_text(encoding="utf-8", errors="ignore")
                    prefetched_content = text[:12000]
                elif file_ext in (".docx", ".doc"):
                    extract_script = "import zipfile,sys,re;z=zipfile.ZipFile(sys.argv[1]);xml=z.read('word/document.xml').decode('utf-8',errors='ignore');t=re.sub(r'<[^>]+>',' ',xml);print(' '.join(t.split())[:12000])"
                    fetch_result = subprocess.run(
                        ["uv", "run", "python", "-c", extract_script, input_text],
                        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
                    )
                    if fetch_result.returncode == 0 and fetch_result.stdout.strip():
                        prefetched_content = fetch_result.stdout.strip()
            except Exception:
                pass
        elif classification.get("is_url"):
            update_task(task_id, status="analyzing", progress="正在获取网页内容...", steps=steps)
            try:
                fetch_result = subprocess.run(
                    ["uv", "run", "--with", "requests", "--with", "beautifulsoup4",
                     "python", "-c",
                     "import requests, sys; from bs4 import BeautifulSoup; "
                     "r=requests.get(sys.argv[1], timeout=30, headers={'User-Agent':'Mozilla/5.0'}); "
                     "soup=BeautifulSoup(r.text,'html.parser'); "
                     "[s.decompose() for s in soup(['script','style','nav','footer','header'])];"
                     "print(soup.get_text(separator='\\n',strip=True)[:12000])",
                     input_text],
                    capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=45,
                )
                if fetch_result.returncode == 0 and fetch_result.stdout.strip():
                    prefetched_content = fetch_result.stdout.strip()
            except Exception:
                pass
        elif input_type == "text" and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", input_text.strip()):
            update_task(task_id, status="analyzing", progress="正在获取 arXiv 元数据...", steps=steps)
            try:
                fetch_result = subprocess.run(
                    ["uv", "run", "--with", "requests", "python", "-c",
                     "import requests,sys; "
                     f"r=requests.get('https://export.arxiv.org/api/query?id_list={input_text.strip()}',timeout=30); "
                     "print(r.text[:12000])"],
                    capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=45,
                )
                if fetch_result.returncode == 0:
                    prefetched_content = fetch_result.stdout.strip()
            except Exception:
                pass

        prompt = build_analysis_prompt(input_text, input_type, note_type, note_id, today, template_content, images_json, prefetched_content)
        ai_ok = False

        try:
            env = os.environ.copy()
            result = subprocess.run(
                ["claude", "-p", "-"],
                input=prompt,
                capture_output=True, text=True,
                cwd=str(PROJECT_ROOT), timeout=480, env=env,
            )
            if result.returncode == 0 and result.stdout.strip():
                note_content = extract_markdown_from_output(result.stdout.strip())
                if note_content.startswith("---"):
                    note_path.write_text(note_content, encoding="utf-8")
                    ai_ok = True
                else:
                    note_path.write_text(build_fallback_note(input_text, note_type, note_id, today, template_content), encoding="utf-8")
            else:
                stdout_text = result.stdout.strip() if result.stdout else ""
                if "authentication_error" in stdout_text or "OAuth token has expired" in stdout_text:
                    raise RuntimeError("Claude CLI 认证已过期。请在终端运行 `claude login` 刷新登录凭证后重试。")
                note_path.write_text(build_fallback_note(input_text, note_type, note_id, today, template_content), encoding="utf-8")
        except subprocess.TimeoutExpired:
            note_path.write_text(build_fallback_note(input_text, note_type, note_id, today, template_content), encoding="utf-8")

        # Step 6: Finalize
        steps = make_steps("write")
        finish_step(steps, "classify", f"{type_label} (置信度 {confidence})")
        finish_step(steps, "gen_id", note_id)
        finish_step(steps, "download", img_detail)
        finish_step(steps, "template", f"{note_type}_template.md")
        finish_step(steps, "analyze", "AI 分析完成" if ai_ok else "已使用基础模板")
        update_task(task_id, status="writing", progress="正在写入...", steps=steps)

        if note_type in ("paper", "book", "project") and temp_img_dir.exists():
            try:
                fin_cmd = [
                    "uv", "run", "python", str(SCRIPTS_DIR / "finalize_images.py"),
                    "--note-path", str(note_path),
                    "--temp-dir", str(temp_img_dir),
                    "--images-dir", str(IMAGES_DIR),
                    "--note-id", note_id,
                ]
                subprocess.run(fin_cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30)
            except Exception:
                pass

        metadata, body = parse_note(note_path)
        title = metadata.get("title", extract_title_from_body(body) or input_text[:50])

        for s in steps:
            s["status"] = "done"
        finish_step(steps, "write", note_filename)
        update_task(
            task_id, status="completed", progress="处理完成", steps=steps,
            result={"note_path": note_filename, "note_type": note_type, "title": title},
        )

    except Exception as e:
        update_task(task_id, status="error", progress="处理出错", error=str(e))


# ── Background Processing (index-chat) ──────────────────────────────────

def process_chat(task_id, user_message):
    """Run index-chat via Claude CLI in background thread."""
    try:
        update_task(task_id, status="running", progress="正在检索记忆并生成回答...")
        env = os.environ.copy()
        prompt = f'/index-chat {user_message}'
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=300, env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            response = result.stdout.strip()
            update_task(task_id, status="completed", progress="完成", result={"response": response})
        else:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            if "authentication_error" in stdout or "OAuth token has expired" in stdout:
                raise RuntimeError("Claude CLI 认证已过期。请运行 `claude login`。")
            raise RuntimeError(f"Chat failed: {stderr or stdout or 'unknown error'}")
    except subprocess.TimeoutExpired:
        update_task(task_id, status="error", error="聊天请求超时，请稍后重试")
    except Exception as e:
        update_task(task_id, status="error", error=str(e))


# ── Background Processing (index-update) ────────────────────────────────

def process_update(task_id):
    """Run index-update via Claude CLI in background thread."""
    try:
        update_task(task_id, status="running", progress="正在扫描已读笔记，提取知识并归档...")
        env = os.environ.copy()
        result = subprocess.run(
            ["claude", "-p", "/index-update"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=600, env=env,
        )
        if result.returncode == 0:
            response = result.stdout.strip() if result.stdout else "归档整理完成"
            update_task(task_id, status="completed", progress="完成", result={"response": response})
        else:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""
            if "authentication_error" in stdout or "OAuth token has expired" in stdout:
                raise RuntimeError("Claude CLI 认证已过期。请运行 `claude login`。")
            raise RuntimeError(f"Update failed: {stderr or stdout or 'unknown error'}")
    except subprocess.TimeoutExpired:
        update_task(task_id, status="error", error="归档整理超时")
    except Exception as e:
        update_task(task_id, status="error", error=str(e))


# ── Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    persona = VAULT_PATH / "persona.md"
    if persona.exists():
        return redirect(url_for("app_view"))
    return redirect(url_for("init_view"))


@app.route("/init")
def init_view():
    return render_template("init.html")


@app.route("/app")
def app_view():
    persona = VAULT_PATH / "persona.md"
    if not persona.exists():
        return redirect(url_for("init_view"))
    return render_template("app.html")


@app.route("/note/<source>/<filename>")
def note_detail(source, filename):
    if source not in ("new", "archived"):
        abort(404)
    return render_template("note_detail.html", source=source, filename=filename)


@app.route("/vault/images/<filename>")
def vault_image(filename):
    if IMAGES_DIR.is_dir():
        for subdir in IMAGES_DIR.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_tmp"):
                candidate = subdir / filename
                if candidate.is_file():
                    return send_from_directory(str(subdir), filename)
    return send_from_directory(str(IMAGES_DIR), filename)


# ── API Routes ───────────────────────────────────────────────────────────

@app.route("/api/init", methods=["POST"])
def api_init():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    profession = data.get("profession", "").strip()
    mbti_data = data.get("mbti", {})
    extra_traits = data.get("extra_traits", "").strip()
    if not profession:
        return jsonify({"error": "Profession is required"}), 400

    mbti_type = (
        mbti_data.get("E_I", "E")
        + mbti_data.get("S_N", "N")
        + mbti_data.get("T_F", "T")
        + mbti_data.get("J_P", "J")
    )

    if mbti_type not in MBTI_TYPES:
        return jsonify({"error": f"Invalid MBTI type: {mbti_type}"}), 400

    try:
        for d in [NEW_DIR, DEEP_DIR, MEMORY_DIR, IMAGES_DIR, DOWNLOADS_DIR, TEMPLATE_DIR, CHAT_DIR, VAULT_PATH / ".obsidian"]:
            d.mkdir(parents=True, exist_ok=True)

        if RESOURCES_DIR.exists():
            for tmpl in RESOURCES_DIR.glob("*.md"):
                shutil.copy2(str(tmpl), str(TEMPLATE_DIR / tmpl.name))

        obsidian_dir = VAULT_PATH / ".obsidian"
        (obsidian_dir / "core-plugins.json").write_text(
            json.dumps([
                "file-explorer", "global-search", "switcher", "graph", "backlink",
                "canvas", "outgoing-link", "tag-pane", "properties", "page-preview",
                "note-composer", "command-palette", "editor-status", "bookmarks",
                "markdown-importer", "word-count", "file-recovery", "outline",
            ]),
            encoding="utf-8",
        )
        (obsidian_dir / "app.json").write_text("{}", encoding="utf-8")
        (obsidian_dir / "appearance.json").write_text("{}", encoding="utf-8")

        persona_content = generate_persona_md(profession, mbti_type, extra_traits)
        (VAULT_PATH / "persona.md").write_text(persona_content, encoding="utf-8")

        info = MBTI_TYPES[mbti_type]
        return jsonify({"success": True, "mbti_type": mbti_type, "nickname": info["nickname"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notes")
def api_notes():
    """List notes. ?status=new|read|archived"""
    status = request.args.get("status", "new")
    notes = []

    if status in ("new", "read"):
        if NEW_DIR.exists():
            for fp in sorted(NEW_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
                is_read = note_is_read(fp)
                if (status == "new" and not is_read) or (status == "read" and is_read):
                    notes.append(build_note_info(fp, "new"))
    elif status == "archived":
        if DEEP_DIR.exists():
            for fp in sorted(DEEP_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
                notes.append(build_note_info(fp, "archived"))

    return jsonify(notes)


@app.route("/api/note/<source>/<filename>")
def api_note(source, filename):
    if source == "new":
        filepath = NEW_DIR / filename
    elif source == "archived":
        filepath = DEEP_DIR / filename
    else:
        return jsonify({"error": "Invalid source"}), 400

    if not filepath.exists() or not filepath.is_file():
        return jsonify({"error": "Note not found"}), 404

    metadata, body = parse_note(filepath)
    return jsonify({
        "filename": filename,
        "source": source,
        "metadata": metadata,
        "content": body,
        "is_read": note_is_read(filepath),
    })


@app.route("/api/note/toggle-read", methods=["POST"])
def api_toggle_read():
    """Toggle the read marker checkbox in a note."""
    data = request.get_json()
    filename = data.get("filename", "")
    personal_notes = data.get("personal_notes", "").strip()
    filepath = NEW_DIR / filename

    if not filepath.exists():
        return jsonify({"error": "Note not found"}), 404

    text = filepath.read_text(encoding="utf-8")

    # Write personal notes into the note (replace everything after the marker)
    if personal_notes:
        text = re.sub(
            r"(\*\*（可选）笔记与想法\*\*[：:])[\s\S]*$",
            lambda m: m.group(1) + "\n" + personal_notes + "\n",
            text,
        )

    # Toggle: checked -> unchecked or unchecked -> checked
    if re.search(r"-\s*\[x\]\s*<big><big>已读</big></big>", text):
        text = re.sub(
            r"-\s*\[x\]\s*<big><big>已读</big></big>",
            "- [ ] <big><big>已读</big></big>",
            text,
        )
        new_state = False
    elif re.search(r"-\s*\[ \]\s*<big><big>已读</big></big>", text):
        text = re.sub(
            r"-\s*\[ \]\s*<big><big>已读</big></big>",
            "- [x] <big><big>已读</big></big>",
            text,
        )
        new_state = True
    else:
        return jsonify({"error": "Read marker not found in note"}), 400

    filepath.write_text(text, encoding="utf-8")
    return jsonify({"success": True, "is_read": new_state})


@app.route("/api/process", methods=["POST"])
def api_process():
    input_type = request.form.get("input_type", "text")
    input_text = ""

    if input_type == "text":
        input_text = request.form.get("input_text", "").strip()
        if not input_text:
            return jsonify({"error": "Text input is required"}), 400
    elif input_type == "url":
        input_text = request.form.get("input_text", "").strip()
        if not input_text:
            return jsonify({"error": "URL is required"}), 400
    elif input_type == "file":
        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "File is required"}), 400
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = DOWNLOADS_DIR / file.filename
        file.save(str(save_path))
        input_text = str(save_path)
    else:
        return jsonify({"error": "Invalid input type"}), 400

    task_id = uuid.uuid4().hex[:12]
    with tasks_lock:
        tasks[task_id] = {
            "status": "pending", "progress": "任务已创建...",
            "result": None, "error": None,
            "input_text": input_text, "input_type": input_type,
        }

    thread = threading.Thread(target=process_note, args=(task_id, input_text, input_type), daemon=True)
    thread.start()
    return jsonify({"task_id": task_id})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400

    task_id = uuid.uuid4().hex[:12]
    with tasks_lock:
        tasks[task_id] = {
            "status": "pending", "progress": "正在处理...",
            "result": None, "error": None,
        }

    thread = threading.Thread(target=process_chat, args=(task_id, message), daemon=True)
    thread.start()
    return jsonify({"task_id": task_id})


@app.route("/api/update", methods=["POST"])
def api_update():
    task_id = uuid.uuid4().hex[:12]
    with tasks_lock:
        tasks[task_id] = {
            "status": "pending", "progress": "正在启动归档整理...",
            "result": None, "error": None,
        }

    thread = threading.Thread(target=process_update, args=(task_id,), daemon=True)
    thread.start()
    return jsonify({"task_id": task_id})


@app.route("/api/task/<task_id>")
def api_task(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", ""),
        "steps": task.get("steps", []),
        "result": task.get("result"),
        "error": task.get("error"),
    })


@app.route("/api/persona")
def api_persona():
    persona_path = VAULT_PATH / "persona.md"
    if not persona_path.exists():
        return jsonify({"exists": False})
    metadata, body = parse_note(persona_path)
    raw = persona_path.read_text(encoding="utf-8")
    return jsonify({"exists": True, "metadata": metadata, "content": body, "raw": raw})


@app.route("/api/persona", methods=["PUT"])
def api_persona_save():
    data = request.get_json()
    raw = data.get("raw", "")
    if not raw.strip():
        return jsonify({"error": "Content cannot be empty"}), 400
    persona_path = VAULT_PATH / "persona.md"
    persona_path.write_text(raw, encoding="utf-8")
    return jsonify({"success": True})


@app.route("/api/chat-logs")
def api_chat_logs():
    """List chat log files from _chat/ (new) and deep/ (archived)."""
    logs = []

    # New chat logs in _chat/
    if CHAT_DIR.exists():
        for fp in sorted(CHAT_DIR.glob("*.md"), reverse=True):
            metadata, body = parse_note(fp)
            date_str = metadata.get("date", fp.stem[:10] if len(fp.stem) >= 10 else "")
            # Extract first line of chat as preview
            preview = ""
            for line in body.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---") and not line.startswith("**🕐"):
                    preview = line[:100] + ("..." if len(line) > 100 else "")
                    break
            logs.append({
                "filename": fp.name,
                "date": date_str,
                "source": "chat",
                "preview": preview,
            })

    # Archived chat logs in deep/ (files with _Chat in name or type: chat)
    if DEEP_DIR.exists():
        for fp in sorted(DEEP_DIR.glob("*Chat*.md"), reverse=True):
            metadata, body = parse_note(fp)
            date_str = metadata.get("date", fp.stem[:10] if len(fp.stem) >= 10 else "")
            preview = ""
            for line in body.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---") and not line.startswith("**🕐"):
                    preview = line[:100] + ("..." if len(line) > 100 else "")
                    break
            logs.append({
                "filename": fp.name,
                "date": date_str,
                "source": "archived",
                "preview": preview,
            })

    return jsonify(logs)


@app.route("/api/chat-log/<source>/<filename>")
def api_chat_log_detail(source, filename):
    """Return content of a specific chat log file."""
    if source == "chat":
        filepath = CHAT_DIR / filename
    elif source == "archived":
        filepath = DEEP_DIR / filename
    else:
        return jsonify({"error": "Invalid source"}), 400

    if not filepath.exists() or not filepath.name.endswith(".md"):
        return jsonify({"error": "Not found"}), 404

    # Security: ensure path doesn't escape
    try:
        filepath.resolve().relative_to(VAULT_PATH.resolve())
    except ValueError:
        return jsonify({"error": "Invalid path"}), 400

    metadata, body = parse_note(filepath)
    return jsonify({
        "filename": filename,
        "source": source,
        "metadata": metadata,
        "content": body,
    })


@app.route("/api/stats")
def api_stats():
    """Return counts for sidebar badges."""
    new_count = 0
    read_count = 0
    archived_count = 0

    if NEW_DIR.exists():
        for fp in NEW_DIR.glob("*.md"):
            if note_is_read(fp):
                read_count += 1
            else:
                new_count += 1

    if DEEP_DIR.exists():
        archived_count = sum(1 for _ in DEEP_DIR.glob("*.md"))

    chat_count = 0
    if CHAT_DIR.exists():
        chat_count = sum(1 for _ in CHAT_DIR.glob("*.md"))

    return jsonify({"new": new_count, "read": read_count, "archived": archived_count, "chat_logs": chat_count})


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3008))
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Vault path:   {VAULT_PATH}")
    print(f"Starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
