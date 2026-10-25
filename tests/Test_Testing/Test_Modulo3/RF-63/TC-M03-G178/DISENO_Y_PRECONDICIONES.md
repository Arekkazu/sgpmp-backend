# TC-M03-G178: Filtros y Combinaciones de Bitácora de Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G178
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT)
- **Subcasos Evaluados:**
  - **TC-M03-340:** Filtrado por `tipo_evento` (`EVALUACION_CALIDAD_COMPLETADA`, `TRANSICION_MANTENIMIENTO_MANUAL`, tipo inexistente devuelve `total=0` y lista vacía sin error 404). Subcaso `DISPOSITIVO_SIN_SEÑAL` marcado como `[BLOQUEADO]`.
  - **TC-M03-341:** Filtrado por `severidad_log` (`INFO`, `WARNING`, `ERROR`, `CRITICAL`; valor inválido).
  - **TC-M03-343:** Filtrado por `entidad_afectada_id` (lectura de telemetría y dispositivo), `resultado` (`EXITOSO`/`FALLIDO`), e inconsistencia de `id_usuario`.
  - **TC-M03-346:** Combinaciones progresivas con conjunción AND (`tipo_evento` + `severidad_log` + `clasificacion_registro`), intersección vacía (`total=0`, `items=[]`), y verificación de no exposición de `componente_origen` en parámetro `rf_origen`.
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico de Filtros en Repositorio y Router

En [auditoria_iot_router.py:49-60](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L49) y [bitacora_auditoria_iot_repository.py:63-93](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/repositories/bitacora_auditoria_iot_repository.py#L63):

| Parámetro Query | Estado en Router | Implementación SQL en Repositorio | Verificado |
|---|---|---|---|
| `tipo_evento` | Soportado (`Optional[str]`) | `filter(BitacoraAuditoriaIotModel.tipo_evento == tipo_evento)` | Sí |
| `severidad_log` | Soportado (`Optional[str]`) | `filter(BitacoraAuditoriaIotModel.severidad_log == severidad_log)` | Sí |
| `clasificacion_registro` | Soportado (`Optional[str]`) | `filter(BitacoraAuditoriaIotModel.clasificacion_registro == clasificacion_registro)` | Sí |
| `entidad_afectada_id` | Soportado (`Optional[str]`) | `filter(BitacoraAuditoriaIotModel.entidad_afectada_id == entidad_afectada_id)` | Sí |
| `resultado` | Soportado (`Optional[str]`) | `filter(BitacoraAuditoriaIotModel.resultado == resultado)` | Sí |
| `fecha_desde` / `fecha_hasta` | Soportado (`Optional[datetime]`) | `filter(fecha_hora >= desde)` / `filter(fecha_hora <= hasta)` | Sí |
| `id_usuario` | **NO expuesto** en Router | No implementado en repositorio | `[LIMITACION API]` |
| `rf_origen` | **NO expuesto** en Router | No implementado en repositorio | `[LIMITACION API]` |
| `orden` / `orden_por` | **NO expuesto** en Router | Hardcoded a `order_by(fecha_hora.desc())` | `[LIMITACION API]` |

---

## 3. Matriz de Resultados Esperados por Filtro

| Subcaso / Filtro | Parámetros Enviados | Código Esperado | Condición de Aprobación | Verificado |
|---|---|---|---|---|
| TC-340 Tipo RF-62 | `?tipo_evento=EVALUACION_CALIDAD_COMPLETADA` | 200 OK | `items.length >= 1`, todos con `tipo_evento="EVALUACION_CALIDAD_COMPLETADA"` | Sí |
| TC-340 Tipo RF-60 | `?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL` | 200 OK | `items.length >= 1`, todos con `tipo_evento="TRANSICION_MANTENIMIENTO_MANUAL"` | Sí |
| TC-340 Tipo RF-60 Inactivo | `?tipo_evento=DISPOSITIVO_SIN_SEÑAL` | N/A | `[BLOQUEADO]`: no emitible por API síncrona sin broker MQTT o worker background | Bloqueado |
| TC-340 Inexistente | `?tipo_evento=EVENTO_INEXISTENTE_QA_XYZ` | 200 OK | `total=0`, `items=[]` (no 404) | Sí |
| TC-341 Severidad INFO | `?severidad_log=INFO` | 200 OK | `items.length >= 1`, todos con `severidad_log="INFO"` | Sí |
| TC-341 Severidad WARNING | `?severidad_log=WARNING` | 200 OK | Si hay items, todos con `severidad_log="WARNING"` | Sí |
| TC-341 Severidad Inválida | `?severidad_log=FATAL` | 200 o 422 | `[LIMITACION API]`: Si no tipado como Enum, responde 200 con `total=0` | Sí |
| TC-343 Entidad Lectura | `?entidad_afectada_id={id_telemetria}` | 200 OK | Todos los items corresponden a la lectura evaluada | Sí |
| TC-343 Entidad Dispositivo | `?entidad_afectada_id={id_dispositivo}` | 200 OK | Todos los items corresponden al dispositivo | Sí |
| TC-343 Resultado EXITOSO | `?resultado=EXITOSO` | 200 OK | Todos los items tienen `resultado="EXITOSO"` | Sí |
| TC-343 Id Usuario | `?id_usuario=1` | 200 OK | `[LIMITACION API]`: FastAPI lo ignora sin fallar, responde 200 | Sí |
| TC-346 Conjunción AND | `?tipo_evento=...&severidad_log=INFO&clasificacion_registro=NIC41` | 200 OK | Todos los items cumplen TODOS los filtros simultáneamente | Sí |
| TC-346 AND Vacío | `?tipo_evento=TRANSICION_MANTENIMIENTO_MANUAL&clasificacion_registro=NIC41` | 200 OK | `total=0`, `items=[]` sin error de base de datos | Sí |
| Invariante rf_origen | `?rf_origen=RF-62` | 200 OK | `componente_origen` no aparece en ningún item | Sí |

---

## 4. Hallazgos y Limitaciones
1. `[BLOQUEADO]`: `DISPOSITIVO_SIN_SEÑAL` no puede ser generado síncronamente vía API; requiere que un dispositivo IoT deje de emitir heartbeats durante el umbral de inactividad de la tarea background periódica (`_evaluar_dispositivos_periodicamente` cada 60s en `main.py`). Se marca como `[BLOQUEADO]` con solo `console.log`.
2. `[LIMITACION API]`: El endpoint no expone `id_usuario` ni `rf_origen` como parámetros de consulta en el Swagger/Router. Peticiones con estos parámetros devuelven 200 pero no filtran por ellos.
3. `[LIMITACION API / DISCREPANCIA]`: `severidad_log` no está validado como Enum Pydantic en los query params del router, permitiendo strings arbitrarios que devuelven lista vacía en lugar de 422.
