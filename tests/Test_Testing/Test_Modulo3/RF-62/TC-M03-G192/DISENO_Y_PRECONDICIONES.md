# Diseño y Precondiciones — TC-M03-G192

## Resumen del Caso
- **ID:** `TC-M03-G192` (Subcasos: TC-369 a TC-373 + Extras)
- **Requerimiento Funcional:** RF-62 (Evaluación de Calidad de Observaciones de VISIÓN).
- **Especificación Vigente:** `AIOT-SPEC-01` (Actualizada al 2026-10-16).
- **Ambiente:** `TEST` (`https://www.api.inmero.co/api-sgpmp-test`) bajo Sandbox Transaccional.

> [!IMPORTANT]
> **Nota de Alineación Documental:**
> La ficha QA en el spreadsheet está escrita contra la versión anterior (2026-10-15, modelo deductivo escalonado). Ese spec fue reemplazado. Este caso se construyó contra el spec vigente. Se solicita a Análisis actualizar la ficha QA para reflejar `AIOT-SPEC-01`.

---

## 1. Contrato Funcional (AIOT-SPEC-01)

### Fórmula del Índice de Calidad
$$\text{indice} = 100 \times \left(w_1 \cdot c + w_2 \cdot \min\left(1, \frac{\text{fps}}{\text{fps}_{\text{cfg}}}\right) + w_3 \cdot \left(1 - \min\left(1, \frac{\text{perdidos}}{\text{tol}}\right)\right)\right) \times \text{modificador}$$

- Parámetros por defecto (M09):
  - $w_1 = 0.40$, $w_2 = 0.35$, $w_3 = 0.25$
  - $\text{fps}_{\text{cfg}} = 15$
  - $\text{tracks\_perdidos\_tolerables} = 5$
  - $\text{modificador}$: `CALIBRADO` $\rightarrow 1.00$, `EN_CALIBRACION` $\rightarrow 0.70$, `SIN_LINEA_BASE` $\rightarrow 0.00$.
- Redondeo / Cuantización: 2 decimales (`NUMERIC(5,2)`).

### Clasificación y Flags
| Rango de Índice | Clasificación | `apto_para_ia` | `confianza_baja` | `apto_para_nic41` |
|---|---|:---:|:---:|:---:|
| $\ge 80.00$ | `OPTIMA` | `true` | `false` | `false` |
| $40.00 - 79.99$ | `DEGRADADA` | `true` | `true` | `false` |
| $< 40.00$ | `NO_APTA` | `false` | `false` | `false` |
| `SIN_LINEA_BASE` ($\text{mod}=0$) | `NO_APTA` | `false` | `false` | `false` |

---

## 2. Flujo Arquitectónico en 2 Pasos
A diferencia de las telemetrías escalares de sensores tradicionales, la ingestión y evaluación de observaciones de visión computacional operan en un flujo desacoplado:
1. **Ingestión Asíncrona:** El broker MQTT autenticado (`BROKER_SERVICE_TOKEN`) registra el sobre D4 en `POST /iot/telemetria/vision` (HTTP 201 Created), persistiendo la observación en `modulo3.observaciones_vision` con `fecha_evaluacion_calidad` nula.
2. **Evaluación Determinista:** El Administrador (`Authorization: Bearer <token_admin>`) o el worker post-commit evalúa la observación en `POST /iot/calidad/vision/{id}/evaluar` (HTTP 200 OK), calculando el índice según los parámetros vigentes, aplicando los flags y persistiendo el resultado de forma idempotente.

---

## 3. Dispositivos y Precondiciones de Prueba
- **Cámara activa elegida:** `QA-M09-G55-cam-290655` (ID 147, categoría `CAMARA`, `es_activo = true`, `fps = 30`).
- **Área preexistente:** `area_id = 3` (Infraestructura activa en `modulo9.infraestructuras`).
- **Autenticación (DEF-04):** Un único login administrativo al inicio (`00.01-Login-Admin`). Todas las peticiones propagan headers `X-Test-Run-Id` y `X-Sandbox-Secret`.
- **Teardown:** `99.01-Rollback-Sandbox` cierra y revierte todas las mutaciones en `modulo3` y `modulo9`.

---

## 4. Matriz de Subcasos y Valores de Prueba (Evaluación Oficial V1)

| Subcaso | Ítem | $c$ | fps | Perdidos | Calibración | Índice Esperado | Clasificación |
|---|---|:---:|:---:|:---:|---|:---:|:---:|
| **TC-369** | `01.01` / `01.02` | 1.00 | 30.0 | 0 | `CALIBRADO` | 100.00 | `OPTIMA` |
| **TC-370** | `02.01-Cobertura-Baja` | 0.50 | 30.0 | 0 | `CALIBRADO` | 80.00 | `OPTIMA` |
| **TC-370** | `02.02-FPS-Bajo` | 1.00 | 10.0 | 0 | `CALIBRADO` | 86.66 / 76.67 | `OPTIMA` / `DEGRADADA` |
| **TC-370** | `02.03-Tracks-Perdidos` | 1.00 | 30.0 | 5 | `CALIBRADO` | 75.00 | `DEGRADADA` |
| **TC-370** | `02.04-EN-CALIBRACION` | 1.00 | 30.0 | 0 | `EN_CALIBRACION` | 70.00 | `DEGRADADA` |
| **TC-371** | `03.01-Indice-80-OPTIMA` | 0.50 | 30.0 | 0 | `CALIBRADO` | 80.00 | `OPTIMA` |
| **TC-371** | `03.02-Indice-79.99-DEGRADADA` | 0.4998 | 30.0 | 0 | `CALIBRADO` | 79.99 | `DEGRADADA` |
| **TC-371** | `03.03-Indice-40-DEGRADADA` | 0.40 | 12.0 | 3 | `CALIBRADO` | 40.00 | `DEGRADADA` |
| **TC-371** | `03.04-Indice-39.99-NO-APTA` | 0.3997 | 12.0 | 3 | `CALIBRADO` | 39.99 | `NO_APTA` |
| **TC-372** | `04.01-SIN-LINEA-BASE` | 1.00 | 30.0 | 0 | `SIN_LINEA_BASE` | 0.00 | `NO_APTA` |
| **TC-372** | `04.02-EN-CALIBRACION-Base-100`| 1.00 | 30.0 | 0 | `EN_CALIBRACION` | 70.00 | `DEGRADADA` |
| **TC-373** | `05.01` a `05.06` | 0.75 | 30.0 | 0 | `CALIBRADO` (Pesos: 0.5, 0.3, 0.2) | 87.50 | `OPTIMA` |

---

## 5. Historial de Corridas y Trazabilidad
- **Evaluación Oficial V1:** Ejecución canónica aprobada (125/125 checkpoints OK), disponible en `resultados/resultado_TC-M03-G192.{json,html}` con la cámara activa 147 (`QA-M09-G55-cam-290655`).
- **Intento previo de construcción:** Ejecución fallida por fixture de dispositivo 7 (registrado como sensor) archivada en `evidencias/run-20261030_construccion_fixture_fallido/` como evidencia de fase de construcción.
