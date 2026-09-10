# TC-M02-G77 — Resultado de ejecución

**Estado general: 3/4 sub-casos con veredicto (2 PASS, 1 FAIL confirmado); 1 sub-caso no reproducible en vivo sin
riesgo (gap confirmado por código). 13/14 assertions PASS** vía Postman/Newman contra el backend TEST desplegado,
usando datos reales ya existentes.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G77 (TC-M02-127, 128, 129, 130) |
| RF / CU | RF-47 / CU-10B |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Activos usados | 5 (individual, datos completos) · 10 (individual, sin sanitarios, BAJA+fase activa) · 8 (lote, CERRADO+fase activa) |
| Fecha de ejecución | 2026-09-10, ~02:1X UTC |

## TC-M02-127 — Consultar ficha integral completa

**FAIL — falta la Sección 8 (accesos directos).**

```json
// GET /activos-biologicos/5/ficha-integral → HTTP 200
{
  "identificador":"BOV-0852","tipo":"INDIVIDUAL","especie":"Tilapia Roja","estado_actual":"ACTIVO",
  "fase_productiva_activa":"Ciclo completo tilapia 2025-A","infraestructura_asociada":"Estanque-01",
  "raza":"Brahman","peso_actual":"2.60","eventos_sanitarios":[...], "eventos_crecimiento":[...5 items...],
  "indicadores":[], "advertencias":[]
  // sin ningun campo "accesos_directos"
}
```

Confirmadas presentes: identificación, estado/fase, ubicación, datos biológicos, eventos recientes (sección 5),
indicadores (sección 6, como campo aunque vacío para este activo). **Ausente: Sección 8 (accesos directos)** — no
existe como campo en la respuesta, ni en la entidad `FichaIntegral` ni en el schema. El RF exige explícitamente 8
secciones (7 en LOTE); solo hay 7 implementadas en total, sin importar el tipo de activo.

## TC-M02-128 — Sección sin datos

**PASS a nivel de contrato de API.**

```json
// GET /activos-biologicos/10/ficha-integral → HTTP 200
{"eventos_sanitarios": [], "identificador": "BOV-006", "tipo": "INDIVIDUAL", ...}
```

`eventos_sanitarios` es un arreglo vacío, sin error ni omisión de la sección — el resto de la ficha se cargó con
normalidad (identificador, tipo, estado, etc.). El texto exacto "Sin información registrada" es responsabilidad
del frontend al renderizar un arreglo vacío; no se verificó visualmente en esta ejecución (ver README, sección
"herramienta").

## TC-M02-129 — Fallo parcial de un módulo fuente

**No reproducido en vivo — confirmado por código que el gap existe.**

Se consultaron 4 activos distintos (incluyendo el activo 8, con indicadores realmente poblados) sin lograr que
`vw_rf47_indicadores_zootecnicos_activo` fallara — no hay forma de forzar esa falla sin modificar temporalmente un
objeto de base de datos compartido por todo el equipo de TEST, algo que se decidió no hacer.

`consultar_ficha_integral_use_case.py`, método `_indicadores()` (y los 4 métodos `_ultimos_*` hermanos):

```python
def _indicadores(self, id_activo: int) -> list[dict]:
    rows = self.db.execute(text('SELECT ... FROM modulo2.vw_rf47_indicadores_zootecnicos_activo ...')).fetchall()
    return [...]
```

Ningún `try/except` individual por sección — si esta consulta lanzara una excepción, se propagaría sin control
hacia arriba (no hay ningún bloque que la capture antes del `return ficha` en `execute()`), muy probablemente
tumbando la ficha completa con un 500 en vez del "Información no disponible. [Actualizar]" localizado que exige
este sub-caso. Gap ya documentado en `anotaciones/modulo_2/estado.md` (RF-47); esta revisión confirma que el
código actual sigue sin el manejo granular necesario.

## TC-M02-130 — Advertencia de inconsistencia sin bloquear la ficha

**PASS completo.**

```json
// GET /activos-biologicos/8/ficha-integral → HTTP 200
{
  "estado_actual": "CERRADO", "fase_productiva_activa": "Ciclo completo mojarra 2025-A",
  "indicadores": [{"tipo":"ganancia_peso", ...}],
  "advertencias": ["Se detectó una inconsistencia: el activo está en estado CERRADO pero aún tiene una fase productiva activa (Ciclo completo mojarra 2025-A). Verifique el estado o la fase del activo."]
}
```

La ficha se muestra completa (200, todas las demás secciones presentes, incluyendo indicadores poblados para este
activo en particular) con la advertencia visible — comportamiento exactamente como exige el RF, y ya
correctamente implementado.

## Resumen de assertions (Newman, 13/14 PASS)

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login (200) | PASS |
| 2–4 | TC-M02-127: ficha 200, secciones 1-4/7 presentes, sección 5 presente, sección 6 presente | PASS |
| 5 | **TC-M02-127: existe Sección 8 (accesos_directos)** | **FAIL — no existe el campo** |
| 6–8 | TC-M02-128: ficha 200, eventos_sanitarios vacío, resto normal | PASS |
| 9–12 | TC-M02-130: ficha 200, estado+fase inconsistentes, advertencia presente, resto de secciones normal | PASS |

## Evidencia

- [Colección Postman](../TC-M02-G77.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G77.html) · [JSON](newman-TC-M02-G77.json)

## Conclusión

RF-47 tiene una base sólida (7 de 8 secciones funcionando correctamente, incluyendo la detección de inconsistencia
estado/fase, que es una de las piezas más finas del RF). El gap real y accionable es la Sección 8 (accesos
directos), ausente por completo — ya documentado previamente, ahora confirmado en vivo. El manejo de fallo parcial
por sección (TC-M02-129) también sigue siendo un gap real por lectura de código, aunque no se pudo forzar una
reproducción en vivo sin arriesgar el entorno compartido.
