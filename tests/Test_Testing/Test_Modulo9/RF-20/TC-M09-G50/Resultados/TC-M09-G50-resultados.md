# TC-M09-G50 (TC-M09-101) — Edición de un área productiva existente

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**
**Estado: FALLA / BLOQUEADO** — mismo gap de `TC-M09-G48/NOTA_BLOQUEO.md`.

## Causa raíz

Confirmado en código antes de ejecutar la prueba: `EditarInfraestructuraUseCase.execute()`
(línea 73) revalida `tipo_area` contra `modulo9.tipos_area` en **toda** edición, sin importar
si el tipo cambia o no. Esa tabla no existe en el servidor de test compartido (mismo gap que
bloquea TC-M09-G48/TC-M09-96 y parcialmente TC-M09-G49). Por lo tanto, editar un área
productiva está bloqueado al 100%, igual que registrarla.

Se usó un área ya existente en el entorno (`id_infraestructura=1`, "Estanque-01") porque
registrar una nueva también está bloqueado.

## Resultado de la ejecución (2026-09-06)

```
Paso 2 - Leer el area existente (estado 'antes')       -> 200, nombre="Estanque-01", superficie=2500.00, fecha_actualizacion=null
TC-M09-101 - Editar el area con datos validos distintos -> 500 ERROR_INTERNO (esperado: 200)
Paso 4 - Confirmar que el area no cambio                -> 200, mismos valores que "antes" (sin alteración)
```

4 requests, 8 assertions, 3 failed — las 3 fallas son exactamente las esperadas por el gap
ya documentado (status 500 en vez de 200, y los dos campos que dependían de ese 200).

**Nota técnica:** el primer intento de esta prueba enmascaró el bug real con un `400
VAL_ENTRADA` en vez del `500` esperado, porque `fecha_actualizacion` del área nunca editada
es `null` y el body la envió como el string `"null"` en vez del literal JSON `null` —
corregido generando el fragmento JSON correcto según el caso (`null` vs fecha entre comillas)
antes de insertarlo en el body.

## Cómo cerrar el caso

Igual que TC-M09-G48/G49: aplicar la migración `2dbb6d44046f` en `sgpmp_test`, luego
reejecutar sin cambios:

```bash
newman run "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G50/TC-M09-G50.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G50/Resultados/reporte-TC-M09-G50.html"
```
