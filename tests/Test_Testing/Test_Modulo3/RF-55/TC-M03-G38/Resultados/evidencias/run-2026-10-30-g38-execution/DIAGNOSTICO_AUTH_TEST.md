# Diagnóstico de autenticación TEST — G38 E2/E3/E5

Fecha UTC: 2026-10-30. **Ningún POST. Ningún PUBLISH MQTT. E6 no ejecutado.** Sin lectura de valores de token. Sin `BROKER_SERVICE_TOKEN` como sustituto.

## Credencial TEST disponible: **no**

| Origen | `MQTT_BROKER_TOKEN` | `BROKER_SERVICE_TOKEN` |
|---|---|---|
| Proceso | UNSET | UNSET |
| User Windows | UNSET | UNSET |
| Machine Windows | UNSET | UNSET |
| `MQTT_BROKER_URL` proceso | UNSET | — |

`.env.example` nombra las dos variables por separado; **no** se abrió `.env` ni se listaron secretos. En la Pi, el intento anterior ya había mostrado que el Edge **no** guarda `MQTT_BROKER_TOKEN`; no se volvió a buscar.

No hay forma, en este entorno, de afirmar que exista un Bearer **autorizado para TEST**.

## Mecanismo seguro de autenticación: **sí** (preparado, no usado)

- `ejecutar_e2.ps1 -Enviar`: cuadro `Get-Credential` con usuario `MQTT_BROKER_TOKEN`; el secreto va por tubería a Python y se anula; no se escribe a disco.
- `ejecutar_g38_e2_e3_e5.ps1`: rechaza usar `BROKER_SERVICE_TOKEN` si estuviera definido; **no** abre el cuadro; con `-Enviar` se detiene si `MQTT_BROKER_TOKEN` no está en el proceso (no hay POST automático).

El canal de producto sigue siendo `POST` al broker TEST `…sslip.io/v1/commands` con Gateway `RASPBERRY3B-TEST`.

## Requisitos pendientes

1. Entregar el Bearer **TEST** en el cuadro seguro (o User env `MQTT_BROKER_TOKEN`), no `BROKER_SERVICE_TOKEN`.
2. Confirmación de que ese Bearer es el del broker TEST.
3. Monitor MQTT vivo en el momento de cada POST.
4. Releer version/hash del umbral 65 antes de cada escenario.

Hasta entonces E2, E3 y E5 **no se pueden continuar como ejecución**.

## Comandos enviados

**Ninguno.**
