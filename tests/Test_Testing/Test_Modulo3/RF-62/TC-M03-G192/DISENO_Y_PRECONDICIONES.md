# DISENO_Y_PRECONDICIONES — TC-M03-G192

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G192 (TC-M03-369, TC-M03-370, TC-M03-371, TC-M03-372, TC-M03-373)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-62 (Evaluación de Calidad) / RFC-011 (Evaluación de Observaciones de Visión Computacional)
- **Estado Global:** `[BLOQUEADO POR ENDPOINT NO IMPLEMENTADO]`
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)

---

## 2. Diagnóstico Técnico y Motivo del Bloqueo
1. **Inspección de OpenAPI (`openapi-test.json`):**
   - No contiene ninguna definición de ruta ni esquema para evaluar observaciones de visión computacional.
2. **Inspección de Routers y Casos de Uso (`src/`):**
   - En `src/telemetry/infrastructure/routers/calidad_router.py:105`, el único endpoint de evaluación puntual disponible es `POST /iot/calidad/{id_telemetria}/evaluar`, el cual opera exclusivamente sobre lecturas escalares de la tabla `modulo3.telemetrias` (consultando columnas `id_sensor, id_variable, valor_crudo, valor_ajustado, timestamp_captura, estado_calidad, parametros_calibracion`).
   - La ingesta de visión existe de forma preliminar en `POST /iot/telemetria/vision` (`telemetria_router.py:154`, persistiendo en `modulo3.observaciones_vision`), pero **no existe ningún endpoint, caso de uso ni servicio de evaluación de calidad de observaciones de visión** (`POST /iot/calidad/vision/{id}/evaluar` o similar).
3. **Subcasos Afectados por Bloqueo:**
   - **TC-M03-369:** Evaluación nominal (índice 100, APTO, apto_para_ia=true, apto_para_nic41=false). `[BLOQUEADO]`
   - **TC-M03-370:** 8 variantes de degradación (cobertura, ratio tracks, fps, cámara degradada). `[BLOQUEADO]`
   - **TC-M03-371:** Fronteras exactas de descuento (0.70/0.69, 0.40/0.39, fps 10/9/5). `[BLOQUEADO]`
   - **TC-M03-372:** Acumulación y saturación a 0 (apto_para_nic41=false siempre). `[BLOQUEADO]`
   - **TC-M03-373:** Clasificación INDETERMINADA (SIN_SEÑAL, tracks=0, alertamiento RF-60). `[BLOQUEADO]`
   - **Configurabilidad M09 y Trazabilidad RF-63:** `[BLOQUEADO]`.

---

## 3. Comportamiento del Runner de Automatización
Siguiendo las directrices de QA, no se inventan endpoints ni se fuerza la evaluación escalar como sustituto. El runner emite el motivo de bloqueo por endpoint ausente y reporta el estado al dashboard sin generar fallos espurios.
