# TC-M09-G140 — RF-24 v2.0

Cálculo automático de línea base **VISION** (Flujo F): filtrado, p5/p95 y refinamiento iterativo.

- **Requisito:** RF-24 v2.0
- **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo F
- **Tipo:** Reglas de negocio
- **Informe consolidado:** `RESULTADOS/TC-M09-G140_resultado.md`

## Ejecución mixta: dos ambientes, dos RUN

| Caso | Ambiente | Etapa |
|---|---|---|
| TC-M09-284 | TEST | etapa 1 — `apto_para_ia=false` queda excluido |
| TC-M09-285 | TEST | etapa 2 y 3 — p5/p95 y refinamiento |
| TC-M09-286 | **LOCAL AISLADO** | etapa 3 — no convergencia con `max_iter = 1` |

TC-M09-286 es local porque exige cambiar el máximo de iteraciones, y eso **no** puede tocarse en
TEST, DEV, MAIN ni en ninguna configuración compartida.

Los RUN se separan por ambiente y no se mezclan evidencias:

```text
RESULTADOS/run-test-YYYYMMDD-HHMMSS/    evidencia de TC-284 y TC-285
RESULTADOS/run-local-YYYYMMDD-HHMMSS/   evidencia de TC-286
RESULTADOS/TC-M09-G140_resultado.md     informe ÚNICO del grupo (los tres casos)
```

No son reintentos: son dos componentes oficiales del mismo grupo.

## Compuertas de ejecutabilidad

Antes de crear datos o ejecutar cálculos hay que demostrar que VISION es ejecutable. Las dos
compuertas están automatizadas y son de **solo lectura**:

```powershell
$env:G140_RUN_ID_TEST="run-test-YYYYMMDD-HHMMSS"
$env:G140_RUN_ID_LOCAL="run-local-YYYYMMDD-HHMMSS"

python -m pytest test_tc_m09_g140_test.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G140_RUN_ID_TEST/pytest.xml"
python -m pytest test_tc_m09_286_local.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G140_RUN_ID_LOCAL/pytest.xml"
```

- **`test_tc_m09_g140_test.py`** comprueba los 10 puntos de ejecutabilidad contra el contrato de
  TEST (`GET /openapi.json`). No escribe nada en TEST ni usa credenciales. Si VISION no existe,
  deja TC-284 y TC-285 bloqueados **sin** crear áreas gemelas, sin fabricar K/M y sin POST.
- **`test_tc_m09_286_local.py`** comprueba, sobre `src/` y `alembic/`, que el artefacto contiene
  realmente VISION. Si falta cualquier pieza esencial, deja TC-286 bloqueado y **no levanta el
  laboratorio**: no crea base, no migra, no siembra y no toca configuración.

Ambas fallan a propósito mientras VISION no exista: ese fallo **es** la constancia del bloqueo, y
dejan su `evidencia.json` escrito de todos modos.

### Cuidado con los falsos positivos

Buscar "vision" por subcadena da positivos que no acreditan nada, y darlos por buenos llevaría a
montar un laboratorio para una función inexistente:

- **`provisión`** y **`revisión`** contienen "vision". Por eso la compuerta de TEST cuenta la
  palabra como token, no como subcadena.
- **`CAMARA_VISION`** y **`ATRIBUTOS_VISION`** son el tipo de dispositivo cámara y sus atributos
  (resolución, fps, área de cobertura), no una operación de calibración VISION.
- **"línea base de integridad"** y **`integridad_baseline`** son el baseline de **RF-10**, no la
  línea base del Flujo F.

La compuerta local descarta explícitamente esos casos y los registra en la evidencia en lugar de
silenciarlos.

## `oracle_vision.py` — oráculo matemático externo

Contiene **solo** aritmética independiente: no importa nada de `src/` ni contiene código
productivo. Su diseño evita falsear el oráculo en tres puntos:

1. **No elige entre descarte y winsorización.** Calcula las dos lecturas que la matriz admite y
   deja que decida la comparación con la salida real del producto.
2. **No inventa la regla de refinamiento.** `refinar()` exige una `EspecificacionRefinamiento`
   con estimador, actualización del conjunto, medida del cambio relativo, tratamiento del cero,
   criterio de convergencia, ε, `max_iter` y su **fuente formal**. Si falta algo levanta
   `EspecificacionIncompleta`. El código del producto no cuenta como requisito.
3. **No elige método de percentil.** `percentil_robusto()` solo devuelve un valor si es
   invariante entre `lower`, `higher`, `nearest`, `midpoint` y `linear`; si no, levanta
   `PercentilAmbiguo`. Para evitarlo, el dataset debe construirse con una meseta de valores
   iguales en los bordes, con `S = max(N, 100)` o más.

Todo cálculo usa `Decimal`, para comparar la línea base al scale real de la columna `NUMERIC` sin
pasar por `float`.

## Reglas que la automatización hace cumplir

- **TEST decide TC-284 y TC-285; el laboratorio local decide TC-286.**
- **No se escribe en TEST:** nada de SQL de escritura, nada de modificar `apto_para_ia`, fabricar
  vectores, cambiar ε ni `max_iter`. Sobre TEST, solo lectura.
- **No se crean datos para un caso bloqueado**, ni se usan mocks o SQL para convertir un bloqueo
  en ejecutable.
- **Presupuesto:** 3 POST VISION en TEST (K, K+M, dataset) y 2 en LOCAL (baseline previa de setup
  y caso objetivo). Sin reintentos automáticos.
- **STOP_ALL en TEST** si una corrida generase una línea base inesperada o un efecto ambiguo no
  reversible.
- **En LOCAL:** laboratorio desechable propio, sin reutilizar volúmenes de otros grupos, con
  migraciones reales; los datos de entrada pueden sembrarse, pero **el resultado debe producirlo
  el producto**: nunca se inserta a mano la línea base que el algoritmo debe calcular, ni se
  mockea el refinamiento, ni se fabrica la respuesta HTTP. `max_iter` se restaura en `finally`.
- **Las ambigüedades de especificación no se reportan como bug del producto**: se registran con
  `Type = question` e incidencia de producto `NO`, y bloquean únicamente la parte cuyo oráculo
  exacto depende de esa definición.

## Estado actual

VISION no existe ni en el contrato de TEST ni en el artefacto de la rama, de modo que los tres
casos están **BLOQUEADOS / NO VERIFICABLES** y no se ejecutó ningún POST ni se levantó ningún
laboratorio. El detalle está en `RESULTADOS/TC-M09-G140_resultado.md`.

Cuando VISION esté disponible, ambas compuertas pasarán automáticamente y el trabajo pendiente
será construir los datasets y conectar `oracle_vision.py` con la especificación formal del
refinamiento.

## Archivos

```text
TC-M09-G140/
├── README.md
├── oracle_vision.py              oráculo matemático externo (sin código productivo)
├── test_tc_m09_g140_test.py      compuerta de ejecutabilidad en TEST (TC-284 / TC-285)
├── test_tc_m09_286_local.py      compuerta previa al laboratorio local (TC-286)
└── RESULTADOS/
    ├── TC-M09-G140_resultado.md  informe ÚNICO del grupo: cubre los tres casos y ambos RUN
    ├── run-test-.../             evidencia.json · pytest.xml
    └── run-local-.../            evidencia.json · pytest.xml
```

El informe de resultado es **uno solo para todo el grupo**. Los RUN se separan por ambiente
porque las evidencias no deben mezclarse, pero no llevan informe propio: cada carpeta de RUN
guarda su `evidencia.json` y su `pytest.xml`, y la decisión de los tres casos se redacta en
`RESULTADOS/TC-M09-G140_resultado.md`.
