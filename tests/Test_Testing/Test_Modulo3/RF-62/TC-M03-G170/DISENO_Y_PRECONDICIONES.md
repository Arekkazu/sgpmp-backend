# DISEÑO Y PRECONDICIONES — TC-M03-G170 (RF-62 / RF-63)

**Versión del diseño:** V1 — Re-evaluación explícita de calidad de telemetría.  
**Módulo:** Módulo 3 — Telemetría y Calidad.  
**Requisitos Funcionales:** RF-62 (Evaluación de calidad de telemetría, FA-08 re-evaluación), RF-63 (Bitácora de auditoría IoT).

---

## 1. Identificación del Caso de Prueba

* **Caso de Prueba:** TC-M03-G170 — Re-evaluación explícita de calidad ante error de configuración.
* **Endpoints Evaluados:**
  * `POST /iot/calidad/reevaluar` (Rol Requerido: ADMINISTRADOR / recurso 38, acción 5).
* **Subcasos cubiertos:**
  * **TC-M03-324 (Caso exitoso):**
    * Re-evaluación masiva de evaluaciones de calidad de un sensor en un rango temporal con causa documentada válida ($\ge 10$ caracteres).
    * Oráculo CSV: HTTP 200 con `{ evaluaciones_superadas: 5, evaluaciones_creadas: 5 }`.
    * Las evaluaciones previas pasan de `VIGENTE` a `SUPERADA` con `motivo_reevaluacion` registrado.
  * **TC-M03-325 (Rechazos por causa inválida):**
    * `325a`: Sin campo `causa_documentada` $\rightarrow$ HTTP 422.
    * `325b`: `causa_documentada = ""` (cadena vacía) $\rightarrow$ HTTP 422.
    * `325c`: `causa_documentada = "ab"` ($<10$ caracteres) $\rightarrow$ HTTP 422.
    * `325d`: `causa_documentada` por preferencia (CA-17: `"quiero cambiar el umbral_drift de 5% a 3%"`).
  * **TC-M03-326 (Validaciones por rango de fechas):**
    * `326a`: `fecha_desde > fecha_hasta` $\rightarrow$ HTTP 422 (`SIN_EVALUACIONES_EN_RANGO`).
    * `326b`: `fecha_desde == fecha_hasta` $\rightarrow$ Comportamiento de borde en microsegundo.

---

## 2. Oráculos por Subcaso

| Subcaso | Petición | Causa / Rango | Respuesta HTTP Esperada | Estado Evaluaciones | Auditoría RF-63 |
|---|---|---|---|---|---|
| **TC-324** | `POST /iot/calidad/reevaluar` | Causa válida ($\ge 10$ chars), rango con 5 vigentes | 200 OK (`evaluaciones_superadas: 5`) | Previas: `SUPERADA`<br>Nuevas: `VIGENTE` | `REEVALUACION_CALIDAD_SOLICITADA` |
| **TC-325a** | `POST /iot/calidad/reevaluar` | Sin `causa_documentada` | 422 Unprocessable Content | Sin cambios | No se emite |
| **TC-325b** | `POST /iot/calidad/reevaluar` | `causa_documentada: ""` | 422 Unprocessable Content | Sin cambios | No se emite |
| **TC-325c** | `POST /iot/calidad/reevaluar` | `causa_documentada: "ab"` | 422 Unprocessable Content | Sin cambios | No se emite |
| **TC-325d** | `POST /iot/calidad/reevaluar` | Cambio de preferencia | 422 (CSV / CA-17) / 200 (código) | N/A | N/A |
| **TC-326a** | `POST /iot/calidad/reevaluar` | `fecha_desde > fecha_hasta` | 422 Unprocessable Content | Sin cambios | No se emite |
| **TC-326b** | `POST /iot/calidad/reevaluar` | `fecha_desde == fecha_hasta` | 200 OK / 422 (según existencia) | N/A | N/A |

---

## 3. Estrategia de Autosiembra Canónica (Camino 1)

## Intento de camino alternativo (sensor 7) — NO VIABLE
Razón: El sensor 7 no existe en `modulo9.sensores` (es un ID huérfano de seeds previos) y sus 5 evaluaciones en `modulo3.telemetria_calidad` se encuentran en estado `SUPERADA`, por lo que `listar_vigentes_por_sensor_rango` retorna 0 registros y el endpoint responde `422 SIN_EVALUACIONES_EN_RANGO`. No es posible inyectar nuevas lecturas para el sensor 7 porque la ingesta valida existencia en `modulo9.sensores` rechazando con HTTP 401 `ERROR_AUTENTICACION`.
La colección V1 queda con autosiembra canónica.

### Flujo de Autosiembra Canónica:
1. `00-Preflight-Autosiembra`:
   * Login Admin y extracción de JWT (`id_usuario_admin`).
   * Descubrimiento de tipos de dispositivo (`SENSOR`) y área.
   * Creación de Finca y Área (`especie_id: 2`, `tipo_modelo_asignado: null` según G169 H2).
   * Creación de Dispositivo IoT (`00.06`).
   * Creación de Sensor (`00.07`) $\rightarrow$ **Punto de falla por INC-M03-G167-SENSOR-500**.
   * Asociación de Sensor al Área (`00.08`).
2. Escenarios funcionales (TC-324, TC-325, TC-326).
3. `99-Teardown`:
   * `DELETE /test-control/runs/{{run_id}}` para rollback completo en base de datos.

---

## 4. Hallazgos del Ambiente y Requerimientos

### INC bloqueante de autosiembra
* **INC-M03-G167-SENSOR-500**: `POST /configuracion/dispositivos-iot/{id}/sensores` retorna HTTP 500 ERROR_INTERNO por `es_activo` NOT NULL sin valor por defecto en `SensorModel`. Bloquea la autosiembra en `00.07`.

### Hallazgos de Requerimiento e Implementación (A.3 / A.6)
* **H1 — No generación de nuevas evaluaciones (`evaluaciones_creadas = 0`)**:
  En `SolicitarReevaluacionUseCase`, el backend únicamente marca las evaluaciones existentes como `SUPERADA` e incrementa `evaluaciones_superadas`. El retorno está explícitamente fijado en `evaluaciones_creadas = 0` (no regenera ni recomputa nuevas filas de calidad automáticamente en el use case). El oráculo del CSV asume `evaluaciones_creadas = 5`.
* **H2 — Validación de cambios de preferencia no implementada (CA-17 / TC-325d)**:
  El backend no implementa análisis semántico de la `causa_documentada` para distinguir errores técnicos de meros cambios de preferencia del operador. Cualquier cadena con longitud $\ge 10$ caracteres es aceptada sintácticamente por el use case.
* **H3 — Validación de fechas invertidas (TC-326a)**:
  El DTO `SolicitarReevaluacionDTO` no posee un validador de orden cronológico (`fecha_desde <= fecha_hasta`). Cuando `fecha_desde > fecha_hasta`, la consulta SQL devuelve 0 registros y el use case lanza `422 SIN_EVALUACIONES_EN_RANGO` (o 400 según el error handler de FastAPI).
* **H4 — Tipos de evento en bitácora RF-63**:
  La auditoría emite `tipo_evento = 'REEVALUACION_CALIDAD_SOLICITADA'` hacia `modulo3.bitacora_auditoria_iot`.

---

## 5. Veredicto Inicial Esperado

* **Veredicto V1:** **RECHAZADO POR BLOQUEO EXTERNO** — `INC-M03-G167-SENSOR-500` en paso `00.07-Crear-Sensor`.
