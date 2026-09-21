# Platform installation

The package is a portable Agent Skill: keep the directory name `clay-jev-people-ranker` and preserve `SKILL.md`, `scripts/`, and `references/` together.

## Automatic local installation

From the extracted package directory:

```bash
python install_skill.py --agent claude-code --scope user
python install_skill.py --agent cursor --scope user
python install_skill.py --agent grok-build --scope user
```

Use `--agent all` for all local agents. Use `--scope project --project-root <path>` to install into one repository instead of the current user's configuration. Existing destinations are not modified unless `--force` is explicitly passed.

## Claude Code

Manual locations:

- Project: `.claude/skills/clay-jev-people-ranker/`
- User: `~/.claude/skills/clay-jev-people-ranker/`

Restart Claude Code if the skill does not appear, then invoke `/clay-jev-people-ranker` or ask Claude to use it.

## Cursor

Manual locations:

- Project: `.cursor/skills/clay-jev-people-ranker/`
- User: `~/.cursor/skills/clay-jev-people-ranker/`

Cursor also discovers project skills under `.agents/skills/` and compatible Claude/Codex skill directories. Open Customize → Skills to confirm discovery, then invoke `/clay-jev-people-ranker` or let Agent select it automatically.

## Grok Build

Manual locations:

- Project: `.grok/skills/clay-jev-people-ranker/`
- User: `~/.grok/skills/clay-jev-people-ranker/`

Run `grok inspect` to confirm discovery. Grok Build also reads Claude Code skills, so an existing `.claude/skills/` installation can be reused without duplication.

## Grok Bot

Grok Bot manages reusable workflows as private skills rather than discovering a local `.grok/skills/` directory. Attach this extracted skill folder or ZIP to a one-to-one Bot conversation and send:

```text
Create a private skill named "Clay + JEV People Ranker" from the attached package.
Use SKILL.md as the instructions and keep scripts/rank_clay_people.py,
scripts/requirements.txt, and env.example as skill resources. Preserve the quota
safeguard and approval boundary. Never store or repeat credentials, workspace IDs,
or generated lead files in the skill. Before the first live run, follow the linked
official TypeSafe and Clay setup instructions, ask me to complete interactive login
when required, and validate the workflow on a small safe sample.
```

After Grok Bot creates it, confirm it appears under Marketplace → Your plugins → Manage plugins and skills → Private skills. Invoke it from the desktop composer with `/`.

The Bot's computer must have Python, the Python dependencies, the official Clay CLI, a valid Clay login, and `TYPESAFE_API_KEY` configured privately. Do not paste credentials into the conversation or skill text.
