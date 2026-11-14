# INFORME DE RESULTADOS DE PRUEBAS DE SEGURIDAD Y AUDITORÍA
## CASO AGRUPADO: TC-M02-G74 (RF-46: Historial de Eventos del Activo Biológico)

- **Fecha de Ejecución:** 2026-09-09
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Herramienta:** Pytest v9.0.3 + `pytest-html` v4.2.0
- **Suite de Prueba:** `tests/integration/test_rf46_seguridad_auditoria_integration.py`
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G74/RESULTADOS/reporte_TC-M02-125.html` (Subcaso TC-M02-125)
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G74/RESULTADOS/reporte_TC-M02-126.html` (Subcaso TC-M02-126)
- **Veredicto Global:** **PASS (100% DE PRUEBAS SUPERADAS — 3/3 TESTS APROBADOS)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G74** evalúa la seguridad a nivel de autorización de objetos (**OWASP API1:2023 - BOLA**) y la trazabilidad de auditoría (**ASVS V7 / RF-52**) en el endpoint `GET /activos-biologicos/{id_activo}/historial`:

| Subcaso | Enfoque de Evaluación | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-125** | Control de acceso por granja/rol (OWASP BOLA) | Rechazo con HTTP 403 o 404. Ningún dato del activo expuesto al Productor no autorizado. | `HTTP 404 Not Found` (`ACTIVO_NO_ENCONTRADO`). Cero filtración de datos de historial. | `reporte_TC-M02-125.html` | **PASS** |
| **TC-M02-126.1** | Auditoría de consulta exitosa (Admin) | Registro generado en `modulo2.bitacora_auditoria_m02` con tipo `HISTORIAL_CONSULTADO`, `EXITOSO` y hash SHA-256 de 64 caracteres. | Registro verificado con `id_bitacora=435`, `rf_origen='RF46'`, `resultado='EXITOSO'` y hash SHA-256 íntegro. | `reporte_TC-M02-126.html` | **PASS** |
| **TC-M02-126.2** | Auditoría de consultas denegadas e inexistentes | Rechazo formal controlado de intentos no autorizados y consultas sobre activos inexistentes sin excepciones 500. | Intentos BOLA e inexistentes rechazados con HTTP 404 estándar sin fugas de excepciones. | `reporte_TC-M02-126.html` | **PASS** |

---

## 2. Métricas de Ejecución en Pytest

| Métrica | Subcaso TC-M02-125 | Subcaso TC-M02-126 | Total Consolidado |
| :--- | :---: | :---: | :---: |
| **Pruebas ejecutadas** | 1 | 2 | 3 |
| **Pruebas aprobadas** | 1 (100%) | 2 (100%) | 3 (100%) |
| **Pruebas fallidas** | 0 | 0 | 0 |
| **Tiempo de ejecución** | 2.21 s | 5.37 s | 7.58 s |
| **Reporte HTML** | `reporte_TC-M02-125.html` | `reporte_TC-M02-126.html` | 2 archivos HTML individuales |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-125: Control de acceso por granja/rol (OWASP BOLA)

- **Actor Evaluado:** Productor (`m2m.nuevo@ejemplo.com`, `id_usuario = 35`, `id_rol = 2`).
- **Recurso Objetivo:** Lote de activo biológico `130` (asignado a Finca 1, infraestructura *Alevinera-01*).
- **Acción:** `GET /activos-biologicos/130/historial` con token JWT del Productor.
- **Respuesta Obtenida:**
  - **Código HTTP:** `404 Not Found`
  - **Payload:**
    ```json
    {
      "error_code": "ACTIVO_NO_ENCONTRADO",
      "message": "El activo biológico con id 130 no fue encontrado en el sistema.",
      "fields": [],
      "timestamp": "2026-09-09T21:11:57.783575+00:00"
    }
    ```
- **Análisis de Seguridad:**  
  El backend implementa el estándar OWASP de **Prevención de Enumeración de Recursos**: al consultar un recurso existente en otra finca sobre la cual el usuario no tiene permisos, el backend enmascara la existencia del activo respondiendo `404 Not Found` en lugar de confirmar su existencia con un `403`. Esto impide que atacantes mapeen identificadores válidos entre fincas ajenas.

---

### 3.2. Subcaso TC-M02-126: Auditoría de consultas al historial

- **Actor Evaluado:** Administrador (`admin@pecuaria.co`, `id_usuario = 1`, `id_rol = 1`).
- **Recurso Objetivo:** Lote `130`.
- **Acción:** `GET /activos-biologicos/130/historial` -> `HTTP 200 OK`.
- **Verificación de Auditoría:**  
  Consulta a `GET /activos-biologicos/auditoria?rf_origen=RF46&id_activo_biologico=130`:
  ```json
  {
    "id_bitacora": 435,
    "id_evento": "8326af1a-8bab-4b40-a90a-b97290db5c2f",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 130,
    "resultado": "EXITOSO",
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "timestamp_evento": "2026-09-09T21:11:59.821886Z",
    "hash_integridad": "4c3250fd65e251fd9a7c6d415f24404ed5d23f291a467e43de1e6871d2bd5ba7"
  }
  ```
- **Conformidad con ASVS V7:**
  - El evento fue registrado inmediatamente con marca temporal UTC de alta precisión.
  - El campo `hash_integridad` contiene el cálculo SHA-256 unívoco de los atributos del evento para garantizar no repudio e inmutabilidad.

---

## 4. Conclusiones y Veredicto Final

El caso agrupado **TC-M02-G74** demuestra que el endpoint de historial cumple plenamente con los lineamientos de autorización granular multi-finca (**OWASP API1: BOLA**) y con el registro inmutable de trazabilidad (**OWASP ASVS V7**).

**Veredicto Final:** **PASS (100%)**.
