# 中文视频内容技能集合

一套面向中老年受众，用于策划、撰写、事实核验和打包中文视频旁白的
Codex 技能集合。

## 旅行内容技能

技能标识：`travel-content-skills`

适用于历史文化、地理文旅和生活技能的完整单集或系列项目。

旅游类单集通常提供：

- 旅行地点
- 情感基调或带情绪色彩的表达方式
- 目标视频时长

主题、内容领域和项目类型可由技能根据现有信息补全。发布平台、目标受众、
既有资料和禁用表达可另外提供。

技能会生成内部结构化校验文件，核验时间轴、朗读语速、事实与证据关系，最后
交付一个压缩包：

```text
01_可朗读正文.docx
02_项目审阅.docx
03_证据表.csv
```

## 示例

```text
使用 $travel-content-skills，地点是西湖、灵隐寺、龙井村，情感基调是温暖治愈，
视频总时长 90 秒，发布平台抖音，目标受众是第一次到杭州旅行的中老年观众。
```

## 仓库结构

```text
.agents/skills/travel-content-skills/
  SKILL.md
  agents/openai.yaml
  references/
  scripts/
  tests/
  examples/
tools/
  run_tests.py
  validate_repo.py
.github/workflows/
  validate.yml
```

## 本地校验

需要 Python 3.10 或更高版本。技能脚本仅使用 Python 标准库。

```powershell
python tools\validate_repo.py
python tools\run_tests.py
```

## 安装到 Codex

仓库内版本位于 `.agents/skills/`。个人全局安装时，将
`travel-content-skills` 复制到：

```text
%USERPROFILE%\.codex\skills\travel-content-skills
```

## 许可

默认不授予复用或再分发许可。公开复用前请先选择并添加许可证。
