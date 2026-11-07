# TC-M09-G125 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (7/7)

### G125-02 — Ataques al registro
- **Tipo:** Seguridad (OWASP API1/API3/API4/API8) · **Ejecutable:** Sí.
- **Quitado de este grupo:** `activo=false` como mass assignment (es entrada legítima del contrato).
- **Pendiente:** confirmar el estado de INC-M09-21-01 e INC-M09-21-02 antes de reejecutar. El payload `' OR '1'='1` cabe en 50 caracteres y no viola ninguna regla escrita: el 201 es defendible contra la especificación actual (ver decisión 3 del consolidado).

---

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g125.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G125.html`
- Aserciones: 7 total, 0 fallidas (incluye el login)
