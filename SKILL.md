---
name: clay-jev-people-ranker
description: Find and rank people with the official Clay CLI and TypeSafe JEV. Use for B2B lead scoring, prospect qualification, ICP ranking, enrichment gating, or false-positive job-title filtering where typed probabilities should control downstream GTM workflows; the bundled example targets current operating founders.
---

# Clay + JEV People Ranker

Use the official Clay CLI for database search and TypeSafe JEV for semantic qualification. Do not substitute QMD, web search, or an unofficial Clay integration for Clay database searches.

## Install this skill

This package uses the portable Agent Skills `SKILL.md` layout. For Claude Code, Cursor, Grok Build, or Grok Bot setup, read [references/platform-installation.md](references/platform-installation.md). Local coding agents can install it with:

```bash
python install_skill.py --agent claude-code --scope user
python install_skill.py --agent cursor --scope user
python install_skill.py --agent grok-build --scope user
```

Use `--agent all` to install all three local-agent copies. Grok Bot uses the supported private-skill conversation flow described in the platform reference.

## Install the official dependencies

Follow the maintained upstream instructions rather than copying either vendor's code into this skill.

- TypeSafe agent skill: [typesafe-ai/skills](https://github.com/typesafe-ai/skills)
  - Claude Code: `claude plugin marketplace add typesafe-ai/skills`, then `claude plugin install typesafe@typesafe-ai`.
  - Cursor, Grok Build, Codex, and other Agent Skills clients: `npx skills add typesafe-ai/skills --skill typesafe-ai`, then select the agent. Add `-g` only when a global installation is wanted.
- Clay plugin and CLI: [clay-run/agent-plugins](https://github.com/clay-run/agent-plugins) and its [getting-started guide](https://github.com/clay-run/agent-plugins/blob/main/GETTING_STARTED.md).
  - Codex: `codex plugin marketplace add clay-run/agent-plugins`, install `clay` from Plugins, then run the bundled `clay:setup` skill.
  - Claude Code: `/plugin marketplace add clay-run/agent-plugins`, `/plugin install clay@clay-plugins`, then run `clay:setup`.
  - Cursor: follow the repository's Cursor setup and then run the bundled setup skill.
  - Grok Build or Grok Bot: use the repository's `clay/skills/setup/SKILL.md` as the installation runbook on the agent's computer; Clay does not document a Grok-specific marketplace command.

Verify authentication with `clay whoami`. Run `clay login` only when the official setup flow requires it. The CLI resolves the active workspace from its authenticated session; never request, pass, print, or embed a workspace ID.

Install the Python dependencies from this skill directory:

```bash
python -m pip install -r scripts/requirements.txt
```

Set the TypeSafe credential outside the skill:

```text
TYPESAFE_API_KEY=replace-with-your-key
```

Copy `env.example` to `.env` if a local environment file is preferred.

Never place a real key in the skill, command history, source control, examples, or output files.

## Run the workflow

1. Translate the user's hard filters into a Clay Query Mode people query. Keep facts Clay can filter deterministically—location, company size, industry, and title—in that query.
2. Use JEV for the semantic judgment: whether the matched current experience is truly an operating Founder or Co-Founder role rather than investing, advising, board membership, a founding-employee title, or founder support.
3. Run the bundled script. It pages the same forward-only Clay search until the target is reached, Clay is exhausted, the candidate cap is reached, or the quota safeguard stops it.

```bash
python scripts/rank_clay_people.py \
  --query '<Clay Query Mode people query>' \
  --target-qualified 500 \
  --current-founder-threshold 0.90 \
  --operating-founder-threshold 0.80
```

Use `--search-id <id>` to continue an existing search instead of creating one. Use `clay searches query-mode --help` when the live CLI syntax or output shape needs confirmation.

The default query is only an example profile: US-based current founders at Software Development companies in Clay's `51-200` and `201-500` size buckets. Those buckets over-include the requested 50-250 range. Clay's missing B2B classification is retained by the example query, so a selected lead with missing classification is not independently verified B2B.

## Interpret the output

The script writes timestamped JSON and CSV files to `outputs/`. It deliberately drops Clay workspace metadata and sends only matched title/date evidence—not names, profile URLs, or Clay IDs—to JEV. The local ranked files still contain the selected people's contact-identifying fields because they are the usable search result; never add generated outputs to a shared skill archive.

Treat thresholds as operating policies, not measured accuracy. Validate precision and recall on a human-labeled sample before claiming that a `0.90` Noul threshold produces 90% accurate leads. Report:

- Clay candidates consumed and JEV-qualified results.
- Qualification yield and whether the target was reached.
- JEV input/output tokens and elapsed time.
- Clay exhaustion or quota-safeguard conditions.
- The semantic criteria and thresholds used.

Do not spend additional Clay quota after the requested target is reached. Before a page that could leave less than 15% of the reported period quota, stop and obtain confirmation.
