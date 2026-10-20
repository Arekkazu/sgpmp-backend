"""
TC-M03-G150 (RF-60 Salida 6/RNF-03/RNF-04/Restricción 9, CU-16) - "Métricas
de flota, disponibilidad y escalabilidad." Grupo NUEVO (sin TC previo).

Código bajo prueba: búsqueda exhaustiva en todo `src/` y en `main.py` de
cualquier endpoint o campo relacionado con M08 (`/api/v1/fleet/metrics`,
`total_dispositivos_registrados`, `total_por_estado`,
`porcentaje_disponibilidad_flota`, `dispositivos_bateria_critica`,
`dispositivos_senal_degradada`, `MTBF`, `MTTR`), más inspección directa del
único endpoint de salud real (`GET /health` en `main.py:667`).

HALLAZGO PRINCIPAL (invalida (a), (b) y (c) por ausencia de base): no existe
`/api/v1/fleet/metrics` ni ningún router de M08 registrado en `main.py`
(revisados los 50 `include_router(...)` del archivo) -- ninguno de los 7
agregados que pide la Salida 6 aparece una sola vez en todo `src/` (grep
exhaustivo, 0 coincidencias para cada nombre literal). El proxy más cercano,
`ResumenUnidadProductiva` (RF-58, ya usado en TC-M03-G147), es un resumen
POR UNIDAD PRODUCTIVA (`sensores_online`, `sensores_sin_senal`,
`sensores_con_error`), no un agregado de flota global, y tampoco tiene
ningún campo de batería crítica, señal degradada, MTBF ni MTTR. El único
endpoint de salud real que existe (`GET /health`) es un liveness check
genérico y estático (`{"status": "ok", "message": "..."}`) sin ningún
cálculo de disponibilidad, SLA ni verificación de recuperación.

(a) Salida 6 "M08 recibe los 7 agregados y la suma por estado cuadra con el
    total" -- HALLAZGO: no hay endpoint ni entidad que produzca ninguno de
    los 7 agregados. No hay nada que sumar porque no hay nada que consultar.
(b) RNF-04 "monitoreo simultáneo de 50 y 200 nodos sin degradación" --
    HALLAZGO: no puede medirse -- no existe ningún endpoint de métricas de
    flota contra el cual observar degradación. No se ejecuta carga real
    contra el entorno compartido porque el punto de medición mismo no
    existe (confirmado por análisis estático, sin necesidad de k6/Locust).
(c) RNF-03 "disponibilidad del servicio de heartbeat >= 99,5%, con
    recuperación verificada tras una caída inducida" -- HALLAZGO: el único
    endpoint de salud real (`/health`) no calcula disponibilidad de ningún
    servicio -- es un literal estático, no una medición. No hay ningún
    mecanismo de "ventana sostenida" ni de verificación de recuperación.

Nota (ya anticipada por la propia ficha, "[PENDIENTE]"): como el RF tampoco
define la fórmula de MTBF/MTTR, este TC no intenta validar valores -- y aquí
se confirma que ni siquiera hay un lugar donde esos valores pudieran existir.

Cómo se prueba: grep exhaustivo sobre src/ y main.py + inspección estática
del cuerpo literal de `GET /health` en `main.py` (no se importa `main.app`
porque arrastra una dependencia no instalada en este entorno, `audit_sdk`,
ajena a RF-60; la inspección estática es equivalente para este TC porque el
handler es un literal fijo sin lógica condicional).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g150_metricas_de_flota_no_implementadas.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G150.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
_CAMPOS_SALIDA_6 = (
    'total_dispositivos_registrados', 'total_por_estado', 'porcentaje_disponibilidad_flota',
    'dispositivos_bateria_critica', 'dispositivos_senal_degradada', 'MTBF', 'MTTR',
)


def _grep(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestSubCasoANingunAgregadoDeFlotaExiste:
    """(a): de los 7 agregados de la Salida 6, confirmar cuantos existen."""

    @pytest.mark.parametrize('campo', _CAMPOS_SALIDA_6)
    def test_campo_de_salida_6_no_existe_en_el_codigo(self, campo):
        archivos = _grep(campo)
        pytest.fail(
            f"HALLAZGO (a): '{campo}' (agregado de M08/Salida 6) no existe en ningun archivo de "
            f"src/ (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_no_existe_endpoint_fleet_metrics_en_main(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        archivos_fleet = _grep('fleet')
        pytest.fail(
            "HALLAZGO (a): no existe ningun router ni endpoint '/api/v1/fleet/metrics' -- "
            f"'fleet' no aparece en src/ (encontrados: {archivos_fleet or 'ninguno'}) ni como "
            f"include_router en main.py. M08/Salida 6 no tiene ningun punto de entrada en la API."
        ) if 'fleet' not in texto_main.lower() and not archivos_fleet else None

    def test_resumen_unidad_productiva_es_por_unidad_no_de_flota_global(self):
        """El proxy mas cercano (RF-58) es un resumen por unidad productiva,
        no un agregado de flota global, y no tiene bateria/señal/MTBF/MTTR."""
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/monitoreo.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'class ResumenUnidadProductiva' in texto
        tiene_mtbf_o_mttr = 'MTBF' in texto or 'MTTR' in texto
        tiene_bateria_o_senal_degradada = 'bateria_critica' in texto or 'senal_degradada' in texto
        pytest.fail(
            "HALLAZGO (a): ResumenUnidadProductiva (el agregado mas cercano que existe, usado en "
            "RF-58/G147) es un resumen POR UNIDAD PRODUCTIVA (total_sensores, sensores_online, "
            "sensores_sin_senal, sensores_con_error) -- no un agregado de FLOTA GLOBAL como pide "
            "la Salida 6, y no declara ningun campo de bateria critica, senal degradada, MTBF ni "
            "MTTR."
        ) if not tiene_mtbf_o_mttr and not tiene_bateria_o_senal_degradada else None


class TestSubCasoBYCRnf03Rnf04SinPuntoDeMedicion:
    """(b)/(c): RNF-03/RNF-04 no pueden medirse porque el punto de medicion
    (endpoint de metricas de flota / disponibilidad de heartbeat) no existe.
    No se ejecuta carga real contra el entorno compartido -- se confirma por
    analisis estatico que no hay nada que medir."""

    def test_health_check_es_un_literal_estatico_sin_calculo_de_disponibilidad(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        assert '@app.get("/health"' in texto_main
        assert '{"status": "ok", "message": "API funcionando correctamente"}' in texto_main
        assert 'disponibilidad' not in texto_main.lower()
        assert 'uptime' not in texto_main.lower()
        pytest.fail(
            "HALLAZGO (c): GET /health devuelve un literal estatico ({'status': 'ok', ...}) sin "
            "ningun calculo real de disponibilidad del servicio de heartbeat, sin ventana "
            "sostenida y sin ningun mecanismo de verificacion de recuperacion tras una caida. "
            "RNF-03 (>= 99,5% de disponibilidad) no tiene como demostrarse porque no hay ninguna "
            "metrica de disponibilidad detras de este endpoint."
        )

    def test_rnf04_no_tiene_endpoint_de_metricas_contra_el_cual_medir_degradacion(self):
        archivos_fleet = _grep('fleet')
        pytest.fail(
            "HALLAZGO (b): RNF-04 pide verificar que el monitoreo de 50 y 200 nodos no degrade "
            "los tiempos de deteccion ni el ciclo de 60 s -- pero no existe ningun endpoint de "
            "metricas de flota (confirmado arriba) contra el cual observar esa degradacion. "
            "Ejecutar una carga real de 200 nodos contra el entorno TEST compartido no resolveria "
            "nada: no hay ningun agregado que leer al final de la prueba. Se requiere primero que "
            "M08/Salida 6 exista antes de poder diseñar un TC de carga con un resultado esperado "
            "verificable."
        ) if not archivos_fleet else None
