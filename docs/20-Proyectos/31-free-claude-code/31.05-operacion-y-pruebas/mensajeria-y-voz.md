---
tema: free-claude-code
subtema: operacion-y-pruebas
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Mensajería FCC, Discord, Telegram, Voz FCC]
tags: [free-claude-code, documentacion, operacion]
---

# Mensajería y voz

La mensajería es **opcional**. Envuelve sesiones remotas de Claude Code: streamea
progreso, soporta ramas de conversación por respuesta y puede detener o limpiar
tareas. Hoy los bots de Discord/Telegram usan Claude Code; para Codex se usa
`fcc-codex` o la extensión de Codex.

## Configuración

Con `fcc-server` corriendo, abrir la Admin UI → **Messaging**, elegir plataforma
(`discord` o `telegram`), pegar los tokens y allowlists, setear **Allowed
Directory** (ruta absoluta del workspace que el bot puede usar), y
**Validate** + **Apply**.

- **Discord**: crear el bot en el Developer Portal, habilitar Message Content
  Intent, invitarlo con permisos de lectura/envío/historial, y copiar el token y
  el/los channel ID.
- **Telegram**: crear el bot con @BotFather (token) y obtener tu user ID numérico
  con @userinfobot para que solo tú lo uses.

Comandos útiles: `/stop` (cancela una tarea; responde a un mensaje para detener
solo esa rama), `/clear` (resetea sesiones), `/stats` (estado de la sesión).

## Arquitectura del puente

`api/runtime.py` llama `create_messaging_platform()`
(`messaging/platforms/factory.py`) en el arranque; si `MESSAGING_PLATFORM` es
`none` o falta el token de la plataforma, el puente se omite.

- Los adaptadores de plataforma (`messaging/platforms/telegram.py`,
  `discord.py`) son cascarones delgados del SDK: ciclo de vida del cliente,
  extracción de eventos, reintentos del SDK, descarga de adjuntos y send/edit/
  delete crudos.
- La política de entrega compartida vive en `platforms/outbox.py` (envíos en
  cola, dedup, delegación al limitador, fire-and-forget). La orquestación de voz
  compartida vive en `platforms/voice_flow.py`.
- `messaging/workflow.py` (`MessagingWorkflow`) es el coordinador agnóstico de
  plataforma.
- `messaging/turn_intake.py` graba mensajes entrantes, despacha slash commands,
  resuelve replies, crea/extiende árboles, envía estados iniciales, persiste y
  encola.
- `messaging/node_runner.py` gestiona el ciclo de vida de la sesión CLI para
  nodos en cola (fork/resume de sesión padre, parseo de eventos CLI, updates de
  transcripción/estado, cancelación, cleanup).
- `messaging/trees/` preserva el orden por conversación con colas por árbol:
  cada respuesta es un nodo hijo, cada árbol procesa un nodo a la vez y árboles
  distintos progresan en paralelo. `messaging/session.py` persiste árboles y
  mapeos a un JSON bajo el workspace con escrituras atómicas debounced.
- `cli/managed/` gestiona los subprocesos de Claude Code usados por la
  mensajería (con `--output-format stream-json`, `--resume`/`--fork-session`
  opcionales, etc.).

## Voz (notas de voz)

Funciona en Discord y Telegram tras extender la instalación con los extras de voz
(`--voice-nim`, `--voice-local`, `--voice-all`). En la Admin UI → **Messaging** →
**Voice**: activar **Voice Notes**, elegir **Whisper Device** (`cpu`, `cuda` o
`nvidia_nim`), setear **Whisper Model** y, si hace falta, el **Hugging Face
Token**. Para `nvidia_nim` hay que instalar el extra `voice` y setear la API key
de NVIDIA NIM.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/vista-general-y-flujo|Vista general y flujo de petición]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/clientes|Conectar clientes]]
