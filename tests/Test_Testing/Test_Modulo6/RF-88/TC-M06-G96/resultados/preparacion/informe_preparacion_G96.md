# TC-M06-G96 — Informe de preparación (solo lectura)

**Fase:** preparación · **Escritura:** No · **Dictamen de grupo:** pendiente de autorización funcional  
**Antecedentes:** INC-M06-280-G68 (#967) datos aislados; INC-M06-281-G68-07 (#968) alerta · commit `8829599f` / lote PR #1036  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test` · Usuario sesión: Contador (`QA_CORREO`)

---

## 1. Estado actual de los datos aislados

Consultado con Contador (GET). Coincide con lo declarado por el responsable:

| Dato | Esperado | Observado |
|---|---|---|
| Activo | 2126 `QA-M06-DEP-COSTO-10M` | OK · estado **ACTIVO** |
| Finca / infraestructura | 478 / 1253 | OK |
| Titular | NIT 901999213(-8) | Periodo visible con NIT `901999213` · razón social `[SEED-QA-M06-DEP] Agropecuaria Depreciacion S.A.S.` |
| Periodo 411 | ABIERTO 2026-11-01…11-30 | **ABIERTO** · mismas fechas |
| Reconocimiento 886 | CONFIRMADO · costo | **CONFIRMADO** · `VALORACION_POR_COSTO` · periodo 411 |
| Valoración por costo | 66 | **id 66** · `es_activa=true` |
| Costo | 10.000.000 | **`10000000.0000`** |
| Depreciación acumulada | 0 | **`0.0000`** |
| Deterioro acumulado | 0 | **`0.0000`** |
| Valor en libros | 10.000.000 | **`10000000.0000`** |
| Vida útil (valoración) | — | **100 meses** (relevante para cómo se obtiene la depreciación) |
| Eventos sanitarios del activo | — | **0** (HTTP 200) |
| Auditoría `VALOR_LIBROS_AJUSTADO_A_CERO` (activo 2126) | baseline | HTTP 200 · **total 0** |

**Permisos Contador observados:** `valoracion_por_costo` C/R/U (1,2,3), `cierre_periodo` R/E (2,5), `auditoria_financiera` R (2), `configuracion_contable` C/R/U, `valoracion_activos` R/E.

---

## 2. Endpoints identificados (RF-88 / verificación)

| Uso | Método y ruta | Permiso |
|---|---|---|
| Consultar valor en libros / dep / det | `GET /finanzas/activos/{id}` → `valoracion_costo` | `valoracion_activos` R |
| Listar eventos sanitarios (precondición deterioro) | `GET /finanzas/activos/{id}/eventos-sanitarios` | `valoracion_por_costo` R |
| Registrar deterioro | `POST /finanzas/activos/{id}/deterioros` | `valoracion_por_costo` C |
| Depreciación del periodo | **No hay POST de monto de depreciación.** Se calcula en `POST /finanzas/periodos/{id}/cierre` vía `_depreciar` | `cierre_periodo` E |
| Prevalidación cierre | `GET /finanzas/periodos/{id}/prevalidacion` | `cierre_periodo` |
| Periodos | `GET /finanzas/periodos?numero_id_tributaria=` | lectura finanzas |
| Alerta persistente (#968) | `GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO&id_activo_biologico=2126&formato=TECNICO\|LEGIBLE` | `auditoria_financiera` R |
| Aviso en bandeja (complementario) | `GET /notificaciones` · código esperado `ALERTA_FINANCIERA_NIC41` (según commit #968) | notificaciones |
| OpenAPI | `GET /openapi.json` · path deterioros presente | — |

**DTO deterioro (OpenAPI / código):** `id_evento_sanitario`, `impacto_economico_cop` > 0, `justificacion` ≥ 30 caracteres.

**Fórmula de dominio:** `MAX(0, costo − depreciación_acumulada − deterioro_acumulado)` (`nic41.valor_por_costo` / actualización en deterioro).

---

## 3. Criterios de aceptación por subcaso

| Subcaso | Costo | Depreciación | Deterioro | Esperado |
|---|---:|---:|---:|---|
| TC-M06-05 | 10.000.000 | 2.000.000 | 1.000.000 | Valor en libros **7.000.000** |
| TC-M06-06 | 10.000.000 | 10.000.000 | 0 | Valor en libros **0** |
| TC-M06-07 | 10.000.000 | 7.000.000 | 5.000.000 | Valor en libros **0** + alerta persistente (`VALOR_LIBROS_AJUSTADO_A_CERO`; cálculo matemático −2.000.000) |

---

## 4. Procedimiento de ejecución propuesto (aún no autorizado)

### Hallazgo crítico de diseño de prueba

No existe endpoint que reciba “depreciación = X”. La depreciación acumulada la produce el **cierre de periodo** según `vida_util_meses` y meses transcurridos desde `fecha_adquisicion`.

Hoy la valoración 66 tiene **vida útil 100 meses** → depreciación mensual teórica = 100.000. Para alcanzar exactamente 2M / 7M / 10M haría falta ajustar vida útil / fechas / número de cierres (escrituras de configuración o de cierre), **no** un POST de monto.

Además, `POST .../deterioros` exige un **evento sanitario del mismo activo**. Hoy hay **0** eventos → antes del deterioro hace falta crear/asignar un evento sanitario (escritura M02/RF-41 u operación autorizada), fuera del alcance de esta preparación.

### TC-M06-05 (objetivo libros 7.000.000)

1. Baseline GET activo 2126 (dep=0, det=0, libros=10M).  
2. Conseguir depreciación acumulada **2.000.000** (vía cierre(s) con vida útil/meses coherentes, **o** dato pre-acondicionado por el responsable).  
3. Asegurar ≥1 evento sanitario del activo 2126.  
4. `POST /finanzas/activos/2126/deterioros` con `impacto_economico_cop=1000000` y justificación ≥30.  
5. Verificar `GET /finanzas/activos/2126`: dep≈2M, det=1M, `valor_contable_por_costo=7000000.0000`.  
6. **No** exigir alerta de ajuste a cero (libros siguen positivos).

### TC-M06-06 (objetivo libros 0, solo depreciación)

1. Requiere activo/valoración en estado inicial (dep=0, det=0, costo=10M) **o** otro activo gemelo.  
2. Conseguir depreciación acumulada **10.000.000** (vida útil agotada / tope al costo en cierre).  
3. Sin deterioro.  
4. Verificar libros **0**. Puede o no generar `VALOR_LIBROS_AJUSTADO_A_CERO` según si el cierre detecta cálculo negativo o solo tope al costo (validar en ejecución; el commit #968 también cubre depreciación de cierre).

### TC-M06-07 (objetivo libros 0 + alerta)

1. Estado con depreciación **7.000.000** y deterioro **0**, libros 3.000.000.  
2. Evento sanitario disponible.  
3. `POST .../deterioros` con impacto **5.000.000**.  
4. Esperado: `valor_contable=0`; en respuesta posiblemente `aviso` y/o `valor_libros_calculado=-2000000` (si el deploy incluye #968).  
5. Persistencia: `GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO&id_activo_biologico=2126` → ≥1 evento WARNING con payload `valor_calculado` / `valor_aplicado=0.0000`.  
6. Complemento: bandeja Contador `ALERTA_FINANCIERA_NIC41` (no sustituye la auditoría).

---

## 5. Cómo verificar el valor en libros

`GET /finanzas/activos/2126` → objeto `valoracion_costo`:

- `costos_adquisicion`
- `depreciacion_acumulada`
- `deterioro_acumulado`
- `valor_contable_por_costo` ← **valor en libros**

Comparar contra el esperado del subcaso (string decimal con 4 decimales, p. ej. `7000000.0000`).

---

## 6. Cómo demostrar la alerta persistente (TC-M06-07)

1. **Fuente de verdad del caso:** auditoría financiera  
   `GET /finanzas/auditoria?tipo_evento=VALOR_LIBROS_AJUSTADO_A_CERO&id_activo_biologico=2126&formato=LEGIBLE`  
   (o `TECNICO`).  
   Comprobar: `total_registros ≥ 1`, severidad WARNING, descripción/payload con valor calculado negativo y aplicado 0.

2. **Evidencia de que el tipo existe en TEST:** hoy el filtro `VALOR_LIBROS_AJUSTADO_A_CERO` responde **200** (un tipo inexistente responde **400 `TIPO_EVENTO_INVALIDO`**). Baseline del activo: **0** eventos.

3. **No asumir** que el cierre de #968 garantiza el comportamiento: hay que ejercitar el POST de deterioro (o cierre) y volver a leer.

4. **Discrepancia de repositorio:** el commit `8829599f` (**#968**) **no está en la rama local `laura`** (`git merge-base --is-ancestor` falso). Sí aparece en tags `v1.4.0-rc.52+`. TEST ya reconoce el enum del evento. La corrida funcional debe basarse en el comportamiento **desplegado**, no solo en el árbol local de `laura`.

---

## 7. Riesgos de reutilización (activo 2126 / periodo 411)

| Riesgo | Impacto |
|---|---|
| Un solo activo para tres subcasos | Tras TC-05/07 el deterioro/dep ya no son 0; **no se pueden reejecutar** los tres sobre el mismo baseline sin reset del responsable. |
| Depreciación vía **cierre 411** | Cierra el periodo del NIT seed; afecta a **todos** los activos reconocidos de ese titular; abre periodo siguiente. Alto impacto. |
| Cambiar `vida_util_meses` de la especie | Efecto compartido sobre otros activos a costo de esa especie. |
| Sin eventos sanitarios | Bloqueo inmediato del POST de deterioro hasta crear uno. |
| Vida útil actual = 100 | No produce 2M/7M/10M de depreciación con un único mes de noviembre 2026 sin reconfigurar. |
| Orden TC-05 → TC-07 sobre el mismo activo | Estados acumulativos incompatibles con montos absolutos de la matriz. |

**Recomendación de preparación (para autorización posterior):**  
pedir al responsable **tres valoraciones/activos gemelos** en baseline (10M / 0 / 0), **o** reset explícito entre subcasos, **más** al menos un evento sanitario por activo, **y** aclarar si la depreciación objetivo se pre-cargará o si se autoriza ajustar vida útil / cierres controlados.

---

## 8. Operaciones POST que serán necesarias (efectos esperados)

| POST | Efecto | Subcasos |
|---|---|---|
| (Posible) alta/uso de evento sanitario en M02 | Habilita `id_evento_sanitario` | 05, 07 (y 06 si no aplica) |
| (Posible) `PUT` configuración especie / vida útil | Cambia meses de depreciación del cierre | 05, 06, 07 |
| `POST /finanzas/periodos/411/cierre` (o cierres sucesivos) | Calcula/acumula depreciación; **cierra 411**; asientos; auditoría `DEPRECIACION_REGISTRADA`; posible alerta si aplica | según diseño acordado |
| `POST /finanzas/activos/2126/deterioros` | Suma deterioro, recalcula libros ≥0, asiento, `DETERIORO_REGISTRADO`; si cálculo &lt; 0 → libros 0 + (si deploy #968) `VALOR_LIBROS_AJUSTADO_A_CERO` + aviso Contador | 05 (1M), 07 (5M) |

**Ninguno de estos POST se ejecutó en esta fase.**

---

## 9. Issues / commit (documental)

| Ref | Estado en preparación |
|---|---|
| #967 | Datos aislados **presentes y verificados** en TEST (activo 2126 / periodo 411). |
| #968 / `8829599f` | Introduce `VALOR_LIBROS_AJUSTADO_A_CERO` + notificación. **No en `laura` local**; tipo de evento **aceptado en TEST**. Funcionamiento del alta: **no verificado** (sin escritura). |
| PR/lote #1036 | Contiene el merge del lote que incluye el fix #968 (evidencia git). |

---

## 10. Dictamen de preparación

**PREPARADO_CON_RIESGOS — pendiente autorización y precondiciones.**

- Lectura del baseline: **OK**.  
- Endpoints y verificación de libros/alerta: **identificados**.  
- Ejecución funcional de 05/06/07: **bloqueada operativamente** hasta resolver (a) depreciación exacta sin dañar el aislamiento, (b) evento sanitario, (c) estrategia anti-reutilización del activo 2126, (d) confirmación de deploy #968 en el flujo de escritura.

Solicitud formal a DBA/Desarrollo (R1–R6):  
`resultados/preparacion/requerimientos_pendientes_DBA_Desarrollo_G96.md`.

Análisis de alternativa segura (dominio + integración aislada, sin escritura en TEST compartido):  
`resultados/preparacion/analisis_alternativa_segura_G96.md`.

El grupo **permanece** en `PREPARADO_CON_RIESGOS` hasta que QA revise las condiciones entregadas y autorice expresamente la ejecución. No hay escritura pendiente ni autorizada en esta fase.

Histórico BLOQUEADO anterior conservado en `resultados/primera_evaluacion/`.  
Evidencia de esta inspección: `resultados/preparacion/inspeccion_preparacion_G96.json`.
