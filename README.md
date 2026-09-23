一套用于生成标准化中文旅游视频文案的技能集合。
第一个技能 travel-content-skills 需要三个必填的输入参数：
旅行地点
情绪化的语气/带有情绪色彩的表达方式
目标视频时长
它生成了一份经过验证的文档 .docx ，其中包含了创意策略、标题选项、完整的故事情节、各角色的分工、语言风格说明以及时间安排。

## Repository layout

```text
.agents/skills/
  travel-content-skills/
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

## Local validation

Python 3.10 or newer is required. The skill scripts use only the Python
standard library.

```powershell
python tools\validate_repo.py
python tools\run_tests.py
```

## Use the skill

After installing the skill in Codex, use:

```text
使用 $travel-content-skills，地点是西湖、灵隐寺、龙井村，情感基调是温暖治愈，
视频总时长 90 秒，交付 DOCX。
```

The skill creates an internal JSON contract, validates locations, tone markers,
and duration, then builds the final Word document.

## Install locally in Codex

The repository version stays under `.agents/skills/`. For a personal global
installation, copy `travel-content-skills` to:

```text
%USERPROFILE%\.codex\skills\travel-content-skills
```

## License

No reuse or redistribution license is granted by default. Choose a license
before publishing this repository for public reuse.
