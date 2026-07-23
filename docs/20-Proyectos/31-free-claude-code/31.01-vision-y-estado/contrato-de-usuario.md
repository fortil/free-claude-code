---
tema: free-claude-code
subtema: vision-y-estado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Contrato de usuario FCC, Customer-facing contract]
tags: [free-claude-code, documentacion, vision]
---

# Contrato de cara al usuario

FCC optimiza para **flujos de trabajo instalados del usuario**, no para
compatibilidad interna. El comportamiento que se compromete a preservar es que
estas superficies funcionen correctamente con prompts reales contra proveedores
soportados.

## Superficies que deben funcionar

- **`fcc-server` y Admin UI**: configurar proveedores, enrutado de modelos,
  auth, server tools, mensajería y diagnósticos.
- **`fcc-claude` + Claude Code + proxy Anthropic-compatible**: streaming de
  texto, thinking nativo/intercalado, uso y resultados de herramientas,
  descubrimiento de modelos, conteo de tokens, reintentos/recuperación y server
  tools locales soportados.
- **`fcc-codex` + Codex + streaming OpenAI Responses**: reasoning
  nativo/intercalado, llamadas a funciones y tools custom, catálogo `/model`
  generado, eventos de ciclo de vida del stream Responses y conversión
  Responses→Anthropic en el borde del adaptador.
- **Puentes de mensajería Discord/Telegram**: comandos, ramas de conversación
  por respuesta, actualizaciones de estado, renderizado de transcripción,
  ejecución de tareas Claude/Codex gestionadas, flujos de stop/clear,
  persistencia y transcripción de voz opcional.
- **Scripts de instalación, actualización, init y desinstalación** en la medida
  en que ponen a disposición los flujos anteriores.

## Qué NO es contrato estable

Módulos internos, diseños de clases, APIs auxiliares, implementaciones de rutas
y tests **no** son contratos estables. Los refactors pueden reemplazarlos o
eliminarlos cuando eso simplifica el sistema, mejora la corrección o encaja
mejor con los límites de arquitectura. Cuando un test codifica sobre todo una
forma interna obsoleta, se actualiza para afirmar el comportamiento de cara al
usuario. Features, shims de compatibilidad, endpoints o rutas auxiliares que no
sirven a una de las superficies anteriores no son requisitos de producto y
deben eliminarse, no preservarse.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.01-vision-y-estado/vision-general|Visión general y capacidades]]
- [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/pruebas-ci-y-versionado|Pruebas, CI y versionado]]
