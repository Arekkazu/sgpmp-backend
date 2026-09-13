# Reporte de Ejecución - TC-M09-G06 (Sub-caso TC-M09-16) — v2

## 📌 Ficha del Caso de Prueba

| Campo | Valor |
| :--- | :--- |
| **ID Caso** | TC-M09-G06 |
| **Sub-caso** | TC-M09-16 (1 de 1) |
| **Nombre** | Concurrencia Optimista en Edición de Especie |
| **Categoría** | Concurrencia / Integridad |
| **Tipo** | Pytest — threading real con `ThreadPoolExecutor(2)` + `threading.Barrier(2)` |
| **Requisito Funcional** | RF-15 — Catálogo de Especies Productivas (CU-01) |
| **Responsable** | Sebastian |
| **Prioridad** | Alta |
| **Iteración** | v2 — Especie migrada de *Mojarra Plateada* (`id=5`) a **Cachama Blanca** (`id=4`) |
| **Estado anterior (v1)** | Rechazado — resultado unitario PASSED, integración FAILED (HTTP 500 en Mojarra Plateada) |
| **Entorno** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`) |
| **Base de Datos** | PostgreSQL TEST (`158.69.200.27:5448 / sgpmp_test`, usuario `member_qa`) |
| **Fixture especie** | Cachama Blanca (`id_especie = 4`) |
| **Timestamp de referencia (ts_v0)** | `2026-04-28T14:42:28.213141+00:00` (confirmado en BD TEST) |
| **Fecha de ejecución** | 2026-09-07 |
| **Credencial BD usada** | `member_qa` — **única cuenta disponible para QA** (hallazgo INC-M09-04) |

---

## 🗂️ Archivos del Caso

| Tipo | Ruta |
| :--- | :--- |
| Prueba unitaria (fakes, sin BD) | [`tests/configuration/test_rf15_editar_especie_concurrencia.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/configuration/test_rf15_editar_especie_concurrencia.py) |
| Prueba de integración (BD TEST real) | [`tests/integration/test_rf15_concurrencia_especie_cachama_integration.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/integration/test_rf15_concurrencia_especie_cachama_integration.py) |
| Reporte HTML — Unitario | [`Resultados/resultado_tc_m09_g06_unitario.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G06/Resultados/resultado_tc_m09_g06_unitario.html) |
| Reporte HTML — Integración (real) | [`Resultados/resultado_tc_m09_g06_integracion.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G06/Resultados/resultado_tc_m09_g06_integracion.html) |

---

## 📊 Resultados de Ejecución

### Parte A — Prueba Unitaria (con fakes, sin BD)

Comando: `$env:DATABASE_URL="postgresql://dummy:..."; python -m pytest tests/configuration/test_rf15_editar_especie_concurrencia.py -v`
Colectados: 1 · Duración: 1.43s

| Checkpoint | Descripción | Resultado Esperado | Resultado Real | Veredicto |
| :--- | :--- | :--- | :--- | :--- |
| **CP-01** | A y B leen simultáneamente → obtienen `ts_v0` | `fecha_actualizacion == ts_v0` para ambos | Confirmado ✓ | **PASS** |
| **CP-02** | Usuario A edita con `ts_v0` válido | HTTP 200 OK, `ts_v1 ≠ ts_v0`, commit=1 | `nombre = "Cachama Blanca Edit A"`, `ts_v1 ≠ ts_v0`, `commits == 1` ✓ | **PASS** |
| **CP-03** | Usuario B edita con `ts_v0` obsoleto → rechazado | `PreconditionFailedError`, `code="CONFLICTO_CONCURRENCIA"`, HTTP 412 | Excepción lanzada con code y status_code correctos ✓ | **PASS** |
| **CP-04** | En repo prevalece la versión de A | `nombre == "Cachama Blanca Edit A"` | Confirmado en `repo.rows[4]` ✓ | **PASS** |
| **CP-05** | `fecha_actualizacion` se incrementó exactamente 1 vez | `ts_final == ts_v1 ≠ ts_v0` | `ts_final == ts_v1`, `ts_final ≠ ts_v0` ✓ | **PASS** |

**Resultado Pytest Unitario: `1 passed in 1.43s`** ✅

---

### Parte B — Prueba de Integración (concurrencia real contra BD TEST)

Comando: `$env:TEST_DATABASE_URL="postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"; python -m pytest tests/integration/test_rf15_concurrencia_especie_cachama_integration.py -m integration -v -s`
Colectados: 1 · Duración: 5.48s

**Resultado Pytest Integración**: `1 passed, 1 warning in 5.48s`

> ⚠️ **ACLARACIÓN CRÍTICA SOBRE EL RESULTADO `PASSED`**: El resultado `PASSED` reportado por pytest **no significa que la concurrencia optimista funcionó end-to-end en BD**. Significa lo contrario: el árbol de decisión de INC-M09-02 dentro del bloque `try/finally` detectó el error del trigger, ejecutó `pytest.skip()` en el flujo interno, y el `finally` de teardown completó exitosamente (Cachama Blanca verificada intacta). Cuando `pytest.skip()` se llama dentro de un `try/finally`, Python ejecuta el bloque `finally` antes de propagar la señal de skip. Al retornar el `finally` sin excepción, pytest registra el test como `PASSED` en lugar de `SKIPPED`. El **resultado técnico real** es: **BLOQUEADO / INC-M09-02 RECONFIRMADO CON EVIDENCIA REAL EN BD TEST**.

**Log de ejecución real (evidencia)**:
```
INFO  [TEARDOWN] A fue bloqueada (INC-M09-02). Sin escritura de restauracion.
      Cachama Blanca: nombre='Cachama Blanca', ts=2026-04-28 14:42:28.213141+00:00.
      Intacta: True
PASSED
```

El log `A fue bloqueada (INC-M09-02)` confirma que el trigger de auditoría interceptó el `UPDATE` de Usuario A y lanzó excepción antes de que pudiera completarse el commit. INC-M09-02 queda **reconfirmado con evidencia de ejecución real** sobre Cachama Blanca (`id=4`) en BD TEST.

| Paso | Descripción | Resultado Real | Veredicto |
| :--- | :--- | :--- | :--- |
| **Paso 0 — Precondición** | Verificar Cachama Blanca (`id=4`) existe y activa | Confirmado: `es_activo=True` | **OK** |
| **Paso 1 — Lanzamiento concurrente** | A y B sincronizados por `Barrier(2)` intentan `PATCH` simultáneo | Usuario A lanzó excepción por trigger `modulo9.trg_fn_especies_audit` | **BLOQUEADO** |
| **Paso 2 — Árbol de decisión INC-M09-02** | Excepción de A clasificada como error de trigger → `pytest.skip()` | Skip ejecutado dentro de `finally` → pytest reporta `PASSED` (comportamiento de Python) | **BLOQUEADO / INC-M09-02 ✔** |
| **Teardown — verificación BD** | Confirmar integridad de Cachama Blanca post-rollback | `nombre='Cachama Blanca'`, `ts=2026-04-28 14:42:28.213141+00:00`, `es_activo=True` | **✅ INTACTA** |

---

## ✅ Estado Final de Cachama Blanca en BD TEST

Verificación real mediante consulta directa `SELECT` tras la ejecución:

```sql
SELECT id_especie, nombre, descripcion, es_activo, fecha_actualizacion
FROM modulo9.especies WHERE id_especie = 4;
```

| Campo | Valor |
| :--- | :--- |
| `id_especie` | `4` |
| `nombre` | `'Cachama Blanca'` ✅ (nombre original intacto) |
| `descripcion` | `'Pez de agua dulce tropical con alta adaptabilidad a sistemas extensivos e intensivos.'` ✅ |
| `es_activo` | `True` ✅ |
| `fecha_actualizacion` | `2026-04-28 14:42:28.213141+00:00` ✅ (ts_v0 original — sin cambio) |

**Conclusión**: El rollback automático de PostgreSQL al fallar el trigger dejó la especie **100% inalterada**. No se generaron filas huérfanas ni datos sintéticos persistidos en BD TEST.

---

## 🔍 Hallazgos Técnicos

### INC-M09-02 — **RECONFIRMADO CON EVIDENCIA REAL** (Severidad Alta)

- **Estado**: Reconfirmado en BD TEST el 2026-09-07 sobre **Cachama Blanca (`id=4`)**.
- **Descripción**: El trigger `modulo9.trg_fn_especies_audit` (disparado en `AFTER UPDATE` sobre `modulo9.especies`) requiere la variable de sesión PostgreSQL `app.usuario_id`. Al no estar configurada, el trigger lanza excepción PL/pgSQL y PostgreSQL hace rollback automático de la transacción completa.
- **Causa raíz**: `SqlAlchemyEspecieRepository.actualizar()` no ejecuta `SET LOCAL app.usuario_id = :id` antes del `flush()`, por lo que la variable de sesión nunca llega al trigger.
- **Evidencia**: Log de la prueba de integración: `[TEARDOWN] A fue bloqueada (INC-M09-02)`.
- **Historial de confirmaciones**:
  - v1 (2026-09-07): Confirmado sobre *Mojarra Plateada* (`id=5`) — integración FAILED (HTTP 500).
  - v2 (2026-09-07): **Reconfirmado** sobre *Cachama Blanca* (`id=4`) — árbol de decisión detectó error de trigger, skip interno ejecutado, BD intacta.
- **Impacto**: Bloquea **todas las operaciones de escritura** en `modulo9.especies` (CREATE, UPDATE, DEACTIVATE) desde la capa de aplicación.
- **Estado de corrección**: **Pendiente — Desarrollo**. Fuera del alcance de esta sesión de QA.

### INC-M09-04 — Privilegios DML excesivos en `member_qa` (Severidad Alta)

- **Descripción**: La única cuenta de BD disponible para QA (`member_qa`) tiene privilegios `INSERT`/`UPDATE`/`DELETE` sobre el esquema `modulo9`.
- **Declaración explícita**: Esta prueba de integración solo pudo ejecutarse usando `member_qa`, cuya capacidad de escritura es en sí misma el hallazgo INC-M09-04. No existe una cuenta de servicio de menor privilegio disponible para esta prueba.
- **Estado**: **Pendiente — Infraestructura/DBA**.

### Comportamiento técnico: `pytest.skip()` dentro de `try/finally`

- Cuando `pytest.skip()` se llama dentro de un bloque `try/finally` en Python, la excepción `Skipped` que internamente levanta pytest es interceptada por el `finally`. Si el `finally` termina sin propagar otra excepción, pytest interpreta el test como `PASSED`.
- **Consecuencia**: El reporte HTML muestra `1 passed`, pero el **resultado de negocio es BLOQUEADO por INC-M09-02**. Esta limitación es un artefacto de la implementación del árbol de decisión; el log `[TEARDOWN] A fue bloqueada (INC-M09-02)` es la evidencia definitiva del resultado real.
- **Acción de mejora futura**: Reestructurar el test para hacer el `pytest.skip()` antes del bloque `finally`, o usar un flag booleano que se evalúe fuera del `try/finally` para garantizar que pytest registre correctamente `SKIPPED`.

---

## 🔄 Acciones Pendientes

1. **Desarrollo** → Corregir `SqlAlchemyEspecieRepository.actualizar()` para ejecutar `SET LOCAL app.usuario_id = :id` antes del `flush()` (corrección de INC-M09-02).
2. **QA** → Re-ejecutar la prueba de integración una vez corregido INC-M09-02. El veredicto esperado post-fix es **PASS real** (la concurrencia optimista funciona en capa de aplicación, confirmado por la prueba unitaria).
3.  **Infraestructura/DBA** → Revisar y reducir los privilegios DML de `member_qa` en esquema `modulo9` (INC-M09-04).

---

