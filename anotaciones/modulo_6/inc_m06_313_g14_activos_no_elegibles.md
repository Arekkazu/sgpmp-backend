# INC-M06-313-G14 — La medición por evento no excluía los activos no elegibles (RF-83)

**RF:** RF-83 (medición por evento; restricción 5 para el cierre), RF-82 (PENDIENTE_RECONOCIMIENTO tras la
reversión, CA-14) y RF-85 paso 2. **Issue:** #1000.
**Estado:** corregido con pruebas unitarias y verificación en una base efímera. **Requiere migración (DBA).**

## Causa

`ProcesarEventosM02UseCase._procesar` no revisaba el estado del activo:

- **INACTIVO** (y AISLADO o CERRADO): se medía igual. QA vio 0 → 1 medición y el evento `PROCESADO`.
- **PENDIENTE_RECONOCIMIENTO** (reconocimiento revertido): la cola de `EventoM02Adapter` solo tomaba
  eventos de activos con reconocimiento CONFIRMADO. El evento no se medía, pero tampoco quedaba registro.
- **BAJA**: M02 rechaza los eventos posteriores (409). El propio evento de baja deja el activo en BAJA, y
  M06 debe valorarlo (RF-83 FA-3).

No existía un tipo de evento de RF-94 para la exclusión.

## Gap de BD

| Gap | Decisión | SQL |
|---|---|---|
| Sin tipo de evento para la exclusión | Nuevo valor `MEDICION_EXCLUIDA` | `ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento ADD VALUE IF NOT EXISTS 'MEDICION_EXCLUIDA'` |

- Migración `d81f3a5c7e02` (`v5_5_0`, revisa `b7e2d94c1a68`). **Requiere la autorización del DBA.**
- El downgrade no quita el valor (PostgreSQL no lo permite sin recrear el tipo).
- La migración de INC-M06-306-G07 (#993, `a3c5e7f9b201`) también revisa `b7e2d94c1a68`. Si entran las
  dos, hace falta una migración que una los heads, como las que el equipo ya usa.

## Corrección

- **Elegibilidad:** la misma de `DatosActivo.es_valorable` (ACTIVO o EN_TRATAMIENTO) que usa el cierre.
  - Si no es elegible y el evento no es una BAJA, el evento queda `SIN_EFECTO` y no se mide ni se busca período.
  - Se escribe `MEDICION_EXCLUIDA` (INFO, actor SISTEMA). Payload: `motivo` (`ESTADO_<estado>` o
    `PENDIENTE_RECONOCIMIENTO`), `estado_activo`, `id_evento`, `tipo_evento_m02`, `fecha_evento` y `mensaje`.
  - El detalle del procesamiento lleva el mensaje legible.
- **Cola:** `_PENDIENTES` también toma los eventos posteriores a la última reversión de un activo que quedó
  sin reconocimiento CONFIRMADO (`sin_reconocimiento = true`); se excluyen con `PENDIENTE_RECONOCIMIENTO`.
  - Los eventos de activos que nunca se reconocieron no entran, igual que antes: no son de M06.
  - Los eventos anteriores a un reconocimiento siguen fuera, porque ya están en su valor.
- **Consulta de auditoría:** la vista legible describe el tipo como «Evento sin medición: activo no elegible».

Mensajes:

- «El activo BOV-007 no se midió: está inactivo y solo se miden los activos activos o en tratamiento.»
- «El activo BOV-007 no se midió: su reconocimiento inicial fue revertido y está pendiente de un nuevo reconocimiento.»

## Decisiones

1. **`SIN_EFECTO` y no `MEDICION_PENDIENTE`.** El evento no queda por resolver; para el activo no elegible
   no hay nada que medir. `SIN_EFECTO` no se reintenta.
2. **Solo auditoría, sin aviso al Contador.** El ticket pide registrar la exclusión. RF-85 paso 2 pide
   además notificar al Contador cuando una cosecha llega de un activo INACTIVO. El notificador del
   procesador entra con #995, así que se puede agregar cuando esté en `dev`.
3. **Fuera del alcance:** un reconocimiento bloqueado (RF-82 FA-7) no deja fila en `reconocimientos_iniciales`;
   sus eventos se tratan como los de un activo nunca reconocido.

## Verificación

- `tests/financial_valuation/test_inc_m06_313_g14_activos_no_elegibles.py`:
  - INACTIVO, AISLADO y CERRADO × crecimiento, productivo e ingreso: sin medición, con exclusión registrada
    y su mensaje;
  - PENDIENTE_RECONOCIMIENTO registra la exclusión;
  - ACTIVO y EN_TRATAMIENTO se miden;
  - la baja se valora aunque el activo ya esté en BAJA;
  - los eventos sanitarios no registran nada;
  - descripción legible del tipo.
- Base efímera local (`alembic upgrade head`, borrada al terminar):
  - la migración aplica;
  - `_PENDIENTES` corre sin error (sin datos: valida el SQL);
  - el INSERT real de `MEDICION_EXCLUIDA` pasa los triggers: actor SISTEMA y hash de 64 calculado.
