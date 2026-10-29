# DEV-14 — Parametrización dinámica de valores operativos

Fecha de verificación: 2026-10-19. Historia #3520; subtareas #3590–#3593.
Rama: `fix/dev14-parametros-operativos`, base `origin/dev` en `cd06a257`.

## 1. Resultado y diagnóstico

Se implementó la configuración persistida de calidad RF-62 (`k`, `M`, `N`,
`umbral_drift`, `P`), confianza Edge/IA RF-57 y ventana de retroalimentación
RF-72. Los consumidores vuelven a consultar los parámetros durante su ejecución;
no requieren reinicio ni redespliegue. RF-18 acepta el nombre canónico
`umbral_sin_senal` y mantiene `heartbeat` como alias de compatibilidad.

**La historia completa no está cerrada.** RF-53 HTTP, deduplicación RF-57 y
batería/RSSI RF-60 requieren ampliar el esquema M09. La temporalidad RF-60
requiere además aclaración funcional. Las partes independientes se implementaron
y verificaron sin introducir tablas paralelas ni modificar bases compartidas.

El repositorio utiliza FastAPI/Python y SQLAlchemy, no NestJS. El inventario
incluyó código, puertos, modelos, migraciones y una inspección de `sgpmp_dev`
con transacción de solo lectura. No se ejecutaron semillas ni migraciones allí.

La tabla `modulo9.configuraciones_globales` contiene únicamente los escalares
operativos `frecuencia_muestreo` y `heartbeat`, además de ID, fecha, responsable
y estado activo. No dispone de un contenedor genérico de configuración.
`modulo4.parametros_mlops` sí tiene nombre único, valor actual/default JSONB,
límites numéricos, responsable y fecha. Admite la configuración estadística,
confianza del resultado IA y ventana MLOps sin cambios de esquema.

## 2. Referencias y discrepancias

Se contrastaron los RF actualizados entregados para M03, M04 y M09, las
migraciones y el acuerdo consolidado AIoT disponible. Los archivos solicitados
`gaps_m03_m04_m09_patron_transversal.md` y
`AIOT-DEV-01_Hallazgos_y_Dependencias_para_Desarrollo.md` no se localizaron
en el repositorio ni en las descargas inspeccionadas; no se atribuyen decisiones
a documentos no disponibles.

RF-18 incorpora RFC-015 C1, aplicada el 2026-10-16: `umbral_sin_senal` es el
nombre canónico del antiguo `heartbeat`, en minutos. No equivale a la cadencia
`intervalo_heartbeat`. Se aceptan ambos nombres de entrada; si llegan juntos
deben representar el mismo entero. La respuesta expone el nombre canónico y
conserva el campo anterior marcado como deprecado. La columna física, auditoría
y contratos internos continúan usando `heartbeat`; no hay doble almacenamiento.

RF-60 aclara la cadena entre intervalo, muestreo y umbral, pero persisten dos
problemas del algoritmo escrito: el PASO 3 (`> umbral_sin_senal`) absorbe el
PASO 4 (`> umbral_inactivo`) si se aplica el primer paso que coincida, y no
define el estado del intervalo entre activo y sin señal. También faltan en el
esquema las magnitudes por tipo necesarias para los umbrales derivados. Se
conserva el algoritmo actual sin presentarlo como resolución normativa.

## 3. Inventario #3590

Las rutas de esta matriz son relativas a la raíz del repositorio.

| RF | Parámetro / valor anterior | Ubicación original | Fuente destino | Cambio de esquema | Estado |
|---|---|---|---|---|---|
| RF-18 | `heartbeat`, minutos persistidos | `configuration/infrastructure/dto/{crear,actualizar}_configuracion_dto.py` y repositorio global, bajo `src/` | M09, columna existente `heartbeat` | No | Alias canónico implementado; lectura global refrescada |
| RF-60 | 300 / 1800 / 86400 s | `src/telemetry/domain/entities/estado_dispositivo_iot.py` | M09; alcance por tipo por confirmar | Sí, diseño tras aclaración | Bloqueado por Análisis y almacenamiento; constantes conservadas |
| RF-60 | Batería 30 %, crítica 10 %, RSSI −100 dBm | `src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py` | M09 global | Sí | Solicitud técnica preparada; comparaciones originales conservadas |
| RF-53 | Latencia HTTP 30000 ms | `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py` | M09 global | Sí | Pendiente de esquema; no se confunde con antigüedad ni reglas SQL |
| RF-57 | Deduplicación 30 min | `src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py` | M09 global | Sí | Pendiente de esquema; idempotencia conservada |
| RF-57 | Confianza Edge/IA 0.85 | El mismo caso de uso, `_clasificar` | M04 `parametros_mlops` | No | Dinámico: `umbral_confianza_edge_ia`; sin configurar, valor base 0.85 (G76) |
| RF-57 | Ventana de reevaluación 60 min (E16) | `reevaluar_alerta_use_case.py` | M04 `parametros_mlops` | No | Dinámico: `rf57_ventana_reevaluacion_min`; sin configurar, valor base 60 (G75) |
| RF-57 | Confianza mínima de IA 0.75 (CA-2) | El mismo caso de uso, antes de la deduplicación | M04 `parametros_mlops` | No | Dinámico: `rf57_umbral_confianza_minimo`; sin configurar, valor base 0.75 (G73) |
| RF-62 | k=3, M=5, N=20, drift=5 %, P=3 | `src/telemetry/infrastructure/adapters/parametros_calidad_stub_adapter.py` | M04 `parametros_mlops` | No | Adaptador real e inyección en las tres composiciones presentes en esta base |
| RF-62 | Frecuencia 5 min del stub | El mismo adaptador | Configuración activa M09 existente | No | Adaptador obtiene frecuencia real; se registra en la evaluación |
| RF-72 | Ventana 90 días | `src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py` | M04, clave existente `ventana_retroalimentacion_dias` | No | Dinámica, conserva comparación por `.days` |

El campo `umbral_drift_significativo` del puerto de calidad no tiene consumidor
en el cálculo actual; no se crea una regla nueva para él. Las bandas de severidad
RF-57 (0.85/0.95), el umbral recall RF-69 y las bandas normativas del índice de
calidad tienen otras responsabilidades y no fueron sustituidos por el umbral
de confianza Edge/IA. Los límites físicos/biológicos por variable/especie siguen
usando sus fuentes propias. La configuración estadística conserva el alcance
global que admite el algoritmo existente.

## 4. Intervención de Samuel #3591

**Fue necesaria para una parte comprobada del alcance.** Se preparó
[la solicitud técnica mínima](dev14_solicitud_samuel.md), sin enviarla:
cinco parámetros operativos nuevos en la tabla global M09, con tipos, unidades,
restricciones, incorporación inicial y criterios de comprobación. No se aplicó
unilateralmente una migración reservada a DBA.

Almacenar umbrales de dispositivo en MLOps evitaría físicamente una migración,
pero mezclaría la responsabilidad operativa M09 con parámetros de modelos.
Los campos de transmisión remota y confirmación de alertas tampoco representan
latencia ni deduplicación. No se reutilizaron con otro significado.

Para M04 no se necesita intervención externa: se comprobaron los privilegios
SELECT/INSERT/UPDATE de `sgpmp_app` y `member_dev`, la ausencia de RLS en la
tabla y la estructura genérica existente. La ausencia de los nuevos nombres
se resuelve mediante la herramienta administrativa incluida, no mediante una
solicitud de semillas a Samuel. La configuración debe revisarse e instalarse
explícitamente antes de habilitar los consumidores en un entorno compartido.

## 5. Contrato de configuración e implementación #3592

| Nombre persistido | Tipo / unidad | Restricción del consumidor |
|---|---|---|
| `rf62_k` | Número; desviaciones estándar | Finito, > 0, representable por el cálculo float |
| `rf62_m` | Entero; lecturas iguales consecutivas | 1 ≤ M ≤ N |
| `rf62_n` | Entero; tamaño de serie | N ≥ 2, requerido por desviación estándar |
| `rf62_umbral_drift` | Número; porcentaje | Finito, ≥ 0, representable por el cálculo float |
| `rf62_p` | Entero; lecturas consecutivas | 1 ≤ P ≤ N |
| `umbral_confianza_edge_ia` | Número; probabilidad | 0.70–0.95. **Excepción (INC-M03-168-G76):** si falta, se usa el valor base del RF (0.85); un valor inválido sigue respondiendo 503 |
| `rf57_ventana_reevaluacion_min` | Entero; minutos | ≥ 1. RF-57 E16 (INC-M03-167-G75): ventana de reevaluación por IA desde la generación de la alerta. Si falta, se usa el valor base del RF (60); un valor inválido responde 503 |
| `rf57_ventana_deduplicacion_min` | Entero; minutos | ≥ 1. RF-57 E4 (INC-M03-176-G57A). Si falta, valor base 30 |
| `rf57_sla_critico_min` / `rf57_sla_moderado_min` / `rf57_sla_leve_min` | Entero; minutos | ≥ 1. SLA por severidad (G57A). Si faltan, valores base 5 / 30 / 120 |
| `rf57_umbral_confianza_minimo` | Número; probabilidad | 0–1. RF-57 CA-2 (INC-M03-166-G73): mínimo para generar PREDICCION_PATOLOGIA. **Excepción:** si falta, se usa el valor base que publica el RF (0.75); un valor inválido sí responde 503 |
| `ventana_retroalimentacion_dias` | Entero; días | 7–365 |

Los límites almacenados pueden restringir estos dominios, nunca ampliarlos.
Se rechazan booleanos, strings, null, objetos, fracciones para enteros y números
no finitos. No hay fallback a los valores del stub. Un parámetro faltante produce
503 `PARAMETRO_CONFIGURACION_AUSENTE`; uno inválido, 503
`PARAMETRO_CONFIGURACION_INVALIDO`. Una solicitud administrativa inválida usa
el error de validación existente, 400 `PARAMETRO_MLOPS_INVALIDO`.

La lectura utiliza columnas explícitas de SQLAlchemy en cada ejecución, sin
caché de proceso ni objetos antiguos del identity map. La configuración global
usa `populate_existing()`. Cada cálculo conserva su conjunto de parámetros
aplicados, ahora incluyendo P y frecuencia. En RF-57 no se exige la configuración
IA para un evento únicamente Edge ni cuando no existe conflicto que resolver.

La escritura administrativa valida el lote completo antes de guardarlo y
serializa sus propias actualizaciones mediante advisory lock transaccional.
El repositorio solo hace flush; el caso de uso confirma o revierte la transacción.
Se preserva `valor_por_defecto` cuando ya existe y se actualizan responsable y
fecha. Una modificación SQL externa debe respetar las mismas restricciones;
las lecturas siguen validando y no aceptan valores inválidos por omisión.

### Archivos de producción

| Archivo / grupo | Responsabilidad y cambio |
|---|---|
| `src/configuration/domain/entities/parametro_mlops.py` | Claves, valor de dominio y validación numérica/correlacionada central |
| `src/configuration/domain/repositories/parametros_mlops_port.py` | Puerto de consulta y administración persistente |
| `src/prediction/infrastructure/models/parametro_mlops_model.py` | Mapeo de la tabla M04 existente; no crea DDL |
| `src/prediction/infrastructure/repositories/parametros_mlops_repository.py` | Lectura fresca, bloqueo y upsert con metadata |
| `src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py` | Validación atómica y límites de transacción de carga administrativa |
| `scripts/configurar_parametros_dev14.py` | CLI de administración con destino explícito y validación de responsable Administrador |
| `src/telemetry/infrastructure/adapters/parametros_calidad_mlops_adapter.py` | Implementación real del puerto RF-62, cinco parámetros M04 y frecuencia M09 |
| `src/telemetry/domain/repositories/parametros_alertas_port.py` y `infrastructure/adapters/parametros_alertas_mlops_adapter.py` bajo `src/telemetry/` | Puerto y adaptador de confianza RF-57 |
| `src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py` | Usa confianza persistida para el conflicto Edge/IA; conserva deduplicación pendiente |
| `src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py` | Recupera la ventana vigente por operación |
| `src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py` | Completa snapshot de configuración; no incorpora correcciones ajenas de DEV-02 |
| `src/telemetry/infrastructure/routers/{alerta,calidad,telemetria}_router.py` | Inyección de repositorios/adaptadores reales |
| `src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py` y `infrastructure/routers/evento_edge_router.py` bajo `src/telemetry/` | Completa la inyección al constructor de alertas del camino Edge, sin alterar la recepción ni el transporte |
| `src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py` | Inyección de configuración persistida RF-72 |
| `src/configuration/infrastructure/repositories/configuracion_global_repository.py` | Refresca valores M09 al reutilizar sesión |
| `src/configuration/infrastructure/dto/{crear,actualizar}_configuracion_dto.py` y `alias_umbral_sin_senal.py` | Acepta nombre canónico y alias; detecta contradicción |
| `src/configuration/infrastructure/schema/configuracion_global_schema.py` | Respuesta compatible con nombre canónico adicional y alias deprecado |

Se conserva `ParametrosCalidadPort`; el stub permanece disponible para pruebas,
pero se retiró de las composiciones de producción presentes en esta rama.
No hay nuevos endpoints, permisos, tópicos, buffers ni migraciones.

### Carga inicial y cambios posteriores

`dev14_parametros_ejemplo.json` contiene un ejemplo explícito para revisión;
no es una semilla automática ni una aprobación de valores clínicos/operativos.
La CLI exige `DEV14_DATABASE_URL` y un usuario Administrador existente como
responsable. No toma la conexión del `.env` como destino implícito ni constituye
un nuevo mecanismo de autenticación HTTP: requiere acceso administrativo
autorizado a la BD.

```powershell
$env:DEV14_DATABASE_URL = '<conexion autorizada; no almacenar credenciales en Git>'
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py --archivo anotaciones/modulo_9/dev14_parametros_ejemplo.json --id-usuario <id-administrador>
# La instrucción anterior valida en transacción READ ONLY, sin escrituras.
# Solo en el entorno autorizado y tras revisar los valores:
.venv/Scripts/python.exe scripts/configurar_parametros_dev14.py --archivo anotaciones/modulo_9/dev14_parametros_ejemplo.json --id-usuario <id-administrador> --aplicar
Remove-Item Env:DEV14_DATABASE_URL
```

No se ejecutó `--aplicar` contra desarrollo compartido. La ausencia deliberada
de defaults exige preparar la configuración antes del despliegue.

## 6. Pruebas ejecutadas #3593

PostgreSQL 18.4 aislado local, con migraciones hasta `3a9d5e7c1b24`.
Las pruebas de parámetros usan lectura/escritura SQL real y los casos de uso
reales; los puertos de salida de calidad/alertas/retroalimentación se aíslan
con dobles para separar dependencias. Una prueba adicional combina el RF-62
con la implementación real de DEV-02 y verifica también la persistencia final.

| Grupo, sin contar repeticiones | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Configuración M09, incluidas 42 nuevas unitarias DEV-14 | 597 | 1 | 0 |
| Regresión telemetría M03 | 30 | 0 | 0 |
| Regresión predicción M04 | 23 | 0 | 0 |
| Regresión shared seleccionada | 73 | 0 | 0 |
| Integración PostgreSQL DEV-14 en rama independiente | 17 | 0 | 1 |
| Total en rama independiente | **740** | **1** | **1** |
| Comprobación adicional con DEV-02 aplicado temporalmente | **1** | 0 | 0 |

La prueba adicional es la misma prueba omitida por dependencia en la rama
independiente: en conjunto hay **741 pruebas distintas que aprobaron en al menos
uno de los dos contextos**, no 741 aprobadas en la rama independiente.
Las ejecuciones unitarias preliminares son subconjunto de la regresión M09 y
no se suman otra vez. Evidencia resumida: [dev14_validacion.json](dev14_validacion.json).

El fallo restante es previo al cambio: `test_la_aplicacion_sirve_el_directorio_de_logotipos`
importa `main`, que importa M02 y requiere `fcntl`, no disponible en Windows.
Por el mismo problema no se pudieron recolectar los archivos
`test_inc_m09_75_g142_disparo_automatico_vision.py` y
`test_inc_m09_77_g137_observaciones_vision.py`; se informan como dos archivos
no recolectables, sin inventar el número de casos internos. El conftest raíz
también requiere ese módulo; se usó `--confcutdir` para los grupos independientes.
No se modificaron ni debilitaron esas pruebas.

### Evidencia de comportamiento dinámico

| Cambio persistido | Verificación obtenida sin reconstruir consumidor |
|---|---|
| k: 1 → 4 | La misma serie deja de generar outlier estadístico |
| M: 3 → 4 | Cambia la detección de sensor congelado |
| Drift: 5 → 20 % | Cambia la detección de posible drift |
| P: 3 → 6 | Cambia la detección de deriva consecutiva |
| N: 6 → 8 | La serie de seis lecturas pasa a INDETERMINADA |
| Frecuencia M09: 7 → 9 min | El mismo adaptador registra el nuevo valor; no se afirma una nueva regla de gaps |
| Confianza IA: 0.80 → 0.90 | El caso de uso resuelve el mismo conflicto Edge/IA de forma diferente |
| Ventana RF-72: 30 → 7 días | La misma retroalimentación pasa de aceptada a FUERA_DE_VENTANA_TEMPORAL |
| Confianza modificada y confirmada desde otra conexión | La misma sesión y consumidor observan el valor nuevo |
| N: 6 → 30, con DEV-02 y 21 lecturas reales | Persiste evaluación vigente INDETERMINADA con aptitud false, antes apta; telemetría original idéntica |

Se verificaron además ausencia/valores JSON inválidos, límites persistidos,
rollback de lote inválido, preservación del default y responsable, errores de
persistencia controlados y CLI de previsualización sin escrituras.
Una regresión adicional ejecuta la recepción Edge con sus puertos de salida
aislados y comprueba que la alerta efectivamente se guarda tras incorporar la
nueva dependencia; no basta con que el bloque best-effort termine sin propagar
una excepción.

DEV-02 (`8fc5ef9c`) no está integrado en la base `origin/dev` elegida. Esta base
todavía intenta actualizar telemetría inmutable en el caso de uso RF-62. Por eso
el escenario completo se omite en la rama independiente en vez de atribuirle
a DEV-14 la solución de otra incidencia. Para verificar compatibilidad se
aplicaron temporalmente los siete archivos correspondientes de DEV-02 y se
ejecutó la prueba real: aprobó. Después se restauraron exactamente los archivos
de DEV-14, comprobando sus bytes. No se incluyó esa corrección en este commit.

### Comandos ejecutados

Se usaron `.venv/Scripts/python.exe`, `TEST_DATABASE_URL` y `DATABASE_URL`
apuntando exclusivamente al PostgreSQL aislado para las integraciones.
`<tmp-dev14>` representa el directorio temporal propio de esta ejecución.

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m pytest --confcutdir=tests/configuration tests/configuration -q --ignore=tests/configuration/test_inc_m09_75_g142_disparo_automatico_vision.py --basetemp=<tmp-dev14>/pytest-configuracion-final-edge2 --junitxml=.dev14-config-regression.xml --tb=short
.venv/Scripts/python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry -q --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py --junitxml=.dev14-telemetry-regression.xml
.venv/Scripts/python.exe -m pytest --confcutdir=tests/prediction tests/prediction -q --junitxml=.dev14-prediction-regression.xml
.venv/Scripts/python.exe -m pytest --confcutdir=tests/shared tests/shared/test_db_error_translator.py tests/shared/test_error_handlers_globales.py tests/shared/test_contexto_rls.py tests/shared/test_database_reintentos.py tests/shared/test_orm_foreign_keys_resolvibles.py -q --junitxml=.dev14-shared.xml
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev14_parametros_dinamicos.py -q --basetemp=<tmp-dev14>/pytest-integration-final --junitxml=.dev14-integration.xml
# Solo durante la comprobación temporal de la dependencia DEV-02:
.venv/Scripts/python.exe -m pytest --confcutdir=tests/integration tests/integration/test_dev14_parametros_dinamicos.py::test_rf62_persistencia_completa_dinamica_con_dev02 -q --tb=short --junitxml=.dev14-dependencia.xml
.venv/Scripts/python.exe -m compileall -q src/configuration src/telemetry src/prediction scripts/configurar_parametros_dev14.py
git diff --check
```

Compileall y diff-check aprobaron. Bandit se ejecutó desde la caché local con
`uv tool run --offline bandit -f json -q <archivos Python de producción cambiados>`;
no reportó hallazgos medios/altos. La revisión con nivel bajo identificó dos
B110 preexistentes: `_emitir_auditoria` de calidad y el bloque best-effort de
alertas Edge; no se modificaron para mezclar correcciones ajenas.
No se ejecutó Semgrep ni se afirma
una ejecución satisfactoria de toda la aplicación en Windows.

## 7. Estado final y pendientes

- **#3590:** inventario completado y contrastado con BD de desarrollo en solo lectura.
- **#3591:** dependencia parcial demostrada, mensaje técnico preparado; no enviado ni migración aplicada.
- **#3592:** partes independientes implementadas; faltan los cinco parámetros M09 y la regla temporal aclarada.
- **#3593:** pruebas independientes ejecutadas, integración condicional DEV-02 aprobada; límites del entorno documentados.
- No hay migraciones nuevas, modificaciones de BD compartida, push ni force-push.
- La instancia PostgreSQL temporal se detuvo y eliminó después de conservar la evidencia sanitizada. La entrega se guarda en un commit local de la rama indicada; su identificador se obtiene con `git log -1 --oneline` y se comunica en la entrega.
- Antes de activar los consumidores, cargar explícitamente los parámetros revisados en el entorno autorizado.
- Integrar DEV-02 para que la persistencia completa RF-62 respete inmutabilidad. La parametrización por sí sola no corrige ese defecto previo.
- DEV-05 está en otra rama: al integrarlo, su composición del worker debe recibir este adaptador real. Ese archivo no existe en la base de esta rama y no se copió como parte de DEV-14.
- La función SQL legacy `modulo4.fn_verificar_ventana_retroalimentacion` mantiene 90 días y pertenece al camino legacy `predicciones/auditorias_predicciones`. No se encontró llamada Python a ese camino; el backend RF-72 usa `resultados_inferencia/retroalimentaciones_clinicas`. No se alteró una función sin consumidor activo demostrado.
- Resolver `fcntl` en un entorno compatible para ejecutar los archivos no recolectables y el test restante de aplicación completa.

El alcance comprobado permite configurar dinámicamente la calidad, confianza
y ventana MLOps sin redespliegue. No se declara completada toda #3520 ni se
resuelven por suposición las decisiones pendientes de Análisis.

## Parámetros de RF-57 por API (INC-M03-168-G76)

Además del script offline, los parámetros de RF-57 (`umbral_confianza_edge_ia`, `rf57_umbral_confianza_minimo`, `rf57_ventana_reevaluacion_min` y los de tormenta) se consultan con `GET /configuracion/parametros-alertas` y se cambian con `PATCH /configuracion/parametros-alertas` (`{"parametros": {...}}`), con el recurso 21 (`configuraciones_globales`), R y U. La escritura reutiliza `ConfigurarParametrosMLOpsUseCase.execute`: mismo lock, misma validación y el autor queda en `id_usuario_modificador`.
