---
tema: free-claude-code
tipo: índice
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Free Claude Code, FCC, free-claude-code]
tags: [free-claude-code, indice, proyecto, proxy, llm]
---

# Free Claude Code — Proyecto

Free Claude Code (FCC) es un **proxy local** que enruta el tráfico de la API de
Anthropic Messages (Claude Code CLI / extensión) y de la API OpenAI Responses
(Codex CLI / extensión) hacia cualquier proveedor de modelos. Mantiene estable
el protocolo que espera cada cliente mientras te deja elegir modelos gratuitos,
de pago o locales a través del mismo proxy y una Admin UI.

Es un proyecto **Python 3.14** gestionado con `uv`, empaquetado con Hatchling y
distribuido como herramienta de línea de comandos (`fcc-server`, `fcc-claude`,
`fcc-codex`, `fcc-init`).

**Fuente de la verdad:** el repositorio `/Users/william/Develop/own/free-claude-code`
(código + docs). Estas notas son el espejo documental en el vault; ante
discrepancia, manda el repo.

## Estado

- Versión del paquete: **2.13.2** (`pyproject.toml`).
- Runtime: **Python 3.14.0**, `uv >= 0.11`, FastAPI + Uvicorn.
- **18 backends de proveedor** soportados (9 vía chat OpenAI-compatible, 9 vía
  Anthropic Messages).
- Estado general: **activo**, con CI obligatorio (ruff, ty, pytest, ban de
  `type: ignore`) y cobertura de smoke tests opcionales.

## Bloques

- [[20-Proyectos/31-free-claude-code/31.01-vision-y-estado/index|31.01 · Visión y estado]] — qué es FCC, qué entrega y el contrato con el usuario.
- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/index|31.02 · Arquitectura]] — superficies de runtime, límites de paquetes, flujo de petición y conversión de protocolo.
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/index|31.03 · Proveedores y enrutado]] — catálogo de proveedores, familias de transporte y enrutado de modelos.
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/index|31.04 · Uso y configuración]] — instalación, clientes, Admin UI, seguimiento de uso y costos.
- [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/index|31.05 · Operación y pruebas]] — mensajería/voz, observabilidad y seguridad, pruebas, CI y versionado.

## Documentos base en el repo

Estas notas sintetizan y organizan los documentos existentes del repositorio:

- `README.md` — instalación, proveedores y uso de cara al usuario.
- `ARCHITECTURE.md` — mapa técnico para mantenedores (límites, flujos, extensión).
- `AGENTS.md` / `CLAUDE.md` — directiva de trabajo, entorno de código y reglas de versionado.
- `smoke/README.md` — taxonomía de smoke tests.
