# TC-M09-G75 — RF-24, límites técnicos y validación de `valor_referencia`

Responsable QA Juan Esteban. Solo TEST real. No ejecutar G74 desde aquí. No avanzar a
otro grupo. Grupo de API: **sin Cypress, sin mocks, sin PostgreSQL**.

Ejecución `run-20260906` concluida. Decisión general: **APROBADO**.
TC-M09-142 · TC-M09-143 · TC-M09-144 · TC-M09-145, los cuatro APROBADOS. Sin defectos
que reportar. Consultar `RESULTADOS/run-20260906/TC-M09-G75_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-142 | Ingeniero autorizado, dispositivo activo, sensor asociado a su área, rango técnico publicado | POST con `valor_referencia` = mínimo técnico exacto | 201, calibración persistida con trazabilidad y vigente para su aplicación posterior |
| TC-M09-143 | Mismas precondiciones | POST con `valor_referencia` = máximo técnico exacto | 201, persistida, **sin sustituir** la calibración anterior |
| TC-M09-144 | Mismas precondiciones | POST por debajo del mínimo y por encima del máximo | 400 `VALOR_FUERA_DE_RANGO`, sin persistencia, calibración válida anterior intacta |
| TC-M09-145 | Mismas precondiciones | POST con `""` y con `"abc"` | 400 `VALOR_CALIBRACION_INVALIDO` sobre `valor_referencia`, sin persistencia |

## Contrato revisado una sola vez (solo lectura)

- `POST /configuracion/sensores/{id_sensor}/calibrar` → **201** en éxito.
- Fuera de rango → `VALOR_FUERA_DE_RANGO` (`ValidationError`) → **400**.
- Vacío o no numérico → `VALOR_CALIBRACION_INVALIDO` (`ValidationError`) → **400**.
  El DTO acepta `Decimal | str | None` a propósito para que Pydantic no responda 422
  por tipo y el caso de uso devuelva el 400 que pide RF-24.
- Rango técnico por categoría: `GET /configuracion/sensores/rangos-calibracion`.
  Límites **inclusivos** (`valor_min <= valor <= valor_max`).
- Historial por sensor: `GET /configuracion/sensores/{id_sensor}/calibraciones`.
- Aplicación posterior: el adaptador de telemetría toma la calibración **más reciente
  por `fecha_calibracion`** y aplica `valor_ajustado = ganancia × crudo + offset`.

### Discrepancia documental de TC-M09-144

`Matriz: 422` · `RF-24 v1.0: 400` · `Contrato y OpenAPI: 400` → **oráculo 400**,
resuelto **antes** del primer POST. Se registra como
`TEST_MATRIX_REQUIREMENT_MISMATCH`: es una desactualización de la matriz, no un
defecto del producto. La assertion **no** se cambió en silencio; la justificación
completa está en el informe. QA no modificó la matriz.

## Datos

Descubiertos dinámicamente, sin IDs supuestos: dispositivo activo, sensor activo con
asociación de área vigente (`fecha_finalizacion: null`) y categoría con rango técnico
publicado, prefiriendo `TEMPERATURA` por fidelidad con el original. Se usa **el mismo
sensor** para los cuatro originales, ya que RF-24 mantiene historial por sensor.

Los valores fuera de rango se calculan con **aritmética decimal exacta** sobre el
límite publicado, con el menor incremento de `numeric(10,4)` (`0.0001`), y el cuerpo
JSON se construye con literales exactos: `0.0000` no se degrada a `0` ni `45.0001` a
un binario de coma flotante. TC-M09-144 prueba el rango técnico, nunca un
desbordamiento del tipo.

## Requisitos y ejecución

Ya instalados, no se instala nada: Newman 6.2.2 y `newman-reporter-htmlextra` 1.23.1.

Variables de proceso: `QA_EMAIL` y `QA_PASSWORD` (Ingeniero de campo, actor
funcional), `G75_RUN_ID` y `G75_CASE`. Opcionalmente `QA_DISCOVERY_EMAIL` /
`QA_DISCOVERY_PASSWORD` si el actor no tuviera lectura para el descubrimiento; en
esta ejecución no hizo falta. Las credenciales nunca se escriben en archivos.

`G75_CASE` admite: `TC-M09-142`, `TC-M09-143`, `TC-M09-144-LOW`, `TC-M09-144-HIGH`,
`TC-M09-145-EMPTY`, `TC-M09-145-NONNUMERIC`.

```
NODE_PATH=<npm root -g>  node run-newman.cjs      # una invocación = un subescenario
NODE_PATH=<npm root -g>  node verificar-cierre.cjs # GET final + escaneo de secretos
```

Presupuesto por original, implementado y no solo documentado: **TC-142 y TC-143 hasta
2 POST** (el segundo solo con reintento justificado), **TC-144 exactamente 2** (bajo
mínimo y sobre máximo) y **TC-145 exactamente 2** (vacío y no numérico). El runner
rechaza un tercer POST del mismo original y también sobrescribir la evidencia de un
subescenario ya ejecutado. Las dos variantes de TC-144 y TC-145 **no son reintentos**:
por eso sus archivos se nombran por escenario y no `intento1/2`.

Si un dato inválido llegara a persistir, o si un histórico resultara alterado, el
runner marca `STOP_ALL`: detener sin limpiar, sin borrar y sin restaurar.

## Evidencia

`RESULTADOS/<G75_RUN_ID>/` con el JSON sanitizado por subescenario, los datos y
preflight, el estado acumulado (`estado-g75.json`, que conserva `HISTORY_INITIAL` y
la calibración válida anterior), la verificación final de solo lectura, el escaneo de
secretos, el estado de Git y el informe; los HTML reales de htmlextra en
`RESULTADOS/<G75_RUN_ID>/newman/`.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.

Las calibraciones creadas (**#10** con `0.0000` y **#11** con `45.0000`, sensor 6) se
conservan como evidencia TEST: no se eliminan ni se desactivan.
