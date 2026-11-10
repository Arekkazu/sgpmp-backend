# INC-M06-336-G36 — No existía un mecanismo público de correctivos para variaciones (RF-86)

**RF:** RF-86 (restricción 5, CA-12, CA-13). **Issue:** #1023. **Casos QA:** TC-M06-009, TC-M06-010.
**Estado:** corregido con pruebas unitarias, de contrato y de punta a punta contra Postgres.
**Requiere migración** (`e6a2c48f9d13`, aprobación del DBA). Sin frontend en este PR.

## Causa

- La protección append-only funcionaba: `tgr_m06_10_inmutabilidad_variaciones` bloquea UPDATE y DELETE sobre
  variaciones, y otro trigger hace lo mismo con las líneas de asiento.
- Pero el router de M06 no tenía ninguna operación de correctivo. `variaciones_valor_razonable.id_variacion_corregida`
  existía y no se usaba.
- PUT, PATCH y DELETE sobre `/finanzas/variaciones/{id}`, `/finanzas/periodos/{p}/variaciones/{id}` y
  `/finanzas/lineas/{id}` respondían 404 genérico, sin código ni orientación (CA-12).

## Decisiones (del equipo, 2026-11-10)

1. **Tabla nueva para la solicitud pendiente.** La variación es inmutable, así que no puede nacer «pendiente» y
   después aprobarse. La solicitud vive en `modulo6.solicitudes_correctivos_variaciones` y la variación correctiva se
   inserta al aprobarla.
2. **Doble control.** Quien aprueba o rechaza debe ser distinto de quien solicitó. Las dos acciones exigen el
   permiso `valoracion_activos` / Ejecutar, que el Contador ya tiene.

## Migración `e6a2c48f9d13` (v5.5.0)

- `modulo6.solicitudes_correctivos_variaciones`: `id_variacion_valor_razonable`, `motivo` (≥ 20), `estado`
  (PENDIENTE / APROBADA / RECHAZADA), solicitante, resolutor, fechas, `motivo_rechazo` (≥ 20 al rechazar) e
  `id_variacion_correctiva`.
  - CHECK de coherencia de cada estado y CHECK de doble control (`id_usuario_resolutor <> id_usuario_solicitante`).
  - Índice único parcial `uq_solicitud_correctivo_variacion_vigente`: una sola solicitud PENDIENTE o APROBADA por
    variación.
  - Permisos para los roles de la app.
- Tipos de auditoría: `CORRECTIVO_VARIACION_SOLICITADO`, `CORRECTIVO_VARIACION_APROBADO` y
  `CORRECTIVO_VARIACION_RECHAZADO`.
- `down_revision = b7e2d94c1a68`, la misma de las migraciones de #993 y #1000. Al mergear las tres habrá que agregar
  una migración de merge de heads.

## Flujo

| Paso | Endpoint | Resultado |
|---|---|---|
| Solicitar | `POST /finanzas/variaciones/{id}/correctivos` `{motivo}` | 201: solicitud PENDIENTE con el monto opuesto; no cambia nada contable |
| Consultar | `GET /finanzas/correctivos?estado=&id_periodo_contable=&id_activo_biologico=` | Solicitudes con su variación, activo, solicitante y resolutor |
| Aprobar (otro Contador) | `POST /finanzas/correctivos/{id}/aprobacion` | Variación correctiva (tipo opuesto, montos negados, valores de referencia invertidos, `id_variacion_corregida` = original) y líneas inversas de las de la original (`revertir_lineas`: par invertido, `es_reverso`, `id_linea_corregida`) |
| Rechazar (otro Contador) | `POST /finanzas/correctivos/{id}/rechazo` `{motivo_rechazo}` | RECHAZADA; la variación puede volver a solicitarse |
| Modificar directo | `PUT`/`PATCH`/`DELETE` en las tres rutas | **409** `VARIACION_INMUTABLE` / `LINEA_ASIENTO_INMUTABLE` con un mensaje que explica la inmutabilidad y orienta al correctivo |

Rechazos:

| Caso | Respuesta |
|---|---|
| Motivo ausente, en blanco o corto | 400 `MOTIVO_REQUERIDO` (`motivo` / `motivo_rechazo`) |
| Variación inexistente | 404 `VARIACION_NO_ENCONTRADA` |
| Corregir un correctivo | 409 `CORRECTIVO_NO_CORREGIBLE` |
| Ya hay un correctivo pendiente o aprobado | 409 `CORRECTIVO_EXISTENTE` |
| Período de la variación no abierto | 422 `PERIODO_NO_ABIERTO` (un período cerrado se corrige con ajuste de período anterior en el cierre) |
| Solicitud inexistente o ya resuelta | 404 `CORRECTIVO_NO_ENCONTRADO` / 409 `CORRECTIVO_YA_RESUELTO` |
| Resolver la propia solicitud | 403 `APROBADOR_DEBE_SER_OTRO` |

El historial del período (`GET /finanzas/periodos/{id}/variaciones`) muestra el original y el correctivo. Agrega
`id_variacion_corregida`, `es_correctivo`, `id_solicitud_correctivo` y `estado_correctivo`, y la línea del correctivo
es su línea inversa.

## Fuera de alcance

- La pantalla para solicitar y aprobar correctivos. No hay ninguna en el front (Variaciones solo lista y filtra).

## Verificación

`tests/financial_valuation/test_inc_m06_336_g36_correctivo_variaciones.py`:
- dominio: monto opuesto, tipo invertido y referencia al original, sin cambiar el original;
- solicitar: 400 con motivo insuficiente; 404, 409 (correctivo de correctivo y correctivo existente) y 422; éxito
  sin tocar nada contable;
- aprobar: variación correctiva, líneas inversas, solicitud APROBADA, auditoría y commit; 404, 409 ya resuelta,
  403 si aprueba el mismo usuario, 422 con período cerrado;
- rechazar: motivo, doble control y éxito;
- HTTP: PUT/PATCH/DELETE en las tres rutas dan 409 con el código y la orientación; 400 sin motivo; 400 con un
  estado fuera del catálogo; el OpenAPI publica crear, aprobar y rechazar.

Contra una BD efímera con `alembic upgrade head`, que incluye la migración nueva:
- original con su línea; la solicitud del usuario 1 queda PENDIENTE; la segunda solicitud da 409;
- la aprobación del mismo usuario da 403; la del usuario 2 crea la correctiva PERDIDA de −4.600.000, que corrige la
  1, y la línea inversa 2, que corrige la 1 y es reverso;
- el historial muestra las dos y la auditoría trae SOLICITADO y APROBADO;
- volver la solicitud a PENDIENTE viola el CHECK;
- UPDATE y DELETE directos sobre la variación y UPDATE sobre la línea siguen bloqueados por los triggers.
