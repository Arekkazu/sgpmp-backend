# README_EJECUCION.md — Guía Operativa para Ejecución de TC-M03-G165

Este documento define las instrucciones para ejecutar el caso de prueba **TC-M03-G165** (RF-62 / RF-63) cuando el equipo de QA autorice la ejecución contra el entorno desplegado de **TEST**.

---

## 1. 📋 Variables de Entorno Requeridas

Las variables deben configurarse en el entorno o en el archivo `.env.test` en la raíz del repositorio:

| Variable | Descripción | Ejemplo / Valor |
|---|---|---|
| `TEST_BASE_URL` | URL base del backend en TEST | `https://api.inmero.co/back-sigab-test` |
| `ENABLE_TEST_SANDBOX` | Habilitación de aislamiento transaccional | `true` |
| `TEST_SANDBOX_SECRET` | Secreto del middleware de testing | `[SECRETO_CONFIGURADO]` |
| `TEST_ADMIN_EMAIL` | Cuenta administrativa autorizada | `administador.dev@gmail.com` |
| `TEST_ADMIN_PASSWORD` | Contraseña administrativa de TEST | `[PASSWORD_CONFIGURADO]` |

> ⚠️ **Regla de Seguridad:** Está estrictamente prohibido usar `admin@pecuaria.co`.

---

## 2. 🚀 Comando de Ejecución Oficial

Para ejecutar la suite completa generando el reporte HTML estandarizado para el scanner:

```powershell
# Desde la raíz del repositorio sgpmp-backend:
& ".\.venv\Scripts\python.exe" -m pytest --noconftest `
  tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/test_tc_m03_g165.py `
  --html=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/resultados/resultado_TC-M03-G165.html `
  --self-contained-html `
  -v
```

### 💡 Recomendación Operativa: Primera Corrida Solo con S_BASE
Antes de ejecutar los 6 escenarios completos, se recomienda validar la conectividad, descubrimiento dinámico y rollback corriendo únicamente el escenario base:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest --noconftest `
  tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/test_tc_m03_g165.py -k "TestEscenarioBase" -v
```

---

## 3. 🔍 Supuestos "NO VERIFICADO" a Confirmar en la Primera Corrida

Durante la primera ejecución contra el entorno real de TEST se deben verificar los siguientes puntos:

1. **Enum real de `estado_evaluacion` en OpenAPI vivo**: Verificar si el schema expone un enum explícito o si permanece como `string` genérico.
2. **Ausencia de lecturas previas en la ventana del sensor**: Confirmar mediante SELECT dinámico que el sensor ambiental descubierto no tenga lecturas preexistentes en la base de datos de testing que contaminen la ventana $N=20$.
3. **Inocuidad de auditoría en `modulo1.eventos`**: Confirmar que antes y después de cada escenario el delta de filas en `modulo1.eventos` sea exactamente **0** (ningún evento de login o control persistido).
4. **Respuesta de `/test-control/query`**: Confirmar que devuelva el formato esperado `{"data": [...]}` y que vea los datos no confirmados del mismo `run_id`.
5. **Coexistencia de evaluaciones vigentes**: Confirmar si tras evaluar manualmente quedan 2 evaluaciones con `estado_evaluacion = 'VIGENTE'` para la misma lectura (la autoevaluación de la ingesta y la manual).

---

## 4. Banner Normativo D7 (`estado_evaluacion` - RESUELTO)

Al iniciar la sesión de Pytest, se imprime en consola la siguiente notificación informativa tras la resolución oficial de análisis (RFC de aclaración de RF-62 en trámite):

```text
==============================================================================
 [BANNER D7 RESUELTO] TC-M03-G165 -- ESTADO DE EVALUACION DE CALIDAD
==============================================================================
 * D7 RESUELTO: literal 'VIGENTE'; catálogo {'VIGENTE', 'SUPERADA'}; RFC de aclaración en trámite.
 * Regla canónica: máximo UNA evaluación VIGENTE por lectura.
 * Defecto conocido: /evaluar duplica VIGENTES (invariante debe fallar hoy).
==============================================================================
```

---

## 5. Defectos Probables y Discrepancias Documentadas

1. **[INC-M03-<NN>-TC-M03-G165][RF-62] POST /iot/calidad/{id}/evaluar deja mas de una evaluacion VIGENTE por lectura:**  
   Al evaluar una lectura previamente evaluada (ej. ingesta inicial), el backend no marca la evaluación anterior como `SUPERADA`. Se generan 2 evaluaciones `VIGENTE` para la misma lectura. `test_tc303_invariante_una_sola_vigente` y `test_tc303_transicion_superada` fallarán reportando este defecto reconocido por Desarrollo.
   - *OBSERVACIÓN:* El plan de pruebas indicaba el literal `ACTIVA`. La Decisión de Análisis (D7 RESUELTO) confirmó que el literal estándar y en uso es `VIGENTE`.
2. **Fase 5 de Gap Temporal Incompleta (`evaluar_calidad_telemetria_use_case.py:194-198`):**  
   No descuenta los 10 puntos de gap temporal anómalo en los escenarios 318a y 320.
3. **Incompatibilidad Outlier Estadístico con $\sigma=0$:**  
   Con 20 repeticiones idénticas, $\sigma=0$ y el código no activa outlier estadístico salvo que supere el límite físico absoluto.
