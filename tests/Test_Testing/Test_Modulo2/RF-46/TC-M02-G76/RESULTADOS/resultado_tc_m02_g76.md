# INFORME DE RESULTADOS DE PRUEBAS DE HISTORIAL, PAGINACIÓN E INMUTABILIDAD
## CASO AGRUPADO: TC-M02-G76 (RF-46: Historial de Eventos del Activo Biológico)

- **Fecha de Ejecución:** 2026-09-09
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** `postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test`
- **Herramientas Utilizadas:**
  - **Newman:** v6.2.2 + `newman-reporter-htmlextra` v1.23.1
  - **Pytest:** v9.0.3 + `pytest-html` v4.2.0
- **Suites Ejecutadas:**
  - Colección Newman: `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/test_tc_m02_g76.json` (Folders `TC-M02-210` y `TC-M02-212`)
  - Suite Pytest: `tests/integration/test_rf46_limite_paginacion_integration.py` (Subcaso `TC-M02-211`)
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/reporte_TC-M02-210.html` (70 KB)
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/reporte_TC-M02-211.html` (33 KB)
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/reporte_TC-M02-212.html` (157 KB)
- **Documentos y Scripts de Gestión Asociados:**
  - **Reporte Formal de Defecto:** [`tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/defecto_INC-M02-G76-01.md`](file:sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/defecto_INC-M02-G76-01.md)
  - **Script de Re-test:** [`tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/retest_tc_m02_210.ps1`](file:sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/retest_tc_m02_210.ps1)
  - **Script de Contingencia y Limpieza:** [`tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/cleanup_tc_m02_g76.sql`](file:sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/cleanup_tc_m02_g76.sql)
- **Veredicto Global:** **PASS PARCIAL CON DEFECTO DOCUMENTADO (2 DE 3 SUB-CASOS PASSED, 1 DEFECTO FUNCIONAL DETECTADO)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G76** evalúa la estabilidad del endpoint `GET /activos-biologicos/{id_activo}/historial` ante filtros sin resultados (Flujo E-04), el comportamiento matemático exacto en fronteras de paginación (500 vs 501 registros) y la inmutabilidad/seguridad del historial contra métodos de escritura HTTP (`POST`, `PATCH`, `DELETE`):

| Subcaso | Enfoque Evaluado | Herramienta | Parámetros / Operación | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-210** | Filtro sin resultados (Flujo E-04) | Newman | `GET ?categoria_evento=BAJA` sobre activo 130 | HTTP 200 OK, `total_registros: 0`, `registros: []`, y mensaje informativo presente. | HTTP 200 OK, `total_registros: 0`, `registros: []`. Falla aserción de mensaje informativo (campo ausente en esquema). | `reporte_TC-M02-210.html` | **FAIL (Defecto INC-M02-G76-01)** |
| **TC-M02-211** | Límite de paginación (500 vs 501 registros) | Pytest | Setup/Teardown sintético (año 2030) con `page_size=100` | 500 regs -> 5 págs (100 c/u); 501 regs -> 6 págs; pág 6 con 1 reg. Teardown limpio. | Validaciones matemáticas cumplidas al 100%. Teardown verificado en BD (0 huérfanos). | `reporte_TC-M02-211.html` | **PASS** |
| **TC-M02-212** | Rechazo de escritura e inmutabilidad | Newman | `POST`, `PATCH`, `DELETE` sobre `/historial` | HTTP 405 Method Not Allowed, header `Allow: GET`. Historial inalterado tras ataques. | HTTP 405 en los 3 métodos con header `Allow: GET`. Historial verificado idéntico (25 regs). | `reporte_TC-M02-212.html` | **PASS** |

---

## 2. Métricas de Ejecución

| Subcaso | Herramienta | Solicitudes / Tests | Aserciones | Exitosas | Fallidas | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-210** | Newman | 2 requests | 5 aserciones | 4 | 1 | 2.0 s | **FAIL (Con Defecto)** |
| **TC-M02-211** | Pytest | 3 requests API + 5 operaciones BD | 12 validaciones internas | 12 | 0 | 11.41 s | **PASSED** |
| **TC-M02-212** | Newman | 6 requests | 11 aserciones | 11 | 0 | 2.7 s | **PASSED** |
| **Total Suite** | **Newman + Pytest** | **11 requests** | **28 aserciones / checks** | **27** | **1** | **16.11 s** | **96.4% Éxito** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-210: Consultar historial con filtro sin resultados (Flujo E-04)

- **Vector de Prueba:** Consulta de historial aplicando un filtro de categoría (`categoria_evento=BAJA`) que no tiene registros asociados en el lote 130.
- **Petición HTTP:** `GET /activos-biologicos/130/historial?categoria_evento=BAJA` con cabecera `Authorization: Bearer <token_admin>`.
- **Respuesta Obtenida:**
  - **Código HTTP:** `200 OK`
  - **Payload Recibido:**
    ```json
    {
      "id_activo_biologico": 130,
      "total_registros": 0,
      "pagina_actual": 1,
      "total_paginas": 0,
      "registros_por_pagina": 20,
      "registros": []
    }
    ```
- **Aserciones Ejecutadas en Newman:**
  - `[TC-M02-210] Autenticación exitosa (200 OK)`: **PASS**
  - `[TC-M02-210] Estado HTTP 200 OK`: **PASS**
  - `[TC-M02-210] total_registros es 0`: **PASS**
  - `[TC-M02-210] registros es array vacío`: **PASS**
  - `[TC-M02-210] Mensaje informativo presente`: **FAIL**  
    *Detalle del error:* `AssertionError: expected '' to include 'no se encontraron eventos'`.
- **Análisis de Causa Raíz:**  
  El contrato funcional del caso de uso (CU10A / RF-46 Flujo Alternativo E-04) especifica que cuando una consulta con filtros no arroja resultados, el sistema debe responder con un mensaje informativo indicando *"No se encontraron eventos para los filtros especificados"*. Sin embargo, el esquema Pydantic backend `HistorialActivoResponse` (`src/biological_assets/infrastructure/schema/activo_biologico_schema.py`) no contempla el campo opcional `mensaje: Optional[str] = None`. En consecuencia, el backend devuelve el objeto de paginación vacío sin el mensaje estipulado en la especificación.

---

### 3.2. Subcaso TC-M02-211: Validación de Límite de Paginación Exacta (500 vs 501 registros)

- **Vector de Prueba:** Simulación de frontera matemática en la paginación con `page_size=100`.
- **Estrategia Técnica de Aislamiento:**
  - Se utilizó la tabla `modulo2.indicadores_zootecnicos` vinculada al lote 130 con fechas aisladas en el año 2030 (`[2030-01-01, 2030-01-02)`).
  - Esta tabla nutre la vista unificada `modulo2.vw_rf46_historial_completo_activo` con categoría `'INDICADOR'` y no posee triggers de inmutabilidad `IMMUTABLE_RECORD` (presentes en `modulo2.eventos_activos`), lo que permitió un teardown atómico y limpio sin requerir privilegios de superusuario.
- **Fases de Ejecución y Validaciones:**
  1. **Lote Inicial (500 registros):**
     - Inserción en lote mediante `execute_values`.
     - `GET /activos-biologicos/130/historial?fecha_inicio=2030-01-01&page_size=100&pagina=1`:
       - `status_code`: `200 OK`
       - `total_registros`: `500`
       - `total_paginas`: `5` ($\lceil 500 / 100 \rceil = 5$)
       - `pagina_actual`: `1`
       - `len(registros)` en página 1: `100`
  2. **Inserción de Frontera (Registro 501):**
     - Inserción de 1 registro adicional con `rango_fecha = '[2030-02-01, 2030-02-02)'`.
     - `GET /activos-biologicos/130/historial?fecha_inicio=2030-01-01&page_size=100&pagina=1`:
       - `status_code`: `200 OK`
       - `total_registros`: `501`
       - `total_paginas`: `6` ($\lceil 501 / 100 \rceil = 6$)
       - `len(registros)` en página 1: `100`
  3. **Verificación de Página Final (Página 6):**
     - `GET /activos-biologicos/130/historial?fecha_inicio=2030-01-01&page_size=100&pagina=6`:
       - `status_code`: `200 OK`
       - `pagina_actual`: `6`
       - `total_paginas`: `6`
       - `len(registros)` en página 6: `1` (registro remanente exacto).
  4. **Teardown y Limpieza:**
     - Se ejecutó `DELETE FROM modulo2.indicadores_zootecnicos WHERE id_activo_biologico = 130 AND lower(rango_fecha) >= '2030-01-01'::date;`.
     - Consulta de verificación posterior confirmó: **0 registros sintéticos remanentes** en la base de datos TEST.
- **Resultado:** **PASSED (100% de aserciones conformes)**.

---

### 3.3. Subcaso TC-M02-212: Rechazo de métodos de escritura en endpoint de historial

- **Vector de Prueba:** Envío deliberado de solicitudes HTTP de modificación y borrado (`POST`, `PATCH`, `DELETE`) hacia la ruta de solo lectura `/activos-biologicos/{id_activo}/historial`.
- **Comprobaciones Realizadas:**
  1. **Línea Base Inicial:** `GET /activos-biologicos/130/historial` retornó `HTTP 200 OK` con un total de 25 registros reales preexistentes.
  2. **Intento POST:** `POST /activos-biologicos/130/historial` con payload JSON sintético.
     - **Código HTTP:** `405 Method Not Allowed`
     - **Cabecera `Allow`:** `GET`
     - **Cuerpo:** `{"detail": "Method Not Allowed"}`
  3. **Intento PATCH:** `PATCH /activos-biologicos/130/historial` con payload de actualización.
     - **Código HTTP:** `405 Method Not Allowed`
     - **Cabecera `Allow`:** `GET`
     - **Cuerpo:** `{"detail": "Method Not Allowed"}`
  4. **Intento DELETE:** `DELETE /activos-biologicos/130/historial`.
     - **Código HTTP:** `405 Method Not Allowed`
     - **Cabecera `Allow`:** `GET`
     - **Cuerpo:** `{"detail": "Method Not Allowed"}`
  5. **Verificación Dinámica de Inmutabilidad:**
     - Inmediatamente después de los 3 intentos fallidos, se ejecutó una nueva consulta `GET /activos-biologicos/130/historial`.
     - **Resultado:** El historial se mantuvo exactamente en 25 registros y la estructura de los eventos no sufrió alteración alguna.
- **Resultado:** **PASSED (11 de 11 aserciones conformes)**.

---

## 4. No Conformidades Residuales

A partir de la ejecución completa y el análisis exhaustivo de los 3 subcasos de prueba, se certifica el siguiente estado de conformidad del sistema:

1. **Filtrado sin Resultados (TC-M02-210):** El filtrado sin resultados opera de forma segura y consistente a nivel de base de datos y controlador (código HTTP `200 OK`, colección vacía `registros: []`, y contador `total_registros: 0`). El único punto de no conformidad es la ausencia del atributo `mensaje` en el JSON de respuesta.
2. **Límite de Paginación y Frontera Matemática (TC-M02-211):** La funcionalidad de paginación opera al **100% de conformidad**, respetando de forma matemática y estricta el límite de páginas tanto para 500 como para 501 registros sin discrepancias numéricas ni pérdida de registros.
3. **Rechazo de Métodos de Escritura e Inmutabilidad (TC-M02-212):** La protección de solo lectura opera al **100% de conformidad**. Los métodos no permitidos (`POST`, `PATCH`, `DELETE`) son invariablemente bloqueados con `HTTP 405 Method Not Allowed`, se provee la cabecera `Allow: GET`, y los registros existentes se mantienen completamente inmutables.
4. **Unicidad del Hallazgo:** El defecto **`INC-M02-G76-01` es el único hallazgo / defecto detectado** en la ejecución de todo el caso agrupado **TC-M02-G76**.

---

## 5. Criterios de Cierre del Caso Agrupado

El caso agrupado **TC-M02-G76** permanecerá en estado **PASS PARCIAL** hasta que el subcaso **TC-M02-210** transicione satisfactoriamente al estado **PASS**.

Para proceder con el cierre formal y definitivo de este caso agrupado se requerirá el cumplimiento irrestricto de las siguientes 4 condiciones:

1. **Despliegue del Fix en TEST:** Despliegue de la corrección en el entorno TEST (`HistorialActivoResponse` con `mensaje: Optional[str] = None` y lógica de asignación en router/use-case).
2. **Ejecución del Retest Automatizado:** Ejecución exitosa del script [`retest_tc_m02_210.ps1`](file:sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/retest_tc_m02_210.ps1), alcanzando `5/5 aserciones PASSED` y código de salida `0` (Exit code 0).
3. **Regeneración del Reporte HTML:** Actualización del reporte [`reporte_TC-M02-210.html`](file:sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/RESULTADOS/reporte_TC-M02-210.html) evidenciando el 100% de aserciones conformes.
4. **Aprobación Formal de QA:** Revisión y firma de cierre formal por parte del equipo de QA en `defecto_INC-M02-G76-01.md`.

---

## 7. Conclusiones y Veredicto Final

1. **Robustez de Paginación (TC-M02-211):**  
   El algoritmo de paginación y cálculo de páginas totales del backend (`ceil(total / page_size)`) funciona de manera impecable en la frontera matemática de 500 a 501 registros, garantizando la consistencia de los datos en consultas masivas.
2. **Inmutabilidad y Protección de Métodos HTTP (TC-M02-212):**  
   El endpoint `/activos-biologicos/{id_activo}/historial` rechaza consistentemente cualquier método de escritura (`POST`, `PATCH`, `DELETE`) con `HTTP 405 Method Not Allowed`, informa apropiadamente la cabecera `Allow: GET`, y preserva la integridad absoluta del historial zootécnico.
3. **Consistencia de Filtrado (TC-M02-210):**  
   El filtrado vacío retorna el código de estado apropiado (`HTTP 200 OK`) y una colección vacía (`registros: []`), detectándose la omisión del campo `mensaje` estipulado en el flujo E-04 (documentado como `INC-M02-G76-01`).
4. **Limpieza e Integridad de la Base de Datos:**  
   El procedimiento de prueba automatizada garantizó la remoción total de los 501 registros sintéticos generados, dejando la base de datos TEST en su estado original sin registros huérfanos.

**Veredicto Final:** **CONFORME CON OBSERVACIÓN (PASS PARCIAL — 2/3 SUB-CASOS PASSED, 1 DEFECTO DOCUMENTADO ABIERTO)**.
