# Evidencia de ejecución — TC-M09-G117 (TC-M09-225/226)

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M09-G117 (agrupa TC-M09-225 y TC-M09-226) |
| Descripción | Confirmación previa al reemplazo de la configuración existente: solicitar confirmación antes de reemplazar (TC-225) y cancelar la aplicación cuando el usuario rechaza el reemplazo (TC-226) |
| Categoría | Usabilidad / Funcional |
| RF | RF-32 |
| CU | CU-07 — Gestionar Plantillas de Configuración |
| Tipo | Prueba funcional — Frontend (Cypress) |
| Entorno (frontend) | TEST — `http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Backend | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador) |
| Especie destino usada | Camarón Blanco (especie activa con configuración real ya existente, confirmada en TC-M09-G104) |
| Fecha de ejecución | 2026-09-05 |
| Ejecutado por | Daniela Castillo |
| Resultado | ✅ **APROBADO — 2/2 pruebas, 5/5 checkpoints correctos** |

## TC-M09-225 — Solicitar confirmación antes de reemplazar la configuración existente

Se abrió el asistente de aplicación sobre una plantilla y se eligió "Camarón Blanco" como especie destino (una especie con configuración de ciclos biológicos ya existente). Al avanzar con "Siguiente", el asistente muestra el paso "Previsualizar" con un aviso explícito ("Esta acción es irreversible") y el detalle de la plantilla y la especie que se van a reemplazar, exigiendo una confirmación explícita ("Aplicar plantilla") antes de continuar.

Para verificar que llegar a este paso no reemplaza nada por sí solo, se consultó por API la configuración de ciclos biológicos de Camarón Blanco justo antes de abrir el asistente y justo después de llegar al paso de previsualización: es idéntica en ambos momentos. El sistema no modifica la configuración destino mientras el usuario no confirme explícitamente.

## TC-M09-226 — Cancelar la aplicación cuando el usuario rechaza el reemplazo

Desde el mismo paso de previsualización, en vez de confirmar, se cerró el asistente con el botón "Cerrar" del encabezado (rechazando el reemplazo). El diálogo se cerró correctamente, sin quedar ningún mensaje de error ni estado inconsistente en pantalla.

Se verificó por API, comparando el estado justo antes de abrir el asistente contra el estado justo después de cancelar:

- La configuración de ciclos biológicos de Camarón Blanco es idéntica antes y después — no se reemplazó nada.
- El historial de aplicaciones de plantillas (`GET /configuracion/plantillas/historial`) es idéntico antes y después — no se registró ninguna aplicación nueva, es decir, no se generó un snapshot de aplicación efectiva por el solo hecho de haber abierto y cancelado el asistente.

## Conclusión

El asistente de aplicación de plantillas cumple correctamente con ambas reglas de esta ficha: exige un paso explícito de confirmación con aviso de irreversibilidad antes de poder reemplazar la configuración de una especie destino, y al rechazar ese reemplazo (cerrando el asistente) no se produce ningún cambio ni se registra ninguna aplicación, ni en la configuración destino ni en el historial.

## Recomendación

Sin defectos que reportar.

## Herramienta (Cypress)

```bash
CYPRESS_ADMIN_EMAIL="admin.test@sgpmp.com.co" CYPRESS_ADMIN_PASSWORD="Administrador123#" npx cypress run --browser chrome
```
Evidencia visual generada automáticamente en `RESULTADOS/`: `01_confirmacion_previa.png` (paso de previsualización con el aviso de confirmación), `02_antes_de_cancelar.png` y `03_despues_de_cancelar.png` (antes y después de rechazar el reemplazo), además del video completo de la corrida.
