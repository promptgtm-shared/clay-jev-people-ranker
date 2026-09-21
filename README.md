# TypeSafe JEV Lead Scoring with Clay CLI

An Agent Skill and Python workflow for **Clay lead scoring**, **B2B prospect qualification**, and **AI-powered people search ranking** with **TypeSafe JEV**.

## Quick answer

This project uses the official Clay CLI to retrieve people who match deterministic filters such as job title, company size, industry, seniority, and location. It then uses TypeSafe JEV to make the harder semantic decision: does each person actually match the intended role and qualification criteria?

The included JEV use case targets current operating Founders and Co-Founders. It filters false positives such as founding investors, founding employees, former founders, and people working in a Founder's Office before downstream enrichment.

The workflow is designed for GTM engineers, RevOps teams, sales operations, CROs, BDMs, SDRs, recruiters, and developers building programmable lead-qualification systems.

## What is JEV?

JEV is TypeSafe AI's first public System One model. Instead of generating long-form text, it returns typed decisions and probabilities that software can evaluate directly.

This workflow uses two TypeSafe primitives:

- **Choice** classifies the candidate as an operating founder, investor or board member, founding employee, founder-support role, or unclear.
- **Noul** estimates whether the candidate clearly and currently holds an operating Founder or Co-Founder role.

Code then applies explicit thresholds to those outputs. This makes JEV useful as a fast decision layer for classification, routing, scoring, verification, filtering, and reranking—not as a replacement for generative writing or multi-step reasoning.

Official background:

- [Introducing System One Models and JEV](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [TypeSafe use-case map](https://docs.typesafe.ai/concepts/use-case-map)
- [Choice primitive](https://docs.typesafe.ai/primitives/choice)
- [Noul primitive](https://docs.typesafe.ai/primitives/noul)

## JEV use case: Clay lead scoring and qualification

Clay is strong at hard filters. A Clay people search can narrow a market by title, geography, company size, industry, seniority, experience, and other supported fields.

The remaining problem is semantic ambiguity. A broad search for `founder` can also match titles such as:

- Founding Investor
- Founding Employee
- Founder's Office
- Executive Assistant to Founder
- Former Founder

The workflow separates the jobs:

```text
Clay Query Mode
  -> apply deterministic people and company filters
  -> return broad candidate pages
  -> JEV Choice + Noul qualification
  -> apply probability thresholds in Python
  -> export qualified people to JSON and CSV
  -> enrich only the selected rows
```

This is a practical TypeSafe AI use case for GTM automation: Clay retrieves the market, JEV judges ambiguous fit, and Python controls the policy.

## Measured founder-ranking test

The September 21, 2026 test targeted 500 US-based Founders or Co-Founders at Software Development companies using Clay's available company-size buckets.

| Metric | Result |
|---|---:|
| Clay candidates evaluated | 577 |
| JEV-qualified candidates | 472 |
| Candidates rejected before enrichment | 105 |
| Qualification yield | 81.8% |
| Current-founder threshold | 0.90 |
| Operating-founder threshold | 0.80 |
| JEV scoring time from cached Clay data | 20.115 seconds |
| JEV input tokens | 490,395 |
| JEV output tokens | 53,648 |
| Estimated JEV input charge | $0.0206 |

The target was 500 qualified people. The test stopped at 472 after a Clay continuation request returned HTTP 504. The two saved Clay pages had already returned 500 and 77 candidates successfully, and the JEV scoring stage completed for all 577.

The 0.90 Noul threshold is an operating policy, not proof of 90% precision. Production use requires a human-labeled evaluation set.

## Where the savings come from

JEV rejected 105 of 577 candidates before downstream processing. That reduced the number of rows entering later enrichment or outreach steps by **18.2%**.

Running one AI qualification prompt per candidate inside Clay would also use 577 Clay Actions plus the selected model's Data Credits. At the fixed content-generation rates published during the test, 577 rows would consume:

| Clay model | Data Credits for 577 rows |
|---|---:|
| GPT-5 Nano | 115.4 |
| GPT-5 Mini | 230.8 |
| GPT-4o or GPT-4.1 | 577 |
| Claude 4.5 Sonnet | 865.5 |

The JEV input-cost estimate uses TypeSafe's published rate of $42 per billion input tokens. Pricing changes over time, so verify the current [TypeSafe pricing](https://typesafe.ai/) and [Clay AI pricing](https://university.clay.com/docs/ai-pricing) before making a purchasing decision.

This comparison does not imply that JEV replaces Clay. The workflow still consumes Clay search-result quota and requires Clay for data retrieval. The savings depend on which Clay AI and enrichment steps would otherwise run.

## Other TypeSafe JEV use cases for GTM teams

The founder example is only one configuration. The same Clay + JEV pattern can support other sales automation, RevOps automation, and GTM engineering workflows.

| Use case | Clay retrieves or filters | JEV judges |
|---|---|---|
| Job-title disambiguation | Title, seniority, experience | Whether the role means what the title appears to mean |
| ICP lead scoring | Industry, size, location, technology | Whether the complete record fits the ICP definition |
| B2B prospect qualification | People and company attributes | Whether evidence is strong enough for outreach |
| Account prioritization | Firmographic candidate accounts | Strategic fit, relevance, or risk against a rubric |
| Inbound lead routing | Form and company data | Correct segment, owner, or next workflow |
| Enrichment gating | Broad candidate list | Whether a row is worth paid enrichment |
| Outreach eligibility | Contact and company evidence | Whether outreach criteria are satisfied |
| Data-quality review | Structured records | Whether fields are contradictory, stale, or ambiguous |

Possible audience configurations include:

- Sales leaders at European cybersecurity companies
- RevOps executives at US B2B SaaS companies with 50-250 employees
- Engineering leaders at recently funded AI companies
- Healthcare executives in a defined geography
- Founders in a specific industry, funding stage, or company-size range

## Adapt the workflow to another audience

This skill can be adapted to any job title, company size, industry, location, seniority, company attribute, or other filter supported by Clay Query Mode.

1. Pass a different Clay query with `--query`, or change `DEFAULT_QUERY` in `scripts/rank_clay_people.py`.
2. Replace the founder-specific Choice categories and Noul criteria in `jev_payload()` with the target qualification rubric.
3. Rename the threshold flags when building a permanent role-specific version.
4. Evaluate the new rubric on labeled examples before selecting production thresholds.

Keep exact filters in Clay. Use JEV only where semantic interpretation or uncertainty makes deterministic rules brittle.

## Requirements

- Python 3.11+
- A TypeSafe API key stored as `TYPESAFE_API_KEY`
- The official Clay CLI authenticated to the intended workspace
- `httpx` and `pydantic`

Install from the maintained upstream sources:

- [Official TypeSafe agent skill](https://github.com/typesafe-ai/skills)
- [Official Clay CLI and agent plugins](https://github.com/clay-run/agent-plugins)

## Install the Agent Skill

The package follows the portable Agent Skills structure and supports Claude Code, Cursor, and Grok Build. It also includes a Grok Bot private-skill import flow.

Install for one local agent:

```bash
python install_skill.py --agent claude-code --scope user
python install_skill.py --agent cursor --scope user
python install_skill.py --agent grok-build --scope user
```

Install all three:

```bash
python install_skill.py --agent all --scope user
```

For project-level installation or Grok Bot, read [platform installation](references/platform-installation.md).

Install the Python dependencies:

```bash
python -m pip install -r scripts/requirements.txt
```

Copy `env.example` to `.env`, then supply your own TypeSafe key. Never commit `.env`, credentials, Clay workspace identifiers, or generated lead files.

## Run the founder example

```bash
python scripts/rank_clay_people.py \
  --target-qualified 500 \
  --current-founder-threshold 0.90 \
  --operating-founder-threshold 0.80
```

Pass a custom Clay Query Mode query:

```bash
python scripts/rank_clay_people.py \
  --query '<Clay people query>' \
  --target-qualified 500
```

The runner pages the same forward-only Clay search until it reaches the target, Clay is exhausted, the candidate cap is reached, or the quota safeguard stops it. It writes timestamped JSON and CSV files under `outputs/`.

## Privacy and data handling

- The shared package contains no API keys, workspace IDs, search IDs, or lead records.
- The JEV request receives matched job titles and dates, not names, LinkedIn URLs, or Clay profile IDs.
- Local result files contain identifying fields for the selected prospects because those fields are required to use the list.
- Never commit or redistribute generated results without an appropriate lawful basis and review.

## Limitations and next steps

- A JEV probability threshold is not measured accuracy.
- Clay's company-size buckets may be wider than an exact requested range.
- Missing Clay classifications remain unknown rather than verified facts.
- JEV only evaluates the evidence included in its state.
- Clay search failures and JEV service failures are independent.
- The founder rubric does not rank commercial attractiveness, buying intent, growth, or funding.

Recommended next steps:

1. Label a representative sample as qualified or unqualified.
2. Measure precision, recall, false positives, and false negatives at several thresholds.
3. Compare JEV with deterministic title rules and the Clay AI model normally used by the team.
4. Add separate JEV questions for ICP fit, buying signals, or enrichment eligibility.
5. Pin the JEV model version when reproducibility matters.

## Frequently asked questions

### What is the main JEV use case in this repository?

Semantic lead qualification after a broad Clay people search. JEV distinguishes genuine current operating founders from title-based false positives and returns probabilities that Python can threshold.

### Is JEV a replacement for Clay?

No. Clay searches and returns people or company data. JEV evaluates ambiguous semantic criteria over the returned evidence. They solve different parts of the workflow.

### Can this rank roles other than Founder or Co-Founder?

Yes. Change the Clay query and replace the founder-specific JEV Choice and Noul criteria. The same architecture works for sales, marketing, RevOps, engineering, recruiting, and executive searches.

### Does a JEV score of 0.90 mean the results are 90% accurate?

No. It is a model probability used by the workflow's decision policy. Accuracy, precision, and recall must be measured against labeled examples from the target domain.

### Why use JEV instead of a normal LLM prompt?

JEV is designed for bounded typed decisions such as Choice, Score, and Noul. The application receives probabilities and applies explicit code-level thresholds instead of parsing generated prose. Whether it performs better must still be tested on the specific task.

### How does the workflow reduce Clay usage?

It runs semantic qualification outside Clay's AI columns, then prevents rejected candidates from entering later row-based enrichment and outreach steps. It does not eliminate Clay search-result usage.

### Does the skill work with Claude Code, Cursor, and Grok?

Yes. The installer supports Claude Code, Cursor, and Grok Build skill directories. The package also documents Grok Bot's private-skill workflow.

### Why did the test stop at 472 instead of 500?

The stricter v2 rubric qualified 472 of the first 577 candidates. A request for another Clay page returned HTTP 504, and the test was stopped rather than repeatedly risking search quota.

## What is Clay?

Clay is a GTM data and workflow platform for finding, enriching, qualifying, and acting on company and people data.

[Sign up for Clay](https://clay.com?via=ta).



## Contact

Questions, feedback, or use cases: [follow or contact me on LinkedIn](https://linkedin.com/in/gtm-architect).
