# INC-M06-323-G27 — Una cosecha pendiente por falta de precio o de costos de venta no podía continuar (RF-85)

**RF:** RF-85 v1.2 (FA-1 y FA-2), con RF-84 R2. **Issue:** #1010.
**Estado:** corregido con pruebas unitarias y la cola verificada contra el esquema real. Sin migración.
**Requiere cambio en el frontend** para la parte (b).

## Causa

- **(a)** Sin precio del producto, el evento productivo quedaba en `MEDICION_PENDIENTE` y se auditaba
  `RECONOCIMIENTO_PRODUCTO_PENDIENTE`. Después de registrar un precio ESTIMADO justificado (`POST /finanzas/precios`)
  y volver a procesar, la cosecha no se reconocía. La cola (`EventoM02Adapter._PENDIENTES`) solo volvía a tomar
  eventos sin procesar, en `ENCOLADO_CIERRE` o en `ERROR` con menos de 3 intentos. Además, repetir la cosecha en M02
  da 409 por duplicado.
- **(b)** Sin costos de venta en M09 la cosecha quedaba pendiente y no había ninguna operación para ingresar a mano
  los costos del producto con su justificación.

## Corrección

### (a) La cola retoma la cosecha cuando cambia lo que faltaba

`_PENDIENTES` agrega la condición `_COSECHA_REANUDABLE`: un evento productivo en `MEDICION_PENDIENTE` vuelve a la
cola si, después de su `fecha_procesamiento`, se registró:
- un precio de la especie (`precios_mercado.fecha_registro`), o
- un parámetro de costos de venta de la especie (`parametros_costos_venta.fecha_creacion`; cada cambio inserta una
  fila).

Cada intento actualiza `fecha_procesamiento`. Si sigue faltando algo, la cosecha no se reintenta hasta el siguiente
cambio, así que no se acumulan alertas en cada pasada. Con el precio de 3.500 y el 6 % de costos, los 200 kg se
reconocen por 658.000.

### Bandeja de cosechas pendientes

`GET /finanzas/productos/pendientes` (permiso `valoracion_activos` / Leer) lista los eventos productivos en
`MEDICION_PENDIENTE` con:
- activo (identificador, especie, finca, clasificación);
- producto, unidad, cantidad y fecha de la cosecha;
- motivo, fecha del último intento e intentos;
- `admite_costos_manuales`: falso para la cosecha de consumo.

### (b) Costos manuales del producto

`POST /finanzas/productos/pendientes/{id_evento}/reconocimiento` (permiso `valoracion_activos` / Ejecutar), con
cuerpo `{"costos_manuales": {"transporte", "comisiones", "impuestos", "otros"}, "justificacion": "..."}`.

| Caso | Respuesta |
|---|---|
| Sin ningún costo | 400 `COSTOS_VENTA_REQUERIDOS` (`field: costos_manuales`) |
| Justificación ausente, en blanco o de menos de 20 caracteres | 400 `JUSTIFICACION_REQUERIDA` (`field: justificacion`) |
| El evento no es una cosecha pendiente | 404 `COSECHA_PENDIENTE_NO_ENCONTRADA` |
| Sigue faltando algo (por ejemplo, el precio) o el activo es de consumo | 422 `COSECHA_SIGUE_PENDIENTE` con el motivo; no se guarda nada |
| Válida | 200 `{id_evento, resultado: PROCESADO}` |

Cuando es válida:
- el cálculo del producto queda MANUAL, con la justificación, el Contador y sin parámetro de M09;
- el producto queda con la justificación;
- `PRODUCTO_AGRICOLA_RECONOCIDO` se audita con el Contador como actor y `justificacion_costos_manual`;
- el evento queda `PROCESADO`.

`ProcesarEventosM02UseCase.reconocer_cosecha_pendiente` reutiliza el mismo flujo de `_producto` (precio, cálculo,
producto, línea y auditoría). Si el producto tiene parámetro en M09, los costos manuales reemplazan solo los
componentes que se ingresan.

## Decisiones

1. **Sin precio manual en el endpoint.** FA-1 ya se cubre con un precio ESTIMADO justificado en Precios de mercado,
   que exige justificación y queda en su historial. La cola lo toma sola.
2. **La cosecha de consumo no admite costos manuales del producto.** Su valor sale de remedir el activo con sus costos
   de venta (RF-84).
3. **Reintento por cambio, no en cada pasada.** Así se evitan alertas repetidas y cargas inútiles en la cola.

## Impacto en el frontend

Se revisaron todas las ramas del front (2026-11-09): ninguna mostraba las cosechas pendientes ni permitía ingresar sus
costos. El PR del front `fix/m06-inc323-g27-cosechas-pendientes` agrega en Productos la bandeja de cosechas pendientes
y la acción «Ingresar costos». La parte (a) no necesita front: el botón «Procesar eventos pendientes» que ya existe
retoma la cosecha.

## Verificación

`tests/financial_valuation/test_inc_m06_323_g27_cosecha_pendiente.py` (14 pruebas):
- (a) sin precio queda pendiente; con el precio ESTIMADO se reconoce por 658.000;
- (b) los costos manuales reconocen la cosecha sin parámetros de M09: cálculo MANUAL, justificación, Contador como
  actor, 658.000;
- consumo: no admite costos manuales;
- validaciones del caso de uso: sin costos, sin justificación y justificación corta dan 400; evento no pendiente da
  404; si sigue pendiente da 422 con rollback; si es válida, `PROCESADO` y commit;
- contrato HTTP: 400 con `error_code` y `field`; el `GET` de la bandeja devuelve la lista.

La bandeja se probó contra otra BD efímera: trae las dos cosechas pendientes (una de producción y una de consumo),
deja fuera la procesada y marca `admite_costos_manuales` según la clasificación.

La cola se probó contra una BD efímera con `alembic upgrade head`:
- la cosecha pendiente no vuelve sin cambios;
- vuelve después de registrar un precio de la especie;
- tras un nuevo intento sin cambios, sale otra vez de la cola;
- `cosecha_pendiente(500)` devuelve el evento y `cosecha_pendiente(999)` devuelve `None`.
