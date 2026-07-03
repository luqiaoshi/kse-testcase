# KSE TestCase

KubeSphere Enterprise (KSE) 功能测试用例库，覆盖许可证管理、网络 IPPool、告警规则组等核心模块。

## 目录结构

```
kse-testcase/
├── cases/                    # 测试用例（按模块组织）
│   ├── license/              # 许可证管理（82条用例）
│   ├── network/              # 网络 IPPool（11个测试文件）
│   └── 告警规则组/             # 告警规则组（6个测试文件）
├── ai/                       # XMind 脑图生成脚本
│   ├── gen_xmind.py          # 模板生成器
│   ├── gen_xmind_md.py       # 目录扫描生成器
│   └── gen_xmind_from_license_md.py  # 自定义解析器
├── ui/                       # UI 参考截图
├── test_license_ui.js        # Playwright UI 自动化测试脚本
└── package.json
```

## 工作流

需求分析 → 用例编写 (Markdown) → 人工评审 → XMind 脑图生成 → UI 自动化测试

## 用例格式

- **标准格式**：独立「测试步骤」和「预期结果」章节
- **行内格式**：步骤与结果用 `→` 分隔
- **ID 规范**：`tc-{P0|P1|P2|P3}-{type}: {name}`

## 快速开始

```bash
npm install
node test_license_ui.js    # 运行 License UI 自动化测试
```

## 生成 XMind 脑图

```bash
python3 ai/gen_xmind_md.py --dir cases/{模块名}
```