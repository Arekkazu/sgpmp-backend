# INC-M03-246-G88 (#889) — RF-58: semáforo, tolerancia T y recálculo

## Causa

- `fn_actualizar_estado_sensor` deja `estado_semaforo = 'VERDE'` en la caché
  `modulo3.estados_actuales_sensores` para toda lectura con umbral, sin evaluar el
  valor. Solo `ReclasificarSemaforoUseCase` lo corregía, y solo cuando la lectura
  se vinculaba a un activo. Una lectura `FUERA_DE_RANGO` de un sensor de área
  quedaba VERDE (TC-M03-170/171).
- La tolerancia T existía como `SemaforoCalculator.calcular(tolerancia_pct=10)`
  pero ningún flujo la usaba ni había dónde configurarla (TC-M03-172).
- Como el color se fijaba al ingerir, editar el umbral no lo recalculaba
  (TC-M03-266).

## Decisión

El semáforo del dashboard se calcula en cada consulta con:

1. La última lectura del sensor (válida o `FUERA_DE_RANGO`; `ERROR_CALIBRACION`
   no trae un valor confiable y conserva la caché).
2. Los umbrales RF-17 activos **hoy** de las especies del área para la variable
   (con varias especies, el peor color).
3. `SemaforoCalculator.calcular_rf58`:
   - Dentro de `[valor_min, valor_max]`: la banda RF-17 (normal → VERDE,
     precaución → AMARILLO, crítico → ROJO).
   - Fuera: AMARILLO si la distancia al borde es menor que T; ROJO si la alcanza
     o la supera.
   - T = `umbrales_ambientales.tolerancia_semaforo` (en la unidad del umbral) o,
     si es NULL, el 10 % del rango (lo que ya hacía `calcular`).

El historial (RF-59) usa la misma función para que dashboard e historial
coincidan. El conteo del semáforo y el estado general de la unidad usan el mismo
cálculo (ver también G92).

## BD

Migración `b7d2e4f6a813`:

```sql
ALTER TABLE modulo9.umbrales_ambientales ADD COLUMN tolerancia_semaforo NUMERIC(5,2);
ALTER TABLE modulo9.umbrales_ambientales ADD CONSTRAINT ck_umbral_ambiental_tolerancia_semaforo
    CHECK (tolerancia_semaforo IS NULL OR tolerancia_semaforo >= 0);
```

## API

`POST /configuracion/umbrales` y `PATCH /configuracion/umbrales/{id}` aceptan
`tolerancia_semaforo` (opcional, ≥ 0). En el PATCH, omitir el campo conserva la
T vigente y `null` vuelve al 10 % del rango. Las respuestas traen
`tolerancia_semaforo` y `tolerancia_semaforo_efectiva`.

`GET /iot/monitoreo/dashboard` agrega `valor_condicion_actual` por sensor: el
valor de la última lectura con el que se calculó el color (difiere de
`ultimo_valor`, que sigue siendo la última lectura válida, cuando la última es
`FUERA_DE_RANGO`).

```bash
curl -X PATCH "$API/configuracion/umbrales/95" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"valor_min":15,"valor_max":30,"tolerancia_semaforo":2,"niveles":[...],"fecha_actualizacion":"..."}'
# 200 {"tolerancia_semaforo":"2.00","tolerancia_semaforo_efectiva":"2.00",...}
# 422 si tolerancia_semaforo < 0
```

## Pruebas

- `tests/integration/test_inc_m03_246_g88_semaforo_tolerancia.py`: 13.65/14.85/30.15/31.35
  → AMARILLO, 13.35/31.65 → ROJO (umbral 15-30), T=2 y recálculo 15-30 → 25-30 sin
  lectura nueva; GRIS y "Sin umbral configurado" se conservan.
- `tests/integration/test_inc_m03_246_g88_tolerancia_umbral_m09.py`: T se persiste,
  se conserva en el PATCH sin el campo y se rechaza si es negativa.
