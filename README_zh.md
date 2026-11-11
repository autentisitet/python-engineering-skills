# python-engineering-skills

[English](README.md) | [中文](README_zh.md)

[![CI](https://github.com/autentisitet/python-engineering-skills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/autentisitet/python-engineering-skills/actions/workflows/ci.yml)
[![Codex Skills](https://img.shields.io/badge/Codex-Skills-000000?logo=openai&logoColor=white)](https://developers.openai.com/codex/skills/)
[![Anthropic Agent Skills](https://img.shields.io/badge/Anthropic-Agent_Skills-D97757?logo=anthropic&logoColor=white)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
[![Skill Evals](https://img.shields.io/badge/Anthropic-Skill_Evals-D97757?logo=anthropic&logoColor=white)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

一组面向中大型 Python 仓库的 Codex skills。它们将重复出现的工程决策转化为可复用的审查标准，
提高 Agent 代码修改的可靠性，并力图显著降低程序员 code review 的心智负担。

## Skills

| Skill | 用途 |
| --- | --- |
| [python-domain-modeling](skills/python-domain-modeling/SKILL.md) | Python 类型、dataclass、Pydantic/settings、接口、不变量和模型拷贝语义 |
| [python-callable-caching](skills/python-callable-caching/SKILL.md) | 可调用对象归属、property、闭包、缓存、构造钩子和资源清理 |
| [python-sklearn-workflow](skills/python-sklearn-workflow/SKILL.md) | 防泄漏的数据划分、CV、预处理、搜索、诊断曲线、PCA 和 inspection |
| [python-cli-file-workflows](skills/python-cli-file-workflows/SKILL.md) | 流式文件 CLI、路径所有权、tqdm 输出和 argparse 契约 |
| [python-matplotlib-config](skills/python-matplotlib-config/SKILL.md) | 全局样式、中文字体回退、`.mplstyle` 和 Axes 优先调用 |
| [python-loguru-logging](skills/python-loguru-logging/SKILL.md) | 异常边界、上下文绑定、文件生命周期、队列日志和退出等待 |
| [python-media-processing](skills/python-media-processing/SKILL.md) | OpenCV/Pillow/Decord/PyAV 配置、库选择、抽帧和颜色空间 |
| [python-binary-buffers](skills/python-binary-buffers/SKILL.md) | `bytes`、`bytearray`、`memoryview`、二进制协议、所有权和增量 I/O |

安装后可以通过 `$python-domain-modeling` 等名称显式调用，也可以由 description 自动匹配相关任务。

---

## 安装

将本仓库作为版本化源，只把需要的 skills 链接到受信任目标项目的 `.agents/skills/`。

### Linux 与 WSL

```bash
make use TARGET=/path/to/python-project
```

Shell 脚本需要 Bash 4+ 和 GNU `find`/`readlink`。

### Windows PowerShell

```powershell
$TargetProject = Join-Path $HOME "src\python-project"
.\scripts\links\use-skills.ps1 `
  -Target $TargetProject `
  -Skills python-domain-modeling,python-sklearn-workflow
```

PowerShell 默认创建目录 Junction，源仓库和目标项目必须保留在 Windows 可访问的本地路径中。

移除受本仓库管理的链接：

```bash
make remove TARGET=/path/to/python-project
```

```powershell
.\scripts\links\remove-skills.ps1 -Target $TargetProject
```

移除脚本会保留普通目录以及不由本仓库管理的链接。

---

## 更新

符号链接和 Junction 安装会直接使用本仓库作为源。更新仓库后先审查修改、运行验证，再在目标项目中
开启新的 Agent 会话。

```bash
git pull
make validate
```

---

## 目录

```text
python-engineering-skills/
├── evals/
│   ├── train_queries.json
│   ├── validation_queries.json
│   └── results/                 # 本地生成，Git 忽略
├── scripts/
│   ├── evals/                   # 发现、真实激活和数据集验证
│   ├── links/                   # 项目级安装/移除工具
│   └── packages/                # skill package linter
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       └── references/
└── tests/
```

---

## 验证

使用 Python 3.10+，并在虚拟环境中安装开发依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make validate PYTHON=.venv/bin/python
```

`make eval` 会运行 `validate` 外加一次真实的 Codex skill 发现检查，然后打印可选的模型步骤；
`make smoke` 运行廉价的每 skill 行为 smoke 测试。

Windows 安装 `requirements.txt` 后运行：

```powershell
python -m scripts.packages.lint_skill_packages --strict-warnings
python -m scripts.evals.validate_evals
python -m unittest discover -s tests -p "test_*.py"
```

CI 固定使用 Ubuntu 24.04 和 Windows Server 2025 runner。

---

## 评测

`evals/train_queries.json` 和 `evals/validation_queries.json` 包含 8 个 skills 的 160 条正负路由案例，
按 60/40 固定划分：

- 训练集：96 条，每个 skill 6 条正例、6 条负例；
- 验证集：64 条 held-out 案例，每个 skill 4 条正例、4 条负例。

不调用模型即可检查数据集：

```bash
python3 -m scripts.evals.validate_evals
```

不调用模型即可检查 Codex 的实际发现结果：

```bash
python3 -m scripts.evals.check_skill_discovery \
  --output evals/results/discovery.json
```

接受模型费用和数据传输后，只通过 Codex 运行可观察的真实激活评测：

```bash
python3 -m scripts.evals.run_activation_evals evals/train_queries.json \
  --runs 3 \
  --jobs 1 \
  --allow-model-calls \
  --output evals/results/activation-train.json
```

想降低行为 smoke 测试成本时，可以设置 `--sample-per-label N`，使每个 skill 最多运行 `N` 条正例和
`N` 条负例。数值超过现有案例数时只会使用全部可用案例，不会重复；零、负数和非整数会被拒绝。

| 结果 | 状态 |
| --- | --- |
| Codex skill 发现 | 8/8 已发现并启用 |
| 训练集基线，单次运行 | 96 条中 85 条通过、6 条失败、5 条无法判定 |
| 路由优化后的训练集，单次运行 | 96 条中 91 条通过、1 条失败、4 条无法判定 |
| 验证集回归检查 | 64 条中 61 条通过、0 条失败、3 条无法判定；仅重试无法判定项 |

“无法判定”表示运行未提供预期 skill 入口已被读取的可靠证据，与已观察到的路由不匹配分开统计。

---

## 设计约定

- **只保留重复决策。** Skill 必须能反复改变实现或审查决策；通用 Python 知识不单独建 skill。
- **路由范围明确。** Description 同时说明适用工作与相邻排除项，偶然出现关键词不足以触发。
- **渐进披露。** `SKILL.md` 保存共用约束与路由，条件细节放在直接链接的 references。
- **只为确定性操作增加脚本。** 只有可重复执行逻辑能明显提高可靠性或降低 token 成本时，才增加
  skill 自带脚本。
- **区分平台层。** `agents/openai.yaml` 是可选 Codex 元数据，不是通用 Agent Skills 必需文件。
- **权限不随 skill 扩大。** Skill 可以推荐工具或脚本，但不能授予 workspace、网络或执行权限。
- **结果边界明确。** 结构检查、路由观察和最终产物正确性分别报告。

---

## License

本项目使用 [MIT License](LICENSE)。
