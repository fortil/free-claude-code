---
tema: free-claude-code
subtema: uso-y-configuracion
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Clientes FCC, fcc-claude, fcc-codex, VS Code, JetBrains ACP]
tags: [free-claude-code, documentacion, configuracion]
---

# Conectar clientes

FCC soporta cuatro superficies de cliente. Los lanzadores leen en cada arranque
el puerto y el token de auth gestionados por la Admin UI.

## Claude Code CLI (`fcc-claude`)

`fcc-claude` limpia las variables `ANTHROPIC_*` heredadas, setea
`ANTHROPIC_BASE_URL`, habilita el descubrimiento de modelos gateway, configura
la ventana de auto-compactación (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=190000`) y
siempre setea `ANTHROPIC_AUTH_TOKEN`. Con auth de proxy en blanco, inyecta el
sentinela local `ANTHROPIC_AUTH_TOKEN=fcc-no-auth` solo para satisfacer el gate
de login local de Claude Code; el proxy sigue tratando la auth en blanco como
deshabilitada.

## Codex CLI (`fcc-codex`)

`fcc-codex` inyecta config efímera de Codex en cada arranque:

- `model_provider=fcc`
- `model_providers.fcc.base_url=http://127.0.0.1:<PORT>/v1`
- `model_providers.fcc.env_key=FCC_CODEX_API_KEY`
- `model_providers.fcc.wire_api=responses`
- `model_catalog_json=~/.fcc/codex-model-catalog.json`

Reutiliza el token de auth de la Admin UI como `FCC_CODEX_API_KEY`, elimina las
credenciales oficiales `OPENAI_*`/Codex del entorno hijo para que el tráfico
quede en el proxy local, y genera el catálogo para el selector nativo `/model`.
La generación del catálogo es fail-open: si no se puede preparar, lanza con
advertencia. Los args de Codex pasan igual (p. ej. `fcc-codex exec "hello"`).

## Claude Code en VS Code

Instalar la extensión y añadir en `settings.json` (`claudeCode.environmentVariables`):
`ANTHROPIC_BASE_URL` (URL del proxy), `ANTHROPIC_AUTH_TOKEN` (mismo valor que la
Admin UI), `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` y
`CLAUDE_CODE_AUTO_COMPACT_WINDOW=190000`. Recargar la extensión.

## Codex en VS Code

La extensión comparte el config de usuario de Codex (`~/.codex/config.toml`).
Configurar el provider `fcc` apuntando al proxy local (`base_url` a `.../v1`,
`env_key=FCC_CODEX_API_KEY`, `wire_api=responses`) y guardar el token en
`~/.codex/auth.json` bajo `FCC_CODEX_API_KEY` (mismo valor que
`ANTHROPIC_AUTH_TOKEN`). Reiniciar VS Code tras cambiar estos archivos.

## Claude Code en JetBrains ACP

Editar el config de Claude ACP (`~/.jetbrains/acp.json` en Linux/macOS o el
`installed.json` de JetBrains en Windows) y setear el `env` de
`acp.registry.claude-acp` con `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` y
`CLAUDE_CODE_AUTO_COMPACT_WINDOW=190000`. Reiniciar el IDE.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/enrutado-de-modelos|Enrutado de modelos]]
- [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/mensajeria-y-voz|Mensajería y voz]]
