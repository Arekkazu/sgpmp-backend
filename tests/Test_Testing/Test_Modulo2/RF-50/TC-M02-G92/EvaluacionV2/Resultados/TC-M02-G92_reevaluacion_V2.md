# REEVALUACIÓN V2 — TC-M02-G92

**Proyecto:** SGPMP / SIGAB · **Módulo:** M02 · **RF:** RF-50 (datos consolidados) y RF-51 (indicadores) · **CU:** CU12
**Subcasos:** TC-M02-154 (RF-50) · TC-M02-159 (RF-51)
**Responsable QA:** Juan Esteban · **Ambiente:** TEST · **Fecha:** 2026-09-20
**Incidente asociado:** INC-M02-90-G92 / #241 — identidad técnica M04

---

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| Caso | TC-M02-G92 |
| RF / CU | RF-50 y RF-51 / CU12 |
| Subcasos | TC-M02-154 · TC-M02-159 |
| Estado V1 | ⛔ **BLOQUEADO** (TC-M02-154 y TC-M02-159 no ejecutados) |
| Estado V2 | ⛔ **SIGUE BLOQUEADO** |
| Ejecución funcional V2 | **NINGUNA**: no se ejecutó Newman, Postman, Pytest ni k6, y no se emitió ningún GET oficial |
| TC-M02-154 | ⛔ **BLOQUEADO / NO EJECUTADO** |
| TC-M02-159 | ⛔ **BLOQUEADO / NO EJECUTADO** |
| Motivo del bloqueo | **CONFIGURACIÓN / PROVISIÓN DE IDENTIDAD M04 EN TEST** |
| Naturaleza del bloqueo | No es falta de desarrollo funcional · No es falta de datos · No es un defecto de RF-50/RF-51 |
| Responsable de desbloqueo | DBA / administrador de TEST (provisión y credencial); Desarrollo / responsable funcional (alcance por finca) |
| **Veredicto** | ⛔ **BLOQUEADO** |

La prueba **no exige que el Módulo M04 esté desarrollado**. RF-50 y RF-51 se pueden ejercitar simulando al módulo consumidor con una **identidad técnica autorizada**, tal como decidió Desarrollo en INC-M02-90-G92. Lo que falta es que esa identidad exista y quede bien configurada en la base de datos de TEST.

---

## 1. Motivo de la reevaluación

V1 cerró en BLOQUEADO con dos motivos: la identidad M04 no estaba disponible para QA y la restricción de "cero escrituras" de entonces impedía invocar unos endpoints que registran sesión y auditoría.

En V2 se revisa si esos motivos siguen vigentes:

| Motivo del bloqueo V1 | Estado en V2 |
|---|---|
| Identidad M04 no disponible para QA en TEST | **SIGUE BLOQUEADO** — la provisión no está aplicada en TEST (§2) |
| Restricción QA de cero escrituras | **RESUELTO POR CRITERIO QA ACTUALIZADO** — la metodología V2 separa las escrituras técnicas de sesión y auditoría de la persistencia de dominio, que es la que debe quedar con Δ 0. Ya no impide ejecutar, pero no llegó a ejercitarse |

Esta tarea es **exclusivamente documental**: registrar por qué el caso sigue bloqueado hoy y qué hace falta para desbloquearlo. No se ejecutan los subcasos.

---

## 2. Verificación del bloqueo actual

Consulta de solo lectura a PostgreSQL TEST el **2026-09-20 22:20 UTC**, con `SET default_transaction_read_only = on` (`member_qa` / `sgpmp_test` / `transaction_read_only = on`). No se consultaron contraseñas, hashes, tokens ni secretos.

| Verificación | Resultado |
|---|---|
| Usuario `integracion.m04.test@pecuaria.co` | **0 filas** — no existe |
| Usuarios con correo `%m04%` o `%integracion%` | **0 filas** |
| Rol `Integración M04` (búsqueda por nombre: `%integr%`, `%m04%`) | **0 filas** — no existe |
| Roles existentes en TEST | 30 roles, con ids entre 1 y 77; ninguno es la identidad técnica |
| `modulo1.credenciales_servicio` (sin leer `hash_valor`) | Solo `1 · broker_mqtt · activo`, igual que en V1 |
| Credencial de M04 disponible para QA | **No** |

### 2.1 Clasificación del bloqueo

| Tipo de bloqueo | ¿Aplica? | Sustento |
|---|---|---|
| Falta de desarrollo funcional | **NO** | RF-50 y RF-51 están implementados y desplegados; la propia V1 verificó ambos contratos. INC-M02-90-G92 decidió no construir ningún mecanismo nuevo de autenticación y reutilizar el RBAC existente |
| **Falta de configuración / provisión en TEST** | **SÍ** | El rol, el usuario y la cuenta de la identidad técnica no están creados en la base de TEST. La propia nota de Desarrollo deja el bloque SQL como *"Pendiente — no aplicable desde este entorno"* y pide ejecutarlo contra la base de TEST |
| Falta de datos | **NO** | El fixture del caso está completo (§2.2) |
| Falta de credenciales | **SÍ, derivada** | Aunque se cree el usuario, QA necesita recibir la contraseña vigente por canal seguro |
| Dependencia de otro módulo (M04 desarrollado) | **NO** | La prueba puede ejecutarse simulando al consumidor con la identidad técnica autorizada; no requiere la aplicación M04 |

### 2.2 El fixture no bloquea: los datos están disponibles

| Activo | Identificador | Tipo | Estado | Infraestructura | Finca | Propietario de la finca |
|---:|---|---|---|---:|---:|---:|
| 295 | `QAJE-DAT-COMPL` | INDIVIDUAL | ACTIVO | 48 | 57 | usuario 35 |

Mediciones de peso de TC-M02-159, verificadas hoy:

| Evento | Fecha (UTC) | Valor | Unidad |
|---:|---|---:|---|
| 224 | 2026-07-15 10:00:00+00 | 200.00 | kg |
| 225 | 2026-08-15 10:00:00+00 | 230.00 | kg |

Las dos mediciones están en fechas distintas, dentro del ciclo. Valor esperado calculado por QA, listo para contrastar cuando se ejecute: `(230 − 200) / 31 = 0.967741935…` kg/día, que con la cuantización de la implementación (4 decimales) da **0.9677 kg/dia**; variables esperadas `peso_inicial_kg = 200`, `peso_final_kg = 230`, `dias = 31`, `total_mediciones = 2`. **No se contrastó con la API**: no hubo ejecución.

### 2.3 Alcance por finca: parte de la configuración pendiente

Crear el usuario y darle READ sobre `activos_biologicos` **no basta**. Los endpoints de RF-50 y RF-51 restringen los activos por alcance de finca (`_ids_fincas_alcance` → `src/shared/alcance_finca_adapter.py`):

- el alcance es global solo si el rol tiene permiso de **actualizar (3)** o **desactivar (4)** sobre el recurso **`fincas` (9)**. Hoy en TEST únicamente el rol 1 (Administrador) cumple esa condición;
- en cualquier otro caso, el alcance se reduce a `SELECT id_finca FROM modulo9.fincas WHERE id_usuario = :id_usuario`, es decir, las fincas cuyo propietario es el propio usuario.

El activo 295 pertenece a la finca 57, cuyo propietario es el usuario 35. Con el rol documentado en INC-M02-90-G92 (solo el permiso (29, 2)), la identidad técnica **no tendría alcance sobre ese activo**. Desarrollo indicó que este alcance debe resolverse mediante los permisos de la base de datos, así que forma parte de la provisión de TEST y no de un cambio de código.

Esta conclusión proviene de la lectura del código en el HEAD actual: **no se comprobó en ejecución**, porque la identidad no existe.

### 2.4 Escrituras técnicas: no son un bloqueo

El login actualiza `ultimo_acceso` y los endpoints registran auditoría (`DATOS_ANALITICOS_CONSULTADOS`, `INDICADOR_CALCULADO`). En la metodología V2 esas escrituras técnicas se separan de la persistencia de dominio, que es la que debe quedar con Δ 0, así que **no impiden ejecutar el caso** y no se consideran motivo de bloqueo.

---

## 3. Por qué no se ejecutan TC-M02-154 y TC-M02-159

**TC-M02-154 — BLOQUEADO / NO EJECUTADO.**
**TC-M02-159 — BLOQUEADO / NO EJECUTADO.**

Motivo en ambos casos: **la identidad técnica M04 aún no está completamente provisionada y disponible para QA en TEST.** Sin ella no hay token con el que invocar `GET /activos-biologicos/295/datos-consolidados` ni `GET /activos-biologicos/295/indicadores`.

Además, QA no sustituye la identidad técnica:

- no se usó ninguna cuenta humana (Productor, Administrador, Veterinario, Ingeniero) como sustituto de M04: mediría el acceso de un usuario del negocio, no el del módulo consumidor;
- no se creó ni se provisionó la identidad: es una escritura en TEST y no corresponde a QA;
- no se construyó la colección V2 ni se generaron reportes: sin token no podrían ejecutarse y producirían un artefacto sin validar.

Ningún subcaso se marca como aprobado ni rechazado en esta V2, porque no se ejecutó ninguno.

---

## 4. Qué se necesita para desbloquear

1. **DBA / administrador de TEST — provisionar la identidad técnica:**
   - rol `Integración M04`, **localizado o creado por nombre**, usando el `id_rol` real que asigne TEST. No debe asumirse el `id_rol = 12` de DEV: en TEST ese id corresponde a otro rol;
   - usuario `integracion.m04.test@pecuaria.co`;
   - cuenta **activa y verificada** (`modulo1.cuentas_usuarios`; sin esa fila el login falla);
   - permiso mínimo **READ**: `id_recurso = 29` (`activos_biologicos`), `id_accion = 2`;
   - la configuración necesaria para que la identidad tenga **alcance sobre la finca/activo de la prueba** (finca 57 / activo 295), resuelta por permisos de base de datos según indicó Desarrollo.
2. **Administrador — asignar o rotar una contraseña segura** para esa cuenta.
3. **Entrega de la credencial a QA por canal seguro.** No se escribe en Git, ni en este Markdown, ni en la colección Postman, ni en scripts. QA la usará solo mediante `--env-var`.
4. **QA — gate previo a ejecutar**, verificando en este orden:
   - existencia del usuario;
   - rol correcto;
   - cuenta activa y verificada;
   - permiso (29, 2);
   - alcance sobre la finca/activo de la prueba;
   - login exitoso;
   - acceso válido al activo de prueba (GET base).
5. **Solo después de superar ese gate** se construye o actualiza la colección V2 y se ejecutan TC-M02-154 y TC-M02-159.

---

## 5. Evolución V1 → V2

| Elemento | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-154 | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **SIGUE BLOQUEADO** |
| TC-M02-159 | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **SIGUE BLOQUEADO** |
| Identidad M04 | No disponible para QA | Definida en INC-M02-90-G92 y aplicada en DEV; **no provisionada en TEST**; alcance de finca pendiente de resolver | **SIGUE BLOQUEADO — provisión y configuración en TEST** |
| Datos del fixture (activo 295, 2 pesos) | Disponibles | Disponibles y verificados hoy | Sin cambio: **no es causa de bloqueo** |
| Restricción de cero escrituras | Impedía ejecutar los GET | Las escrituras técnicas se separan del dominio | **BLOQUEO RESUELTO POR CRITERIO QA ACTUALIZADO** |
| Veredicto del caso | BLOQUEADO | BLOQUEADO | **SIGUE BLOQUEADO**, con un motivo menos |

---

## 6. Veredicto final

# ⛔ BLOQUEADO

**Evolución: BLOQUEADO (V1) → SIGUE BLOQUEADO (V2).**

**Motivo actual: CONFIGURACIÓN / PROVISIÓN DE IDENTIDAD M04 EN TEST**, incluida la credencial y el alcance sobre la finca/activo de la prueba.

No se atribuye a:

- falta de desarrollo completo del Módulo M04 — la prueba puede ejecutarse con una identidad técnica autorizada;
- falta de datos — el fixture de G92 está completo, con las dos mediciones de peso en fechas distintas;
- un defecto funcional de RF-50 o RF-51 — no se ha demostrado ninguno, porque no hubo ejecución.

---

## 7. Integridad

- ✅ **V1 intacta:** no se modificaron `test_tc_m02_g92.json` ni `Resultados/` (informe y reportes de V1).
- ✅ **Ninguna prueba ejecutada:** sin Newman, sin Postman, sin Pytest, sin k6 y sin ningún GET oficial a la API.
- ✅ **Ninguna escritura de dominio:** solo `SELECT` en sesión `transaction_read_only = on`. Sin INSERT, UPDATE, DELETE ni scripts de provisión. No se creó rol, usuario, cuenta ni permiso, y no se modificó el alcance de fincas.
- ✅ **Ningún cambio de código** del producto.
- ✅ **Sin commit, push, merge, rebase ni deploy**, y sin cambio de rama (`qa/juan-esteban-re-evaluacion-m02`, HEAD `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`).
- ✅ No se usó ninguna cuenta humana como sustituto de M04 y no se leyeron contraseñas ni secretos.
- ✅ **Único artefacto nuevo:** este documento (`EvaluacionV2/Resultados/TC-M02-G92_reevalucion_V2.md`).
