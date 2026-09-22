# TC-M09-G128 (RF-23) - Ataques al protocolo LoRaWAN - BLOQUEADO (sin reporte a proposito)

Fecha: 2026-09-22 - Ambiente de referencia: DEV

## Casos
- TC-M09-254: reenviar un join-request capturado (mismo DevNonce) y verificar el rechazo anti-replay.
- TC-M09-255: verificar que las claves de sesion (AppSKey/NwkSKey) de >= 3 dispositivos no se repiten ni son predecibles.

## Por que no se ejecuta
Ambos sub-casos son propiedades de un **servidor de red LoRaWAN** (ChirpStack u otro): el join procedure y la
generacion de claves de sesion ocurren ahi. Evidencia de que el sistema SGPMP no incluye ninguno:
- `src/`, `alembic/` y `anotaciones/` no contienen ningun cliente, adaptador ni configuracion LoRaWAN/ChirpStack
  (unica mencion: el header opcional `X-Gateway-Id` de la ingesta de telemetria, solo para trazabilidad).
- La configuracion remota (RF-23) solo existe por MQTT via BROKER-MQTT-SGPMP; el campo `protocolo` no existe en el
  contrato y se ignora (ver TC-M09-G69, sub-caso 132: `protocolo="LoRaWAN"` y `"PROTOCOLO_INEXISTENTE"` dan el mismo 202).
- No hay endpoint ni servicio donde inspeccionar un join-request o una clave de sesion.

Levantar un ChirpStack propio con Docker probaria ese software, no al sistema bajo prueba: seria una prueba parcial
que da falsa confianza (el plan de pruebas pide declarar estos casos "FUERA DE STACK" en vez de improvisarlos).

## Que haria falta para ejecutarlo
Una decision del equipo: (a) confirmar que RF-23 debe soportar LoRaWAN y con que servidor de red, y entregar acceso
al join server / logs de ese servidor; o (b) declarar TC-M09-254/255 fuera de alcance del sistema.

## Estado propuesto
Pendiente (sin reporte). Registrar en Taiga solo si el equipo confirma que LoRaWAN es requisito (entonces el
defecto es el de TC-M09-G69 sub-caso 132: ausencia de soporte).
