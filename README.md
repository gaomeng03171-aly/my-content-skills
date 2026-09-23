# Travel Content Skills

A Codex Skill collection for producing standardized Chinese travel-video copy.

The first skill, `travel-content-skills`, accepts three required inputs:

- travel locations
- emotional tone
- target video duration

It produces a validated `.docx` containing the creative strategy, title options,
the complete narration, location roles, tone markers, and a duration plan.

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
