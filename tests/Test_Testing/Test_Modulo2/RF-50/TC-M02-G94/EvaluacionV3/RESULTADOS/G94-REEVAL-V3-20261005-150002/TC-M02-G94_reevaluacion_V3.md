# TC-M02-G94 — TERCERA EVALUACIÓN (V3)

**Grupo:** Seguridad de la API de datos analíticos
**Requerimiento:** RF-50 — Disponibilidad de datos para módulos analíticos
**Caso de uso:** CU12 — Consultar indicadores y exponer datos
**Subcasos:** TC-M02-158 (rate limiting) · TC-M02-164 (solo lectura) · TC-M02-165 (autenticación obligatoria)
**Responsable QA:** Juan Esteban
**RUN_ID:** `G94-REEVAL-V3-20261005-150002`
**Fecha:** 2026-10-05 · **Ambiente decisorio:** TEST
**Incidencia en seguimiento:** INC-M02-96-G94

---

## DECISIÓN GENERAL

### TC-M02-G94: APROBADO

### TC-M02-158: APROBADO
### TC-M02-164: APROBADO
### TC-M02-165: APROBADO

Los tres subcasos se ejecutaron en esta V3 y los tres cumplen. El grupo queda **cerrado con una
ejecución actual y homogénea**, posterior a los cambios de autenticación técnica, scopes, rate
limiter y aislamiento por módulo.

El resultado decisivo es el de TC-M02-158, que en V1 y V2 nunca había podido ejecutarse: **101
solicitudes de M04 en 2,87 segundos produjeron exactamente 100 respuestas 200 y 1 respuesta 429**,
y en el mismo instante en que M04 estaba saturado, **M06 obtuvo 200**. El límite de RF-50 —100
solicitudes por minuto por módulo consumidor— quedó demostrado empíricamente, junto con el
aislamiento de contadores entre módulos.

| Subcaso | Resultado V3 | Evidencia decisiva |
| --- | --- | --- |
| TC-M02-158 | **APROBADO** | 101 solicitudes → 100 × 200 + 1 × 429 (`LIMITE_TASA_EXCEDIDO`); M06 → 200 con M04 en 429 |
| TC-M02-164 | **APROBADO** | POST y PUT → **405** con `Allow: GET`; activo sin cambios antes/después |
| TC-M02-165 | **APROBADO** | sin token → **401** `TOKEN_REQUERIDO`; Bearer inválido → **401** `TOKEN_INVALIDO`; 0 datos expuestos |
| **Grupo** | **APROBADO** | Escenario A del paquete |

**Escrituras de dominio: 0.** 0 SQL de escritura, 0 cambios de RBAC, 0 identidades provisionadas,
0 modificaciones del activo.

---

## RESUMEN DEL RESULTADO

**Assertions funcionales: 16 · Failures: 0.**

| Bloque | Assertions | Fallidas |
| --- | ---: | ---: |
| Pytest TC-M02-164 y TC-M02-165 | 6 | 0 |
| Ráfaga TC-M02-158 | 10 | 0 |
| **Total** | **16** | **0** |

La suite de Pytest ejecutó 7 pruebas: las 6 funcionales anteriores más una séptima que solo
transporta las observaciones a la evidencia consolidada y no es un criterio del caso.

Lo que esta V3 añade respecto de V2 es, en una frase: **las dos identidades técnicas independientes
que faltaban ya existen y funcionan**, de modo que la prueba que llevaba dos evaluaciones bloqueada
pudo ejecutarse por fin, y pasó.

| Precondición | V2 | V3 |
| --- | --- | --- |
| Rate limiter en el endpoint | ya existía | confirmado |
| 429 declarado en el contrato | ya existía | confirmado |
| Cuota 100 solicitudes / 60 s | declarada | **medida** |
| Dos identidades técnicas independientes en TEST | **no existían** | **existen y autentican** |
| Ejecución funcional de la ráfaga | ninguna | **realizada** |

---

## ANTECEDENTES

| Evaluación | Fecha | TC-M02-158 | TC-M02-164 | TC-M02-165 | Grupo |
| --- | --- | --- | --- | --- | --- |
| **V1** | 2026 | **BLOQUEADO** — M04 no existía como consumidor autenticable y no había módulo de control; se registró además que el endpoint no aplicaba ningún limitador (OBS-G94-01) y que el contrato no declaraba 429 (OBS-G94-02) | **APROBADO** | **APROBADO** | **BLOQUEADO** |
| **V2** | 2026-09-20 | **BLOQUEADO / NO EJECUTADO** — el endpoint ya tenía limitador y el contrato ya declaraba 429 con cuota 100/60 s, pero seguían faltando dos identidades técnicas independientes en TEST | no reejecutado; conserva el antecedente APROBADO de V1 | no reejecutado; conserva el antecedente APROBADO de V1 | **BLOQUEADO** |
| **V3** | 2026-10-05 | **APROBADO** | **APROBADO** (reejecutado) | **APROBADO** (reejecutado) | **APROBADO** |

Los resultados históricos no se reescriben. V1 y V2 se conservan intactas, y sus archivos de
automatización originales no se modificaron.

TC-M02-164 y TC-M02-165 se reejecutaron en V3 —aunque ya estaban aprobados en V1— porque el grupo
debía cerrarse con una ejecución actual y homogénea después de los cambios de autenticación
técnica, scopes y limitador. Ambos volvieron a cumplir con las identidades nuevas.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **TEST** |
| URL TEST oficial utilizada | `https://api.inmero.co/back-sigab-test` |
| `GET /health` | 200 |
| `GET /openapi.json` | 200 |
| Dominio histórico `sslip.io` | **no ejercitado** — la prueba no se duplicó contra dos dominios |
| Rama QA (backend y frontend) | `qa/juan-esteban-cuarta-evaluacion-M09-y-M02` |
| HEAD backend | `0371f2ec1d97ddfe7f3f33526d0db071d016e6ea` (= `origin/test`, `0 0`) |
| HEAD frontend | `cd3af47c07302f7310b17e6800642aab2253f479` (`2 0` respecto de `origin/test`) |

Contrato del endpoint `GET /activos-biologicos/{id_activo}/datos-consolidados` en TEST:

| Aspecto | Valor |
| --- | --- |
| Métodos declarados en la ruta | **solo `get`** |
| Respuestas declaradas | 200, 400, 401, 403, 404, 422, **429**, 500 |
| `429` | **declarado** — `Too Many Requests` con esquema `ErrorResponse` |

Que la ruta declare únicamente `get` es evidencia contractual a favor de TC-M02-164, y la presencia
de `429` cierra la observación OBS-G94-02 de V1.

### Nota sobre la herramienta de carga

El paquete pide **k6**. **k6 no está instalado en la estación de QA** —la misma limitación que V1
ya había registrado— y QA no instala software en la estación durante una ejecución.

La ráfaga se ejecutó con un arnés equivalente en Node que reproduce exactamente los parámetros y el
oráculo que el paquete define para k6:

| Parámetro del paquete | Aplicado |
| --- | --- |
| Exactamente 101 solicitudes oficiales | sí, 101 — ni una más |
| Concurrencia para cerrar la ventana < 60 s | 5 trabajadores, equivalente a `shared-iterations` con 5 VUs |
| Oráculo por conteos globales, no por orden de llegada | sí |
| Sin petición de *setup* al endpoint RF-50 antes de la ráfaga | sí, 0 peticiones de setup |
| Consulta de control de M06 inmediatamente después | sí |

El informe de la ráfaga se escribió con la forma de un resumen de k6
(`reporte-k6-g94-v3.json`) para que la evidencia sea comparable. Si los líderes prefieren la
ejecución con el binario de k6, el caso puede repetirse sin cambios de oráculo en cuanto k6 esté
disponible en la estación.

---

## ACTOR / IDENTIDADES TÉCNICAS

| Campo | M04 | M06 |
| --- | --- | --- |
| Correo | `dev.m04.rf50@sgpmp-test.com` | `dev.m06.rf50@sgpmp-test.com` |
| Login | **200** | **200** |
| `id_usuario` | **123** (coincide con lo esperado) | **124** (coincide con lo esperado) |
| Rol | **Integración M04** | **Integración M06** |
| Estado de cuenta | **Activo** | **Activo** |
| Permisos activos | 5 | 3 |
| Recursos con READ | 9, 29, 60, 61, 62 | 29, 63, 64 |

Scopes analíticos verificados en runtime, con el token de cada identidad:

| Scope | Recurso | M04 | M06 |
| --- | ---: | --- | --- |
| `datos_analiticos_eventos` | 60 | **sí** | no |
| `datos_analiticos_fases` | 61 | **sí** | no |
| `datos_analiticos_estado` | 62 | **sí** | no |
| `datos_analiticos_metricas` | 63 | no | **sí** |

La asimetría es la esperada y **no se corrigió**: G94 evalúa el limitador del endpoint RF-50 por
módulo consumidor, no que ambos módulos tengan los mismos scopes funcionales. Por eso cada módulo
consultó el tipo de dato que tiene legítimamente autorizado —M04 `eventos`, M06 `metricas`—,
atravesando el mismo endpoint y el mismo limitador. **No se exigió `metricas` a M04** ni se le
concedió ningún permiso.

Las contraseñas se pasaron únicamente por variables de entorno del proceso y no aparecen en ningún
artefacto. No se persistieron JWT, refresh tokens, cookies ni encabezados `Authorization`.

**No se modificó el RBAC:** 0 scopes añadidos, 0 permisos añadidos, 0 roles modificados, 0 usuarios
creados, 0 contraseñas cambiadas, 0 fincas modificadas. Las identidades entregadas por Desarrollo se
probaron tal como estaban.

---

## CONFIGURACIÓN UTILIZADA / FIXTURE

El fixture histórico **se revalidó y se reutilizó sin cambios**.

| Campo | Esperado | Observado | Coincide |
| --- | --- | --- | --- |
| `id_activo_biologico` | 279 | 279 | sí |
| Identificador | `QAJE-CREC-OK` | `QAJE-CREC-OK` | sí |
| Estado | ACTIVO | ACTIVO | sí |
| Tipo | — | INDIVIDUAL | — |
| Especie | — | 40 | — |
| Infraestructura | — | 48 | — |
| Visible para M04 | sí | **200** sobre el activo y sobre `datos-consolidados?tipo_dato=eventos` | sí |
| Visible para M06 | sí | **200** sobre `datos-consolidados?tipo_dato=metricas` | sí |

**Nota sobre la finca.** El detalle de la infraestructura 48 responde **403** a estas identidades
técnicas, porque no tienen ese scope, de modo que la finca 57 no se leyó directamente con ellas. El
alcance quedó demostrado de la forma que el caso necesita, que es empírica: **ambos módulos obtienen
200 sobre el activo del fixture**. No se usó una cuenta administrativa para suplir esa lectura ni se
modificó ningún alcance.

### Implementación de RF-50 verificada en código (`origin/test`)

| Aspecto | Valor |
| --- | --- |
| Limitador | `rate_limit(100, 60, alcance="activos_datos_consolidados", clave=_clave_consumidor_datos_consolidados)` |
| Ubicación | `activo_biologico_router.py:214-216`, aplicado como dependencia en la línea 1804 |
| Clave del contador | identidad técnica → `modulo:<n>` · usuario humano → `usuario:<id>` |
| Resolución del módulo | `resolver_modulo_consumidor`: el patrón `Integración M0<n>` del nombre del rol produce `modulo<n>` → **M04 → `modulo4`**, **M06 → `modulo6`** |
| Almacenamiento del contador | en memoria del proceso, con cerrojo |

Esta revisión se hizo, como exige el paquete, **sin que sirviera de aprobación**: el veredicto de
TC-M02-158 se decidió por la ejecución real en TEST.

### Controles positivos del preflight

| Módulo | `tipo_dato` | HTTP | Activo devuelto |
| --- | --- | ---: | --- |
| M04 | `eventos` | **200** | 279 · `QAJE-CREC-OK` |
| M06 | `metricas` | **200** | 279 · `QAJE-CREC-OK` |

Ninguno devolvió 401, 403 ni 404, de modo que el gate principal quedó abierto y se creó el RUN.

---

## TC-M02-158 — RATE LIMITING

**Resultado: APROBADO.**

### Preparación de la ventana

El último GET autenticado de M04 al endpoint RF-50 antes de la ráfaga fue el control positivo de
TC-M02-164, a las **15:01:01.790 Z**. La ráfaga oficial comenzó a las **15:02:30.649 Z**, es decir
**88,9 segundos después**, por encima de los 61 segundos exigidos. Durante esa espera no se emitió
ningún GET de M04 al endpoint.

Los logins se hicieron antes de la espera: el endpoint de sesiones no consume el contador de RF-50.

**La ráfaga no incluyó ninguna petición de *setup* al endpoint RF-50.** Este es precisamente el
defecto del script histórico de V1, que hacía un GET de M04 en `setup()` inmediatamente antes de las
101 iteraciones y arrancaba la ventana con una solicitud ya consumida. El script de V3 separa
preflight → espera de ventana limpia → ráfaga oficial.

### Ráfaga oficial

```
GET /activos-biologicos/279/datos-consolidados?tipo_dato=eventos&pagina=1&page_size=20
Actor: M04 (dev.m04.rf50@sgpmp-test.com, rol Integración M04)

Solicitudes: 101    Concurrencia: 5 trabajadores
Inicio: 2026-10-05T15:02:30.649Z
Fin:    2026-10-05T15:02:33.518Z
Duración: 2,869 s  (muy por debajo de la ventana de 60 s)
```

| Código | Cantidad |
| --- | ---: |
| HTTP 200 | **100** |
| HTTP 429 | **1** |
| Otros (401 / 403 / 404 / 500) | **0** |
| **Total** | **101** |

Es el comportamiento ideal que el paquete describe: exactamente 100 permitidas y la que excede el
límite rechazada.

### El 429

| Campo | Valor |
| --- | --- |
| Orden de llegada | 100.ª respuesta |
| HTTP | **429** |
| `error_code` | **`LIMITE_TASA_EXCEDIDO`** |
| `message` | «Demasiadas solicitudes en poco tiempo. Intenta de nuevo en unos momentos.» |
| Expone datos del activo | **no** |
| Cabeceras de cuota (`Retry-After`, `RateLimit-*`, `X-RateLimit-*`) | **ninguna presente** |

La semántica es la correcta y el cuerpo no filtra información del activo. La ausencia de cabeceras
de cuota **no hace fallar el caso**, porque RF-50 no las exige; queda registrada como observación
para quien quiera mejorar la experiencia del consumidor.

Latencias de la ráfaga: mínima 110 ms, máxima 368 ms, media 139 ms.

### Aislamiento M04 vs M06

Inmediatamente después de saturar a M04:

| Momento | Actor | Petición | HTTP | `error_code` |
| --- | --- | --- | ---: | --- |
| 15:02:33.642 Z | **M06** | `?tipo_dato=metricas` | **200** | — |
| 15:02:33.739 Z | **M04** | `?tipo_dato=eventos` | **429** | `LIMITE_TASA_EXCEDIDO` |

Las dos lecturas están separadas por menos de 100 ms, de modo que la comparación es sobre el mismo
instante: **M06 pasa mientras M04 sigue bloqueado**. Eso demuestra que los contadores son
independientes por módulo consumidor y que la ráfaga de un módulo no penaliza al otro.

La reconfirmación de M04 es importante: sin ella, un 200 de M06 podría explicarse por una ventana ya
expirada en lugar de por aislamiento real.

### Oráculo del subcaso

| Condición | Resultado |
| --- | --- |
| Las 101 solicitudes se completaron dentro de la ventana de 60 s | **CUMPLE** (2,87 s) |
| Se emitieron exactamente 101 solicitudes | **CUMPLE** |
| Apareció al menos una respuesta HTTP 429 al exceder el límite | **CUMPLE** (1) |
| No aparecieron códigos inesperados (401 / 403 / 404 / 500) | **CUMPLE** (0) |
| El número de respuestas permitidas no excede el límite declarado | **CUMPLE** (100 ≤ 100) |
| El 429 no expone datos del activo | **CUMPLE** |
| El 429 trae un error funcional identificable | **CUMPLE** (`LIMITE_TASA_EXCEDIDO`) |
| M06 responde 200 inmediatamente después de saturar M04 | **CUMPLE** |
| M06 no recibe 429 por la ráfaga de M04 | **CUMPLE** |
| M04 sigue saturado en ese mismo instante | **CUMPLE** |

**10 de 10.** Todos los criterios de aprobación del subcaso se satisfacen: M04 estaba autenticado y
con acceso válido, las 101 solicitudes entraron en la ventana, el 429 apareció al superar 100, no
hubo códigos inesperados, el 429 no expuso datos, y M06 respondió 200 sin verse afectado.

---

## TC-M02-164 — SOLO LECTURA

**Resultado: APROBADO.**

### Control positivo

```
GET /activos-biologicos/279/datos-consolidados?tipo_dato=eventos&pagina=1&page_size=20
Actor: M04 autenticado
→ HTTP 200 · id_activo_biologico 279 · identificador QAJE-CREC-OK
```

Esto establece que el token es válido, el módulo está autorizado, el activo es visible y el endpoint
es accesible: cualquier rechazo posterior se debe al método, no a la identidad.

### Intentos de escritura

Dos intentos, con token M04 válido y cuerpo mínimo sintácticamente válido
(`{"qa_intento_escritura": true}`):

| Método | HTTP | Cabecera `Allow` | `error_code` |
| --- | ---: | --- | --- |
| `POST /activos-biologicos/279/datos-consolidados` | **405** | `GET` | — |
| `PUT /activos-biologicos/279/datos-consolidados` | **405** | `GET` | — |

Ambos devolvieron **405 Method Not Allowed**, que es el resultado preferible: la ruta solo declara
`GET`, de modo que el rechazo ocurre en el enrutamiento y **ninguna petición alcanzó lógica de
escritura**. No hubo ningún 2xx, y no se aceptó un 400 ni un 422 como prueba de solo lectura. La
cabecera `Allow: GET` lo confirma desde el propio servidor.

### Integridad del activo

Snapshot antes y después de los intentos, tomado de `GET /activos-biologicos/279` —endpoint que no
comparte el contador de RF-50, para no consumir cuota antes de TC-M02-158:

| Campo | Antes | Después |
| --- | --- | --- |
| `id_activo_biologico` | 279 | 279 |
| `identificador` | `QAJE-CREC-OK` | `QAJE-CREC-OK` |
| `tipo` | INDIVIDUAL | INDIVIDUAL |
| `id_especie` | 40 | 40 |
| `id_estado` / `nombre_estado` | 1 / ACTIVO | 1 / ACTIVO |
| `id_infraestructura` | 48 | 48 |
| `fecha_inicio_ciclo` | 2026-06-01 | 2026-06-01 |
| `fecha_actualizacion` | `null` | `null` |
| `atributos_dinamicos` | `null` | `null` |

**Sin cambios.** `fecha_actualizacion` permanece en `null`, lo que descarta cualquier escritura
silenciosa: no se modificó el activo, no se crearon eventos, no se alteraron métricas y no se tocó
configuración. **Escrituras de dominio producidas: 0.** No se ejecutó ningún SQL de escritura.

---

## TC-M02-165 — AUTENTICACIÓN OBLIGATORIA

**Resultado: APROBADO.**

Endpoint: `GET /activos-biologicos/279/datos-consolidados?tipo_dato=eventos`

| Variante | HTTP | `error_code` | Campos sensibles expuestos | Menciona el activo |
| --- | ---: | --- | --- | --- |
| **A** — sin encabezado `Authorization` | **401** | `TOKEN_REQUERIDO` | ninguno | no |
| **B** — `Bearer` ficticio e inválido | **401** | `TOKEN_INVALIDO` | ninguno | no |

Ambas variantes devolvieron **401 de autenticación**, no 403 de autorización: la distinción importa,
porque TC-M02-165 prueba autenticación y un 403 no satisfaría el caso.

Se comprobó que ninguna de las dos respuestas contiene los campos de datos consolidados
(`id_activo_biologico`, `identificador`, `tipo_activo`, `especie`, `estado_actual`,
`infraestructura_asociada`, `fase_productiva_activa`, `historial_eventos`, `historial_fases`,
`historico_estados`, `metricas_actuales`) ni el identificador `QAJE-CREC-OK`. **No se expusieron
datos consolidados, eventos, métricas ni información sensible.**

El `Bearer` de la variante B es una cadena inventada sin valor criptográfico
(`qa-token-ficticio-invalido-g94-v3`): no es un token real y por eso puede documentarse.

---

## RESULTADO DEL ORÁCULO

| Elemento | Valor |
| --- | --- |
| RUN_ID | `G94-REEVAL-V3-20261005-150002` (único) |
| Assertions funcionales | **16** |
| Failures | **0** |
| Pytest (TC-164 + TC-165) | 7 pruebas ejecutadas · 6 funcionales · 0 fallidas |
| Ráfaga (TC-158) | 10 condiciones · 10 cumplidas · 0 fallidas |
| Solicitudes oficiales de M04 | 101 |
| Duración de la ráfaga | 2,869 s |
| HTTP 200 / 429 / otros | 100 / 1 / 0 |
| Escrituras de dominio | **0** |
| SQL de escritura | **0** |
| Cambios de RBAC | **0** |
| Identidades provisionadas por QA | **0** |
| Ejecuciones V3 creadas | **1** |

No se redujo, relajó ni eliminó ninguna assertion, y no se aumentó el volumen de la ráfaga por
encima de 101 solicitudes.

---

## COMPARACIÓN V1 VS V2 VS V3

| Aspecto | V1 | V2 | **V3** |
| --- | --- | --- | --- |
| TC-M02-158 | BLOQUEADO | BLOQUEADO / NO EJECUTADO | **APROBADO** |
| TC-M02-164 | APROBADO | antecedente de V1 | **APROBADO (reejecutado)** |
| TC-M02-165 | APROBADO | antecedente de V1 | **APROBADO (reejecutado)** |
| Grupo | BLOQUEADO | BLOQUEADO | **APROBADO** |
| Ejecución funcional de la ráfaga | ninguna | ninguna | **101 solicitudes** |
| Limitador en el endpoint | **no existía** | existía | existía, **medido** |
| `429` en el contrato | **no declarado** | declarado | declarado y **observado** |
| Identidad técnica M04 | **no existía** | no provisionada | **id 123, Integración M04, activa** |
| Módulo de control | **no disponible** | no disponible | **id 124, Integración M06, activa** |
| Aislamiento por módulo | no evaluable | no evaluable | **demostrado** |
| Cabeceras de cuota | ninguna | ninguna | **ninguna** (no exigidas por RF-50) |
| POST / PUT | rechazados | no reejecutado | **405 con `Allow: GET`** |
| Datos expuestos sin token | no | no reejecutado | **no (401 en ambas variantes)** |
| Escrituras de dominio | 0 | 0 | **0** |
| Herramienta de carga | k6 entregado, no ejecutado | no ejecutada | **arnés equivalente en Node** (k6 no instalado) |

La serie cuenta una corrección completa: V1 encontró que no existía limitador y que no había
identidad técnica; V2 confirmó que Desarrollo ya había implementado el limitador y el 429, pero que
seguían faltando las identidades; V3 encuentra las identidades disponibles y **mide** el
comportamiento, que resulta correcto en los tres ejes del grupo.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

### Lo que quedó demostrado

El endpoint de exposición de RF-50 se comporta como el requerimiento exige en los tres frentes de
seguridad que este grupo evalúa:

1. **Cuota por módulo consumidor.** No es un límite por usuario disfrazado: la clave del contador es
   `modulo:<n>`, derivada del nombre del rol técnico, y la ejecución lo confirma. M04 agotó su cuota
   y M06 siguió pasando en el mismo instante.
2. **Solo lectura.** La ruta no expone escritura en el contrato y el servidor lo hace cumplir en el
   enrutamiento, con 405 y `Allow: GET`. Los intentos no alcanzaron lógica de escritura y el activo
   quedó intacto.
3. **Autenticación obligatoria.** Ambas variantes se rechazan con 401 —no con 403— y sin filtrar
   nada del activo.

### Lo que cerró las observaciones históricas

- **OBS-G94-01** de V1 (el endpoint no aplicaba ningún limitador): resuelta. El limitador existe,
  está aplicado como dependencia del endpoint y se midió funcionando.
- **OBS-G94-02** de V1 (el contrato no declaraba 429): resuelta. El contrato declara 429 y la
  ejecución lo produjo.
- **Bloqueo de V2** (faltaban dos identidades técnicas independientes en TEST): resuelto por
  Desarrollo. Ambas identidades autentican, están activas y tienen los scopes que su módulo necesita.

### Observaciones que no afectan el veredicto

- **Sin cabeceras de cuota.** Las respuestas no incluyen `Retry-After`, `RateLimit-*` ni
  `X-RateLimit-*`. RF-50 no las exige, de modo que no hacen fallar el caso, pero su ausencia obliga
  al consumidor a descubrir el límite por ensayo y error. Es una mejora razonable de experiencia de
  integración, no un defecto.
- **Contador en memoria de proceso.** El limitador guarda el contador en memoria con un cerrojo. En
  esta ejecución el comportamiento fue exacto —100 permitidas, 1 rechazada—, lo que indica que TEST
  atendió la ráfaga con un único proceso. Conviene tenerlo presente: si en producción el servicio se
  despliega con varias réplicas o *workers*, el límite efectivo podría multiplicarse por el número
  de procesos. **No es un hallazgo de esta ejecución** —aquí el requisito se cumplió— sino una
  consideración de arquitectura que corresponde decidir al equipo antes de escalar el servicio.
- **Asimetría de scopes entre M04 y M06.** Es deliberada y correcta para este grupo. No se tocó.

### Sobre la herramienta

La sustitución de k6 por un arnés equivalente en Node es una **limitación de la estación de QA**, no
del producto ni del caso. Los parámetros y el oráculo son los que el paquete define, y el resultado
—100/1/0 en 2,87 s— es inequívoco. Queda a criterio de los líderes repetir la ráfaga con el binario
de k6 si desean ese formato de evidencia; el oráculo no cambiaría.

---

## INCIDENCIA

**INC-M02-96-G94.**

Estado tras V3: **VERIFICADA — CORRECCIÓN CONFIRMADA FUNCIONALMENTE.**

| Alcance de la incidencia | Estado en V3 | Evidencia |
| --- | --- | --- |
| El endpoint de exposición no aplicaba ningún limitador de tasa | **Corregido y verificado** | 101 solicitudes → 100 × 200 + 1 × 429 en 2,87 s |
| El contrato no declaraba `429` | **Corregido y verificado** | `429 Too Many Requests` en el OpenAPI de TEST y observado en la ejecución |
| La cuota debía ser 100 solicitudes / minuto | **Verificado** | el 429 apareció en la solicitud que excede 100 |
| La cuota debía ser **por módulo consumidor** | **Verificado** | M06 → 200 con M04 en 429 en el mismo instante |
| Faltaban identidades técnicas independientes en TEST | **Resuelto por Desarrollo** | M04 id 123 y M06 id 124, ambas activas |

**No se creó ninguna incidencia nueva** y no se modificó ningún registro externo. La decisión de
cerrar INC-M02-96-G94 queda fuera de esta ejecución automática, pero esta V3 aporta la evidencia
funcional que faltaba para sustentarla.

---

## CONCLUSIÓN

La tercera evaluación de TC-M02-G94 cierra el grupo en **APROBADO**, con los tres subcasos
ejecutados en esta misma V3 y **0 failures** sobre 16 assertions funcionales, sin ninguna escritura
de dominio, sin SQL de escritura y sin tocar el RBAC.

El subcaso que llevaba dos evaluaciones bloqueado, **TC-M02-158, queda APROBADO con evidencia
empírica**: 101 solicitudes de la identidad técnica M04 dentro de una ventana limpia produjeron
exactamente 100 respuestas permitidas y una respuesta **429 `LIMITE_TASA_EXCEDIDO`**, sin ningún
código inesperado y sin filtrar datos del activo; y, en el mismo instante en que M04 estaba
saturado, **M06 obtuvo 200**, lo que demuestra que el contador está aislado por módulo consumidor y
no es un límite por usuario ni un límite global compartido.

**TC-M02-164 queda APROBADO**: POST y PUT se rechazan con 405 y `Allow: GET`, sin alcanzar lógica de
escritura, y el activo permanece idéntico antes y después. **TC-M02-165 queda APROBADO**: tanto la
petición sin encabezado como la del `Bearer` inválido devuelven 401 de autenticación y no exponen
ningún dato.

Las dos observaciones que V1 había registrado —ausencia de limitador y ausencia de `429` en el
contrato— están resueltas y verificadas, y la precondición que bloqueó V2 —la falta de dos
identidades técnicas independientes— fue atendida por Desarrollo.

Quedan dos notas para el equipo, ninguna de las cuales afecta el veredicto: las respuestas no
publican cabeceras de cuota, que RF-50 no exige pero ayudarían al consumidor; y el contador vive en
memoria del proceso, algo que conviene revisar si el servicio se despliega con varias réplicas.

V1 y V2 permanecen intactas, igual que los archivos históricos de automatización del grupo.

---

### Artefactos de este RUN

`EvaluacionV3/RESULTADOS/G94-REEVAL-V3-20261005-150002/`

| Archivo | Contenido |
| --- | --- |
| `evidencia-g94-v3.json` | Evidencia consolidada: RUN_ID, ambiente, Git inicial y final, ambos actores saneados con roles, IDs y scopes, fixture revalidado, implementación de RF-50 verificada en código, controles positivos, TC-164 con integridad antes/después, TC-165 variantes A y B, ventana y conteos de TC-158, primer 429, aislamiento, escrituras, oráculo y seguridad |
| `reporte-k6-g94-v3.json` | Informe de la ráfaga con forma de resumen de k6: configuración, ventana, conteos, secuencia de las 101 respuestas, primer 429 con sus cabeceras, control de aislamiento, latencias y oráculo |
| `reporte-pytest-g94-v3.xml` | JUnit XML de TC-M02-164 y TC-M02-165 |
| `TC-M02-G94_reevaluacion_V3.md` | Este informe |

Automatización en `EvaluacionV3/`:

| Archivo | Contenido |
| --- | --- |
| `test_tc_m02_g94_security_v3.py` | TC-M02-164 y TC-M02-165. Adaptación mínima del archivo histórico: mismos objetivos, oráculos y criterios; cambian el dominio TEST vigente y la identidad técnica, que en V1 no existía |
| `test_tc_m02_g94_rate_limit_v3.js` | TC-M02-158. Reutiliza la lógica y las assertions del script histórico, corrigiendo su defecto de *setup*: separa preflight, espera de ventana limpia y ráfaga oficial de 101 solicitudes sin petición previa al endpoint RF-50 |

No se crearon colección Postman, reportes HTML de k6 o Newman, `README`, `preflight.json`,
`git-final.json` ni `security.json`: esa información está consolidada en `evidencia-g94-v3.json`.
Los archivos históricos del grupo no se modificaron.
