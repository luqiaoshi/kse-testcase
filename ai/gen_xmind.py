#!/usr/bin/env python3
"""Generate XMind test case files for KubeSphere Console features.

Usage:
    python3 gen_xmind.py --feature "弹性伸缩" --module "容器水平伸缩" --page "HPA" \\
        --component "ks-core" --version "4.2.1" \\
        --output /path/to/output.xmind
    
    Or with JSON input:
    python3 gen_xmind.py --json /path/to/cases.json
"""

import json
import sys
import os
import argparse
import hashlib
import shutil
import tempfile
import zipfile
from xml.sax.saxutils import escape
from datetime import datetime

# XMind 8 namespace
NS_CONTENT = "urn:xmind:xmap:xmlns:content:2.0"
NS_FO = "http://www.w3.org/1999/XSL/Format"
NS_SVG = "http://www.w3.org/2000/svg"
NS_XHTML = "http://www.w3.org/1999/xhtml"
NS_XLINK = "http://www.w3.org/1999/xlink"


def _make_id(seed=None):
    h = hashlib.sha256()
    h.update((seed or str(datetime.now().timestamp())).encode())
    return h.hexdigest()[:26]


def _xml_topic(title, children=None, topic_id=None, width=None):
    tid = topic_id or _make_id(title)
    parts = [f'<topic id="{tid}">']
    if width:
        parts.append(f'<title svg:width="{width}">{escape(title)}</title>')
    else:
        parts.append(f'<title>{escape(title)}</title>')
    if children:
        parts.append('<children>')
        parts.append('<topics type="attached">')
        for child in children:
            parts.append(child)
        parts.append('</topics>')
        parts.append('</children>')
    parts.append('</topic>')
    return '\n'.join(parts)


def _build_test_case_xml(tc):
    """Build XML for a single test case.
    
    tc format:
    {
        "id": "hpa-list-1.1",
        "category": "List",
        "name": "List fields & UI",
        "priority": "P0",
        "steps": ["step1", "step2"],
        "expected": "All columns displayed correctly",
        "precondition": "存在HPA数据（可选）"
    }
    """
    title = f"tc-{tc['priority']}-{tc.get('module', '')}-{tc['name']}"
    
    children = []
    
    # Precondition (if any)
    if tc.get('precondition'):
        pc = _xml_topic(f"pc：{tc['precondition']}")
        children.append(pc)
    
    # Steps
    for i, step in enumerate(tc.get('steps', []), 1):
        step_topic = _xml_topic(f"{i}. {step}")
        children.append(step_topic)
    
    # Expected result
    if tc.get('expected'):
        exp = _xml_topic(f"预期：{tc['expected']}")
        children.append(exp)
    
    width = 500 if len(title) > 30 else None
    return _xml_topic(title, children=children, width=width)


def _build_content_xml(feature, version, categories):
    """Build content.xml.
    
    categories: {
        "List": [tc_dict, ...],
        "Add": [...],
        "Edit": [...],
        "Describe": [...],
        "Delete": [...]
    }
    """
    sheet_id = _make_id("sheet")
    root_id = _make_id("root")
    ts = str(int(datetime.now().timestamp() * 1000))
    
    topics_xml = []
    
    for cat_name in ["List", "Add", "Edit", "Describe", "Delete"]:
        cases = categories.get(cat_name, [])
        if not cases:
            continue
        
        cat_title = {
            "List": "1. 列表查询",
            "Add": "2. 新增数据",
            "Edit": "3. 编辑数据",
            "Describe": "4. 详情查看",
            "Delete": "5. 删除数据"
        }.get(cat_name, cat_name)
        
        child_topics = [_build_test_case_xml(tc) for tc in cases]
        cat_topic = _xml_topic(cat_title, children=child_topics)
        topics_xml.append(cat_topic)
    
    root_topic = _xml_topic(
        f"{feature} - {version}",
        children=topics_xml,
        topic_id=root_id
    )
    
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-content xmlns="{NS_CONTENT}" xmlns:fo="{NS_FO}" xmlns:svg="{NS_SVG}" xmlns:xhtml="{NS_XHTML}" xmlns:xlink="{NS_XLINK}" modified-by="opencode" timestamp="{ts}" version="2.0">
<sheet id="{sheet_id}" modified-by="opencode" theme="245isfvbft4906gtq3tpf0a2ot" timestamp="{ts}">
{root_topic}
</sheet>
</xmap-content>'''


def _build_meta_xml():
    ts = str(int(datetime.now().timestamp() * 1000))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0">
<author>
<name>opencode</name>
</author>
<created>{ts}</created>
</meta>'''


def _build_manifest_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
<file-entry full-path="content.xml" media-type="text/xml"/>
<file-entry full-path="meta.xml" media-type="text/xml"/>
<file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
</manifest>'''


def generate_xmind(output_path, feature, version, categories, component="ks-core"):
    """Generate an XMind file from structured test case data."""
    
    temp_dir = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(temp_dir, "META-INF"), exist_ok=True)
        
        with open(os.path.join(temp_dir, "content.xml"), "w", encoding="utf-8") as f:
            f.write(_build_content_xml(feature, version, categories))
        
        with open(os.path.join(temp_dir, "meta.xml"), "w", encoding="utf-8") as f:
            f.write(_build_meta_xml())
        
        with open(os.path.join(temp_dir, "META-INF", "manifest.xml"), "w", encoding="utf-8") as f:
            f.write(_build_manifest_xml())
        
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(os.path.join(temp_dir, "content.xml"), "content.xml")
            zf.write(os.path.join(temp_dir, "meta.xml"), "meta.xml")
            zf.write(os.path.join(temp_dir, "META-INF", "manifest.xml"), "META-INF/manifest.xml")
    
    finally:
        shutil.rmtree(temp_dir)


def generate_cases_from_template(feature, module, page, component="ks-core", version="4.2.1"):
    """Generate standard CRUD test cases for a feature following the skill template."""
    
    categories = {}
    
    # === List ===
    categories["List"] = [
        {
            "id": f"{page}-list-1.1", "category": "List",
            "name": "列表字段及UI校验", "priority": "P0",
            "steps": [f"进入{module}列表页面", "确认列表展示的字段名称和UI布局"],
            "expected": f"列表字段及UI显示正确，与原型一致",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-list-1.2", "category": "List",
            "name": "新增后列表同步显示", "priority": "P0",
            "steps": [f"新增{module}数据", "返回列表页面，确认新增数据显示在列表中"],
            "expected": f"新增数据正确显示在列表第一页/末页",
            "precondition": None
        },
        {
            "id": f"{page}-list-1.3", "category": "List",
            "name": "编辑后列表同步更新", "priority": "P0",
            "steps": ["编辑已存在的{module}数据", "返回列表页面，确认数据已更新"],
            "expected": "列表显示编辑后的最新数据",
            "precondition": "存在{module}数据"
        },
        {
            "id": f"{page}-list-1.4", "category": "List",
            "name": "删除后列表同步移除", "priority": "P0",
            "steps": [f"删除{module}数据", "返回列表页面，确认数据已移除"],
            "expected": "被删除数据不在列表中展示",
            "precondition": "存在{module}数据"
        },
        {
            "id": f"{page}-list-1.5", "category": "List",
            "name": "查询功能校验", "priority": "P1",
            "steps": [
                "使用模糊查询：输入部分字段关键词，确认过滤结果",
                "使用精确查询：输出完整匹配条件，确认精确命中",
                "输入特殊字符：@#$%^&*等，确认处理正常",
                "输入不存在的条件，确认空数据展示状态",
                "组合多个查询条件，确认结果交集正确"
            ],
            "expected": "模糊/精确查询正常，特殊字符不报错，无数据时显示友好的空状态提示",
            "precondition": "存在{module}数据"
        },
        {
            "id": f"{page}-list-1.6", "category": "List",
            "name": "排序功能校验", "priority": "P1",
            "steps": [
                "点击可排序字段标题，确认按升序排列",
                "再次点击，确认按降序排列",
                "如支持自定义列展示，确认可正常显示/隐藏字段"
            ],
            "expected": "排序功能正常，升序/降序切换正确",
            "precondition": "存在多条{module}数据"
        },
        {
            "id": f"{page}-list-1.7", "category": "List",
            "name": "翻页功能校验", "priority": "P1",
            "steps": [
                "上/下一页翻页，确认数据正确切换",
                "快速跳转至指定页码，确认跳转正确",
                "携带查询条件翻页，确认查询条件保留"
            ],
            "expected": "翻页正常，查询条件翻页后保留",
            "precondition": "存在多页{module}数据"
        },
        {
            "id": f"{page}-list-1.8", "category": "List",
            "name": "中英文切换校验", "priority": "P1",
            "steps": ["切换系统语言为中文，确认列表字段显示中文", "切换系统语言为English，确认列表字段显示英文"],
            "expected": "中英文切换后列表字段文案正确展示",
            "precondition": None
        },
        {
            "id": f"{page}-list-1.9", "category": "List",
            "name": "权限校验", "priority": "P3",
            "steps": [
                "使用集群管理员角色登录，确认可访问列表",
                "使用企业空间普通用户角色登录，确认权限控制正确",
                "使用无权限用户登录，确认页面提示无权限"
            ],
            "expected": "不同角色用户访问列表权限控制正确",
            "precondition": "准备不同角色的测试用户"
        },
        {
            "id": f"{page}-list-1.10", "category": "List",
            "name": "接口权限校验", "priority": "P3",
            "steps": ["使用无权限用户的token，直接调用列表查询API", "确认API返回403或适当的错误码"],
            "expected": "无权限用户调用API返回403",
            "precondition": "获取无权限用户的token"
        },
        {
            "id": f"{page}-list-1.11", "category": "List",
            "name": "越权访问校验", "priority": "P3",
            "steps": ["低权限用户直接在浏览器地址栏输入列表URL", "确认页面被拦截或提示无权限"],
            "expected": "越权访问被正确处理",
            "precondition": "准备低权限用户"
        },
    ]
    
    # === Add ===
    categories["Add"] = [
        {
            "id": f"{page}-add-2.1", "category": "Add",
            "name": "仅输入必填项新增", "priority": "P0",
            "steps": [f"点击新增{module}按钮", "仅填写必填字段（如名称）", "提交保存"],
            "expected": f"{module}新增成功，列表显示新增数据",
            "precondition": None
        },
        {
            "id": f"{page}-add-2.2", "category": "Add",
            "name": "输入全部字段新增", "priority": "P0",
            "steps": [f"点击新增{module}按钮", "填写所有字段", "提交保存"],
            "expected": f"{module}新增成功，所有字段保存正确",
            "precondition": None
        },
        {
            "id": f"{page}-add-2.3", "category": "Add",
            "name": "数据重复性校验", "priority": "P1",
            "steps": [f"新增{module}，名称填写已存在的名称", "提交保存", "确认是否提示重复"],
            "expected": "提示资源名不可重复，创建失败",
            "precondition": f"已存在同名{module}"
        },
        {
            "id": f"{page}-add-2.4", "category": "Add",
            "name": "删除后重新添加同名数据", "priority": "P2",
            "steps": [f"新增{module}，填写名称A", f"删除名称为A的{module}", f"重新添加名称为A的{module}"],
            "expected": "删除后同名数据可以正常创建",
            "precondition": None
        },
        {
            "id": f"{page}-add-2.5", "category": "Add",
            "name": "各字段格式及长度校验", "priority": "P1",
            "steps": [
                "名称超长输入，确认是否校验",
                "特殊字符输入，确认是否允许",
                "各字段输入边界值（最大/最小值）"
            ],
            "expected": "字段格式和长度校验正确，提示信息准确",
            "precondition": None
        },
        {
            "id": f"{page}-add-2.6", "category": "Add",
            "name": "中英文切换校验", "priority": "P1",
            "steps": ["切换中文，确认新增界面文案正确", "切换English，确认新增界面文案正确"],
            "expected": "新增页面中英文切换正常",
            "precondition": None
        },
        {
            "id": f"{page}-add-2.7", "category": "Add",
            "name": "权限校验", "priority": "P3",
            "steps": ["使用无权限用户，确认新增按钮不可见/置灰", "使用有权限用户，确认可正常新增"],
            "expected": "不同角色用户新增权限控制正确",
            "precondition": "准备不同角色的测试用户"
        },
        {
            "id": f"{page}-add-2.8", "category": "Add",
            "name": "接口权限校验", "priority": "P3",
            "steps": ["使用无权限用户的token，直接调用新增API"],
            "expected": "无权限用户调用新增API返回403",
            "precondition": "获取无权限用户的token"
        },
    ]
    
    # === Edit ===
    categories["Edit"] = [
        {
            "id": f"{page}-edit-3.1", "category": "Edit",
            "name": "修改数据正常保存", "priority": "P0",
            "steps": [f"编辑{module}数据，修改部分字段", "保存并确认"],
            "expected": "修改保存成功，列表显示更新后的数据",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-edit-3.2", "category": "Edit",
            "name": "编辑界面数据回显", "priority": "P1",
            "steps": [f"点击编辑{module}数据", "确认编辑界面各字段值正确回显为当前值"],
            "expected": "编辑界面数据回显正确，与实际数据一致",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-edit-3.3", "category": "Edit",
            "name": "各字段格式及长度校验", "priority": "P1",
            "steps": [
                "编辑时输入超长内容，确认校验",
                "编辑时输入非法格式，确认校验"
            ],
            "expected": "编辑时字段格式和长度校验正确",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-edit-3.4", "category": "Edit",
            "name": "中英文切换校验", "priority": "P1",
            "steps": ["切换中文，确认编辑界面文案正确", "切换English，确认编辑界面文案正确"],
            "expected": "编辑页面中英文切换正常",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-edit-3.5", "category": "Edit",
            "name": "权限校验", "priority": "P3",
            "steps": ["使用无权限用户，确认编辑按钮不可见/不可点击", "使用有权限用户，确认可正常编辑"],
            "expected": "不同角色用户编辑权限控制正确",
            "precondition": "准备不同角色的测试用户"
        },
        {
            "id": f"{page}-edit-3.6", "category": "Edit",
            "name": "接口权限校验", "priority": "P3",
            "steps": ["使用无权限用户的token，直接调用编辑API"],
            "expected": "无权限用户调用编辑API返回403",
            "precondition": "获取无权限用户的token"
        },
    ]
    
    # === Describe ===
    categories["Describe"] = [
        {
            "id": f"{page}-desc-4.1", "category": "Describe",
            "name": "数据详情属性校验", "priority": "P0",
            "steps": [
                f"点击{module}名称/详情按钮",
                "确认基础信息字段展示正确",
                "确认关联资源信息展示正确"
            ],
            "expected": "详情页面信息展示完整、正确",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-desc-4.2", "category": "Describe",
            "name": "中英文切换校验", "priority": "P1",
            "steps": ["切换中文，确认详情界面文案正确", "切换English，确认详情界面文案正确"],
            "expected": "详情页面中英文切换正常",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-desc-4.3", "category": "Describe",
            "name": "权限校验", "priority": "P3",
            "steps": ["使用集群管理员角色查看详情", "使用企业空间普通用户角色查看详情"],
            "expected": "不同角色用户查看详情权限控制正确",
            "precondition": "准备不同角色的测试用户"
        },
        {
            "id": f"{page}-desc-4.4", "category": "Describe",
            "name": "接口权限校验", "priority": "P3",
            "steps": ["使用无权限用户的token，直接调用详情API"],
            "expected": "无权限用户调用详情API返回403",
            "precondition": "获取无权限用户的token"
        },
    ]
    
    # === Delete ===
    categories["Delete"] = [
        {
            "id": f"{page}-del-5.1", "category": "Delete",
            "name": "单个删除", "priority": "P0",
            "steps": [f"选择一个{module}数据，点击删除", "确认删除", "确认数据从列表移除"],
            "expected": "单个删除成功",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-del-5.2", "category": "Delete",
            "name": "批量删除", "priority": "P1",
            "steps": [f"勾选多个{module}数据，点击批量删除", "确认删除", "确认所有选中数据从列表移除"],
            "expected": "批量删除成功，所有选中数据被清除",
            "precondition": f"存在多条{module}数据"
        },
        {
            "id": f"{page}-del-5.3", "category": "Delete",
            "name": "存在关联数据时的级联删除", "priority": "P2",
            "steps": [
                f"选择一个存在关联资源的{module}",
                "点击删除，确认是否提示关联数据",
                "确认是否支持级联删除"
            ],
            "expected": "有关联数据时提示用户，级联删除行为符合预期",
            "precondition": f"{module}存在关联资源"
        },
        {
            "id": f"{page}-del-5.4", "category": "Delete",
            "name": "中英文切换校验", "priority": "P1",
            "steps": ["切换中文，确认删除对话框文案正确", "切换English，确认删除对话框文案正确"],
            "expected": "删除流程中英文切换正常",
            "precondition": f"存在{module}数据"
        },
        {
            "id": f"{page}-del-5.5", "category": "Delete",
            "name": "权限校验", "priority": "P3",
            "steps": ["使用无权限用户，确认删除按钮不可见/不可点击", "使用有权限用户，确认可正常删除"],
            "expected": "不同角色用户删除权限控制正确",
            "precondition": "准备不同角色的测试用户"
        },
        {
            "id": f"{page}-del-5.6", "category": "Delete",
            "name": "接口权限校验", "priority": "P3",
            "steps": ["使用无权限用户的token，直接调用删除API"],
            "expected": "无权限用户调用删除API返回403",
            "precondition": "获取无权限用户的token"
        },
    ]
    
    return feature, categories


def main():
    parser = argparse.ArgumentParser(description="Generate KubeSphere test case XMind files")
    parser.add_argument("--feature", default="示例功能", help="Feature name (e.g. 弹性伸缩)")
    parser.add_argument("--module", default="示例", help="Module name (e.g. 容器水平伸缩)")
    parser.add_argument("--page", default="example", help="Page name for ID (e.g. hpa)")
    parser.add_argument("--component", default="ks-core", help="Component (ks-core or extension name)")
    parser.add_argument("--version", default="4.2.1", help="KubeSphere version")
    parser.add_argument("--output", "-o", default=None, help="Output xmind path")
    parser.add_argument("--json", help="JSON file with custom test cases")
    
    args = parser.parse_args()
    
    if args.json:
        with open(args.json, "r", encoding="utf-8") as f:
            data = json.load(f)
        feature = data.get("feature", args.feature)
        version = data.get("version", args.version)
        categories = data.get("categories", {})
    else:
        feature, categories = generate_cases_from_template(
            args.feature, args.module, args.page,
            args.component, args.version
        )
    
    if args.output:
        output = args.output
    else:
        safe_name = args.feature.replace("/", "-")
        output = f"{safe_name}-testcase.xmind"
    
    generate_xmind(output, feature, args.version, categories, args.component)
    print(f"✅ XMind generated: {output}")
    print(f"   Feature: {feature} ({args.version})")
    total = sum(len(cases) for cases in categories.values())
    print(f"   Total test cases: {total}")
    for cat, cases in categories.items():
        print(f"     - {cat}: {len(cases)} cases")


if __name__ == "__main__":
    main()