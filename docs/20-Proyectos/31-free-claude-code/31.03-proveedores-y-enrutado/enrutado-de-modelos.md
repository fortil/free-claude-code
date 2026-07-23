---
tema: free-claude-code
subtema: proveedores-y-enrutado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Enrutado de modelos FCC, Passthrough, Prompt keywords]
tags: [free-claude-code, documentacion, proveedores]
---

# Enrutado de modelos

`api/model_router.py` resuelve el nombre de modelo entrante del cliente. Soporta
dos formas:

- **Refs directas de proveedor**, como `nvidia_nim/nvidia/model-name`.
- **Gateway model IDs**, decodificados por `api/gateway_model_ids.py`.

Si el modelo entrante no es directo, `Settings.resolve_model()` lo mapea por
tier de Claude.

## Tiers de modelo

- `MODEL` es el fallback (ref de modelo con prefijo de proveedor).
- `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU` sobrescriben los tiers de Claude:
  los nombres que contienen `opus`, `sonnet` o `haiku` usan el override del tier
  correspondiente cuando está seteado; si no, caen a `MODEL`.
- Se pueden mezclar proveedores por tier (p. ej. Opus a un proveedor, Sonnet a
  otro, Haiku a un modelo local, y el fallback en otro).

El router también resuelve el **thinking**: los gateway model IDs pueden forzar
thinking on/off; si no, `Settings.resolve_thinking()` aplica overrides por tier
(`ENABLE_OPUS_THINKING`, `ENABLE_SONNET_THINKING`, `ENABLE_HAIKU_THINKING`) o el
global `ENABLE_MODEL_THINKING`.

## Modo passthrough (`MODEL` vacío)

Con `MODEL` en blanco, FCC deja de forzar un fallback y **reenvía lo que el
cliente resuelva**: un slug con prefijo de proveedor, uno de los gateway models
que FCC anuncia, un `-<keyword>` o el modelo activo persistido. Un nombre Claude
"pelado" y no mapeado (que no coincide con `MODEL_OPUS`/`SONNET`/`HAIKU` y no
lleva prefijo) devuelve un `400` claro explicando cómo enrutarlo — FCC nunca
elige un proveedor en silencio. Con passthrough en Claude Code conviene setear
`MODEL_HAIKU` para que sus llamadas de fondo (títulos, resúmenes) resuelvan.

## Palabras clave de prompt (`-<keyword>`)

Se puede cambiar de modelo al vuelo empezando un prompt con `-<keyword>` (p. ej.
`-kimi2.7 refactor este módulo`). FCC resuelve el keyword a un modelo, elimina el
token del prompt reenviado y enruta ahí. La elección es **persistente**: se
guarda en `~/.fcc/active-model.json` y se aplica a cada petición posterior
(incluso sin keyword, tras compactaciones del cliente, y entre reinicios) hasta
que escribas otro `-<keyword>` o `-default` (que limpia la selección y vuelve al
`MODEL` de la Admin UI). Keywords desconocidos mantienen la selección actual.

El diccionario editable de keywords vive en `~/.fcc/model-aliases.json`
(sembrado con un keyword sugerido por modelo descubierto; tus ediciones se
preservan). La tabla acumulada de modelos descubiertos vive en `~/.fcc/models.json`.

## `GET /v1/models`

Anuncia: refs de modelo de proveedores configurados, modelos descubiertos y
cacheados, variantes no-thinking cuando aplica, e IDs de modelos Claude
built-in para compatibilidad con clientes Claude. El descubrimiento de modelos
es de ámbito de app vía `ProviderRegistry`. Codex usa la misma respuesta:
`fcc-codex` la obtiene al arrancar, convierte los gateway IDs en slugs
seleccionables por Codex y escribe `~/.fcc/codex-model-catalog.json`.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/catalogo-de-proveedores|Catálogo de proveedores]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/clientes|Conectar clientes]]
