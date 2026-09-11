# RF-10 — Auditoría de cumplimiento al pie de la letra

Fecha: 2026-08-28 · Rama: `feature/rf10-retencion-auditoria-12-meses`
Método: lectura de código + consultas al esquema real de `sgpmp` + sonda de
integración ejecutada contra `pruebas` con `TestClient`.

> **Estado: los 8 incumplimientos de esta auditoría están cerrados.**
> Este documento se conserva como registro de qué se encontró y por qué.
> El cómo se resolvió cada uno está en [`RESUMEN_FINAL.md`](./RESUMEN_FINAL.md),
> y cada punto tiene una prueba en
> `tests/integration/test_rf10_conformidad_integration.py`.

**Veredicto al momento de la auditoría: ⚠️ Cumple parcialmente (~70%).**

---

## 1. Lo que SÍ cumple

| Exigencia del RF | Evidencia |
|---|---|
| Registra los 11 eventos auditables listados | 25 tipos en `modulo1.tipos_eventos`; los 11 del RF están cubiertos |
| Registra intentos fallidos | `resultado = fallido`; 38 `LOGIN_FALLIDO` en dev |
| Inmutabilidad a nivel de BD | `trg_proteger_auditoria_update` / `_delete` bloquean incluso a `postgres` |
| Hash SHA-256 al crear el registro | `SqlAlchemyEventoRepository.registrar` |
| Hash recalculado en cada consulta | `_verificar_hash` → campo `integridad_ok` |
| Solo administradores consultan | `require_permission(6, 2)`; sólo `id_rol=1` tiene el permiso |
| Consulta con filtros usuario / tipo / fecha | `GET /auditoria/` |
| Paginación obligatoria | `tamano` acotado a 50 por `Query(..., le=50)` |
| Retención mínima de 12 meses + archivado automático | tarea diaria 04:00 UTC → `modulo1.eventos_archivados` |
| Histórico consultable | `GET /auditoria/archivado/` |
| FA rango de fechas inconsistente → 400 | `RANGO_FECHAS_INVALIDO` |
| FA fallo del archivado → alerta interna al administrador | evento tipo 25 + notificación canal 2 |
| Blocker: si falla la auditoría, la acción principal se revierte | patrón `try / registrar / commit / except: rollback; raise` |

---

## 2. Incumplimientos

### A. Faltan campos obligatorios de la sección "Entradas"

El RF define once campos. Tres no existen como columna y dos están casi siempre
vacíos. Además el criterio de aceptación exige explícitamente *"El sistema
almacena IP y sesión"*.

Columnas reales de `modulo1.eventos`: `id_evento`, `tipo_evento`, `descripcion`,
`fecha_evento`, `modulo`, `resultado`, `detalle`, `id_usuario`, `categoria`,
`estado`, `id_sesion`, `hash_integridad`.

| Campo del RF | Estado | Cobertura real (de 936 eventos) |
|---|---|---|
| `nombre_usuario varchar(80)` | ❌ no existe | 0 |
| `direccion_ip varchar(45)` | ❌ no existe como columna; va suelto en `detalle` JSONB | 194 (21%) |
| `user_agent varchar(255)` | ❌ no existe como columna; va suelto en `detalle` JSONB | 224 (24%) |
| `id_sesion` | ⚠️ columna existe, casi nunca se llena | 146 (16%) |
| `descripcion` | ⚠️ columna existe, `registrar()` nunca la escribe | 81 (9%, legado) |

Sólo 4 de los 29 call-sites de `registrar()` pasan `id_sesion`. IP y user_agent
sólo llegan en login, refresh, registro, activación y recuperación; **no** en
cambio de contraseña, modificación de perfil, cambio de estado de cuenta, roles,
permisos ni consultas de auditoría.

Ninguno de los tres campos se expone en `AuditoriaItemResponse`, así que aunque
estuvieran poblados el administrador no los vería.

### B. FA "Fallo de integridad del registro" no responde 500

El RF exige HTTP 500 con el mensaje *"Alerta de seguridad: Se ha detectado una
violación de integridad en el registro de auditoría [ID_EVENTO]..."*.

Sonda con un evento de hash corrupto:

```
HASH_MISMATCH status: 200
HASH_MISMATCH body: [(568, False)]
```

Devuelve 200 con `integridad_ok: false`. Detecta la manipulación pero no la
escala como incidente de seguridad.

### C. FA "Acceso denegado" no registra el intento y usa otro mensaje

El RF exige mensaje propio y que *"registra este mismo intento fallido en la
auditoría"*. Sonda con un veterinario:

```
403 status: 403
403 body: {'error_code': 'ACCESO_DENEGADO',
           'message': 'Acceso denegado. Su rol no tiene permisos para realizar esta operación.'}
403 evento auditado? 0 -> 0
```

Causa: `require_permission` es dependencia de ruta y se ejecuta **antes** del use
case. Como sólo `id_rol=1` tiene el permiso `(6,2)`, cualquier otro rol se
detiene ahí, con el mensaje genérico de RBAC y sin auditar nada.

El bloque de `ConsultarAuditoriaUseCase` que sí registra el intento denegado
(`if usuario_actual.id_rol != ROL_ADMINISTRADOR`) es **código muerto**: nunca se
alcanza porque RBAC ya cortó.

### D. FA "Intento de modificación o eliminación" usa el 405 por defecto

El RF exige el mensaje *"Operación no permitida: Los registros de auditoría son
inmutables por diseño..."*. Sonda:

```
PUT status: 405 body: {'detail': 'Method Not Allowed'}
PATCH status: 405 body: {'detail': 'Method Not Allowed'}
DELETE status: 405 body: {'detail': 'Method Not Allowed'}
```

El código es correcto, pero el cuerpo es el de FastAPI y ni siquiera sigue el
formato de error del proyecto (`error_code` / `message` / `fields` / `timestamp`).

### E. FA "Exceso de resultados" nunca responde 206

El RF exige HTTP 206 Partial Content con *"Consulta extensa: Se muestran los
primeros 50 resultados..."* cuando la consulta excedería 10.000 registros.
Hoy siempre responde 200: la paginación se fuerza por validación de `Query`, sin
señalizar la truncación.

### F. FA "Filtro de búsqueda inválido" ignora el `id_usuario` inexistente

El RF exige 400 tanto por rango de fechas inconsistente **como** por
*"un id_usuario inexistente en los filtros"*. Sólo lo primero está implementado:

```
ID_INEXISTENTE status: 200 body: {'total': 0, 'pagina': 1, 'tamano': 20, 'items': []}
```

### G. FA "Blocker" no emite el mensaje exigido

El comportamiento sí es correcto — si falla el registro de auditoría, la acción
principal se revierte. Pero la excepción original se propaga cruda; no se produce
*"Fallo crítico de seguridad: No se pudo generar el registro de auditoría
obligatorio. La operación [ACCION_SOLICITADA] ha sido cancelada..."*.

### H. RNF de rendimiento y escalabilidad sin respaldo

`modulo1.eventos` tiene **un solo índice: la clave primaria**.

```sql
CREATE UNIQUE INDEX eventos_pkey ON modulo1.eventos USING btree (id_evento)
```

Los filtros del endpoint (`id_usuario`, `tipo_evento`, `fecha_evento`) y el
`ORDER BY fecha_evento DESC` van a *sequential scan*. Con 936 filas no se nota,
pero los RNF piden *"consulta < 3 segundos"* y *"soporte para alto volumen de
logs"*. Irónicamente la tabla histórica **sí** tiene dos índices; la tabla activa
no.

---

## 3. Observación adicional (no está en el RF, pero lo contradice)

`_verificar_hash` devuelve `True` cuando `hash_integridad IS NULL`:

```python
def _verificar_hash(self, evento):
    if evento.hash_integridad is None:
        return True
```

Un registro sin hash se reporta como íntegro. Como la Restricción del RF declara
el hash **obligatorio**, borrar el hash es hoy una vía para que un registro
manipulado pase la verificación. En dev hay **21 eventos sin hash** (legado
anterior al mecanismo), que además son inmutables y no se pueden rellenar.

---

## 4. Cambios de base de datos que exigiría el cierre

| # | Cambio | Motivo |
|---|---|---|
| 1 | `ALTER TABLE modulo1.eventos ADD COLUMN nombre_usuario varchar(80)` | Entrada del RF |
| 2 | `ALTER TABLE modulo1.eventos ADD COLUMN direccion_ip varchar(45)` | Entrada del RF + criterio de aceptación |
| 3 | `ALTER TABLE modulo1.eventos ADD COLUMN user_agent varchar(255)` | Entrada del RF + criterio de aceptación |
| 4 | Mismas 3 columnas en `modulo1.eventos_archivados` | El histórico replica el esquema |
| 5 | Índices en `(fecha_evento DESC)`, `(id_usuario, fecha_evento DESC)`, `(tipo_evento)` | RNF de rendimiento y escalabilidad |

Las tres columnas deben ser **nullable**: los 936 eventos existentes son
inmutables y no se pueden rellenar retroactivamente. Los eventos nuevos sí las
llenarían siempre.

Los triggers de inmutabilidad **no bloquean `ALTER TABLE`** (son `BEFORE UPDATE
OR DELETE FOR EACH ROW`), así que añadir columnas es seguro.

Nota: `hash_integridad` cubre `tipo_evento`, `fecha_evento`, `id_usuario`,
`resultado`, `modulo` y `detalle`. Si los campos nuevos deben quedar protegidos
por el hash hay que incluirlos en el cálculo, y eso hace que **todos los eventos
anteriores queden con hash no verificable**. Recomendación: dejar el cálculo del
hash como está y guardar los campos nuevos también dentro de `detalle`, que ya
entra en el hash.

---

## 5. Estado real por criterio de aceptación

| Criterio | Estado |
|---|---|
| Registra TODOS los eventos definidos | ✅ |
| Cada registro contiene TODOS los campos obligatorios | ❌ faltan 3 columnas, 2 casi vacías |
| El sistema registra intentos fallidos | ⚠️ salvo el acceso denegado a auditoría (gap C) |
| El sistema almacena IP y sesión | ❌ IP 21%, sesión 16% |
| No permite modificación de registros | ✅ |
| Permite consulta con filtros funcionales | ✅ |
| La paginación funciona correctamente | ✅ (sin el 206 del FA) |
| Los registros se mantienen según política de retención | ✅ |
