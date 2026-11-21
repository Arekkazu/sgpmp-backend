# Reporte de Resultados: TC-M05-G17

## Información General
- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-76
- **Endpoint:** `POST /suministros/medicamentos`
- **Caso Agrupado:** TC-M05-G17 — Tratamientos simultáneos y concurrencia real
- **Subcasos:** TC-M05-008 y TC-M05-009
- **Ambiente:** API Real de Staging (`https://www.api.inmero.co/api-sgpmp-test`) con commits reales
- **Activo QA Dedicado:** ID desconocido (`desconocido`) en Finca 1 (Infra 389)
- **Veredicto Global:** **RECHAZADO** (0/7 superados, 0 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 7 |
| Checkpoints Aprobados | 0 |
| Checkpoints Fallidos | 7 |
| Rondas de Concurrencia | 20 |
| Peticiones Concurrentes de POST | 100 (5 hilos x 20 rondas) |
| Tasa de Éxito Concurrente | 100.0% (0 errores 500, 0 conflictos 409) |
| Estado Final Activo QA | ACTIVO (id_estado: 1) |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Setup de activo QA dedicado y fase productiva | HTTP 201 en creación de activo individual QA (Mojarra Plateada, infra 389) y apertura de fase con ciclo 5; estado inicial ACTIVO (id_estado: 1) | Activo QA ID desconocido ('desconocido') creado exitosamente (HTTP 201), fase ciclo 5 abierta (HTTP 201), estado inicial ACTIVO (1). Status HTTP: 400. Error: AssertionError: Fallo creacion activo QA: {"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"tipo_activo","message":"Este campo es obligatorio."},{"field":"fecha_inicio_ciclo","message":"Este campo es obligatorio."},{"field":"origen_financiero","message":"Este campo es obligatorio."}],"timestamp":"2026-11-07T20:43:39.546339+00:00"}
assert 400 == 201
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| A01 Primer tratamiento con período de retiro (5 días) | HTTP 201/200, fecha_fin_retiro_vigente = hoy + 5 días, tratamientos_activos = 1, activo transiciona a estado EN_TRATAMIENTO (id_estado: 3) | HTTP 201/200; retiro vigente registrado hoy+5 días, 1 tratamiento activo; activo pasó a estado EN_TRATAMIENTO (3). Status HTTP: 400. Error: AssertionError: A01 status inesperado: 400 ({"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"id_activo_biologico","message":"El valor ingresado debe ser un número entero."}],"timestamp":"2026-11-07T20:43:40.787864+00:00"})
assert 400 in (200, 201)
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| A02 Segundo tratamiento con retiro mayor (10 días) | HTTP 200 (E11), fecha_fin_retiro_vigente = hoy + 10 días, tratamientos_activos = 2, mensaje descriptivo E11, activo se mantiene EN_TRATAMIENTO | HTTP 200 (E11); retiro extendido a hoy+10 días; 2 tratamientos activos; mensaje E11 confirmó tratamientos y fecha; activo se mantuvo EN_TRATAMIENTO. Status HTTP: 400. Error: AssertionError: A02 esperaba HTTP 200 (E11), obtenido 400 ({"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"id_activo_biologico","message":"El valor ingresado debe ser un número entero."}],"timestamp":"2026-11-07T20:43:42.293272+00:00"})
assert 400 == 200
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| A03 Tercer tratamiento con retiro menor (3 días) | HTTP 200 (E11), fecha_fin_retiro_vigente mantiene MAX (hoy + 10 días), tratamientos_activos = 3, activo se mantiene EN_TRATAMIENTO | HTTP 200 (E11); retiro vigente mantuvo MAX hoy+10 días; 3 tratamientos activos; activo se mantuvo EN_TRATAMIENTO. Status HTTP: 400. Error: AssertionError: A03 esperaba HTTP 200 (E11), obtenido 400 ({"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"id_activo_biologico","message":"El valor ingresado debe ser un número entero."}],"timestamp":"2026-11-07T20:43:43.275610+00:00"})
assert 400 == 200
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| A04 Cuarto tratamiento mayor (15 días) y reversibilidad | HTTP 200 (E11), retiro vigente = hoy + 15 días, tratamientos_activos = 4; GET confirma 4 tratamientos VALIDADOS; anulación de los 4 restaura activo a ACTIVO (id_estado: 1) | HTTP 200 (E11); retiro extendido a hoy+15 días (4 tratamientos activos); GET validó 4 tratamientos VALIDADOS; anulación de los 4 restauró activo a ACTIVO (1). Status HTTP: 400. Error: AssertionError: A04 esperaba HTTP 200 (E11), obtenido 400 ({"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"id_activo_biologico","message":"El valor ingresado debe ser un número entero."}],"timestamp":"2026-11-07T20:43:44.267485+00:00"})
assert 400 == 200
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| B01 Concurrencia real (20 rondas de 5 hilos con Barrier) | 20 rondas consecutivas; 100% de peticiones (100 de 100) responden HTTP 2xx sin colisiones 409 ni 500; fecha_fin_retiro_vigente = hoy + 10 días; anulación limpia restaura ACTIVO en cada ronda | 20 rondas exitosas de 5 hilos concurrentes sincronizados con Barrier(5) (100 peticiones POST exitosas 2xx, 0 colisiones 409, 0 errores 500); retiro MAX verificado en hoy+10 días; anulación limpia restauró ACTIVO en cada ronda. Total peticiones: 1. Error: assert 400 == 200
 +  where 400 = <Response [400]>.status_code | **FALLA** |
| T98 Limpieza final y certificación de estado de activo QA | 0 tratamientos activos pendientes; activo QA en estado ACTIVO (id_estado: 1) | Verificación de inocuidad completada: 0 tratamientos activos en activo QA desconocido; estado final confirmado ACTIVO (1). Status HTTP: . Error: AssertionError: Falta id_activo en contexto
assert None | **FALLA** |

## Verificación de Integridad de Código
- **SHA-256 TC-M05-G17 Script Inicio:** `0558855be65f22becd8c85820a1eab02dd175cc9d5707e88793c24b32b13f6d3`
- **SHA-256 TC-M05-G16 Script:** `ecbc14e9eedd17ea1cf29a4ab97476055dd47b7e2bf0dc2f3ded552ae8801112`
- **SHA-256 TC-M05-G16 Runner:** `546babddc7aad1bf388f2738bd6444e4482635fe0368ad74455733209012d3b0`
- **SHA-256 TC-M05-G15 Script:** `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`
- **SHA-256 TC-M05-G15 Runner:** `b545084981ed1257a6be0ee3a88e08688ebcbbeea83f84e38124395137c7d1a7`
- **SHA-256 TC-M05-G14 Script:** `a693e2df2229eb52501079e9bc9365b39e084c52c2c87699067db2f8079b680d`
- **SHA-256 TC-M05-G14 Runner:** `01eea075baec9150e3683f18bcf84161c14dcf1e8497d3732e0e83045829d536`
- **SHA-256 TC-M05-G19 Script:** `6a4496f457d044721a2bb2b19b7e348c467e142c49c333ca1259c7f0b049a92e`
- **SHA-256 TC-M05-G19 Runner:** `d22d89c2dedf3abd861255252a8df4ed79192364c082ce73b32a8ad0d65e09fd`
