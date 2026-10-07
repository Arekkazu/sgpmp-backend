# TC-M09-G71-V2 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA (9/10): Ingeniero recibe 404 DISPOSITIVO_NO_ENCONTRADO (filtro por finca, decisión 1)

### G71-02 — Autorización
- **Tipo:** Seguridad (OWASP A01) · **Ejecutable:** Sí. Admin e Ingeniero autorizados; Productor y Veterinario 403.
- **Pendiente:** escenario 3 (rol correcto sobre dispositivo de otra estructura) depende de la decisión 1 (§9): hoy responde 404 `DISPOSITIVO_NO_ENCONTRADO`.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g71_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G71-V2.html`
- Aserciones: 10 total, 1 fallidas (incluye el login)
- Nota: Ingeniero de prueba: el backend filtra por fincas permitidas; confirmar si el Ingeniero debe tener finca 1 o si 404 es el diseño (decisión 1).
- Fallo: Ingeniero configura -> 202 — expected response to have status code 202 but got 404
