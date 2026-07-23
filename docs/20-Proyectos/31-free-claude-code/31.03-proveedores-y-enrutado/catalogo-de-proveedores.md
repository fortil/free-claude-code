---
tema: free-claude-code
subtema: proveedores-y-enrutado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-23
estado: activa
aliases: [Catálogo de proveedores FCC, 18 proveedores]
tags: [free-claude-code, documentacion, proveedores]
---

# Catálogo de proveedores

Los metadatos de proveedor son neutrales y están centralizados en
`config/provider_catalog.py`. Cada `ProviderDescriptor` declara el ID del
proveedor, el tipo de transporte, capacidades, variable de entorno de
credencial, URL base por defecto, nombres de atributos de settings y soporte de
proxy. FCC soporta **18 backends**; el modelo se enruta con el prefijo de slug
`provider_id/model_id`.

## Backends soportados

| Prefijo de slug | Proveedor | Transporte | Credencial (nombre de var) |
| --- | --- | --- | --- |
| `nvidia_nim/` | NVIDIA NIM | `openai_chat` | `NVIDIA_NIM_API_KEY` |
| `open_router/` | OpenRouter | `anthropic_messages` | `OPENROUTER_API_KEY` |
| `gemini/` | Google AI Studio (Gemini) | `openai_chat` | `GEMINI_API_KEY` |
| `deepseek/` | DeepSeek | `anthropic_messages` | `DEEPSEEK_API_KEY` |
| `mistral/` | Mistral La Plateforme | `openai_chat` | `MISTRAL_API_KEY` |
| `mistral_codestral/` | Mistral Codestral | `openai_chat` | `CODESTRAL_API_KEY` |
| `opencode/` | OpenCode Zen | `openai_chat` | `OPENCODE_API_KEY` |
| `opencode_go/` | OpenCode Go | `openai_chat` | `OPENCODE_API_KEY` (compartida con Zen) |
| `wafer/` | Wafer | `anthropic_messages` | `WAFER_API_KEY` |
| `kimi/` | Kimi (Moonshot) | `anthropic_messages` | `KIMI_API_KEY` (base URL overridable: `KIMI_BASE_URL`) |
| `cerebras/` | Cerebras Inference | `openai_chat` | `CEREBRAS_API_KEY` |
| `groq/` | Groq | `openai_chat` | `GROQ_API_KEY` |
| `openai/` | OpenAI | `openai_chat` | `OPENAI_API_KEY` |
| `fireworks/` | Fireworks AI | `anthropic_messages` | `FIREWORKS_API_KEY` |
| `zai/` | Z.ai | `anthropic_messages` | `ZAI_API_KEY` |
| `lmstudio/` | LM Studio (local) | `anthropic_messages` | — (base URL: `LM_STUDIO_BASE_URL`) |
| `llamacpp/` | llama.cpp (local) | `anthropic_messages` | — (base URL: `LLAMACPP_BASE_URL`) |
| `ollama/` | Ollama (local) | `anthropic_messages` | — (base URL: `OLLAMA_BASE_URL`) |

> Los valores de las credenciales se configuran en la Admin UI; aquí solo se
> nombran las variables. Ver
> [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/observabilidad-y-seguridad|seguridad]].

## Notas por familia

- **OpenAI-chat** (9): NVIDIA NIM, Gemini, Mistral, Mistral Codestral, OpenCode
  Zen, OpenCode Go, Cerebras, Groq, OpenAI. Usan `/chat/completions`
  OpenAI-compatible traducido a SSE Anthropic (OpenAI first-party para el
  proveedor `openai`; los modelos `*-codex` y `-pro` de OpenAI se detectan y van
  por `/v1/responses`).
- **Anthropic Messages** (9): OpenRouter, DeepSeek, Wafer, Kimi, Fireworks,
  Z.ai, LM Studio, llama.cpp, Ollama. Usan endpoints estilo `/messages`
  Anthropic-compatible (con particularidades por proveedor: p. ej. Kimi en
  `https://api.moonshot.ai/anthropic/v1` por defecto — overridable con
  `KIMI_BASE_URL` a la suscripción Kimi Code, ver
  [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/kimi-code-suscripcion|Kimi Code suscripción]] —,
  Z.ai en `https://api.z.ai/api/anthropic/v1`).
- **Locales**: LM Studio, llama.cpp y Ollama se configuran por URL base
  (`*_BASE_URL`), no por API key. `OLLAMA_BASE_URL` es la raíz del servidor Ollama
  (no se le añade `/v1`).

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/transportes|Familias de transporte]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/index|31.04 · Uso y configuración]]
