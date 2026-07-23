---
tema: free-claude-code
subtema: proveedores-y-enrutado
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Añadir proveedor FCC, Checklist de proveedor]
tags: [free-claude-code, documentacion, proveedores]
---

# Añadir un proveedor

Checklist de extensión (según `ARCHITECTURE.md`):

1. Añadir metadatos del proveedor a `config/provider_catalog.py`
   (`ProviderDescriptor`: ID, transporte, capacidades, credencial, base URL,
   atributos de settings, proxy).
2. Añadir credenciales y settings relacionados a `config/settings.py` y a
   `.env.example` cuando sean configurables por el usuario.
3. Añadir campos al manifiesto del admin en `api/admin_config.py` cuando el
   setting deba editarse en la Admin UI.
4. Implementar el proveedor bajo `providers/` usando la familia de transporte
   compartida apropiada (`OpenAIChatTransport` para APIs OpenAI-compatible;
   `AnthropicMessagesTransport` para APIs Anthropic-compatible).
5. Añadir una factoría en `providers/registry.py`.
6. Añadir tests deterministas bajo `tests/providers/` y los tests de contrato
   relevantes.
7. Añadir cobertura o configuración de smoke en `smoke/` cuando el proveedor se
   pueda ejercitar en vivo.
8. Actualizar la doc de proveedor de cara al usuario en `README.md` cuando el
   usuario necesite instrucciones nuevas de setup.

## Principios relacionados

- **Utilidades compartidas**: la lógica de protocolo Anthropic compartida va a
  módulos neutrales de `core/anthropic/`; un proveedor no importa de los utils
  de otro proveedor.
- **Config específica de proveedor**: los campos propios (p. ej. `nim_settings`)
  van en el constructor del proveedor, no en el `ProviderConfig` base.
- **Sin literales**: usar settings/config en lugar de valores hardcodeados
  (p. ej. `settings.provider_type`, no `"nvidia_nim"`).
- **Migraciones completas**: al mover módulos, actualizar imports al nuevo dueño
  y eliminar shims de compatibilidad en el mismo cambio, salvo que se requiera
  preservar una interfaz publicada.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/transportes|Familias de transporte]]
- [[20-Proyectos/31-free-claude-code/31.05-operacion-y-pruebas/pruebas-ci-y-versionado|Pruebas, CI y versionado]]
