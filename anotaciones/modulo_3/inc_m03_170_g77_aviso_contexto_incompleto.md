# INC-M03-170-G77 — El administrador no recibe el aviso de contexto incompleto (RF-57 E6, TC-M03-N21)

**RF:** RF-57 E6 ("Se genera notificación al administrador para que complete la asociación del sensor
(RF-22)") y CA-7. **Issue:** #749.
**Estado:** corregido y verificado con PostgreSQL real. El defecto se **reproduce** en `dev` y se corrige en
esta rama.

## Causa

El aviso **sí existía**: DEV-32, `NotificarAlertasUseCase`, el worker que cada 10 s notifica las alertas
nuevas. Pero se enviaba con **anti-spam** (`agrupable=True`), y el anti-spam de `NotificacionService`
filtra por **usuario + tipo de evento + canal** en una ventana de 5 minutos.

El aviso de E6 usa el mismo tipo de evento (32, `NOTIFICACION_ALERTA`) que las notificaciones normales de
alertas. Por eso, si el administrador había recibido **cualquier** notificación de alerta en los 5 minutos
anteriores, el aviso se **descartaba en silencio**. Pasaba lo mismo con el segundo sensor sin asociación
dentro de la misma vuelta. Eso explica el caso de QA: la alerta 278 de G76, en el mismo run, dejó una
notificación de alerta, y los avisos de las alertas 289 y 290 se perdieron. El total del administrador se
quedó en 723.

## Solución

- **Sin anti-spam:** el aviso de E6 sale con `agrupable=False`, así que otras notificaciones de alerta no lo
  tapan.
- **Sin inundar al administrador:** **un aviso por sensor cada 24 horas** (el RF no fija la frecuencia).
  - **Misma vuelta:** dentro de una vuelta del worker, varias alertas del mismo sensor generan un solo aviso.
  - **Vueltas siguientes:** si otra alerta sin contexto del mismo sensor ya se notificó en las últimas 24 h
    (`AlertaRepository.contexto_incompleto_avisado_desde`, sobre `modulo3.alertas`), no se repite.
- **Sin cambios:** el destinatario (los administradores, `fn_rol_protegido`), el texto y el canal (bandeja
  INTERNA, más correo).

**Latencia:** el aviso lo envía el worker de notificaciones cada **10 s**. Para verificarlo, QA debe
consultar `GET /notificaciones` unos segundos después de crear la alerta, no en el mismo instante.

## Cambios

- `notificar_alertas_use_case.py`: aviso sin anti-spam, `_avisar_contexto` y `VENTANA_AVISO_CONTEXTO`.
- `AlertaRepository` (puerto e implementación): `contexto_incompleto_avisado_desde`.
- `tests/telemetry/test_dev32_rf57_notificaciones.py`: la prueba de E6 afirmaba `agrupable=True`, que es
  justo el defecto. Ahora exige `False`, y el doble del repositorio implementa el método nuevo.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_170_g77_aviso_contexto_incompleto.py`, sin BD:
- **Envío:** el aviso no usa anti-spam.
- **Una vuelta:** un aviso por sensor, y la consulta de 24 h usa la ventana correcta.
- **24 horas:** un sensor ya avisado no se repite.
- **Alerta sin sensor:** siempre avisa.

**Pruebas de integración.** `tests/integration/test_inc_m03_170_g77_aviso_contexto_incompleto.py`, con el
worker real (`NotificarAlertasUseCase` y el adaptador RF-14) contra PostgreSQL real:

| Prueba | Escenario | Rama | `dev` (sin la corrección) |
|---|---|---|---|
| `test_n21_aviso_llega_aunque_haya_otra_notificacion_de_alerta_reciente` | **Caso de QA:** el administrador acaba de recibir otra notificación de alerta | 1 aviso | **0 avisos** (`assert 0 == 1`) |
| `test_un_aviso_por_sensor_en_la_misma_vuelta_y_otro_sensor_tambien_avisa` | 2 alertas del sensor A y 1 del B | (1, 1) | **(1, 0)**: se perdía el aviso del B |
| `test_no_se_repite_el_aviso_del_mismo_sensor_en_24_horas` | Otra alerta del mismo sensor en la vuelta siguiente | 1 aviso | 1 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g77b_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G77 E6 + DEV-32)                                       11 passed
Integración (G77 E6 + DEV-32)                                     4 passed
Misma integración sobre dev (sin la corrección)                   2 failed, 1 passed  ← reproduce el defecto
Suite completa (sin red): 2268 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA

- **TC-M03-N21:** crear la alerta sin contexto, esperar unos **10 s** (lo que tarda la vuelta del worker) y
  consultar `GET /notificaciones` del administrador. Llega una notificación "Alerta sin contexto de activo
  biológico", con el sensor que hay que asociar.
- **Repeticiones:** un segundo evento del mismo sensor dentro de 24 h no genera otro aviso; otro sensor, sí.
