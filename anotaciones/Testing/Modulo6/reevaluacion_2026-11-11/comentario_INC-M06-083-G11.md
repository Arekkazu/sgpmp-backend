**Reevaluación 11/11/2026 (TEST, código de `dev` del 11/11 con el merge dev → test de las 08:18) — RESULTADO: SIGUE FALLANDO (pendiente de decisión)**

**Qué se hizo**
Se repitió TC-M06-G11 de RF-92 (TC-92-083) con las cuentas Administrador (caso evaluado) y Productor (control). Se usa un id inexistente: si el rol tiene lectura responde 404; si no la tiene, 403.

| Rol | Petición | Esperado (guía de Finanzas) | Obtenido | X-Request-Id | Hora (Colombia) |
|---|---|---|---|---|---|
| Administrador | `GET /finanzas/revelaciones/999999999` | 404 (tiene lectura) | **403 ACCESO_DENEGADO** | `55bdc06c-f0d1-4127-be17-9b7bcf2919ab` | 11:18:59 |
| Administrador | `GET /finanzas/revelaciones/2` (APROBADO) | 200 | **403 ACCESO_DENEGADO** | `fa2a2009-d2c1-428a-9c71-bf85f80ae18d` | 11:18:59 |
| Productor (control) | `GET /finanzas/revelaciones/2` (APROBADO) | 200 | 200 | `40f36233-d176-44dc-977f-cb3ea45303aa` | 11:18:59 |

El Administrador sigue recibiendo 403 al aprobar (correcto, solo lectura).

**Mensaje del 403:** *«Acceso denegado: su rol (Administrador) no tiene permiso para esta operación del módulo financiero.»* La decisión de fondo sigue abierta: la guía de Finanzas le da al Administrador lectura de todo Finanzas; RF-92 no lo menciona entre sus actores y el código sigue al RF.

**Revisión del código (origin/test y origin/dev, 11/11):** `c4d81e6f2a95_m06_nic41_esquema_rfc018.py:96` mantiene `revelaciones_nic41` solo para los roles 5, 2 y 8. Sin migración posterior que dé lectura al rol 1. Las notas de lanzamiento 1.4.0 / 1.5.0 no incluyen una corrección para esta incidencia.

**Adjunto:** `reeval_RF-92_TC-M06-G11.html` (sin contraseña, tokens ni cookies).

**Estado propuesto:** se mantiene abierta hasta que Análisis decida cuál manda: si la guía, se agrega el permiso de lectura; si el RF, se corrigen la guía y la matriz de pruebas y la incidencia se cierra sin cambio de código.

**Dato adicional (no es esta incidencia):** el Productor ya no puede leer un informe en BORRADOR: `GET /finanzas/revelaciones/41` (BORRADOR) ahora responde 404 (`26565556…`/`58d4333b-37a6-4ddd-9dcf-70748a19e343`, 11:18:59); en la ejecución del 10/11 respondía 200.
