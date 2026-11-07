# RF-60 DEV-42 — Flujos alternos de heartbeat y mantenimiento

Fecha de cierre técnico: 2026-10-22. Responsable: Leandro Estiven Ramirez.
Historia #3700; tareas #3795, #3796 y #3797; épica #3667.

**Estado: implementación parcial verificable; la historia no está lista para cierre.**
No se han inventado tolerancias, tiempos de buffer, N, ventanas ni agrupaciones.

## 1. Diagnóstico y decisiones

| Componente | Estado encontrado | Corrección / estado final |
|---|---|---|
| DEV-27 | Disponible en `fix/dev27-heartbeat-parametros-canonicos`, sin integrar en `dev` | Se reutiliza como base; no se copia otro clasificador |
| E2 reloj | Se admitía un primer contacto futuro y se confiaba en el indicador del cliente | Contacto del servidor; futuro genera diagnóstico y alerta. Falta tolerancia aprobada para desfases hacia el pasado |
| E4 batería | Búsqueda por causa permitía aviso y crítica simultáneas | Lock por dispositivo, una alerta vigente nueva y escalamiento monotónico; ≤5 % genera APAGADO_INMINENTE |
| E5 buffer | DEV-27 ya consulta el último buffer persistido | Se conserva el algoritmo y se prueba BUFFER_ACTIVO periódico. BUFFER_PROLONGADO bloqueado por falta de parámetro |
| E6 reconexión | Se cerraban períodos, pero quedaban alertas abiertas; el trigger duplicaba historia | Recuperación selectiva transaccional y una sola transición de dispositivo |
| E9 fallo masivo | Sin N, ventana ni contrato verificable de unidad | No se implementa un agrupador basado en supuestos |
| E10 ausencia de heartbeat | No había diagnóstico si continuaba llegando telemetría | Evidencia de recepción válida + más de dos intervalos sin heartbeat; ACTIVO y alerta LEVE |
| Mantenimiento | Admitía cualquier origen; sin filtro explícito de finca | Solo INACTIVO → EN_MANTENIMIENTO → ACTIVO, JWT/RBAC, finca, lock y auditoría atómica |

### Fuentes y discrepancias

Se contrastó la tarea con `Especificacion-Requerimientos-Modulo3.md`, RF-60
(fase 5, Restricción 12, E2/E4/E5/E6/E9/E10 y CA-12/CA-18), el código,
los modelos y las migraciones vigentes. La especificación recibida conserva
contradicciones que no se resuelven inventando reglas:

- CA-7 menciona mantenimiento desde cualquier estado; fase 5 y esta tarea lo
  restringen. Se aplica la instrucción explícita de DEV-42.
- E4 dice alerta adicional de apagado, mientras DEV-42 exige una sola alerta
  activa de batería. Se conserva una alerta y se escala.
- RF-57 protege `tipo_variable` con P0006. Una alerta nacida como BATERIA_BAJA
  conserva ese tipo histórico; su condición vigente se expresa en `diagnostico`
  y `metadato_evento.condicion_bateria`. Si nace con ≤5 %, su tipo inicial es
  APAGADO_INMINENTE. No se desactiva la inmutabilidad ni se finge una resolución.
- E9/CA-12 dicen «más de N»; la tarea resume «N dispositivos». Falta confirmar
  comparación y valores antes de implementar ese flujo.
- CA-18 describe BUFFER_ACTIVO aun con heartbeat reciente; el algoritmo
  canónico prioriza el contacto reciente. Se conserva la Restricción 12 de
  DEV-27: buffer activo es alcanzable cuando se supera el umbral ACTIVO.

## 2. Implementación

### E2 — Alcance disponible

Ambos canales usan el trigger de contacto corregido. Un timestamp futuro no
adelanta `fecha_ultimo_contacto`, ni puede conservar `reloj_sincronizado=true`.
El worker registra DESINCRONIZACION_RELOJ con `reloj_desincronizado=true`,
instantes originales y heartbeat de origen en los metadatos existentes.
La fecha del evento de rechazo temporal es la recepción, no una fecha futura.
La alerta no se cierra por un heartbeat posterior normal. El DTO exige zona
horaria y los instantes persistidos se comparan como instantes absolutos.

Esto **no** implementa la regla completa de desfase absoluto: DEV-27 no define
la tolerancia de reloj. Tampoco se agrega una columna ficticia de diagnóstico
al estado; el indicador calculado queda en la evidencia técnica de la alerta.

### E4 — Batería y escalamiento

Los umbrales de aviso/crítica siguen siendo dinámicos de DEV-27. El límite de
apagado ≤5 % procede de la tarea. La búsqueda agrupa las tres condiciones de
batería y usa el advisory lock transaccional por dispositivo de DEV-05 (3505).
Reintentos no incrementan la frecuencia ni crean otra alerta; una mejora de
batería no degrada ni cierra automáticamente una condición activa. Los
identificadores del heartbeat de creación/escalamiento quedan en metadatos.
El tipo original es inmutable; severidad y diagnóstico reflejan el escalamiento.

Se conserva el acceso técnico mediante recurso 36, sin IDs ni nombres de roles
quemados. La creación es visible mediante el contrato de alertas técnicas.
**No se ha verificado entrega de notificaciones externas al Administrador**;
no hay una integración de notificación RF-60 conectada en este flujo y no se
presenta la mera creación de la alerta como una entrega de correo/push.
No se depuran ni se cierran duplicados históricos de batería o de historial de una base compartida.

### E5 — Buffer

La fuente es el último heartbeat por `fecha_recepcion,id_heartbeat`, no un
valor supuesto. La evaluación periódica utiliza el adaptador real de DEV-27;
A activa BUFFER_ACTIVO después del límite canónico y evita SIN_SEÑAL.
I o ausencia de reporte no se convierten en buffer activo. Falta el umbral
aprobado para BUFFER_PROLONGADO y, por tanto, ese escalamiento no se simula.

### E6 — Reconexión

Heartbeat confirmado, telemetría válida y evaluación periódica usan los mismos
efectos de comunicación. Una etapa RF60 independiente en DEV-05 evita que una
falla de diagnóstico bloquee RF-17: efectos y evidencia se confirman juntos,
y la telemetría previamente confirmada se conserva ante una falla.

Se resuelven solo DISPOSITIVO_SIN_SEÑAL, DISPOSITIVO_INACTIVO y
FALLO_CONECTIVIDAD del dispositivo recuperado. RF-57 exige
ACTIVA → EN_ATENCION → RESUELTA: se usan esas dos transiciones reales dentro
de la misma transacción, con historia del trigger y motivo de reconexión.
Una alerta ya EN_ATENCION va a RESUELTA. No hay inserciones manuales de historia.
La resolución automática no se atribuye al operador que atendió antes la alerta.
Batería, firmware, temperatura y reloj permanecen abiertos.

### E10 — Telemetría sin heartbeat

La recepción de telemetría LECTURA_VALIDA es la evidencia, sin leer flags
obsoletos de aptitud. Se exige telemetría dentro de la frecuencia configurada y
ausencia independiente de heartbeat por más de 2 × su intervalo. Para un
dispositivo sin heartbeat se usa la primera telemetría válida como comienzo del
período de gracia. Sin telemetría reciente no se genera esta alerta.
La evaluación excluye mantenimiento. Una alerta HEARTBEAT_AUSENTE no se resuelve
por telemetría; requiere recepción reciente de heartbeat.

### Fase 5 — Transiciones manuales

La entidad valida el origen/destino; el caso de uso lee bajo lock y el router
mantiene permiso U del recurso 35 y calcula el alcance por finca con el adaptador
existente. Un recurso fuera del alcance devuelve 404. La auditoría RF-63,
con actor, motivo y hash, se guarda antes del commit: si no puede persistirse,
se rechaza con 503 y se revierte estado e historial. No se modifican permisos.
Se conserva el 400 estructural del DTO para destinos no expuestos, como INACTIVO;
las transiciones de origen no permitido hacia los destinos expuestos generan
422 TRANSICION_INVALIDA. JWT ausente da 401 y falta de permiso da 403.

## 3. Archivos modificados

| Archivo | Responsabilidad y cambio | Tarea |
|---|---|---|
| `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py` | Reloj futuro, batería única y recuperación aun sin nueva transición | #3795/#3796 |
| `src/telemetry/application/use_cases/infraestructura/transicion_comunicacion.py` | Efectos compartidos de recuperación y ausencia de heartbeat | #3796/#3797 |
| `src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py` | Lectura bloqueada, diagnóstico sin cambio de estado y transacción externa | #3796/#3797 |
| `src/telemetry/application/use_cases/infraestructura/aplicar_mantenimiento_dispositivo_use_case.py` | Restricción manual, ámbito y auditoría atómica | #3797 |
| `src/telemetry/application/use_cases/alertas/actualizar_estado_alerta_use_case.py` | Resolución interna con las transiciones RF-57 existentes | #3796 |
| `src/telemetry/domain/entities/estado_dispositivo_iot.py` | Validación manual y actor automático independiente | #3797 |
| `src/telemetry/domain/repositories/parametros_heartbeat_port.py` | Evidencia temporal tipada y regla E10 | #3797 |
| `src/telemetry/domain/repositories/alerta_repository.py` | Contratos de lock, escalamiento y consulta de conectividad | #3795/#3796 |
| `src/telemetry/domain/repositories/estado_dispositivo_iot_repository.py` | Contratos de bloqueo y alcance | #3797 |
| `src/telemetry/domain/repositories/postcommit_port.py` | Etapa RF60 recuperable, sin nuevo worker | #3796/#3797 |
| `src/telemetry/infrastructure/adapters/parametros_heartbeat_mlops_adapter.py` | Consulta dinámica de actividad y contexto de dispositivo | #3797 |
| `src/telemetry/infrastructure/dto/heartbeat_dto.py` | Zona horaria y enum real de buffer | #3795/#3796 |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Lock, escalamiento sin romper P0006 y motivo de recuperación | #3795/#3796 |
| `src/telemetry/infrastructure/repositories/estado_dispositivo_iot_repository.py` | Serialización por dispositivo y pertenencia a finca | #3797 |
| `src/telemetry/infrastructure/routers/infraestructura_iot_router.py` | Alcance de finca en mantenimiento, sin alterar RBAC | #3797 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Composición RF60 post-commit compartida para telemetría | #3796/#3797 |
| `alembic/versions/f42a70c6b102_dev42_heartbeat_contacto_historial.py` | Funciones/trigger reversibles; contacto, historial y actor automático | #3795/#3796 |
| `tests/telemetry/test_dev42_heartbeat_flujos.py` | Límites, dominio, reloj y exclusiones de recuperación | Todas |
| `tests/integration/test_dev42_heartbeat_flujos.py` | HTTP/SQL, transacciones, RBAC, finca y concurrencia real PostgreSQL | Todas disponibles |
| `tests/telemetry/test_dev27_heartbeat_parametros.py` | Doble de lectura bloqueada compatible con el contrato nuevo | #3797 |
| `tests/integration/test_dev27_heartbeat_parametros.py` | Expectativas de apagado y escalamiento inmutable | #3795 |
| `tests/integration/test_dev05_ingesta_bplus_postcommit.py` | Etapa RF60 y batería ≤5 % | #3795/#3796 |

No se modificaron los documentos pendientes preexistentes no versionados.

## 4. Base de datos y dependencias

- Se usan heartbeats, estados_dispositivos_iot, periodos_inactividad, alertas,
  historico_transiciones_dispositivos, historico_estados_alertas,
  bitacora_auditoria_iot y telemetrias de M03; dispositivos, infraestructuras,
  usuarios_fincas y configuración RF-18 de M09; parametros_mlops de M04.
- Migración `f42a70c6b102`, hija de `e5a3c9b17d42`: corrige
  fn_procesar_heartbeat, añade la guarda BEFORE INSERT del reloj futuro y
  corrige la selección del actor en fn_alerta_validar_transicion. Sus reglas
  de transición permanecen iguales. Downgrade restaura las funciones previas.
- No se crean tablas/columnas/enums ni se toca inmutabilidad RF-53/RF-57.
- PostgreSQL 18 temporal, puerto 55442, bases con nombre de prueba. Cada test
  ordinario revierte su transacción; la concurrencia usa otra base efímera
  con commits reales que se elimina al terminar.
- DEV-27 está disponible en la base de esta rama, commit `a218a3d9`.
  P-1 continúa provisional. No se ha sembrado DEV/TEST desde este desarrollo.
- La consulta de configuración de `.env` apuntó a `integrador:5432`, no a la
  base oficial: no se usa como prueba de disponibilidad oficial.
  El intento de conexión de solo lectura a `sgpmp_dev:5447` falló con
  OperationalError. No se efectuaron escrituras oficiales ni compartidas.
- MQTT real requiere broker/credenciales/entorno de BRK: no está verificado.

## 5. Pruebas y evidencia

| Verificación | Resultado | Evidencia |
|---|---|---|
| Regresión conjunta final M03/M09 | **1034 aprobadas, 0 fallidas, 0 errores, 0 omitidas**, 190.40 s | `.pytest_cache/dev42_final.xml`, `dev42_final.log`, `dev42_resumen_validacion.json` |
| Desglose sin duplicaciones | 311 telemetría + 616 configuración + 107 PostgreSQL | XML final |
| Casos propios DEV-42, incluidos arriba | 57: 33 unitarios + 24 PostgreSQL | Los dos archivos `test_dev42_heartbeat_flujos.py` |
| E2 futuro HTTP/SQL | Contacto no futuro, reloj no sincronizado y alerta con diagnóstico true | `test_e2_reloj_futuro_no_adelanta_contacto_y_no_duplica` |
| E4 HTTP/SQL y concurrencia | Una alerta, límites inclusivos, escalamiento sin reescribir tipo ni duplicar efectos | Pruebas E4 y `test_bateria_concurrente_reintentos_no_duplican_alerta` |
| E5 periódico | Buffer A real alcanza BUFFER_ACTIVO; I/ausencia no inventan buffer | `test_e5_periodico_usa_buffer_real_y_no_infiere_buffer_ausente` |
| E6 HTTP/SQL/telemetría | Resolución selectiva, motivo, actor correcto y una transición de dispositivo | Pruebas E6 y recuperación en atención |
| Recuperación y auditoría fallidas | Rollback de efectos; heartbeat confirmado conservado; mantenimiento sin historia parcial | Pruebas de fallo de resolución y de auditoría manual |
| E10 | ACTIVO con HEARTBEAT_AUSENTE LEVE; solo heartbeat reciente resuelve | `test_e10_telemetria_reciente_sin_heartbeat_activo_y_alerta_leve` |
| Fase 5 | 200 válido; 422 transición; 400 destino fuera del DTO; 401/403/404; actor/motivo y concurrencia | Pruebas HTTP de mantenimiento y concurrencia real |
| Migración reversible | Upgrade → downgrade → upgrade correctos | `.pytest_cache/dev42_cierre_migraciones.log`; instalación nueva final en `dev42_final_migraciones.log` |
| AST/seguimiento | 22 archivos Python válidos y una fila DEV-42 por archivo, Git author Leandro, fecha 2026-10-22 | Revisión automatizada final |
| Bandit medio/alta confianza | 0 hallazgos en 17 archivos de producción/migración afectados | `.pytest_cache/dev42_bandit.txt` |
| Espacios y diferencias | `git diff --check` sin errores | Ejecución final |

Comando de la suite final (con DATABASE_URL, ALEMBIC_DATABASE_URL y
TEST_DATABASE_URL apuntando únicamente a la base aislada):

```powershell
.venv/Scripts/python.exe -c "import sys,types;sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None);import pytest;sys.exit(pytest.main(['tests/telemetry','tests/configuration','tests/integration/test_dev42_heartbeat_flujos.py','tests/integration/test_dev27_heartbeat_parametros.py','tests/integration/test_dev05_ingesta_bplus_postcommit.py','tests/integration/test_dev12_heartbeat_extendido.py','tests/integration/test_dev14_parametros_dinamicos.py','-q','--import-mode=importlib','--basetemp=.pytest_cache/dev42_final','--tb=short','--junitxml=.pytest_cache/dev42_final.xml']))"
```

Comandos de migración: `.venv/Scripts/python.exe -m alembic upgrade head`,
`downgrade e5a3c9b17d42` y nuevamente `upgrade head`, solo en PostgreSQL temporal.
Bandit: `.venv/Scripts/python.exe -m bandit -q -ll -ii <17 archivos afectados>`.

No se ejecutaron los escenarios de desfase absoluto con tolerancia aprobada,
BUFFER_PROLONGADO, FALLO_MASIVO ni MQTT con broker real. Son criterios pendientes,
no casos aprobados ni tests omitidos por pytest. Tampoco se ejecutó toda la suite
de todos los módulos del backend.

La primera regresión conjunta tuvo un fallo en el fixture de atención:
PostgreSQL `now()` representaba el inicio de la transacción exterior, anterior
a la alerta. Se preparó la atención con `clock_timestamp()` para representar
un instante válido. No se cambió `chk_alerta_timestamps`. La ejecución final
anterior, sobre base nueva, sustituye ese intento y no se suman sus casos.


Se utiliza `--import-mode=importlib` por nombres repetidos de tests existentes.
En Windows se empleó el puente de importación `fcntl` descrito por DEV-27;
no se probó ni modificó el bloqueo de archivos de M02. La advertencia de
Starlette/httpx procede de la infraestructura existente. Los intentos iniciales
revelaron la inmutabilidad P0006 al cambiar el tipo; se corrigió la solución
para conservarla. Los conteos finales no suman ejecuciones repetidas.

## 6. Estado de tareas y pendientes reales

| Tarea | Estado | Motivo |
|---|---|---|
| #3795 | Parcial | E4 y reloj futuro implementados; falta tolerancia oficial E2 y verificar notificación externa al Administrador |
| #3796 | Parcial | Buffer real y reconexión implementados; falta umbral de BUFFER_PROLONGADO |
| #3797 | Parcial | E10 y mantenimiento implementados; FALLO_MASIVO bloqueado por contrato N/ventana/unidad |
| #3700 | No cerrada | Flujos funcionales pendientes y MQTT real sin verificar |

Solicitud concreta a Análisis/M09/DEV-27, sin pedir esquemas nuevos a BD:

1. Tolerancia oficial de desfase absoluto de reloj, unidad y clave persistida.
2. Umbral de BUFFER_PROLONGADO, inicio del cómputo, unidad y clave persistida.
3. N y comparación inclusiva/exclusiva de fallo masivo; ventana temporal y
   contrato de «unidad productiva». El modelo tiene infraestructura/finca,
   pero esa asociación no prueba por sí sola la agrupación normativa de E9.
4. Formalizar P-1 y la configuración aprobada; confirmar si existe un mecanismo
   de notificación RF-60 a reutilizar y su contrato de destinatarios.
5. Comparar las funciones oficiales con el baseline antes de aplicar la migración;
   no fue posible descartar cambios manuales en la base oficial.
6. Acceso de solo lectura a la base oficial y entorno de broker para verificar
   allí parámetros vigentes, RBAC/RLS y MQTT extremo a extremo.

No se envió ningún mensaje externo ni se inventaron claves con defaults.
No se marca la tarea como finalizada solo por tener pruebas verdes del alcance
implementado. QA debe reevaluar cada flujo pendiente cuando se reciban esos datos.

## 7. Propuesta de Pull Request

**Título:** `fix(rf60): corregir bateria, reconexion y mantenimiento de heartbeat (DEV-42)`

### Desvío y causa raíz

Las alertas de batería se buscaban por causa, la reconexión dejaba alertas
abiertas y duplicaba historia mediante dos inserciones. El flujo no distinguía
telemetría reciente de ausencia de heartbeat y mantenimiento no validaba origen.

### Cambios implementados

- Reutiliza DEV-27 y DEV-05 para batería única, apagado ≤5 % y recuperación.
- Preserva tipo histórico de batería y registra escalamiento en diagnóstico.
- Corrige contacto futuro e historial del trigger; conserva actor y motivo.
- Implementa HEARTBEAT_AUSENTE y recuperación solo con evidencia adecuada.
- Restringe mantenimiento a la fase 5, con RBAC, finca, lock y auditoría atómica.
- Añade pruebas PostgreSQL/HTTP/SQL, concurrencia, rollback y regresión M03/M09.

### Validación

1034 pruebas aprobadas, sin fallos, errores ni omisiones; incluyen 57 casos propios DEV-42. PostgreSQL aislado, HTTP y frontera SQL de broker; no MQTT extremo a extremo. Migración reversible, AST, seguimiento, Bandit y diferencias verificados. Evidencia completa en este informe.

### Dependencias y pendientes

Este PR depende de DEV-27 (`fix/dev27-heartbeat-parametros-canonicos`,
`a218a3d9`). Comparar primero contra esa rama; para dirigirlo a `dev`, integrar
DEV-27 o aceptar explícitamente el PR dependiente que incluiría ambos cambios.
Faltan tolerancia E2, umbral BUFFER_PROLONGADO y N/ventana/unidad E9 aprobados;
no se afirma entrega externa de notificaciones ni MQTT con broker real.
La historia permanece parcial. No utilizar `Closes` mientras falten criterios.

Referencias: #3700, #3795, #3796, #3797.

Rama: `fix/dev42-heartbeat-flujos-alternos`.
La instancia PostgreSQL temporal fue detenida y su directorio eliminado después de verificar ruta y puerto; las evidencias quedan en `.pytest_cache/`.
