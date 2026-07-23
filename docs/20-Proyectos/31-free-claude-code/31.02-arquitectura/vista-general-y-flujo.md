---
tema: free-claude-code
subtema: arquitectura
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Flujo de petición FCC, Runtime FCC]
tags: [free-claude-code, documentacion, arquitectura]
---

# Vista general y flujo de petición

## Superficies de runtime

FCC expone tres superficies:

1. **Proxy HTTP** (FastAPI): rutas Anthropic-compatible, Responses-compatible,
   salud, listado de modelos, stop y admin.
2. **Lanzadores CLI**: entrypoints que preparan el entorno de Claude Code y
   Codex para que apunten al proxy local.
3. **Puente de mensajería** (opcional): adaptadores de Discord o Telegram que
   convierten mensajes de chat en sesiones gestionadas del CLI cliente.

Flujo de alto nivel: los clientes (Claude Code, Codex, Admin UI) y los bots
llegan al proxy FastAPI; el `ApiRequestPipeline` coordina el `ModelRouter` y el
`ProviderRegistry`, que despacha a proveedores OpenAI-chat o Anthropic Messages.

## Arranque y ciclo de vida

- Los console scripts se registran en `pyproject.toml`: `fcc-server` y
  `free-claude-code` → `cli.entrypoints:serve`; `fcc-init` → `:init`;
  `fcc-claude` → `cli.launchers.claude:launch`; `fcc-codex` →
  `cli.launchers.codex:launch`.
- `cli/entrypoints.py` arranca FastAPI con Uvicorn. `serve()` migra archivos de
  entorno legacy, carga settings cacheadas, corre una instancia supervisada y
  puede reiniciar el servidor tras cambios de configuración del admin. En el
  apagado final mata best-effort los procesos hijos registrados.
- `api/app.py` construye la app con `create_app()`: configura logging, registra
  routers de admin y API, añade metadatos de correlación HTTP e instala
  handlers de excepciones. `GracefulLifespanApp` reporta fallos de arranque sin
  tracebacks ruidosos.
- `api/runtime.py` gestiona los recursos de vida del proceso vía `AppRuntime`:
  publica un `ProviderRegistry` de ámbito de app, valida modelos configurados
  best-effort sin bloquear el primer acceso al admin, arranca el refresco de
  listas de modelos, arranca la mensajería opcional, publica estado en
  `app.state` y limpia todo (mensajería, sesiones CLI, transportes, limitadores)
  con cleanup acotado en el apagado.

## Flujo de una petición HTTP

Rutas públicas del proxy en `api/routes.py`:

- `POST /v1/messages` — Anthropic Messages con streaming.
- `POST /v1/responses` — OpenAI Responses-compatible.
- `POST /v1/messages/count_tokens` — conteo de tokens Anthropic.
- `GET /v1/models` — listado de modelos gateway y Claude-compatible.
- `GET /health` — health check.
- `POST /stop` — detener sesiones CLI y tareas pendientes.
- `HEAD`/`OPTIONS` — sondas de compatibilidad.

Camino de `/v1/messages`:

1. La ruta llama `require_api_key()` (`api/dependencies.py`). Si
   `ANTHROPIC_AUTH_TOKEN` está vacío, la auth del proxy está deshabilitada; si
   no, el token puede venir por `x-api-key`, `Authorization: Bearer …` o
   `anthropic-auth-token`, con comparación de tiempo constante.
2. El `ApiRequestPipeline` (`api/request_pipeline.py`) valida mensajes no
   vacíos, resuelve el modelo y el thinking, corre intercepts de solo-mensaje
   (server tools locales y optimizaciones), resuelve el proveedor, hace el
   preflight del upstream y hace stream de SSE Anthropic de vuelta al cliente.
3. **OpenAI Responses** usa el mismo camino de ejecución de proveedor sin
   intercepts de solo-mensaje: `create_response()` delega en el
   `OpenAIResponsesAdapter` (`core/openai_responses/adapter.py`), que convierte
   el payload Responses a Anthropic Messages antes de ejecutar el proveedor y
   luego convierte el SSE Anthropic de vuelta a SSE Responses.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/limites-de-paquetes|Límites de paquetes]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/enrutado-de-modelos|Enrutado de modelos]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/admin-ui-y-configuracion|Admin UI y configuración]]
