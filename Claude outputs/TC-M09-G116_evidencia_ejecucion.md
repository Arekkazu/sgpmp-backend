# Evidencia de ejecución — TC-M09-G116 (TC-M09-224)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G116 (TC-M09-224) |
| Descripción | Aplicación exitosa de una plantilla a un destino válido (camino feliz) |
| Categoría | Funcional |
| RF | RF-32 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba funcional — Frontend (Cypress) + Backend (Newman/Postman) |
| Entorno (frontend) | TEST — `http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Backend | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador) |
| Fecha de ejecución | 2026-09-05 |
| Ejecutado por | Daniela Castillo |
| Resultado | ❌ **DEFECTO CRÍTICO CONFIRMADO — el flujo principal de RF-32 no se puede completar ni desde el API ni desde la interfaz** |

## Validación contra el API (Newman)

Se inició sesión como Administrador, se tomaron dos especies activas distintas del entorno como origen y destino, y se registró una plantilla nueva sobre la especie origen (`POST /configuracion/plantillas`) con un `params_snapshot` válido y vigente (`schema_version=1`). Al aplicar esa plantilla sobre la especie destino:

```
POST /configuracion/plantillas/{id}/aplicar
→ 500 Internal Server Error
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[],"timestamp":"2026-09-05T..."}
```

Se verificó además, consultando la configuración de la especie destino después del intento, que la nueva etapa de la plantilla **no** quedó registrada — es decir, el sistema no realiza una escritura parcial ni silenciosa: la operación falla por completo y de forma consistente antes de completarse. 5 de 7 assertions de la colección pasaron; las 2 restantes documentan exactamente este resultado (código 500 en vez de 200, y ausencia de la etapa en el destino).

## Defecto confirmado desde la interfaz (Cypress)

El mismo comportamiento se reproduce end-to-end desde la interfaz. Siguiendo el camino feliz completo (Configuración → Plantillas → elegir una plantilla con parámetros → seleccionar una especie destino distinta de la de origen → previsualizar → "Aplicar plantilla"), el asistente avanza correctamente hasta el paso 3 ("Aplicar"), pero al confirmar la aplicación:

- La API responde `500 ERROR_INTERNO` / "Error inesperado en base de datos", igual que en Newman.
- La interfaz muestra el aviso "Error al aplicar — Error inesperado en base de datos".
- **El asistente queda bloqueado de forma permanente en la pantalla "Aplicando plantilla...".** El paso 3 (`step === 2` en `AplicarPlantillaWizard.tsx`) es el único de los cuatro pasos del asistente cuyo pie no renderiza ningún botón y cuyo encabezado tampoco muestra el botón de cierre ("X") — ambos se ocultan específicamente para ese paso. Como la aplicación nunca tiene éxito, el usuario no tiene ninguna forma de cerrar el diálogo ni de volver atrás salvo recargando la página completa, perdiendo el contexto de en qué especie y plantilla estaba trabajando.

Nota de alcance: las 3 plantillas semilla originales del entorno ("Plantilla estándar camarón/tilapia/trucha") son anteriores a la existencia del campo `schema_version` en `params_snapshot` y, al intentar aplicarlas, el sistema las rechaza de forma correcta y controlada con `412 VERSION_SNAPSHOT_INCOMPATIBLE`. Ese es un comportamiento válido e intencional del sistema para esas plantillas puntuales, distinto del defecto documentado aquí, que ocurre con cualquier plantilla creada en el formato vigente (`schema_version=1`).

## Impacto

El flujo principal de RF-32 (aplicar una plantilla de configuración a una especie destino) no se puede completar en ningún caso, ni por API ni por interfaz, cuando la plantilla usa el formato vigente. Esto bloquea por completo la funcionalidad central de "Gestionar Plantillas de Configuración": una plantilla se puede crear pero nunca aplicarse. Adicionalmente, el asistente de la interfaz no ofrece ninguna salida ante este error, degradando aún más la experiencia del usuario que lo enfrenta.

## Recomendación

1. Revisar los logs del backend en el timestamp exacto del intento para identificar la causa real del error de base de datos al ejecutar `POST /configuracion/plantillas/{id}/aplicar` con una plantilla y destino válidos.
2. Independientemente de la corrección anterior, en `AplicarPlantillaWizard.tsx` agregar un botón de cierre/volver visible también en el paso `step === 2` cuando la aplicación termine en error, para que el usuario no quede atrapado en el diálogo.
3. Una vez corregido el error 500, repetir esta ficha (Newman y Cypress) para confirmar el flujo completo, incluyendo que el paso "Resultado" muestre correctamente el detalle de diferencias aplicadas.

## Herramientas

**Newman (API):**
```bash
newman run tc-m09-g116.json --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-g116.html
```

**Cypress (UI):**
```bash
CYPRESS_ADMIN_EMAIL="admin.test@sgpmp.com.co" CYPRESS_ADMIN_PASSWORD="Administrador123#" npx cypress run --browser chrome
```
Evidencia visual generada automáticamente en `RESULTADOS/`: `01_previsualizacion.png` (previsualización antes de confirmar), `02_resultado.png` (asistente bloqueado en "Aplicando plantilla..." tras el error 500) y video completo de la corrida.
