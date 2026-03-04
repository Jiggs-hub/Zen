# n8n Workflow Setup

1. Start n8n (optional):
   - `docker compose up -d`
2. Open n8n at `http://localhost:5678`.
3. Import `workflows/n8n_clara_pipeline.json`.
4. In each Execute Command node, ensure command paths are valid from repo root.
5. Run `Run All (Batch)` to process all demo and onboarding inputs.
6. Verify artifacts in `outputs/accounts/`, `tracker/tasks.json`, and `changelog/pipeline_runs.jsonl`.
