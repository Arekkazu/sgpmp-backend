# Reintento de conexión — Raspberry laboratorio (TC-M03-G45)

Fecha: **2026-10-31** 02:54–02:55 hora local (UTC−5); sondas **07:54–07:55 UTC**.  
Alcance: diagnóstico de red y SSH. **Sin** mediciones P1–P4, **sin** MQTT publish, **sin** cambios de configuración, **sin** reinicios, **sin** Git.

Resultado: **SSH no establecido.**

---

## 1. VPN / red

| Comprobación | Resultado |
|---|---|
| CLI Tailscale | presente |
| Backend Tailscale (esta estación) | `Running`, nodo `Laura`, IP `100.99.91.44`, `Online: true` |
| Adaptador | `Tailscale` **Up** (`Tailscale Tunnel`) |
| Otras interfaces Up | Wi-Fi; VirtualBox Host-Only |
| Resolución de `100.96.29.65` | MagicDNS `raspberry3b.tail685cf2.ts.net` |
| Peer `raspberry3b` (`100.96.29.65`) | Linux; relay `mia`; **offline**; last seen ~14 min antes de esta sonda; `tx 780 rx 0` |
| `tailscale ping 100.96.29.65` (3 intentos, timeout 5 s) | **timed out / no reply** |
| `tailscale ping raspberry3b.tail685cf2.ts.net` | **timed out / no reply** |

La VPN **de este PC está conectada**. El peer de la Raspberry **no está en línea** en Tailscale, así que el túnel no llega al puerto 22.

---

## 2. TCP puerto 22

| Destino | Puerto | Resultado | Tiempo |
|---|---|---|---|
| `100.96.29.65` | 22 | **timeout** (`TimeoutError: timed out`) | 5003 ms |
| `100.96.29.65` | 41641 (WireGuard Tailscale) | **timeout** | 5004 ms |
| `192.168.40.5` (LAN histórica) | 22 | **connection refused** (`WinError 10061`) | 2720 ms |
| `192.168.40.5` | 1886 | **connection refused** (`WinError 10061`) | 2698 ms |

`192.168.40.5` responde con RST: hay *algún* equipo en esa IP o un filtro, **no** un SSH aceptando conexiones. No se asume que sea la Raspberry.

---

## 3. Intentos SSH (`sgpmp`)

Autenticación **no se llegó a negociar**: el TCP no abre. No se pidió contraseña (no habría banner). No hay clave privada de usuario en `~/.ssh` (solo `known_hosts`). No se imprimieron secretos.

| Destino | Error exacto | Exit |
|---|---|---|
| `sgpmp@100.96.29.65` | `ssh: connect to host 100.96.29.65 port 22: Connection timed out` | 255 |
| `sgpmp@raspberry3b.tail685cf2.ts.net` | `ssh: connect to host raspberry3b.tail685cf2.ts.net port 22: Connection timed out` | 255 |
| `sgpmp@192.168.40.5` | `banner exchange: Connection to UNKNOWN port -1: Connection refused` | 255 |

No es `Permission denied` (eso requeriría llegar al demonio sshd).

---

## 4. Comprobaciones en el nodo (no ejecutadas)

Sin sesión SSH:

| Dato | Estado |
|---|---|
| hostname | no leído |
| `edge-agent` | no leído |
| servicio SSH en la Pi | no leído |
| historial local | no consultado |

---

## 5. Qué impidió la conexión

1. **Causa principal:** el nodo Tailscale `raspberry3b` (`100.96.29.65`) figura **offline** (último visto ~14 min). Ping Tailscale sin respuesta → TCP/SSH **timeout**.
2. **LAN histórica `192.168.40.5:22`:** **connection refused**; no es un camino SSH usable y no se confirma que sea la Pi.
3. Esta estación **sí** tiene Tailscale activo; el fallo no es “VPN local caída”.

Para un tercer intento: la Raspberry debe volver a aparecer **online** en `tailscale status` (peer `raspberry3b`) y responder `tailscale ping`. Entonces sí se puede autenticar `sgpmp` y leer hostname / `edge-agent` / historial, todavía sin P1–P4.
