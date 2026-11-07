# Plan de restauración de umbrales (aún no ejecutable)

Fecha UTC: 2026-10-30. **No se restauró nada.** No hay copia de umbrales reales del laboratorio.

## Qué hay que restaurar

El Edge guarda umbrales RF-17 en disco y en memoria:

- Ruta por defecto: `/var/lib/sgpmp-edge/umbrales.json` (`UmbralStore` junto a `EDGE_STATE_PATH` / `config.json`).
- `UmbralStore` **carga el JSON al arrancar**. `set()` escribe disco y actualiza memoria; un `ACK_UMBRAL` OK solo sale después de ese `set()`.
- Sobrescribir el archivo **con el agente en marcha no actualiza la memoria** del proceso. Restaurar solo el fichero no basta.

## Mecanismos de consulta / respaldo (comprobados o no)

| Mecanismo | ¿Comprobado en esta fase? | Resultado |
|---|---|---|
| SSH `cat /var/lib/sgpmp-edge/umbrales.json` como `sgpmp` | Sí | Permiso denegado / no legible |
| SSH `sudo cat` del mismo archivo | No | Requiere autorización explícita de sudo |
| `GET /configuracion/umbrales?id_especie=` en TEST | Sí, sin JWT | HTTP **401** |
| Login JWT + GET umbrales | No | El POST de login puede escribir sesión; fuera de esta fase |
| MQTT `ACK_UMBRAL` / telemetría | Suscripción sí | No llegó ningún umbral ni ACK en las ventanas de 60 s |

Sin respaldo, **no hay procedimiento seguro de restauración**.

## Procedimiento exacto (cuando haya autorización; no ejecutado)

1. **Antes de cualquier E2–E6/E1 que persista umbrales:** con sudo, copiar `/var/lib/sgpmp-edge/umbrales.json` (y, si se va a tocar, `config.json`) a esta carpeta de evidencias, por ejemplo `UMBRALES_ORIGINALES.json` real.
2. Opcional paralelo: con JWT de TEST, `GET /configuracion/umbrales?id_especie=<id>` y guardar la respuesta (es la vista plataforma, **no** se demostró que coincida con el disco del Edge).
3. Ejecutar escenarios (fase posterior).
4. **Restaurar en dos capas:**
   - Disco: devolver el JSON respaldado a `/var/lib/sgpmp-edge/umbrales.json` (sudo).
   - Memoria: o bien **reiniciar** `edge-agent` (cambia estado del servicio; no se hizo ni se pide aquí), o bien **republicar** cada `UMBRAL_AMBIENTAL` original válido por MQTT/`POST /v1/commands` para que `handle_umbral` + `set()` recarguen memoria sin depender de un archivo huérfano.
5. Verificar: monitor MQTT recibe `ACK_UMBRAL` resultado OK (si se usa comando) y, con sudo, el JSON coincide con el respaldo.

## Qué escenarios escriben disco

Según `casos_rf55.json` (`origin/develop` `e618a75`) y `handle_umbral`:

- **E2, E3, E5:** el comando es inválido → `ACK_UMBRAL` ERROR → **no** hay `set()`. No deberían mutar `umbrales.json` si el firmware se comporta como el código.
- **E4:** umbral **válido** (límite 0 con bandas de ancho > 0) → **sí se guarda**. Restauración obligatoria después.
- **E1:** parte de un umbral de `frecuencia_respiratoria` presente y `temperatura_ambiente` ausente. Si se aplica por MQTT el umbral de FR o se borra el de T, hay mutación.
- **E6:** exige un umbral **incompleto ya en el store** (`umbrales_guardados`). El mismo payload por comando es E5 (ACK ERROR, no se guarda). En laboratorio eso implica escribir disco **saltando** `handle_umbral` y recargar memoria (parada/arranque o mecanismo equivalente). **No se hizo.**

## Restricciones que siguen vigentes

No sudo, no restart, no MQTT publish, no PATCH de umbrales, hasta autorización.
