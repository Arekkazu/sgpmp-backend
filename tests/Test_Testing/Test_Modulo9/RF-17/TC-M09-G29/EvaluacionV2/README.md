# TC-M09-G29 — Evaluación V2 (reevaluación RF-17, propagación a Nodo Edge)

Reevaluación de TC-M09-62 (propagación exitosa hacia Nodo Edge) y TC-M09-63
(fallo de sincronización). Coexiste con la evaluación V1 de `RF-17/TC-M09-G29/`
(BLOCKED en TEST), que es de solo lectura. Ambiente decisorio: **DEV**, porque
MQTT solo existe allí.

`test_tc_m09_g29.py` es una verificación de implementación de **solo lectura**:
- contrato OpenAPI desplegado en DEV y TEST;
- código de `origin/dev` con `git show` / `git grep`;
- login del Administrador DEV y GET de umbrales reales.

No hace POST ni PATCH de umbrales, SQL, checkout, fetch ni conexión MQTT. Las
pruebas `test_oraculo_*` codifican lo que exige RF-17; si fallan, documentan la
ausencia del flujo.

## Ejecución

Desde la raíz de `sgpmp-backend`:

```bash
V2=tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G29/EvaluacionV2
RUN=G29-REEVAL-V2-<fecha>-<hora>
mkdir -p "$V2/RESULTADOS/$RUN"
PYTHONDONTWRITEBYTECODE=1 G29_REEVAL_V2_RUN_ID=$RUN DEV_ADMIN_PASSWORD=... \
  python -m pytest "$V2/test_tc_m09_g29.py" -v -rA -p no:cacheprovider --confcutdir="$V2" \
  --junitxml="$V2/RESULTADOS/$RUN/pytest-TC-M09-G29-v2.xml" > "$V2/RESULTADOS/$RUN/pytest-TC-M09-G29-v2.log" 2>&1
```

La contraseña va solo en la variable de proceso. La prueba no sobrescribe
evidencia existente.

Resultado de `G29-REEVAL-V2-20260913-014534`: **DESAPROBADO — FUNCIONALIDAD NO
IMPLEMENTADA** (FLUJO → Desarrollo) para TC-62 y TC-63.
