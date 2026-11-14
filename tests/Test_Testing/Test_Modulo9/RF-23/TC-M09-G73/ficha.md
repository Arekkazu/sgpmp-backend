# TC-M09-G73 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-08, reintento1):** APROBADO (2/2) — atomicidad confirmada: fallo del historial → rollback, 500, cero publicaciones MQTT.

### G73-02 — Atomicidad ante fallo del historial
- **Tipo:** Atomicidad · **Ejecutable:** con inyección de fallo (mocks sobre `config_repo.guardar`) y un spy en el adaptador MQTT que levanta error si se invoca.
- **Esperado:** 500 con rollback y **ningún mensaje en el broker**. **Confirmado: se cumple.**
- Por qué mocks y no un fallo real de BD en TEST: no hay forma de forzar un error de base de datos controlado contra el backend real sin acceso a logs/BD; se usó el mismo patrón ya establecido en el repo (`tests/configuration/test_rf23_alcance_finca.py`, TC-M09-G71) — spies/fakes en vez de SqlAlchemy real, vía `monkeypatch`.

## Reintento1 (2026-10-08)
- Script: `test_tc_m09_g73_atomicidad_historial.py` (pytest, mocks — sin BD/broker real)
- Reporte: `resultados/resultado_TC-M09-G73_reintento1.html`
- 2/2 passed: a nivel use case directo (rollback + 0 llamadas a `mqtt_port.enviar_configuracion`) y a nivel endpoint (`TestClient`, 500 `ERROR_INTERNO` + 0 publicaciones). Confirmado en el código: `config_repo.guardar()`/`db.commit()` ocurren **antes** del envío MQTT en `ConfigurarRemotamenteUseCase.execute()`, así que un fallo ahí nunca alcanza a publicar.
