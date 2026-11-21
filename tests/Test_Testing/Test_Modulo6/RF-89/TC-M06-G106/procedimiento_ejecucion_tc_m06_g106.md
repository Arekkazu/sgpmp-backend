# Procedimiento de TC-M06-G106

Ejecutor: `ejecutar_tc_m06_g106.py`.

La primera evaluación permanece en `resultados/primera_evaluacion/`. El
diagnóstico escribe en `resultados/soporte_preparacion/`. La ejecución
funcional escribe en `resultados/ultima_evaluacion/`.

## Autorizaciones

Valores exactos `AUTORIZADO` cuando correspondan:

- `TC_M06_G106_AUTORIZAR_SESION`
- `TC_M06_G106_MODO`: `DIAGNOSTICO` o `FUNCIONAL`
- `TC_M06_G106_AUTORIZAR_CORRECCION` (solo funcional)
- `QA_CORREO` / `QA_CONTRASENA` (Contador)

El importe del escenario positivo está fijado en el ejecutor a `4200000.00`
conforme a la aclaración funcional. No se envía `fecha_vigencia`.

## Diagnóstico

```powershell
$env:TC_M06_G106_AUTORIZAR_SESION = "AUTORIZADO"
$env:TC_M06_G106_MODO = "DIAGNOSTICO"
python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G106/ejecutar_tc_m06_g106.py
```

Lee especie 424, umbral, precios 436 y 645. No envía el POST positivo.

## Funcional

Orden interno del ejecutor:

1. Negativo fuente distinta → 400 `CORRECCION_NO_COINCIDE`
2. Negativo fecha distinta → 400 `FECHA_VIGENCIA_CORRECCION`
3. Positivo sin `fecha_vigencia` → 201
4. Segunda corrección del 436 → 409 `PRECIO_YA_CORREGIDO`

```powershell
$env:TC_M06_G106_AUTORIZAR_SESION = "AUTORIZADO"
$env:TC_M06_G106_AUTORIZAR_CORRECCION = "AUTORIZADO"
$env:TC_M06_G106_MODO = "FUNCIONAL"
python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G106/ejecutar_tc_m06_g106.py
```

Si el POST positivo responde `DESVIACION_PRECIO_REQUIERE_CONFIRMACION`, el
ejecutor reintenta una sola vez con `confirmar_desviacion: true`. No hay más
reintentos. No se altera la base de datos fuera del API.
