# INC-M03-166-G73 — Umbral mínimo de confianza de IA para PREDICCION_PATOLOGIA (TC-M03-G73)

**RF:** RF-57, CA-2 y la regla "ALERTA: PREDICCION_PATOLOGIA" de la Fase 5 ("probabilidad ≥
umbral_confianza_minimo (configurable, valor base: 0.75)"). **Issue:** #744.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa

En `_clasificar`, la rama de PREDICCION_PATOLOGIA de IA llamaba a `_severidad_por_probabilidad`, que
devuelve LEVE para cualquier probabilidad menor que 0.85, y **no comparaba contra ningún mínimo**. Así,
cualquier `probabilidad_ia` entre 0 y 1 generaba una alerta. QA lo vio con 0.74, que creó la alerta 239.

## Solución

- **Parámetro nuevo** en el almacén de DEV-14 (`modulo4.parametros_mlops`), que el administrador carga con
  `ConfigurarParametrosMLOpsUseCase`: `rf57_umbral_confianza_minimo`, entre 0 y 1.
- **Valor:**
  - Si **no está configurado**, se usa el **valor base que publica el RF (0.75)**. Es una excepción a la
    regla de DEV-14 ("sin fallback"), porque aquí el RF fija explícitamente el valor base. Es el mismo
    criterio que las bandas base de G68.
  - Si está configurado pero es **inválido** (texto, fuera de 0–1, booleano), falla con 503
    `PARAMETRO_CONFIGURACION_INVALIDO`, como el resto de DEV-14.
- **Regla (antes de la deduplicación):** un evento con `origen_evento = IA` y
  `tipo_alerta_ia = PREDICCION_PATOLOGIA` y una probabilidad menor que el umbral, o sin probabilidad:
  - no crea alerta ni consolida;
  - responde **201** con `id_alerta: null` y el motivo, igual que las demás exclusiones de RF-57 (CA-3);
  - queda en la bitácora RF-63 como `PREDICCION_BAJO_UMBRAL_CONFIANZA`, con la probabilidad y el umbral.
- **Desde el umbral en adelante**, la severidad sigue las bandas del RF: 0.75–0.84 LEVE, 0.85–0.94
  MODERADO y ≥ 0.95 CRITICO.
- **No cambia:** el umbral de conflicto Edge vs IA (`umbral_confianza_edge_ia`, E12/E13, de 0.70 a 0.95) es
  otro parámetro y sigue igual. Los eventos que no son predicción de IA tampoco cambian.

## Cambios

- `src/configuration/domain/entities/parametro_mlops.py`: `RF57_CONFIANZA_MINIMA` y
  `RF57_CONFIANZA_MINIMA_BASE` (0.75).
- `configurar_parametros_mlops_use_case.py`: límites y validación de 0 a 1.
- `ParametrosAlertasPort.obtener_confianza_minima_ia` y su implementación en
  `ParametrosAlertasMLOpsAdapter`.
- `generar_alerta_use_case.py`: la comprobación de CA-2 antes de la deduplicación y
  `_auditar_bajo_umbral`.
- `anotaciones/modulo_9/dev14_parametros_operativos.md` y `dev14_parametros_ejemplo.json`: el parámetro
  nuevo.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_166_g73_confianza_minima_ia.py`, sin BD:
- **Adaptador:** sin configurar devuelve 0.75; configurado devuelve 0.8; con un valor inválido, 503.
- **DEV-14:** rechaza 1.2, −0.5 y `"0.8"`.
- **Caso de uso:** con 0.74, 0.7499, 0 o sin probabilidad no crea ni consolida; con 0.75 crea LEVE; los
  eventos que no son predicción no se ven afectados.

**Pruebas de integración.** `tests/integration/test_inc_m03_166_g73_confianza_minima_ia.py`: router real y
PostgreSQL real.

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_prediccion_bajo_el_valor_base_no_genera_alerta` | Caso de QA: 0.74, sin configurar | 201 sin alerta; `PREDICCION_BAJO_UMBRAL_CONFIANZA` con 0.74 y 0.75 |
| `test_prediccion_en_o_sobre_el_umbral_genera_alerta[0.75/0.85/0.95]` | En el umbral y por encima | LEVE, MODERADO y CRITICO |
| `test_umbral_configurado_prevalece_sobre_el_valor_base` | Umbral configurado en 0.80 | 0.78 sin alerta; 0.80 con alerta |
| `test_umbral_configurado_invalido_falla_expresamente` | Valor `"alto"` | 503 `PARAMETRO_CONFIGURACION_INVALIDO`, sin alerta |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g73_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G73 + DEV-14, DEV-41, DEV-49, DEV-13, DEV-30)                  141 passed
Integración (G73 + DEV-14, DEV-30, DEV-41, DEV-49, DEV-17)                89 passed, 6 skipped
Suite completa (sin red): 2279 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Nota de integración

Esta rama sale de `dev` y no depende de la cadena G68 → G70 → G71. Toca `generar_alerta_use_case.py` en
otra zona (justo antes de la deduplicación), así que al unir las ramas lo esperable es que solo choquen las
filas de la tabla de seguimiento y algún import. Se resuelve conservando los dos lados.

## Para QA

- **Volver a ejecutar TC-M03-G73:** 0.74 no genera alerta y 0.75 sí.
- **Cambiar el umbral:** se carga `rf57_umbral_confianza_minimo` con la configuración de parámetros de DEV-14.
