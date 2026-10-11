# INC-M09-04-124 (#316) — Aplicación fallida de plantilla no auditada

Fecha: 2026-09-18

## Síntoma reportado

Un intento fallido de aplicación de plantilla (con rollback) no quedaba
registrado en ningún lugar consultable — ni en `/configuracion/plantillas/historial`
ni en auditoría. El bloque `except` de `AplicarPlantillaUseCase` nunca invocaba
al repositorio de auditoría. El rollback de datos en sí funcionaba bien; el
problema era exclusivamente de trazabilidad.

## Resolución

Mismo mecanismo agregado en INC-M09-01-109 (#319):
`AplicarPlantillaUseCase.execute()` envuelve toda la validación y aplicación
en un try/except que audita cualquier fallo (`tipo_operacion=APPLY`,
`resultado=FALLIDO`) en una transacción propia, después de deshacer la
operación principal. No fue necesario código adicional en esta rama — solo la
prueba de regresión.

## Prueba de regresión agregada

`tests/integration/test_rf32_aplicacion_fallida_auditoria.py`: fuerza un
conflicto de concurrencia (`fecha_actualizacion_especie_destino` desincronizada,
412) y verifica que:
1. No aparece ningún registro en `/configuracion/plantillas/historial` para
   ese intento (el rollback de datos sigue funcionando — nada se escribe a
   medias).
2. Sí aparece una fila `APPLY`/`FALLIDO` en `/configuracion/plantillas/auditoria`,
   con el `id_especie_destino` del intento en el detalle.

## Nota sobre el rollback de datos (no auditado aquí, ya correcto)

El plan de esta tarea contemplaba revisar también que el rollback de
`ciclo_repo`/`metrica_repo`/`umbral_repo`/`patologia_repo` siguiera íntegro
ante un fallo a mitad de escritura. Por lectura de código: todos esos
repositorios usan `flush()`, nunca `commit()` (regla no negociable del
proyecto), así que un `db.rollback()` en cualquier punto revierte todo lo
escrito hasta ahí en la misma transacción — la prueba de este issue no
necesitó forzar un fallo *a mitad de la escritura* (una violación de
constraint de BD a mitad del loop) para confirmarlo, porque esa garantía la
da el motor de transacciones, no lógica de aplicación que pudiera romperse.
