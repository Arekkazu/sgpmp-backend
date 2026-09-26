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

## Actualizacion 2026-09-26 - confirmado con acceso real, sigue sin poder ejecutarse
El usuario proveyo credenciales reales de un gateway (`sgpmp_gateway`) y el serial de una Raspberry Pi realmente
activa (`TC-M09-G64-1789321890010`). Se uso ese acceso para TC-M09-G69/G127 (ver sus reintento2/3): confirma en
vivo que **todo el tráfico real observado es MQTT** -- topicos `sgpmp/<serial>/command` y `sgpmp/<serial>/status`,
sin ningun join-request, DevNonce ni clave de sesion LoRaWAN en ningun punto. La credencial del "gateway" autentica
contra el mismo broker Mosquitto (puertos 1884/9001), no contra un servidor de red LoRaWAN. Esto no abre ninguna
via nueva para TC-M09-254/255: siguen siendo propiedades de un protocolo que este sistema, ni siquiera con
hardware real de por medio, implementa. La nota y el estado Pendiente se mantienen sin cambios.
