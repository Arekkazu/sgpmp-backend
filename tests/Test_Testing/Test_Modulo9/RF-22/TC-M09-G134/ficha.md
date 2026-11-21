# TC-M09-G134 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento2):** APROBADO (7/7) — **DESBLOQUEADO**: la cámara se asocia en RF-21, no en RF-22.

### G134-02 — Asociación cámara→área (nuevo)
- **Reencuadre del TC:** `AsociarSensorAreaDTO` sigue sin campo de cámara (reintento1 lo confirmó, 2026-10-09 temprano) — pero resultó ser la pregunta equivocada. El backend desplegó un tipo de dispositivo `CAMARA_VISION` (`id_tipo_dispositivo=5`, catálogo `GET /configuracion/tipos-dispositivo-iot`) con atributos propios (`resolucion`, `fps`, `area_cobertura_m2`) directamente en `RegistrarDispositivoIotDTO` (RF-21). Una cámara **no se asocia a un área vía RF-22**: su `id_infraestructura` de registro YA ES su asociación. Confirmado en vivo: intentar registrar un sensor escalar (RF-22, precursor de `/asociar`) sobre un dispositivo cámara responde `422 CAMARA_SIN_SENSORES` con el mensaje explícito "se asocia directamente al área productiva donde está instalada".
- **Conclusión: no hay nada que corregir ni que agregar a `AsociarSensorAreaDTO`.** El diseño real resolvió esto por otra vía. Cerrar este TC como "aprobado por reencuadre", no reportar como bug.

## Reintento1 (2026-10-09, temprano) — histórico, superado por el reintento2
- Script: `test_tc_m09_g134_sin_campo_camara_reintento1.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G134_reintento1.html`
- 2/2 passed (confirmó la ausencia del campo en `AsociarSensorAreaDTO` — correcto, pero la pregunta estaba mal encuadrada, ver arriba).

## Reintento2 (2026-10-09, TEST, en vivo)
- Colección: `tc_m09_g134_reintento2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G134_reintento2.html`
- 7/7 passed: cámara registrada con `id_infraestructura` queda inmediatamente "asociada" (GET lo confirma); intento de registrar sensor escalar sobre la cámara correctamente rechazado con `CAMARA_SIN_SENSORES`.

---
