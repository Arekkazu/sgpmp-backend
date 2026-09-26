# INFORME DE RESULTADOS DE PRUEBAS RBAC, SEGURIDAD Y VISIBILIDAD
## CASO AGRUPADO: TC-M02-G75 (RF-46: Historial de Eventos del Activo Biológico)

- **Fecha de Ejecución:** 2026-09-09
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Herramienta:** Pytest v9.0.3 + `pytest-html` v4.2.0
- **Suite de Pruebas:** `tests/integration/test_rf46_rbac_historial_integration.py`
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G75/RESULTADOS/reporte_TC-M02-206.html`
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G75/RESULTADOS/reporte_TC-M02-207.html`
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G75/RESULTADOS/reporte_TC-M02-208.html`
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G75/RESULTADOS/reporte_TC-M02-209.html`
- **Veredicto Global:** **PASS (100% DE PRUEBAS SUPERADAS — 4 DE 4 PASSED)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G75** evalúa la visibilidad por rol (RBAC), la resistencia a la escalación de privilegios (**OWASP API5**) y el aislamiento territorial (**OWASP API1: BOLA**) en el endpoint `GET /activos-biologicos/{id_activo}/historial`:

| Subcaso | Enfoque Evaluado | Actor y Parámetros | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-206** | Escalación vía `usuario_consulta_id` (OWASP API5) | Productor (`m2m.nuevo@ejemplo.com`) con `?usuario_consulta_id=1` sobre lote 130 (Finca 1) | HTTP 403 o 404 (nunca 200). Parámetro ignorado. | `HTTP 404 Not Found` (`ACTIVO_NO_ENCONTRADO`). Cero fuga de datos. Parámetro ignorado. | `reporte_TC-M02-206.html` | **PASS** |
| **TC-M02-207** | Veterinario consulta activo de su finca (Positivo) | Veterinario (`juan.carlos.qa133@sgpmp-test.com`) sobre activo en su propia finca (Finca 4 asignada temporalmente con fixture Setup/Teardown) | HTTP 200 OK con estructura canónica de historial | `HTTP 200 OK` (Historial retornado con `id_activo_biologico: 75`, `total_registros: 1`, y lista de eventos). Restitución exitosa en BD. | `reporte_TC-M02-207.html` | **PASS** |
| **TC-M02-208** | Veterinario consulta activo de finca ajena (BOLA) | Veterinario (`juan.carlos.qa133@sgpmp-test.com`) sobre lote 130 (Finca 1) | HTTP 403 o 404. Rechazo territorial. | `HTTP 404 Not Found` (`ACTIVO_NO_ENCONTRADO`). Aislamiento BOLA efectivo. | `reporte_TC-M02-208.html` | **PASS** |
| **TC-M02-209** | Administrador consulta activo global (Positivo) | Administrador (`admin@pecuaria.co`) sobre lote 130 (Finca 1) | HTTP 200 OK con historial completo sin restricción territorial | `HTTP 200 OK` (Historial retornado con total_registros y estructura canónica). | `reporte_TC-M02-209.html` | **PASS** |

---

## 2. Métricas de Ejecución en Pytest

| Subcaso | Enfoque de Prueba | Estado | Duración | Reporte Generado |
| :--- | :--- | :---: | :---: | :--- |
| **TC-M02-206** | OWASP API5 (Escalación de privilegios) | **PASSED** | 4.31 s | `reporte_TC-M02-206.html` |
| **TC-M02-207** | Funcional Veterinario (Activo Propio con Fixture Temporal) | **PASSED** | 5.43 s | `reporte_TC-M02-207.html` |
| **TC-M02-208** | OWASP API1 BOLA (Aislamiento Veterinario) | **PASSED** | 3.08 s | `reporte_TC-M02-208.html` |
| **TC-M02-209** | Funcional Administrador (Acceso Global) | **PASSED** | 4.60 s | `reporte_TC-M02-209.html` |
| **Total Suite** | **4 Subcasos evaluados individualmente** | **4/4 PASSED (100%)** | **17.42 s** | **4 Reportes HTML generados** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-206: Rechazar escalación de privilegios vía `usuario_consulta_id` (OWASP API5)

- **Vector de Prueba:** Inyección de query parameter `?usuario_consulta_id=1` (ID del Administrador) por parte del Productor (`m2m.nuevo@ejemplo.com`, ID 35) para intentar forzar la visibilidad del lote 130 de la Finca 1.
- **Petición:** `GET /activos-biologicos/130/historial?usuario_consulta_id=1` con header `Authorization: Bearer <token_productor>`.
- **Respuesta Obtenida:**
  - **Código HTTP:** `404 Not Found`
  - **Payload:**
    ```json
    {
      "error_code": "ACTIVO_NO_ENCONTRADO",
      "message": "El activo biológico con id 130 no fue encontrado en el sistema.",
      "fields": [],
      "timestamp": "2026-09-09T22:57:49.124501+00:00"
    }
    ```
- **Hallazgo de Seguridad:**  
  El backend descarta parámetros query no tipados ni autorizados en el DTO/Router. La identidad y el rol derivan inviolablemente de los claims criptográficos del JWT (`Depends(get_current_user)`). El intento de escalación fue bloqueado exitosamente.

---

### 3.2. Subcaso TC-M02-207: Veterinario consulta activo de su propia finca

- **Actor:** Veterinario `juan.carlos.qa133@sgpmp-test.com` (`id_usuario = 3`, `id_rol = 3`).
- **Mecanismo de Aislamiento y Transaccionalidad:**
  - Se implementó el fixture `veterinario_con_finca_temporal` con alcance de función (`scope="function"`).
  - **Setup:** Conexión a BD PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`). Se consultó y respaldó el `id_usuario` original de la Finca 4 (*Granja Piscícola La Esperanza*, valor original `id_usuario = 2`). Se ejecutó `UPDATE modulo9.fincas SET id_usuario = 3 WHERE id_finca = 4;` vinculando temporalmente la finca y sus activos (`id_activo = 75`) al Veterinario.
  - **Petición API:** `GET /activos-biologicos/75/historial` con token del Veterinario.
  - **Respuesta Obtenida:**
    - **Código HTTP:** `200 OK`
    - **Payload:**
      ```json
      {
        "id_activo_biologico": 75,
        "total_registros": 1,
        "pagina_actual": 1,
        "total_paginas": 1,
        "registros_por_pagina": 20,
        "registros": [
          {
            "categoria": "ESTADO",
            "fecha_evento": "2026-09-08T00:00:00Z",
            "descripcion": "Limpieza de activo de prueba inicial",
            "detalle_especifico": {
              "detalle_1": "ACTIVO",
              "detalle_2": "BAJA"
            },
            "usuario_responsable": "Carlos Rodríguez Pérez",
            "modulo_origen": "modulo2"
          }
        ]
      }
      ```
  - **Teardown (Garantizado en bloque `finally`):** Se restituyó el propietario original ejecutando `UPDATE modulo9.fincas SET id_usuario = 2 WHERE id_finca = 4;` y se verificó inmediatamente mediante `SELECT` que el valor retornó a `2`.
- **Hallazgo Funcional:**  
  El Veterinario puede consultar legítimamente el historial de eventos de los activos biológicos ubicados dentro de sus fincas asignadas, validando el comportamiento funcional positivo de RBAC territorial.

---

### 3.3. Subcaso TC-M02-208: Veterinario consulta activo de finca ajena (OWASP BOLA)

- **Vector de Prueba:** El Veterinario intenta consultar el lote 130 (ubicado en Finca 1, infraestructura 3, propiedad de `productor@pecuaria.co`).
- **Petición:** `GET /activos-biologicos/130/historial` con token del Veterinario.
- **Respuesta Obtenida:**
  - **Código HTTP:** `404 Not Found`
  - **Payload:**
    ```json
    {
      "error_code": "ACTIVO_NO_ENCONTRADO",
      "message": "El activo biológico con id 130 no fue encontrado en el sistema.",
      "fields": [],
      "timestamp": "2026-09-09T22:58:12.871034+00:00"
    }
    ```
- **Hallazgo de Seguridad:**  
  Aislamiento BOLA efectivo. El Veterinario recibe un error de recurso no encontrado, protegiendo tanto los datos zootécnicos del lote como la existencia misma del ID ante enumeración no autorizada.

---

### 3.4. Subcaso TC-M02-209: Administrador consulta cualquier activo (Acceso Global)

- **Actor:** Administrador `admin@pecuaria.co` (`id_usuario = 1`, `id_rol = 1`).
- **Petición:** `GET /activos-biologicos/130/historial` con token del Administrador.
- **Respuesta Obtenida:**
  - **Código HTTP:** `200 OK`
  - **Payload:**
    ```json
    {
      "id_activo_biologico": 130,
      "total_registros": 3,
      "pagina_actual": 1,
      "total_paginas": 1,
      "registros_por_pagina": 20,
      "registros": [
        {
          "categoria": "CRECIMIENTO",
          "fecha_evento": "2026-09-09T03:00:00Z",
          "descripcion": "Registro de medición de crecimiento (PESO: 58.0 gr)",
          "usuario_responsable": "Carlos Rodríguez Pérez",
          "modulo_origen": "modulo2"
        }
      ]
    }
    ```
- **Hallazgo Funcional:**  
  El Administrador goza de acceso global legítimo sobre cualquier activo biológico del sistema, independientemente de la finca de radicación.

---

## 4. Conclusiones y Veredicto Final

1. **Inmunidad a Escalación (OWASP API5):** La inyección de parámetros de identidad no altera el contexto de seguridad derivado del JWT.
2. **Defensa en Profundidad BOLA (OWASP API1):** Tanto el Productor como el Veterinario quedan estrictamente limitados a su frontera territorial.
3. **Acceso Funcional del Veterinario:** Con la asignación territorial activa, el Veterinario accede al historial de su activo biológico (`HTTP 200 OK`).
4. **Acceso Global de Administración:** El rol Administrador opera sin restricciones.
5. **Aislamiento de Pruebas:** El fixture garantiza que el estado de la base de datos TEST no sufre alteraciones residuales (restitución verificada en teardown).

**Veredicto Final:** **PASS (100% CONFORME — 4/4 SUB-CASOS PASSED)**.
