# DISEÑO Y PRECONDICIONES — TC-M03-G170 (RF-62 / RF-63)

## 1. Identificación del Caso
* **Caso de Prueba:** TC-M03-G170 — Re-evaluación explícita de calidad de telemetría.
* **Endpoints Evaluados:**
  - `POST /iot/calidad/reevaluar` (Rol Requerido: ADMINISTRADOR / recurso 38, acción 5).
  - `POST /test-control/query` (auditoría en BD).
* **Subcasos cubiertos:**
  - **TC-M03-324 (Caso feliz):**
    - Parámetros: `id_sensor`, `fecha_desde`, `fecha_hasta`, `causa_documentada` ($\ge 10$ caracteres: `'Offset de calibración mal configurado en RF-24 generó drift falso masivo'`), `parametros_correctos`.
    - Respuesta HTTP 200 con `{ evaluaciones_superadas, evaluaciones_creadas }`.
    - Transición en base de datos: evaluaciones previas marcadas como `SUPERADA` con su `motivo_reevaluacion`.
    - Registro de auditoría en `modulo3.bitacora_auditoria_iot` con `tipo_evento = 'REEVALUACION_CALIDAD_SOLICITADA'`.
    - Discrepancia D7 documentada: los estados canónicos son `VIGENTE` y `SUPERADA` (el valor `'ACTIVA'` del caso queda formalmente descartado).
    - Notificaciones a M04/M06: marcadas como **BLOQUEADO** (solo `console.log`, sin `pm.test`).
  - **TC-M03-325 (Validaciones 422 de causa_documentada):**
    - (a) Sin `causa_documentada` $\rightarrow$ HTTP 422.
    - (b) `causa_documentada = ""` $\rightarrow$ HTTP 422.
    - (c) `causa_documentada = "ab"` ($<10$ caracteres) $\rightarrow$ HTTP 422.
    - (d) Causa de mera preferencia $\rightarrow$ Verificación de rechazo con código y motivo observados.
    - Inmutabilidad: confirmación por SELECT de que ninguna petición 422 mutó evaluaciones en BD.
  - **TC-M03-326 (Validaciones de fechas):**
    - `fecha_desde > fecha_hasta` $\rightarrow$ Aserción estricta exigiendo HTTP 422 (marcado con prefijo `[DISCREPANCIA]` si el backend responde HTTP 400).
    - `fecha_desde == fecha_hasta` $\rightarrow$ Comportamiento no definido en RF (observación con `console.log` sin `pm.expect`).
  - **Invariante D7:**
    - Verificación final de que ninguna lectura conserve más de una evaluación en estado `VIGENTE`.

---

## 2. Precondiciones, Control de Fechas y Aislamiento Transaccional
1. **Control de Fechas:** Fechas controladas en rango pasado (`2026-10-10`, anterior al 19-oct-2026).
2. **Aislamiento Sandbox:**
   - Toda la colección se ejecuta con `X-Test-Run-Id` y `X-Sandbox-Secret`.
   - Limpieza completa al finalizar mediante `DELETE /test-control/runs/{{run_id}}`.
3. **Fixture Controlado en Fechas Pasadas:**
   - Se siembran 5 lecturas en `modulo3.telemetrias` con timestamps pasados (`2026-10-10`) y sus correspondientes evaluaciones iniciales.
   - Las validaciones 422 se ejecutan antes del caso feliz para no alterar el snapshot de datos.
   - Duración estimada de ejecución: **4 a 7 segundos** (19 requests en total).
