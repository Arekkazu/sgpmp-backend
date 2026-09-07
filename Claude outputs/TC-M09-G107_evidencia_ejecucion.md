# Evidencia de ejecución — TC-M09-G107 (TC-M09-206)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G107 (TC-M09-206) |
| Descripción | Prevención de nombre de plantilla duplicado — impedir la creación de una plantilla con nombre duplicado |
| Categoría | Validación / Seguridad — OWASP A03 (Improper Input Validation) |
| RF | RF-30 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba de seguridad y validación — API (Newman) sobre el backend desplegado en TEST |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador) |
| Fecha de ejecución | 2026-09-07 |
| Ejecutado por | Daniela Castillo |
| Resultado | ✅ **APROBADO — 5/5 requests, 11/11 assertions** |

## Procedimiento y resultados

Se creó una plantilla de prueba (`template_name="QA-G107-1788812792815"`) sobre la especie activa Cachama Blanca (`id_especie=4`), quedando registrada correctamente en `version=1` (`id_plantilla=80`). Inmediatamente después se intentó crear una segunda plantilla con **exactamente el mismo nombre, la misma especie y el mismo `params_snapshot`** — un duplicado literal de la original.

El sistema respondió:

```json
{
  "error_code": "NOMBRE_PLANTILLA_DUPLICADO",
  "message": "Nombre no disponible: ya existe una plantilla denominada 'QA-G107-1788812792815'. Asigne un nombre único, o genere una nueva versión de la plantilla existente.",
  "fields": [{ "field": "template_name", "message": "..." }]
}
```

`409 Conflict`, con un `error_code` específico y un mensaje claro que además orienta al usuario hacia la vía correcta ("genere una nueva versión de la plantilla existente" en vez de un nombre nuevo). La respuesta de rechazo no trae ningún `id_plantilla`, confirmando que no se creó ningún registro nuevo.

Se verificó además, consultando el listado completo de plantillas, que existe exactamente **una** plantilla con ese nombre — la original, sin cambios, todavía en `version=1`. No quedó ningún duplicado ni ningún registro huérfano.

## Nota de alcance (para no confundir con TC-M09-204)

Esta ficha bloquea específicamente un **duplicado exacto**: mismo nombre, misma especie y mismo contenido (`params_snapshot`) que una plantilla ya existente. Es un escenario distinto al ya confirmado en TC-M09-G106 (TC-M09-204), donde crear de nuevo con el **mismo nombre pero con el contenido cambiado** genera correctamente una **nueva versión** (`version=2`) en vez de rechazarse — esa es la vía intencional para "editar" una plantilla en este sistema. Ambos comportamientos son correctos y consistentes entre sí: el sistema distingue un reenvío idéntico (bloqueado, `409`) de una actualización real de contenido (permitida, nueva versión).

## Conclusión

El sistema cumple correctamente la regla de unicidad que exige RF-30: no permite crear una plantilla duplicada (mismo nombre, especie y contenido que una existente), responde con un código y mensaje claros (`409 NOMBRE_PLANTILLA_DUPLICADO`), y no deja ningún registro duplicado en el listado.

## Recomendación

Sin defectos que reportar.

## Herramienta (Newman)

```bash
newman run tc-m09-g107.json --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-g107.html
```
