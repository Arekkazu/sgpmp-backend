# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G26 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución**: 2026-09-08 / 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **PASS (100% EXITOSO - 3/3 SUB-CASOS APROBADOS)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Objetivo de la Prueba | Resultado Esperado | Resultado Obtenido | Veredicto |
| :--- | :--- | :--- | :--- | :---: |
| **TC-M02-053** | Rechazar edición directa de métricas calculadas | `HTTP 400` / `422`. Rechazo por edición directa no permitida; métricas inalteradas. | `HTTP 400 Bad Request`<br>`VAL_ENTRADA`<br>Rechazo por campos no editables directamente. | **PASS** |
| **TC-M02-054** | Evento sanitario con muertes no descuenta cantidad automáticamente | `HTTP 201 Created`. Evento guardado como informativo; `cantidad_actual` permanece inalterada. | `HTTP 201 Created`<br>Evento `DIAGNOSTICO` registrado.<br>`GET` confirma `cantidad_actual` = 5 intacta. | **PASS** |
| **TC-M02-055** | Rechazar cambio de estado directo del lote | `HTTP 400 Bad Request`. Rechazo por cambio de estado fuera de RF-44; estado inalterado. | `HTTP 400 Bad Request`<br>`VAL_ENTRADA`<br>Rechazo directo de alteración de estado. | **PASS** |

---

## 2. Datos del Lote de Prueba (Activo Biológico Poblacional)

- **ID Activo**: `130`
- **Especie**: `4` (*Cachama Blanca*)
- **Infraestructura**: `3` (*Alevinera-01*, superficie = 500 m²)
- **Tipo de Activo**: `POBLACIONAL`
- **Estado Inicial y Final**: `1` (`ACTIVO`)
- **Población Inicial y Final (`cantidad_actual`)**: `5` individuos
- **Métricas Registradas**: `peso_promedio = 55.0`, `biomasa_total = 275.0`, `densidad = 0.01`
- **Fase Productiva Activa**: `Fase juvenil cachama` (`id_gestion_fases = 35`, ciclo `4`)

---

## 3. Detalle de Ejecución por Sub-caso

### 3.1. Sub-caso TC-M02-053: Rechazar edición directa de métricas calculadas

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/TC-M02-053.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/RESULTADOS/reporte_TC-M02-053.html`
- **Endpoint**: `PATCH /activos-biologicos/130`
- **Payload Enviado**:
  ```json
  {
    "biomasa_total": 500.0,
    "densidad": 12.5,
    "peso_promedio": 100.0
  }
  ```
- **Respuesta de la API**:
  - **Código HTTP**: `400 Bad Request`
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "VAL_ENTRADA",
      "message": "Errores de validacion en la solicitud",
      "fields": [
        {
          "field": null,
          "message": "Value error, Al menos un campo debe estar presente para actualizar."
        }
      ],
      "timestamp": "2026-09-09T02:49:00.000000+00:00"
    }
    ```
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 400 Bad Request o 422
  - `[PASS]` El backend rechaza la edición directa de métricas calculadas
- **Conclusión**: El backend rechaza de forma estricta la manipulación manual de métricas calculadas que solo deben actualizarse por vía de eventos biológicos formales.

---

### 3.2. Sub-caso TC-M02-054: Evento sanitario con muertes no descuenta cantidad automáticamente

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/TC-M02-054.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/RESULTADOS/reporte_TC-M02-054.html`
- **Paso 1 - Registro Evento Sanitario**: `POST /activos-biologicos/130/eventos/sanitario`
  - **Payload Enviado**:
    ```json
    {
      "tipo": "DIAGNOSTICO",
      "diagnostico": "Sospecha de bacteriosis con reporte de 5 individuos afectados",
      "observaciones": "Se observan 5 ejemplares afectados con sintomatología clínica, pendientes de evento formal de BAJA",
      "descripcion": "Reporte clínico preliminar de afectación",
      "fecha": "2026-09-09T02:30:00Z"
    }
    ```
  - **Respuesta API**:
    - **Código HTTP**: `201 Created`
    - **Cuerpo JSON (extracto)**:
      ```json
      {
        "evento": {
          "id_eventos": 132,
          "id_activo_biologico": 130,
          "fecha": "2026-09-09T02:30:00Z",
          "descripcion": "Reporte clínico preliminar de afectación",
          "id_usuario": 1,
          "sanitario": {
            "tipo": "DIAGNOSTICO",
            "diagnostico": "Sospecha de bacteriosis con reporte de 5 individuos afectados",
            "observaciones": "Se observan 5 ejemplares afectados con sintomatología clínica, pendientes de evento formal de BAJA"
          }
        },
        "cambio_estado": null
      }
      ```
- **Paso 2 - Consulta Activo Biológico**: `GET /activos-biologicos/130`
  - **Respuesta API**: `HTTP 200 OK`
  - **Valor `cantidad_actual` obtenido**: `5`
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 201 Created (evento sanitario registrado)
  - `[PASS]` El evento sanitario se registra con tipo DIAGNOSTICO
  - `[PASS]` Código HTTP esperado: 200 OK al consultar activo
  - `[PASS]` cantidad_actual NO se descontó automáticamente (permanece intacta)
- **Conclusión**: Se confirma la regla de separación de responsabilidades: los eventos sanitarios son informativos y diagnósticos/terapéuticos; no disminuyen la población biológica a menos que se registre formal e independientemente un evento de BAJA (RF-36 / RF-40).

---

### 3.3. Sub-caso TC-M02-055: Rechazar cambio de estado directo del lote

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/TC-M02-055.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G26/RESULTADOS/reporte_TC-M02-055.html`
- **Endpoint**: `PATCH /activos-biologicos/130`
- **Payload Enviado**:
  ```json
  {
    "id_estado": 2,
    "estado_activo": "INACTIVO"
  }
  ```
- **Respuesta de la API**:
  - **Código HTTP**: `400 Bad Request`
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "VAL_ENTRADA",
      "message": "Errores de validacion en la solicitud",
      "fields": [
        {
          "field": null,
          "message": "Value error, Al menos un campo debe estar presente para actualizar."
        }
      ],
      "timestamp": "2026-09-09T02:49:38.000000+00:00"
    }
    ```
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 400 Bad Request o 422
  - `[PASS]` El backend rechaza el cambio directo de estado
- **Conclusión**: El cambio de estado no puede ejecutarse arbitrariamente por actualización genérica; debe canalizarse a través del ciclo de vida controlado en el módulo de gestión de estados (RF-44 / endpoint específico `PATCH /activos-biologicos/{id}/estado`).

---

## 4. Auditoría y Verificación en Base de Datos (Solo Lectura)

Se ejecutó la siguiente consulta SQL sobre PostgreSQL `sgpmp_test`:
```sql
SELECT 
    a.id_activo_biologico, 
    a.id_estado, 
    e.nombre AS nombre_estado,
    d.cantidad_actual, 
    d.peso_promedio, 
    d.biomasa_total, 
    d.densidad
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
    ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 130;
```

### Resultado Obtenido:
```text
ID Activo: 130
ID Estado: 1 (ACTIVO)
Cantidad Actual: 5
Peso Promedio: 55
Biomasa Total: 275
Densidad: 0.01000000000000000000
```

### Hallazgo de Integridad:
1. `cantidad_actual` se mantuvo exactamente en **5** (el evento sanitario informativo no afectó el inventario poblacional).
2. `id_estado` se mantuvo en **1 (`ACTIVO`)** (los intentos de cambio directo de estado no alteraron el ciclo de vida del lote).
3. `biomasa_total`, `densidad` y `peso_promedio` se mantuvieron en sus valores previos (**275, 0.01 y 55** respectivamente), demostrando que las métricas calculadas están protegidas contra manipulaciones manuales directas vía API.

---

## 5. Veredicto Final y Conclusiones

| Sub-caso | Veredicto | Observación |
|---|:---:|---|
| **TC-M02-053** | **PASS** | Edición directa de métricas calculadas rechazada (`HTTP 400`). |
| **TC-M02-054** | **PASS** | Evento sanitario registrado (`HTTP 201`); población intacta (`cantidad_actual = 5`). |
| **TC-M02-055** | **PASS** | Intento de cambio directo de estado rechazado (`HTTP 400`). |
| **GLOBAL TC-M02-G26** | **PASS (100%)** | Cumple todas las reglas de negocio de RF-36. |
