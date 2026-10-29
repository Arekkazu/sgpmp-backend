# INC-M03-121-G64 — Control de ráfagas de eventos Edge (TC-M03-127)

**RF:** RF-56 E6 ("Alta carga o saturación del sistema"). **Issue:** #668.
**Estado:** el mecanismo **existía** (DEV-45) y ahora queda **verificado bajo carga real**. El umbral
se puede configurar por entorno y la cifra sigue pendiente de confirmación de Análisis. Hay un
hallazgo de capacidad, que se explica abajo.

## Requisito y umbral: dónde está cada cosa

| Fuente | Qué dice |
|---|---|
| RF-56 E6 | "Se generan demasiados eventos en corto tiempo" → **se activa control de tasa (rate limiting), se priorizan eventos críticos, se agrupan eventos en batch**. **No fija una cifra** |
| RF-55 §7 | "Manejo de alta frecuencia de eventos": control de tasa para evitar saturar el buffer (RF-54) y el backend. Sin cifra |
| `gaps_rf_m03_telemetria.md` (G-13) | E6: "No existe", dueño DEV |
| Reparto DEV del 20/10, **DEV-45** | "E6 rate limiting", sin cifra. La regla 4 del reparto dice que, si Análisis no responde, se aplica la propuesta de Desarrollo y se anota |
| "≤ 50 mensajes/s" y "≥ 50 mediciones/s" | Son de **RF-53** (recepción de telemetría, camino MQTT → `fn_ingesta_telemetria`), **no de RF-56** |

El umbral vigente es **la propuesta de DEV-45: 60 eventos por minuto por dispositivo**. Desde este
cambio se ajusta con `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO` sin tocar código. Queda **pendiente de que
Análisis confirme la cifra**.

QA no lo encontró porque buscaba en `src/telemetry`, pero el limitador es transversal y vive en
`src/shared/rate_limit.py`. Se invoca desde
`recibir_evento_edge_use_case.py` (`registrar_llamada("rf56_eventos_edge:<serial>", límite, 60)`).

## Comportamiento

| Pregunta de QA | Respuesta |
|---|---|
| ¿Se limita la frecuencia de eventos? | Sí, **por dispositivo** (`serial`, que el broker fija desde el topic), con una ventana deslizante de 60 s |
| ¿Cómo responde al superar el límite? | **429 `LIMITE_TASA_EXCEDIDO`** con `Retry-After` (segundos hasta que se libera la ventana) y `RateLimit-Limit`, `RateLimit-Remaining: 0` y `RateLimit-Reset`. El evento **no se persiste** ni genera paquete: el Edge lo conserva en su buffer (RF-54) y lo reintenta |
| Prioridad de eventos críticos | Un evento `CRITICO` **no cuenta ni se frena**, aunque el dispositivo esté saturado |
| Procesamiento por lotes | Agrupación temporal de 5 s en la consolidación (Fase 4) y envío a M04 en lotes de máximo 500 (INC-M03-112-G55, #655) |
| Aislamiento | Un dispositivo saturado no afecta a otro |

**Límite del diseño:** el contador vive en memoria **por proceso**. El backend corre a propósito con un
solo proceso (`docker-compose.prod.yml`: "No introducir Gunicorn ni --workers sin migrar antes esos
dos a un backend compartido"). Con N procesos o réplicas, el límite efectivo sería N × 60.

## Cambio de código

`recibir_evento_edge_use_case.py`: `_limite_eventos_por_minuto()` lee
`IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO`. Si está vacía usa 60, y un valor no entero o ≤ 0 se registra en
el log y también usa 60. La constante `LIMITE_EVENTOS_POR_MINUTO` se conserva. `.env.example`
documenta la variable.

## Evidencia: carga real en un entorno aislado

`tests/integration/test_inc_m03_121_g64_rafagas_eventos_edge.py`:
- **Servidor:** uvicorn real en `127.0.0.1` con el router de eventos Edge.
- **BD:** una sesión por solicitud, con un pool de 50 conexiones, contra PostgreSQL real.
- **Carga:** 50 clientes HTTP concurrentes que arrancan juntos con una barrera.
- **Aislamiento:** no se usa DEV/TEST y no hay tráfico fuera de la máquina.

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_rafaga_concurrente_acepta_exactamente_el_limite_y_no_persiste_lo_rechazado` | 100 eventos simultáneos de un dispositivo | **60 × 201 y 40 × 429** exactos; `Retry-After ≥ 1`, `RateLimit-Limit: 60`; **60 eventos y 60 paquetes** en BD |
| `test_criticos_no_se_frenan_con_el_dispositivo_saturado` | 70 normales, luego 30 `CRITICO` y luego 1 normal | 60/10; **30 × 201**; el normal sigue con 429; 90 persistidos |
| `test_un_dispositivo_saturado_no_afecta_a_otro` | 90 de A + 40 de B mezclados | A 60/30; **B 40 × 201** |
| `test_la_ventana_se_libera_al_vencer` | Reloj +61 s | El dispositivo vuelve a aceptar |
| `test_limite_configurable_por_entorno` | `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO=10` | 10 × 201, 15 × 429, `RateLimit-Limit: 10` |
| `test_limite_invalido_en_entorno_usa_el_valor_por_defecto[0/-5/abc]` | Valor inválido | 60 |
| `test_rafaga_de_muchos_dispositivos_bajo_el_limite_no_pierde_eventos` | 10 dispositivos × 30 eventos, 50 clientes | **300 × 201**, 30/30 persistidos por dispositivo; caudal medido (abajo) |

### Ejecución (2026-10-27)

- **BD efímera:** `pruebas_g64_test` en el PostgreSQL 18 local (`sgpmp-db`), con `alembic upgrade head`
  hasta `ebbb160365e5`. Se borró al terminar, junto con los roles temporales.
- **Ejecución en contenedor:** las pruebas corrieron en un contenedor con la imagen del backend
  (Python 3.13), conectado solo a la red Docker de `sgpmp-db`.
- **Por qué no en Windows:** en este equipo Windows, las conexiones locales simultáneas fallan bajo
  carga con `WinError 10053/10038` (el software del host corta la conexión; el antivirus intercepta
  el tráfico local, como en G63). Las 8 pruebas de límite sí pasan en Windows, pero la de caudal no.

```
tests/integration/test_inc_m03_121_g64_rafagas_eventos_edge.py    9 passed
tests/integration/test_rf56_dev17_paquetes_pendientes.py          23 passed (incluye test_e6_limite_por_dispositivo_salvo_criticos)
32 passed in 62.70s
[G64] 300 eventos con 50 clientes en 15.52 s = 19.3 eventos/s; latencia ms: mediana 1550, p95 3095, máx 3318
```

## Hallazgo: capacidad del endpoint por proceso

Perfil del mismo entorno, con 200 eventos de 10 dispositivos:

| Clientes concurrentes | Eventos/s | Latencia mediana | p95 |
|---|---|---|---|
| 1 (secuencial) | ~20 | 49 ms | — |
| 5 | 28,4 | 167 ms | 213 ms |
| 10 | 22,0 | 400 ms | 484 ms |
| 25 | 17,1 | 1 094 ms | 1 510 ms |
| 50 | 14,6 | 2 352 ms | 4 588 ms |

Durante la ráfaga, `pg_stat_activity` muestra las sesiones casi siempre en `ClientRead`: la BD espera a
la aplicación, no hay contención de locks. El cuello de botella es el **proceso único de Python**:
unos 49 ms de trabajo por evento (validación, M09, evento, paquete por trigger, bitácora RF-63 con
hash y consolidación), con el GIL. Con más concurrencia solo crece la cola.

- **Frente a RF-56:** no se incumple ninguna cifra. RF-56 no fija un caudal, y su RNF de "< 500 ms" es
  para la detección en el Edge. Cada evento Edge es una desviación detectada, no una medición, y el
  límite de 60/min por dispositivo protege al backend.
- **Por qué importa:** en una tormenta en la que muchos dispositivos reportan a la vez, el endpoint
  atiende unos 20 eventos/s. Con 50 clientes simultáneos, la latencia supera 1,5 s.
- **Fuera de alcance:** optimizar el costo por evento, o escalar procesos después de mover el limitador
  a un almacén compartido. Se propone como una tarea aparte de rendimiento. Las cifras de este entorno
  local (Docker en Windows) son orientativas; la medición válida debe hacerse en TEST con su hardware.

## Para QA

- **TC-M03-127:** el mecanismo está en `src/shared/rate_limit.py` y se aplica en el caso de uso, no en el
  router. Usar la prueba de arriba como evidencia de carga aislada, ejecutada en Linux.
- **Umbral:** 60/min por dispositivo (DEV-45), configurable. La cifra oficial le toca a Análisis.
