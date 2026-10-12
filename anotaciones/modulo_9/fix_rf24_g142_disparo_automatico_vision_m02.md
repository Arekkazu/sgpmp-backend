# RF-24 VISION — disparo automático desde M02 (#551, G142: TC-M09-288/289)

## Síntoma

El alta de un lote (`POST /activos-biologicos`) y el cierre de ciclo
(`POST /activos-biologicos/{id}/cierre`) no recalibraban la línea base por visión.
No quedaba calibración `AUTOMATICO`, ni línea base, ni evento RF-10. La integración
M02 → M09 no existía: `OrigenDisparo.AUTOMATICO` estaba declarado pero nadie lo usaba.

## Cambio

**M02** (`src/biological_assets/`)
- Puerto `domain/repositories/recalibracion_vision_port.py` con un solo método, `solicitar(id_infraestructura, momento, motivo)`.
- `RegistrarActivoBiologicoUseCase` lo llama tras el commit del alta de un lote **POBLACIONAL**.
- `CerrarCicloUseCase` lo llama tras el commit del cierre de ciclo de un lote **POBLACIONAL**.
- Un INDIVIDUAL no dispara nada, y un alta o cierre rechazado tampoco.
- Adaptador `infrastructure/adapters/recalibracion_vision_m09_adapter.py`. Agenda el cálculo
  en `BackgroundTasks`, con el mismo patrón que las notificaciones de M01.
- El cálculo corre después de la respuesta, con una sesión propia del **usuario de servicio** (D1).
  Las tablas VISION ya tienen las políticas `pol_*_servicio`, y el servicio queda vinculado a
  toda finca nueva por `trg_despues_insertar_finca`.
- Un fallo en M09 nunca afecta el 201/200 de M02.

**M09** (`CalibrarVisionUseCase.execute_automatico`)
- Valores de la calibración automática:
  - `origen_disparo = AUTOMATICO`
  - `id_usuario = NULL`
  - `fecha_calibracion` = momento del evento
  - `observaciones` = motivo, por ejemplo "Disparo automático M02: nuevo lote 792"
- El evento RF-10 lo firma el usuario de servicio, porque `modulo1.eventos.id_usuario` es
  NOT NULL. `detalle.origen_disparo = AUTOMATICO`.
- Si el área no calibra por visión (sin especie, sin modelo POBLACIONAL o sin cámaras
  activas), el disparo **no aplica**. No guarda nada ni audita.
- En los demás casos el flujo es el del manual:
  - EXITOSA: publica la línea base.
  - FALLIDA o NO_CONVERGIDA: queda en el historial y conserva la línea base vigente.
  - Sin ninguna observación apta: VISION_NO_DISPONIBLE auditado.
- Manual y automático comparten el núcleo `_guardar`. El manual no cambia de comportamiento.

Sin migración ni cambios de BD.

## Decisiones para Análisis

1. **Ventana de observación del disparo automático: los 7 días anteriores al evento**
   (`VENTANA_DISPARO_AUTOMATICO`). La ficha solo dice "ventana de muestreo" y no fija su
   tamaño. Cambiarla es una constante.
2. **Áreas sin visión: el disparo no deja rastro.** La mayoría de altas y cierres de M02 son de
   áreas sin cámaras. Auditar cada uno como rechazo llenaría RF-10 de eventos sin valor.
3. **Solo lotes POBLACIONAL.** La ficha habla de "nuevo lote" y de "fin de ciclo", y VISION
   solo aplica al paradigma POBLACIONAL.
4. **Es asíncrono.** La calibración aparece justo después de la respuesta de M02, en el mismo
   proceso, sin cola externa. Un mismo evento de M02 la dispara una sola vez: un cierre
   repetido responde 409 antes, y cada alta es un lote nuevo.

## Verificación

- **Unitarias:** `tests/configuration/test_inc_m09_75_g142_disparo_automatico_vision.py`, 9 pruebas:
  - éxito automático;
  - 4 variantes de área sin visión;
  - N−1 FALLIDA conservando la línea base vigente;
  - alta de lote vs alta individual;
  - cierre de lote;
  - cierre rechazado.
- **Suites `tests/biological_assets` y `tests/configuration`:** 967 passed. El único fallo
  (`test_ingreso_fecha_futura_lanza_validation_error`) también falla en dev.
- **De punta a punta en Postgres 17 desechable** (`alembic upgrade head`, transacción con
  rollback, adaptador real con `SET ROLE sgpmp_app`, es decir, bajo RLS y como el usuario
  de servicio):
  - 40 aptas → `EXITOSA`, `AUTOMATICO`, `id_usuario NULL`, línea base vigente, evento 30
    `exitoso` firmado por el servicio.
  - 29 aptas → `FALLIDA`/`FILTRADO`, `json_linea_base IS NULL`, sin línea base nueva, evento 29
    `fallido` `LINEA_BASE_NO_CALCULADA`.
- **Integración M02 de alta y cierre:** los mismos 3 fallos de entorno en dev y en la rama
  (catálogos y `app.usuario_id` en una BD recién creada). No hay regresión.
