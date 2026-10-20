# TC-M03-G182: Retención Diferenciada y Naturaleza Append-Only en Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G182
- **Requisito Funcional:** RF-63 (Retención Diferenciada e Inmutabilidad de Bitácora)
- **Subcasos Evaluados:**
  - **TC-M03-348:** Verificación de políticas de retención legal: eventos `NIC41` con `retencion_aplicable = 5` años y eventos `TECNICO` con `retencion_aplicable = 1` año.
  - Comprobación de la naturaleza **append-only** (inmutabilidad estricta): cualquier intento de eliminación o modificación vía `DELETE`, `PUT` o `PATCH` sobre `/iot/auditoria/{id_evento}` debe responder HTTP 405 Method Not Allowed (o 404/403 si la ruta no está registrada).
  - Verificación posterior de que el registro auditado permanece intacto y con el mismo `hash_integridad`.
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico de Inmutabilidad en Router
En [auditoria_iot_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py):
- Métodos registrados en el router de auditoría:
  - `GET /` (listar)
  - `GET /exportar` (exportar)
  - `GET /{id_evento}` (detalle)
  - `POST /verificar-integridad` (verificación SHA-256)
- **NO existen** métodos `DELETE`, `PUT` ni `PATCH`.
- Por especificación de arquitectura REST en FastAPI, solicitudes con métodos no declarados sobre rutas de un recurso son interceptadas respondiendo `405 Method Not Allowed` o `404 Not Found`.

---

## 3. Matriz de Resultados de Inmutabilidad y Retención

| Verificación | Operación / Endpoint | Resultado Esperado | Resultado Observado | Estado |
|---|---|---|---|---|
| Retención NIC41 | `GET /iot/auditoria?clasificacion_registro=NIC41` | `retencion_aplicable === 5` | `retencion_aplicable === 5` | OK |
| Retención TECNICO | `GET /iot/auditoria?clasificacion_registro=TECNICO` | `retencion_aplicable === 1` | `retencion_aplicable === 1` | OK |
| Intento DELETE | `DELETE /iot/auditoria/{id_evento}` | HTTP 405 (o 404/403) | HTTP 405 | OK |
| Intento PUT | `PUT /iot/auditoria/{id_evento}` | HTTP 405 (o 404/403) | HTTP 405 | OK |
| Intento PATCH | `PATCH /iot/auditoria/{id_evento}` | HTTP 405 (o 404/403) | HTTP 405 | OK |
| Integridad post-intento | `GET /iot/auditoria/{id_evento}` | Mismo payload y `hash_integridad` | Mismo hash SHA-256 | OK |
| Eliminación directa BD | `DELETE FROM modulo3.bitacora_auditoria_iot` | N/A | Prohibido por regla CERO DML | `[BLOQUEADO]` |
| Simular reloj repositorio | Modificar timestamp / fecha del sistema | N/A | Sin soporte externo en TEST | `[BLOQUEADO]` |
| Política retención M09 | `GET /configuracion/politicas-retencion` | N/A | Endpoint no expuesto en M09 | `[LIMITACION API]` |

---

## 4. Hallazgos y Motivos de Bloqueo
1. `[BLOQUEADO]`: El caso de prueba original contemplaba intentar borrar registros directamente en PostgreSQL. Esto violaría la Regla 2 obligatoria de aseguramiento QA (CERO DML en BD). Se valida la inmutabilidad a través de la interfaz de servicio HTTP.
2. `[BLOQUEADO]`: Simular el avance del reloj del servidor para comprobar la purga automática por retención de 1 o 5 años no es viable desde el exterior del contenedor en el entorno de pruebas compartidas.
3. `[LIMITACION API]`: El endpoint para consultar las políticas globales de retención de M09 no está implementado ni expuesto en Swagger.
