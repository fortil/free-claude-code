---
tema: free-claude-code
subtema: operacion-y-pruebas
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Observabilidad FCC, Seguridad FCC, Trazas FCC]
tags: [free-claude-code, documentacion, operacion]
---

# Observabilidad y seguridad

## Trazas y logging

`core/trace.py` emite eventos de traza estructurados a lo largo de etapas como
ingress, routing, provider, egress, messaging y ejecución del CLI cliente. Las
trazas conectan actividad de API, proveedor, CLI y mensajería sin requerir logs
de transporte crudos por defecto.

Los defaults de logging son conservadores:

- Los payloads de API y eventos SSE **no** se loguean crudos salvo que se
  habilite explícitamente.
- Los errores de proveedor y aplicación loguean metadatos por defecto; el
  traceback verboso y el logueo de mensajes son opt-in.
- El texto de mensajería, previews de transcripción, diagnósticos del CLI y
  strings detallados de excepción de mensajería se controlan con flags de
  diagnóstico separados.
- Los valores bajo claves que parecen API keys, authorization, tokens o secrets
  se **redactan** por los helpers de traza donde se emiten trazas estructuradas.

El log del servidor vive en `~/.fcc/logs/server.log`; la consola de `fcc-server`
muestra además una línea concisa `FCC | model: …` por petición.

## Límites de seguridad

- La **Admin UI** y las APIs de admin son **solo loopback**
  (`require_loopback_admin()` rechaza clientes no-loopback y orígenes no-locales).
- La auth de la API del proxy se controla con `ANTHROPIC_AUTH_TOKEN` (comparación
  de tiempo constante; en blanco = deshabilitada).
- El egress de `web_fetch` se limita por defecto a esquemas de URL configurados y
  **bloquea objetivos de red privada** salvo permiso explícito
  (`api/web_tools/egress.py`).
- Las URLs de proveedores locales son configurables por el usuario, pero las
  comprobaciones de estado de proveedor local solo se exponen por la API de
  admin local.
- Los lanzadores limpian credenciales heredadas del cliente para mantener el
  tráfico en el proxy local (`fcc-claude` limpia `ANTHROPIC_*`; `fcc-codex`
  limpia `OPENAI_*`/Codex).

## Ver también

- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/conversion-de-protocolo|Conversión de protocolo y streaming]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/admin-ui-y-configuracion|Admin UI y configuración]]
