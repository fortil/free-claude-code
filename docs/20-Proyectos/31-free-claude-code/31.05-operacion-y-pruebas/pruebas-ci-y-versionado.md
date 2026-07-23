---
tema: free-claude-code
subtema: operacion-y-pruebas
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Pruebas FCC, CI FCC, Versionado FCC, Semver]
tags: [free-claude-code, documentacion, operacion]
---

# Pruebas, CI y versionado

## Tests deterministas

Viven bajo `tests/`. Cubren rutas de API, config, conversión de proveedor,
transportes, contratos de streaming, mensajería, adaptadores CLI, límites de
import, contratos del catálogo de proveedores y otros invariantes. Deben quedar
en verde con `uv run pytest` (pytest configurado con `-n auto` y `testpaths =
["tests"]`).

## Smoke tests (`smoke/`)

Locales y en vivo; pueden lanzar subprocesos, llamar proveedores reales, tocar
servidores de modelos locales y opcionalmente enviar mensajes de bot. Taxonomía:

- `smoke/prereq/` — checks de liveness (servidor, rutas, auth, scripts CLI, pings
  de proveedor, `/models` local, permisos de bot). Solo prerrequisitos.
- `smoke/product/` — escenarios E2E de producto (de aquí sale la cobertura de
  feature, no de los pings).
- `smoke/features.py` — mapa fuente-de-verdad de features
  (feature → subfeature → escenario → env → comportamiento esperado → clase de
  fallo).

Se activan solo con `FCC_LIVE_SMOKE=1`; los targets se filtran con
`FCC_SMOKE_TARGETS` y los modelos de proveedor con `FCC_SMOKE_MODEL_<PROVIDER>`.
Ver `smoke/README.md` para el detalle de targets y variables.

## CI (`.github/workflows/tests.yml`)

CI corre en jobs paralelos y exige **cinco checks**:

1. **Ban type ignore suppressions** — grep que prohíbe `# type: ignore` /
   `# ty: ignore`.
2. **ruff-format** (`uv run ruff format --check`).
3. **ruff-check** (`uv run ruff check`).
4. **ty** (`uv run ty check`).
5. **pytest** (`uv run pytest`).

Todos deben pasar; fallar bloquea el merge. Localmente, antes de pushear, correr
`./scripts/ci.sh` (macOS/Linux) o `.\scripts\ci.ps1` (Windows), que corren Ruff
en modo reparación (`ruff format`, luego `ruff check --fix`) antes de type check
y tests. Flags útiles: `--only` / `--skip` / `--dry-run` (PowerShell: `-Only` /
`-Skip` / `-DryRun`).

## Versionado (rama `main`)

Cada commit en `main` que cambie un **archivo de producción** debe incluir un
bump de semver en `pyproject.toml` en el **mismo commit** (y `uv lock` para
reflejarlo en `uv.lock`).

- **Archivos de producción**: `api/`, `cli/`, `config/`, `core/`, `messaging/`,
  `providers/`, `.env.example`, `pyproject.toml`, y los scripts de
  install/uninstall/ci.
- **No** requieren bump por sí solos: `tests/`, `smoke/`, docs y assets
  (`README.md`, `assets/`, `AGENTS.md`, `CLAUDE.md`), y config de repo/CI
  (`.github/`, `.gitignore`). Un commit mixto sí bumpa.

Reglas de semver (`MAJOR.MINOR.PATCH`):

- **PATCH**: bug fixes, refactors sin cambio visible, updates de dependencias,
  arreglos de packaging/install.
- **MINOR**: features backward-compatible (nuevos proveedores, campos de admin,
  comandos CLI, opciones de config).
- **MAJOR**: cambios que rompen (env vars removidas/renombradas, cambios
  incompatibles de API/CLI/defaults, migraciones que el usuario debe hacer).

Versión actual del paquete: **2.13.2**.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.01-vision-y-estado/contrato-de-usuario|Contrato de cara al usuario]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/anadir-proveedor|Añadir un proveedor]]
