---
tema: free-claude-code
subtema: uso-y-configuracion
tipo: documentación
proyecto: free-claude-code
creada: 2026-07-17
actualizada: 2026-07-17
estado: activa
aliases: [Usage FCC, Costos FCC, Pricing FCC, Imágenes FCC]
tags: [free-claude-code, documentacion, configuracion]
---

# Seguimiento de uso y costos

## Tokens y dólares

FCC registra cuántos tokens —y cuántos dólares— se gastan por proveedor. El uso
de cada petición completada se acumula en `~/.fcc/usage.json`, desglosado por
proveedor, modelo y día. La pestaña **Usage** de la Admin UI (`/admin`) muestra
una tabla por proveedor (tokens de entrada/salida, peticiones y costo) con
desglose por modelo. El uso se persiste por petición, así que sobrevive a
reinicios.

Si un `-<keyword>` o el modelo activo persistido está sobrescribiendo tu `MODEL`
configurado, la pestaña Usage muestra un banner **Active model override** arriba,
para que siempre sea obvio a qué modelo se enruta realmente cada petición.

## Pricing híbrido

- Modelos mainstream (OpenAI/Anthropic/Gemini…) se cotizan automáticamente desde
  la base `tokencost` incluida.
- Para los proveedores que esa base no cubre (NVIDIA NIM, Kimi, Wafer, Z.ai…),
  se ponen los precios en `~/.fcc/model-pricing.json` (USD por 1.000.000 de
  tokens, con `input_per_million` / `output_per_million`). Un **Refresh models**
  siembra una entrada por modelo descubierto para rellenar.
- Tus overrides ganan sobre la base incluida. El costo se computa en tiempo de
  lectura, así que editar un precio re-cotiza el uso histórico. Los tokens
  siempre se rastrean; un modelo sin precio conocido simplemente no muestra
  costo. Los conteos son exactos cuando el proveedor reporta uso, y una
  estimación de tokens si no.

## Entrada de imágenes

Se puede pegar una imagen en Codex o Claude Code y se reenvía al modelo. El
proxy convierte la imagen para el proveedor que sirve la petición, así que hay
que usar un modelo **con visión** (p. ej. `gemini/…`, `openai/gpt-4o`),
seleccionado con `-<keyword>` o `MODEL`. Los modelos sin visión reciben la
imagen pero pueden rechazarla.

## Ver también

- [[20-Proyectos/31-free-claude-code/31.03-proveedores-y-enrutado/enrutado-de-modelos|Enrutado de modelos]]
- [[20-Proyectos/31-free-claude-code/31.04-uso-y-configuracion/admin-ui-y-configuracion|Admin UI y configuración]]
