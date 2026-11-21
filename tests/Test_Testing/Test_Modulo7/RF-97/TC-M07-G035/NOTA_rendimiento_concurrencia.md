# TC-M07-G035 — Rendimiento, concurrencia e interoperabilidad

Agrupa TC-97-076 a TC-97-081. Herramienta sugerida por la ficha: k6/JMeter + APM.

**Actualización 2026-11-20:** se instaló k6 (v1.6.1; JMeter no está disponible en este equipo) y
se corrió carga real contra TEST. Ver "Carga real con k6" más abajo. Esto reemplaza la limitación
anterior de "sin herramienta de carga" para CA-7, RNF-97.2 y, de forma no planeada, encontró un
hallazgo real sobre TC-97-077/078 (ver "Hallazgo: techo de concurrencia real"). RNF-97.1 literal
(2.000 facturas), RNF-97.7 (escalado a 2/4 instancias) y CA-14 (AgroFusión real) siguen sin
poderse confirmar — ver razones en el encabezado de `carga_k6_concurrencia_y_determinismo.js`.

## Confirmado en vivo, de forma ligera (no es una prueba de carga formal)

Script reproducible: `chequeo_aislamiento_concurrente.py` (en esta misma carpeta). Ejecutar con
`python chequeo_aislamiento_concurrente.py --pass "<clave real del Contador>"`.

2026-11-21, 8 llamadas concurrentes (`ThreadPoolExecutor`, 2 titulares × 4 repeticiones, el
default real de `--repeticiones` en el script comiteado) contra
`GET /integracion/aaef/vista-previa/productores/{nit}` en TEST:

- Duración total: 0.53 s para las 8 llamadas.
- **Corrección 2026-11-21:** una versión anterior de esta nota (2026-11-18) citaba "12 llamadas
  / 3 titulares / 0.69 s" -- eran los números de una corrida exploratoria hecha *antes* de
  escribir `chequeo_aislamiento_concurrente.py`, que nunca se actualizaron para coincidir con el
  script finalmente comiteado (2 titulares, no 3). La líder de pruebas detectó la
  inconsistencia; se corrigió re-ejecutando el script tal cual está en el repo. De paso, el
  titular `901458732` (uno de los dos originales) se reemplazó por `901333217`: desde el
  2026-11-21 el primero da 403 `ALCANCE_INSUFICIENTE` (cambio de otro QA en sus fincas, no
  relacionado con este TC).
- **Ninguna mezcla de datos entre titulares**: cada respuesta devolvió `SourceSystem.SystemNIT`
  exactamente igual al NIT solicitado, confirmando que no hay estado compartido visible entre
  solicitudes concurrentes (consistente con que `ConsultarAaefUseCase`/`mapear_compras` son
  funciones puras sin estado global, ya confirmado por unidad en TC-M07-G022 de RF-96).
- Esto es una señal a favor de CA-7 bajo concurrencia ligera, **no** una confirmación de
  RNF-97.1 (2.000 facturas), RNF-97.7 (escalado con múltiples instancias) ni de los 20
  concurrentes exactos que pide TC-97-077/078.

## Carga real con k6 (2026-11-20)

Script: `carga_k6_concurrencia_y_determinismo.js`. Corrida con
`$env:CONTADOR_PASS = "<clave real>"; k6 run carga_k6_concurrencia_y_determinismo.js`.

- **Aislamiento entre titulares (CA-7), 20 VUs reales concurrentes, 4 titulares distintos**:
  el escenario de aislamiento no pudo completarse limpio en la misma corrida que mide el
  umbral de concurrencia (ver hallazgo abajo: a 20 VUs casi todo da timeout). El aislamiento en
  sí (ningún `SystemNIT` cruzado) se confirma con las respuestas que sí completan, y de forma
  limpia con el chequeo liviano de `chequeo_aislamiento_concurrente.py` (8 llamadas, 0 mezclas).
  No se detectó ninguna mezcla de datos entre titulares en ninguna corrida, a ninguna
  concurrencia probada.
- **Determinismo del hash (RNF-97.2), 20 solicitudes concurrentes del mismo rango vía
  `http.batch()`**: las 20 respondieron 200 y las 20 trajeron el mismo `X-Content-SHA256`.
  TC-97-078 (mismo hash bajo concurrencia) **pasa**.

## Hallazgo: techo de concurrencia real entre 13 y 15 solicitudes simultáneas

Script de triage: `carga_k6_umbral_concurrencia.js` (barre `N_VUS` solicitudes concurrentes
reales — VUs/conexiones separadas, no `http.batch()` en un solo VU — contra el mismo endpoint
`vista-previa`, un solo login compartido vía `setup()`). Medido 2026-11-20 contra TEST:

| N solicitudes concurrentes | Resultado | `http_req_duration` |
|---|---|---|
| 5 | 100% (5/5) OK | avg 282ms, max 411ms |
| 10 | 100% (10/10) OK | avg 389ms, max 416ms |
| 11 | 100% (11/11) OK | avg 336ms, max 419ms |
| 12 | 100% (12/12) OK | avg 346ms, max 413ms |
| 13 | 100% (13/13) OK | avg 423ms, max 448ms |
| **14** | 100% (14/14) OK, pero en cola | avg **4.25s**, med 4.54s (1 rápida ~400ms, 13 esperando) |
| **15** | **0% (0/15)** — timeout | todas ~29.7s (tope del timeout del script) |
| 20 | 15% (3/20) OK, resto timeout | las que pasan ~0.47-0.96s; el resto ~29.7-31.2s |

Lectura: hasta 13 conexiones concurrentes reales, el tiempo de respuesta es estable (~300-450ms).
En 14 ya aparece una cola visible (13 de las 14 esperan ~4s a que se libere algo), pero todas
alcanzan a responder dentro del timeout. En 15 la cola ya no drena a tiempo y prácticamente todo
expira. Esto es compatible con un **pool de conexiones/recursos de tamaño ~13-14** en el backend
o en su infraestructura (BD, proxy/gateway de TEST) — no con una degradación gradual ni con un
problema del caso de uso (`ConsultarAaefUseCase`/`mapear_compras` ya están confirmados sin estado
compartido por unidad, TC-M07-G022). No se identificó la causa exacta (no hay acceso a métricas
de infraestructura de TEST desde este hilo).

Esto responde TC-97-077 (20 concurrentes "responden en tiempo"): **no pasa como está** — a 20
concurrentes el 85% de las solicitudes expira. Reportado como hallazgo real, ver
`../../incidencias/INC-M07-376-G035/reporte.md`.

## Evidencia oficial en `resultados/` (2026-11-21) — intencionalmente en rojo

Por decisión explícita del usuario, `resultados/` ya tiene evidencia real para que el scanner la
lea (antes estaba vacía, igual que le pasó a G024-G027):

- `resultado_TC-M07-G035_k6_summary.json` — resumen de k6 de la corrida completa de
  `carga_k6_concurrencia_y_determinismo.js` (20 VUs reales). **Checks en rojo a propósito**:
  `200 OK` 0/20, `las 20 respondieron 200` 0/1, `se recibieron 20 hashes` 0/1 — es el mismo techo
  de concurrencia de `INC-M07-376-G035` reflejado aquí, no una regresión nueva ni un error de la
  prueba. El aislamiento (nunca mezcla de `SystemNIT`) y el determinismo del hash siguen
  confirmados en las pocas respuestas que sí completan.
- `resultado_TC-M07-G035_aislamiento_8vus.txt` — el chequeo liviano de 8 llamadas (concurrencia
  moderada), que sí pasa limpio: 0 mezclas detectadas.

**Si el dashboard muestra TC-M07-G035 como Rechazado, es correcto y esperado** mientras
`INC-M07-376-G035` (severidad Alta) siga abierta — no intentar "arreglarlo" ocultando o quitando
esta evidencia; se resuelve cuando Infraestructura/Desarrollo corrija el techo de concurrencia y
se vuelva a correr `carga_k6_umbral_concurrencia.js`/`carga_k6_concurrencia_y_determinismo.js`.

## Sigue pendiente

- RNF-97.1 literal (2.000 facturas, 50 comprobantes, ≤5s) — no hay un período con ese volumen
  real en TEST; medir con datos chicos no probaría el límite real.
- RNF-97.7 (escalado a 2/4 instancias sin estado compartido) — no se controla el despliegue de
  TEST, no se puede forzar cuántas instancias atienden la corrida. El hallazgo de arriba es un
  indicio en contra (si hubiera 2+ instancias balanceando, 14-20 conexiones no deberían chocar
  con un pool tan pequeño), pero no es una confirmación formal de RNF-97.7.
- RNF-97.8 (tiempo máximo excedido → error controlado) — no se conoce el valor configurado en
  M09; los timeouts observados en el hallazgo de arriba son del cliente (k6), no un error
  controlado del servidor.
- Interoperabilidad real con AgroFusión TEST (CA-14) — requiere acceso a un entorno de
  AgroFusión de pruebas, no confirmado disponible.
