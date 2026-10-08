# RF-24 / RF-10 — Evento de calibración exitosa

Incidencia: `INC-M09-72-G80-v2.0`, issue `#508`.
Grupo: `TC-M09-G80-v2.0`. Caso: `TC-M09-151-v2.0`.
Rama: `fix/rf24-g80-evento-calibracion-exitosa`.
Base: `origin/dev`, commit `5541ea36`.

## Diagnóstico y gaps de BD

El camino válido de `RegistrarCalibracionUseCase` guardaba la calibración y
su auditoría interna en `modulo9.auditorias_calibraciones`, pero no llamaba
al repositorio de eventos RF-10. Los rechazos sí emitían el tipo 29.
La auditoría interna de M09 no sustituye el evento de `modulo1.eventos`.

Se contrastaron RF-24 v2.0 de `Requerimientos_3.md` y RF-10 de
`Requerimientos_1.md`. RF-24 exige trazabilidad de la operación y rollback
si falla la auditoría; RF-10 exige hash SHA-256, consulta e inmutabilidad.

La inspección de `sgpmp_dev` se realizó con `member_dev`, en modo de solo
lectura y rollback al finalizar:

- El catálogo contiene los tipos 1–29, incluido `CALIBRACION_RECHAZADA`.
- No existe el tipo 30 ni un tipo de calibración exitosa en ese catálogo.
- `modulo1.eventos` ya contiene usuario, fecha, resultado, detalle JSONB,
  categoría, módulo y hash; no hacen falta columnas nuevas.
- La secuencia es `modulo1.tipos_evento_id_tipo_evento_seq`.
- Existe `modulo1.eventos_archivados`, relevante para el downgrade.
- La consulta de recursos 6 y 12 no devolvió filas visibles para esa cuenta.
  No se utiliza ese resultado para alterar permisos ni equipararlo a TEST.

Gap: falta el tipo de evento exitoso y su emisión desde RF-24. Se resuelve
con una migración versionada y una llamada al puerto RF-10, sin DML manual
persistido en DEV. No se consultaron ni modificaron los históricos de TEST.

## Implementación

Se define `CALIBRACION_EXITOSA`, ID 30, categoría `MODIFICACION`.
Se incorpora al catálogo canónico de nombres y categorías del dominio RF-10.

La transacción exitosa ahora realiza:

1. Guardar la calibración y obtener su ID.
2. Registrar la auditoría interna de M09.
3. Registrar el evento RF-10 con `exitoso=True` y módulo `MODULO9`.
4. Confirmar todo mediante un único commit.

El detalle del evento incluye `operacion=CALIBRACION_SENSOR`, el
`id_calibracion`, el área solicitada y el snapshot de los parámetros
persistidos: usuario, sensor, dispositivo, valor de referencia, ganancia,
offset, fecha de calibración, observaciones y modo.

La fecha del evento es la fecha UTC generada por el repositorio RF-10,
independiente de la fecha de calibración enviada por el cliente. El mismo
repositorio genera y verifica el SHA-256 y agrega el contexto de origen.
La serialización existente del resultado no cambia: `EnumEventoResultado.EXITOSO`
se devuelve como `"exitoso"` en el JSON.

Si falla cualquiera de las dos auditorías, se conserva HTTP 500,
`AUDITORIA_CALIBRACION_FALLIDA` y el mensaje de integridad existente de RF-24.
El rollback revierte la calibración y ambas trazas. El fallo de commit
también conserva el rollback existente.

Los rechazos siguen emitiendo `CALIBRACION_RECHAZADA` con resultado fallido
y mantienen su comportamiento best-effort. No se cambian mensajes de G75,
G76 o G77, permisos, validaciones, DTO, rutas o `modo_calibracion` de G74.
No se generan eventos retroactivos para calibraciones previas.

## Migración

Archivo: `b6f2d8a40c91_rf24_tipo_evento_calibracion_exitosa.py`.
Revisión: `b6f2d8a40c91`. Padre: `a3c9e5d17b42`.

El upgrade bloquea temporalmente las escrituras del catálogo, valida que
el ID 30 y el nombre no pertenezcan a otros tipos e inserta el evento
sin duplicarlo si ya existe con esa identidad. Ante conflicto aborta;
no sobrescribe otro evento. La secuencia se ajusta sin retroceder su valor.

El downgrade elimina únicamente el tipo nuevo si no tiene referencias
en eventos activos ni archivados. Si ya fue utilizado, conserva la fila
para proteger la trazabilidad; no borra eventos ni retrocede secuencias.

Se verificó una única cabeza Alembic y la generación de SQL de upgrade y
downgrade en modo offline. Esto no acredita una ejecución online:

```powershell
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade a3c9e5d17b42:b6f2d8a40c91 --sql
.\.venv\Scripts\python.exe -m alembic downgrade b6f2d8a40c91:a3c9e5d17b42 --sql
```

La generación utilizó una URL ficticia local y no abrió conexiones.
La migración debe aplicarse con el usuario de migraciones durante el
despliegue, antes de habilitar el código que emite el tipo 30.

## Pruebas

Con el arnés preparado y antes de corregir la aplicación, las nueve
pruebas nuevas dieron **5 fallidas y 4 aprobadas**: faltaba el evento
exitoso y un fallo de RF-10 no podía bloquear una escritura que no se intentaba.

Tras la corrección, el conjunto enfocado y de regresión dio **52 aprobadas**:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g80_evento_calibracion_exitosa.py tests/configuration/test_rf24_calibracion_json_numerico.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py tests/identity_access/test_rf10_categorias_eventos.py tests/identity_access/test_rf10_exportar_auditoria.py tests/identity_access/test_inc_m01_71_paginacion_auditoria_estable.py -q --tb=short --show-capture=no
```

Las nuevas pruebas cubren POST 201 y consulta por GET `/auditoria/`,
filtrando usuario, tipo, categoría y ventana temporal, con valores 0, 22.5
y 45. Verifican ID de calibración, correlación completa, hash íntegro,
conservación de eventos existentes e históricos simulados 10–14.
También cubren rollback ante fallos de RF-10, M09 y commit, conservación
de rechazos por formato/permisos y detección de manipulación del detalle.

El router, RBAC, casos de uso, handlers, middleware de contexto y repositorio
RF-10 son reales. La sesión y consultas SQL son simuladas en memoria;
los repositorios M09, el alcance y la identidad autenticada son dobles.
No se afirma persistencia ni inmutabilidad por triggers en PostgreSQL.

Se añadieron dos pruebas de integración PostgreSQL: registro consultable
con autenticación real y rollback cuando falla RF-10. Su recolección pasó,
pero quedaron **2 omitidas** porque `TEST_DATABASE_URL` no está configurada:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/integration tests/integration/test_tc_m09_g80_evento_calibracion_exitosa.py -q --tb=short -rs
```

Estas pruebas requieren el esquema y catálogo migrados. La transacción
exterior revierte las filas de prueba, aunque las secuencias pueden avanzar.
Se conserva la protección existente que impide usar `sgpmp_dev` como base
de integración. No se ejecutó la suite global: el conftest global de M02
importa `fcntl`, incompatible con Windows. Se observó la advertencia
existente de Starlette/httpx.

## Cierre QA

No se desplegó la migración ni se modificaron datos de DEV o TEST.
El RUN_ID compartido es evidencia textual; no están disponibles sus
artefactos originales para repetirlo aquí.

QA debe realizar una calibración nueva en TEST y recuperar su evento
RF-10 con usuario, ventana temporal y tipo 30. Debe verificar el ID de
calibración, sensor, dispositivo, valor, resultado y hash. LOGIN_EXITOSO,
CONSULTA_PERFIL_PROPIO y la auditoría interna de M09 no sustituyen ese evento.
La aprobación oficial de G80 queda pendiente del despliegue y esa ejecución.
