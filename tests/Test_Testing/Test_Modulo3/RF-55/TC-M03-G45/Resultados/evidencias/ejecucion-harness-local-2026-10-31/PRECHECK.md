# Precheck — ejecución local harness G45

Fecha UTC: 2026-10-31 (corrida local, no Raspberry).

## Archivos

| Archivo | Presente |
|---|---|
| `harness-propuesto-2026-10-31/harness_g45.py` | sí |
| `harness-propuesto-2026-10-31/escenarios_p1_p4.json` | sí |

## Condiciones de seguridad (inspección estática)

| Condición | Cumple |
|---|---|
| `Agent` real (`from edge_agent.agent import Agent`) | sí |
| `lecturas_invalidas` real | sí |
| Almacenamiento `tempfile.TemporaryDirectory(prefix="g45-harness-")` | sí |
| `FakeLink.publish` solo lista en memoria | sí |
| `paho` / `socket.connect` / broker TEST | no hay llamadas |
| Escritura `/var/lib/sgpmp-edge` | no |
| `systemctl` / SSH | no |
| `mqtt_host` en `Settings` | solo campos del dataclass; el link no conecta |

Se autorizó la ejecución local. No se modificó el script (tampoco tras el error).
