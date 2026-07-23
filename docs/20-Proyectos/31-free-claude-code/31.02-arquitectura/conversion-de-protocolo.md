---
tema: free-claude-code
subtema: arquitectura
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Conversión de protocolo FCC, Streaming FCC, SSE FCC]
tags: [free-claude-code, documentacion, arquitectura]
---

# Conversión de protocolo y streaming

La lógica de protocolo neutral vive en `core/` y es la que permite que un
cliente Anthropic y un cliente Responses hablen con cualquier proveedor sin
copiar código de conversión dentro de cada proveedor.

## `core/anthropic/` — lado Anthropic

Posee:

- Conversión de contenido y mensajes para upstreams OpenAI-compatible.
- Manejo de esquema y resultados de herramientas.
- Manejo de bloques de thinking.
- Formateo de eventos SSE vía `SSEBuilder`.
- Política de stream nativo Anthropic.
- Política de recuperación de stream (holdback, continuación, reparación).
- Conteo de tokens y formateo de errores de cara al usuario.

La política **compartida** de recuperación vive en
`core/anthropic/stream_recovery_session.py` y `stream_recovery.py`: clasificación
de reintento temprano, buffering de holdback, conteo de intentos y
flush/discard comunes. Los transportes de proveedor siguen dueños de la
construcción de la petición upstream, el parseo semántico del stream, el estado
específico del transporte y los eventos SSE de recuperación reales.

## `core/openai_responses/` — soporte OpenAI Responses (Codex)

Posee:

- El fachada `OpenAIResponsesAdapter` que usa la capa API.
- Soporte solo-streaming de `/v1/responses`.
- Conversión de petición Responses → payload Anthropic Messages.
- Conversión de SSE Anthropic → SSE Responses.
- Sobres de error OpenAI-compatible.

Detalles clave del diseño:

- **No** implementa toda la superficie de OpenAI Responses: acepta `stream`
  omitido o `stream: true`; `stream: false` se rechaza con error de cliente
  OpenAI-shaped porque los flujos instalados solo necesitan streaming.
- Las **tools custom** de Responses se representan internamente como tools
  Anthropic con un único campo `input` string y se restauran en el borde
  Responses (`custom_tool_call`, `custom_tool_call_output`,
  `response.custom_tool_call_input.*`). FCC no valida gramáticas de tools custom.
- **Reasoning** como conversión de protocolo, no política de proveedor:
  `reasoning.effort = "none"` desactiva el `thinking` de Anthropic; cualquier
  otro request explícito de reasoning lo habilita sin traducir nombres de
  effort a presupuestos de tokens. El thinking del proveedor vuelve a mapearse
  a `reasoning` de Responses en el mismo orden de bloques; `redacted_thinking`
  se expone como `encrypted_content` sin texto visible.

`stream.py` es el entrypoint público de streaming; `stream_state.py` mantiene el
libro mayor de salida indexado por bloque para preservar el orden de items. El
código de la API depende del adaptador, no de esos módulos internos.

## Optimizaciones locales y server tools

- `api/optimization_handlers.py` cortocircuita peticiones de cliente de bajo
  valor antes de llegar al proveedor: sondas de cuota, detección de prefijo de
  comando, generación de título, modo sugerencia y extracción de filepath. Cada
  una se controla con flags de settings.
- `api/web_tools/` maneja `web_search` y `web_fetch` locales cuando
  `ENABLE_WEB_SERVER_TOOLS` es true, sin enviar la petición upstream.
  `api/web_tools/egress.py` fuerza restricciones de esquema de URL y de red
  privada para `web_fetch`.
- Los upstreams **OpenAI-chat** no pueden representar de forma segura bloques de
  server tool Anthropic, así que el servicio rechaza peticiones de server tool no
  soportadas antes de la ejecución en lugar de hacer conversión con pérdida.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/transportes|Familias de transporte]]
- [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/observabilidad-y-seguridad|Observabilidad y seguridad]]
