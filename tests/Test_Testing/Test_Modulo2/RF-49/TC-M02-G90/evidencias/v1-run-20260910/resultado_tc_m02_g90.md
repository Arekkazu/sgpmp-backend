# INFORME DE EJECUCIÓN CONSOLIDADO: CASO AGRUPADO TC-M02-G90
**Módulo:** 2 — Activos Biológicos  
**Requisito Funcional:** RF-49: Asociación de sensores IoT a activos biológicos (Comportamiento en Vacíos de Diseño: Tipo AMBIENTAL y Coherencia Territorial de Infraestructura)  
**Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)  
**Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`)  
**Fecha de Ejecución:** 2026-09-10  
**Herramienta de Ejecución:** Newman v6.2.1 + newman-reporter-htmlextra  
**Estado Global:** **NO CONFORME (1 PASS CON OBSERVACIÓN / 1 FAIL)**

---

## 1. RESUMEN EJECUTIVO Y TABLA DE VEREDICTOS

Se ejecutó la suite de pruebas agrupada **TC-M02-G90**, orientada a evaluar y documentar el comportamiento del backend ante dos vacíos y contradicciones de especificación del **RF-49**:

1. **TC-M02-220 (TC-M02-161-A):** Creación de asociación de tipo `AMBIENTAL` y evaluación de la dependencia forzada de un activo biológico puntual frente al diseño conceptual del Tipo B (*Asociación Ambiental Compartida mediada por infraestructura pura*).
2. **TC-M02-221 (TC-M02-162-A):** Validación de coherencia territorial entre infraestructuras productivas distintas dentro de una misma finca territorial (Sensor en Infraestructura 1 y Activo en Infraestructura 2 de Finca 1).

### Tabla de Veredictos

| Subcaso | Nombre / Objetivo | Método / Endpoint | HTTP Esp. | HTTP Obt. | Aserciones | Veredicto | Defecto / Observación |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TC-M02-220** | Asociación AMBIENTAL con activo forzoso | `POST /activos-biologicos/19/sensores` | 201 | 201 | 3/3 | **FAIL** | [INC-M02-G90-01](#defecto-inc-m02-g90-01-severo) |
| **TC-M02-221** | Coherencia entre infraestructuras (misma finca) | `POST /activos-biologicos/1/sensores` | [201, 409, 422] | 201 | 2/2 | **PASS CON OBSERVACIÓN** | [OBS-M02-G90-02](#observación-obs-m02-g90-02-contradicción-interna-del-rf-49-en-coherencia-de-infraestructura) |

**Resultado Consolidado:** 1 subcaso aprobado con observación y 1 subcaso fallido por funcionalidad faltante del RF-49. Veredicto global: **NO CONFORME**.

---

## 2. MÉTRICAS DE EJECUCIÓN

| Métrica | Valor |
| :--- | :--- |
| **Total Subcasos Ejecutados** | 2 |
| **Subcasos PASS CON OBSERVACIÓN** | 1 (50%) |
| **Subcasos FAIL** | 1 (50%) |
| **Total Solicitudes HTTP (incluyendo Auth)** | 4 |
| **Total Aserciones Evaluadas** | 7 (incluyendo Auth) |
| **Aserciones Aprobadas** | 7 (100% técnicas en Newman) |
| **Aserciones Fallidas** | 0 (en Newman; 1 FAIL por regla de negocio funcional) |
| **Tiempo Promedio de Respuesta Backend** | ~208 ms (excluyendo autenticación) |
| **Defectos Registrados** | 1 (`INC-M02-G90-01`, Severo) |
| **Observaciones de Requisito** | 1 (`OBS-M02-G90-02`, Baja) |
| **Estado de BD al Finalizar** | Limpia (0 asociaciones remanentes, histórico íntegro) |

---

## 3. DETALLE TÉCNICO POR SUBCASO

### 3.1 TC-M02-220 — Asociación AMBIENTAL con Activo Forzoso
- **Solicitud HTTP:** `POST /activos-biologicos/19/sensores`
- **Payload Aprobado y Ejecutado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "AMBIENTAL",
    "dispositivo_iot_id": 1,
    "sensor_id": 3,
    "id_infraestructura": 1,
    "motivo": "Evaluacion de asociacion AMBIENTAL en endpoint de activo TC-M02-220"
  }
  ```
- **Respuesta:** `HTTP 201 Created`
- **Cuerpo Retornado:**
  ```json
  {
    "id_asociacion_activo_sensor": 22,
    "id_activo_biologico": 19,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "ambiental",
    "dispositivo_iot_id": 1,
    "sensor_id": 3,
    "id_infraestructura": 1,
    "fecha_inicio": "2026-09-10T10:00:58.280899Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Evaluacion de asociacion AMBIENTAL en endpoint de activo TC-M02-220",
    "advertencia": null
  }
  ```
- **Aserciones Newman:** 3/3 PASS (`TC-M02-220: Código HTTP es 201 Created`, `TC-M02-220: Tipo de asociación es AMBIENTAL`, `TC-M02-220: Estado inicial es ACTIVA`).
- **Verificación en BD:** Se confirmó que la fila 22 persistió `id_activo_biologico = 19`.
- **Evaluación Funcional:** Aunque la petición HTTP devuelve 201 Created, el sistema obliga a registrar la asociación AMBIENTAL atándola forzosamente a un activo individual (`id_activo_biologico = 19`), incumpliendo el diseño del Tipo B del RF-49 que exige vinculación a la infraestructura productiva sin depender de un activo puntual.
- **Veredicto:** **FAIL** (Defecto `INC-M02-G90-01`).

### 3.2 TC-M02-221 — Coherencia entre Infraestructuras Distintas de la Misma Finca
- **Contexto:** Sensor 3 ubicado en Infraestructura 1 (`Estanque-01`, Finca 1). Activo 1 ubicado en Infraestructura 2 (`Estanque-02`, Finca 1).
- **Solicitud HTTP:** `POST /activos-biologicos/1/sensores`
- **Payload Aprobado y Ejecutado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 1,
    "sensor_id": 3,
    "id_infraestructura": 1,
    "motivo": "Evaluacion de sensor en Infra 1 con activo en Infra 2 dentro de Finca 1 TC-M02-221"
  }
  ```
- **Respuesta:** `HTTP 201 Created`
- **Cuerpo Retornado:**
  ```json
  {
    "id_asociacion_activo_sensor": 23,
    "id_activo_biologico": 1,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "directa",
    "dispositivo_iot_id": 1,
    "sensor_id": 3,
    "id_infraestructura": 1,
    "fecha_inicio": "2026-09-10T10:01:12.630136Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Evaluacion de sensor en Infra 1 con activo en Infra 2 dentro de Finca 1 TC-M02-221",
    "advertencia": null
  }
  ```
- **Aserciones Newman:** 2/2 PASS (`TC-M02-221: Respuesta coherente con alguna interpretación del RF-49`, `TC-M02-221: Estado de asociación creada es ACTIVA`).
- **Verificación en BD:** Se confirmó que la fila 23 persistió con `id_activo_biologico = 1`, `id_sensor = 3` y `id_infraestructura = 1`.
- **Veredicto:** **PASS CON OBSERVACIÓN**.

---

## 4. REGISTRO FORMAL DE DEFECTOS Y OBSERVACIONES

### DEFECTO INC-M02-G90-01 (Severo)
- **Título:** Ausencia de endpoint para asociación AMBIENTAL pura a nivel de infraestructura (Tipo B del RF-49 no implementado en API).
- **Subcaso de Origen:** TC-M02-220 (TC-M02-161-A).
- **Categoría:** FLUJO.
- **Severidad:** **SEVERO (S2)**.
- **Prioridad:** MEDIA.
- **Equipo Responsable:** Backend / Desarrollo API.
- **Tiempo Máximo de Solución:** 8 horas.
- **Impacto:** El Tipo B del RF-49 no está disponible. Para monitorear N activos de una infraestructura se requiere N asociaciones en lugar de 1.
- **Trazabilidad del Rediseño:**
  1. El subcaso original solicitaba: *"Crear asociación tipo_asociacion=AMBIENTAL enviando únicamente id_infraestructura, sin activo_biologico_id ni id_lote"*.
  2. La inspección técnica demostró que el único endpoint expuesto es `POST /activos-biologicos/{id_activo}/sensores`, exigiendo ineludiblemente un `{id_activo}` numérico en la URL y obligando a enviar `tipo_activo` en el body (`AsociarSensorActivoDTO`). Resulta técnicamente imposible omitir el activo en dicha ruta sin provocar `404 Not Found` o `422 Unprocessable Entity`.
  3. La inspección exhaustiva línea por línea de `AsociarSensorActivoUseCase` reveló que **el backend no contiene ninguna rama condicional para el tipo `AMBIENTAL`**: toma forzosamente el `{id_activo}` del path y lo persiste obligatoriamente en `modulo2.asociaciones_activos_sensores.id_activo_biologico`.
  4. **Conclusión Técnica:** El Tipo B del RF-49 (*Asociación Ambiental Compartida mediada por infraestructura pura, donde 1 sensor ambiental monitoriza a N activos que residen en la infraestructura*) no cuenta con un endpoint a nivel de infraestructura en la API actual. Toda asociación ambiental queda artificialmente anclada a un activo biológico individual o lote puntual.
- **Criterio de Cierre:** Implementación de endpoint a nivel de infraestructura (ej. `POST /configuracion/infraestructuras/{id}/sensores` o similar) para registrar asociaciones ambientales puras sin requerir `id_activo_biologico`, y ejecución exitosa de retest con veredicto PASS.

---

### OBSERVACIÓN OBS-M02-G90-02: Contradicción Interna del RF-49 en Coherencia de Infraestructura
- **Subcaso de Origen:** TC-M02-221 (TC-M02-162-A).
- **Severidad:** BAJA (Inconsistencia Documental en Especificación).
- **Categoría:** CALIDAD DEL REQUISITO FUNCIONAL.
- **Análisis de la Contradicción en RF-49:**
  - **Precondición 4:** Expresa permisividad amplia: *"El activo biológico debe estar asignado a la misma infraestructura productiva a la que pertenece el sensor, o a una infraestructura dentro de la misma granja, para garantizar coherencia de ubicación"*.
  - **Restricción 2:** Restringe a nivel de finca territorial: *"El sensor y el activo biológico deben pertenecer a la misma granja. No se permiten asociaciones entre activos y sensores de granjas distintas"*.
  - **Flujo Alterno E2:** Solo rechaza cuando los identificadores de finca difieren (`HTTP 409 Conflict`, mensaje de error territorial). No existe ningún flujo alterno que contemple el rechazo de infraestructuras distintas dentro de una misma finca.
- **Comportamiento Backend Observado:** El caso de uso (`asociar_sensor_activo_use_case.py`, L115) implementa fielmente la cláusula permisiva de la Precondición 4 y la Restricción 2: valida únicamente que `infra_sensor.id_finca == infra_activo.id_finca`. Por ende, acepta asociaciones entre infraestructuras dispares de la misma finca (`HTTP 201 Created`).
- **Conclusión:** El sistema se comporta de forma coherente con la Restricción 2 y el Flujo E2. Se documenta internamente la falta de una regla estricta de infraestructura a nivel de negocio.

---

## 5. BLOQUEOS EXTERNOS

- **Bloqueos Externos:** Ninguno. La API TEST y la base de datos respondieron en conformidad durante toda la ejecución.

---

## 6. CONFIRMACIÓN DE LIMPIEZA DE BASE DE DATOS

En cumplimiento del RF-49 Restricción 8 (Historial Append-Only), se ejecutó el script acotado `cleanup_tc_m02_g90.sql` aplicando la **Estrategia A (UPDATE de estado)** sin sentencias `DELETE`:

### Resultado de Limpieza:
```text
Filas actualizadas en paso 1 (Activo 1): 1
Filas actualizadas en paso 2 (Activo 19): 1
asociaciones_activas_remanentes: 0
```

### Consulta de Comprobación Final:
```sql
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico IN (1, 19)
  AND id_sensor = 3
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```
**Resultado:** `0`. Base de datos TEST limpia y conforme.

---

## 7. CRITERIOS DE CIERRE

El caso agrupado **TC-M02-G90** se considera **NO CONFORME**. Requiere:
- **(a)** Corrección de `INC-M02-G90-01` para dar **CONFORME** al subcaso 220 mediante la implementación del endpoint que permita asociar sensores ambientales a nivel de infraestructura productiva sin activo puntual.
- **(b)** Decisión de negocio sobre `OBS-M02-G90-02` para el subcaso 221 respecto a la exigencia o no de coherencia estricta de infraestructura dentro de la misma finca.

---

## 8. INSTRUCCIONES DE RE-EJECUCIÓN (SCRIPTS DE RETEST)

Para re-ejecutar de forma independiente cualquiera de los subcasos:

1. **Retest Subcaso TC-M02-220 (Asociación AMBIENTAL):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G90\retest_tc_m02_220.ps1
   ```
2. **Retest Subcaso TC-M02-221 (Coherencia de Infraestructura):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G90\retest_tc_m02_221.ps1
   ```
