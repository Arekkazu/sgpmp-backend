# INC-M03-164-G71 — RF-57 E14: varias reglas simples activas a la vez (TC-M03-G71)

**RF:** RF-57, E14 ("Múltiples reglas simples activas simultáneamente") y E15 (la compuesta prevalece).
**Issue:** #742. **Depende de:** G68 (#740) y G70 (#741); esta rama parte de la de G70.
**Estado:**
- **Escenario 1** (con compuesta aplicable): implementado y verificado.
- **Escenario 2** (sin compuesta aplicable): **bloqueado**, por decisión del equipo (ver abajo).

## Causa

El caso de uso solo deduplicaba por sensor y variable (ventana de 30 min) y copiaba `reglas_activadas`.
No agrupaba lecturas de varios sensores, no absorbía las reglas simples en una compuesta y no marcaba
los eventos correlacionados. Por eso un mismo fenómeno producía varias alertas sin relación entre ellas.

## Escenario 1: con regla compuesta aplicable (implementado)

En `POST /iot/alertas` (con `origen_evento` distinto de IA), para ESTRES_TERMICO:

1. **Variable compañera.** Si el evento de temperatura (o de humedad) no trae la otra variable ni el THI en
   `correlacion_variables`, se busca la **lectura `LECTURA_VALIDA` más cercana** de la otra variable en la
   **misma área** (o el mismo dispositivo si no hay área), dentro de la **ventana de 10 min** de la regla
   (RF-57: "ventana de evaluación 10 min"). Con ella se completa la correlación y se calcula el THI con
   la fórmula NRC de G70.
2. Si se cumple la condición mínima de G70, se crea **una sola alerta ESTRES_TERMICO**:
   - **`reglas_activas`:** las reglas declaradas por el emisor, más las **dos reglas simples** como objeto
     (`{"id": "RF57_BASE_TEMPERATURA_AMBIENTAL", "nombre": "TEMPERATURA_AMBIENTAL_LEVE", "tipo":
     "REGLA_SIMPLE_RF57", "id_sensor", "id_telemetria", "valor"}`) y la **regla compuesta**
     (`{"id": "RF57_ESTRES_TERMICO", "nombre": "ESTRES_TERMICO", "tipo": "REGLA_COMPUESTA_RF57", "thi"}`).
   - **`metadato_evento.e14`:** `evento_correlacionado: true` y `lecturas_correlacionadas`, con la lectura
     compañera (id, sensor, valor y hora).
   - **Bitácora RF-63:** `REGLAS_MULTIPLES_CORRELACIONADAS`.
3. **Consolidación (E15):** si llega el evento de la otra variable (otro sensor del área) y ya hay una
   alerta compuesta del mismo tipo **abierta en el área** en los últimos 30 min, **no se crea otra**. El
   evento se consolida en la existente:
   - suma `frecuencia_evento`;
   - agrega sus reglas sin repetir las que ya están (por `id` y sensor);
   - sube la severidad si la nueva es mayor;
   - lo registra en `metadato_evento.e14.eventos_consolidados`;
   - escribe `REGLAS_MULTIPLES_CORRELACIONADAS` en la bitácora.

   La respuesta es 201 con `es_duplicado: true` y `alerta_existente_id`. Esto se serializa con un lock
   consultivo por área y tipo.

**RIESGO_HIDRICO:** su ventana es "dato puntual (sin ventana deslizante)", así que no se buscan
compañeras; la condición mínima la decide el evento con su correlación (G70). La consolidación por área sí
aplica.

## Escenario 2: sin regla compuesta aplicable (bloqueado)

E14 pide "una alerta **independiente** por cada variable, con `evento_correlacionado = true` y referencia
cruzada". El RF no define el `tipo_alerta` de una alerta simple, y el enum solo tiene tipos compuestos. En
G70 el equipo decidió **rechazar con 422** (`REGLA_COMPUESTA_NO_ACTIVADA`) los eventos que no activan su
compuesta. Por eso este escenario (HR 45 % y 19 °C, con THI por debajo de 72) **no genera alertas**.

**Para desbloquearlo** hay que definir un tipo para las alertas simples, lo que implica un valor nuevo en
`enum_tipo_alerta` (migración con aprobación del DBA). Con ese tipo:
- G70 crearía la alerta simple en lugar de responder 422.
- La marca `evento_correlacionado` y la referencia cruzada se guardarían en `metadato_evento.e14`, que es
  el mismo mecanismo de esta rama.

## Cambios

- `src/telemetry/domain/repositories/lectura_companera_port.py` (nuevo) y
  `src/telemetry/infrastructure/adapters/lectura_companera_m03_adapter.py` (nuevo, SQL sobre
  `modulo3.telemetrias` filtrado por área y ventana).
- `reglas_base_rf57.py`: `companera_faltante`, `regla_simple`, `regla_compuesta` y
  `VENTANA_ESTRES_TERMICO_MIN`.
- `AlertaRepository` (puerto e implementación): `buscar_compuesta_activa` (lock consultivo
  `rf57:compuesta:<área>:<tipo>`) y `consolidar_compuesta`. El trigger `trg_rf57_04_contenido_inmutable`
  no protege `reglas_activas` ni `metadato_evento`, así que se pueden actualizar.
- `generar_alerta_use_case.py`: `_completar_con_companera`, `_reglas_e14`, `_metadato_e14` y
  `_auditar_e14`, más la consolidación por área antes de crear la alerta.
- `alerta_router.py`: inyecta `LecturaCompaneraM03Adapter`.
- **Pruebas:** el helper `_lectura` de G68 insertaba siempre `id_variable = 9` (temperatura), también para
  los eventos de humedad. Con E14 eso crea compañeras falsas, así que ahora usa la variable del evento (en
  G68 y G70).

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_164_g71_e14.py`, sin BD: `companera_faltante`,
`regla_simple` y `regla_compuesta`.

**Pruebas de integración.** `tests/integration/test_inc_m03_164_g71_e14_reglas_multiples.py`: un
dispositivo con un sensor de temperatura y otro de humedad en la misma área, como el dispositivo 339 de QA
(sensores 525 y 526).

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_temperatura_y_humedad_en_la_ventana_generan_una_sola_compuesta` | Escenario 1 de QA: 31 °C (LEVE) y 75 % (LEVE), dos eventos | **1 alerta** ESTRES_TERMICO MODERADO (THI 83.70), `frecuencia_evento = 2`; reglas TEMPERATURA y HUMEDAD (simples), ESTRES_TERMICO y las declaradas por el emisor, sin repetir; `e14.evento_correlacionado`; 2 registros `REGLAS_MULTIPLES_CORRELACIONADAS` |
| `test_la_compuesta_registra_la_lectura_companera` | Temperatura con humedad ya ingerida | `lecturas_correlacionadas` con el sensor de humedad |
| `test_lectura_companera_fuera_de_la_ventana_no_cuenta` | Humedad de hace 15 min | 422 |
| `test_lectura_companera_de_otra_area_no_cuenta` | Humedad de otra área | 422 |
| `test_escenario_sin_compuesta_aplicable_queda_bloqueado` | Escenario 2 de QA: HR 45 % y 19 °C | 422 y 422, sin alertas (bloqueado) |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g71_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
tests/telemetry (G71 + G70 + G68 + DEV-41, DEV-49, DEV-13, DEV-30)                     175 passed
tests/integration: G71 (5) + G70 + G68 + DEV-04, DEV-30, DEV-41, DEV-43, DEV-49, DEV-17     135 passed, 6 skipped
Suite completa (sin red): 2355 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA

- **Escenario 1:** volver a ejecutarlo. Las lecturas de temperatura y humedad deben existir en la
  telemetría (RF-53) dentro de una ventana de 10 min, o el evento debe traer la otra variable en
  `correlacion_variables`.
- **Escenario 2:** queda bloqueado hasta que Análisis defina el tipo de las alertas simples.
- **`AlertaSchema`:** no agrega un campo `evento_correlacionado`. La marca viaja en `metadato_evento.e14`,
  que el detalle ya devuelve.
