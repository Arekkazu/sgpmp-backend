# TC-M09-G133 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-10, reintento1):** BLOQUEADO — no se puede re-verificar: `POST /dispositivos-iot/{id}/sensores` responde 500 incondicional, no se puede crear el sensor que este TC necesita.

### G133-02 — Precedencia del orden de validación (nuevo)
- **Estado:** Ejecutable para el orden declarado (dispositivo → sensor → área → área activa → asociación previa → duplicado).
- **Abierto:** dónde entra la validación de `punto_instalacion` (decisión 6).

## Ejecución automatizada (2026-10-06, TEST) — histórico
- Colección: `tc_m09_g133.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G133.html`
- Aserciones: 8 total, 2 fallidas (incluye el login)
- Nota: El backend valida primero la pareja sensor-dispositivo: un dispositivo inexistente produce 422 en vez de 404 (orden de la matriz: dispositivo → sensor → área).
- Fallo: Dispositivo y area inexistentes con sensor valido -> 404 DISPOSITIVO_NO_ENCONTRADO — expected response to have status code 404 but got 422

## Reintento1 (2026-10-10, TEST) — BLOQUEADO, no ejecutable
Este TC necesita un sensor real (`id_sensor` válido) para ejecutar cualquiera de sus sub-casos del orden de validación. `POST /configuracion/dispositivos-iot/{id}/sensores` responde `500 ERROR_INTERNO` de forma incondicional en TEST — confirmado en 3 dispositivos distintos, 2 infraestructuras distintas (277 y 271), con `categoria` y sin ella. No es un problema de datos de prueba: es un bug nuevo de backend que bloquea este TC y a TC-M09-G62 por igual. **Reportar como bug nuevo antes de poder re-verificar el orden de validación que pide este TC.**
