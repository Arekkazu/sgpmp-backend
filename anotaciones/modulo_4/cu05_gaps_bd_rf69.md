# CU-05 — Gaps de BD y RBAC — RF-69

Fecha de análisis: 2026-07-12

---

## 1. Gaps de BD encontrados

### Tabla `modulo4.versiones_modelos`

**Gap 1 — `id_usuario` NOT NULL incompatible con registro automático de RF-71**

El flujo de las Fases 1-3 del RF-69 es completamente automático: RF-71 invoca el endpoint interno sin que exista un actor humano. La columna `id_usuario NOT NULL` impedía insertar versiones sin usuario.

Decisión: hacer la columna nullable. En registros automáticos, el actor se identifica mediante `id_proceso_rf71` y el tipo de actor `SISTEMA` en `historial_estados_modelos`.

```sql
ALTER TABLE modulo4.versiones_modelos ALTER COLUMN id_usuario DROP NOT NULL;
```

**Gap 2 — `algoritmo` NOT NULL sin campo equivalente en el contrato de RF-71**

El contrato de integración documentado en `m04_responsabilidades_equipos.md` (Frontera 1 → RF-71 → RF-69) no incluye `algoritmo` como campo enviado por RF-71. La restricción NOT NULL impedía el registro.

Decisión: hacer la columna nullable. Si RF-71 envía el algoritmo en una versión futura del contrato, se puede rellenar sin cambio de esquema.

```sql
ALTER TABLE modulo4.versiones_modelos ALTER COLUMN algoritmo DROP NOT NULL;
```

**Gap 3 — Columna `fecha_registro` ausente**

La sección de Salida del RF-69 exige `timestamp_registro (Timestamp)` como campo de la versión persistida. La tabla no tenía esta columna; solo existía `fecha_entrenamiento` (cuando RF-71 entrenó el modelo) y `fecha_despliegue` (cuando se activó), pero no el momento en que el backend recibió y registró la versión.

```sql
ALTER TABLE modulo4.versiones_modelos
    ADD COLUMN IF NOT EXISTS fecha_registro TIMESTAMPTZ NOT NULL DEFAULT now();
```

---

## 2. Gaps de RBAC

**Sin gaps.** `id_recurso = 43` (`version_modelo`) ya tenía los permisos correctos al momento del análisis:

| id_permiso | nombre | id_rol | id_accion |
|-----------|--------|--------|-----------|
| 253 | admin_leer_version_modelo | 1 (Admin) | 2 (R) |
| 254 | admin_actualizar_version_modelo | 1 (Admin) | 3 (U) |
| 255 | admin_ejecutar_version_modelo | 1 (Admin) | 5 (E) |
| 256 | vet_leer_version_modelo | 3 (Vet) | 2 (R) |
| 257 | vet_actualizar_version_modelo | 3 (Vet) | 3 (U) |
| 258 | vet_ejecutar_version_modelo | 3 (Vet) | 5 (E) |

No se creó permiso C(1) porque el registro de versiones es exclusivamente interno (RF-71 invoca el endpoint sin usuario humano; no pasa por RBAC).

---

## 3. Decisiones de diseño

| Decisión | Justificación |
|----------|---------------|
| Endpoint interno autenticado por `X-RF71-Internal-Key` | No pasa por RBAC; la clave compartida con IoT/IA previene registros de origen externo (FA-02) |
| `nombre_version` generado automáticamente como `{tipo_modelo}_{fecha_entrenamiento:%Y%m%d}_{id_proceso_rf71[:8]}` | UNIQUE constraint ya existe en la tabla; nombre descriptivo y reproducible |
| Magic bytes para validar formato (no solo extensión) | Extensión puede ser falsificada; protobuf header de ONNX y SavedModel.pb son verificables sin dependencias externas |
| Artefacto almacenado en `MODELOS_STORAGE_PATH` del entorno | El backend no gestiona almacenamiento en nube; ubicación configurable por infraestructura |
| `id_usuario NULL` en versiones auto-registradas | Actor identificado vía `id_proceso_rf71` + `tipo_actor = SISTEMA` en historial |
| Activación requiere `notas_validacion` no vacío | CA-13 del RF-69; el Veterinario debe registrar su evaluación clínica antes de activar |
| Activación atómica usando un único `commit()` | Garantiza que nunca coexistan dos versiones ACTIVO del mismo tipo (CA-7) |
| Auditoría VERSION_ACTIVADA + VERSION_DEPRECADA con mismo `correlacion_id` | Permite trazar el par de eventos como una operación única en RF-73 |
