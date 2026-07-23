---
tema: free-claude-code
subtema: arquitectura
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Paquetes FCC, Estructura del proyecto FCC]
tags: [free-claude-code, documentacion, arquitectura]
---

# Límites de paquetes

Los paquetes instalables del wheel se declaran en `pyproject.toml`
(`api`, `cli`, `config`, `core`, `messaging`, `providers`). Cada uno tiene una
responsabilidad clara.

| Paquete | Responsabilidad |
| --- | --- |
| `api/` | App FastAPI, handlers de ruta, `ApiRequestPipeline`, catálogo de modelos, APIs de admin, optimizaciones locales y manejo de server tools. |
| `cli/` | Console entrypoints, lanzadores de CLI cliente (`fcc-claude`, `fcc-codex`), gestión de procesos/sesiones y contratos de adaptador de cliente. |
| `config/` | Settings, metadatos de proveedor (catálogo), rutas de filesystem, setup de logging, constantes y stores (modelos, pricing, uso, modelo activo). |
| `core/` | Lógica de protocolo neutral: conversión Anthropic, construcción de SSE, conversión OpenAI Responses, recuperación de stream, conteo de tokens y trazas estructuradas. |
| `messaging/` | Adaptadores de plataforma opcionales, manejo de mensajes entrantes, colas por árbol, renderizado de transcripción, persistencia, comandos y voz. |
| `providers/` | Construcción de proveedores, clases base compartidas, transportes upstream, rate limiting, listado de modelos y adaptadores concretos. |

`tests/` contiene cobertura determinista (unit y contract). `smoke/` contiene
smoke tests locales y en vivo que pueden lanzar subprocesos o tocar servicios
reales.

## Regla de propiedad principal

El comportamiento **compartido** de protocolo Anthropic y Responses pertenece a
`core/`. Los módulos de proveedor deben usar helpers neutrales en lugar de
importar comportamiento de otro módulo específico de proveedor (verificado por
tests de contrato / límites de import).

## Objetivos de refactor (presión de diseño)

El repo marca estos módulos como blancos de refactor, no como sitios para añadir
comportamiento no relacionado:

- `api/request_pipeline.py` — coordina enrutado, intercepts de solo-mensaje,
  ejecución de proveedor, conteo de tokens y adaptación Responses. Mantener los
  handlers de ruta delgados.
- `providers/transports/` — familias de transporte; las reglas de protocolo
  compartidas deben seguir migrando hacia `core/`.
- `messaging/workflow.py` — coordina dependencias del runtime de mensajería;
  intake, ejecución de nodos en cola y colas de árbol viven en módulos aparte.
- `api/admin_config.py` — manifiesto de configuración del admin; mantenerlo
  data-driven.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/conversion-de-protocolo|Conversión de protocolo y streaming]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/index|31.03 · Proveedores y enrutado]]
