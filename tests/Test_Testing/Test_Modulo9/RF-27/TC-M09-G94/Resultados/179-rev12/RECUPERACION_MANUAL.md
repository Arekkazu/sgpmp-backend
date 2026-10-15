# Recuperación manual — TC-M09-179 rev12

Usar **solo** si Cypress se interrumpe o existe `G94-rev12-179-RESTORE-PENDIENTE.json`. No forma parte de la corrida automatizada. **No** reintentar en bucle. No pegar JWT ni contraseñas en este archivo.

Ubicación de evidencias (cwd `sgpmp-backend`):

`tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/`

| Archivo | Uso |
|---|---|
| `G94-rev12-179-paquete-recuperacion.json` | Valores de restore. Exigir `snapshot_valido: true`. Si falta el archivo o `snapshot_valido` es false: **no escribir**. |
| `G94-rev12-179-snapshot-identidad.json` | Copia del GET original |
| `G94-rev12-179-RESTORE-PENDIENTE.json` | Fallo de restore automático |

Base API TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`

Estímulo de esta prueba: `primary_color=#FFFFFF`, tema productor `theme_mode=1` (si se modificó).

## 1. Identidad finca 1 (admin, recurso 23)

1. `POST /sesiones/` con `admin@pecuaria.co` (login nuevo).
2. `GET /configuracion/identidad-visual/1`.
3. Comparar con el paquete (`snapshot_valido` debe ser true):
   - Si primary, secondary, org y `logo_path` **ya coinciden** con el snapshot: no PATCH.
   - Si `primary_color` es `#FFFFFF` (estímulo): **un** PATCH multipart **sin** `logo`, campos del snapshot, `version` del GET **vigente**. Luego GET de comprobación.
   - Si no es ni snapshot ni `#FFFFFF`: **detener**. Otro cambio concurrente; no sobrescribir.
4. HTTP 401 o 412: detener. 412 = concurrencia; recargar GET y decidir con un humano. No reenviar el mismo `version`. No bucle.
5. Tras un restore exitoso, `id_usuario` de la fila puede ser el admin que restauró. Eso es el use case, no un fallo de colores.

## 2. Tema personal del productor (recurso 24)

1. `POST /sesiones/` con `productor@pecuaria.co` (login nuevo).
2. `GET /configuracion/personalizacion/tema`.
3. Si `theme_mode` ya es el del snapshot: no PATCH.
4. Si es `1` (claro del estímulo) y el snapshot era otro: **un** PATCH JSON `{ "theme_mode": <snapshot> }` y GET de confirmación.
5. Si no es ni snapshot ni 1: detener (cambio concurrente). 401: detener; no reusar token del SPA.

## 3. Qué no hacer

- No PATCH a otras fincas ni `/tema/global`.
- No enviar `logo` vacío. Omitir el campo conserva el logo.
- No interpretar 401 como éxito.
- No restaurar “a ciegas” si el GET vigente no parece el estímulo de rev12.
