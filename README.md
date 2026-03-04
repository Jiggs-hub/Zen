# Clara Answers Intern Assignment - Zero-Cost Automation Pipeline

This repository implements a local, zero-cost automation pipeline for:

1. Demo call transcript/form -> Account Memo `v1` + Retell Agent Draft Spec `v1`
2. Onboarding transcript/form -> Account Memo `v2` + Retell Agent Draft Spec `v2`
3. Changelog generation (`v1` -> `v2`) with deterministic, repeatable outputs

No paid APIs are required. The workflow runs using Python standard library only.

## Repo Layout

- `scripts/` - pipeline code
- `workflows/` - n8n workflow export
- `inputs/demo/` - demo transcripts/forms
- `inputs/onboarding/` - onboarding transcripts/forms
- `outputs/accounts/<account_id>/v1` and `v2` - generated artifacts
- `tracker/tasks.json` - local task tracker (free alternative to Asana)
- `changelog/pipeline_runs.jsonl` - batch run logs
- `Docs/` - assignment PDFs

## What This Generates (Per Account)

For demo stage (`v1`):
- `account_memo.json`
- `retell_agent_spec.json`

For onboarding stage (`v2`):
- `account_memo.json`
- `retell_agent_spec.json`
- `changes.json` at account root

Also generated:
- `manifest.json` at account root with version metadata
- `tracker/tasks.json` upserted task items

## Required Fields Covered

The Account Memo JSON includes:
- `account_id`
- `company_name`
- `business_hours` (`days`, `start`, `end`, `timezone`)
- `office_address`
- `services_supported`
- `emergency_definition`
- `emergency_routing_rules`
- `non_emergency_routing_rules`
- `call_transfer_rules`
- `integration_constraints`
- `after_hours_flow_summary`
- `office_hours_flow_summary`
- `questions_or_unknowns`
- `notes`

The Retell Agent Draft Spec includes:
- `agent_name`
- `voice_style`
- `system_prompt`
- `key_variables`
- `tool_invocation_placeholders`
- `call_transfer_protocol`
- `fallback_protocol_if_transfer_fails`
- `version`

## Prompt Hygiene Implemented

Generated prompts explicitly include:
- Business-hours flow
- After-hours flow
- Emergency data collection requirements
- Transfer protocol and transfer-fail fallback
- Rule to avoid mentioning tools/function calls to caller

## Idempotency and Versioning

- Outputs are written to deterministic paths and overwritten safely.
- Running pipeline multiple times does not create duplicate artifacts.
- Task tracker uses upsert behavior (`task_id` key).
- Onboarding merges into existing `v1` and writes `v2` with explicit diffs.

## Input Formats

Supported file types in `inputs/demo` and `inputs/onboarding`:
- `.txt`
- `.md`
- `.json`

For `.json`, either transcript text or structured fields can be provided.
If `account_id` is missing, it is derived from filename.

Recommended naming:
- `acme-demo.txt`
- `acme-onboarding.txt`

Both map to the same `account_id` (`acme`).

## Run Locally

### Prerequisite
- Python 3.10+ installed

### Commands

Run both pipelines (demo + onboarding):

```bash
python scripts/run_pipeline.py --mode all
```

Run only demo stage:

```bash
python scripts/run_pipeline.py --mode demo
```

Run only onboarding stage:

```bash
python scripts/run_pipeline.py --mode onboarding
```

Optional args:

```bash
python scripts/run_pipeline.py \
  --demo-dir inputs/demo \
  --onboarding-dir inputs/onboarding \
  --output-dir outputs/accounts \
  --tracker-file tracker/tasks.json \
  --run-log changelog/pipeline_runs.jsonl \
  --mode all
```

## n8n Workflow Export

File: `workflows/n8n_clara_pipeline.json`

Import in n8n:
1. Open n8n UI
2. Import workflow JSON
3. Update execute command node paths if needed
4. Run manually or schedule

## Retell Setup Notes

If free-tier Retell API creation is unavailable, use generated `retell_agent_spec.json` as manual import blueprint:
1. Open Retell dashboard
2. Create/edit agent manually
3. Copy values from generated spec (name, prompt, transfer/fallback protocol, variables)

## How To Plug In Real Dataset (5 Demo + 5 Onboarding)

1. Put all demo inputs in `inputs/demo/`
2. Put onboarding inputs in `inputs/onboarding/`
3. Ensure file naming maps each pair to same account id
4. Run `python scripts/run_pipeline.py --mode all`
5. Inspect outputs under `outputs/accounts/`

## Known Limitations

- Extraction is deterministic (regex/heuristics) and may miss unusual phrasing.
- Audio transcription is not included; pipeline expects transcript/form input.
- Routing extraction quality depends on transcript clarity.

## Production Improvements

- Stronger parser using constrained LLM extraction with strict schema validation
- Confidence scoring per extracted field
- Web dashboard for account diffs and QA approvals
- Native task system integration (Asana/Jira/Trello APIs)
- Automated Retell API sync if free-tier access allows

## Quick Smoke Test Data Included

Sample files are included in:
- `inputs/demo/`
- `inputs/onboarding/`

Run:

```bash
python scripts/run_pipeline.py --mode all
```

Then inspect:
- `outputs/accounts/acme-fire/`
- `outputs/accounts/northside/`
- `tracker/tasks.json`
- `changelog/pipeline_runs.jsonl`
