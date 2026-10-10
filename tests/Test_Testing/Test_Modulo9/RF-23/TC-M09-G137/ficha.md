# TC-M09-G137 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento2):** APROBADO (11/11) — **DESBLOQUEADO**, sin hallazgos de seguridad.

### G137-02 — Ataques a la superficie de cámara (nuevo)
- **Desbloqueado** porque sus dos precondiciones (G134, G136) se resolvieron el mismo día. Fuzzing real de `resolucion`/`fps`/`area_cobertura_m2` en registro (RF-21) y configuración remota (RF-23): payloads tipo SQLi/XSS en `resolucion`, formato inválido, `area_cobertura_m2` negativa, `fps` decimal/no-numérico. **Resultado: todos los casos maliciosos/inválidos rechazados correctamente (400, nunca 500, sin reflejo inseguro). No se encontraron vulnerabilidades.**

## Reintento1 (2026-10-09, temprano) — histórico, superado por el reintento2
- Script: `test_tc_m09_g137_dependencias_bloqueadas_reintento1.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G137_reintento1.html`
- 3/3 passed (confirmó correctamente que, en ese momento, ambas precondiciones seguían bloqueadas).

## Reintento2 (2026-10-09, TEST, en vivo)
- Colección: `tc_m09_g137_reintento2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G137_reintento2.html`
- 11/11 passed (6 casos de ataque rechazados + 1 control que confirma que datos válidos sí se aceptan).

---
