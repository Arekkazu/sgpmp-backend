# TC-M02-G33 — Resultado de ejecución

**Estado general: BLOQUEADO — 0/2 sub-casos pudieron completarse. 3/6 assertions PASS, 3/6 FAIL vía Postman/Newman
contra el backend TEST desplegado.** Ambos bloqueos tienen causa raíz documentada — ver `NOTA_BLOQUEO.md`.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G33 (agrupa TC-M02-039 y TC-M02-042) |
| RF / CU | RF-37 / CU-02 — Gestión de Fases del Ciclo Productivo |
| Endpoints | `POST /activos-biologicos/{id_activo}/fases` · `GET /activos-biologicos/{id_activo}/fases` |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta | `admin.test@sgpmp.com.co` |
| Activo de prueba | `id_activo_biologico=201`, especie 2 (Trucha Arcoíris) |
| Fecha de ejecución | 2026-09-10, ~00:30 UTC |
| Herramienta | Newman 6.2.2 + htmlextra 1.23.1 |

## TC-M02-039 — Registrar cambio de fase estándar válido

**BLOQUEADO — mismo defecto que INC-M02-37-01.**

```json
// POST /activos-biologicos/201/fases
// {"id_ciclo_productiva": 2, "motivo_cambio": "Inicio de ciclo estandar - QA-G33"}
// HTTP 500
{"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.","fields":[]}
```

Se usó `id_ciclo_productiva=2` — el mismo ID documentado en `anotaciones/modulo_2/curls_m02_cu02_activo_individual.md`
como "Ciclo completo trucha 2025-A", y el activo de prueba se registró deliberadamente con `id_especie=2` (Trucha)
para que coincidiera exactamente con la especie de ese ciclo — descartando que el 500 se deba a un descalce de
especie en vez de al bug real ya diagnosticado en `tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/NOTA_BLOQUEO.md`.

`GET /activos-biologicos/201/fases` posterior confirma `{"fases":[]}` — ninguna fase llegó a crearse, consistente
con que el `INSERT` nunca se ejecuta (el `TypeError` ocurre antes, en la llamada a `cerrar_gestion_activa`).

## TC-M02-042 — Aceptar transición no estándar con confirmación explícita

**BLOQUEADO por el mismo defecto, y adicionalmente por un gap estructural independiente.**

```json
// POST /activos-biologicos/201/fases
// {"id_ciclo_productiva": 2, "motivo_cambio": "...", "confirmacion_no_estandar": true, "fase_destino_id": 9999}
// HTTP 500 (mismo error_code y mensaje que TC-M02-039)
```

Confirmado por lectura de código (`cambiar_fase_dto.py`): el DTO no declara `confirmacion_no_estandar` ni
`fase_destino_id` — estos campos se descartan en silencio antes de llegar al use case, que de todas formas
**siempre** avanza automáticamente a la siguiente fase de la secuencia, sin ninguna lógica de "salto" ni de
"confirmación". Esto significa que **incluso si INC-M02-37-01 se corrige, TC-M02-042 seguirá sin poder pasar** —
requiere una extensión de diseño (nuevos campos + lógica de validación), no un fix de una línea. Detalle en
`NOTA_BLOQUEO.md`, sección 2.

## Resumen de assertions

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login admin (200) | PASS |
| 2 | Setup: activo INDIVIDUAL creado (201) | PASS |
| 3 | **TC-M02-039: transición estándar → 201** | **FAIL — obtuvo 500** |
| 4 | GET historial de fases → 200 | PASS |
| 5 | **El historial refleja la fase creada** | **FAIL — `fases: []`, no se creó ninguna** |
| 6 | **TC-M02-042: transición no estándar confirmada → 201** | **FAIL — obtuvo 500** |

## Evidencia

- [Colección Postman](../TC-M02-G33.postman_collection.json)
- [Nota de bloqueo](../NOTA_BLOQUEO.md)
- [Reporte Newman HTML](newman-TC-M02-G33.html)
- [Reporte Newman JSON](newman-TC-M02-G33.json)

## Conclusión

TC-M02-G33 no pudo verificar ninguno de sus dos sub-casos por dos motivos distintos y ya diagnosticados:

1. **INC-M02-37-01** (ya reportado desde TC-M02-G23): bloquea TC-M02-039 por completo y es la causa inmediata del
   500 en TC-M02-042 también. Fix de una línea, ya identificado.
2. **Gap estructural nuevo, exclusivo de TC-M02-042**: la API no tiene ningún mecanismo para expresar "transición
   fuera de secuencia" ni "confirmación explícita" — el DTO no declara esos campos y el use case no tiene lógica
   para ellos. Este es un hallazgo de diseño, no un bug puntual; requiere que Desarrollo decida el contrato antes
   de implementarlo.

Una vez corregido (1), este caso debe re-ejecutarse: TC-M02-039 debería pasar a PASS de inmediato; TC-M02-042
seguirá en FAIL hasta que se resuelva (2).
