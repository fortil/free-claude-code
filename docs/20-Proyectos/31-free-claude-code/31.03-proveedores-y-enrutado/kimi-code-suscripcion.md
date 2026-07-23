---
tema: free-claude-code
subtema: proveedores-y-enrutado
tipo: nota
proyecto: free-claude-code
creada: 2026-07-23
actualizada: 2026-07-23
estado: activa
aliases: [Kimi Code suscripción, Haiku a Kimi K3, KIMI_BASE_URL]
tags: [free-claude-code, nota, proveedores, kimi, enrutado]
---

# Kimi Code suscripción — enrutar Haiku a K3 vía membresía

Fuente de la verdad: el repo `free-claude-code`
(`config/settings.py`, `config/provider_catalog.py`, `providers/kimi/client.py`,
`api/routes.py`, `core/http_context.py`). Esta nota es un resumen orientado a
operación; ante cualquier discrepancia manda el código.

## Objetivo

Enrutar el tier Haiku de Claude Code al modelo Kimi K3 con contexto de 1M
(`k3[1m]`) servido por la **suscripción Kimi Code** (`api.kimi.com/coding`,
facturación plana), en vez de la API de pago por token de Moonshot
(`api.moonshot.ai` / `platform.kimi.ai`). Opus y Sonnet no se tocan.

## Decisión de diseño

Se reutiliza el provider `kimi` existente (mismo protocolo Anthropic Messages
nativo, misma clase `KimiProvider`, misma credencial `KIMI_API_KEY`) en vez de
crear un provider `kimi_coding` nuevo. La diferencia entre ambos endpoints es
*dónde está desplegado el backend*, no *qué proveedor es* — el caso canónico
para el que el catálogo ya soporta `base_url_attr` (patrón de LM Studio /
llama.cpp / Ollama). Ver
[[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/anadir-proveedor|Añadir un proveedor]].

## Configuración

```
KIMI_API_KEY="<Kimi Code Console key>"
KIMI_BASE_URL="https://api.kimi.com/coding/v1"
MODEL_HAIKU="kimi/k3[1m]"
```

- El valor correcto lleva **`/v1` final** (`.../coding/v1`), no `.../coding/`
  como sugería el borrador original de la especificación: el transporte
  Anthropic Messages compone `POST {base_url}/messages`, así que sin `/v1` el
  request cae en `.../coding/messages` (ruta inexistente). Un validador de
  `Settings` rechaza explícitamente el host `api.kimi.com` sin sufijo `/v1`.
  El default (`KIMI_DEFAULT_BASE`, open platform) no dispara este validador.
- El corchete `k3[1m]` sobrevive todo el pipeline de enrutado: el validador de
  formato de modelo solo inspecciona el prefijo antes de la primera `/`, y
  `parse_provider_type` / `parse_model_name` /
  `ModelRouter._direct_provider_model` /
  `decode_gateway_model_id` hacen split o partición en esa misma barra, sin
  tocar el resto de la cadena.
- El descubrimiento de modelos de arranque (fail-fast) deriva de
  `KIMI_BASE_URL`: con el default se mantiene la URL legacy
  `https://api.moonshot.ai/v1/models`; con el override apunta automáticamente
  a `https://api.kimi.com/coding/v1/models`, así que un modelo mal escrito
  falla en el arranque en vez de facturar un request.

## Reenvío de User-Agent (zona gris de ToS)

El endpoint de suscripción exige un `User-Agent` de una allowlist de clientes
("Kimi CLI, Claude Code, ..."); Claude Code está en esa lista. FCC reenvía el
`User-Agent` **entrante del cliente, byte a byte** — nunca lo fabrica ni lo
reescribe. Mecanismo: un `ContextVar` neutral en `core/http_context.py`, seteado
desde la dependencia FastAPI `get_request_pipeline`
(`api/routes.py`), que **debe ser `async def`**: como dependencia síncrona,
FastAPI la ejecuta en un threadpool y el `.set()` del ContextVar se pierde
antes de llegar al stream real (verificado empíricamente). Un test de
integración end-to-end (`tests/api/test_request_pipeline.py`) contra el stack
ASGI real actúa de guardarraíl: si alguien revierte la dependencia a síncrona,
ese test falla en CI en vez de romper el reenvío en producción silenciosamente.

Si no hay `User-Agent` entrante (p. ej. el descubrimiento de modelos de
arranque, que no tiene request entrante que reenviar), no se añade la
cabecera: queda el default honesto de httpx. Si el upstream rechaza el UA
genuino reenviado de Claude Code, eso es un límite de ToS del proveedor, no
un bug de FCC — no se sortea fabricando un UA.

## Riesgos operativos

- **Caché de providers a nivel de proceso**: cambiar `KIMI_BASE_URL` desde la
  Admin UI no re-crea un provider `kimi` ya cacheado (misma limitación que
  `LM_STUDIO_BASE_URL` hoy); reiniciar el server aplica el cambio.
- **Override sticky `~/.fcc/active-model.json`**: puede enmascarar
  `MODEL_HAIKU`; limpiarlo (`-default` o borrar el archivo) antes de probar en
  vivo.
- **`credential_url` del descriptor** sigue apuntando a la consola de la
  plataforma open-platform de Moonshot; para la suscripción, la Console key se
  obtiene en la consola de Kimi Code, no en ese enlace.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/catalogo-de-proveedores|Catálogo de proveedores]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/enrutado-de-modelos|Enrutado de modelos]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/index|31.03 · Proveedores y enrutado]]
