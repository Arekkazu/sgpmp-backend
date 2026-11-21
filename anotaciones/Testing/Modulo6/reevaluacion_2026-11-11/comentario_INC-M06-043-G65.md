**Reevaluación 11/11/2026 (TEST, código de `dev` del 11/11 con el merge dev → test de las 08:18) — RESULTADO: SIGUE FALLANDO (no corregida)**

**Qué se hizo**
Se repitió TC-M06-G65 (RF-92, TCG-07), subcaso TC-92-043, con el usuario Contador:
`POST /finanzas/periodos/999999999/revelaciones` con `{"compromisos_vigentes":[{"descripcion":"QA M06 compromiso negativo","monto_estimado":-1000,"contraparte":"Banco QA"}]}`.
Se usa un período inexistente para no crear informes: si la validación rechaza el monto responde 400; si lo acepta, la petición llega a la regla del período y responde 422.

**Esperado:** HTTP 400 VAL_ENTRADA indicando `compromisos_vigentes.0.monto_estimado`.
**Obtenido:** HTTP 422 `PERIODO_NO_CERRADO`: el monto negativo pasó la validación de entrada.
**Evidencia:** X-Request-Id `133f816c-3418-474f-aa42-35d2d920ddc2`, 11/11/2026 11:18:46 hora Colombia (16:18:46 GMT).

**Revisión del código (origin/test y origin/dev, 11/11):** sin cambios. `src/financial_valuation/infrastructure/dto/m06_dto.py:225` sigue con `monto_estimado: Optional[Decimal] = None`, sin restricción de signo. Las notas de lanzamiento 1.4.0 / 1.5.0 no incluyen una corrección para esta incidencia.

**Resumen del grupo:** TC-M06-G65, 77 aserciones, 1 fallida (esta). Las demás validaciones de entrada del grupo (descripción vacía o ausente, pignorado sin acreedor o con activo 0, formato de descarga) responden 400 correctamente.

**Adjunto:** `reeval_RF-92_TC-M06-G65.html` (reporte Newman de esta corrida, sin contraseña, tokens ni cookies).

**Estado propuesto:** se mantiene abierta; no pasar a resuelta.
