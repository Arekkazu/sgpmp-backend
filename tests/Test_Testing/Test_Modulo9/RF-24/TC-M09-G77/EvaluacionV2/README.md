# TC-M09-G77 — Evaluación V2 (reevaluación de TC-M09-148)

Reevaluación de **TC-M09-148 — Rechazar calibración realizada por usuario sin
permisos** (RF-24, CU-05). Coexiste con la evaluación original de
`RF-24/TC-M09-G77/`, que es de solo lectura y no se modifica.

Escenario: un **Productor** autenticado y activo envía una calibración válida
en todo lo demás (dispositivo activo, sensor asociado, área vigente, valor
interior al rango). Se espera **HTTP 403 por RBAC** y **ninguna calibración
persistida**.

Entorno: **TEST** únicamente (G77 no usa MQTT). No usa Cypress ni PostgreSQL.

## Archivos

| Archivo | Función |
| --- | --- |
| `helpers.cjs` | Login, GET, descubrimiento dinámico, construcción del payload y saneamiento |
| `precheck.cjs` | Precondiciones sin POST: contrato, actor negativo, datos, HISTORY_BEFORE y checklist |
| `run-newman.cjs` | Único POST negativo con Newman, HISTORY_AFTER y evidencia sanitizada |
| `TC-M09-G77-reevaluacion-v2.postman_collection.json` | Colección con un solo request y sus aserciones |
| `RESULTADOS/<RUN_ID>/` | Evidencias y reporte `TC-M09-G77_reevaluacion_V2.md` |

## Ejecución

Las contraseñas se pasan solo como variables de proceso; nunca en archivos.
Newman y htmlextra están instalados globalmente, por eso se define `NODE_PATH`.

```bash
export G77_CASE=TC-M09-148
export G77_REEVAL_V2_RUN_ID=G77-REEVAL-V2-<fecha>-<hora>
export TEST_PRODUCTOR_PASSWORD=...   # actor negativo m2m.nuevo@ejemplo.com
export TEST_ENGINEER_PASSWORD=...    # ingeniero@pecuaria.co, solo GET
export TEST_ADMIN_PASSWORD=...       # administador.dev@gmail.com, solo GET

node precheck.cjs                    # debe terminar con LISTO_PARA_POST = true
NODE_PATH="$(npm root -g)" G77_INTENTO=1 node run-newman.cjs
```

`run-newman.cjs` se niega a sobrescribir evidencia, exige un precheck completo
y bloquea un tercer POST. El intento 2 solo procede si el intento 1 no persistió
y fue invalidado por un error de prueba concreto y corregido.

El Administrador se usa exclusivamente para GET, porque en TEST el Ingeniero no
tiene fincas asignadas y el alcance de finca le oculta dispositivos y
asociaciones. Nunca se ejecuta una calibración positiva.
