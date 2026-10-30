# INC-M04-220-G032 · RF-68 — Recálculo inmediato ante cambios

Fecha: 2026-10-30. Responsable Git verificado: Leandro. Referencia: [#855](https://github.com/Arekkazu/sgpmp-backend/issues/855).

## Definición funcional confirmada

RF-68 mantiene una contradicción: CA-4 exige actualizar la estimación ante cambios sanitarios y el paso 5.1 solo reutiliza un resultado si Fs, ambiente, densidad y configuración no cambiaron; otra restricción impone mínimo de cinco segundos y máximo de 12 cálculos por minuto y lote.

El usuario confirmó recalcular de inmediato ante cambios de Fs, ambiente, densidad o configuración y utilizar los cinco segundos únicamente como ventana de caché para entradas iguales. Esa excepción permite superar 12 cálculos/minuto cuando las entradas cambian. No se introduce otro límite de frecuencia ni una cola nueva.

Fuentes: ambas copias de RF-68 entregadas en Downloads y la issue consultada en GitHub, que no tenía comentarios adicionales. Se mantienen los otros contratos y criterios existentes; no se agrega una regla sanitaria nueva.

## Reproducción y causa raíz

Con pesos 0.5/0.3/0.2, Fa=0.875, Fd=0.80 y Fs=0.20, el primer cálculo entregaba P=0.5225. Dos segundos después, Fs=0.45 producía HTTP 429 EJECUCION_CONTAGIO_MUY_FRECUENTE y permanecía un único resultado, en lugar de calcular P=0.6475.

Evidencia de diagnóstico: .pytest_cache/g44_reproduccion.log. La regresión previa al cambio también falló por el 429, como consta en g44_antes.xml/log; no se cuenta como validación final.

La causa era la rama posterior al fallo de coincidencia de huella: cualquier entrada diferente dentro de INTERVALO_MINIMO se rechazaba. El cálculo, persistencia y auditoría nunca se ejecutaban para esa solicitud.

## Flujo corregido

1. JWT y RBAC conservan recurso 41/acción Ejecutar. Se comprueba acceso al lote y configuración activa antes de consultar o reutilizar resultados.
2. Se conserva la huella existente del DTO completo y config_version de RF-65. Es una comparación conservadora: una diferencia en datos o timestamps del DTO invalida la caché; no se introduce una equivalencia nueva entre entradas.
3. Solo se reutiliza el último resultado si su antigüedad está entre cero y menos de cinco segundos y la huella coincide. Devuelve HTTP 200 sin persistencia ni auditoría nuevas.
4. Una huella diferente continúa inmediatamente al motor. Se mantienen validaciones de datos, fórmula, pesos, normalización, sincronización y clasificación existentes.
5. El nuevo cálculo se inserta como resultado independiente con su propia auditoría RF-73. No sobrescribe el resultado anterior. Devuelve HTTP 201.
6. Si es ALTO y la confianza no es baja, el flujo existente emite o consolida la alerta RF-57. El resultado queda asociado a ella; la auditoría RF-63 y RF-73 participa en la misma transacción.
7. Un fallo real revierte únicamente la operación nueva. Se conservan los resultados anteriores y el reintento puede ejecutarse de inmediato.

La constante se renombra a VENTANA_CACHE y se retira la respuesta 429 de frecuencia de este POST en OpenAPI. No se altera la jerarquía de errores compartida ni otros endpoints.

## Hallazgo del flujo completo: alerta ALTO

Tras corregir el recálculo, la prueba real del cambio a ALTO detectó un HTTP 500 por falta de confirmación de la evidencia obligatoria RF-63. No era un fallo de la fórmula ni un resultado apto para omitir auditoría.

El adaptador de contagio emitía una alerta automática bajo la identidad del Veterinario. Se reutilizó la identidad de servicio existente mediante como_sistema, exclusivamente alrededor de la emisión/consolidación, después de autorizar el lote. El contexto del solicitante se restaura al salir. El rol SQL sigue siendo sgpmp_app, sin superusuario ni BYPASSRLS.

Este ajuste coincide con la parte de identidad del commit 831ea427 de #852, que no forma parte de la base de esta rama. Se incluye aquí esa corrección mínima necesaria para completar el flujo solicitado; no se copian los cambios de umbrales, dominio o snapshot de #852. Al integrar ambas ramas debe quedar un único bloque de identidad, conservando ambas filas de seguimiento.

## Archivos y arquitectura

| Archivo | Cambio |
|---|---|
| src/prediction/application/use_cases/riesgo_contagio/estimar_riesgo_contagio_use_case.py | Ventana de caché; quitar el rechazo de entradas diferentes; mantener transacción |
| src/prediction/infrastructure/adapters/alerta_contagio_rf57_adapter.py | Identidad de servicio acotada con restauración del solicitante |
| src/prediction/infrastructure/routers/riesgo_contagio_router.py | Documentar 201 inmediato y retirar 429 obsoleto |
| tests/prediction/test_rf68_riesgo_contagio.py | Sustituir expectativa de 429 por recálculo |
| tests/prediction/test_inc_m04_220_recalculo_contagio.py | Casos de orquestación con fakes y reloj controlado |
| tests/integration/test_inc_m04_220_recalculo_contagio_integration.py | HTTP, SQL, auditorías, alertas, RLS y rollback reales |

Además se entregan este diagnóstico y la descripción preparada del PR. Los seis archivos de código tienen una fila de seguimiento de esta tarea con fecha real e identidad Git consultada; se conservan filas anteriores.

No se agregan commit() en repositorios, SQL en entidades ni reglas de dominio en routers. El commit/rollback permanece en el caso de uso; se reutilizan repositorios y mecanismos de error existentes.

## BD, RBAC y migraciones

La inspección oficial fue exclusivamente de lectura: current_database=sgpmp_dev, current_user=member_dev y transaction_read_only=on. Se verificaron tablas, columnas, tipos, índices, restricciones y políticas relacionadas con resultados y auditoría. Las tablas de resultados y auditoría tienen RLS y FORCE RLS; los roles API revisados no son superusuarios ni BYPASSRLS y tienen privilegios SQL sobre las tablas inspeccionadas. No se encontraron triggers de resultados que impongan los cinco segundos.

member_dev recibió 42501 al consultar modulo1.permisos y public.alembic_version; no se presume su contenido ni la revisión desplegada. El RBAC se comprobó en la base local y por HTTP: Veterinario autorizado, Veterinario ajeno 404, Productor 403 y sin JWT 401.

No se requiere una migración nueva ni se modifican permisos, políticas, enums, funciones o triggers oficiales. La base exclusiva local sgpmp_g44_test se migró desde cero a la única head 6bd01d026ac4 del dev actualizado. Los grants de preparación pertenecen únicamente a esa base local.

## Contrato comprobado

| Solicitud | Respuesta y efecto |
|---|---|
| Fs=0.20, Fa=0.875, Fd=0.80 | 201, P=0.5225, primer resultado |
| A los 2 s: Fs=0.45; mismo ambiente y densidad | 201, P=0.6475, segundo resultado e historial conservado |
| Repetición idéntica del segundo cálculo dentro de 5 s | 200, mismo ID; no duplica resultado, auditoría ni frecuencia de alerta |
| Cambio de ambiente, densidad, score poblacional o config_version | 201 inmediato; usa las nuevas entradas/configuración |
| Entradas iguales a los 5 s exactos | 201; ya no corresponde la caché |
| Cambio con sensores insuficientes | 422 ERROR_DATOS_INSUFICIENTES; conserva resultado previo y audita rechazo |
| Cambio a ALTO | 201; crea o consolida una sola alerta con evidencia RF-63/RF-73 |
| Falla después de flush o después de emitir alerta | Rollback del cálculo nuevo, alerta y auditorías; resultado anterior intacto |

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009, tres archivos | 65 | 0 | 0 |
| Integración HTTP/PostgreSQL 18, G032 | 19 | 0 | 0 |
| Total distinto | 84 | 0 | 0 |

Evidencias finales: .pytest_cache/g44_unit.xml/log y .pytest_cache/g44_pg.xml/log. No se suman corridas repetidas ni reproducciones fallidas. La integración conserva una advertencia preexistente de TestClient/httpx.

La prueba de más de 12 cambios dentro de un minuto verifica la política funcional con reloj controlado y fakes; no es una medición de capacidad o latencia bajo carga. No se utilizaron esperas reales de dos o cinco segundos: las fronteras temporales se fijaron explícitamente.

La integración usa TestClient, JWT/RBAC reales y TEST_ROL_APP=sgpmp_app. Una prueba observa current_user=sgpmp_app, rolsuper=false y rolbypassrls=false al guardar el recálculo. Otra comprueba la identidad de servicio dentro de la emisión y la restauración al usuario solicitante después. No se desactivan RLS, restricciones ni triggers.

La creación, consolidación y ausencia de duplicado de alertas están probadas en PostgreSQL, igual que rollback tras resultado, auditoría y alerta. Las salidas RF-66 son datos sintéticos controlados del contrato HTTP; no se ejecuta un motor RF-66 real ni se acredita el funcionamiento de un despliegue compartido.

El shim fcntl permanece exclusivamente en lanzadores temporales de pruebas Windows. Código de producción no se modificó por esa limitación del entorno.

## Base Git y dependencias

Rama fix/inc-m04-220-g032-recalculo-contagio-rf68 creada desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414. Los cambios previos ajenos de dev permanecen en la base; no forman parte de esta corrección.

Las correcciones #852, #853 y #854 no están integradas en esa base. Aquí solo se incluye el ajuste mínimo de identidad de alertas compartido con #852; quedan fuera sus umbrales, la densidad histórica de #853 y la cobertura del 60 % de #854. Al integrar se deben conservar todos los comportamientos y las cabeceras, verificando antes el estado actual en GitHub. No se presenta #855 como sustituto de esas correcciones.

Queda reflejar la excepción de frecuencia confirmada en RF-68 y en la matriz QA, desplegar y reejecutar G032 en TEST autorizado. La cola de concurrencia/FIFO y la agregación de historial no se implementan en esta tarea ni se presentan como verificadas.

Commit y push autorizados por el usuario para #855; no se solicitó publicar un PR. Se preservan AGENTS.md y documentos ajenos; los artefactos .pytest_cache/g44_* no pertenecen al commit.

## Cierre del entorno

Se eliminó exclusivamente sgpmp_g44_test y se verificó que las demás bases locales permanecieran intactas. Se detuvo el clúster iniciado para esta tarea. Evidencia: .pytest_cache/g44_cierre_bd.log. Los logs y scripts se conservan fuera del commit.
