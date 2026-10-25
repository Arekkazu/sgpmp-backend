# INC-M01-24-500-nombre-rol — Evidencia v2.0 (2026-09-13)

## Resumen

`POST /roles/` responde **HTTP 500 `ERROR_INTERNO`** (en vez de 201, o un
4xx controlado) cuando `nombre_rol` **empieza exactamente** con la cadena
`"Auxiliar de Campo"` (mayúsculas y un solo espacio, tal como se usaba el
rol semilla original de INC-M01-03-119, `id_rol=10`, ya eliminado).

**Reproducido 10/10 veces** contra `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`,
con `admin.dev@gmail.com`, usando tanto `curl` como el módulo `requests` de
Python en scripts sueltos (no vía `pytest`), incluyendo:

- 4 intentos consecutivos con distintos sufijos.
- 3 intentos con re-login completo entre cada uno (token nuevo cada vez).
- 3 intentos **intercalados** con nombres de control (`Auxiliar de Campo
  interleave1/2/3` → 500; `Control Role interleave1/2/3` → 201), en la misma
  sesión, para descartar que fuera un problema de temporización o de un
  reemplazo de réplica de backend.

## Aislamiento por nombre (2026-09-13, mismo token, mismo minuto)

| `nombre_rol` | Resultado |
|---|---|
| `Auxiliar de Campo <sufijo>` | **500** |
| `Auxiliar de Campo` (exacto) | **500** |
| `auxiliar de campo <sufijo>` | 201 |
| `AUXILIAR DE CAMPO <sufijo>` | 201 |
| `Auxiliar de Camp <sufijo>` (un carácter menos) | 201 |
| `Auxiliar  de Campo <sufijo>` (doble espacio) | 201 |
| `xAuxiliar de Campo <sufijo>` (con prefijo) | 201 |
| `Auxiliar <sufijo>` / `Campo <sufijo>` (por separado) | 201 |

Conclusión del aislamiento: es sensible a mayúsculas/minúsculas y al
espaciado exacto — apunta a una comparación de string exacta en algún
punto (constraint, índice parcial o trigger), no a un filtro de contenido
genérico ni a una expresión regular laxa.

## Transacción de ejemplo (reproducción vía Python `requests`, fuera de pytest)

```
POST /roles/
Authorization: Bearer <token admin.dev@gmail.com>
Content-Type: application/json

{"nombre_rol": "Auxiliar de Campo pyverify 1789325846185", "descripcion": "pyverify", "permisos": [{"id_recurso": 1, "id_accion": 2}]}
```

```
HTTP 500
{"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.","fields":[],"timestamp":"2026-09-13T18:57:26.727543+00:00"}
```

## ⚠️ Anomalía sin explicar — evidencia no viene del script automatizado

El script `repro_defecto_nombre_auxiliar_de_campo.py` de esta misma carpeta,
que ejecuta la **misma lógica exacta** (mismo endpoint, mismo payload, mismo
usuario), **no reproduce el 500 cuando se corre a través de `pytest`** — pasó
3/3 veces. Al extraer el mismo código a un script suelto (`python
probe_direct.py`, sin pytest) y ejecutarlo inmediatamente después de una
corrida de pytest exitosa, **sí reprodujo el 500**. Se descartaron como causa:

- Diferencia curl vs. `requests` (ambos fallan igual).
- Reutilización de token vs. login fresco (ambos fallan igual; se probó con
  3 logins nuevos consecutivos, 3/3 con 500).
- Retraso antes de la petición (se probó con 5 s de espera tras el login;
  siguió en 500).

No se identificó la causa de por qué específicamente la invocación vía
`pytest` evita el error. Por eso **esta evidencia no se reporta como
"reproducido con pytest-html"**: se documenta aquí, con las transacciones
HTTP crudas, para no dejar un falso negativo en el panel de QA. Se
recomienda que Desarrollo reproduzca directamente contra el backend (no
solo vía suite de pytest) antes de dar el hallazgo por no reproducible.

## Hipótesis de causa raíz (QA, sin acceso a BD/logs del backend)

El rol semilla original (`id_rol=10`, nombre `"Auxiliar de Campo"`) fue
eliminado con éxito en algún punto tras el fix de INC-M01-03-119 (ya no
aparece en `GET /roles/`, sin rastro de un 500 residual). Es posible que
haya quedado un registro de auditoría, un índice parcial o una constraint
que compara el nombre nuevo contra el histórico de forma exacta y no
maneja bien el caso de reutilización — pero esto requiere confirmación de
Desarrollo con acceso a los logs/DB de TEST; QA no puede confirmarlo desde
la API.

## Impacto

No bloquea TC-M01-119 (que ya no depende de este nombre — ver
`../TC-M01-119/test_tc_m01_119_v2.py`, retest v2.0 exitoso). Sí bloquea
cualquier flujo futuro (manual o automatizado) que intente recrear un rol
llamado `"Auxiliar de Campo"` en el ambiente TEST.
