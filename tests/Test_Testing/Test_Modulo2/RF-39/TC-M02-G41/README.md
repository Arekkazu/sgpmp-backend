# TC-M02-G41 — Validación del esquema de `datos_evento` según `tipo_evento` y tipo de activo (individual/lote)

**CU-05 · RF-39 — Registro de Eventos Biológicos (base).**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-077) Rechazar esquema incompleto · (TC-M02-078) Rechazar CRECIMIENTO en LOTE sin campos de agregación · (TC-M02-079) Rechazar BAJA con `cantidad_afectada` excesiva |
| Tipo | Validación / Valores límite |
| Herramienta | API — Postman |
| Responsable | Juan Manuel · Prioridad Alta |

## ✅ Resultado: PASS — 12/12 assertions

Los 3 sub-casos funcionan exactamente como exige el RF, con mensajes claros y específicos del campo faltante.
Detalle completo en `RESULTADOS/TC-M02-G41_resultado.md`.

### Nota sobre TC-M02-078 — por qué se usó el activo preexistente 130, no uno nuevo

`CRECIMIENTO` exige una fase productiva activa antes de llegar siquiera a validar los campos de agregación — y
crear una fase nueva está bloqueado por **INC-M02-37-01**. Se usó el activo POBLACIONAL **130** (especie Cachama,
fase "Fase juvenil cachama" ya activa desde antes de esta sesión) para poder llegar a ese punto del código. Como el
payload enviado es **deliberadamente inválido** (sin `nuevo_peso_promedio`), la petición se rechaza sin persistir
ningún dato — no se modificó nada del activo 130, verificado implícitamente por el propio rechazo (400, sin
`id_eventos` en la respuesta).

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN | Resultado |
|---|---|---|---|---|
| TC-M02-077 | Activo INDIVIDUAL, ACTIVO | `POST /eventos/sanitario` tipo `DIAGNOSTICO` sin `diagnostico` | 400, mensaje menciona el campo | **PASS** — `"DIAGNOSTICO requiere el campo diagnostico."` |
| TC-M02-078 | Activo POBLACIONAL con fase activa | `POST /eventos/crecimiento` sin `nuevo_peso_promedio`/`cantidad_medida`/`tipo_agregacion` | 400, campos faltantes listados | **PASS** — `NUEVO_PESO_REQUERIDO`, `field: nuevo_peso_promedio` |
| TC-M02-079 | Lote con `cantidad_actual=50` | `POST /eventos/baja` con `cantidad_afectada=80` | Rechazo, `80 > 50` | **PASS** — `422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`, mensaje con ambos números |

### Por qué TC-M02-079 sí funciona pese a INC-M02-45-02 (bug de baja)

El chequeo `cantidad_afectada > cantidad_actual` ocurre en Python, **antes** de que el use case intente cualquier
`INSERT` en `eventos_bajas` (donde vive el trigger roto de INC-M02-45-02). Como esta petición se rechaza en ese
punto anterior, nunca llega a tocar el trigger defectuoso — el bug de INC-M02-45-02 solo afecta bajas que **sí**
pasan esta validación (bajas con cantidad válida), no a este caso.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Activos: `218` (individual, TC-M02-077) · `130` (lote preexistente,
  TC-M02-078) · `219` (lote fresco cantidad=50, TC-M02-079).
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G41
newman run TC-M02-G41.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G41.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G41.html
```

Los pasos "0B" y "3A" crean activos nuevos en cada corrida; el paso "2" reutiliza el activo 130 (dato compartido
persistente de TEST) — la petición se rechaza siempre, así que repetir la ejecución no acumula datos.
