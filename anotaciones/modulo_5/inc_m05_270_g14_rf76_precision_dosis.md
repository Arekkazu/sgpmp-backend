# INC-M05-270-G14 · RF-76 · Precisión de dosis de medicamentos (#954)

Fecha: 2026-11-07, America/Bogota. Identidad Git consultada: Leandro.

## Resultado y causa raíz

El defecto se reprodujo en Desarrollo Backend/BD. La columna modulo5.registros_medicamentos.cantidad y su ORM eran numeric(10,3), mientras que el contrato exige decimal(10,4) y el ledger ya admite cuatro decimales.

PostgreSQL convierte el valor a la escala de la columna antes de ejecutar el trigger BEFORE INSERT. Así, 0.0001 y 0.0004 llegan al trigger como 0.000 y disparan CANTIDAD_INVALIDA/P0001. Como no existía traducción de ese rechazo, el cliente recibía 500 ERROR_INTERNO. Para 0.0005 y 0.0015 el INSERT sí funcionaba, pero guardaba 0.001 y 0.002. No era un redondeo explícito del caso de uso o del dominio Python.

La regresión previa dio cuatro fallidas esperadas y dos controles aprobados. Evidencias: .pytest_cache/inc954_antes.xml/.log y inc954_bd_errores.jsonl. Se conserva la captura técnica solo en el entorno local; no se expone al cliente.

## Alcance y contrato

Se conservan los contratos de ruta, respuesta, JWT/RBAC, acceso por finca, fases, retiro RF-44, cálculos de costo por trigger y transacciones. Cambios:

- DTO: dosis_aplicada con max_digits=10 y decimal_places=4, manteniendo la validación y el mensaje existente de dosis positiva.
- ORM: cantidad Numeric(10,4).
- PostgreSQL: nueva revisión d2e71a4c980b, padre b7e2d94c1a68, para alinear cantidad.
- Traductor compartido: solo P0001 originado por modulo5.fn_trg_calcular_costo_total_medicamento con etiqueta CANTIDAD_INVALIDA o COSTO_INVALIDO se convierte a 400 VAL_ENTRADA, campos dosis_aplicada/costo_unitario y mensajes seguros. Función, etiqueta o SQLSTATE desconocidos conservan error de infraestructura.
- Referencia pública de la API actualizada.

Regla para precisión excesiva: se rechazan con 400 los valores que no caben exactamente en decimal(10,4), sin redondearlos. Se admiten ceros finales numéricamente equivalentes: 0.00010 se conserva como 0.0001, y 1.23450 como 1.2345. Se admite notación 1e-4; 1e-5 no es representable y se rechaza. El máximo es 999999.9999 (seis enteros y cuatro decimales). No se restringe arbitrariamente la dosis por recomendaciones clínicas.

| Dosis | Antes | Ahora |
|---|---|---|
| 0.0001 | 500, sin registro | 201, cantidad 0.0001, costo 0.0500 con precio 500 |
| 0.0004 | 500, sin registro | 201, cantidad 0.0004, costo 0.2000 |
| 0.0005 | 201, guardaba 0.001 | 201, cantidad 0.0005, costo 0.2500 |
| 0.0015 | 201, guardaba 0.002 | 201, cantidad 0.0015, costo 0.7500 |
| 0.001 / 10 | Control correcto | Se conserva |
| 0.00001 / 1.23456 | Sin política de precisión en DTO | 400, sin persistencia |

## Flujo verificado

POST /suministros/medicamentos → JWT y permiso de creación del recurso 48 → activo accesible y fase abierta → DTO/dominio con Decimal sin cuantizar la dosis total → flush de medicamento → trigger de costo → auditoría/hash → ledger → acumulado → RF-80 y outbox RF-79 → RF-44 si hay retiro → commit → notificación.

La dosis total exacta se conserva en respuesta, registros_medicamentos, registro_suministro, vista, JSON de auditoría y GET posterior. El costo exacto se conserva en medicamento, ledger, acumulado, costo_afectado y columna/payload JSON del outbox.

Dosis por individuo conserva el cálculo existente a cuatro decimales; por ejemplo, 0.0015 / 10 se representa como 0.0002. Esto no cambia ni sustituye la dosis total. Los costos monetarios mantienen sus escalas existentes y el redondeo de representación que corresponda a esas columnas; el caso no redefine esa política.

## Paso 0: esquema, datos y RBAC

Se inspeccionó sgpmp_dev solo en lectura (SET TRANSACTION READ ONLY, statement_timeout de 5 s por consulta). Se verificaron precisión/escalas, constraints, índices, triggers y la vista dependiente. Las columnas relacionadas cantidad del ledger, costos/acumulado y dosis_por_individuo ya tienen cuatro decimales; no se duplicaron cambios allí.

Dependencia real: modulo5.vw_m05_aplicacion_medicamentos publica cantidad como cantidad_dosis y bloquea ALTER TYPE directo. Se inspeccionaron su definición, propietario sgpmp_owner, opciones y grants. El agregado de inspección no encontró dosis históricas de siete enteros en DEV. Ese resultado no acredita TEST; la migración incluye su propia comprobación bajo lock.

member_dev no pudo consultar modulo1.permisos ni public.alembic_version (42501), por lo que no se presume su contenido o revisión. Las pruebas locales usan los permisos existentes de Administrador/Veterinario y verifican rechazos de Productor y Veterinario sin acceso a finca. No se cambiaron permisos ni RLS de la API.

No se ejecutó DDL/DML oficial ni se enviaron POST a TEST. La revisión de TEST realizada para #948 confirmó en GitHub la aplicación de b7e2d94c1a68; no acredita d2e71a4c980b ni la prueba de #954 en ese ambiente.

## Migración y protección de histórico

La revisión d2e71a4c980b:

1. Bloquea la tabla durante comprobación y cambio para evitar escrituras concurrentes entre ambos.
2. Comprueba que los valores existentes caben en decimal(10,4). Si hubiera siete enteros históricos, aborta con mensaje explícito antes de cambiar el esquema; no los trunca ni borra.
3. Conserva la definición, propietario, opciones, comentario de vista y de columnas, ACL de tabla/columnas, grant option y otorgantes de vw_m05_aplicacion_medicamentos.
4. Retira la vista con RESTRICT, sin CASCADE. Dependencias o personalizaciones no previstas abortan la transacción.
5. Cambia solo cantidad a numeric(10,4) y reconstruye la vista. Elimina grants nuevos adquiridos por default privileges antes de restaurar los originales.
6. No actualiza medicamentos ni recalcula costos o auditorías. Los valores históricos permanecen iguales; la representación puede ganar un cero final.

Downgrade: vuelve a numeric(10,3) únicamente si todas las dosis son representables sin pérdida. Si ya existen dosis con cuarto decimal significativo, se bloquea para impedir redondeo. No se ofrece una reversión destructiva.

Se aplica con el rol autorizado de migración/propietario y capacidad de restaurar los otorgantes existentes. La prueba con owner diferente usa los permisos de migración, no representa al usuario de la API. Los cambios SET LOCAL ROLE se restauran al terminar; si hay error, se revierten con la transacción Alembic y se conserva el error original.

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias de suministros y traductor compartido | 95 | 0 | 0 |
| HTTP/PostgreSQL y migración | 27 | 0 | 0 |
| Total distinto | 122 | 0 | 0 |

Unitarias: tests/supplies y tests/shared/test_db_error_translator.py. Integración: test_inc_m05_270_g14_precision_dosis_integration.py (23 casos) y test_inc_m05_270_g14_migracion_precision.py (4 casos).

Cobertura: valores del reporte; máximo/rango y precisión excesiva; ceros finales y exponentes; petición válida posterior al 400; costos exactos y acumulación de varias dosis; vista/GET/auditoría/outbox; poblacional y retiro; aislamiento por finca/RBAC; rollback posterior al outbox; errores reales de dosis/costo inválidos en trigger; errores desconocidos que no se degradan a 4xx.

Migración: roundtrip transaccional con dosis histórica representable; preservación de owner, security_barrier, comentarios y grants de tabla/columnas con grant option/otorgante; default privileges adicionales no amplían la vista; auditoría histórica y protecciones de tabla intactas; bloqueo del downgrade con cuarto decimal; bloqueo del upgrade con histórico fuera de rango; dependencia de vista adicional que aborta sin CASCADE.

Entorno: PostgreSQL 18, sgpmp_inc954_test exclusivo en localhost:55429, migrado desde cero a b7e2d94c1a68 y luego a d2e71a4c980b. HTTP usa TEST_ROL_APP=sgpmp_app no superusuario/sin BYPASSRLS, con JWT real y restricciones/triggers activos. Siembra, aserciones y DDL se ejecutan con el administrador local; no se presentan como comportamiento normal de la API. Las pruebas de DDL exigen host local y nombre exacto de base.

Shim fcntl solo en lanzadores ignorados para Windows. Se conserva una advertencia preexistente de TestClient/httpx. Se corrigió durante el desarrollo la preparación del test de grants (PostgreSQL exige grantor actual); el resultado final usa el comportamiento real y no desactiva controles. No se suman corridas repetidas al total.

Evidencias ignoradas: .pytest_cache/inc954_antes.xml/.log, inc954_bd_errores.jsonl, inc954_preflight.json, inc954_migraciones.log, inc954_migracion_nueva.log, inc954_unit.xml/.log, inc954_pg.xml/.log y inc954_verificacion.json.

## Despliegue y límites

- Aplicar la migración antes del backend que expone el contrato nuevo y reejecutar TC-M05-G14 en entorno autorizado.
- No aplicar solo la traducción a 400: esa mejora no corrige la precisión de una BD que siga en numeric(10,3).
- No se recuperan dosis originales que ya fueron redondeadas históricamente; no se conoce el valor original y los registros son inmutables. Requiere revisión operativa autorizada si se necesitan correcciones.
- Mantener el permiso pgcrypto de b7e2d94c1a68 y las migraciones previas; no duplicar #948.
- Si una BD tiene históricos fuera de rango o dependencias adicionales, revisar el caso antes de migrar; la revisión falla sin pérdida de datos.
- No se afirma despliegue, aprobación de QA en TEST, validación visual ni entrega del outbox a M06.

## Git y alcance

Rama fix/inc-m05-270-g14-precision-dosis-rf76 desde dev actualizado a 3251d78d2c5822624dde988a94a37331610d1cef; no parte de la rama anterior de #948. Se preservan sus archivos pendientes sin incluirlos en esta entrega.

Tres archivos de producción editados, una migración nueva, tres archivos nuevos de pruebas, una referencia API actualizada y dos informes: diez archivos. Los siete archivos de código contienen la fila de seguimiento INC-M05-270-G14/RF-76 con fecha real e identidad Git consultada. Se conservan filas previas y documentos ajenos.

Commit y push autorizados por el usuario para #954. No se solicitó publicar un PR.

## Cierre local

Se eliminó exclusivamente sgpmp_inc954_test y se comprobó que las demás bases locales permanecieron intactas. Se detuvo el clúster iniciado para esta tarea. Se conservaron scripts y evidencias ignoradas. Evidencia: .pytest_cache/inc954_cierre_bd.log.
