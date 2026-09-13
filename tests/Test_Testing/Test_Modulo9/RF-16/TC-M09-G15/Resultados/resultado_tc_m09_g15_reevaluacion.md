# Reporte de Reevaluación - TC-M09-G15 (Subcasos TC-M09-36, TC-M09-37, TC-M09-38)

## 1. Encabezado y Metadatos de Ejecución

* **ID Caso de Prueba**: `TC-M09-G15`
* **Subcasos Oficiales**: 
  - `TC-M09-36`: Impedir desactivación de Etapa productiva en uso (con activos biológicos asociados).
  - `TC-M09-37`: Impedir desactivación de Patología en uso (con registros clínicos / predicciones / alertas).
  - `TC-M09-38`: Impedir desactivación de Métrica de producción en uso (con eventos productivos asociados).
* **Módulo / Requisito**: Módulo 9 (Configuración) / `RF-16` (CU-02 — Configurar Parámetros Productivos y Sanitarios por Especie).
* **Tipo de Prueba**: Integridad Referencial / Reglas de Negocio / Seguridad y Control de Datos.
* **Fecha de Reevaluación (Corrida de Confirmación)**: 2026-09-13
* **Fecha de Corrida Histórica**: 2026-09-05 (Corrida previa donde TC-M09-37 y TC-M09-38 fueron rechazados por stubs del defecto `INC-M09-03`).
* **Entorno de Ejecución**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
* **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
* **Herramienta**: Newman CLI v6.2.2 + `newman-reporter-htmlextra` v1.23.1
* **Colección Ejecutada**: `tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/test_tc_m09_g15.json`
* **Ruta del Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/Resultados/reporte_tc_m09_g15_reevaluacion.html`
* **Veredicto Global**: **⚠️ PASS PARCIAL (2/3) — INC-M09-07 confirmado como defecto reproducible**

---

## 2. Objetivo de la Reevaluación / Resumen Ejecutivo

### Contexto del Fallo Original (Defecto `INC-M09-03`)
En la evaluación histórica del caso `TC-M09-G15`, únicamente se ejecutó contra la API el subcaso `TC-M09-36` (Etapa), resultando exitoso con `HTTP 422`. Por su parte, los subcasos `TC-M09-37` (Patología) y `TC-M09-38` (Métrica) fueron rechazados formalmente debido al hallazgo de integridad y seguridad **`INC-M09-03`**: los adaptadores inyectados en los routers eran stubs hardcodeados (`StubDependenciaPatologiaAdapter` y `StubDependenciaMetricaAdapter`) que retornaban incondicionalmente `False` en `tiene_dependencias_activas()`. Esto provocaba que cualquier intento de desactivación respondiera con `HTTP 200 OK` desprotegiendo de forma destructiva y silenciosa entidades en uso.

### Estado del Defecto en la Reevaluación
Dichos adaptadores stub fueron erradicados en el backend mediante el commit `a2dd2ed`, sustituyéndolos por repositorios SQLAlchemy que consultan la base de datos real:
- `SqlAlchemyDependenciaPatologiaRepository`: consulta la vista `modulo9.vw_rf16_dependencias_patologias` sumando predicciones y alertas patológicas del Módulo 4.
- `SqlAlchemyDependenciaMetricaRepository`: consulta `modulo2.eventos_productivos`.

En esta reevaluación se completó la colección Newman para ejecutar de punta a punta los 3 subcasos utilizando entidades reales del catálogo bajo estricto monitoreo pre/post de base de datos. Para garantizar la reproducibilidad y descartar fallos transitorios, se llevaron a cabo **dos ejecuciones completas e independientes** con resultados estrictamente idénticos.

### Resumen Comparativo de Resultados por Subcaso (Corrida de Confirmación Definitiva)

| Subcaso | Parámetro Evaluado | Endpoint | Estado Esperado | Estado Obtenido | Error Code Obtenido | Veredicto |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M09-36** | Etapa con activos asociados (`id=10`) | `PATCH /configuracion/ciclos/10/desactivar` | `HTTP 422` | `HTTP 422` | `ETAPA_CON_ACTIVOS` | ✅ **PASS** |
| **TC-M09-37** | Patología con dependencias M04 (`id=7`) | `PATCH /configuracion/patologias/7/desactivar` | `HTTP 422` | `HTTP 422` | `PATOLOGIA_CON_DEPENDENCIAS` | ✅ **PASS** |
| **TC-M09-38** | Métrica con eventos productivos (`id=1`) | `PATCH /configuracion/metricas/1/desactivar` | `HTTP 422` | `HTTP 500` | `ERROR_INTERNO` | ❌ **FAIL (INC-M09-07)** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

Inmediatamente antes de ejecutar la colección de pruebas en vivo, se ejecutó el script de verificación `tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/verificar_bd_pre_post.py` vía conexión de solo lectura (`member_qa`), reportando:

```text
=== ESTADO DE BASE DE DATOS (TC-M09-G15) ===
[ETAPA] id_ciclo_biologico=10 | nombre='Fase juvenil cachama' | es_activo=True | referencias_productivas=1
[PATOLOGÍA] id_especies_patologias=7 | nombre='Ich (Ichthyophthirius)' | es_activo=True | id_patologia=1 | predicciones=7 | alertas=4
[MÉTRICA] id_metrica_produccion=1 | nombre='Peso promedio individual' | tipo_medicion='manual' | es_activo=True | eventos_productivos=4
```

* **Confirmación Pre-condición**:
  1. `id_ciclo_biologico = 10` se encontraba activa (`es_activo = True`) y con 1 referencia en `modulo9.ciclos_productivos_biologicos`.
  2. `id_especies_patologias = 7` se encontraba activa (`es_activo = True`), vinculada a la patología de catálogo `id_patologia = 1`, la cual registra 11 dependencias activas (7 predicciones y 4 alertas en Módulo 4).
  3. `id_metrica_produccion = 1` se encontraba activa (`es_activo = True`), con 4 eventos productivos registrados en `modulo2.eventos_productivos`.

---

## 4. Resultados Detallados de la Ejecución (Newman)

### Tabla de Ejecución Paso a Paso (Corrida de Confirmación)

| Paso | Método & Endpoint | Esperado | Obtenido | Latencia | Estado | Detalle de la Evaluación |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | `POST /sesiones/` | `200 OK` | `200 OK` | 1286 ms | **PASS** | Autenticación con `administador.dev@gmail.com`. JWT obtenido exitosamente. |
| **2** | `PATCH /configuracion/ciclos/10/desactivar` | `422 Unprocessable` | `422 Unprocessable` | 206 ms | **PASS** | **TC-M09-36**: Bloqueo exitoso. `error_code: ETAPA_CON_ACTIVOS`. Mensaje: *"No es posible desactivar la etapa 'Fase juvenil cachama'..."* |
| **3** | `GET /configuracion/patologias?id_especie=4` | `200 OK` | `200 OK` | 209 ms | **PASS** | **TC-M09-37 (Pre)**: Constatación previa por API. Entidad `id=7` está activa (`es_activo: true`). |
| **4** | `PATCH /configuracion/patologias/7/desactivar` | `422 Unprocessable` | `422 Unprocessable` | 139 ms | **PASS** | **TC-M09-37**: Bloqueo exitoso. `error_code: PATOLOGIA_CON_DEPENDENCIAS`. Mensaje: *"La patología 'Ich (Ichthyophthirius)' no puede ser desactivada porque forma parte del historial clínico..."* |
| **5** | `GET /configuracion/patologias?id_especie=4` | `200 OK` | `200 OK` | 125 ms | **PASS** | **TC-M09-37 (Post)**: Verificación posterior por API. Entidad `id=7` permanece activa (`es_activo: true`). |
| **6** | `GET /configuracion/metricas?id_especie=4` | `200 OK` | `200 OK` | 241 ms | **PASS** | **TC-M09-38 (Pre)**: Consulta de catálogo de métricas operativas por especie. |
| **7** | `PATCH /configuracion/metricas/1/desactivar` | `422 Unprocessable` | `500 Internal` | 235 ms | **FAIL** | **TC-M09-38**: Rechazado con error interno HTTP 500 en lugar de regla de negocio HTTP 422. Causa: `ValueError` de mapeo ORM por dato legado `tipo_medicion = 'manual'`. |
| **8** | `GET /configuracion/metricas?id_especie=4` | `200 OK` | `200 OK` | 188 ms | **PASS** | **TC-M09-38 (Post)**: Catálogo de métricas permanece operativo (`es_activo: true`). |

### Métricas Globales de la Ejecución
* **Total de Iteraciones**: 1
* **Total de Requests Ejecutados**: 8/8
* **Total de Aserciones Evaluadas**: 8
* **Aserciones Pasadas**: 7 (87.5%)
* **Aserciones Fallidas**: 1 (12.5%)
* **Duración Total de Corrida**: 3.2 segundos
* **Tiempo Promedio de Respuesta**: 328 ms (Mínimo: 125 ms, Máximo: 1286 ms)
* **Exit Code de Newman**: `1` (Esperado por aserción no cumplida en Paso 7 ante el HTTP 500)

### Detalle del Fallo en Paso 7 (TC-M09-38)
```text
AssertionError: TC-M09-38: Bloquear desactivación de MÉTRICA en uso - HTTP 422 BusinessRuleError
expected response to have status code 422 but got 500
at assertion:0 in test-script inside "Paso 7: TC-M09-38 - Impedir desactivación de MÉTRICA en uso (id=1)"
```

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Verificación de Integridad)

Inmediatamente después de la corrida de Newman, se ejecutó nuevamente `tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/verificar_bd_pre_post.py`:

```text
=== ESTADO DE BASE DE DATOS (TC-M09-G15) ===
[ETAPA] id_ciclo_biologico=10 | nombre='Fase juvenil cachama' | es_activo=True | referencias_productivas=1
[PATOLOGÍA] id_especies_patologias=7 | nombre='Ich (Ichthyophthirius)' | es_activo=True | id_patologia=1 | predicciones=7 | alertas=4
[MÉTRICA] id_metrica_produccion=1 | nombre='Peso promedio individual' | tipo_medicion='manual' | es_activo=True | eventos_productivos=4
```

### Comparativa Pre vs Post en Base de Datos:

| Entidad Real Evaluada | ID Entidad | Estado Pre-ejecución | Estado Post-ejecución | Dependencias Pre | Dependencias Post | ¿Intacta? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Etapa** (*Fase juvenil cachama*) | `10` | `es_activo = True` | `es_activo = True` | 1 ref. | 1 ref. | ✅ **SÍ (100% Intacta)** |
| **Patología** (*Ich / Ichthyophthirius*) | `7` | `es_activo = True` | `es_activo = True` | 11 deps. | 11 deps. | ✅ **SÍ (100% Intacta)** |
| **Métrica** (*Peso promedio individual*) | `1` | `es_activo = True` | `es_activo = True` | 4 eventos | 4 eventos | ✅ **SÍ (100% Intacta)** |

* **Confirmación de Cero Mutaciones**: Ninguna de las tres entidades reales sufrió alteración física ni lógica (`0` mutaciones). Las tres entidades conservan su estado original activo y sus mismos vínculos referenciales tanto en la primera corrida como en la corrida de confirmación.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

Dado que se trata de pruebas de validación negativa de integridad referencial (donde la especificación contractual exige el **rechazo y bloqueo de la mutación**):
* **Mutaciones en BD**: Cero (`0`) registros creados, modificados o eliminados.
* **Necesidad de Teardown / Cleanup**: **NO se requiere cleanup** manual ni scripts de reversión SQL en la base de datos.
* **Inocuidad ante Contingencia**: Se constata que la métrica `id_metrica_produccion = 1`, a pesar del fallo no controlado `HTTP 500`, abortó la transacción en la capa de hidratación ORM antes de ejecutar ninguna mutación sobre la columna `es_activo`. No se requirió invocación correctiva a `PATCH /configuracion/metricas/{id}/reactivar`.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 1. Subsanación Comprobada de `INC-M09-03` en Patologías y Etapas (TC-M09-36 y TC-M09-37)
* Los casos `TC-M09-36` y `TC-M09-37` se declaran **PASS DEFINITIVO**.
* El defecto histórico `INC-M09-03` (adaptadores stub retornando `False`) quedó **totalmente subsanado y confirmado reproducible en dos corridas independientes**.
* La infraestructura de `SqlAlchemyDependenciaPatologiaRepository` consultó con éxito la vista `modulo9.vw_rf16_dependencias_patologias`, detectó las 11 dependencias en Módulo 4 y activó la regla de negocio FA-04 devolviendo **`HTTP 422 Unprocessable Entity`** con código `PATOLOGIA_CON_DEPENDENCIAS`.

### 2. Diagnóstico Técnico del Defecto `INC-M09-07` en Métricas (TC-M09-38)
* En `TC-M09-38`, se declara **FAIL**, identificando y confirmando formalmente el defecto reproducible **`INC-M09-07`** (*Inconsistencia de enum en datos semilla de `modulo9.metricas_produccion`*), demostrado de manera idéntica en dos ejecuciones consecutivas.
* **Causa Raíz Detallada**:
  - En la base de datos TEST, el registro semilla de `modulo9.metricas_produccion` (`id_metrica_produccion = 1`, *Peso promedio individual*) posee el valor legado `'manual'` en su columna `tipo_medicion`.
  - Al invocarse el caso de uso `DesactivarMetricaUseCase.execute(1)`, se invoca `self.metricas_repo.obtener_por_id(1)`.
  - El método `SqlAlchemyMetricaProduccionRepository._a_entidad(orm)` realiza la hidratación de dominio:
    ```python
    tipo_medicion = TipoMedicion(orm.tipo_medicion)
    ```
  - La clase `TipoMedicion` (`src/configuration/domain/value_objects/tipo_medicion.py`) es un Enum estricto que admite exclusivamente: `{'PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO'}`.
  - Al procesar el valor legado `'manual'`, Python lanza un `ValueError: 'manual' is not a valid TipoMedicion` no capturado en la capa de infraestructura, lo que detiene la ejecución antes de evaluar `dependencia_port.tiene_dependencias_activas(1)` y provoca que FastAPI devuelva `HTTP 500 Internal Server Error`.
* **Diseño y Calidad de la Prueba**:
  - La prueba está **correctamente diseñada**: el fixture real (`id_metrica_produccion = 1`) es válido y posee 4 dependencias activas en `modulo2.eventos_productivos`.
  - La verificación de integridad pre/post fue 100% exitosa (la métrica permaneció activa).
  - El fallo es imputable **exclusivamente a una inconsistencia entre los datos semilla de producción y el enum de dominio**, no a un problema en la suite de pruebas.

### 3. Dictamen Final por Subcaso y Global

* **TC-M09-36 (Etapa con activos)**: ✅ **PASS DEFINITIVO**.
* **TC-M09-37 (Patología con dependencias)**: ✅ **PASS DEFINITIVO** (`INC-M09-03` superado y certificado).
* **TC-M09-38 (Métrica con eventos productivos)**: ❌ **FAIL** (Defecto de datos/código confirmado: `INC-M09-07`).
* **Veredicto Global del Grupo TC-M09-G15**: **PASS PARCIAL (2/3) — Caso bloqueado parcialmente por INC-M09-07, pendiente de corrección de datos semilla o del enum de dominio.**
