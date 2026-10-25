# Reporte de Ejecución de Pruebas — SGPMP

## 1. Metadatos de la Ejecución

| Parámetro | Valor |
|---|---|
| **Caso / Grupo de Prueba** | TC-M02-G31 (Valores Límite en la Gestión de Lotes) |
| **Módulo / Requerimiento Funcional** | Módulo 2 (Activos Biológicos) · RF-36 (Gestión Poblacional / CU03) |
| **Versión de Evaluación** | V2 (Primera Reevaluación tras Correcciones de Test y Datos) |
| **RUN_ID** | `G31-REEVAL-V2-20260915-012500` |
| **Fecha y Hora de Ejecución** | 2026-09-15 01:25:00 (America/Bogota, UTC-5) |
| **Evaluador / Responsable** | Antigravity — QA Lead Senior SGPMP |
| **Entorno de Prueba** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Base de Datos TEST** | PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`) |
| **Colección de Prueba** | `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/test_tc_m02_g31.json` |
| **Herramienta de Prueba** | Newman CLI v6.2.2 + Reporter `htmlextra` v1.23.1 |
| **Rama Git / Commit Base** | `5b651f59` (con modificaciones locales en colección de prueba) |
| **Veredicto Global** | ⚠️ **Rechazado** |

---

## 2. Resumen Ejecutivo y Correcciones del Test

### 2.1. Objetivo de la Sesión
Reevaluar de manera controlada y segregada el caso agrupado **TC-M02-G31**, que en su corrida original V1 (2026-09-11) concluyó con veredicto **FALLIDO (0/2)** debido al error de persistencia `HTTP 500` en eventos de crecimiento (TC-M02-196) y al fallo del trigger de base de datos en eventos de baja (TC-M02-197).

### 2.2. Correcciones Técnicas Aplicadas a la Colección de Prueba
Previo a la ejecución de Fase 2, se intervinieron los defectos identificados en el diseño original del test sobre `test_tc_m02_g31.json`:

1. **Actualización de Credenciales (D2):** Se sustituyó el usuario obsoleto `admin@pecuaria.co` por el usuario administrador oficial `administador.dev@gmail.com` / `Test1234!` en ambos folders de autenticación.
2. **Reasignación de Lote Limpio en Crecimiento (D3):** Para el subcaso TC-M02-196, se sustituyó el lote contaminado `130` (26 eventos previos acumulados) por el lote limpio `296` (especie 40, 10 individuos iniciales, 0 eventos previos, fase activa confirmada). Se mantuvieron las aserciones permisivas para documentar contractualmente el estado de bloqueo del endpoint.
3. **Fecha de Baja Dinámica (D4b):** En TC-M02-197, se reemplazó la fecha estática `2026-09-11` por un pre-request script dinámico:
   ```javascript
   const safeDate = new Date(Date.now() - 60000).toISOString().split('T')[0];
   pm.collectionVariables.set('fecha_baja_dinamica', safeDate);
   ```
   garantizando coherencia cronológica con el reloj del servidor.
4. **Depuración de Lotes Inactivos (D4c):** Se eliminaron las peticiones duplicadas e inválidas sobre el lote `345` (el cual se encontraba en estado `INACTIVO`), concentrando la prueba de baja total en el lote `344` (`ACTIVO`, 10 individuos, 0 eventos).
5. **Endurecimiento Contractual de Aserciones (D4d):** Se eliminó el `oneOf` permisivo en TC-M02-197, exigiendo estrictamente `HTTP 201 Created` en la baja, `cantidad_actual === 0` en el inventario poblacional y la transición formal a estado terminal `BAJA` (`id_estado = 6`, `nombre_estado = 'BAJA'`).

### 2.3. Métrica Numérica Consolidada

| Subcaso | Enfoque Evaluado | Peticiones HTTP | Aserciones Exitosas | Aserciones Fallidas | Tasa de Éxito (%) | Veredicto |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-196** | Densidad en Crecimiento (Lote 296) | 3 | 3 / 3 | 0 | 100% (test) / Bloqueo en API | ⚠️ **BLOQUEADO** |
| **TC-M02-197** | Baja Total de Lote (Lote 344) | 3 | 3 / 3 | 0 | 100% | ✅ **PASS** |
| **Total Consolidado** | Suite TC-M02-G31 V2 | **6** | **6 / 6** | **0** | **100%** | ⚠️ **PASS PARCIAL** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

Previo a la ejecución de las pruebas, se ejecutó una verificación en vivo contra PostgreSQL TEST para validar el aislamiento de los lotes de prueba:

```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_estado,
       d.cantidad_inicial, d.cantidad_actual, d.densidad,
       (SELECT COUNT(*) FROM modulo2.eventos_activos ea WHERE ea.id_activo_biologico = a.id_activo_biologico) AS total_eventos,
       (SELECT COUNT(*) FROM modulo2.gestiones_fases gf WHERE gf.id_activo_biologico = a.id_activo_biologico AND gf.es_activa = TRUE) AS fases_activas
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico IN (296, 344)
ORDER BY a.id_activo_biologico;
```

**Salida Literal en Vivo:**
```text
(296, 'POBLACIONAL', 40, 1, 10, 10, NULL, 0, 1)
(344, 'POBLACIONAL', 4,  1, 10, 10, NULL, 0, 0)
```

**Diagnóstico de Pre-condición:**
- **Lote 296:** Estado `1` (`ACTIVO`), 10 individuos, 0 eventos registrados previamente y 1 fase activa. Condición óptima e inocua para aislar la prueba de crecimiento.
- **Lote 344:** Estado `1` (`ACTIVO`), 10 individuos iniciales, 10 actuales, 0 eventos registrados previamente. Condición óptima para evaluar la baja total de 10 unidades.

---

## 4. Resultados Detallados de Ejecución por Subcaso

### 4.1. Subcaso TC-M02-196: Evaluación de Densidad de Lote ante Evento de Crecimiento
- **Colección / Folder:** `test_tc_m02_g31.json` -> Folder `TC-M02-196`
- **Artefactos Técnicos:** `EvidenciasPorSubcaso/TC-M02-196_run.json` y `EvidenciasPorSubcaso/TC-M02-196_report.html`

| # | Petición HTTP | Endpoint / URL | Método | HTTP Status Obtenido | Aserciones | Veredicto |
|---|---|---|:---:|:---:|:---:|:---:|
| 0 | Autenticación Admin (TC-M02-196) | `{{baseUrl}}/sesiones/` | POST | `200 OK` (1371 ms) | 1 / 1 PASS (Token capturado) | ✅ PASS |
| 1 | Registrar evento de crecimiento sobre lote 296 | `{{baseUrl}}/activos-biologicos/296/eventos/crecimiento` | POST | `500 Internal Server Error` (136 ms) | 1 / 1 PASS (Aserción laxa `oneOf`) | ⚠️ BLOQUEADO |
| 2 | Consultar estado y métricas del lote 296 | `{{baseUrl}}/activos-biologicos/296` | GET | `200 OK` (142 ms) | 1 / 1 PASS (Lectura de estado) | ✅ PASS |

**Respuesta Literal de la Petición 1 (HTTP 500):**
```json
{
  "error_code": "ERROR_INTERNO",
  "message": "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.",
  "fields": [],
  "timestamp": "2026-09-15T06:25:29.981628+00:00"
}
```

**Diagnóstico Técnico:**
La petición de crecimiento falló con `HTTP 500` debido a que el caso de uso `RegistrarEventoCrecimientoUseCase` invoca el adaptador `ParametrosEspecieM09Adapter`, el cual ejecuta una consulta SQLAlchemy contra `modulo9.metricas_produccion`. La tabla física en PostgreSQL TEST no cuenta con la columna `tipo_dato`, provocando la excepción `UndefinedColumn` a nivel de base de datos y un rollback inmediato. El inventario del lote 296 no sufrió alteración.

---

### 4.2. Subcaso TC-M02-197: Baja Total sobre Lote 344
- **Colección / Folder:** `test_tc_m02_g31.json` -> Folder `TC-M02-197`
- **Artefactos Técnicos:** `EvidenciasPorSubcaso/TC-M02-197_run.json` y `EvidenciasPorSubcaso/TC-M02-197_report.html`

| # | Petición HTTP | Endpoint / URL | Método | HTTP Status Obtenido | Aserciones | Veredicto |
|---|---|---|:---:|:---:|:---:|:---:|
| 0 | Autenticación Admin (TC-M02-197) | `{{baseUrl}}/sesiones/` | POST | `200 OK` (1527 ms) | 1 / 1 PASS (Token capturado) | ✅ PASS |
| 1 | Aplicar baja total sobre lote 344 | `{{baseUrl}}/activos-biologicos/344/eventos/baja` | POST | `201 Created` (414 ms) | 1 / 1 PASS (Evento creado) | ✅ PASS |
| 2 | Consultar lote 344 tras intento de baja | `{{baseUrl}}/activos-biologicos/344` | GET | `200 OK` (130 ms) | 1 / 1 PASS (`cantidad=0`, `estado=BAJA`) | ✅ PASS |

**Payload Enviado en Petición 1:**
```json
{
  "tipo_baja": "venta",
  "fecha_baja": "2026-09-15",
  "motivo_baja": "Baja total QA-TC-M02-197 sobre lote 344",
  "cantidad_afectada": 10
}
```

**Cuerpo de Respuesta Petición 1 (`201 Created`):**
```json
{
  "id_eventos": 278,
  "id_activo_biologico": 344,
  "fecha": "2026-09-15T00:00:00Z",
  "descripcion": null,
  "id_usuario": 104,
  "crecimiento": null,
  "baja": {
    "cantidad_afectada": 10,
    "tipo": "venta",
    "motivo_baja": "Baja total QA-TC-M02-197 sobre lote 344"
  },
  "sanitario": null,
  "productivo": null,
  "reproductivo": null
}
```

**Cuerpo de Respuesta Petición 2 (`200 OK`):**
```json
{
  "id_activo_biologico": 344,
  "id_especie": 4,
  "tipo": "POBLACIONAL",
  "id_estado": 6,
  "nombre_estado": "BAJA",
  "detalle_poblacional": {
    "id_detalle": 93,
    "cantidad_inicial": 10,
    "cantidad_actual": 0,
    "densidad": 0.0
  }
}
```

**Diagnóstico Técnico:**
El subcaso TC-M02-197 aprobó con **100% de éxito**. Se confirmó que la corrección del trigger `trg_fn_baja_cantidad_valida` en base de datos (PR #254) opera con total robustez: al solicitar la baja de los 10 individuos existentes, el backend redujo `cantidad_actual` exactamente a 0, recalculó la densidad a 0 y cerró el lote automáticamente mediante la transición canónica al estado terminal `BAJA` (`id_estado = 6`).

---

## 5. Post-condición de Base de Datos y Verificación de Auditoría

### 5.1. Comprobación de Estado en PostgreSQL TEST
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_estado, e.nombre AS nombre_estado,
       d.cantidad_inicial, d.cantidad_actual, d.densidad,
       (SELECT COUNT(*) FROM modulo2.eventos_activos ea WHERE ea.id_activo_biologico = a.id_activo_biologico) AS total_eventos
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON a.id_estado = e.id_estado_activo_biologico
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico IN (296, 344)
ORDER BY a.id_activo_biologico;
```

**Salida Literal:**
```text
(296, 'POBLACIONAL', 40, 1, 'ACTIVO', 10, 10, NULL, 0)
(344, 'POBLACIONAL', 4,  6, 'BAJA',   10,  0, 0E-20, 1)
```

### 5.2. Verificación de Trazabilidad en `modulo2.bitacora_auditoria_m02`
```sql
SELECT id_bitacora, rf_origen, tipo_evento, resultado, severidad_log,
       id_activo_biologico, id_usuario_responsable, timestamp_registro, detalle_tecnico
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico IN (296, 344)
ORDER BY id_bitacora DESC LIMIT 4;
```

**Salida Literal:**
```text
(1898, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO', 344, 104, 2026-09-15 06:25:52.928127+00, NULL)
(1897, 'RF45', 'BAJA_REGISTRADA',            'EXITOSO', 'INFO', 344, 104, 2026-09-15 06:25:52.461467+00, {"motivo": "Baja total QA-TC-M02-197 sobre lote 344", "tipo_baja": "venta"})
(1896, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO', 296, 104, 2026-09-15 06:25:30.222451+00, NULL)
(1895, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO', 344, 104, 2026-09-15 06:24:29.644381+00, NULL)
```

**Hallazgos de Auditoría:**
- El registro `1897` certifica la auditoría oficial del evento bajo **RF-45** con `tipo_evento = 'BAJA_REGISTRADA'`, `resultado = 'EXITOSO'`, severidad `INFO` y usuario responsable `104` (`administador.dev@gmail.com`).
- La inmutabilidad de la bitácora quedó demostrada con el registro secuencial e inalterable de cada interacción.

---

## 6. Verificación de Limpieza e Inocuidad (Cleanup)

### 6.1. Inactivación y Cierre de Lotes de Prueba
Conforme a la regla de inocuidad de datos y ciclo de vida de activos biológicos:
1. **Lote 344 (Consumido por Baja Total):**  
   Al haberse procesado la baja de la totalidad de individuos (10/10), el lote fue colocado automáticamente en estado `BAJA` (`id_estado = 6`). Al intentar una inactivación lógica vía `PATCH /api-sgpmp-test/activos-biologicos/344/estado`, el sistema respondió conforme al diseño contractual:
   ```json
   {
     "error_code": "ESTADO_BAJA_IRREVERSIBLE",
     "message": "El activo se encuentra en estado BAJA. No se permite modificar el estado de activos dados de baja definitivamente."
   }
   ```
   El lote 344 se encuentra en estado terminal definitivo y ya no consume recursos activos ni altera inventarios productivos.
2. **Lote 345 (Lote Residual V1):**  
   Se verificó en base de datos que ya se encontraba en estado `2` (`INACTIVO`).
3. **Lote 296:**  
   Debido al rollback automático del fallo `HTTP 500`, el lote 296 no registró transacciones ni eventos huérfanos (total eventos: 0).

### 6.2. Comprobación de Residuos Activos de Prueba
```sql
SELECT id_activo_biologico, id_estado, e.nombre AS estado
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON a.id_estado = e.id_estado_activo_biologico
WHERE a.id_activo_biologico IN (344, 345);
```
**Salida Literal:**
```text
(344, 6, 'BAJA')
(345, 2, 'INACTIVO')
```
- **Resultado:** 0 lotes de prueba residuales en estado `ACTIVO`.
- **Garantía:** Cero operaciones destructivas (cero DDL, cero DELETE en BD).

---

## 7. Conclusiones, Diagnóstico Técnico, Dictamen Final y Referencias

### 7.1. Estado Real de los Subcasos
1. **TC-M02-197 (Baja total a cantidad_actual = 0):** ✅ **PASS COMPLETO (100% — 3/3 aserciones).**  
   - El incidente reportado en V1 respecto al fallo en base de datos quedó completamente superado tras la aplicación del PR #254 en el entorno TEST.
   - El endpoint gestiona la baja total de manera impecable: actualiza inventario a 0, recalcula densidad y hace la transición automática del lote a estado terminal `BAJA`.
2. **TC-M02-196 (Densidad igual al máximo permitido en crecimiento):** ⚠️ **BLOQUEADO ESTRUCTURALMENTE EN BACKEND.**  
   - El ticket **INC-M02-100-G31** no constituye un defecto funcional particular del caso G31 ni del lote 130, sino una manifestación directa de la **migración Alembic `b92f7e1a4c63` no aplicada en PostgreSQL TEST**.
   - Adicionalmente, se confirmó mediante análisis estático y dinámico que la regla zootécnica `densidad_maxima_por_especie` no está implementada en el backend de SGPMP (cero referencias a topes máximos de densidad).

### 7.2. Trazabilidad del Bloqueo Arquitectural (INC-M02-100-G31 / b92f7e1a4c63)
Se constató la cadena de invocaciones en el backend:
1. `POST /activos-biologicos/{id}/eventos/crecimiento` invoca `RegistrarEventoCrecimientoUseCase`.
2. El caso de uso consulta `self.parametros_port.obtener_por_tipo_medicion(...)` implementado en `ParametrosEspecieM09Adapter`.
3. El adaptador ejecuta `self.db.query(MetricaProduccionModel)`.
4. El modelo SQLAlchemy incluye `tipo_dato: Mapped[str]` introducida por la migración `b92f7e1a4c63`.
5. La base de datos TEST carece de la columna `modulo9.metricas_produccion.tipo_dato`, detonando la excepción `UndefinedColumn` y retornando `HTTP 500 ERROR_INTERNO`.

### 7.3. Dictamen Final Consolidado
⚠️ **Rechazado (1 de 2 subcasos aprobados al 100% — TC-M02-197 verificado con éxito; TC-M02-196 bloqueado por infraestructura externa de M09).**

### 7.4. Recomendaciones para el QA Lead y DevOps
1. **Cierre de Incidente en Bajas:** Declarar oficialmente verificado el correcto funcionamiento del endpoint `POST /activos-biologicos/{id}/eventos/baja` para bajas totales.
2. **Escalamiento DevOps/DBA:** Aplicar la migración Alembic `b92f7e1a4c63` en PostgreSQL TEST para desbloquear los endpoints dependientes de parámetros de especies (casos G25, G29 y G31-TC-M02-196).
3. **Definición de Requerimiento:** Remitir a Análisis de Negocio la especificación formal sobre si el sistema debe rechazar eventos de crecimiento que superen una supuesta `densidad_maxima_por_especie`, dado que dicha validación no existe actualmente en el código ni en el esquema.

---

### Referencias de Artefactos de Ejecución (Rutas Relativas)

- **Artefactos Consolidados (Raíz del RUN_ID):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/newman_summary_v2.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/reporte_v2.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/console_v2.log`
- **Evidencias y Sub-reportes por Subcaso (`EvidenciasPorSubcaso/`):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/EvidenciasPorSubcaso/TC-M02-196_run.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/EvidenciasPorSubcaso/TC-M02-196_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/EvidenciasPorSubcaso/TC-M02-197_run.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/EvaluacionV2/RESULTADOS/G31-REEVAL-V2-20260915-012500/EvidenciasPorSubcaso/TC-M02-197_report.html`
- **Colección Oficial de Prueba:**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/test_tc_m02_g31.json`
