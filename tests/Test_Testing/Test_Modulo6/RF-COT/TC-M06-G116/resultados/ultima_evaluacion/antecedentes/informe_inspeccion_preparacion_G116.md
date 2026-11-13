# TC-M06-G116 — Informe de inspección de preparación

## 1. Estado actual del caso

- Caso: **TC-M06-G116** (antecedente TC-M06-G88 / #1019 / INC-M06-332-G88).
- Corrección: #1024.
- Subcasos: TC-M06-46, TC-M06-47.
- Fase: inspeccion_preparacion_solo_lectura.
- Histórico G116 en `resultados/` (primera evaluación): REQUIERE ACLARACIÓN — **conservado**.
- Dictamen preparación: **PREPARADO_CONDICIONAL**

Candidatos de datos encontrados para los 4 escenarios, pero el despliegue de #1024 en TEST sigue PENDIENTE DE CONFIRMACIÓN. No ejecutar hasta confirmar.

## 2. Cambios documentales

- Se agrega `resultados/preparacion/expectativas_actualizadas_G116.md` con la matriz corregida (404/422).
- Se conservan íntegros `resumen_ejecucion_TC-M06-G116.json`, evidencias HTML/MD/JSON históricos.
- No se marca G116 como APROBADO.

## 3. Despliegue #1024 en TEST

- Estado: **PENDIENTE_DE_CONFIRMACION**
- Confirmado en TEST: False
- OpenAPI version observada: `1.0.0` (no identifica SHA de despliegue).
- Código en `origin/dev`: commit `29512934` / merge PR #1024 `e84650d3` incluyen `PERIODO_CONTABLE_CERRADO` tras `periodo.contiene(hoy)`.
- Tags de release recientes (`v1.4.0-rc.55` … `v1.4.0-rc.59`) **no** contienen el merge de #1024 (`git merge-base --is-ancestor` = NO).
- Por tanto **no** se asume que TEST tenga la corrección solo por existir rc.52+ o por el cierre del issue.
- Rama local `laura` aún no tiene el check (no implica estado de TEST).
- Sin POST funcional autorizado no se observó el 422 de período cerrado en runtime.

## 4. Tabla de escenarios y candidatos

| Escenario | Esperado | Candidato | Apto | Evidencia |
|---|---|---|---|---|
| Activo inexistente | 404 ACTIVO_NO_ENCONTRADO | 999999 | True | GET /finanzas/activos/999999 → 404 |
| Activo BAJA | 422 ACTIVO_NO_DISPONIBLE | 948 | True | GET /finanzas/activos/{id} estado BAJA |
| Sin VR vigente | 422 VALOR_RAZONABLE_NO_DISPONIBLE | 951 | True | GET detalle sin cálculo/VR |
| Período cerrado | 422 PERIODO_CONTABLE_CERRADO | 1568 | True | períodos 900000002 + activo 1568 |

### Detalle período cerrado

```json
{
  "id_activo_sugerido_dev": 1568,
  "activo": {
    "codigo": 200,
    "existe": true,
    "estado": "ACTIVO",
    "id_finca": 466,
    "razon_social": "QA M06 Cierre SAS",
    "indicador_valoracion": "VALOR_RAZONABLE",
    "reconocimiento_estado": "CONFIRMADO",
    "ultimo_calculo_estado": "CALCULADO",
    "valor_razonable_neto": "3760000.0000",
    "tiene_calculo": true,
    "n_calculos": 1,
    "n_reconocimientos": 1
  },
  "periodo_219": {
    "id_periodo_contable": 219,
    "estado": "CERRADO",
    "fecha_inicio": "2026-11-01",
    "fecha_fin": "2026-11-30",
    "fecha_cierre": "2026-11-10T06:18:00.098094Z",
    "razon_social": "QA M06 Cierre SAS"
  },
  "periodo_nov_2026": {
    "id_periodo_contable": 219,
    "estado": "CERRADO",
    "fecha_inicio": "2026-11-01",
    "fecha_fin": "2026-11-30",
    "fecha_cierre": "2026-11-10T06:18:00.098094Z",
    "razon_social": "QA M06 Cierre SAS"
  },
  "periodo_hoy_cerrado": true,
  "apto": true,
  "nota": "El rechazo PERIODO_CONTABLE_CERRADO aplica cuando el período que contiene la fecha de emisión (hoy) está cerrado; periodo_para traslada y el use case responde 422 si el período resuelto no contiene hoy. No basta con que 219 esté cerrado si noviembre está ABIERTO."
}
```

### Período 220: `{"id_periodo_contable": 220, "estado": "ABIERTO", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-30", "fecha_cierre": null, "razon_social": "QA M06 Operaciones SAS"}`
### Período 219: `{"id_periodo_contable": 219, "estado": "CERRADO", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-30", "fecha_cierre": "2026-11-10T06:18:00.098094Z", "razon_social": "QA M06 Cierre SAS"}`

## 5. Consultas de solo lectura realizadas

- Total peticiones registradas: 24
- GET health/version/openapi, períodos por NIT, listado/detalle de activos, cotizaciones, auditoría.
- Única escritura de autenticación: POST /sesiones/ (sin cotizaciones).

- Baseline cotizaciones: total=7, ids=[10, 9, 8, 7, 6, 4, 5]
- Baseline eventos COTIZACION_REGISTRADA: 5

## 6. Riesgos / dependencias

- Despliegue de #1024 en TEST **no confirmado**; releases rc.55–rc.59 no incluyen el merge.
- Si TEST aún corre código previo a #1024, el escenario de período cerrado puede insertar cotización trasladando período (comportamiento histórico) en lugar de 422.
- No cerrar 220 ni reabrir 219. No usar cotizaciones 6/7 ni activos 1570/1571 (#1022).
- Rama local `laura` sin el check; `origin/dev` sí.

## 7. Recomendación de ejecución

**Listo para ejecutar:** False

Datos candidatos: listos para los 4 escenarios (incl. 1568 + período 219 CERRADO = noviembre del titular 900000002).

Requisitos previos:
- Confirmación verificable de que TEST despliega el fix de #1024 (SHA/release que contenga `29512934`/`e84650d3`, o dictamen técnico).
- Autorización expresa para los POST negativos.

## 8. Confirmación de no escritura

**No se ejecutaron POST de cotizaciones ni operaciones de escritura sobre datos de TEST** (solo autenticación de sesión y GET).

Dictamen: **PREPARADO_CONDICIONAL**

