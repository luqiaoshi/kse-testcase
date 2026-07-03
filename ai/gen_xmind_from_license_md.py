#!/usr/bin/env python3
"""Generate XMind from the License test case markdown file.

Structure:
  Test Case
    ├─ pc：xxx (if any)
    ├─ 1. step
    │   └─ expected result (sub-items as children)
    ├─ 2. step
    │   └─ expected result
    └─ ...
"""

import re, os, sys, tempfile, zipfile, shutil, hashlib
from xml.sax.saxutils import escape
from datetime import datetime

NS_CONTENT = "urn:xmind:xmap:xmlns:content:2.0"


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

    # Split by major sections (## 模块 or 专项 sections)
    module_blocks = re.split(r'\n(?=## (?:模块|国际化|API|老版本|汇总))', content)

    modules = []
    for mblock in module_blocks:
        mblock = mblock.strip()
        if not any(mblock.startswith(prefix) for prefix in ['## 模块', '## 国际化', '## API', '## 老版本']):
            continue
        if '### tc-' not in mblock:
            continue

        name_m = re.search(r'## (.+?)(?:\n|$)', mblock)
        if not name_m:
            continue
        module_name = name_m.group(1).strip()

        # Split by test cases
        case_blocks = re.split(r'\n(?=### tc-)', mblock)
        cases = []
        for cblock in case_blocks:
            cblock = cblock.strip()
            if not cblock.startswith('### tc-'):
                continue

            title_m = re.search(r'### (tc-.+?)(?:\n|$)', cblock)
            title = title_m.group(1).strip() if title_m else 'testcase'

            # Extract precondition
            pc_m = re.search(r'前置条件 \(pc\)\n(.+?)(?=\n#### |\n---|\Z)', cblock, re.DOTALL)
            pc = None
            if pc_m:
                raw = pc_m.group(1).strip()
                # Take all - lines and join
                pc_items = [l.strip().lstrip('- ').strip() for l in raw.split('\n') if l.strip()]
                pc = '；'.join(pc_items) if pc_items else None

            # Extract steps
            steps_section = re.search(r'#### 测试步骤\n(.+?)(?=\n#### |\n---|\Z)', cblock, re.DOTALL)
            step_lines = []
            if steps_section:
                raw = steps_section.group(1).strip()
                for line in raw.split('\n'):
                    line = line.strip()
                    m = re.match(r'\d+\.\s*(.+)', line)
                    if m:
                        step_lines.append(m.group(1).strip())

            # Extract expected results - group by top-level - items
            expected_section = re.search(r'#### 预期结果\n(.+?)(?=\n#### |\n---|\Z)', cblock, re.DOTALL)
            expected_groups = []  # list of lists: each inner list is one expected group with sub-items
            if expected_section:
                raw = expected_section.group(1)
                current_group = []
                for line in raw.split('\n'):
                    if not line.strip():
                        continue
                    # A new group starts with '- ' at the beginning (no leading indent)
                    if line.startswith('- '):
                        if current_group:
                            expected_groups.append(current_group)
                        current_group = [line.strip().lstrip('- ').strip()]
                    else:
                        # Continuation of previous group (indented), i.e. sub-items
                        stripped = line.strip()
                        if stripped:
                            current_group.append(stripped)
                if current_group:
                    expected_groups.append(current_group)

            cases.append({
                'title': title,
                'pc': pc,
                'steps': step_lines,
                'expected_groups': expected_groups
            })

        if cases:
            modules.append({
                'name': module_name,
                'cases': cases
            })

    return modules


def generate_xmind(output_path, feature, version, modules):
    sheet_id = _id("sheet")
    root_id = _id("root")
    ts = str(int(datetime.now().timestamp() * 1000))

    module_topics = []
    for mod in modules:
        case_topics = []
        for case in mod['cases']:
            case_children = []

            # Precondition
            if case['pc']:
                case_children.append(_topic(f"pc：{case['pc']}"))

            # Pair steps with expected groups by index
            steps = case['steps']
            exps = case['expected_groups']

            for i, step in enumerate(steps, 1):
                step_text = step  # 序号由 XMind 树结构体现，不再前缀
                if i <= len(exps):
                    # This step has a corresponding expected group
                    exp_items = exps[i - 1]
                    if len(exp_items) == 1:
                        # Single expected item
                        case_children.append(
                            _topic(step_text, children=[_topic(exp_items[0])])
                        )
                    else:
                        # Multiple sub-items: concatenate into one expected node
                        combined = '\n'.join(exp_items)
                        case_children.append(
                            _topic(step_text, children=[_topic(combined)])
                        )
                else:
                    # No expected result for this step
                    case_children.append(_topic(step_text))

            # Extra expected groups that don't correspond to steps (shouldn't happen normally)
            if len(exps) > len(steps):
                remaining = exps[len(steps):]
                for exp_group in remaining:
                    combined = '；'.join(exp_group)
                    case_children.append(_topic(f"预期：{combined}"))

            case_topics.append(_topic(case['title'], children=case_children))

        module_topics.append(_topic(mod['name'], children=case_topics))

    root_topic = _topic(f"{feature} - {version}", children=module_topics, tid=root_id)

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

    total_cases = sum(len(mod['cases']) for mod in modules)
    print(f"✅ XMind generated: {output_path}")
    print(f"   Feature: {feature} ({version})")
    print(f"   Total test cases: {total_cases}")
    for mod in modules:
        print(f"     - {mod['name']}: {len(mod['cases'])} cases")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate XMind from License test case markdown")
    parser.add_argument("input", help="Path to the markdown test case file")
    parser.add_argument("--output", "-o", default=None, help="Output xmind path")
    parser.add_argument("--feature", default="License优化", help="Feature name")
    parser.add_argument("--version", default="4.2.1", help="Version")
    args = parser.parse_args()

    modules = parse_md(args.input)
    if not modules:
        print("No test cases found.")
        sys.exit(1)

    output = args.output or os.path.join(
        os.path.dirname(args.input),
        f"{args.feature}-testcase.xmind"
    )
    generate_xmind(output, args.feature, args.version, modules)