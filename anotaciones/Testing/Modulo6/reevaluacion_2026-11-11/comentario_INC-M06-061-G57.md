**Reevaluación 11/11/2026 (TEST, código de `dev` del 11/11 con el merge dev → test de las 08:18) — RESULTADO: SIGUE FALLANDO (pendiente de decisión)**

**Qué se hizo**
Se repitieron TC-M06-G57 de RF-91 (TC-91-061) y de RF-92 (TC-92-071) con la cuenta Externo AgroFusion (auditor externo). Se usan ids inexistentes para la comprobación de permiso: si el rol tiene lectura responde 404; si no la tiene, 403.

| Petición | Esperado (RF) | Obtenido | X-Request-Id | Hora (Colombia) |
|---|---|---|---|---|
| `GET /finanzas/lineas/999999999/cadena` | 404 (tiene lectura) | **403 ACCESO_DENEGADO** | `6613c9ec-13fc-4ccc-ba4f-ef798ab30fc3` | 11:18:27 |
| `GET /finanzas/revelaciones/999999999` | 404 (tiene lectura) | **403 ACCESO_DENEGADO** | `d2287a81-dd30-452c-aa34-f50b48c8e86d` | 11:18:57 |
| `GET /finanzas/revelaciones/2` (APROBADO) | 200 | **403 ACCESO_DENEGADO** | `e3b21a30-8c02-4df7-a119-e09c70a1428c` | 11:18:57 |
| `GET /finanzas/revelaciones/2/descarga?formato=pdf` (APROBADO) | 200 | **403 ACCESO_DENEGADO** | `b3a58ea2-e2ec-4cd2-8e40-21e918c5769e` | 11:18:57 |

Sin cambios en lo que sí funciona: el auditor recibe 403 al verificar, cerrar, aprobar, rechazar o generar (correcto).

**Novedad:** el mensaje del 403 ahora es más claro: *«Acceso denegado: su rol (Externo AgroFusion) no tiene permiso para esta operación del módulo financiero.»* La decisión de fondo sigue abierta: RF-91 y RF-92 (Actores) dan al auditor externo lectura de la cadena de períodos CERRADOS y de informes APROBADOS/ARCHIVADOS «a través de M08», y M08 no existe en este backend.

**Revisión del código (origin/test y origin/dev, 11/11):** la matriz de permisos de M06 (`alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py:95-96`) sigue asignando `trazabilidad_contable` y `revelaciones_nic41` solo a los roles 1, 2, 5 y 8. No hay una migración posterior que dé permisos al rol Externo. Las notas de lanzamiento 1.4.0 / 1.5.0 no incluyen una corrección para esta incidencia.

**Resumen de los grupos:** RF-91 TC-M06-G57, 60 aserciones, 2 fallidas (esta incidencia). RF-92 TC-M06-G69, 92 aserciones, 8 fallidas: 4 de esta incidencia, 3 de INC-M06-083-G69 y 1 de la comprobación del Productor sobre un BORRADOR (ahora responde 404 en vez del 403 esperado: es una mejora, no un fallo).

**Adjuntos:** `reeval_RF-91_TC-M06-G57.html` y `reeval_RF-92_TC-M06-G69.html` (sin contraseña, tokens ni cookies).

**Estado propuesto:** se mantiene abierta hasta que Análisis y Desarrollo decidan si el acceso del auditor va en la API de M06 o en M08. Si va en M08, el comportamiento actual (403) pasa a ser el esperado y los casos TC-91-061 y TC-92-071 se reescriben para probar ese acceso cuando M08 esté disponible.
