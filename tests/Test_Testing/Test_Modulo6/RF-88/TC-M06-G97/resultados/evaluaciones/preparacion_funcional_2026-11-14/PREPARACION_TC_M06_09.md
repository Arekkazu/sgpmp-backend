# Preparación TC-M06-09 — Depreciación lineal consultable

**Estado:** listo para ejecución funcional de lectura con activo **real** (no el canónico 12M/72).  
**Endpoint:** `GET /finanzas/activos/{id}/depreciacion?fecha=AAAA-MM-DD`  
**Permiso:** `valoracion_por_costo` R (Contador QA verificado).

---

## Escenario canónico ficha (12.000.000 / 72)

| Esperado ficha | Estado en TEST |
|---|---|
| Costo 12.000.000 · vida 72 · anual 2.000.000 · acum 2.000.000 · VC 10.000.000 | **Sin activo verificado** |

No se inventan IDs. Se sustituye por activo real coherente con la misma fórmula.

---

## Candidato principal recomendado: ID **1858** (`QA-RF88-AL-COSTO`)

Datos verificados (GET depreciación):

| Campo | Valor |
|---|---|
| `id_activo_biologico` | **1858** |
| Costo depreciable | **1.700.000** |
| Vida útil | **60** meses |
| Fecha adquisición | **2026-11-12** |
| Depreciación registrada (baseline) | **0** |
| Fecha consulta (+12 meses dominio) | **2027-11-12** |

### Solicitud preparada

```http
GET /finanzas/activos/1858/depreciacion?fecha=2027-11-12
Authorization: Bearer <token_contador>
X-Zona-Horaria: America/Bogota
```

### Aserciones esperadas (dominio + coherente con API en sonda readonly)

| Campo | Esperado |
|---|---|
| HTTP | 200 |
| `meses_transcurridos` | 12 |
| `depreciacion_anual` | 340000.0000 |
| `depreciacion_acumulada` | 340000.0000 |
| `valor_contable` | 1360000.0000 |
| `depreciacion_registrada` | 0.0000 |
| `vida_util_meses` | 60 |
| `costo_adquisicion` | 1700000.0000 |
| Side-effect | `GET /finanzas/activos/1858` → `depreciacion_acumulada` registrada sin cambio |

Fórmula: `anual = q4(costo × 12 / vida)`; acum = `valor_por_costo(..., meses=12)`.

---

## Alternativas verificadas (también coherentes a +12 meses)

| ID | Costo | Vida | Fecha consulta | Anual | Acum | Valor contable | Reg. |
|---|---|---|---|---|---|---|---|
| 1635 | 2.500.000 | 60 | 2027-11-10 | 500.000 | 500.000 | 2.000.000 | 0 |
| 1639 | 1.800.000 | 60 | 2027-11-10 | 360.000 | 360.000 | 1.440.000 | 0 |
| 1643 | 500.000 | 120 | 2027-11-10 | 50.000 | 50.000 | 450.000 | 0 |
| 951 | 4.500.000 | 240 | 2027-11-07 | 225.000 | 225.000 | 3.975.000 | 0 |
| 2126 | 10.000.000 | 100 | 2027-10-12 | 1.200.000 | 1.200.000 | 8.800.000 | 0 |
| 1567 | 4.500.000 | 120 | 2027-08-01 | 450.000 | 450.000 | 4.050.000 | **112.500** |

`1567` sirve para asertar `depreciacion_registrada == 112500` (ya hubo cierres).

---

## Precondiciones pendientes TC-M06-09

| Ítem | Estado |
|---|---|
| Endpoint en TEST | Verificado (200 autenticado) |
| Activo 12M/72 | **No disponible** — usar 1858 u otro de la tabla |
| Auth Contador | Disponible (`QA_*`) |
| Ejecución formal AC + evidencias oficiales | **Pendiente** (esta fase solo preparó) |

**Dictamen 09:** **LISTO para ejecución funcional** con activo 1858 (u alternativa documentada). No APROBADO aún.
