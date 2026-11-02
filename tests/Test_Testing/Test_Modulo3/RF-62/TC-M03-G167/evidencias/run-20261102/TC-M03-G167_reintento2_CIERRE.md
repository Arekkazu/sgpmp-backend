# TC-M03-G167 — Reintento 2 (2026-11-02)

## Ambiente
- **URL:** https://www.api.inmero.co/api-sgpmp-test
- **Sensor:** 536 (`QA-SEMILLA-ADM-M03-CAL-01`)
- **Dispositivo:** 346 | **Área:** 347
- **Calibración BD:** id=39, offset=-3.0, ganancia=1.0, ref=25.0
- **Producto en HEAD local:** fix #876 (`ea6ec4bf`)
- **Producto desplegado en TEST:** versión anterior sin despliegue de #876 (despliegue pendiente)

## Resultado
- **Duración:** 15.55 s
- **Requests ejecutados:** 32 / 32
- **Checkpoints:** 23 / 32 OK (9 fallas)
- **Veredicto computado:** **RECHAZADO** (RECHAZADO_POR_PRODUCTO / DESPLIEGUE_PENDIENTE)

## Escenarios
| Escenario | Drift nominal | Drift esperado | Drift obtenido | Activo | Índice | Clasificación | NIC41 | Estado |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1A** | 5.00% | 5.0000% | 11.4286% | `true` (esp: `false`) | 75 (esp: 100) | APTO_CON_RESERVA (esp: APTO) | false (esp: true) | ❌ |
| **1B** | 7.00% | 7.0000% | 11.2150% | `true` | 75 (esp: 90) | APTO_CON_RESERVA (esp: APTO) | false (esp: true) | ❌ |
| **1C** | 9.99% | 9.9900% | 10.9101% | `true` | 75 (esp: 90) | APTO_CON_RESERVA (esp: APTO) | false (esp: true) | ❌ |
| **2A** | 10.00% | 10.0000% | 10.9091% | `true` | 75 | APTO_CON_RESERVA | false | ❌ |
| **2B** | 15.00% | 15.0000% | 10.4348% | `true` | 75 | APTO_CON_RESERVA | false | ❌ |
| **3A** | 20.01% | 20.0100% | Omitido (RF-53) | N/A | 0 (esp: 60) | NO_APTO (esp: APTO_CON_RESERVA) | false | ❌ |
| **3B** | 25.00% | 25.0000% | Omitido (RF-53) | N/A | 0 (esp: 60) | NO_APTO (esp: APTO_CON_RESERVA) | false | ❌ |

## Detalle de Fallas Detectadas

1. **Discrepancia de fórmula de Drift en el backend desplegado:**
   - El endpoint desplegado calcula la deriva con la fórmula pre-#876:
     $$\text{magnitud} = \frac{|\text{mean(crudo)} - \text{mean(calibrado)}|}{\text{mean(calibrado)}} \times 100 = \frac{|29.25 - 26.25|}{26.25} \times 100 = 11.4286\%$$
   - En lugar de la fórmula introducida en commit `ea6ec4bf` (Fix #876 / INC-M03-236-G16):
     $$\text{magnitud} = \frac{|\text{mean(calibrado)} - \text{referencia}|}{\text{referencia}} \times 100 = \frac{|26.25 - 25.0|}{25.0} \times 100 = 5.0000\%$$
   - El campo `base_comparacion: "VALOR_REFERENCIA"` introducido por #876 **no aparece** en ninguna de las respuestas del servidor remoto, confirmando que el fix #876 **no ha sido desplegado** al contenedor de TEST.

2. **Intercepción de RF-53 en Escenarios 3A y 3B (`FUERA_DE_RANGO`):**
   - Para 3A ($\bar{X}=33.0025$) y 3B ($\bar{X}=34.25$), el valor ajustado supera los 30.0 °C (umbral operativo biológico de la especie asignada en el área).
   - El trigger `fn_ingesta_telemetria` marca las telemetrías como `FUERA_DE_RANGO`.
   - La regla RF-62 CA-9 fuerza `indice_calidad = 0`, `clasificacion = NO_APTO` y omite todas las fases estadísticas.

3. **Inconsistencia de nombrado en Bitácora RF-63 (3B):**
   - En `3B.05`, `componente_origen` devolvió `'RF62'` en lugar de `'RF-62'`.

## Archivos de Resultados
- `resultado_TC-M03-G167_reintento2.json` (SHA256: `61d98a9910fa55d38d474e6f58c93904ce8dbd8a33625639c838f92c505ab260`)
- `resultado_TC-M03-G167_reintento2.html` (SHA256: `e6f529b32ac80e2e55337915ad7f2d3fe68e89ad8f538ca10c3f2fbb8427472a`)
- `_raw_newman_reintento2.json` (SHA256: `d9030f98d30c556e18b4528834daaa4c3a03f69909c202bcd5dc6d77a8f7000a`)

## Archivos Archivados
- `evidencias/run-20261102_reintento2_previo/CLASIFICACION.md`

## INCs
- Se registra defecto de producto / despliegue:
  `[INC-M03-248-G167][RF-62] Backend en TEST no tiene desplegado el fix #876 (drift calcula crudo vs calibrado sin referencia)`

## Próximo Paso
- Escalar a DevOps/Desarrollo el reporte del Reintento 2 para que se ejecute el pipeline de despliegue en TEST del commit `ea6ec4bf` (Fix #876).

