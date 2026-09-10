# TC-M02-G22 (TC-M02-038) — BLOQUEO en la precondición: RF-41 no permite registrar eventos sanitarios en TEST

**RF-35 / CU-02.** No es un bug de RF-35 — es un defecto de RF-41 (`POST /activos-biologicos/{id}/eventos/sanitario`)
que impide construir la precondición literal de TC-M02-038 ("Activo con eventos sanitarios/biológicos pendientes
sin cerrar"). Se documenta aquí porque bloqueó el camino directo de la prueba, y porque es un hallazgo real e
independiente que vale la pena que el equipo revise.

## Qué se observó

`POST /activos-biologicos/{id_activo}/eventos/sanitario` devuelve **500** para los dos únicos tipos de evento
sanitario que no requieren un diagnóstico previo (`DIAGNOSTICO` y `CONTROL_PREVENTIVO`), en dos activos distintos
recién creados:

```json
// POST .../eventos/sanitario {"tipo":"DIAGNOSTICO","diagnostico":"Infeccion bacteriana QA-G22"}
// HTTP 500
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[],"timestamp":"2026-09-09T22:59:28.020067+00:00"}
```

```json
// POST .../eventos/sanitario {"tipo":"CONTROL_PREVENTIVO","observaciones":"Control preventivo QA-G22"}
// (sin solicitar_estado, para descartar que el cambio de estado sea la causa)
// HTTP 500
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[],"timestamp":"2026-09-09T23:01:18.849310+00:00"}
```

Reproducido en **3 intentos independientes**, en **2 activos distintos** (id 195 y 196), con y sin `solicitar_estado`
— consistente, no es un fallo intermitente.

Esto crea un **bloqueo circular**: `TRATAMIENTO` y `VACUNACION` exigen un `DIAGNOSTICO` previo
(`RegistrarEventoSanitarioUseCase._TIPOS_REQUIEREN_DIAGNOSTICO`), pero registrar ese `DIAGNOSTICO` es precisamente
lo que falla con 500. En la práctica, **ningún tipo de evento sanitario se puede registrar hoy en este entorno TEST**
sobre un activo sin historial sanitario previo.

## Hipótesis de causa raíz (no confirmada — sin acceso a la base de datos)

No tengo acceso directo a PostgreSQL de TEST desde este entorno de ejecución (solo API), así que esto es una
hipótesis basada en lectura de código, no una causa confirmada:

- El use case (`registrar_evento_sanitario_use_case.py`) y el modelo ORM (`evento_sanitario_model.py`, con sus 4
  `CheckConstraint` nombrados) se revisaron línea por línea y no muestran ningún problema evidente para estos dos
  tipos: `DIAGNOSTICO` solo exige `diagnostico IS NOT NULL` (cumplido) y `CONTROL_PREVENTIVO` solo exige
  `observaciones IS NOT NULL` (cumplido).
- La auditoría previa del módulo (`anotaciones/modulo_2/estado.md`, sección RF-41) ya señalaba que el trigger de BD
  `trg_fn_evento_sanitario_secuencia` "infiere diagnóstico previo por proxy (presencia/ausencia de
  medicamento/dosis) en vez de por tipo" — una lógica descrita ahí mismo como "más frágil" que la del use case. Es
  plausible que esa misma lógica por proxy esté fallando (o lanzando una excepción con `ERRCODE` propio) también
  para los tipos que el use case no necesita validar (`DIAGNOSTICO`/`CONTROL_PREVENTIVO`, que no tienen
  medicamento/dosis).
- Esto coincidiría con el "Hallazgo transversal #4" ya documentado: excepciones de trigger con `ERRCODE` propio
  (`P02xx`) que `raise_from_db_error` no traduce, y que caen en el manejador genérico → 500 `ERROR_INTERNO` (el
  mensaje exacto que se observó aquí).
- **No se puede confirmar sin consultar directamente el código fuente del trigger en la base de datos** (`\df+` /
  `pg_get_functiondef` sobre `trg_fn_evento_sanitario_secuencia`) o los logs del servidor — ninguno de los dos está
  disponible desde este entorno de ejecución.

## Por qué no se puede resolver desde esta sesión

Sin acceso a PostgreSQL de TEST ni a los logs del backend desplegado, no se puede inspeccionar la definición real
del trigger ni el traceback completo del error 500 para confirmar la causa exacta.

## Cómo desbloquear

1. Revisar la definición de `trg_fn_evento_sanitario_secuencia` (y cualquier otro trigger sobre
   `modulo2.eventos_sanitarios`) directamente en la base de TEST, con foco en su comportamiento para
   `tipo IN ('DIAGNOSTICO', 'CONTROL_PREVENTIVO')`.
2. Revisar los logs del backend TEST en el momento de los timestamps de arriba
   (`2026-09-09T22:59:28Z`, `2026-09-09T23:01:18Z`) para obtener el traceback real y el `ERRCODE` de Postgres.
3. Una vez identificado, aplicar el mismo criterio ya usado en otros RFs de este módulo: o se corrige el trigger, o
   se amplía `raise_from_db_error` para traducir su `ERRCODE` a un código de negocio controlado en vez de 500.

## Alcance del bloqueo

Cualquier caso de RF-41 (CU-07, no cubierto todavía por ningún `TC-M02-G*` de este módulo) que registre un evento
`DIAGNOSTICO` o `CONTROL_PREVENTIVO` fallará igual mientras esto no se corrija — y por el bloqueo circular descrito
arriba, `TRATAMIENTO`/`VACUNACION` tampoco se pueden probar sobre un activo sin historial sanitario previo sembrado
de antes. Vale la pena confirmar esto antes de escribir los casos de RF-41.

**Para TC-M02-G22 (RF-35) específicamente**: el bloqueo impidió reproducir la precondición literal de TC-M02-038 vía
RF-41. Se usó como alternativa el endpoint `PATCH /{id}/estado` (RF-44) para dejar el activo en `EN_TRATAMIENTO` sin
pasar por RF-41 — ver `RESULTADOS/TC-M02-G22_resultado.md`, sección TC-M02-038, para el resultado de esa
verificación adaptada (que sigue siendo válida para lo que RF-35 necesita probar: si el endpoint bloquea operaciones
mientras el activo tiene un proceso abierto sin cerrar).
