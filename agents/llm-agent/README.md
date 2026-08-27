# llm-agent

A real bring-your-own-key agent. One chat-completion call (OpenAI or Anthropic),
answer written to `output/answer.txt`, token usage to `output/usage.json` so the
platform can price the run. stdlib only — no pip install.

```powershell
faraday submit --task evals/gaia-mini/tasks/g002-capital-australia `
  --agent agents/llm-agent --env OPENAI_API_KEY=sk-...
```

| Env | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | supply one; provider auto-detected |
| `FARADAY_LLM_PROVIDER` | key-based | `openai` or `anthropic` |
| `FARADAY_LLM_MODEL` | `gpt-4o-mini` / `claude-haiku-4-5` | any model id the provider accepts |

Tuned for short factual / computational tasks (gaia-mini). The solver core
(`solve.solve(task_root, instruction, call_llm)`) takes an injected `call_llm`, so
it's unit-tested with no network in `tests/test_llm_agent.py`.
