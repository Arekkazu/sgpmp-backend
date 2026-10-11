# INC-M02-87-G81 — Definición funcional: la transferencia interna (RF-48) es siempre del activo completo

**RF:** RF-48 — Transferencia Interna de Activos Biológicos (CU10C).
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`.
**Caso QA:** `TC-M02-139` (grupo `TC-M02-G81`, hallazgo `BLOQ-G81-02`) — **BLOCKED**.

## Qué reportó QA

`TC-M02-139` requiere transferir 40 individuos de un lote de 100 (transferencia parcial). `RegistrarTransferenciaDTO` declara exactamente 4 campos (`infraestructura_origen_id`, `infraestructura_destino_id`, `fecha_transferencia`, `motivo_transferencia`) — ninguno permite expresar una cantidad. QA, correctamente, **no inventó un campo no soportado por el contrato** ni ejecutó una transferencia completa como sustituto (eso habría movido el lote entero de 100, produciendo evidencia engañosa sobre un escenario que no es el que pide el caso de prueba). El caso quedó bloqueado y QA solicitó una definición funcional oficial, planteando explícitamente dos posibilidades:

- **Posibilidad 1:** RF-48 permite cantidad parcial → el contrato necesita representarla.
- **Posibilidad 2:** RF-48 transfiere siempre el activo completo por diseño → la ausencia del campo es el propio mecanismo que impide transferencias parciales, y `TC-M02-139` debe reformularse.

## Decisión (confirmada con el usuario/equipo funcional)

**Posibilidad 2.** La transferencia interna mueve siempre el activo completo:

- Para un activo `INDIVIDUAL`: el individuo entero.
- Para un lote `POBLACIONAL`: la totalidad de `cantidad_actual` en el momento de la transferencia.

No existe la operación "dividir un lote entre dos infraestructuras" en RF-48. La ausencia de un campo de cantidad en `RegistrarTransferenciaDTO` **no es un gap del contrato** — es intencional y ya coincide con cómo el resto del use case está construido: `_cantidad_a_transferir(activo)` (usado tanto en la validación de capacidad C3 como en `listar_infraestructuras_disponibles`) siempre calcula sobre `activo.detalle_poblacional.cantidad_actual` completo, nunca sobre un subconjunto — el código ya asumía esta semántica antes de que QA la cuestionara, solo que nunca se había declarado explícitamente como decisión de negocio.

## Por qué no se agrega el campo

Agregar `cantidad`/`cantidad_transferida` implicaría rediseñar el modelo de datos (¿un lote parcial es una fila nueva de `activos_biologicos` con su propio `detalle_poblacional`, o se resta de la misma fila?), el cálculo de capacidad y densidad (ya corregido en `INC-M02-40-G28`/`INC-M02-41-G28` para el lote completo), y la auditoría — un cambio de alcance mucho mayor que lo que RF-48 especifica. No hay ningún requisito que pida esta funcionalidad; el gap lo introdujo la interpretación de `TC-M02-139`, no el RF.

## Acción para QA

`TC-M02-139` debe reformularse para verificar una condición observable por la API actual — por ejemplo, confirmar que **no existe ningún mecanismo** para transferir una cantidad parcial (ej. enviar un campo `cantidad` no declarado y verificar que Pydantic lo ignora silenciosamente sin fraccionar el lote, o que la única forma de "transferir 40 de 100" es fuera de alcance de este endpoint). Esa reformulación es responsabilidad del equipo de QA, no de este repositorio.

## Cambios

Ninguno en código. Se documenta la definición funcional en este archivo y en `curls_m02_cu10_gestionar_transferencias_historial.md` (sección CU10C).

## Fuera de alcance

- Implementar transferencias parciales — explícitamente descartado por esta decisión.
- Reformular `TC-M02-139` — responsabilidad de QA.
- QA señaló, correctamente, que `BaseDTO` no declara `model_config = {'extra': 'forbid'}`, por lo que un campo desconocido (ej. `cantidad`) sería ignorado en silencio por Pydantic en vez de rechazado — es una observación válida de robustez de API, pero es un cambio transversal a *todos* los DTOs del sistema, no específico de RF-48; queda fuera de este ticket, que es puramente de definición funcional.
