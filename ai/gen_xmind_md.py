#!/usr/bin/env python3
"""Generate XMind from markdown test case directory.

Usage:
    python3 ai/gen_xmind_md.py cases/告警规则组 -o cases/告警规则组.xmind
"""

import re, os, sys, tempfile, zipfile, shutil, hashlib
from xml.sax.saxutils import escape
from datetime import datetime

NS_CONTENT = "urn:xmind:xmap:xmlns:content:2.0"

CATEGORY_MAP = {
    "列表": "1. 列表查询",
    "创建": "2. 新增数据",
    "编辑": "3. 编辑数据",
    "详情": "4. 详情查看",
    "删除": "5. 删除数据",
    "其他": "6. 其他",
}
CATEGORY_ORDER = ["列表", "创建", "编辑", "详情", "删除", "其他"]


def _id(seed=None):
    return hashlib.sha256((seed or str(datetime.now().timestamp())).encode()).hexdigest()[:26]


def _topic(title, children=None, tid=None):
    parts = [f'<topic id="{tid or _id(title)}"><title>{escape(title)}</title>']
    if children:
        parts.append('<children><topics type="attached">')
        parts.extend(children)
        parts.append('</topics></children>')
    parts.append('</topic>')
    return '\n'.join(parts)


def parse_md(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by test case headers
    blocks = re.split(r'\n(?=## tc-)', content)
    results = []
    for block in blocks:
        block = block.strip()
        if not block.startswith('## tc-'):
            continue

        title_m = re.search(r'## (tc-.+)', block)
        title = title_m.group(1).strip() if title_m else 'testcase'

        pc_m = re.search(r'### 前置条件 \(pc\)\n- (.+)', block)
        pc = pc_m.group(1).strip() if pc_m else None

        steps = []
        step_section = False
        for line in block.splitlines():
            if '测试步骤 & 预期结果' in line:
                step_section = True
                continue
            if step_section and line.startswith('#'):
                break
            if step_section:
                m = re.match(r'\d+\.\s*(.+?)\s*→\s*(.+)', line.strip())
                if m:
                    steps.append((m.group(1).strip(), m.group(2).strip()))

        results.append((title, pc, steps))
    return results


def generate_xmind(output_path, feature, version, categories):
    """categories: { category_name: [(test_case_title, pc, steps), ...] }"""
    sheet_id = _id("sheet")
    root_id = _id("root")
    ts = str(int(datetime.now().timestamp() * 1000))

    cat_topics = []
    for cat_key in CATEGORY_ORDER:
        if cat_key not in categories:
            continue
        cat_label = CATEGORY_MAP[cat_key]
        case_topics = []
        for title, pc, steps in categories[cat_key]:
            case_children = []
            if pc:
                case_children.append(_topic(f"pc：{pc}"))
            for i, (step_desc, expected) in enumerate(steps, 1):
                case_children.append(
                    _topic(f"{i}. {step_desc}", children=[_topic(expected)])
                )
            case_topics.append(_topic(title, children=case_children))
        cat_topics.append(_topic(cat_label, children=case_topics))

    root_topic = _topic(f"{feature} - {version}", children=cat_topics, tid=root_id)

    content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-content xmlns="{NS_CONTENT}" modified-by="opencode" timestamp="{ts}" version="2.0">
<sheet id="{sheet_id}" modified-by="opencode" timestamp="{ts}">
{root_topic}
</sheet>
</xmap-content>'''

    meta = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0">
<author><name>opencode</name></author>
<created>{ts}</created>
</meta>'''

    manifest = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
<file-entry full-path="content.xml" media-type="text/xml"/>
<file-entry full-path="meta.xml" media-type="text/xml"/>
<file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
</manifest>'''

    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "META-INF"))
        with open(os.path.join(tmp, "content.xml"), "w", encoding="utf-8") as f:
            f.write(content)
        with open(os.path.join(tmp, "meta.xml"), "w", encoding="utf-8") as f:
            f.write(meta)
        with open(os.path.join(tmp, "META-INF", "manifest.xml"), "w", encoding="utf-8") as f:
            f.write(manifest)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(os.path.join(tmp, "content.xml"), "content.xml")
            zf.write(os.path.join(tmp, "meta.xml"), "meta.xml")
            zf.write(os.path.join(tmp, "META-INF", "manifest.xml"), "META-INF/manifest.xml")
    finally:
        shutil.rmtree(tmp)

    total_cases = sum(len(cases) for cases in categories.values())
    print(f"✅ XMind generated: {output_path}")
    print(f"   Feature: {feature} ({version})")
    for cat_key in CATEGORY_ORDER:
        if cat_key in categories:
            print(f"     - {CATEGORY_MAP[cat_key]}: {len(categories[cat_key])} cases")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate XMind from a directory of markdown test cases")
    parser.add_argument("input", help="Path to directory containing markdown test case files")
    parser.add_argument("--output", "-o", default=None, help="Output xmind path")
    parser.add_argument("--feature", default=None, help="Feature name (default: directory name)")
    parser.add_argument("--version", default="4.x", help="Version")
    args = parser.parse_args()

    input_dir = args.input.rstrip('/').rstrip('\\')
    feature = args.feature or os.path.basename(input_dir)

    categories = {}
    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith('.md'):
            continue
        cat_key = fname.split('-')[0]
        if cat_key not in CATEGORY_MAP:
            continue
        filepath = os.path.join(input_dir, fname)
        for title, pc, steps in parse_md(filepath):
            categories.setdefault(cat_key, []).append((title, pc, steps))

    if not categories:
        print("No valid test case files found.")
        sys.exit(1)

    output = args.output or os.path.join(input_dir, f"{feature}.xmind")
    generate_xmind(output, feature, args.version, categories)