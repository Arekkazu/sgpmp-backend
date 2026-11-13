# TC-M06-G96 — Análisis de alternativa segura de ejecución

**Estado del grupo:** `PREPARADO_CON_RIESGOS` (sin cambio)  
**Alcance de esta actividad:** inspección y preparación únicamente  
**Escritura en TEST compartido:** ninguna  
**Commit / push / cambio de producción:** ninguno  

---

## 1. Veredicto

**Alternativa más segura y viable:** ejecución en **dos capas locales/aisladas**, sin HTTP de escritura contra `api.inmero.co/api-sgpmp-test` y sin tocar activo 2126 / valoración 66 / reconocimiento 886 / periodo 411:

| Capa | Qué demuestra | Aislamiento |
|---|---|---|
| **A — Dominio (pytest, sin BD)** | Cálculo real RF-88 y piso en cero para 05 / 06 / 07 | Proceso local; cero impacto en TEST |
| **B — Integración (PostgreSQL de pruebas + rollback)** | Casos de uso reales (deterioro / cierre) + **persistencia consultable** de `VALOR_LIBROS_AJUSTADO_A_CERO` | `TEST_DATABASE_URL` con nombre `*test*` o `pruebas*`; transacción exterior revertida (`tests/integration/conftest.py`) |

**No sustituye** una corrida funcional autorizada en el API TEST compartido para cerrar el grupo como APROBADO end-to-end. Sí permite demostrar los criterios de **cálculo**, **ajuste a cero** y **generación + consulta de alerta en persistencia aislada**, sin DBA de tres activos adicionales y sin contaminar el seed compartido.

**Condición técnica previa:** el árbol de código usado para las capas A/B debe incluir el fix `#968` (`8829599f`). Ese commit está en `origin/test` / `origin/dev`, pero **no** en el HEAD local de `laura`. Ejecutar sobre `laura` actual **no** ejercita la alerta.

---

## 2. Componentes reales del backend que se pueden probar

### 2.1 Cálculo y piso en cero (capa A)

| Componente | Ubicación (con #968) | Rol |
|---|---|---|
| `valor_por_costo(...)` | `src/financial_valuation/domain/services/nic41.py` | Depreciación por vida útil/meses + `max(0, costo − dep − det)` |
| `valor_libros_calculado(...)` | mismo archivo (**añadido en #968**) | Resultado matemático **antes** del piso (puede ser negativo) |
| `ValorPorCosto` | mismo archivo | DTO de dominio (costo, dep, det, valor_contable) |

Firma real de `valor_por_costo`: `(costo_adquisicion, vida_util_meses, meses, deterioro_acumulado)`. **No** recibe depreciación acumulada como monto; la calcula.

Ruta real del deterioro (#968): tras sumar impacto llama `valor_libros_calculado` y aplica `max(CERO, calculado)` — esa es la lógica a invocar para montos absolutos 2M/7M/10M + deterioro, **sin reimplementar la fórmula en el test**.

### 2.2 Alerta persistente (capa B)

| Componente | Ubicación | Rol |
|---|---|---|
| `RegistrarDeterioroUseCase` | `.../valoracion_costo/registrar_deterioro_use_case.py` | Ajusta libros; si `calculado < 0` audita alerta y avisa Contador |
| `evento_valor_libros_cero(...)` | mismo módulo | Construye `EventoAuditoria` tipo `VALOR_LIBROS_AJUSTADO_A_CERO` |
| `_depreciar` en cierre | `.../cierre/ejecutar_cierre_periodo_use_case.py` | Puede emitir la misma alerta con `origen=DEPRECIACION` |
| `ConsultarAuditoriaFinancieraUseCase` | `.../auditoria/consultar_auditoria_financiera_use_case.py` | Incluye el tipo en el catálogo consultable |
| Migración | `alembic/versions/c6e8a0b2d453_rf88_alerta_valor_libros_cero.py` | Registra el tipo de evento en BD |

Payload esperado (del diseño #968 / prueba de integración):

- `origen`: `DETERIORO` | `DEPRECIACION`
- `valor_calculado`, `valor_aplicado` (`0.0000`)
- `costo_adquisicion`, `depreciacion_acumulada`, `deterioro_acumulado`
- severidad `WARNING`; consultable por `id_activo_biologico`

### 2.3 Lo que **no** existe

- Endpoint o método de “simulación / dry-run” de deterioro sin persistir.
- POST de monto de depreciación acumulada.
- Mecanismo HTTP de validación previa que ejerza el ajuste a cero sin escritura.

Por tanto, la “simulación controlada” viable es **invocar el dominio/casos de uso en pytest**, no un flag de API.

---

## 3. Pruebas y mecanismos ya existentes

| Artefacto | Qué cubre | Limitación |
|---|---|---|
| `tests/Test_Testing/.../TC-M06-G96/test_tc_m06_g96_valor_en_libros.py` | Invoca **`valor_por_costo` real** con vida/meses que producen dep 2M / 10M / 7M | Sin BD/HTTP; el test de alerta está escrito para **fallar a propósito** (documenta ausencia de alerta en el DTO) |
| `tests/financial_valuation/test_m06_nucleo_nic41.py` → `test_valor_por_costo_no_baja_de_cero` | Piso en cero con otros montos | No son los montos G96 |
| `tests/integration/test_inc_m06_281_g68_valor_libros_cero.py` (**en `origin/test`**, ausente en `laura` local) | **TC-M06-07 completo** vía `m06.registrar_deterioro()` + consulta auditoría + notificación; también cobertura de cierre y de no-alerta si no hay negativo | Requiere `TEST_DATABASE_URL` aislada; **no** es el API TEST compartido |

Hallazgo clave: Desarrollo **ya** dejó una prueba de integración alineada a TC-M06-07 (#968). No hace falta inventar un mock de fórmula; hay que **ejecutarla** (cuando se autorice) sobre código con #968 y BD de pruebas.

---

## 4. Cómo ejecutar los tres escenarios (propuesta, no ejecutada)

### 4.1 Capa A — dominio (05 / 06 / 07 de cálculo)

Usar siempre imports de `nic41` (lógica real). Dos formas válidas:

**Forma 1 — montos absolutos (alineada al deterioro real #968):**

```text
calculado = valor_libros_calculado(costo, depreciacion, deterioro)
aplicado  = max(Decimal("0"), calculado)   # misma regla que el caso de uso
```

| Subcaso | Entrada | `calculado` | `aplicado` |
|---|---|---|---|
| 05 | 10M, 2M, 1M | 7.000.000 | 7.000.000 |
| 06 | 10M, 10M, 0 | 0 | 0 |
| 07 | 10M, 7M, 5M | **−2.000.000** | **0** |

**Forma 2 — `valor_por_costo` (ya en el test G96 actual):** elegir `vida_util_meses`/`meses` para que la dep calculada coincida (10/2, 12/12, 10/7). Sigue siendo lógica real; no sustituye `valor_libros_calculado` para demostrar el valor negativo **antes** del piso en 07.

Archivo propuesto (evolución del existente, sin tocar producción):

- `tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G96/test_tc_m06_g96_valor_en_libros.py`  
  — ajustar 07 para afirmar `valor_libros_calculado == -2000000` y `valor_contable == 0`, **sin** fingir que el DTO emite la alerta.

### 4.2 Capa B — integración aislada (persistencia de alerta + 05/07 vía caso de uso)

Patrón ya usado en `test_inc_m06_281_g68_valor_libros_cero.py`:

1. Fixture `db_session` abre transacción exterior; los `commit()` del caso de uso son savepoints.
2. Seed local: finca, activo, reconocimiento a costo, (opcional) `UPDATE` de `depreciacion_acumulada` en la valoración **creada en la prueba**.
3. Evento sanitario insertado solo en esa sesión.
4. `m06.registrar_deterioro().execute(...)` — código de producción del use case.
5. `m06.consultar_auditoria().execute({..., "tipo_evento": ["VALOR_LIBROS_AJUSTADO_A_CERO"]}, ...)`.
6. Al terminar la prueba: **rollback** → no queda rastro en la BD de pruebas.

| Subcaso | Procedimiento de integración propuesto |
|---|---|
| **05** | Seed dep=2.000.000, libros=8.000.000 → deterioro 1.000.000 → assert `valor_contable=7.000.000` y `total_registros` alerta = 0 |
| **06** | Seed dep=10.000.000, det=0, libros=0 **o** cierre controlado que agote el costo → assert libros 0; documentar si aparece o no alerta por origen `DEPRECIACION` |
| **07** | Reutilizar / ejecutar `test_valor_en_libros_negativo_queda_en_cero_con_alerta_persistente` (ya escrito) |

Archivos:

- Existente en `origin/test`: `tests/integration/test_inc_m06_281_g68_valor_libros_cero.py` (07 + negativos de control).
- Propuesto QA (nuevo, solo tras autorización de escritura de **tests**):  
  `tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G96/test_tc_m06_g96_integracion_aislada.py`  
  o ampliar el de integración con casos 05/06 etiquetados G96.

### 4.3 Qué no hacer en esta alternativa

- No POST/PUT/PATCH/DELETE al API TEST compartido.
- No cerrar periodo 411.
- No UPDATE al activo 2126 / valoración 66.
- No reescribir la fórmula en el assert (`assert 10_000_000 - 2_000_000 - 1_000_000 == 7_000_000` como “prueba del sistema”).
- No declarar “alerta persistida en TEST” tras un pytest de integración.

---

## 5. Cómo verificar la alerta

### En capa B (válido y demostrable)

1. Tras `registrar_deterioro` con cálculo negativo:  
   `consultar_auditoria` filtrando `VALOR_LIBROS_AJUSTADO_A_CERO` + `id_activo_biologico`.
2. Asserts mínimos (ya en #968):
   - descripción / tipo correctos  
   - `severidad == WARNING`  
   - `resumen_payload.valor_calculado == "-2000000.0000"`  
   - `resumen_payload.valor_aplicado == "0.0000"`  
   - distinto de solo `DETERIORO_REGISTRADO`  
   - (opcional) notificador `ALERTA_FINANCIERA_NIC41` con el mismo `valor_calculado`
3. Evidencia: salida pytest + JSON/HTML de resultados bajo  
   `TC-M06-G96/resultados/alternativa_segura/` (a generar en corrida autorizada).

### En capa A

Solo se demuestra que el dominio produce `calculado < 0` y `aplicado == 0`.  
**No** demuestra alerta.

### En API TEST compartido (fuera de esta alternativa)

```text
GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO&id_activo_biologico={id}&formato=TECNICO
```

Requiere escritura previa autorizada; **no** forma parte de la alternativa segura.

---

## 6. Aislamiento necesario

| Requisito | Detalle |
|---|---|
| Código | Checkout / worktree basado en `origin/test` (o commit que contenga `8829599f`) para capas A/B con alerta |
| BD | `TEST_DATABASE_URL` → PostgreSQL cuyo nombre contenga `test` o sea `pruebas` / `pruebas-integrador` (validación en `conftest`) |
| Transacción | Usar fixture `db_session` de integración (rollback al final) |
| Datos | Activos/fincas **creados en la prueba**; prohibido referenciar 2126/66/886/411 |
| Secretos | No volcar contraseñas/tokens en evidencias |
| Red | No apuntar el cliente HTTP de integración al host compartido de TEST para escrituras |

Si no hay BD de pruebas disponible, **solo** la capa A es ejecutable; la persistencia de alerta queda pendiente.

---

## 7. Criterios de aceptación: qué sí / qué no se demuestra

| Criterio | Capa A dominio | Capa B integración aislada | API TEST compartido (no en esta alternativa) |
|---|---|---|---|
| 05 → libros 7.000.000 | **Sí** | **Sí** (vía use case) | Pendiente autorización |
| 06 → libros 0 (solo dep) | **Sí** | **Sí** (seed o cierre en BD prueba) | Pendiente |
| 07 → libros 0 pese a −2.000.000 | **Sí** | **Sí** | Pendiente |
| 07 → alerta `VALOR_LIBROS_AJUSTADO_A_CERO` generada | No | **Sí** | Pendiente |
| 07 → alerta consultable tras commit del caso de uso | No | **Sí** (en BD de pruebas, luego rollback) | Pendiente |
| 07 → alerta visible en API TEST / seed 2126 | No | **No** (y no debe afirmarse) | Solo con ejecución funcional autorizada |
| Permisos Contador / OpenAPI en TEST | No (salvo GET ya hechos en prep) | Parcial (stack local) | Lectura ya documentada en prep |
| No contaminar seed compartido | N/A | **Sí**, si se respeta el aislamiento | Riesgo si se escribe |

---

## 8. Limitaciones que quedan pendientes

1. **Cierre formal del grupo G96 como APROBADO en TEST HTTP** sigue requiriendo autorización + datos (o aceptación explícita de evidencia de integración como suficiente para el dictamen del caso).  
2. Rama local `laura` **sin** #968: cualquier corrida sobre ese HEAD es **incompleta** para la alerta.  
3. El test G96 actual `test_tc_m06_07_la_alerta_especifica_no_se_produce` documenta un fallo intencional; debe reemplazarse/separarse al adoptar la capa B, no usarse como veredicto de negocio.  
4. Integración prueba **persistencia en BD de pruebas**, no en el esquema productivo de TEST ni en el API público.  
5. TC-M06-06 vía cierre en integración puede emitir alerta por depreciación según #968; el criterio QA de “solo libros 0” debe aclarar si esa alerta es aceptable u obligatoria.  
6. Sin `TEST_DATABASE_URL`, la capa B no corre.  
7. Esta alternativa **no** elimina la solicitud DBA/Dev si el proyecto exige evidencia exclusivamente sobre el API TEST compartido.

---

## 9. Comandos y procedimiento para una futura ejecución autorizada

> No ejecutar todavía. Listado para cuando QA autorice **solo** la alternativa segura (pytest), no la escritura HTTP en TEST.

### 9.1 Preparar código con #968

```powershell
# Opción recomendada: worktree de solo lectura/ejecución desde origin/test
git fetch origin test
git worktree add ..\sgpmp-backend-g96-test origin/test
cd ..\sgpmp-backend-g96-test
```

### 9.2 Capa A — dominio (sin BD)

```powershell
python -m pytest tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G96/test_tc_m06_g96_valor_en_libros.py -v --noconftest --tb=short
python -m pytest tests/financial_valuation/test_m06_nucleo_nic41.py::test_valor_por_costo_no_baja_de_cero -v --noconftest
```

(Tras ajustar el test G96 para usar también `valor_libros_calculado` en 07.)

### 9.3 Capa B — integración aislada

```powershell
# TEST_DATABASE_URL debe apuntar a BD de pruebas, NUNCA al esquema compartido de negocio
$env:TEST_DATABASE_URL = "<postgresql+psycopg://.../pruebas-o-nombre-con-test>"

python -m pytest tests/integration/test_inc_m06_281_g68_valor_libros_cero.py -v -m integration --tb=short
```

Evidencias sugeridas a guardar bajo  
`tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G96/resultados/alternativa_segura/`:

- `pytest_dominio.xml` / log  
- `pytest_integracion_968.xml` / log  
- `resumen_alternativa_segura_G96.json` (subcaso → PASS/FAIL → capa → “persistido_en_TEST_compartido: false”)

### 9.4 Redacción del dictamen tras esa corrida

- Si A+B pasan: evidencia de **cálculo + alerta en aislamiento**; grupo puede pasar a un estado del tipo `EVIDENCIA_AISLADA_OK` / seguir `PREPARADO_CON_RIESGOS` respecto a TEST HTTP, según criterio del proyecto.  
- **Prohibido** etiquetar “alerta persistida en TEST (API)” sin corrida HTTP autorizada.

---

## 10. Relación con el seed compartido y con DBA

| Enfoque | ¿Necesita 3 activos DBA? | ¿Toca 2126/411? | Cobertura alerta |
|---|---|---|---|
| Ejecución HTTP en TEST compartido | Sí (o reset) | Riesgo alto | Sí, en TEST |
| **Alternativa segura A+B** | **No** | **No** | Sí, en BD de pruebas + dominio |
| Solo dominio A | No | No | No |

Recomendación: adoptar A+B como vía de desbloqueo técnico de G96 mientras DBA/Dev resuelven R1–R6 del documento de requerimientos, **sin** bajar el estado a APROBADO de ambiente compartido hasta decisión explícita de QA.

---

## 11. Dictamen de esta inspección

| Ítem | Valor |
|---|---|
| Alternativa viable sin DBA triple seed | **Sí** (A + B) |
| Usa lógica real (no mock de fórmula) | **Sí** (`valor_por_costo` / `valor_libros_calculado` / use cases) |
| Demuestra alerta persistente aislada | **Sí**, vía integración #968 en BD de pruebas |
| Demuestra alerta en TEST compartido | **No** |
| Escrituras / POST TEST en esta fase | **Ninguna** |
| Estado G96 | **PREPARADO_CON_RIESGOS** (se mantiene) |

**Próximo paso:** autorización expresa de QA para (1) alinear worktree a `origin/test`, (2) ejecutar solo pytest capas A/B, (3) archivar evidencias — o, en su defecto, esperar entregables DBA/Dev para corrida HTTP.
