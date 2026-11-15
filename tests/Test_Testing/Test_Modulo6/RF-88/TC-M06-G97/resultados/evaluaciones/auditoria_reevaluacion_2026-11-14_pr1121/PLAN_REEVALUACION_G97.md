# Plan de reevaluación — TC-M06-G97

**Fecha:** 2026-11-14  
**Dictamen actual:** solución **integrada en `dev`/`test` (git)**; contrato **visible en OpenAPI TEST**; **AC funcionales no ejecutados** → G97 **no APROBADO**.

---

## 0. Gates previos

| Gate | Criterio | Si falla |
|---|---|---|
| G0 | Workspace/QA alineado a commit con `4f3d4962` (p. ej. `origin/test` o `dev`) | Actualizar rama; no auditar código viejo de `laura` |
| G1 | OpenAPI TEST contiene `/finanzas/activos/{id}/depreciacion` | Reabrir bloqueo de despliegue |
| G2 | Contador QA con `valoracion_por_costo` R | Abortar GET |
| G3 | Activo apto TC-M06-09 identificado (12M / 72 / fecha) **o** plan de preparación autorizado | No inventar ID; escalar datos |
| G4 | Para 08: especie/activo de prueba **autorizados** sin contaminar config compartida | No modificar especies productivas |

---

## 1. Orden seguro (cuando se autorice la reevaluación funcional)

```text
[1] Confirmacion despliegue: OpenAPI + GET autenticado de humo (activo conocido al costo)
[2] Inventario readonly: buscar candidato 12M/72 o solicitar preparacion a Samuel/Contador
[3] TC-M06-09: GET depreciacion a adquisicion+12m + aserciones + verificar no side-effect
[4] TC-M06-08 camino A: solo con autorizacion de reconocimiento de prueba
[5] TC-M06-08 camino B: solo si existe registro historico autorizado
[6] (Opcional) prevalidacion cierre readonly si API lo permite sin cerrar
```

No cerrar períodos compartidos. No usar 219/220 de otros casos salvo que el activo de G97 viva allí **y** esté autorizado.

---

## 2. Diseño TC-M06-09 (solicitud y aserciones)

```http
GET /finanzas/activos/{id}/depreciacion?fecha={YYYY-MM-DD}
Authorization: Bearer <token_contador>
X-Zona-Horaria: America/Bogota
```

`fecha` = fecha de adquisición del activo + 12 meses calendario (coherente con `meses_transcurridos`).

| Campo | Esperado (activo 12.000.000 / 72 meses, sin deterioro) |
|---|---|
| `depreciacion_anual` | 2000000 |
| `depreciacion_acumulada` | 2000000 |
| `valor_contable` | 10000000 |
| `depreciacion_registrada` | = `valoracion_costo.depreciacion_acumulada` previa (a menudo 0) |
| `vida_util_meses` | 72 |
| `meses_transcurridos` | 12 |

Si el activo real tiene costo/vida distintos, **recalcular** esperados con la misma fórmula; no forzar 12M/72 inventados.

---

## 3. Diseño TC-M06-08

### Camino A — Reconocimiento
1. Preparar (autorizado) activo/especie sin vida útil, elegible a costo.  
2. Confirmar reconocimiento → esperar **422** `VIDA_UTIL_NO_CONFIGURADA`.  
3. No dejar reconocimientos parciales no autorizados.

### Camino B — Consulta histórica
1. Solo si hay valoración al costo sin `vida_util_meses` y especie sin parámetro.  
2. `GET .../depreciacion` → **422** `VIDA_UTIL_NO_CONFIGURADA`.  
3. No fabricar el registro con SQL en TEST sin autorización explícita.

---

## 4. Criterios de aprobación del grupo G97

| Requisito | Necesario |
|---|---|
| TC-M06-09 APROBADO con evidencia GET en TEST | Sí |
| TC-M06-08 APROBADO (al menos un camino con evidencia) | Sí |
| Side-effect: consulta no modifica depreciación registrada | Sí |
| Sin depender solo del cierre de #1114 / merge #1121 | Sí |

Hasta entonces: **no APROBADO** / reevaluación funcional **pendiente**.

---

## 5. Responsables

| Quién | Acción |
|---|---|
| QA | Actualizar rama; inventario readonly; ejecutar 09; pedir auth para 08 |
| Contador / Samuel | Preparar activo 12M/72 o especie aislada sin vida útil si no existen |
| Backend | Ya integró código; soporte si OpenAPI≠runtime |
