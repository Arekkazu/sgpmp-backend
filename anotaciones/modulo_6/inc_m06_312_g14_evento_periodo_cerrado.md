# INC-M06-312-G14 — Un evento con fecha en un período cerrado no se bloqueaba (RF-83, RF-85, RF-86)

**RF:** RF-83 (precondición 3, restricción 2), RF-86 (paso 1 c, FA-2), RF-85 (G28, TC-M06-126) y RF-87. **Issue:** #999.
**Rama:** apilada sobre la de INC-M06-308-G12 (#995). Usa su notificador en el procesador de eventos y su
cola de alertas del medidor. El PR apunta a esa rama.
**Estado:** corregido con pruebas unitarias. Sin cambios de BD.

## Causa

`Contabilizador.periodo_para` manda un hecho de un período CERRADO al primer período abierto posterior.
Es la regla de RF-87 para **correcciones** del Contador («asientos de ajuste o reversión registrados en el
período siguiente»). El procesador de eventos de M02 la usaba también para eventos biológicos nuevos.
Con el período 77 cerrado, un pesaje con fecha de ese período se midió en el 78 (`PROCESADO`, origen
EVENTO) sin bloqueo, sin alerta y sin registro del intento. Lo mismo con una cosecha (RF-85): el período 179
estaba cerrado y se reconoció en el 180.

Lo que piden los RF:

- RF-83 precondición 3 y restricción 2: no se ejecutan mediciones sobre períodos cerrados.
- RF-86 paso 1 c: si el período no está ABIERTO, «el activo queda en estado MEDICION_PENDIENTE para ese
  evento específico».
- RF-86 FA-2: «rechaza el registro sin modificar ningún dato y notifica al Contador indicando la causa».

## Corrección

- `Contabilizador.periodo_cerrado_en(nit, dia)`: el período CERRADO que contiene el día, si existe.
- `ProcesarEventosM02UseCase._procesar` revisa el período antes de buscarlo con `periodo_para`, para
  los eventos que valoran: crecimiento, ingreso, baja y productivo. Si el período está cerrado:
  - el procesamiento queda `MEDICION_PENDIENTE`, con el mensaje como detalle (este resultado no se reintenta);
  - se escribe `MEDICION_PENDIENTE` (WARNING, `motivo = PERIODO_CERRADO`) en RF-94, en el período cerrado;
  - se alerta al Contador de la finca después del `commit()`;
  - no se crea nada en el período siguiente.
- `EventoM02.encolado_en_cierre`: el adaptador lo toma de `procesamientos_eventos_m02.resultado =
  'ENCOLADO_CIERRE'`. Esos eventos llegaron mientras su período estaba EN_CIERRE y, por RF-87 («se encolan
  y se procesan en el siguiente periodo»), siguen yendo al período siguiente sin rechazo.
- `Medidor.alertar_pendiente` pasa a ser público (antes `_alertar_pendiente`, de #995) para que el
  procesador lo use.

Mensaje (detalle del procesamiento y bandeja del Contador):
«El evento del 2026-11-08 del activo BOV-007 no se valoró: su fecha cae en el período contable del 2026-11-01
al 2026-11-30, que ya está cerrado. Si el hecho debe reconocerse, regístrelo como ajuste en el período abierto.»

## Decisiones

1. **Sin migración.** `MEDICION_PENDIENTE` ya es resultado válido de `procesamientos_eventos_m02`
   (`ck_procesamiento_evento_m02_resultado`) y tipo de evento de RF-94. Es el estado que nombra RF-86 paso 1 c.
2. **Solo eventos de M02.** Costos, reconocimientos, cotizaciones y deterioros siguen usando
   `periodo_para`; el ticket no los incluye. RF-90 FA-4 pide rechazar con `PERIODO_CONTABLE_CERRADO`;
   queda para revisar aparte.

## Verificación

- `tests/financial_valuation/test_inc_m06_312_g14_evento_periodo_cerrado.py`:
  - crecimiento, productivo, baja e ingreso en período cerrado quedan pendientes, sin `periodo_para` ni
    medición; auditados en el período 77; con aviso después del `commit`;
  - el evento encolado durante el cierre va al período siguiente;
  - el período abierto se mide normal;
  - los eventos sin efecto no se tocan;
  - `periodo_cerrado_en` según el estado.
- `test_inc_m06_308_g12_alerta_medicion_estimada.py`: sus fakes reciben `periodo_cerrado_en` y `encolado_en_cierre`.
- La consulta `_PENDIENTES` con la columna nueva se ejecutó sin error en una base efímera local con
  `alembic upgrade head`, borrada al terminar. En `sgpmp_dev`, `member_dev` no tiene permiso sobre
  `modulo2.eventos_ingresos`, igual que con la consulta original.
