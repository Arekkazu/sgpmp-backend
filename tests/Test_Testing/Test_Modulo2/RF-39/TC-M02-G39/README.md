# TC-M02-G39 — Registro de eventos biológicos según estado operativo del activo (ACTIVO, EN_TRATAMIENTO, AISLADO)

**CU-05 · RF-39 — Registro de Eventos Biológicos (base).**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-072) Evento válido sobre ACTIVO · (TC-M02-073) Permitir sobre EN_TRATAMIENTO · (TC-M02-074) Permitir sobre AISLADO |
| Tipo | Funcional |
| Herramienta | API — Postman |
| Endpoints | `GET /activos-biologicos/{id_activo}/eventos` (según ficha) |
| Responsable | Juan Manuel · Prioridad Alta |

## ✅ Resultado: PASS — 13/13 assertions

Los 3 estados operativos permiten registrar el evento, tal como exige el RF. Detalle completo en
`RESULTADOS/TC-M02-G39_resultado.md`.

### Dos adaptaciones necesarias, explicadas

**1. Tipo de evento usado — sanitario (RF-41), no genérico.** RF-39 no tiene un endpoint propio de "evento
biológico genérico"; cada tipo concreto (crecimiento, sanitario, productivo, reproductivo, baja) vive en su propio
endpoint, cada uno con su propio gate de estado. Se usó un evento **sanitario** (`CONTROL_PREVENTIVO`) porque su
use case llama al gate compartido `validar_estado_permite_eventos()` (`_ESTADOS_PERMITEN_EVENTOS = {1,3,4}` =
ACTIVO/EN_TRATAMIENTO/AISLADO), que es exactamente el contrato que pide RF-39. **No se pudo usar crecimiento
(RF-40) ni productivo (RF-43)** — ambos exigen además una fase productiva activa, y crear una fase está bloqueado
hoy por INC-M02-37-01 (ver `TC-M02-G23/NOTA_BLOQUEO.md`). Por lectura de código ya se sabe (auditoría del módulo,
confirmado también en esta sesión) que esos dos tipos **rechazan** EN_TRATAMIENTO/AISLADO con su propio chequeo
restrictivo — una violación real de RF-39 que no se pudo demostrar en vivo por el bloqueo de fase, pero que no
depende de este caso para estar documentada.

**2. Activo POBLACIONAL, no INDIVIDUAL.** El endpoint de verificación listado en la ficha,
`GET /activos-biologicos/{id_activo}/eventos`, está restringido en código a activos `POBLACIONAL`
(`consultar_eventos_use_case.py`: `if activo.tipo != 'POBLACIONAL': raise TIPO_INVALIDO`) — con un INDIVIDUAL
responde 422. Se registró un lote en vez de un individuo para que ese endpoint funcionara tal como lo pide la
ficha del caso.

**3. Nota metodológica sobre `fecha` — desfase de reloj ya reportado (INC-M02-41-01).** Cada evento se registró con
`fecha` explícita (en vez de confiar en el valor por defecto del servidor) para evitar el defecto ya reportado
donde `trg_fn_evento_fecha_coherente` rechaza el "ahora" del servidor con tolerancia casi nula. Se midió el desfase
real de esta máquina de ejecución contra el reloj de la base de datos de TEST (~988 ms, ver método abajo) y se
usó un margen de 2 segundos hacia el pasado — la colección se ejecuta con `newman run ... --delay-request 3000`
para garantizar que ese margen quede siempre después de la creación del activo y antes del "ahora" real del
servidor, sin importar la latencia de red del momento.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN | Resultado |
|---|---|---|---|---|
| TC-M02-072 | Activo POBLACIONAL recién creado, estado ACTIVO | `POST /eventos/sanitario` (CONTROL_PREVENTIVO) | 201, evento asociado al activo y al usuario | **PASS** |
| TC-M02-073 | Mismo activo, transición a EN_TRATAMIENTO (RF-44) | `POST /eventos/sanitario` | 201, no bloquea | **PASS** |
| TC-M02-074 | Mismo activo, transición a AISLADO (RF-44) | `POST /eventos/sanitario` | 201, no bloquea | **PASS** |
| Verificación | — | `GET /eventos` | Los 3 eventos en el historial | **PASS** |
| Verificación | — | `GET /auditoria?rf_origen=RF41` | 3 registros `EVENTO_SANITARIO_REGISTRADO` exitosos | **PASS** |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Activo de prueba: `id_activo_biologico=212` (POBLACIONAL, especie 3).
- Newman 6.2.2 + htmlextra 1.23.1, ejecutado con `--delay-request 3000` (ver nota metodológica arriba).
- Desfase de reloj local vs. base de datos de TEST medido con método de punto medio de ida y vuelta
  (round-trip midpoint): ~988 ms, consistente en 3 mediciones — con autorización del usuario para acceso de solo
  lectura a la base de datos.
- Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G39
newman run TC-M02-G39.postman_collection.json --delay-request 3000 -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G39.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G39.html
```

`--delay-request 3000` es obligatorio para que las fechas explícitas de los eventos queden siempre en la ventana
segura (después de la creación del activo, antes del "ahora" real del servidor) — sin él, la colección corre en
~2.5s y esa ventana es más angosta que el desfase de reloj medido.
