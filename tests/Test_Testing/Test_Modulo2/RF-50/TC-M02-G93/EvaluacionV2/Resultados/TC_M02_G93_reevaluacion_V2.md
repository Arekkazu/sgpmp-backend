# REEVALUACIÓN V2 — TC-M02-G93

**Proyecto:** SGPMP / SIGAB · **Módulo:** M02 · **RF:** RF-50 — Disponibilidad de datos para módulos analíticos · **CU:** CU12
**Sub-casos:** TC-M02-155, TC-M02-156 (variantes A y B), TC-M02-157
**Responsable QA:** Juan Esteban · **Ambiente previsto:** TEST · **Fecha:** 2026-09-19

---

## 0. Estado

# ⏸️ REEVALUACIÓN NO EJECUTADA

**Motivo: error de QA en el registro de los hallazgos.** La reevaluación V2 de TC-M02-G93 queda aplazada hasta que Desarrollo atienda los hallazgos que aún no habían llegado al repositorio de GitHub.

No se ejecutó ninguna herramienta contra TEST para esta V2: cero peticiones a la API, cero consultas a la base de datos, cero ejecuciones de Newman y ninguna escritura. La Evaluación V1 permanece intacta.

---

## 1. Qué ocurrió

La evaluación V1 de TC-M02-G93 terminó en **RECHAZADO** y dejó **5 hallazgos formales**. Esos 5 hallazgos se registraron correctamente en el Excel de seguimiento indicado y en Taiga.

Sin embargo, **en el repositorio de GitHub solo se creó 1 de los 5 issues**. Como el equipo de Desarrollo trabaja las correcciones a partir de los issues del repositorio, solo se corrigió ese hallazgo; los otros 4 nunca les llegaron por ese canal y siguen sin atender.

El error es de QA (responsable: Juan Esteban): la publicación de los hallazgos en GitHub quedó incompleta. No es un incumplimiento del equipo de Desarrollo, que atendió todo lo que tenía registrado.

---

## 2. Hallazgos V1 y su estado de registro

| # | Hallazgo V1 | Excel | Taiga | GitHub | Corrección de Desarrollo |
|---|---|---|---|---|---|
| 1 | **DEF-G93-01** — Fechas futuras aceptadas en `datos-consolidados` (TC-M02-156-B: esperado 400, obtenido 200 con datos) | ✅ | ✅ | ✅ **Sí se subió** | ✅ Corregido |
| 2 | **BLOQ-G93-02** — TC-M02-155 no ejecutable: no existe el modelo de módulos consumidores con scopes por `tipo_dato` | ✅ | ✅ | ❌ **No se subió** | ⛔ Sin atender |
| 3 | **BLOQ-G93-03** — TC-M02-157 no ejecutable: M06 no es un consumidor autenticable | ✅ | ✅ | ❌ **No se subió** | ⛔ Sin atender |
| 4 | **OBS-G93-02** — `metricas_actuales` ignora el filtro temporal y RF-50 no valida la suficiencia de métricas de peso para NIC-41 (no hay vía a 422) | ✅ | ✅ | ❌ **No se subió** | ⛔ Sin atender |
| 5 | **OBS-G93-03** — El mensaje de error expone la traza cruda de Pydantic (nombre del DTO, diccionario de entrada y URL externa) | ✅ | ✅ | ❌ **No se subió** | ⛔ Sin atender |

### Única corrección disponible hoy

El único hallazgo con corrección en el repositorio es **DEF-G93-01**:

```text
commit a2d583758efeab20b12d6a7ebc1306c0eb643559
fix(rf50): rechazar rango de fechas futuro en datos-consolidados
Corrige INC-M02-91-G93
```

Ese commit es ancestro del HEAD actual de la rama QA (`a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`). Es la única evidencia de trabajo de Desarrollo sobre TC-M02-G93, y es coherente con que solo ese issue llegara a GitHub.

---

## 3. Por qué no se reevalúa todavía

Ejecutar ahora la V2 daría un resultado engañoso y obligaría a repetir todo el trabajo más adelante:

- **4 de los 5 hallazgos siguen abiertos**, y dos de ellos (BLOQ-G93-02 y BLOQ-G93-03) mantienen bloqueados a TC-M02-155 y TC-M02-157. Sin la precondición que falta, esos sub-casos volverían a quedar BLOQUEADOS, igual que en V1.
- El veredicto global de TC-M02-G93 **no puede pasar a APROBADO** con solo un hallazgo corregido de cinco, de modo que la reevaluación se cerraría otra vez en RECHAZADO sin aportar información nueva.
- QA no puede fabricar las precondiciones que faltan (identidad de módulo consumidor con scopes, M06 como consumidor autenticable) ni corregir el producto: eso corresponde a Desarrollo.

Por eso se aplaza la V2 y no se consume ambiente TEST.

---

## 4. Acciones

### A cargo de QA (Juan Esteban)

1. Subir al repositorio de GitHub los **4 issues faltantes**: BLOQ-G93-02, BLOQ-G93-03, OBS-G93-02 y OBS-G93-03, con la misma información ya registrada en el Excel y en Taiga (descripción, sub-caso, severidad, evidencia y responsable).
2. Enlazar cada issue nuevo con su registro de Taiga y con la evidencia de V1 (`Resultados/TC-M02-G93_resultado.md`, `reporte_tc_m02_g93.json`, `reporte_tc_m02_g93.html`).
3. Avisar a Desarrollo de que los 4 issues quedaron publicados.
4. **Revisar el resto de casos de M02** para confirmar que no se repitió la misma omisión entre el Excel/Taiga y GitHub.

### A cargo de Desarrollo

5. Atender los 4 issues y avisar cuando las correcciones estén desplegadas en TEST.

### A cargo de QA, después del aviso

6. Ejecutar la reevaluación V2 completa de TC-M02-G93 sobre TEST: gate de rama y contrato, fixtures, ejecución única y reevaluación de los 5 hallazgos, preservando V1.

---

## 5. Condición para ejecutar la V2

La reevaluación se ejecutará cuando se cumplan las dos condiciones:

```text
1. Los 4 issues restantes están publicados en el repositorio de GitHub.
2. Desarrollo avisa de que sus correcciones están desplegadas en TEST.
```

Mientras tanto, TC-M02-G93 conserva el veredicto de V1: **RECHAZADO**, con TC-M02-155 y TC-M02-157 BLOQUEADOS.

---

## 6. Integridad

- No se ejecutó Newman, ni Pytest, ni ninguna petición a la API de TEST, ni ninguna consulta a la base de datos para esta V2.
- No se modificó ningún archivo de la Evaluación V1 (`construir_coleccion.cjs`, `test_tc_m02_g93.json`, `Resultados/`).
- No se modificó código del producto. Sin commit, push, merge, rebase ni deploy, y sin cambio de rama.
- Este documento es el único artefacto de `EvaluacionV2/` para TC-M02-G93 por ahora.
