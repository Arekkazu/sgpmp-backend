# TC-M09-G131-V2 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA parcial (2/2)

### G131-02 — Precedencia del orden de validación (nuevo)
- **Estado:** **Parcial.** Los escenarios que no dependen de cámara sí se pueden ejecutar: serial duplicado + área inactiva → 409; formato inválido + tipo inexistente → 400.
- **Bloqueado:** tipo inexistente + atributos de cámara faltantes. Depende de la decisión de §8.3 (orden de validación).
- **Observado por separado** (no combinado): tipo inexistente → 422; serial de 51 caracteres → 400. La combinación que decide el orden (tipo inexistente + atributos de cámara faltantes) **no se ha probado** porque CAMARA no está implementado. Pendiente de decisión y de implementación.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g131_v2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G131-V2.html`
- Aserciones: 2 total, 0 fallidas (incluye el login)
