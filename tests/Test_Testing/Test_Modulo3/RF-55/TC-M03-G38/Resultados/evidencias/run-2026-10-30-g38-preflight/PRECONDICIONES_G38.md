# Precondiciones G38 — 2026-10-30 (solo lectura)

Contrato firmware: `_consultas/EDGE-FIRMWARE-SGPMP` `origin/develop` `e618a75` / `raspberry/scripts/casos_rf55.json`.  
Agente en Pi: heartbeat `v0.4.0-rc.2` (mismo tag). Escenarios **no ejecutados**.

Leyenda: **LISTO** = se puede correr cuando se autorice la fase 2, con las dependencias ya cubiertas. **NO LISTO** = falta algo comprobado.

## MQTT / observabilidad

| Pregunta | Estado |
|---|---|
| Monitor CONNECT | Sí (rc 0, usuario `sgpmp_gateway_test`) |
| SUB Gateway y nodo | Sí (Granted QoS 1 sobre `#`) |
| HEARTBEAT reciente | Sí, 14:47–14:48 UTC (no en la ventana 14:56) |
| ACK_UMBRAL observable | ACL sí (`status` está bajo `#`). **No se recibió ningún ACK** en las ventanas de 60 s; no hay prueba de tráfico de ACK en reposo |
| Evento `ERROR_CONFIGURACION` observable | Igual: topic `evento` cubierto por `#`; **cero eventos** observados |

## Restauración

**No hay procedimiento seguro operativo:** no existe copia de `umbrales.json` del laboratorio. Ver `PLAN_RESTAURACION.md`.

## Escenarios

### TC-M03-095 — E2, E3, E4

| ID | Contrato (`casos_rf55.json`) | ¿Listo? | Dependencias que faltan |
|---|---|---|---|
| E2 | Comando T `valor_min=valor_max=0` y bandas de ancho 0 → 1 `ACK_UMBRAL` ERROR; no clasifica T | **NO LISTO** | Publicar comando (fase 2). Respaldo de umbrales para no dejar el lab inconsistente si el firmware no rechazara. Umbrales actuales **desconocidos** |
| E3 | Banda `precaucion` ancho 0 (`24–24`) → ACK ERROR | **NO LISTO** | Igual que E2 |
| E4 | Límite 0 con bandas de ancho > 0 es **válido**; T=9 → `DESVIACION_SIMPLE` CRITICO | **NO LISTO** | **Persiste** umbral 0–10 °C. Sin respaldo no se puede devolver el original. Hace falta inyectar lecturas 0 °C y 9 °C (fake/lora no leídos) |

E2/E3 no deberían escribir disco si `handle_umbral` rechaza; E4 sí escribe. Monitor MQTT ya puede ver `status` y `evento`.

### TC-M03-122 — E5, E6

| ID | Contrato | ¿Listo? | Dependencias que faltan |
|---|---|---|---|
| E5 | Solo banda `normal` 18–32 → ACK ERROR; T=35 no clasifica | **NO LISTO** | Publicar comando (fase 2). Mismas observaciones de respaldo |
| E6 | `umbrales_guardados`: mismo JSON incompleto **ya en el store**; T=35 y T=36 → un `ERROR_CONFIGURACION` con `severidad_invalida: true`, motivo de niveles, **sin** `severidad`, **sin** inventar CRITICO; 2.ª emisión LOCAL | **NO LISTO** | Condición especial (no se tocó la Pi): el comando MQTT **no** puede dejar ese umbral (es E5). Hay que colocar el JSON incompleto en `UmbralStore` (disco + recarga de memoria: el store solo lee el archivo al **arrancar**). Eso implica sudo y, en la práctica, reinicio del agente. `EDGE_SOURCE` / variables fake **no leídos**. Sin umbrales originales no hay vuelta atrás |

### TC-M03-083 — E1, S8

| ID | Contrato | ¿Listo? | Dependencias que faltan |
|---|---|---|---|
| E1 | Store **solo** con umbral de `frecuencia_respiratoria`; 3 pares T=30 + FR=50 → un `ERROR_CONFIGURACION` por T y `DESVIACION_SIMPLE` MODERADO por FR; no bloquea siguientes | **NO LISTO** | Contenido actual de `umbrales.json` desconocido (puede haber ya umbral de T). Hace falta aplicar/retirar umbrales (MQTT o disco). Variables T y FR no vistas en telemetría |
| S8 | Lectura `humedad_suelo=99` → `esperado_sin_umbral` | **NO LISTO** | Catálogo TEST `GET /configuracion/variables-ambientales` = **401**. Heartbeat solo lista `rf55_2`, no `humedad_suelo`. `EDGE_FAKE_VARIABLES` no leído. **No se puede afirmar que S8 exista en el catálogo real** |

## Interferencia

Journal: no hay `Comando` el 2026-10-30 en las líneas visibles. Dos conexiones MQTT ESTAB desde la Pi; el segundo peer no está identificado.

## Autorización pendiente para fase 2

- sudo lectura/copia de `umbrales.json` **antes** de mutar.
- JWT de lectura de umbrales/catálogo (si se acepta el POST de login).
- Publicación MQTT / comandos Gateway.
- Para E6: escritura controlada en disco + recarga de memoria (reinicio).
- Restauración explícita después de E4/E1/E6.
