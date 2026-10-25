# TC-M03-G180: Exportación de Bitácora de Auditoría IoT en JSON y CSV (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G180
- **Requisito Funcional:** RF-63 (Exportación y Entrega de Evidencia de Auditoría IoT)
- **Subcasos Evaluados:**
  - **TC-M03-338 (Exportación JSON):** `GET /iot/auditoria/exportar?formato=json`. Verificación de cabeceras (`Content-Type: application/json`, `Content-Disposition: attachment; filename="auditoria_iot.json"`), estructura base + extensión sin `componente_origen`, integridad de registros y respeto de filtros de consulta (`clasificacion_registro=NIC41`). Medición de SLA 10,000 registros marcada como `[BLOQUEADO]`.
  - **TC-M03-339 (Exportación CSV):** `GET /iot/auditoria/exportar?formato=csv`. Verificación de cabeceras (`Content-Type: text/csv`, `Content-Disposition: attachment; filename="auditoria_iot.csv"`), presencia de cabecera con nombres de columnas, ausencia de `componente_origen`, parseo de líneas en script Postman/Newman. Medición de SLA 10,000 registros marcada como `[BLOQUEADO]`.
  - **Aislamiento Sandbox:** Inyección de `X-Test-Run-Id` y verificación de que el streaming respeta el ámbito transaccional.
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico del Endpoint de Exportación

En [auditoria_iot_router.py:84-132](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L84):
- **Decorador:** `@router.get("/exportar", response_class=StreamingResponse)`
- **RBAC:** `require_permission(39, 5)` (Recurso 39: `bitacora_auditoria_iot`, Acción 5: `exportar`)
- **Parámetros:** `fecha_desde`, `fecha_hasta`, `tipo_evento`, `clasificacion_registro`, `formato` (regex `^(json|csv)$`, default `'json'`).
- **Límite interno:** `por_pagina=10000`.
- **Streaming JSON:**
  - `media_type='application/json'`
  - `headers={'Content-Disposition': 'attachment; filename="auditoria_iot.json"'}`
- **Streaming CSV:**
  - `media_type='text/csv'`
  - `headers={'Content-Disposition': 'attachment; filename="auditoria_iot.csv"'}`
  - Serializa las claves del modelo Pydantic `EventoAuditoriaIotSchema` (que omite `componente_origen`).

---

## 3. Matriz de Formatos y Validaciones

| Formato | Content-Type Esperado | Content-Disposition Esperado | Estructura / Filas | componente_origen Expuesto | Hash Verificable (64 hex) | SLA 10,000 Reg <= 10s |
|---|---|---|---|---|---|---|
| **JSON** | `application/json` | `attachment; filename="auditoria_iot.json"` | Array JSON completo | No (Omitido) | Sí (`/^[0-9a-f]{64}$/`) | `[BLOQUEADO]` |
| **CSV** | `text/csv` | `attachment; filename="auditoria_iot.csv"` | Cabecera + N filas | No (Omitido en header) | Sí (en columna hash) | `[BLOQUEADO]` |

---

## 4. Parser CSV Integrado en Newman
El test script de TC-M03-339 implementa un validador ligero en JavaScript dentro del sandbox de Postman:
1. Divide el cuerpo en líneas por `\r?\n`, descartando líneas en blanco.
2. Comprueba que la primera línea (cabecera) incluye las columnas obligatorias: `id_evento`, `tipo_evento`, `modulo`, `hash_integridad`, `clasificacion_registro`.
3. Valida que `componente_origen` **NO** figure en la cabecera CSV.
4. Verifica que existan filas de datos coincidentes con los eventos generados en el sandbox.
5. Se documenta que no se ejecutan parsers externos (Pandas/Excel) dentro del runner Newman para mantener la portabilidad del entorno de pruebas.

---

## 5. Hallazgos y Motivos de Bloqueo
1. `[BLOQUEADO]`: El subcaso CA-10 exige demostrar un tiempo $\le 10$ segundos para la exportación de 10,000 registros. En el entorno de sandbox transaccional (cuyo tiempo de expiración es de 180 s y la duración máxima permitida de la corrida es <120 s), crear 10,000 registros por API consumiría más de 300 segundos, lo que causaría abortos por timeout. Se mide el tiempo de respuesta del endpoint con el volumen sintético generado (<60 s) y se documenta que la prueba de carga a 10,000 registros queda `[BLOQUEADO]`.
2. Se confirma que el endpoint respeta el sandbox `X-Test-Run-Id` al consultar a través del middleware de prueba transaccional.
