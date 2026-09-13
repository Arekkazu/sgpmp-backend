# INFORME DE VERIFICACIÓN DE TRIGGER: DEFECTO INC-M02-G89-02
## Sub-caso: TC-M02-217 (Superación Automática de Asociaciones Sensor-Activo)

- **Fecha de Verificación**: 2026-09-11 (19:31 COT / 00:31 UTC)
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Script Ejecutado**: `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/retest_tc_m02_217.ps1`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/RESULTADOS/reporte_TC-M02-217.html`
- **Veredicto Defecto INC-M02-G89-02**: **DEFECTO CORREGIDO — Verificado en reevaluación (2026-09-11)**

---

## 1. Objetivo de la Verificación

Validar la corrección aplicada por el DBA sobre la función trigger `modulo2.trg_fn_asociacion_sensor_activo_unica()` en PostgreSQL TEST, la cual anteriormente provocaba `HTTP 500 Internal Server Error` (código `P0229`) al crear una segunda asociación `directa` para un activo que ya contaba con una asociación `ACTIVA`, bloqueando la transición requerida por RF-49: `ACTIVA` $\rightarrow$ `SUPERADA`.

---

## 2. Estado Previo de la Base de Datos (Pre-condición)

Antes de iniciar la prueba, se confirmó la ausencia total de asociaciones activas vigentes para el Activo 19 y Sensor 2:

```sql
SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores 
WHERE (id_activo_biologico = 19 OR id_sensor = 2) 
  AND estado_asociacion = 'ACTIVA' 
  AND fecha_fin IS NULL;
```
- **Resultado obtenido**: `0` asociaciones activas. Base de datos en estado limpio.

---

## 3. Resultados de la Ejecución (Newman)

Se ejecutó el script `retest_tc_m02_217.ps1` con los siguientes resultados:

| Paso | Petición HTTP | Endpoint | Código Esperado | Código Obtenido | Aserciones | Estado |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **00** | `POST` | `/sesiones/` | 200 OK | `200 OK` (2.4 s) | 1 / 1 | **PASS** |
| **01** | `POST` | `/activos-biologicos/19/sensores` (Asoc. A) | 201 Created | `201 Created` (159 ms) | 1 / 1 | **PASS** |
| **02** | `POST` | `/activos-biologicos/19/sensores` (Asoc. B - Superación) | 201 Created | `201 Created` (149 ms) | 1 / 1 | **PASS** |

### Métricas Newman:
- **Peticiones Ejecutadas**: 3 / 3
- **Aserciones Evaluadas**: 3 / 3 (100% exitosas, 0 fallidas)
- **Tiempo de Respuesta Promedio**: 920 ms
- **Exit Code**: `0` (`[EXITO] TC-M02-217 supero todas las aserciones`)

---

## 4. Evidencia de Estado en Base de Datos PostgreSQL TEST

Tras la ejecución exitosa de ambos pasos de creación, se consultó `modulo2.asociaciones_activos_sensores`:

```sql
SELECT id_asociacion_activo_sensor, id_activo_biologico, tipo, id_sensor, estado_asociacion, fecha_inicio, fecha_fin, motivo 
FROM modulo2.asociaciones_activos_sensores 
WHERE id_activo_biologico = 19 AND id_sensor = 2 
ORDER BY id_asociacion_activo_sensor DESC 
LIMIT 2;
```

**Resultado verificado en BD TEST**:
```text
1. ID 28 (Asociación B):
   - id_activo_biologico: 19
   - id_sensor:           2
   - tipo:                directa
   - estado_asociacion:   ACTIVA
   - fecha_inicio:        2026-09-12 00:31:12 UTC
   - fecha_fin:           NULL
   - motivo:              None

2. ID 27 (Asociación A):
   - id_activo_biologico: 19
   - id_sensor:           2
   - tipo:                directa
   - estado_asociacion:   SUPERADA
   - fecha_inicio:        2026-09-12 00:31:11 UTC
   - fecha_fin:           2026-09-12 00:31:12 UTC (Poblada con timestamp de reemplazo)
   - motivo:              Reemplazada por nueva asociación
```

- ✅ **Asociación A** pasó de forma atómica a `SUPERADA` con `fecha_fin` debidamente poblada.
- ✅ **Asociación B** se creó exitosamente en estado `ACTIVA` con `fecha_fin IS NULL`.
- ✅ El trigger `trg_fn_asociacion_sensor_activo_unica` permitió la inserción al validar correctamente que no existe conflicto externo.

---

## 5. Verificación de Limpieza (Cleanup)

En apego a la política de inocuidad de datos, se ejecutó inmediatamente el script append-only `cleanup_tc_m02_g89.sql`:

```sql
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = GREATEST(clock_timestamp(), fecha_inicio + INTERVAL '1 second'),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G89'
WHERE id_activo_biologico = 19
  AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```

### Comprobación Post-Limpieza:
```sql
SELECT id_asociacion_activo_sensor, estado_asociacion, fecha_fin, motivo 
FROM modulo2.asociaciones_activos_sensores 
WHERE id_asociacion_activo_sensor IN (27, 28);
```
```text
- ID 27: estado_asociacion = 'SUPERADA', fecha_fin = '2026-09-12 00:31:12+00'
- ID 28: estado_asociacion = 'INACTIVA', fecha_fin = '2026-09-12 00:31:34+00' (desactivada por cleanup)
```

```sql
SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores 
WHERE (id_activo_biologico = 19 OR id_sensor = 2) 
  AND estado_asociacion = 'ACTIVA' 
  AND fecha_fin IS NULL;
```
- **Asociaciones activas remanentes**: `0`.
- **Dictamen**: El fixture quedó 100% limpio y sin datos residuales activos.

---

## 6. Conclusión y Dictamen Final

1. **Defecto INC-M02-G89-02**: **CORREGIDO**. El trigger `modulo2.trg_fn_asociacion_sensor_activo_unica()` ya no genera falsos conflictos de unicidad ante superación legítima de sensores en el mismo activo.
2. **Subcaso TC-M02-217**: **PASS (3/3 aserciones exitosas, HTTP 201 Created verificado)**.
3. **Subcasos TC-M02-216, 218 y 219**: Permanecen no evaluados en esta verificación ya que dependen del defecto independiente `INC-M02-G89-01` (inexistencia de endpoints `PATCH /activos-biologicos/{id}/sensores/{id_asoc}`).
