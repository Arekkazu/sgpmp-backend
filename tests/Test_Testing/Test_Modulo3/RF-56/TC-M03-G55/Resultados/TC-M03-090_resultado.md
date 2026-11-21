# TC-M03-090 (dos funciones del lote de 7) — resultado

Fecha de esta corrida: 2026-10-25T15:23:33-05:00. Distinta de la previa de 1.03s.

## 1. ID y nombre

**TC-M03-090** — consolidación de paquete RF-56.  
Funciones ejecutadas:

- `test_tc_m03_090_error_configuracion_consolida_si_se_invoca_directo`  
- `test_tc_m03_090_normal_no_genera_paquete`

El resto de G55 (estructura, mapeo puerto, inconsistente, 091, 092) **no** forma parte de esta corrida.

## 2. RF y CU

**RF-56 / CU-02.** Comentario del script: consolidar omite `NORMAL`; `Recibir` no llama consolidar para `ERROR_CONFIGURACION` (FA-07 / G59).

## 3. Objetivo

1. Si se invoca consolidar **directo** con `ERROR_CONFIGURACION`, sí hay paquete.  
2. `NORMAL` no genera paquete ni llama motor.

## 4. Precondiciones

`ConsolidarEnviarPaqueteUseCase` + `PaqueteInferenciaRepoMemoria` + `MotorObservado(exito=False)`.

## 5. Pasos

pytest `--noconftest` en el lote de 7.

## 6–7. Esperado vs obtenido

Ambas funciones **PASSED**.

## 8. Estado

**PASSED** estos dos tramos. G55 completo **no** se declara aprobado (091/092 siguen skip en el archivo; no reejecutados aquí).

## 9. Entorno

7 passed in 0.98s, EXIT=0.

## 10. Evidencias

- `Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.log`  
- `Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.html`  
- `Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.xml`

## 11. Limitaciones

`MotorObservado` no es ACK M04. Este PASSED no es clasificación Edge.
