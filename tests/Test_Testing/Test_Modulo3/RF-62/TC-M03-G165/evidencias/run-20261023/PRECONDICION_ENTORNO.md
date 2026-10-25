# Precondiciones de entorno â€” TC-M03-G165

**Caso:** TC-M03-G165 â€” Disparo de evaluaciÃ³n puntual y cÃ¡lculo del Ã­ndice de calidad (RF-62)
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`
**Fecha de corrida definitiva:** 2026-10-23
**run_id asociado:** `test-run-3d455a54-74d5-4485-bbbd-066f7f9e9eac`

## Precondiciones verificadas al inicio de la corrida

### P1 â€” ConfiguraciÃ³n de parÃ¡metros del motor de calidad (RF-62)

El endpoint `POST /iot/calidad/{id_telemetria}/evaluar` depende de la configuraciÃ³n de parÃ¡metros del motor de calidad en la tabla `modulo4.parametros_mlops`. Si cualquiera de los parÃ¡metros `rf62_*` no estÃ¡ configurado, el backend responde:
```text
HTTP 503 PARAMETRO_CONFIGURACION_AUSENTE: No se ha configurado el parÃ¡metro rf62_<nombre>.
```

**VerificaciÃ³n al inicio de la corrida:**

| ParÃ¡metro | Valor verificado |
|---|---|
| `rf62_k` (multiplicador kÂ·Ïƒ para outlier estadÃ­stico) | 3 |
| `rf62_m` (ventana de repeticiones para sensor congelado) | 5 |
| `rf62_n` (tamaÃ±o de serie base histÃ³rica) | 20 |
| `rf62_p` (ventana reciente para detecciÃ³n de drift) | 5 |
| `rf62_umbral_drift` (umbral porcentual de drift admisible) | 5.0 |

**Estado:** los 5 parÃ¡metros presentes al momento de la corrida. `POST /iot/calidad/{id}/evaluar` respondiÃ³ con cÃ³digo distinto de 503 en la verificaciÃ³n previa, confirmando que el motor de calidad estaba operativo.

**Valores de referencia segÃºn especificaciÃ³n:** `spec_tc_m03_g165.py` define N=20, M=5, k=3, P=5, umbral_drift=5% como valores canÃ³nicos para la validaciÃ³n de las fÃ³rmulas del Ã­ndice y clasificaciÃ³n.

### P2 â€” AsociaciÃ³n sensor-Ã¡rea del sensor bajo prueba

El sensor 6 requiere una asociaciÃ³n activa con su infraestructura para que `calibrar_sensor` funcione (si no, el backend responde `SENSOR_AREA_INVALIDA`).

**VerificaciÃ³n al inicio de la corrida:**

- Sensor `id_sensores=6` asociado a `id_infraestructura=1` con `tiene_estado=true`.
- Dispositivo IoT asociado: `id_dispositivo_iot=3`, serial `IOT-ALE01-HLA-003`.

**Estado:** asociaciÃ³n activa presente al momento de la corrida.

### P3 â€” Variables de entorno del runner

| Variable | Presente |
|---|---|
| `TEST_BASE_URL` | sÃ­ |
| `TEST_ADMIN_PASSWORD` | sÃ­ |
| `TEST_SANDBOX_SECRET` | sÃ­ |
| `BROKER_SERVICE_TOKEN` | sÃ­ (necesario para `POST /iot/telemetria` desde los tests) |

### P4 â€” Seed de evaluaciones preexistentes

Para los subcasos que dependen de evaluaciones `SUPERADA` u otra data preexistente, el seed del ambiente TEST (aplicado por la DBA el 2026-10-22) proveyÃ³ las filas necesarias. La corrida consumiÃ³ estas filas en modo lectura.

## Observaciones

- Si cualquiera de las precondiciones P1â€“P4 no se cumple en una futura re-ejecuciÃ³n, la suite fallarÃ¡ con errores de infraestructura (no de lÃ³gica de negocio). En ese caso, el veredicto correcto es **bloqueado por ambiente**, no **rechazado por defecto funcional**.
- Los scripts de verificaciÃ³n disponibles son `check_zeropollution.py` (verifica cero contaminaciÃ³n tras la corrida) y las funciones de `helpers_tc_m03_g165.py`.

---

*Este documento describe el estado del ambiente al momento de la corrida definitiva. No narra el proceso de preparaciÃ³n del entorno.*