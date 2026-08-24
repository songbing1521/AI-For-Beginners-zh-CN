# -*- coding: utf-8 -*-
"""把 translations/zh-CN 下的中文课程笔记打包成单文件阅读网站 course-site/index.html"""
import os
import re
import json
from urllib.parse import quote, unquote

import markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "translations", "zh-CN")
LESSONS = os.path.join(SRC, "lessons")
OUT_DIR = os.path.join(ROOT, "course-site")
OUT_FILE = os.path.join(OUT_DIR, "index.html")
SRC_PREFIX = "translations/zh-CN/"

MODULE_LABELS = {
    "0-course-setup": "第0章 · 课程准备",
    "1-Intro": "第1章 · AI 导论",
    "2-Symbolic": "第2章 · 符号 AI",
    "3-NeuralNetworks": "第3章 · 神经网络",
    "4-ComputerVision": "第4章 · 计算机视觉",
    "5-NLP": "第5章 · 自然语言处理",
    "6-Other": "第6章 · 其他 AI 技术",
    "7-Ethics": "第7章 · AI 伦理",
    "X-Extras": "附加内容 · 多模态",
}

DOC_LABELS = {
    "assignment": "📝 作业",
    "setup": "🛠 环境搭建",
    "how-to-run": "▶ 如何运行课程",
    "for-teachers": "👨‍🏫 教师指南",
    "CNN_Architectures": "🗺 CNN 架构一览",
    "TrainingTricks": "⚙ 训练技巧",
}


def to_id(abs_path):
    """md 文件绝对路径 -> 网站内的 doc id（相对 translations/zh-CN，正斜杠）"""
    rel = os.path.relpath(abs_path, SRC).replace("\\", "/")
    return rel


def rel_to_root(abs_path):
    """文件绝对路径 -> 相对仓库根目录的路径（正斜杠）"""
    return os.path.relpath(abs_path, ROOT).replace("\\", "/")


def doc_id_from_root_rel(root_rel):
    if root_rel.startswith(SRC_PREFIX):
        return root_rel[len(SRC_PREFIX):]
    return None


def extract_title(text, fallback):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if not m:
        return fallback
    t = m.group(1)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)  # 去掉行内图片
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)  # 链接只留文字
    return t.strip()


# ---------- 第一遍：收集所有 md 文件 ----------
all_md = []
overview = os.path.join(SRC, "README.md")
if os.path.exists(overview):
    all_md.append(overview)
for dirpath, dirnames, filenames in os.walk(LESSONS):
    dirnames[:] = [d for d in sorted(dirnames) if d != "sketchnotes"]
    for fn in sorted(filenames):
        if fn.endswith(".md"):
            all_md.append(os.path.join(dirpath, fn))

# 附录：对学习者有用但不在 lessons 结构里的文档
APPENDIX = [
    ("lessons/README.md", "📚 课程大纲"),
    ("etc/Mindmap.md", "🗺 课程思维导图"),
    ("troubleshoot.md", "🔧 环境故障排除"),
    ("lessons/sketchnotes/README.md", "✏️ 课程手绘笔记"),
    ("examples/README.md", "📦 示例项目"),
    ("etc/quiz-app/README.md", "❓ 测验应用"),
]
for rel, _label in APPENDIX:
    p = os.path.join(SRC, rel.replace("/", os.sep))
    if os.path.exists(p):
        all_md.append(p)

ids = {to_id(p): p for p in all_md}
root_rel_to_id = {rel_to_root(p): to_id(p) for p in all_md}

# ---------- 第二遍：转换 ----------
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+?)\)")
IMG_TAG_RE = re.compile(r"(<img\s[^>]*?src=[\"'])([^\"']+)([\"'])")

RAW_BASE = "https://raw.githubusercontent.com/songbing1521/AI-For-Beginners-zh-CN/main/"


def convert(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    base = os.path.dirname(path)

    def resolve_resource(target):
        """把 md 里的相对资源路径转成网站可用的 src；返回 None 表示不用改"""
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith(("#", "/", "data:")):
            return None
        # 源文件里的路径可能已做过百分号编码，先解码再按真实文件名处理，避免二次编码
        target = unquote(target)
        abs_t = os.path.normpath(os.path.join(base, target))
        root_rel = rel_to_root(abs_t)
        if os.path.exists(abs_t):
            return "../" + quote(root_rel)
        # 翻译工具有时引用旧文件名（哈希/扩展名对不上），尝试同目录同前缀匹配
        def name_stem(p):
            s = os.path.basename(p)
            if "." in s:
                s = s[: s.rfind(".")]
            i = s.rfind(".")
            if i > 0 and re.fullmatch(r"[0-9a-f]{8,64}", s[i + 1:]):
                s = s[:i]  # 剥掉嵌入的哈希段（名字.哈希.扩展名）
            return s

        stem = name_stem(target)
        parent = os.path.dirname(abs_t)
        if os.path.isdir(parent):
            for fn in os.listdir(parent):
                if name_stem(fn) == stem:
                    return "../" + quote(rel_to_root(os.path.join(parent, fn)))
        return RAW_BASE + quote(root_rel)

    def img_tag_repl(m):
        new_src = resolve_resource(m.group(2))
        if new_src is None:
            return m.group(0)
        return m.group(1) + new_src + m.group(3)

    def repl(m):
        bang, label, raw_target = m.group(1), m.group(2), m.group(3)
        # 去掉链接里可能带的 "标题" 部分
        target = raw_target
        if target.endswith('"') and ' "' in target:
            target = target.rsplit(' "', 1)[0]
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            return m.group(0)
        anchor = ""
        if "#" in target:
            target, anchor = target.split("#", 1)
            anchor = "#" + anchor
        if not target:
            return m.group(0)
        target = unquote(target)
        abs_t = os.path.normpath(os.path.join(base, target))
        root_rel = rel_to_root(abs_t)
        if target.endswith(".md"):
            did = root_rel_to_id.get(root_rel)
            if did:
                return "[{}]({})".format(label, "#/doc/" + quote(did))
            return "[{}]({})".format(label, "../" + quote(root_rel))
        # 资源链接：原文是图片(!)就保持图片，普通文件链接保持链接
        new_src = resolve_resource(target)
        if new_src is None:
            return m.group(0)
        return "{}[{}]({})".format(bang, label, new_src)

    text = LINK_RE.sub(repl, text)
    text = IMG_TAG_RE.sub(img_tag_repl, text)
    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    html_out = md.convert(text)
    return html_out


docs = {}
for did, path in ids.items():
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    title = extract_title(raw, os.path.basename(did))
    docs[did] = {"t": title, "h": convert(path)}

# ---------- 构建目录树 ----------
nav = []      # [{label, docs:[{id,label,children:[{id,label}]}]}]
order = []    # 线性顺序，用于上一篇/下一篇

if "README.md" in docs:
    nav.append({"label": "🏁 课程总览", "docs": [{"id": "README.md", "label": "课程总览"}]})
    order.append("README.md")

for mod in sorted(os.listdir(LESSONS)):
    mod_dir = os.path.join(LESSONS, mod)
    if not os.path.isdir(mod_dir) or mod == "sketchnotes":
        continue
    mod_label = MODULE_LABELS.get(mod, mod)
    entries = []
    mod_children = []
    mod_readme = os.path.join(mod_dir, "README.md")
    if os.path.exists(mod_readme):
        did = to_id(mod_readme)
        entries.append({"id": did, "label": "章节概述", "children": mod_children})
        order.append(did)

    # 模块目录下直接放置的文档（如第0章的 setup/how-to-run/for-teachers）
    for fn in sorted(os.listdir(mod_dir)):
        if fn.endswith(".md") and fn != "README.md":
            did = to_id(os.path.join(mod_dir, fn))
            stem = fn[:-3]
            label = DOC_LABELS.get(stem, "📄 " + stem)
            if os.path.exists(mod_readme):
                mod_children.append({"id": did, "label": label})
            else:
                entries.append({"id": did, "label": label})
            if did in docs and os.path.exists(mod_readme):
                docs[did]["t"] = mod_label + " · " + label.strip("📄📝 ")
            order.append(did)

    # 一级子目录 = 课程
    lessons = sorted(
        [d for d in os.listdir(mod_dir) if os.path.isdir(os.path.join(mod_dir, d))],
    )
    # 没有编号前缀的目录排在后面（如 lab）
    def lesson_key(name):
        m = re.match(r"^(\d+)", name)
        return (0, int(m.group(1))) if m else (1, 0)

    lessons.sort(key=lesson_key)
    for lesson in lessons:
        ldir = os.path.join(mod_dir, lesson)
        main = os.path.join(ldir, "README.md")
        children = []
        if os.path.exists(main):
            did = to_id(main)
            label = docs[did]["t"]
            entries.append({"id": did, "label": label, "children": children})
            order.append(did)
        # 课程下其他文档
        for fn in sorted(os.listdir(ldir)):
            if fn.endswith(".md") and fn != "README.md":
                did = to_id(os.path.join(ldir, fn))
                stem = fn[:-3]
                label = DOC_LABELS.get(stem, "📄 " + stem)
                children.append({"id": did, "label": label})
                if did in docs and os.path.exists(main):
                    docs[did]["t"] = docs[to_id(main)]["t"] + " · " + label.strip("📄📝 ")
                order.append(did)
        lab = os.path.join(ldir, "lab", "README.md")
        if os.path.exists(lab):
            did = to_id(lab)
            children.append({"id": did, "label": "🧪 实验"})
            if did in docs and os.path.exists(main):
                docs[did]["t"] = docs[to_id(main)]["t"] + " · 实验"
            order.append(did)

    nav.append({"label": mod_label, "docs": entries})

# 附录
appendix_entries = [{"id": rel, "label": label} for rel, label in APPENDIX if rel in docs]
if appendix_entries:
    nav.append({"label": "📎 附录", "docs": appendix_entries})
    order.extend(e["id"] for e in appendix_entries)

payload = json.dumps({"docs": docs, "nav": nav, "order": order}, ensure_ascii=False, separators=(",", ":"))
payload = payload.replace("</", "<\\/")  # 防止提前闭合 script 标签

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI for Beginners · 中文课程笔记</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<style>
:root{--primary:#2563eb;--bg:#f7f8fa;--side:#fff;--text:#1f2937;--muted:#6b7280;--border:#e5e7eb;--code:#f3f4f6}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Microsoft YaHei",-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.8}
.topbar{position:fixed;top:0;left:0;right:0;height:54px;background:var(--primary);color:#fff;display:flex;align-items:center;gap:14px;padding:0 18px;z-index:20;box-shadow:0 2px 10px rgba(0,0,0,.18)}
.topbar .brand{font-size:16px;font-weight:700;white-space:nowrap}
.searchbox{position:relative;flex:1;max-width:420px}
.searchbox input{width:100%;height:32px;border:none;border-radius:16px;padding:0 14px 0 34px;font-size:13px;outline:none;background:rgba(255,255,255,.92)}
.searchbox svg{position:absolute;left:11px;top:8px;width:16px;height:16px;fill:#9ca3af}
.results{position:absolute;top:40px;left:0;right:0;background:#fff;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.18);max-height:60vh;overflow:auto;display:none}
.results.show{display:block}
.results .r{display:block;padding:9px 14px;border-bottom:1px solid #f3f4f6;text-decoration:none;color:var(--text)}
.results .r:hover{background:#eff6ff}
.results .r .rt{font-size:13.5px;font-weight:600}
.results .r .rm{font-size:11.5px;color:var(--muted)}
.results .empty{padding:14px;color:var(--muted);font-size:13px}
.layout{display:flex;padding-top:54px;min-height:100vh}
.sidebar{width:292px;flex-shrink:0;background:var(--side);border-right:1px solid var(--border);position:sticky;top:54px;height:calc(100vh - 54px);overflow-y:auto;padding:14px 10px 40px}
.sidebar::-webkit-scrollbar{width:6px}.sidebar::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:3px}
.mod{margin-bottom:6px}
.mod>.mlabel{font-size:12.5px;font-weight:700;color:var(--muted);letter-spacing:.5px;padding:10px 12px 4px;text-transform:uppercase}
.mod.open>.mlabel,.mod>.mlabel:hover{color:var(--primary)}
.mod .items{display:none}
.mod.open .items{display:block}
.mod.current>.mlabel{color:var(--primary)}
.side-link{display:flex;align-items:center;gap:6px;padding:6px 12px;color:#374151;text-decoration:none;font-size:13.5px;border-radius:6px;border-left:3px solid transparent;line-height:1.4}
.side-link:hover{background:#eef2f7}
.side-link.active{background:#eff6ff;color:var(--primary);border-left-color:var(--primary);font-weight:600}
.child-link{padding-left:30px;font-size:13px;color:var(--muted)}
.content{flex:1;min-width:0;max-width:860px;margin:0 auto;padding:30px 42px 90px}
.doc-body h1{font-size:26px;margin:18px 0 16px;padding-bottom:10px;border-bottom:2px solid var(--border)}
.doc-body h2{font-size:20px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--primary)}
.doc-body h3{font-size:16.5px;margin:26px 0 10px}
.doc-body h4{font-size:15px;margin:20px 0 8px}
.doc-body p{margin:10px 0}
.doc-body ul,.doc-body ol{margin:10px 0 10px 26px}
.doc-body li{margin:4px 0}
.doc-body img{max-width:100%;height:auto;border-radius:8px;margin:12px auto;display:block;box-shadow:0 1px 6px rgba(0,0,0,.1)}
.doc-body code{background:var(--code);padding:2px 6px;border-radius:4px;font-family:Consolas,"Courier New",monospace;font-size:13px;color:#be185d;word-break:break-word}
.doc-body pre{background:#0f172a;color:#e2e8f0;padding:16px 18px;border-radius:10px;overflow-x:auto;margin:14px 0}
.doc-body pre code{background:none;color:inherit;padding:0;font-size:13px;line-height:1.6}
.doc-body blockquote{border-left:4px solid var(--primary);background:#eff6ff;padding:8px 16px;margin:12px 0;border-radius:0 6px 6px 0;color:#374151}
.doc-body table{border-collapse:collapse;width:100%;margin:14px 0;display:block;overflow-x:auto}
.doc-body th,.doc-body td{border:1px solid var(--border);padding:8px 12px;text-align:left;font-size:14px}
.doc-body th{background:#eff6ff}
.doc-body hr{border:none;border-top:1px solid var(--border);margin:26px 0}
.doc-body a{color:var(--primary)}
.breadcrumb{font-size:12.5px;color:var(--muted);margin-bottom:6px}
.pager{display:flex;gap:12px;margin-top:48px}
.pager a{flex:1;background:#fff;border:1px solid var(--border);border-radius:10px;padding:12px 16px;text-decoration:none;color:var(--text)}
.pager a:hover{border-color:var(--primary);box-shadow:0 2px 10px rgba(37,99,235,.12)}
.pager .dir{font-size:11.5px;color:var(--muted)}
.pager .pt{font-size:14px;font-weight:600;color:var(--primary)}
.pager .next{text-align:right}
.totop{position:fixed;right:26px;bottom:26px;width:42px;height:42px;border-radius:50%;background:var(--primary);color:#fff;border:none;font-size:18px;cursor:pointer;box-shadow:0 4px 14px rgba(37,99,235,.4);display:none;z-index:15}
.loading{color:var(--muted);padding:40px;text-align:center}
@media (max-width:900px){.sidebar{display:none}.content{padding:20px}}
@media print{.sidebar,.topbar,.pager,.totop{display:none}.content{max-width:100%}}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">📘 AI for Beginners · 中文课程笔记</div>
  <div class="searchbox">
    <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"/></svg>
    <input id="q" type="text" placeholder="搜索笔记标题或内容…" autocomplete="off">
    <div class="results" id="results"></div>
  </div>
</div>
<div class="layout">
  <nav class="sidebar" id="sidebar"></nav>
  <main class="content"><div class="doc-body" id="doc"><div class="loading">加载中…</div></div></main>
</div>
<button class="totop" id="totop" title="回到顶部">↑</button>
<script id="data" type="application/json">__PAYLOAD__</script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const {docs, nav, order} = DATA;
const docEl = document.getElementById('doc');
const sidebar = document.getElementById('sidebar');

// id -> 面包屑（模块/课程名）
const crumb = {};
nav.forEach(m => m.docs.forEach(d => {
  const prefix = crumb[d.id] === undefined ? m.label : crumb[d.id];
  if (!(d.id in crumb)) crumb[d.id] = m.label;
  (d.children || []).forEach(c => { if (!(c.id in crumb)) crumb[c.id] = (docs[d.id] ? docs[d.id].t : '') ; });
}));

// 侧边栏
nav.forEach((m, mi) => {
  const box = document.createElement('div');
  box.className = 'mod';
  box.innerHTML = '<div class="mlabel">' + m.label + '</div>';
  const items = document.createElement('div');
  items.className = 'items';
  m.docs.forEach(d => {
    const a = document.createElement('a');
    a.className = 'side-link'; a.href = '#/doc/' + encodeURIComponent(d.id);
    a.textContent = d.label; a.dataset.doc = d.id;
    items.appendChild(a);
    (d.children || []).forEach(c => {
      const ca = document.createElement('a');
      ca.className = 'side-link child-link'; ca.href = '#/doc/' + encodeURIComponent(c.id);
      ca.textContent = c.label; ca.dataset.doc = c.id;
      items.appendChild(ca);
    });
  });
  box.appendChild(items);
  box.querySelector('.mlabel').addEventListener('click', () => box.classList.toggle('open'));
  sidebar.appendChild(box);
});

function renderMath(){
  if (window.renderMathInElement) {
    renderMathInElement(docEl, {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false},
        {left: '\\\\(', right: '\\\\)', display: false},
        {left: '\\\\[', right: '\\\\]', display: true}
      ],
      throwOnError: false
    });
  }
}

function currentId(){
  const m = location.hash.match(/^#\/doc\/(.+)$/);
  return m ? decodeURIComponent(m[1]) : (order[0] || 'README.md');
}

function show(){
  const id = currentId();
  const d = docs[id];
  if (!d) { docEl.innerHTML = '<p>找不到该笔记。</p>'; return; }
  // 隐藏加载失败的图片
  let h = d.h.replace(/<img /g, '<img onerror="this.style.display=\\'none\\'" loading="lazy" ');
  docEl.innerHTML = '<div class="breadcrumb">' + (crumb[id] || '') + '</div>' + h;
  // 高亮侧边栏
  sidebar.querySelectorAll('.side-link').forEach(a => a.classList.toggle('active', a.dataset.doc === id));
  sidebar.querySelectorAll('.mod').forEach(b => {
    const has = b.querySelector('.side-link.active');
    b.classList.toggle('current', !!has);
    if (has) b.classList.add('open');
  });
  // 上一篇 / 下一篇
  const i = order.indexOf(id);
  const prev = i > 0 ? order[i - 1] : null;
  const next = i >= 0 && i < order.length - 1 ? order[i + 1] : null;
  let pager = '<div class="pager">';
  pager += prev ? '<a href="#/doc/' + encodeURIComponent(prev) + '"><div class="dir">← 上一篇</div><div class="pt">' + docs[prev].t + '</div></a>' : '<span></span>';
  pager += next ? '<a class="next" href="#/doc/' + encodeURIComponent(next) + '"><div class="dir">下一篇 →</div><div class="pt">' + docs[next].t + '</div></a>' : '<span></span>';
  pager += '</div>';
  docEl.insertAdjacentHTML('beforeend', pager);
  renderMath();
  window.scrollTo(0, 0);
  document.getElementById('results').classList.remove('show');
}
window.addEventListener('hashchange', show);

// 搜索
const q = document.getElementById('q');
const results = document.getElementById('results');
const plain = {};
Object.keys(docs).forEach(id => {
  const tmp = document.createElement('div');
  tmp.innerHTML = docs[id].h;
  plain[id] = (docs[id].t + ' ' + tmp.textContent).replace(/\\s+/g, ' ');
});
q.addEventListener('input', () => {
  const kw = q.value.trim().toLowerCase();
  if (!kw) { results.classList.remove('show'); return; }
  let hits = Object.keys(docs).filter(id => plain[id].toLowerCase().includes(kw));
  hits.sort((a, b) => {
    const ta = docs[a].t.toLowerCase().includes(kw) ? 0 : 1;
    const tb = docs[b].t.toLowerCase().includes(kw) ? 0 : 1;
    if (ta !== tb) return ta - tb;
    return order.indexOf(a) - order.indexOf(b);
  });
  hits = hits.slice(0, 30);
  results.innerHTML = hits.length
    ? hits.map(id => '<a class="r" href="#/doc/' + encodeURIComponent(id) + '"><div class="rt">' + docs[id].t + '</div><div class="rm">' + (crumb[id] || '') + '</div></a>').join('')
    : '<div class="empty">没有找到包含「' + q.value + '」的笔记</div>';
  results.classList.add('show');
});
document.addEventListener('click', e => {
  if (!e.target.closest('.searchbox')) results.classList.remove('show');
});

// 回到顶部
const totop = document.getElementById('totop');
window.addEventListener('scroll', () => totop.style.display = window.scrollY > 500 ? 'block' : 'none');
totop.addEventListener('click', () => window.scrollTo({top: 0, behavior: 'smooth'}));

// 默认展开第一章
const firstMod = sidebar.querySelector('.mod:nth-child(2)');
if (firstMod) firstMod.classList.add('open');
show();
</script>
</body>
</html>
"""

os.makedirs(OUT_DIR, exist_ok=True)
html_out = HTML.replace("__PAYLOAD__", payload)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(html_out)
print("done:", OUT_FILE)
print("docs:", len(docs), "order:", len(order))
