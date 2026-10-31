# RF-68 — Aislar las salidas RF-66 del lote evaluado · INC-M04-222-G034

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Usar únicamente salidas RF-66 del lote | Todas las salidas del payload participaban en el cálculo | Se conservan solo las que identifican al lote solicitado |
| Contar enfermos propios | Tres propios más cinco ajenos daban ocho enfermos, Fs=0.8 y P=0.67 | Tres propios dan Fs=0.3, P=0.42, BAJO y sin alerta |
| Mantener trazabilidad y calidad coherentes | Cobertura, tiempos y Fs incluían entradas ajenas | El filtro precede tiempos, cobertura, cálculo y caché; RF-73 registra los descartes |

Referencias: [#857](https://github.com/Arekkazu/sgpmp-backend/issues/857), INC-M04-222-G034, TC-M04-G034, RF-68 precondición 5/proceso 1, RF-65, RF-57/RF-63/RF-73 y RFC-009.

## Causa raíz

El caso de uso verificaba acceso al lote, pero enviaba toda la lista al motor de cálculo. Ni el conteo de enfermos ni la cobertura comprobaban el origen de las salidas.

M02 representa el lote como un activo biológico y no tiene una relación individuo→lote. El usuario confirmó usar igualdad id_activo_biologico=id_lote y excluir salidas sin ID. Compartir finca, especie o área no demuestra pertenencia.

## Cambios implementados

- Filtrar la lista antes de calcular o reutilizar caché, sin modificar el DTO original.
- Derivar el conteo de enfermos de las salidas propias vigentes, evitando que un conteo agregado del cliente reincorpore enfermos ajenos.
- Calcular cobertura, frescura, sincronía y total inferido sobre entradas filtradas.
- Rechazar con 422 ERROR_DATOS_INSUFICIENTES una lista no vacía sin salidas propias, salvo el camino poblacional independiente por score_anomalia.
- Auditar cantidades recibidas, conservadas, ajenas y sin identidad, sin exponer IDs ajenos.
- Versionar la huella para evitar reutilizar cálculos anteriores a la corrección.
- Conservar alertas por riesgo propio real con la identidad de servicio existente, evidencia RF-63 y restauración del solicitante.
- Actualizar la documentación del DTO y las regresiones del contrato.

## Migración

No requiere migración. No agrega tablas, columnas, permisos ni relaciones. Se conservan RLS/FORCE, triggers y restricciones. Head local: 6bd01d026ac4.

## Contrato resultante

POST /prediccion/riesgo-contagio conserva su estructura y autenticación:

- Solo participa una salida si su id_activo_biologico coincide con id_lote.
- Otro ID o un ID omitido: salida excluida.
- Con una lista recibida, n_enfermos_detectados se deriva de las salidas propias vigentes.
- Si hay diez salidas propias, tres enfermas, y cinco ajenas enfermas: HTTP 201, n_enfermos_detectados=3, Fs=0.3, P=0.42, BAJO y alerta_id=null para el ambiente/densidad del caso.
- Una lista no vacía sin salidas propias y sin score_anomalia: HTTP 422 ERROR_DATOS_INSUFICIENTES, evidencia RF-73 y ningún resultado/alerta nuevos.
- El camino poblacional por score_anomalia se conserva. Una lista originalmente vacía mantiene su flujo previo.
- Salidas ajenas no alteran la huella normalizada. Un acierto de caché válido conserva HTTP 200 y no crea otro cálculo/evento.

La agregación existente de varias observaciones con el ID del lote se conserva. No se introduce una relación de pertenencia de individuos ni una deduplicación distinta del contrato existente.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias RF-68/aislamiento/RFC-009 | 60 | 0 | 0 |
| HTTP/PostgreSQL 18 | 15 | 0 | 0 |
| Total distinto | 75 | 0 | 0 |

Incluyen: mezcla entre lotes y fincas; otro lote en la misma área; falta de ID; conteo agregado contaminado; timestamps ajenos; cobertura; total omitido; score poblacional; caché filtrada; JWT/RBAC/finca; GET posterior; alerta real RF-57/RF-63; restauración de identidad; rollback tras resultado, auditoría y alerta.

HTTP ejecutado con TEST_ROL_APP=sgpmp_app, sin superusuario/BYPASSRLS. La siembra usa el administrador de la base local y no representa al usuario de la API. Las probabilidades son entradas sintéticas; no se ejecutó el clasificador RF-66 real. Una advertencia preexistente de TestClient/httpx.

## Integración con sgpmp_dev

BD oficial inspeccionada exclusivamente en lectura: columnas, constraints, políticas y ausencia de relación individuo→lote. member_dev no pudo consultar modulo1.permisos ni alembic_version; no se presume su contenido.

Pruebas y migraciones existentes ejecutadas en sgpmp_inc857_test local y exclusiva, desde cero. No se ejecutó DDL/DML oficial ni se desplegó la rama.

## Dependencias y pendientes

- Desplegar con autorización y reejecutar G034 usando IDs explícitos coincidentes.
- Adaptar clientes que enviaban salidas anónimas; los IDs distintos de individuos requieren una relación funcional/M02 antes de aceptarlos como pertenecientes al lote.
- No se corrige automáticamente el histórico contaminado ni sus alertas: requiere revisión y recálculo operativo autorizado.
- Integrar preservando las correcciones independientes #852/#853/#854/#855/#856, que no están en esta base. Mantener mínimo del 60 % de #854, recálculo ante cambios de #855 y MVP sin caché de #856.
- El bloque mínimo de identidad de alerta coincide con parte de #852/#855/#856: conservar una sola implementación y todas las cabeceras. Mantener el aviso E10 PARCIAL de #856 al integrar.
- La invalidación de huellas antiguas no modifica el límite de cinco segundos de esta base; un resultado previo con otra huella puede dar 429 temporal hasta vencer esa ventana. #855 aborda por separado el recálculo ante cambios.

## Alcance del commit

Alcance de la entrega: tres archivos de producción, tres de pruebas y dos informes, ocho archivos. Cabeceras con fecha real e identidad Git consultada. Archivos ajenos y evidencias temporales excluidos. Commit y push autorizados por el usuario para #857. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-222-g034-aislamiento-rf66-rf68 creada desde dev actualizado a 3af2d9cf45e831d1aec999a01a5ee57969803414. No parte de la rama MVP anterior. La comparación contiene el filtro, su documentación, el ajuste mínimo de emisión de alerta, pruebas e informes.

Closes #857
