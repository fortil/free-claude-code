---
tema: free-claude-code
subtema: vision-y-estado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Visión general FCC, Qué entrega FCC]
tags: [free-claude-code, documentacion, vision]
---

# Visión general y capacidades

## Propósito

Free Claude Code es un **proxy local para clientes de agentes de código**.
Acepta tráfico Anthropic Messages de Claude Code y tráfico OpenAI Responses de
Codex, enruta la petición a un proveedor upstream configurado y **preserva el
protocolo de cable** que espera cada cliente. Así puedes usar Claude Code CLI,
Codex CLI, sus extensiones de VS Code, JetBrains ACP o bots de chat contra tu
propio proveedor (gratuito, de pago o local) sin que el cliente lo note.

El nombre interno del paquete lo describe como middleware entre Claude Code
(API de Anthropic) y NVIDIA NIM, aunque hoy soporta 18 backends.

## Qué entrega

- Proxy drop-in para las llamadas Anthropic de Claude Code (`/v1/messages`,
  `/v1/models`) y para Codex vía OpenAI Responses (`/v1/responses`).
- Lanzadores `fcc-claude` y `fcc-codex` que leen en cada arranque el puerto y el
  token de auth gestionados por la Admin UI.
- 18 backends de proveedor (ver
  [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/catalogo-de-proveedores|catálogo]]).
- Enrutado por tier de modelo para Claude Code: Opus, Sonnet, Haiku y fallback
  pueden ir a proveedores distintos.
- **Modo passthrough**: con `MODEL` vacío, reenvía el modelo/proveedor que
  resuelva el cliente en lugar de forzar un fallback.
- **Palabras clave de prompt** `-<keyword>` persistentes para elegir modelo al
  vuelo (diccionario en `~/.fcc/model-aliases.json`), con `-default` para
  resetear.
- **Seguimiento de tokens y dólares** por proveedor/modelo/día, visible en la
  pestaña Usage de la Admin UI.
- Registro por petición del modelo activo (`FCC | model: …`).
- **Entrada de imágenes** reenviada a modelos con visión.
- Detección y enrutado automático de modelos OpenAI solo-Responses (familias
  `*-codex` y `-pro`) por `/v1/responses`.
- Soporte del selector nativo `/model` tanto en Claude Code (vía `/v1/models`)
  como en Codex (catálogo generado).
- Streaming, uso de herramientas, manejo de bloques de razonamiento/thinking y
  optimizaciones locales de peticiones triviales.
- Wrapper opcional de bot de Discord o Telegram para sesiones remotas de Claude
  Code, con transcripción opcional de notas de voz (Whisper local o NVIDIA NIM).
- **Admin UI local** en `/admin` (solo loopback) para editar configuración,
  validar cambios y comprobar proveedores.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.01-vision-y-estado/contrato-de-usuario|Contrato de cara al usuario]]
- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/index|31.02 · Arquitectura]]
