# TC-M09-G78 — Evaluación V1 (primera evaluación de TC-M09-149)

**TC-M09-149 — Mantener calibración pendiente cuando falla la propagación al
firmware** (RF-24, CU-05). Ambiente decisorio: **DEV**, porque MQTT solo existe
allí. TEST solo se consulta para comparar el contrato REST desplegado.

`test_tc_m09_149.py` es una verificación de implementación de **solo lectura**:
lee el OpenAPI desplegado en DEV y TEST y el código de `origin/dev` con
`git show` / `git grep`. No hace login, POST, SQL, checkout, fetch ni conexión
MQTT.

- Las pruebas de precondición comprueban la rama, la accesibilidad de DEV, el
  endpoint desplegado, que el código local coincide con `origin/dev` y que TEST
  y DEV comparten el contrato de calibración.
- Las pruebas `test_oraculo_*` codifican lo que exige la matriz: estado de
  propagación en el contrato, invocación MQTT desde la calibración, estado
  pendiente persistido y reintento automático. Si fallan, documentan la ausencia
  del flujo; no se ajustan para que pasen.

## Ejecución

Desde la raíz de `sgpmp-backend`:

```bash
V1=tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G78/EvaluacionV1
RUN=G78-EVAL-V1-<fecha>-<hora>
mkdir -p "$V1/RESULTADOS/$RUN"
PYTHONDONTWRITEBYTECODE=1 G78_RUN_ID=$RUN python -m pytest "$V1/test_tc_m09_149.py" -v -rA \
  -p no:cacheprovider --confcutdir="$V1" \
  --junitxml="$V1/RESULTADOS/$RUN/pytest-TC-M09-149.xml" | tee "$V1/RESULTADOS/$RUN/pytest-TC-M09-149.log"
```

`--confcutdir` evita cargar los `conftest.py` del backend, y
`no:cacheprovider` junto con `PYTHONDONTWRITEBYTECODE` evitan escribir fuera de
esta carpeta. La prueba se niega a sobrescribir una evidencia existente.

Resultado de `G78-EVAL-V1-20260913-002659`: **DESAPROBADO — FUNCIONALIDAD NO
IMPLEMENTADA** (FLUJO → Desarrollo). Ver
`RESULTADOS/G78-EVAL-V1-20260913-002659/TC-M09-G78_resultado.md`.
