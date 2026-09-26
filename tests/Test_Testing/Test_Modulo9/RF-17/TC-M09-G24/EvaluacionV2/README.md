# TC-M09-G24 — Evaluación V2 (reevaluación RF-17, niveles de alerta)

Reevaluación de TC-M09-52 (nivel fuera del rango general), TC-M09-53
(solapamiento entre niveles) y TC-M09-54 (niveles continuos válidos). Coexiste
con la evaluación V1 de `RF-17/TC-M09-G24/`, que es de solo lectura. Entorno
**TEST**, actor Administrador `administador.dev@gmail.com`, herramienta Newman
(sin UI).

Oráculos resueltos antes del primer POST:

| Caso | HTTP | error_code | Persistencia |
| --- | --- | --- | --- |
| TC-M09-52 | 400 | `NIVEL_FUERA_DE_RANGO` | No |
| TC-M09-53 | 422 (contrato vigente; matriz y RF-17 dicen 400) | `SOLAPAMIENTO_NIVELES` | No |
| TC-M09-54 | 201 | — | Sí, con continuidad exacta |

## Archivos

| Archivo | Función |
| --- | --- |
| `helpers.cjs` | Login, actor, preflight, mapa especie-variable, selección de combinación libre, payloads exactos y análisis matemático |
| `plan.cjs` | Discovery y checklists previos (sin POST) |
| `run-newman.cjs` | Un original por invocación: revalida precondiciones, un POST real y GET de persistencia |
| `verificar-cierre.cjs` | Verificación final de solo lectura |
| `TC-M09-G24-reevaluacion-v2.postman_collection.json` | Copia de la colección V1 ya corregida |

## Ejecución

```bash
export G24_REEVAL_V2_RUN_ID=G24-REEVAL-V2-<fecha>-<hora>
export TEST_ADMIN_PASSWORD=...        # nunca en archivos
node plan.cjs
NODE_PATH="$(npm root -g)" G24_CASE=TC-M09-52 G24_INTENTO=1 node run-newman.cjs   # después 53 y 54
node verificar-cierre.cjs
```

Límites implementados: 2 POST por original como máximo; no se reintenta un PASS
ni un negativo que persistió; si un negativo persiste, se detiene el uso de la
combinación; no se sobrescribe evidencia. Sin cleanup: el umbral creado por
TC-54 se conserva.
