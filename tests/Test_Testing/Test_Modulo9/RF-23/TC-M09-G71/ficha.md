# TC-M09-G71 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-10, reintento1):** APROBADO (8/10, 2 fallos no relacionados al bug) — **CORREGIDO**: el Ingeniero ya configura dispositivos de su propia finca.

### G71-02 — Autorización
- **Tipo:** Seguridad (OWASP A01) · **Ejecutable:** Sí. Admin e Ingeniero autorizados; Productor y Veterinario 403.
- **Decisión 1 resuelta:** el filtro por finca SÍ es el diseño correcto (BOLA), y ya funciona en ambos sentidos: dispositivo en finca propia del Ingeniero (finca 1) → **202**; dispositivo en finca ajena (probado con una finca QA cualquiera) → **404** `DISPOSITIVO_NO_ENCONTRADO` (anti-enumeración, correcto). Mismo fix que ya estaba confirmado en DEV desde 2026-09-22 (commit `bb97a10b`), ahora también llegó a TEST.

## Ejecución automatizada (2026-10-06, TEST) — histórico, superado por el reintento1
- Colección: `tc_m09_g71.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G71.html`
- Aserciones: 10 total, 1 fallidas (incluye el login)
- Fallo (en ese momento): Ingeniero configura -> 202 — respondía 404 (ya corregido)

## Reintento1 (2026-10-10, TEST, misma colección sin cambios)
- Reporte: `resultados/resultado_TC-M09-G71_reintento1.html`
- 8/10: Administrador configura → 202 ✓; **Ingeniero configura → 202 ✓ (el fix que buscábamos)**; Veterinario → 403 ✓. Los 2 fallos son de la cuenta Productor (`m2m.nuevo@ejemplo.com`), que ya **no inicia sesión** (401 `CREDENCIALES_INVALIDAS`) — credencial de prueba vencida/cambiada en algún reset de TEST, **no un bug de este TC**. No se reintentó el login para no arriesgar el bloqueo por intentos fallidos (iba en intento 2 de 5). Pendiente: conseguir una credencial vigente de Productor para volver a cubrir ese sub-caso.
