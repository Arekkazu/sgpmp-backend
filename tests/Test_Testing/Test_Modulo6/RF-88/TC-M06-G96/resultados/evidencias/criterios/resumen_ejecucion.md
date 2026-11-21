# Resumen ejecución A+B — TC-M06-G96

## Dictamen final

**A. VALIDACIÓN A+B COMPLETADA**

Cálculos, límite a cero, generación y persistencia consultable de `VALOR_LIBROS_AJUSTADO_A_CERO` comprobados en entorno **Docker PostgreSQL temporal exclusivo**.

**No se declara G96 APROBADO end-to-end** en API TEST compartido.

Estado documental del grupo: evidencia aislada completa; pendiente solo E2E HTTP si el criterio de aceptación del proyecto lo exige.

---

## Resultados por subcaso

| Subcaso | Resultado | Capa |
|---|---|---|
| TC-M06-05 | **PASS** (libros 7.000.000) | A |
| TC-M06-06 | **PASS** (libros 0) | A |
| TC-M06-07 cálculo/piso | **PASS** (−2.000.000 → 0) | A + B |
| Alerta `VALOR_LIBROS_AJUSTADO_A_CERO` | **PASS** (generada y consultable) | B |
| TEST compartido modificado | **No** | — |

## Código y entorno

- Worktree: `sgpmp-backend-g96-ab` @ `91f79e75` (incluye `8829599f`)
- `laura`: intacta
- BD: `g96_ab_test` @ `127.0.0.1:55496` · contenedor `g96-ab-postgres-tmp`
- Migración `c6e8a0b2d453`: aplicada en BD temporal · enum presente
- Pytest B: 3/3 PASS · Pytest A: 3/3 PASS

## Limitaciones

1. Persistencia demostrada en BD temporal (con rollback de fixtures), **no** en el esquema del API TEST compartido.  
2. Harness Windows (`fcntl` stub + `__init__.py` de `tests`) solo en worktree.  
3. No se ejercitó HTTP Contador contra `api.inmero.co`.

## Artefactos

- `diagnostico_integral_G96.md`
- `matriz_criterios_G96.md`
- `resultado_dominio.json` / `resultado_integracion.json`
- `evidencia_alerta.json`
- `pytest_dominio_report.html` / `pytest_integracion_report.html`
- logs y JUnit XML asociados
