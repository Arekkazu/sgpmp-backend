# Diagnóstico Técnico Pre-Ejecución — TC-M03-G168 (Reintento 1)

| Metadato | Detalle |
| :--- | :--- |
| **Caso de Prueba** | `TC-M03-G168` (RF-62 / RF-57 / RF-63) |
| **Casos Agrupados** | `TC-M03-312` (Outlier), `TC-M03-316` (Gap), `TC-M03-317` (Serie Insuficiente), `TC-M03-323` (Calibración) |
| **Módulo** | Módulo 3 — Telemetría IoT / Plataforma Global |
| **Ambiente Evaluado** | TEST (`https://www.api.inmero.co/api-sgpmp-test`) |
| **Tipo de Diagnóstico** | Fase 1 — Inspección Estática + Sondeo Empírico Mínimo de Desbloqueo |
| **Fecha de Diagnóstico** | 2026-10-28 20:12:00 UTC |
| **QA Senior Responsable** | Antigravity QA Senior (SGPMP) |

---

## TAREA 0 — Estado de Archivos del TC (Nomenclatura y Limpieza)

### 0.1. Existencia del Directorio
* **Ruta:** `tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G168/`
* **Estado:** **EXISTE.** Contiene la suite de pruebas automatizada basada en Postman/Newman y artefactos de soporte.

### 0.2. Árbol de Contenido del Caso de Prueba
```text
tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G168/
│
├── .gitkeep
├── DISENO_Y_PRECONDICIONES.md       # Documento de diseño funcional y oráculos de prueba
├── build_collection.cjs             # Script generador/compilador de la colección Postman
├── ejecutar_tc_m03_g168.ps1         # Runner oficial PowerShell con captura y teardown de seguridad
├── test_tc_m03_g168.json            # Colección Newman ejecutable (64 requests, 65 scripts)
│
├── evidencias/
│   ├── .gitkeep
│   ├── console_run.log              # Log de consola histórico de la corrida V1 (2026-10-23)
│   └── run-20261028/                # Carpeta creada para el Reintento 1
│       └── DIAGNOSTICO_TC-M03-G168.md
│
└── resultados/
    ├── .gitkeep
    ├── resultado_TC-M03-G168.html   # Reporte htmlextra V1 (2026-10-23)
    ├── resultado_TC-M03-G168.json   # Resumen estructurado V1 (65 checkpoints)
    └── resultado_TC-M03-G168.md     # Informe ejecutivo V1
```

### 0.3. Verificación de Estructura Plana en `resultados/`
* El directorio `resultados/` es **completamente plano**.
* No contiene subcarpetas `run-YYYYMMDD/` ni carpetas en mayúsculas (`RESULTADOS/`).
* Contiene los archivos computables canónicos V1 (`resultado_TC-M03-G168.{html, json, md}`).

### 0.4. Verificación de `evidencias/`
* Se organiza formalmente bajo la convención `evidencias/run-20261028/`.
* No existen carpetas anómalas fuera de la jerarquía estándar.

### 0.5. Detección de Archivos `_reintento1` Previos
* **Búsqueda realizada:** `find ... -name "*reintento1*"`
* **Resultado:** **0 archivos.** No existen artefactos residuales ni ejecuciones intermedias no documentadas de Reintento 1.

---

## TAREA A — ¿Está el Fix de INC-M03-123-G167 Presente?

### A.1. Inspección Estática de Código Fuente
Se inspeccionó la cadena completa de creación de sensores:

1. **Modelo ORM (`src/configuration/infrastructure/models/sensor_model.py:45`):**
   ```python
   es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
   ```
   - El campo `es_activo` **no** tiene `default=True` ni `server_default=text("true")` a nivel de definición SQLAlchemy.
2. **DTO de Entrada (`src/configuration/infrastructure/dto/registrar_sensor_dto.py:13-16`):**
   ```python
   class RegistrarSensorDTO(BaseDTO):
       nombre: str
       categoria: Optional[CategoriaSensor] = None
   ```
   - No expone `es_activo` (diseño correcto, el cliente de API no debe decidir el estado inicial).
3. **Caso de Uso (`src/configuration/application/use_cases/dispositivos_iot/registrar_sensor_use_case.py:51-55`):**
   ```python
   sensor = Sensor.crear(
       nombre=dto.nombre,
       id_dispositivo_iot=id_dispositivo_iot,
       categoria=dto.categoria,
   )
   ```
4. **Entidad de Dominio (`src/configuration/domain/entities/sensor.py:27-32`):**
   ```python
   @classmethod
   def crear(cls, *, nombre: str, id_dispositivo_iot: int, categoria: Optional[str] = None) -> Sensor:
       return cls(
           nombre=nombre,
           id_dispositivo_iot=id_dispositivo_iot,
           es_activo=True,
           categoria=categoria,
       )
   ```
   - **Hallazgo clave:** La fábrica `Sensor.crear()` **sí inicializa explícitamente `es_activo=True`**.
5. **Repositorio (`src/configuration/infrastructure/repositories/sensor_repository.py:34-39`):**
   ```python
   orm = SensorModel(
       nombre=sensor.nombre,
       id_dispositivo_iot=sensor.id_dispositivo_iot,
       es_activo=sensor.es_activo,  # Pasa True al modelo ORM
       categoria=sensor.categoria,
   )
   ```
   - El repositorio mapea `es_activo` desde la entidad de dominio. No llega nulo a PostgreSQL.
   - En línea 45: `raise_from_db_error(exc, {})` recibe diccionario vacío.
6. **Traductor de Errores (`src/shared/db_error_translator.py`):**
   - No mapea `NotNullViolation` de psycopg2; si ocurriera una violación NOT NULL, caería a `InfrastructureError` (500 ERROR_INTERNO).
7. **Trazabilidad Git (Commit Clave Desplegado):**
   - El 2026-10-25 14:50 UTC, el commit `d3d6ec39` (*"fix(rf22-mod9): registrar sensor sin INSERT ... RETURNING bajo RLS (INC-M03-124-G01)"*) solucionó la causa raíz que provocaba el HTTP 500 en la creación de sensores (`pol_sensores_select` fallaba en el `INSERT ... RETURNING`).
   - Se configuró `{'schema': 'modulo9', 'implicit_returning': False}` en `SensorModel`.
   - Este commit fue mergeado a la rama `test` en el commit `daefc3a5` el **2026-10-26 22:30:06 UTC** y desplegado en el ambiente `TEST`.

### A.2. Verificación Empírica Mínima (Sondeo Controlado)
Se ejecutó un sondeo de verificación transaccional aislado contra el ambiente `TEST`:
* **ID de Corrida Sandbox:** `diag-sensor-check-34685720`
* **Credenciales:** Administrador de pruebas autenticado vía JWT.
* **Dispositivo Objetivo:** Dispositivo IoT existente `id_dispositivo_iot: 148` (tipo `SENSOR_AMBIENTAL`, `categoria: SENSOR`).
* **Petición HTTP:**
  ```http
  POST /api-sgpmp-test/configuracion/dispositivos-iot/148/sensores
  Headers:
    Authorization: Bearer <jwt_admin>
    X-Test-Run-Id: diag-sensor-check-34685720
    X-Sandbox-Secret: <sandbox_secret>
    Content-Type: application/json
  Body:
    {"nombre": "Diag Sensor 433a6f", "categoria": "TEMPERATURA"}
  ```
* **Respuesta Obtenida:**
  - **Código HTTP:** **`201 Created`**
  - **Payload Retornado:**
    ```json
    {
      "id_sensores": 1028,
      "nombre": "Diag Sensor 433a6f",
      "id_dispositivo_iot": 148,
      "es_activo": true,
      "categoria": "TEMPERATURA"
    }
    ```
* **Teardown Inmediato:**
  ```http
  DELETE /api-sgpmp-test/test-control/runs/diag-sensor-check-34685720
  Respuesta: HTTP 200 OK {"status": "ok", "message": "Rollback exitoso"}
  ```

### A.3. Veredicto de INC-M03-123-G167
* **Veredicto:** **RESUELTO / DESBLOQUEADO EN TEST.**
* La creación de sensores opera correctamente con código HTTP 201 y asignación íntegra de `es_activo = true`.
* La autosiembra de sensores ya **no abortará** con HTTP 500.

---

## TAREA B — ¿El Script del Test está en Condiciones?

El caso `TC-M03-G168` está implementado como una suite de integración automatizada sobre **Postman / Newman** (`test_tc_m03_g168.json`) con runner PowerShell dedicado (`ejecutar_tc_m03_g168.ps1`).

### B.1. Checklist de Calidad Newman
- [x] **Pre-request de colección:** Genera `run_id` aleatorio con prefijo `test-` si no fue provisto por el entorno.
- [x] **Inyección de Sandbox:** Inyecta automáticamente los encabezados `X-Test-Run-Id` y `X-Sandbox-Secret` en el 100% de los requests salientes.
- [x] **DEF-04 (Autenticación Única):** Cumplido estrictamente. Se ejecuta exactamente **un solo** `POST /sesiones/` en `00.01-Login-Admin`; el token se almacena en la variable de colección `{{token_admin}}` y se reutiliza en todos los requests subsecuentes.
- [x] **Teardown Transaccional:** Contiene la carpeta `99-Teardown` con la petición `99.01-Rollback-Sandbox` (`DELETE /test-control/runs/{{run_id}}`), respaldada además por el bloque `finally` de `ejecutar_tc_m03_g168.ps1`.
- [x] **Seguridad y Anti-Hardcode:** No existen contraseñas ni tokens estáticos en el JSON. Se resuelven dinámicamente mediante `{{admin_password}}`, `{{sandbox_secret}}` y `{{broker_token}}`.
- [x] **Validación Sintáctica JS (`node --check`):** Se extrajeron y compilaron los **65 scripts** de pre-request y test embebidos en el JSON. **Resultado: 65/65 aprobados (0 errores sintácticos)**.
- [x] **Cobertura de Subcasos:**
  - `TC-M03-312` (Outlier estadístico):
    * `312a`: Desviación extrema ($25.50$) $\rightarrow$ Valida `outlier_estadistico.activo = true`, índice 80, clasificación `APTO`.
    * `312b`: Rango normal ($23.50$) $\rightarrow$ Valida ausencia de flag, índice 100, `APTO`.
    * `312c`: Frontera exacta ($23.51$) $\rightarrow$ Valida oráculo ajustado a $\sigma$ muestral (índice 100, sin flag).
  - `TC-M03-316` (Gap temporal anómalo):
    * `316a`: Salto de 25 min (>2× frecuencia).
    * `316b`: Salto de 20 min.
    * `316c`: Salto con periodo de inactividad.
  - `TC-M03-317` (Serie insuficiente):
    * 3 lecturas previas + 1 evaluada ($N=4 < 20$) $\rightarrow$ Valida `serie_insuficiente = true`, `indice_calidad = null`, clasificación `INDETERMINADA`.
  - `TC-M03-323` (Calibración no disponible):
    * `323a`: Con calibración previa registrada.
    * `323b`: Sin calibración previa registrada $\rightarrow$ Valida `calibracion_no_disponible = true`.
- [x] **Generación de Reportes:** Genera reporte HTML compatible mediante reporter `htmlextra` en `resultados/resultado_TC-M03-G168.html`.

### B.2. Resultado del Script
* **Estado:** **LISTO PARA EJECUCIÓN.**
* El script está íntegramente construido, sintácticamente validado y alineado con los estándares del marco de pruebas SGPMP.

---

## TAREA C — Riesgos de Contaminación

* **C.1. Estrategia de Datos:** **Autosuficiencia 100%**. La suite crea dinámicamente en su fase `00-Preflight-Autosiembra` una finca exclusiva, un área productiva exclusiva y dispositivos/sensores dedicados para cada sub-escenario (`dev_id_312a`, `dev_id_312b`, `dev_id_316a`, etc.).
* **C.2. Dependencia de Semillas Preexistentes:** **Ninguna**. No depende de registros fijos de base de datos ni está afectada por `INC-M03-101-G164`. Solo descubre metadatos de lectura (`id_tipo_dispositivo` y `tipo_area`).
* **C.3. Aislamiento de Sensores Contaminados:** No utiliza los sensores legacy 466 ni 550.
* **C.4. Garantía de Teardown:** Toda la actividad ocurre bajo `X-Test-Run-Id`. Al finalizar, el sandbox ejecuta `DELETE /test-control/runs/{{run_id}}` revirtiendo en PostgreSQL todas las filas insertadas.
* **C.5. Nivel de Riesgo de Contaminación:** **0% (Inocuo)**.

---

## TAREA D — Veredicto del Diagnóstico

### D.1. ¿El INC-M03-123-G167 sigue presente en TEST?
**NO.** Se verificó empíricamente mediante sondeo en vivo que el backend responde `HTTP 201 Created` al registrar sensores. El bug de RLS fue subsanado en el commit `d3d6ec39` y desplegado en TEST.

### D.2. ¿El script del test está listo?
**SÍ.** La colección `test_tc_m03_g168.json` y su runner `ejecutar_tc_m03_g168.ps1` están completamente implementados, verificados y con 0 errores de sintaxis en sus 65 scripts JS.

### D.3. ¿Se puede ejecutar el Reintento 1?
**SÍ.** Se autoriza el avance a Fase 3 (Ejecución única del Reintento 1).

### D.4. Veredicto Esperado de la Corrida
* La suite completará exitosamente la autosiembra (superando el bloqueo de V1).
* Se evaluarán los 4 subcasos. El subcaso `TC-316c` podría registrar un fallo esperado si no existe soporte de periodos de inactividad por API, lo cual reflejará fielmente el estado del requerimiento sin comprometer la validez del diagnóstico.

### D.5. Estado de Artefactos de Prueba
* Los scripts existen y están listos. No se requiere creación desde cero.

### D.6. Nota sobre SLA y Gestión de Incidencias
* El ticket `INC-M03-123-G167` (detectado el 23/10/2026) figuraba administrativamente abierto y vencido por SLA.
* Con la evidencia empírica de este diagnóstico (**Sensor ID 1028 creado con HTTP 201**), se solicita a la mesa de Desarrollo actualizar el estado del ticket a **RESUELTO / VERIFICADO EN TEST**.

---

### Resumen Conclusivo
La precondición bloqueante que detuvo la corrida V1 del 23 de octubre ha sido superada en el backend de TEST. El caso de prueba `TC-M03-G168` queda declarado **HABILITADO** para proceder a su re-ejecución formal.
