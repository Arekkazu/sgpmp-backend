# Fase 1 — detención (laboratorio 2026-10-31)

UTC de la sonda SSH: 2026-10-31T07:39:11Z (timeout).
UTC de la sonda TCP: 2026-10-31T07:42:19Z.

No se enviaron lecturas P1–P4. No se publicó MQTT. No se reinició `edge-agent`. No se modificó configuración.

| Destino | Puerto | Resultado |
|---|---|---|
| `100.96.29.65` (SSH histórico `sgpmp@RASPBERRY3B`) | 22 | Timeout |
| `192.168.40.5` (LAN histórica de la Pi) | 22 | Connection refused |
| `149.130.169.209` (broker TEST G38/G41) | 1886 | TCP abierto |
