# RF-76 — Conservar cuatro decimales en la dosis de medicamentos · INC-M05-270-G14

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| dosis_aplicada decimal(10,4), positiva | Columna y ORM numeric(10,3) | Columna, ORM y DTO alineados a cuatro decimales |
| Aceptar 0.0001 sin alterar su valor | Redondeaba a cero y devolvía 500 | HTTP 201, cantidad 0.0001 |
| Conservar 0.0005 y 0.0015 | Guardaba 0.001 y 0.002 sin avisar | Guarda los valores originales y calcula su costo correcto |
| Evitar redondeo silencioso de la entrada | Sin límite de precisión en DTO | Precisión no representable → 400, sin persistencia |

Referencias: #954 · INC-M05-270-G14 · TC-M05-G14/B03 · RF-76 E4 · RF-78 · RF-79/RF-80.

## Causa raíz

PostgreSQL convierte la dosis a numeric(10,3) antes del trigger. Las dosis pequeñas de cuatro decimales se vuelven cero y provocan CANTIDAD_INVALIDA/P0001; las restantes se almacenan redondeadas. El traductor no reconocía ese rechazo y lo convertía en ERROR_INTERNO.

## Cambios implementados

- Validar dosis_aplicada con diez dígitos totales y cuatro decimales, manteniendo el control de dosis positiva.
- Cambiar cantidad del ORM y PostgreSQL a numeric(10,4).
- Conservar la dosis total a través de costo, ledger, acumulado, vista, auditoría y outbox.
- Traducir únicamente los rechazos conocidos de dosis/costo del trigger RF-76 a 400 VAL_ENTRADA, sin exponer SQL ni mensajes internos.
- Documentar la precisión y el rechazo sin redondeo.

## Migración

Nueva revisión d2e71a4c980b, padre b7e2d94c1a68.

Modifica solo registros_medicamentos.cantidad. Recrea la vista dependiente preservando definición, owner, opciones, comentarios, permisos de tabla/columnas, grant option y otorgantes. No usa CASCADE ni amplía grants por default privileges.

El upgrade bloquea históricos que no quepan en decimal(10,4) antes de modificar el esquema. El downgrade bloquea dosis con cuarto decimal significativo para evitar pérdida. No se reescriben valores de negocio ni auditorías históricas; triggers y RLS se conservan.

## Contrato resultante

POST /suministros/medicamentos conserva autenticación, ruta y respuesta.

| Dosis | HTTP | Cantidad guardada | Costo con precio 500 |
|---|---:|---:|---:|
| 0.0001 | 201 | 0.0001 | 0.0500 |
| 0.0004 | 201 | 0.0004 | 0.2000 |
| 0.0005 | 201 | 0.0005 | 0.2500 |
| 0.0015 | 201 | 0.0015 | 0.7500 |

- Dosis <=0: conserva el rechazo 400 de E4.
- Valores no representables con cuatro decimales, como 0.00001 o 1.23456: 400 sin redondeo ni escritura.
- Ceros finales equivalentes, como 0.00010: se aceptan sin alterar el valor.
- Máximo: 999999.9999.
- Dosis por individuo conserva su cálculo existente a cuatro decimales; no reemplaza ni trunca la dosis total.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias de suministros/traductor | 95 | 0 | 0 |
| HTTP/PostgreSQL y migración | 27 | 0 | 0 |
| Total distinto | 122 | 0 | 0 |

Incluyen valores del reporte, límites y precisión excesiva, petición válida posterior al 400, cálculo de costo, ledger/acumulado, vista/GET, auditoría y payload del outbox, poblacional/retiro, RBAC/finca, rollback y traducción real del trigger.

La migración se probó mediante roundtrip y fallos controlados de histórico/dependencias, conservando metadatos y protecciones. HTTP usa sgpmp_app sin superusuario/BYPASSRLS. El DDL usa el administrador de una base local exclusiva. Una advertencia preexistente de TestClient/httpx.

## Integración con sgpmp_dev

Inspección oficial exclusivamente en lectura: numeric(10,3) confirmado, vista dependiente y escalas relacionadas revisadas. No se encontraron dosis de siete enteros en el agregado DEV; no se extrapola a TEST.

member_dev no permitió consultar permisos ni alembic_version. No se presume su contenido o revisión desplegada.

Migración y pruebas ejecutadas en sgpmp_inc954_test local. Sin DDL/DML oficial, despliegue ni prueba de escritura en TEST.

## Dependencias y pendientes

- Aplicar la migración antes de desplegar el backend y reejecutar TC-M05-G14 en entorno autorizado.
- Mantener la revisión b7e2d94c1a68 para pgcrypto; este cambio no duplica #948.
- No aplicar solo el mapeo a 400: la BD debe soportar cuatro decimales para aceptar las dosis válidas.
- Revisar históricos incompatibles/dependencias adicionales si la migración los encuentra; no forzar truncamientos.
- Las dosis ya redondeadas no se reconstruyen automáticamente. No se afirma entrega del outbox a M06 ni validación visual/de TEST desplegado.

## Alcance del commit

Alcance de la entrega: tres archivos de producción, una migración, tres de pruebas, una referencia API y dos informes; diez archivos. Cabeceras verificadas. Archivos ajenos de #948/M03 y evidencias temporales excluidos.

Commit y push autorizados por el usuario para #954. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m05-270-g14-precision-dosis-rf76 creada desde dev actualizado a 3251d78d2c5822624dde988a94a37331610d1cef. La comparación contiene exclusivamente esta corrección y sus pruebas/documentación.

Closes #954
