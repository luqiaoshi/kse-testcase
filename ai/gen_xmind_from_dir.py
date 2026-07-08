#!/usr/bin/env python3
"""Generate a single XMind file from all markdown test case files in a directory,
regrouped by CRUD category per feature module.

Usage:
    python3 ai/gen_xmind_from_dir.py cases/byd -o cases/byd/BYD测试用例.xmind
"""

import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_xmind_from_license_md import parse_md, _topic, _id
from datetime import datetime
import tempfile, zipfile, shutil

NS_CONTENT = "urn:xmind:xmap:xmlns:content:2.0"

CATEGORY_ORDER = ['list', 'add', 'edit', 'delete', 'describe', 'other']
CATEGORY_TEMPLATES = {
    'list': '{module} 列表',
    'add': '新增 {module}',
    'edit': '编辑 {module}',
    'delete': '删除 {module}',
    'describe': '{module} 详情',
    'other': '{module} 其它',
}


def extract_h1_title(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
    return os.path.splitext(os.path.basename(filepath))[0]


def extract_module_name(file_title):
    """从标题如 'Region 成员 - 测试用例' 中提取模块名 'Region 成员'。"""
    m = re.search(r'(.+?)(?:\s*-\s*测试用例|\s+测试用例)\s*$', file_title)
    if m:
        return m.group(1).strip()
    return file_title.strip()


def classify_case(title):
    """根据用例标题判断 CRUD 类别。"""
    # 优先级：删除 > 编辑 > 新增 > 详情 > 列表 > 其它
    if any(k in title for k in ['删除', '移除']):
        return 'delete'
    if any(k in title for k in ['编辑', '修改']):
        return 'edit'
    if any(k in title for k in ['创建', '新增', '邀请', '注册']):
        return 'add'
    if '详情' in title:
        return 'describe'
    if any(k in title for k in ['列表', '搜索', '分页', '排序', '刷新', '空状态', '查询']):
        return 'list'
    return 'other'


def parse_directory(input_dir):
    """Return list of {file_title, module_name, categories} for each markdown file."""
    results = []
    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith('.md'):
            continue
        filepath = os.path.join(input_dir, fname)
        modules = parse_md(filepath)
        if not modules:
            continue

        file_title = extract_h1_title(filepath)
        module_name = extract_module_name(file_title)

        # 按 CRUD 类别聚合用例
        categories = {cat: [] for cat in CATEGORY_ORDER}
        for mod in modules:
            for case in mod['cases']:
                cat = classify_case(case['title'])
                categories[cat].append(case)

        results.append({
            'file_title': file_title,
            'module_name': module_name,
            'categories': categories,
        })
    return results


def build_case_topic(case):
    """Build XMind topic for a single test case."""
    case_children = []

    if case['pc']:
        case_children.append(_topic(f"pc：{case['pc']}"))

    steps = case['steps']
    exps = case['expected_groups']
    for i, step in enumerate(steps, 1):
        if i <= len(exps):
            exp_items = exps[i - 1]
            combined = '\n'.join(exp_items) if len(exp_items) > 1 else exp_items[0]
            case_children.append(_topic(step, children=[_topic(combined)]))
        else:
            case_children.append(_topic(step))

    if len(exps) > len(steps):
        for exp_group in exps[len(steps):]:
            combined = '；'.join(exp_group)
            case_children.append(_topic(f"预期：{combined}"))

    return _topic(case['title'], children=case_children)


def generate_combined_xmind(output_path, feature, version, files_data):
    """Generate one XMind regrouped by CRUD category per feature module."""
    file_topics = []
    total_cases = 0

    for fdata in files_data:
        category_topics = []
        for cat in CATEGORY_ORDER:
            cases = fdata['categories'].get(cat, [])
            if not cases:
                continue
            cat_title = CATEGORY_TEMPLATES[cat].format(module=fdata['module_name'])
            case_topics = [build_case_topic(case) for case in cases]
            category_topics.append(_topic(cat_title, children=case_topics))
            total_cases += len(cases)

        if category_topics:
            file_topics.append(_topic(fdata['module_name'], children=category_topics))

    sheet_id = _id("sheet")
    root_id = _id("root")
    ts = str(int(datetime.now().timestamp() * 1000))

    root_topic = _topic(f"{feature} - {version}", children=file_topics, tid=root_id)

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

    print(f"✅ XMind generated: {output_path}")
    print(f"   Feature: {feature} ({version})")
    print(f"   Total test cases: {total_cases}")
    for fdata in files_data:
        cat_counts = []
        for cat in CATEGORY_ORDER:
            count = len(fdata['categories'].get(cat, []))
            if count:
                cat_counts.append(f"{CATEGORY_TEMPLATES[cat].format(module=fdata['module_name'])}:{count}")
        print(f"     - {fdata['module_name']} -> {' | '.join(cat_counts)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate a combined CRUD-grouped XMind from markdown test cases")
    parser.add_argument("input", help="Path to directory containing markdown test case files")
    parser.add_argument("--output", "-o", default=None, help="Output xmind path")
    parser.add_argument("--feature", default=None, help="Feature name (default: directory name)")
    parser.add_argument("--version", default="4.x", help="Version")
    args = parser.parse_args()

    input_dir = args.input.rstrip('/').rstrip('\\')
    if not os.path.isdir(input_dir):
        print(f"Input is not a directory: {input_dir}")
        sys.exit(1)

    feature = args.feature or os.path.basename(input_dir)
    output = args.output or os.path.join(input_dir, f"{feature}-testcase.xmind")

    files_data = parse_directory(input_dir)
    if not files_data:
        print("No valid test case files found.")
        sys.exit(1)

    generate_combined_xmind(output, feature, args.version, files_data)
