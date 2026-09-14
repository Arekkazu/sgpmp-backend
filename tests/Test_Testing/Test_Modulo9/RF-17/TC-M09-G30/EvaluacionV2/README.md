# TC-M09-G30 — Evaluación V2 (reevaluación TC-M09-64, auditoría de umbrales)

Reevaluación de **TC-M09-64 — Verificar auditoría de creación y modificación de
umbrales** (RF-17). Coexiste con la evaluación V1 de `RF-17/TC-M09-G30/`
(BLOCKED), que es de solo lectura. Entorno **TEST**, actor Administrador
`administador.dev@gmail.com`, herramienta Newman.

Estrategia: **1 CREATE + 1 UPDATE sobre el mismo umbral**. La auditoría se
verifica en `GET /configuracion/umbrales/{id}/auditoria` (endpoint añadido por
INC-M09-30-G30), correlacionando por ID, usuario, operación, ventana temporal
UTC y valores.

## Archivos

| Archivo | Función |
| --- | --- |
| `helpers.cjs` | Login, actor, preflight/contrato, mapa especie-variable, selección de combinación libre de Temperatura, payloads exactos, observación D09 global |
| `run.cjs` | Fases `plan` → `create` → `audit-create` → `update` → `audit` con estado persistido (`estado-tc64.json`) que impide repetir una escritura persistida |
| `TC-M09-G30-reevaluacion-v2.postman_collection.json` | Cuatro grupos de requests con sus aserciones |

## Ejecución

```bash
export G30_REEVAL_V2_RUN_ID=G30-REEVAL-V2-<fecha>-<hora>
export TEST_ADMIN_PASSWORD=...     # nunca en archivos
export NODE_PATH="$(npm root -g)"
for f in plan create audit-create update audit; do G30_FASE=$f node run.cjs; done
```

Cada fase aborta si su checklist previo no se cumple. `create` y `update` no se
repiten si ya persistieron, y ninguna fase sobrescribe su evidencia. Sin
cleanup: el umbral creado se conserva.
