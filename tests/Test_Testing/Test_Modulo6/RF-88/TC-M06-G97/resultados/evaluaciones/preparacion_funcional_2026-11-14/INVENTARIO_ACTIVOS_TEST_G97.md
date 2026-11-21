# Inventario de activos TEST — TC-M06-G97

**Fecha:** 2026-11-14  
**Commit local:** `3995b923`  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Auth:** Contador QA (`QA_CORREO` / `QA_CONTRASENA`) — único POST: `/sesiones/`  
**Evidencia cruda:** `evidencia_inventario_readonly.json`, `candidatos_recalculados.json`

---

## Verificación de workspace

| Ítem | Resultado |
|---|---|
| Rama | `laura` |
| HEAD | `3995b923` |
| `consultar_depreciacion_use_case.py` | Presente |
| `vida_util_meses or 1` | Ausente |
| WIP G112/G117/G118/G119 | Intactos (6 M / 28 D + untracked previos) |

---

## Activos al costo verificados (GET)

Se listaron activos vía `GET /finanzas/activos` y se confirmó `valorado_por_costo=true`. Detalle y depreciación con GET.

| ID | Identificador | Costo | Vida (meses) | Fecha adquisición (API) | Dep. registrada | Notas |
|---|---|---|---|---|---|---|
| 1858 | QA-RF88-AL-COSTO | 1.700.000 | 60 | 2026-11-12 | 0 | **Candidato principal 09** (nombre RF-88) |
| 1635 | QA-M06-COSTO-02 | 2.500.000 | 60 | 2026-11-10 | 0 | Candidato 09 limpio |
| 1639 | QA-M06-SEED-COSTO-01 | 1.800.000 | 60 | 2026-11-10 | 0 | Candidato 09 |
| 1643 | Lote 1643 | 500.000 | 120 | 2026-11-10 | 0 | Candidato 09 |
| 951 | QA-M06-COSTO-01 | 4.500.000 | 240 | 2026-11-07 | 0 | Candidato 09 |
| 2126 | QA-M06-DEP-COSTO-10M | 10.000.000 | 100 | 2026-10-12 | 0 | Cercano a narrativa 12M (no exacto) |
| 1567 | QA-M06C-COSTO-01 | 4.500.000 | 120 | 2026-08-01 | 112.500 | Ya tiene depreciación registrada |
| 1573 | QA-M06O-COSTO-02 | 4.000.000 | 120 | 2026-08-01* | 0 | *fecha API vía consulta |
| 1629 | BOV-116-TIL | 3.500.000 | 120 | 2026-10-01* | 0 | |

\* Preferir siempre `fecha_adquisicion` del GET depreciación; no usar solo la fecha de reconocimiento de la lista.

### Búsqueda del escenario canónico 12.000.000 / 72 meses

**No encontrado** en el inventario autenticado. Ningún activo tiene costo `12000000` con vida `72`.

---

## Especies (GET `/finanzas/configuracion`)

- Especies con `vida_util_meses` configurada: **9** (p. ej. Bovino 120, Equino 240, Bufalo Depreciacion Qa 100, Especie Qa Mseis Costo 60).
- Especies sin vida útil: **313** (la mayoría no necesariamente aptas para reconocimiento al costo).

---

## Registro histórico sin vida útil

Entre los **9** activos al costo inspeccionados, **todos** tienen `vida_util_meses` en la valoración.  
**No** se identificó fixture histórico sin vida útil utilizable para TC-M06-08 camino B.

---

## Propuesta con bloqueo de vida útil (lectura)

| ID | Identificador | Especie | Bloqueos GET |
|---|---|---|---|
| 1864 | QA-RF82-BLOQUEADO | Caprino Sin Contable Qa Rf (`id_especie` 595) | `CLASIFICACION_NO_CONFIGURADA` **y** `VIDA_UTIL_NO_CONFIGURADA`; `es_confirmable=false` |

El POST de reconocimiento devolvería 422 con el **primer** bloqueo (`CLASIFICACION_NO_CONFIGURADA`), no necesariamente `VIDA_UTIL_NO_CONFIGURADA`. Ver `PREPARACION_TC_M06_08.md`.
