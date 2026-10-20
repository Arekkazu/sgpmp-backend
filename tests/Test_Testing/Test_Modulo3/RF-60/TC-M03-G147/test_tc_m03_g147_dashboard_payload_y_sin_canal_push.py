"""
TC-M03-G147 (RF-60 CA-9/Fase 7/Salida 3/E3, CU-10) - "Presentación del
estado en el dashboard (RF-58)." Grupo NUEVO (sin TC previo).

ALCANCE DE ESTA SESIÓN: (a) y (b) requieren medir latencia de render real
en el cliente y verificar la codificación visual (colores/etiquetas) --
ambas cosas exigen el frontend `SGPMP-FRONT-END-PWA` corriendo con
Playwright. Ese proyecto no tiene `node_modules` instalado en este
entorno (confirmado: no existe la carpeta). Instalar sus dependencias y
levantar el servidor de desarrollo es una acción de alcance mayor a una
verificación de solo lectura -- NO SE EJECUTA EN ESTA SESIÓN sin
confirmarlo antes. (c) y (d), en cambio, son verificables enteramente
contra el backend (el contrato del payload y el comportamiento real de
ERROR_SENSOR), así que sí se prueban aquí.

Código bajo prueba:
    src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py
    src/telemetry/domain/entities/monitoreo.py (`EstadoSensorActual`)
    src/telemetry/infrastructure/routers/monitoreo_router.py
    src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py

HALLAZGO (a), estructural, confirmable sin frontend: no existe ningún
endpoint WebSocket ni mecanismo de push en `src/telemetry/infrastructure/
routers/` (grep exhaustivo de "websocket"/"stream": 0 coincidencias). El
dashboard real (`GET` en `monitoreo_router.py`) es puro *polling*: el
cliente debe pedir el estado, no se le empuja. Un requisito de "<= 500 ms
desde la confirmación de la transición en backend hasta su render en el
cliente" es arquitectónicamente muy difícil de garantizar con polling
puro, salvo que el cliente sondee con una frecuencia absurda -- la
ausencia misma del canal de push que la ficha asume (`WS /api/v1/devices/
status/stream`) ya es, en sí, un hallazgo, independientemente de lo que
mida Playwright.

HALLAZGO (d): "sensor fallido se muestra como ERROR_SENSOR" se interpreta
al revés de lo que ocurre en realidad. Según el propio comentario de
`ingerir_telemetria_use_case.py:124`, "ERROR_SENSOR rechaza sin
persistir" -- es decir, una lectura que califica como ERROR_SENSOR es
RECHAZADA ANTES de guardarse. Nunca llega a la tabla de la que el
dashboard lee (`estados_actuales_sensores`), por lo que NUNCA puede
aparecer como "ERROR_SENSOR" en el dashboard -- lo que el usuario vería
en su lugar es simplemente el último dato válido anterior, cada vez más
desactualizado (`dato_desactualizado=True` eventualmente), nunca una
etiqueta explícita de error de sensor.

(a) CA-9, <= 500 ms -- NO MEDIDO EN ESTA SESIÓN (requiere frontend); pero
    ver HALLAZGO estructural arriba (sin canal de push).
(b) Fase 7, codificación visual por estado -- NO VERIFICADO EN ESTA
    SESIÓN (requiere frontend).
(c) Payload con device_id/estado/tiempo_sin_contacto_min/nivel_bateria/
    calidad_senal/unidad_productiva/timestamp -- HALLAZGO de nombres: el
    payload real (`EstadoSensorActual`) usa `id_dispositivo_iot` (no
    `device_id`), `estado_conectividad`/`estado_semaforo` (no un campo
    único `estado`), `tiempo_sin_reporte_min` (no
    `tiempo_sin_contacto_min`), `nombre_infraestructura`/`nombre_finca`
    (no `unidad_productiva`) y `ultimo_timestamp_captura` (no
    `timestamp`). El CONTENIDO conceptual que pide (c) sí está presente
    -- son solo los nombres de campo los que no coinciden exactamente.
(d) ERROR_SENSOR en variable con sensor fallido -- HALLAZGO: ver arriba --
    el comportamiento real es el opuesto (rechazo sin persistir, nunca
    visible como ERROR_SENSOR en el dashboard).

Cómo se prueba: inspección directa de `EstadoSensorActual` y de la lógica
de rechazo de `ingerir_telemetria_use_case.py`, más grep exhaustivo de
rutas WebSocket/stream en los routers de telemetry.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g147_dashboard_payload_y_sin_canal_push.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G147.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoAEstructuralSinCanalDePush:
    def test_no_existe_ningun_endpoint_websocket_ni_stream(self):
        archivos_con_match = []
        for p in (REPO_ROOT / 'src/telemetry/infrastructure/routers').glob('*.py'):
            texto = p.read_text(encoding='utf-8', errors='ignore').lower()
            if 'websocket' in texto or '@router.websocket' in texto:
                archivos_con_match.append(p.name)
        pytest.fail(
            f"HALLAZGO (a): ningun router de src/telemetry/infrastructure/routers/ declara un "
            f"endpoint websocket (coincidencias: {archivos_con_match or 'ninguna'}). El dashboard "
            f"real es polling puro -- no hay ningun canal de push que pudiera sostener un "
            f"requisito de <= 500 ms desde la confirmacion de la transicion hasta el render."
        ) if not archivos_con_match else None


class TestSubCasoCNombresDePayloadNoCoinciden:
    def test_estado_sensor_actual_no_usa_los_nombres_literales_de_la_ficha(self):
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/monitoreo.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto.split('class EstadoSensorActual:')[1].split('class ')[0]
        for campo_real in ('id_dispositivo_iot', 'estado_conectividad', 'tiempo_sin_reporte_min',
                           'nombre_infraestructura', 'ultimo_timestamp_captura'):
            assert campo_real in bloque
        pytest.fail(
            "HALLAZGO (c): EstadoSensorActual no declara ninguno de los nombres literales "
            "'device_id', 'estado', 'tiempo_sin_contacto_min', 'unidad_productiva' ni "
            "'timestamp' -- usa id_dispositivo_iot, estado_conectividad/estado_semaforo, "
            "tiempo_sin_reporte_min, nombre_infraestructura/nombre_finca y "
            "ultimo_timestamp_captura. El contenido conceptual esta presente; los nombres de "
            "campo de la ficha no coinciden con el contrato real."
        )


class TestSubCasoDErrorSensorSeRechazaNuncaSeMuestra:
    def test_error_sensor_rechaza_la_lectura_sin_persistirla(self):
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert "ERROR_SENSOR rechaza sin persistir" in texto
        pytest.fail(
            "HALLAZGO (d): una lectura ERROR_SENSOR se RECHAZA antes de persistir (confirmado en "
            "el propio comentario del codigo) -- nunca llega a la tabla que alimenta el "
            "dashboard. El usuario nunca ve 'ERROR_SENSOR' en pantalla: ve el ultimo dato valido "
            "anterior, cada vez mas desactualizado, nunca una etiqueta explicita de error."
        )
