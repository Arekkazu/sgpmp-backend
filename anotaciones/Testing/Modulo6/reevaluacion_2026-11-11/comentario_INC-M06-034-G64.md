**Reevaluación 11/11/2026 (TEST, código de `dev` del 11/11 con el merge dev → test de las 08:18) — RESULTADO: SIGUE FALLANDO (no corregida)**

**Qué se hizo**
Se repitió TC-M06-G64 (RF-92, TCG-06), subcaso TC-92-034, con el usuario Contador:
`POST /finanzas/periodos/999999999/revelaciones` con `{"declaracion_sin_novedad":true,"compromisos_vigentes":[{"descripcion":"QA M06 contradiccion"}]}`.
Se usa un período inexistente para no crear informes: si la validación rechaza la combinación responde 400; si la acepta, la petición llega a la regla del período y responde 422.

**Esperado:** rechazo por contradicción (400): `declaracion_sin_novedad = true` significa que no existen compromisos ni activos pignorados (RF-92, Entradas).
**Obtenido:** HTTP 422 `PERIODO_NO_CERRADO`: la combinación contradictoria pasó la validación.
**Evidencia:** X-Request-Id `4435be3a-ed5f-4946-be45-116fae7853f1`, 11/11/2026 11:18:36 hora Colombia (16:18:36 GMT).

**Revisión del código (origin/test y origin/dev, 11/11):** sin cambios. `m06_dto.py:237-241` (`InformeRevelacionesDTO`) sigue sin validador que revise la combinación, y el caso de uso solo exige que exista alguno de los tres datos. Las notas de lanzamiento 1.4.0 / 1.5.0 no incluyen una corrección para esta incidencia.

**Resumen del grupo:** TC-M06-G64, 38 aserciones, 2 fallidas (esta y la sección de riesgos, que no pertenece a esta incidencia). La sección de riesgos sigue mostrando solo SANITARIO y BAJA.

**Adjunto:** `reeval_RF-92_TC-M06-G64.html` (reporte Newman de esta corrida, sin contraseña, tokens ni cookies).

**Estado propuesto:** se mantiene abierta; no pasar a resuelta.
