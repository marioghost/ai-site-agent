# Ollama runtime recommendations

These settings help local LLM performance for AI Site Agent.

## CPU-only (low resource)

```bash
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=30m
```

Use a smaller chat model (`qwen2.5:3b`, `llama3.2:3b`) and **Fast** LLM profile in dashboard settings.

CPU-only `qwen2.5:7b` is often too slow for interactive chat (50s+ time-to-first-token).

## GPU

```bash
export OLLAMA_NUM_PARALLEL=2
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=30m
```

`qwen2.5:7b` is reasonable on GPU; use **Balanced** or **Quality** profiles.

## Backend env

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_WARMUP_ENABLED=true
OLLAMA_WARMUP_MODEL=qwen2.5:3b
OLLAMA_KEEP_ALIVE=30m
```

Warmup runs once on backend startup (not per request).

## Diagnostics

- **Test Chat** → diagnostics panel shows Ollama timing breakdown (load, prompt eval, generation, TTFT).
- **POST /api/llm/benchmark** (admin) runs tiny / Ukrainian / RAG-like prompts and returns tokens/sec.
- **GET /api/llm/runtime** shows hardware, Ollama version, warmup status, recommended models.

## Model selection

| Model | Speed | Ukrainian | Use |
|-------|-------|-----------|-----|
| qwen2.5:3b | Fast | Good | Default local CPU |
| llama3.2:3b | Fast | Fair | Low-resource CPU |
| gemma2:2b | Very fast | Fair | Dev / smoke tests |
| phi3:mini | Fast | Fair | Compact workloads |
| qwen2.5:7b | Slow on CPU | Very good | GPU / quality mode |
