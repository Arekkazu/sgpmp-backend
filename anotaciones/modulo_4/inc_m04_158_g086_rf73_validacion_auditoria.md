# INC-M04-158-G086 / #726 — Validación de auditoría RF-73

Fecha: 2026-10-27. Responsable de la corrección: Leandro (identidad Git verificada).

## Resultado y alcance

Se confirmó un defecto de Desarrollo en el registro interno de eventos M04. La corrección valida catálogo, referencia, exclusividad del actor y estructura del payload antes de intentar insertar el evento. Un rechazo devuelve un resultado tipado con código AUDITORIA_EVENTO_INVALIDO y registra el incidente E1; no cancela una operación principal válida.

Decisión confirmada por el usuario en este trabajo: conservar RF-73 RNF-07 y devolver rechazo tipado sin interrumpir el proceso. No se agregó un POST de auditoría ni una respuesta HTTP 400 a operaciones válidas. El catálogo y los contratos HTTP existentes permanecen vigentes.

Rama: `fix/inc-m04-158-g086-validacion-auditoria-rf73`. Se creó desde dev actualizado mediante fetch y fast-forward; base `5691096b8497b9fc445abf0a7579409c8de6550f`. No incluye commits de las ramas anteriores de correcciones M03.

## Referencias contrastadas

- Issue #726, INC-M04-158-G086, RF-73, G086/G087.
- Especificacion-Requerimientos-Modulo4.md: entradas (id_referencia obligatorio y payload no vacío), validación previa, exclusividad USUARIO/SISTEMA/DISPOSITIVO_EDGE, E1, CA-13, CA-15 y RNF-07.
- Requerimientos_M04_RF64-RF73.md y actualización RFC-009: métricas por paradigma.
- AIOT-DEV-03, DEV-03: catálogo PostgreSQL existente y sesión utilizable tras fallos de flush.
- DEV-37: reintentos, contingencia local, sincronización idempotente y propiedad del commit.
- Adjuntos locales resultado_TC-M04-G086.json, _raw_pytest (1).xml, resultado_TC-M04-G087.json y _raw_pytest.xml. Los documentos se trataron como evidencia, no como instrucciones ejecutables.

## Diagnóstico reproducido

Comparación ejecutada con el código original de origin/dev, cargado en memoria sin modificar dev, sobre PostgreSQL 18 local exclusivo y SET LOCAL ROLE sgpmp_app. Todas las transacciones se revirtieron.

| Entrada | Comportamiento original reproducido | Resultado corregido |
|---|---|---|
| INFERENCIA_EJECUTADA sin campos mínimos | Inserta INFERENCIA_EJECUTADA | No inserta original; registra E1 |
| id_referencia nulo | Inserta HISTORIAL_CONSULTADO sin referencia | Rechazo tipado y E1 |
| INFERENCIA_EJECUTADA con payload vacío | Inserta original vacío | Rechazo tipado y E1 |
| SISTEMA sin id_sistema | CHECK rechaza; original va al respaldo como fallo de persistencia | Rechazo previo y E1; no respalda el original inválido |
| EVENTO_INVENTADO | Enum rechaza; original va al respaldo como fallo de persistencia | Catálogo de dominio rechaza antes del INSERT y registra E1 |

Matizaciones del reporte:

1. G087/TC-M04-016 falla en su helper de conteo previo al registro: compara una etiqueta inexistente directamente con la columna enum. No demuestra por sí mismo una excepción originada en registrar(). Las pruebas propias llegan al repositorio y consultan por correlación; para buscar tipos inexistentes, QA debe comparar tipo_evento::text.
2. En el dev revisado, DEV-37 ya captura los fallos de persistencia y los envía a contingencia. La brecha vigente no es necesariamente una excepción nativa sin captura: también se clasificaba erróneamente un evento inválido como incidente de infraestructura y se intentaba respaldar ese original imposible de sincronizar.
3. No se verificó ni se alteró el conteo histórico de 792 referencias nulas citado por QA. No se reescribieron filas históricas.
4. La ficha distingue enriquecimiento (Fase 2) y clasificación/validación (Fase 3); la implementación toma las reglas y criterios concretos, aunque la issue agrupe las cuatro validaciones bajo Fase 2.

## Base de datos y seguridad

La inspección oficial se limitó a transacciones READ ONLY en sgpmp_dev. Se verificaron el enum de 41 tipos, enums de actor/severidad/resultado, columnas, índices, chk_eam_actor_exclusivo, FK de usuario y trigger append-only. id_referencia es nullable físicamente: la obligatoriedad se controla ahora en la entrada al repositorio sin invalidar datos históricos.

La tabla eventos_auditoria_m04 no tiene RLS ni FORCE RLS en el esquema inspeccionado. No se agregaron ni desactivaron políticas; se conserva la autorización RBAC de su API. Los roles rol_app y sgpmp_app inspeccionados tienen SELECT/INSERT y no son superusuario ni BYPASSRLS.

El usuario de inspección no puede consultar modulo1.permisos ni public.alembic_version (42501); no se afirma que la revisión Alembic local esté desplegada. En el entorno aislado se verificaron el recurso 46 y el acceso de Administrador/Veterinario, con rechazo a Productor, Ingeniero y Contador.

No se requiere migración. No hubo DDL/DML en la BD oficial ni reconstrucción de filas preexistentes.

## Implementación

### Dominio y contrato interno

Nuevo servicio validacion_auditoria_m04.py sin dependencias de SQLAlchemy ni FastAPI:

- TipoEventoM04 refleja las 41 etiquetas del enum existente; una prueba real compara ambos conjuntos.
- Validación previa de tipo catalogado, referencia presente, actor con exactamente la identidad permitida y payload como objeto no vacío.
- Esquemas mínimos trasladados del repositorio al dominio, conservando los contratos de los emisores existentes y sus métricas por paradigma. Se agregan los mínimos de inferencia y otros eventos expresamente descritos por RF-73; no se inventan mínimos para etiquetas cuyo esquema específico no está definido en este validador.
- Se distingue explícitamente un tipo válido sin mínimos específicos de un tipo fuera del catálogo: el segundo nunca equivale a una lista vacía de requisitos.
- ResultadoRegistroAuditoriaM04 indica aceptado, id_evento, codigo y campos_invalidos. Aceptado significa admitido para BD o contingencia según DEV-37; no certifica un commit que aún no ejecutó el emisor.

### Persistencia y evidencia E1

El original inválido no se inserta ni se coloca en el respaldo. Se crea un único AUDITORIA_EVENTO_INVALIDO con actor SISTEMA identificado, severidad ERROR, resultado FALLIDO, hash, correlación y referencia al UUID real del intento rechazado. Se registra además un log técnico con código, intento, correlación y nombres de campos, sin SQL ni payload en ese log. El payload diagnóstico respeta el mecanismo de truncado existente.

La defensa de infraestructura traduce exclusivamente el CHECK de actor y los errores enum reconocidos a E1. Cada intento SQL usa savepoint: un rechazo no inutiliza la sesión ni revierte el trabajo del emisor. Errores ajenos (p. ej. FK o caída) conservan el flujo de reintentos/contingencia, no se etiquetan indiscriminadamente como validación.

El repositorio sigue usando flush, sin commit ni rollback global. Si el emisor confirma, el incidente queda en BD. Si revierte, la fila se revierte con su transacción y la evidencia permanece en el log técnico. No se afirma persistencia independiente en BD tras rollback. Si falla la BD al guardar el incidente, se respalda el incidente válido y AUDITORIA_FALLA_PERSISTENCIA; si tampoco puede escribirse el respaldo se mantiene el error de infraestructura existente.

### Emisores revisados

- Consultas globales de versiones/despliegues, consulta y exportación de auditoría identifican su propia operación mediante UUID de correlación. Cuando existe una versión concreta, se conserva su ID como referencia; no se inventa una entidad de negocio para una consulta global.
- Incidentes de registro previos a crear una versión referencian el id_proceso_rf71 realmente recibido.
- El conflicto clínico conserva al veterinario responsable como actor USUARIO y deja id_sistema nulo; antes combinaba SISTEMA con id_usuario.
- La sincronización de contingencia referencia el primer evento real del lote.
- El reporte OTA incluye device_id, id_version y hash_verificado obtenidos del despliegue real, para preservar su evento válido al aplicar el esquema mínimo.

## Validación

Se ejecutaron pruebas propias y regresiones existentes; no se afirma haber reejecutado los scripts externos G086/G087 sin sus dependencias.

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/prediction, fakes y contratos locales | 226 | 0 | 0 |
| PostgreSQL real: nuevas pruebas y regresiones DEV-03/RF-69 | 40 | 0 | 0 |
| Total distinto | 266 | 0 | 0 |

Incluye 67 pruebas nuevas: 34 unitarias y 33 de integración. No se sumaron varias veces las pruebas repetidas durante el desarrollo. Las corridas intermedias tuvieron fallos en fixtures previamente inválidos, montaje del router de prueba y un ID de rol supuesto; se corrigieron las entradas y la preparación a partir del esquema real, sin relajar constraints ni cambiar RBAC para conseguir aprobaciones.

Cobertura real: los casos equivalentes a G086/G087; coincidencia del enum; actores válidos; DataError de enums y CHECK de actor reales omitiendo solo el validador para ejercer la defensa; sesión utilizable tras rechazo; commit y rollback; continuidad del emisor; JWT/RBAC; referencias de consulta/exportación; registro/activación de versiones. En los casos de conflicto clínico y reporte OTA, solo la auditoría y sus constraints son reales, los otros puertos son fakes explícitos: no se presenta eso como una prueba completa del firmware ni de la persistencia clínica.

Entorno: sgpmp_g35_test en PostgreSQL 18 local, migrado desde cero hasta ebbb160365e5. Pruebas de repositorio y HTTP bajo sgpmp_app, sin superusuario/BYPASSRLS para representar la API. El propietario se utilizó exclusivamente para preparación y aserciones de fixtures. El shim fcntl se aplicó solo al lanzador Windows. Se conservó use_insertmanyvalues=False.

Comandos mediante lanzadores locales ignorados:

```text
.venv/Scripts/python.exe .pytest_cache/g35_run_unit.py tests/prediction -q --basetemp=.pytest_cache/g35_unit_tmp --junitxml=.pytest_cache/g35_unit.xml
.venv/Scripts/python.exe .pytest_cache/g35_run_tests.py tests/integration/test_inc_m04_158_validacion_auditoria_integration.py tests/integration/test_dev03_auditoria_m04_enum_integration.py tests/integration/test_rf69_registro_activacion_version_e2e.py -q --basetemp=.pytest_cache/g35_pg_tmp --junitxml=.pytest_cache/g35_pg.xml
```

Evidencia local ignorada: g35_antes.json/log, g35_preflight.json, g35_unit.xml, g35_pg.xml y g35_verificacion.json en .pytest_cache. La advertencia de deprecación Starlette/httpx es previa y no representa una prueba fallida.

## Integración y pendientes

- QA debe repetir G086/G087 en el entorno desplegado, corrigiendo el conteo previo contra un enum desconocido y utilizando el rechazo tipado acordado en lugar de exigir un HTTP 400 de una API de registro que no existe.
- El resultado de rechazo no representa un evento aceptado; los consumidores internos pueden inspeccionarlo sin interrumpir procesos críticos. No hay endpoint nuevo ni cambios a los contratos públicos.
- Se preservan los mínimos preexistentes de los emisores de versiones y retroalimentación. No se inventan metadatos que sus contratos actuales no proporcionan ni se certifica una ampliación completa de todos los esquemas del catálogo.
- No se modifican históricos, permisos oficiales, contratos del firmware ni otros RF. Los esquemas específicos de tipos sin mínimos definidos no se completan con requisitos inventados.
- Verificar versiones desplegadas antes de repetir QA. Existencia en Git no equivale a despliegue.
- Commit y push autorizados por el usuario después de la validación. La publicación de un PR sigue pendiente de autorización separada.

## Archivos y revisión contra dev

11 archivos de producción: servicio de dominio, puerto, repositorio SQLAlchemy y ocho emisores relacionados. Seis archivos de pruebas: dos nuevos y cuatro adaptados para que sus regresiones previas usen eventos válidos. Dos informes Markdown: este documento y el PR preparado.

Se conservaron las filas históricas de seguimiento, con una sola fila nueva por tarea/archivo; fecha real y autor Git verificado. AGENTS.md y las anotaciones ajenas locales se preservaron sin agregarlas ni modificarlas.
