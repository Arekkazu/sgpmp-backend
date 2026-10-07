# TC-M09-G136-V2 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO — Bloqueado: `ConfigurarRemotamenteDTO` no tiene `fps` y RF-23 v1.1 no define el código para frecuencia en CAMARA (§8.2).

### G136-02 — Parámetros por categoría / fps (nuevo)
- **Estado: BLOQUEADO.** `ConfigurarRemotamenteDTO` no tiene `fps`, y RF-23 v1.1 no define qué código devuelve enviar `frecuencia_captura` a una CAMARA (§8.2). Bloqueo heredado de G134-02 (las precondiciones exigen asociación a área).
