# TC-M06-G96 — RF-88

Caso armado en la rama `laura` (`e5d6934d`, integrada con `origin/test`). La prueba ejecutable es `test_tc_m06_g96_valor_en_libros.py`: llama a `valor_por_costo`. Esa función no recibe la depreciación acumulada. Recibe costo, vida útil en meses, meses transcurridos y deterioro. La prueba usa vida útil y meses que hacen que la propia función calcule la depreciación de cada subcaso.

`tc-m06-g96.json` solo lee OpenAPI. No ejecuta los tres subcasos y no los aprueba.

## Qué cubre cada subcaso

| Subcaso | Datos | Esperado | Capa que sí se ejecuta | Lo que no ejecuta esta prueba |
|---|---|---|---|---|
| TC-M06-05 | Costo 10.000.000, depreciación 2.000.000, deterioro 1.000.000 | 7.000.000 | Dominio: vida 10 meses y 2 meses transcurridos | Ningún endpoint ni la persistencia en TEST |
| TC-M06-06 | Costo 10.000.000, depreciación 10.000.000, deterioro 0 | 0 | Dominio: 12 de 12 meses, deterioro 0 | Ningún endpoint ni la persistencia en TEST |
| TC-M06-07 | Costo 10.000.000, depreciación 7.000.000, deterioro 5.000.000 | Valor en libros 0 y alerta. El resultado matemático es −2.000.000 | Dominio: el piso deja el valor en 0. La comprobación de la alerta no pasa | No hay alerta en el resultado. No hay endpoint ni persistencia |

## Bloqueo de ejecución

Aplica a TC-M06-05, TC-M06-06 y TC-M06-07 por igual.

- No hay endpoint cuyo cuerpo reciba costo, depreciación acumulada y deterioro acumulado.
- `GET /finanzas/activos` y `GET /finanzas/activos/{id}` leen un valor ya guardado. No aplican los datos del subcaso.
- `POST /finanzas/activos/{id}/deterioros` registra un impacto económico ligado a un evento sanitario. No es el cálculo completo del valor en libros y esta colección no lo llama.
- El cierre de período calcula la depreciación desde la vida útil. No recibe 2.000.000, 10.000.000 ni 7.000.000 como monto.
- En TEST existen `modulo6.valoraciones_por_costos`, el trigger `tgr_m06_12_valor_contable_no_negativo` y las restricciones que impiden un valor en libros negativo. Faltan `configuraciones_contables`, `parametros_contables_especies`, `asignaciones_cuentas_contables` y `lineas_asiento_nic41`, así que deterioro y cierre no pueden completar la persistencia.

La colección solo hace `GET /openapi.json`. Si el contrato desplegado llegara a mostrar una operación con los tres montos, tampoco la invoca: guardar el valor sería una escritura. El subcaso seguiría BLOQUEADO hasta una corrida funcional autorizada.

## Ausencia funcional de la alerta (solo TC-M06-07)

Este hallazgo es independiente del bloqueo de ejecución.

- `valor_por_costo`, en `src/financial_valuation/domain/services/nic41.py`, deja el valor en libros en cero con `max(0, costo − depreciación − deterioro)`.
- El trigger de TEST, si el resultado es negativo, asigna `valor_contable_por_costo = 0`. No inserta un aviso ni lanza una alerta.
- `RegistrarDeterioroUseCase` devuelve un texto `aviso` cuando el valor queda en cero después de un deterioro, y escribe `DETERIORO_REGISTRADO` en toda alta de deterioro, también cuando el valor sigue positivo. Ninguno de los dos es la alerta exigida por el subcaso.
- Consultar `GET /finanzas/auditoria` no demuestra que esa alerta se haya generado. La colección no llama esa ruta y no trata un tipo de auditoría como cumplimiento.

## Qué sí existe, y por qué no alcanza

- `valor_por_costo` y su uso en `_depreciar` del cierre.
- Prueba unitaria `test_valor_por_costo_no_baja_de_cero`, con otros montos y sin API ni base de datos. No aprueba estos subcasos.
- Trigger y checks de `valoraciones_por_costos` en TEST. No se ejercitaron con las tres combinaciones: hacerlo sería una escritura.

## Ejecución

Desde la raíz de `sgpmp-backend`:

```powershell
python -m pytest tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G96/test_tc_m06_g96_valor_en_libros.py -v --noconftest
```

`--noconftest` evita el `conftest.py` de `tests/`, que prepara base de datos. Esta prueba no la usa.

`.\correr_newman.ps1 -Caso G96 -Modulo 6 -Rf RF-88` sigue leyendo solo `openapi.json`. Esa corrida no aplica los montos de los subcasos.

## Intento funcional

Se consultaron las rutas reales sin token y el esquema de `sgpmp_test` en solo lectura. No se escribió en la base. Los tres subcasos quedan BLOQUEADO. El informe está en `resultados/resultado_TC-M06-G96_ejecucion_funcional.html` y el resumen en `resultados/resumen_TC-M06-G96.json`.
