# RF-24 — Validación de rango de calibración por tipo de sensor + modelo ganancia/offset

**Rama:** `feature/rf24-validacion-rango-calibracion-mod9`
**Issue:** #1635 · Módulo 9 (`src/configuration/`) · basado en `origin/dev`

## Problema

RF-24 estaba al ~65%: había CRUD y trazabilidad de calibración, pero el único chequeo de
valor era `valor_referencia > 0`, así que un offset absurdo pero positivo (ej. temperatura
500 °C, pH −5) pasaba. Además `modulo9.calibraciones` solo guardaba `valor_referencia`, lo
que obligaba al consumidor de telemetry a aproximar `ganancia=1.0, offset=valor_referencia`.

Se confirmó que **no corresponde al broker MQTT** (`BROKER-MQTT-SGPMP`): ese repo no tiene
concepto de calibración, ni actor Ingeniero de campo, ni endpoint de registro; solo reenvía
`valor_crudo` a un stored proc. RF-24 es un caso de uso REST del backend.

## Qué se hizo

### Base de datos (migración Alembic `c3f1a9e42b7d`, down_revision `b1c4a7e9d2f3`)
- Nueva tabla catálogo `modulo9.rangos_calibracion` (`categoria` UNIQUE, `valor_min`,
  `valor_max`, CHECK `valor_max >= valor_min`), sembrada con los 7 valores del enum de
  `categoria` del sensor (TEMPERATURA, OXIGENO, PH, AMONIACO, SALINIDAD, HUMEDAD, LUMINOSIDAD).
- Columnas `ganancia NUMERIC(10,4) NOT NULL DEFAULT 1.0` y
  `offset_calibracion NUMERIC(10,4) NOT NULL DEFAULT 0` en `modulo9.calibraciones`, con
  backfill `offset_calibracion = valor_referencia`.
- Aplicada a `sgpmp` (dev). `pruebas` es solo-`modulo1` y los tests de M09 hacen `pytest.skip`
  cuando falta el schema → no requiere la migración.
- `offset_calibracion` (no `offset`) porque `OFFSET` es palabra reservada de SQL.

### Código (patrón RF-23 #1632)
- **Modelo ORM:** `models/rango_calibracion_model.py`; columnas nuevas en `calibracion_model.py`.
- **Dominio:** entidad `RangoCalibracion` con `verificar(valor)`; `Calibracion` gana
  `ganancia`/`offset` (offset default = valor_referencia).
- **DTO:** `registrar_calibracion_dto.py` agrega `ganancia` (validator > 0) y `offset`
  opcionales; se quitó el validator duro `valor_referencia <= 0` (lo reemplaza el rango).
- **Puerto + repo:** `RangoCalibracionRepository` + impl SQLAlchemy (solo lectura);
  `calibracion_repository.py` mapea las columnas nuevas.
- **Use case:** `registrar_calibracion_use_case.py` inyecta `rango_repo`, valida
  `valor_referencia` y `offset` contra el rango de la `categoria` → `400 VALOR_FUERA_DE_RANGO`;
  fallback a `> 0` si la categoría no tiene rango configurado.
- **Schema + router:** `CalibracionResponse` expone `ganancia`/`offset`; nuevo
  `GET /configuracion/sensores/rangos-calibracion` (recurso 12, acción 2).
- **Consumidor telemetry:** `calibracion_m09_adapter.py` lee `ganancia`/`offset_calibracion`
  reales — ya no aproxima.

### RBAC
Sin cambios: se reutiliza el recurso 12 (`sensores`), acción C(1) para calibrar y R(2) para
el catálogo. No se insertaron filas nuevas en `modulo1.permisos`. Verificado en DB: solo
Administrador e Ingeniero de Campo tienen C sobre recurso 12 (Productor/Contador → 403).

### Segunda pasada — flujos alternos RF-24 restantes

Tras revisar la implementación contra el texto completo del RF-24, se cerraron dos flujos
alternos que faltaban:

- **Auditoría inmutable RF-10 + rollback → 500.** Nueva tabla `modulo9.auditorias_calibraciones`
  (migración Alembic `d4e2f8a15c9b`), inmutable por trigger (`trg_auditorias_calibraciones_inmutable`
  bloquea UPDATE/DELETE, patrón de `auditorias_especies`). El use case escribe la traza dentro
  de la transacción vía `AuditoriaCalibracionRepository` y `Calibracion._snapshot()`; si falla →
  `InfrastructureError` → rollback → `500 AUDITORIA_CALIBRACION_FALLIDA`. Sigue el patrón del
  flujo hermano `asociar_sensor_area_use_case`.
- **Formato no numérico → 400 (antes 422).** El DTO acepta `valor_referencia` permisivo
  (`Decimal | str | None`) para no dispararse el 422 de Pydantic; el use case convierte y
  devuelve `400 VALOR_CALIBRACION_INVALIDO` ante valor no numérico, vacío o nulo.

Verificación adicional: `tests/test_registrar_calibracion_use_case.py` (fakes en memoria) cubre
happy-path escribe auditoría, fallo de auditoría→500+rollback, no numérico/vacío/nulo→400 y
fuera de rango→400. Inmutabilidad del trigger comprobada contra la BD.

## Verificación
- Test de dominio: `tests/test_rango_calibracion.py` (`RangoCalibracion.verificar`) — pasa.
- End-to-end contra `sgpmp` (con rollback, sin persistir): in-range persiste con
  `ganancia`/`offset`; el adaptador de telemetry devuelve valores reales; `valor_referencia`
  fuera de rango (500 °C) → `400 VALOR_FUERA_DE_RANGO`; `offset` fuera de rango también se
  rechaza; modelo de dos parámetros (ganancia=2.0, offset=10) se almacena.
- `import main` OK.

## Fuera de alcance (no es gap abierto)
- CRUD de escritura para `rangos_calibracion`: se administra por SQL (perilla de calibración),
  igual que el catálogo de RF-23.
- Los rangos sembrados son ilustrativos; el estándar de calibración real se tunea por SQL.
