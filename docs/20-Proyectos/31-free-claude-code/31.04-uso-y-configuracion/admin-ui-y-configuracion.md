---
tema: free-claude-code
subtema: uso-y-configuracion
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Admin UI FCC, Configuración FCC, Settings FCC]
tags: [free-claude-code, documentacion, configuracion]
---

# Admin UI y configuración

## Modelo de configuración

`config/settings.py` centraliza la configuración con Pydantic Settings. Los
archivos dotenv se resuelven en este orden (los posteriores sobrescriben a los
anteriores):

1. `.env` local del repo.
2. `~/.fcc/.env` gestionado.
3. `FCC_ENV_FILE` opcional, añadido al final cuando existe.

Las variables de entorno del proceso también participan. `ANTHROPIC_AUTH_TOKEN`
tiene una guarda extra: si algún dotenv configurado lo define, ese valor
reemplaza un token heredado obsoleto del shell.

> Los valores concretos de credenciales/tokens no se documentan aquí; se editan
> en la Admin UI. Ver
> [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/observabilidad-y-seguridad|seguridad]].

## Rutas gestionadas (`config/paths.py`)

- Directorio de config: `~/.fcc`
- Env gestionado: `~/.fcc/.env`
- Catálogo de modelos de Codex generado: `~/.fcc/codex-model-catalog.json`
- Workspace del agente: `~/.fcc/agent_workspace`
- Log del servidor: `~/.fcc/logs/server.log`
- Otros stores: `~/.fcc/models.json`, `~/.fcc/model-aliases.json`,
  `~/.fcc/active-model.json`, `~/.fcc/model-pricing.json`, `~/.fcc/usage.json`.

## Admin UI

Toda la configuración gestionada del proxy se edita en la Admin UI en `/admin`
(solo loopback): editar campos, **Validate**, luego **Apply**.

- `api/admin_config.py` define el manifiesto de configuración del admin y
  escribe las actualizaciones del env gestionado. Es data-driven; los campos
  marcan `restart_required` o `session_sensitive` cuando el estado de runtime no
  puede actualizarse en caliente.
- `api/admin_routes.py` expone endpoints admin solo-locales que cargan, validan,
  aplican y prueban configuración. Tras un apply se limpia la caché de settings;
  según los campos cambiados, el servidor reemplaza el `ProviderRegistry` de la
  app o pide al servidor supervisado reiniciar.
- `require_loopback_admin()` rechaza clientes no-loopback y orígenes no-locales.

## Configuración de modelos (resumen)

- `MODEL` (fallback), `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU` (overrides por
  tier). `MODEL` vacío = passthrough.
- `ENABLE_MODEL_THINKING` (switch global) y overrides por tier
  (`ENABLE_OPUS_THINKING`, `ENABLE_SONNET_THINKING`, `ENABLE_HAIKU_THINKING`).
- `UPDATE_MODELS_ON_REFRESH` (por defecto `true`) controla si **Refresh models**
  re-siembra `models.json`, `model-aliases.json` y la plantilla de pricing en
  disco, o solo refresca la lista en memoria.

Detalle en [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/enrutado-de-modelos|Enrutado de modelos]].

## Ver también

- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/uso-y-costos|Seguimiento de uso y costos]]
- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/vista-general-y-flujo|Vista general y flujo de petición]]
