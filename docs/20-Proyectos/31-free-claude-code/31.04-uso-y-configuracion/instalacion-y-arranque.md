---
tema: free-claude-code
subtema: uso-y-configuracion
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Instalación FCC, Arranque FCC, fcc-server]
tags: [free-claude-code, documentacion, configuracion]
---

# Instalación y arranque

## Instalar / actualizar

Los instaladores viven en `scripts/install.sh` (macOS/Linux) y
`scripts/install.ps1` (Windows PowerShell). Instalan la herramienta uv más los
extras de voz opcionales, e instalan Claude Code y Codex cuando faltan.
Re-ejecutarlos actualiza a la última versión.

Extras de voz (banderas del instalador): `--voice-nim` (NVIDIA NIM / Riva
gRPC), `--voice-local` (Whisper local, CPU o CUDA), `--voice-all`, y
`--torch-backend cuXXX` para CUDA.

## Desinstalar

`scripts/uninstall.sh` / `scripts/uninstall.ps1` eliminan **solo** la
herramienta uv de FCC y siempre borran el árbol gestionado `~/.fcc/`. No
eliminan uv, Claude Code, Codex ni los runtimes de Python gestionados por uv.
Detener cualquier proceso `fcc-server`, `fcc-claude`, `fcc-codex`, `fcc-init` o
`free-claude-code` antes de desinstalar.

## Arrancar el proxy

```bash
fcc-server
```

Tras el arranque, Uvicorn imprime la dirección de bind y la app registra la URL
del admin, p. ej.:

```text
INFO:     Admin UI: http://127.0.0.1:8082/admin (local-only)
```

Usar el `PORT` configurado si no es `8082`.

## Console scripts (definidos en `pyproject.toml`)

- `fcc-server` — arranca el proxy con host y puerto configurados.
- `free-claude-code` — alias de compatibilidad de `fcc-server`.
- `fcc-init` — scaffold avanzado opcional de `~/.fcc/.env` (preferir la Admin UI
  para configuración normal).
- `fcc-claude` — lanza Claude Code contra el proxy local.
- `fcc-codex` — lanza Codex contra `/v1/responses` con catálogo `/model`
  generado.

## Ejecutar desde fuente (desarrollo)

```bash
git clone https://github.com/Alishahryar1/free-claude-code.git
cd free-claude-code
uv run uvicorn server:app --host 0.0.0.0 --port 8082
```

`server.py` es el punto de entrada ASGI. El entorno requiere **Python 3.14.0**
estable (instalable con `uv python install 3.14.0`) y `uv >= 0.11`; siempre usar
`uv run` en lugar del `python` global.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/clientes|Conectar clientes]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/admin-ui-y-configuracion|Admin UI y configuración]]
