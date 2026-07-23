---
tema: free-claude-code
subtema: proveedores-y-enrutado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Transportes FCC, Registry de proveedores]
tags: [free-claude-code, documentacion, proveedores]
---

# Familias de transporte

## Registro de proveedores

`providers/registry.py` posee las factorías de proveedor y el registro de
runtime. Valida que descriptores, factorías e IDs soportados estén sincronizados,
construye un `ProviderConfig` compartido, comprueba credenciales requeridas, crea
proveedores de forma lazy, los cachea, refresca listas de modelos y limpia
transportes.

`providers/base.py` define:

- `ProviderConfig` — settings compartidos del proveedor: API key, base URL,
  rate limits, timeouts, proxy, thinking y flags de logging.
- `BaseProvider` — la interfaz del proveedor para cleanup, listado de modelos,
  preflight y `stream_response()`.

## Dos familias de transporte

Bajo `providers/transports/`:

- **`openai_chat/`** implementa `OpenAIChatTransport` para proveedores con API
  `/chat/completions` OpenAI-compatible. El paquete posee la base delgada del
  transporte, el runner de stream por petición, el ensamblado de tool-calls
  OpenAI y la construcción de eventos de recuperación OpenAI-chat.
- **`anthropic_messages/`** implementa `AnthropicMessagesTransport` para
  proveedores con API `/messages` Anthropic-compatible. Posee la base delgada,
  el runner de stream nativo, helpers de respuesta HTTP y la construcción de
  eventos de recuperación nativos.

Responsabilidades compartidas del proveedor: rate limiting upstream, listado de
modelos, mapeo seguro de errores, cleanup de transporte, manejo de thinking/tools,
retry/recuperación donde se soporta, y devolver strings de SSE Anthropic a la
capa de servicio.

Los runners de stream por petición mantienen el estado mutable del stream para
que las clases base del transporte se centren en hooks de proveedor, setup del
cliente y listado de modelos. La política de protocolo compartida sigue migrando
hacia `core/` cuando no es específica del proveedor.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.02-arquitectura/conversion-de-protocolo|Conversión de protocolo y streaming]]
- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/anadir-proveedor|Añadir un proveedor]]
