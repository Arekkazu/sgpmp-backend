# Estado del Backend SGPMP (resumen)

> Resumen abreviado de lo implementado en este repositorio. Los módulos con auditoría
> detallada enlazan a su `estado.md`; los demás se describen cualitativamente.

**Stack:** FastAPI · SQLAlchemy 2.0 · PostgreSQL · Pydantic v2 · Python 3.13.
**Arquitectura:** monolito modular + hexagonal + DDD (`Router → UseCase → Port ← Repository`).
**RBAC:** dinámico vía `src/shared/rbac.py` (`require_permission(id_recurso, id_accion)` contra `modulo1.permisos`).

---

## Tabla resumen

| Módulo | Carpeta `src/` | RFs | Estado |
|---|---|---|---|
| M01 Identity & Access | `identity_access` | RF-01..14 | Implementado (auditado) |
| M02 Activos Biológicos | `biological_assets` | RF-33..52 | Implementado (auditado) |
| M03 Telemetría IoT | `telemetry` | RF-53..63 | Implementado |
| M04 Predicción | `prediction` | RF-64..73 | Implementado |
| M05 Suministros | `supplies` | RF-74..81 | Implementado |
| M09 Configuración | `configuration` | RF-15..32 | Implementado (auditado) |

**No implementados** (figuran en `README.md` pero no existen en `src/`): `nic41_valuation`,
`integration`, `business_intelligence`.

---

## M01 — Identity & Access (`identity_access`) · RF-01..14

Base del sistema: registro/activación, login JWT + refresh token (cookie httpOnly),
roles y permisos (CRUD dinámico, no catálogo fijo), gestión de cuentas, contraseñas,
auditoría inmutable con hash SHA-256 y triggers que bloquean UPDATE/DELETE.

**Gaps conocidos:** `ROL_ADMINISTRADOR = 1` hardcodeado
en use cases de edición de perfil y gestión de cuentas (RF-05/06).
CAPTCHA en el registro (RF-01, Google reCAPTCHA v2 vía `siteverify`), refresh tokens, hash de
tokens de un solo uso, RBAC del listado de usuarios y el permiso
especial de identificación completa de RF-12 **ya están resueltos**. RF-12 incorpora además
rate limiting (429) sobre la consulta de fichas, calculado sobre la propia auditoría.

📄 Detalle: [`modulo_1/estado.md`](./modulo_1/estado.md)

---

## M02 — Activos Biológicos (`biological_assets`) · RF-33..52

El más desarrollado (20 RFs con use cases reales y ~25 triggers de BD): registro de activos
individual/poblacional, eventos (crecimiento, sanitario, reproductivo, productivo, bajas),
fases del ciclo, transferencias, sensores IoT, indicadores zootécnicos, ficha integral y bitácora.

**Gaps conocidos:** `PATCH /{id}/estado` permite CERRADO/BAJA saltándose la centralización de
RF-44 (sin cerrar fase ni descontar lote); bitácora RF-52 sin triggers de inmutabilidad a nivel
de BD; violaciones detectadas solo por trigger → HTTP 500 genérico en vez del código del RF;
`modulo_origen` siempre `'modulo2'`.

📄 Detalle: [`modulo_2/estado.md`](./modulo_2/estado.md)

---

## M03 — Telemetría IoT (`telemetry`) · RF-53..63

Runtime de datos en vivo: ingesta de telemetría, recepción de eventos edge, alertas por umbral,
monitoreo/historial, infraestructura IoT (heartbeat/estado de dispositivos), vinculación de
lecturas, calidad de telemetría y bitácora de auditoría IoT.

**Gaps conocidos:** integración MQTT real y motor de inferencia **stubbeados** (los adaptadores
devuelven valores seguros por defecto); dependencias de M09 resueltas vía adaptadores
(`calibracion_m09_adapter`, `dispositivo_m09_adapter`, `umbral_historico_m09_adapter`,
`variable_catalogo_m09_adapter`).

📄 Detalle: [`modulo_3/api_reference_m03_telemetria_iot.md`](./modulo_3/api_reference_m03_telemetria_iot.md)

---

## M04 — Predicción (`prediction`) · RF-64..73

Modelos ML por especie: catálogo de patologías, configuración del motor IA, historial de
diagnóstico, versiones de modelo, despliegues OTA, retroalimentación clínica y auditoría.

**Gaps conocidos:** adaptadores a M09 reales (`especie_m09_adapter`, `variable_i3p1_m09_adapter`)
+ stubs (`modelo_activo_stub_adapter`, `nodo_edge_stub_adapter`) hasta conectar el motor real.

📄 Detalle: [`modulo_4/api_reference_m04_prediccion.md`](./modulo_4/api_reference_m04_prediccion.md)

---

## M05 — Suministros (`supplies`) · RF-74..81

Costos y eficiencia: consumo de alimento, medicamentos, ICA (eficiencia alimenticia),
provisión NIC-41, reportes de gasto, historial de suministros y auditoría, con procesamiento
asíncrono por cola (trabajos batch, reintento y fallos).

**Gaps conocidos:** dependencias de M02 vía adaptadores (`activo_m02_adapter`,
`ciclo_m02_adapter`, `pesaje_m02_adapter`, etc.).

📄 Detalle: [`modulo_5/api_reference_m05_suministros.md`](./modulo_5/api_reference_m05_suministros.md)

---

## M09 — Configuración (`configuration`) · RF-15..32

El más maduro. Catálogo de especies, etapas/patologías/métricas por especie, umbrales
ambientales, parámetros operativos, fincas, infraestructura, dispositivos y sensores IoT,
personalización visual (tema, dashboard, idioma, identidad), plantillas de configuración.

**Gaps conocidos:** reglas gateadas por stubs (`proceso_critico_stub`, `mqtt_stub_adapter` →
ninguna configuración remota llega a `APLICADA`); i18n sin motor de traducción real (RF-29);
`tipos_area` como enum fijo en vez de catálogo administrable (RF-20).

📄 Detalle: [`modulo_9/estado.md`](./modulo_9/estado.md)

---

## Responsabilidades IoT (la separación entre módulos)

El "IoT" aparece en 4 módulos; la división de responsabilidades es:

| Módulo | Rol sobre IoT | Qué cubre |
|---|---|---|
| **M09 Configuración** | *Qué hardware hay y cómo está configurado* | Registro de dispositivos (RF-21, serial único, FK a infraestructura), sensores→áreas (RF-22), configuración remota vía MQTT (RF-23), calibración (RF-24), umbrales ambientales (RF-17) |
| **M03 Telemetría** | *Los datos en vivo* (runtime) | Ingesta de telemetría (RF-53), eventos edge (RF-56), alertas por umbral (RF-57), monitoreo/historial (RF-58/59), heartbeat/estado (RF-60), vinculación de lecturas (RF-61), calidad + auditoría (RF-62/63) |
| **M02 Activos Biológicos** | *El vínculo negocio↔sensor* | Asocia un activo biológico a un sensor IoT (RF-49), con cardinalidad y auto-supersede |
| **M04 Predicción** | *El consumidor* | Nodo edge / motor IA alimentado por la telemetría |

M03 consume el catálogo de M09 vía adaptadores (no toca tablas de M09 directamente).
La integración hardware real (MQTT y motor de inferencia) está **stubbeada** en ambos lados.

---

## Testing

14 archivos de test en `tests/` (módulos `identity_access`, `configuration`, `integration`, `shared`).
Sin suite consolidada para M02/M03/M04/M05 todavía.

---

## Enlaces a documentación detallada

- M01: [`modulo_1/estado.md`](./modulo_1/estado.md)
- M02: [`modulo_2/estado.md`](./modulo_2/estado.md)
- M03: [`modulo_3/api_reference_m03_telemetria_iot.md`](./modulo_3/api_reference_m03_telemetria_iot.md)
- M04: [`modulo_4/api_reference_m04_prediccion.md`](./modulo_4/api_reference_m04_prediccion.md)
- M05: [`modulo_5/api_reference_m05_suministros.md`](./modulo_5/api_reference_m05_suministros.md)
- M09: [`modulo_9/estado.md`](./modulo_9/estado.md)
