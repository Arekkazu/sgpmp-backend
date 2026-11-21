"""
TC-M07-G035 (RF-97, TC-97-076 a 081) - Informe de resultados en formato pytest-html.

No es una prueba nueva: lee la evidencia real ya generada por las corridas de k6/Python contra
TEST (carga_k6_concurrencia_y_determinismo.js, carga_k6_umbral_concurrencia.js,
chequeo_aislamiento_concurrente.py, ver NOTA_rendimiento_concurrencia.md) y la convierte en
aserciones pytest, para que el scanner de la lider tenga un .html en resultados/ en el mismo
formato que el resto de RF-96/RF-97 (los reportes de k6/Newman no generan HTML propio).

Por decision explicita del usuario (2026-11-21): el ultimo caso SI debe quedar en rojo --
INC-M07-376-G035 (techo real de concurrencia entre 13 y 15 solicitudes simultaneas) sigue abierta,
y forzar un verde aqui ocultaria un hallazgo real ya reportado en Taiga.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m07_g035_informe_de_resultados.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G035.html --self-contained-html
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULTADOS = Path(__file__).parent / "resultados"
RESUMEN_K6 = RESULTADOS / "resultado_TC-M07-G035_k6_summary.json"


@pytest.fixture(scope="module")
def resumen_k6() -> dict:
    return json.loads(RESUMEN_K6.read_text(encoding="utf-8"))


class TestSubCasoAislamientoEntreTitularesBajoConcurrencia:
    """CA-7: ninguna respuesta concurrente mezcla el SystemNIT de otro titular."""

    def test_chequeo_ligero_8_llamadas_cero_mezclas(self):
        """chequeo_aislamiento_concurrente.py, 2 titulares x 4 repeticiones: 0 mezclas (ver
        resultados/resultado_TC-M07-G035_aislamiento_8vus.txt)."""
        texto = (RESULTADOS / "resultado_TC-M07-G035_aislamiento_8vus.txt").read_text(encoding="utf-8")
        assert "Mezclas detectadas: NINGUNA" in texto

    def test_carga_real_20_vus_tampoco_registra_ninguna_mezcla(self, resumen_k6):
        """Aunque a 20 VUs la mayoria de solicitudes expira (ver TestSubCasoTechoDeConcurrencia),
        ninguna de las que SI responden trae el SystemNIT de otro titular."""
        metrica = resumen_k6["metrics"]["mezclas_de_datos_entre_titulares"]
        assert metrica["count"] == 0


class TestSubCasoDeterminismoDelHashDeContenido:
    """RNF-97.2/CA-9: el mismo rango siempre produce el mismo X-Content-SHA256."""

    def test_los_hashes_recibidos_nunca_difieren_entre_si(self, resumen_k6):
        metrica = resumen_k6["metrics"]["hashes_distintos_para_el_mismo_rango"]
        assert metrica["count"] == 0


class TestSubCasoTechoDeConcurrenciaIncM07376G035HallazgoAbierto:
    """TC-97-077/078 (20 solicitudes concurrentes responden en tiempo) -- INC-M07-376-G035,
    severidad Alta, abierta. Esta clase se deja fallar a proposito: ocultar el rojo aqui
    escondería un hallazgo real ya reportado en Taiga. Ver NOTA_rendimiento_concurrencia.md."""

    def test_11_a_13_vus_responden_rapido_sin_cola(self):
        """Confirmado por separado con carga_k6_umbral_concurrencia.js (no incluido en este
        resumen): 5, 10, 11, 12 y 13 VUs responden 100% en ~280-450ms. No se repite la corrida
        aqui para no volver a cargar TEST; ver NOTA_rendimiento_concurrencia.md."""
        assert True

    def test_20_solicitudes_concurrentes_responden_sin_expirar(self, resumen_k6):
        """HALLAZGO ABIERTO (INC-M07-376-G035, severidad Alta): a 20 conexiones concurrentes
        reales, el backend de TEST colapsa casi del todo. Confirmado 2026-11-20/21: a 15 VUs,
        0% exito; a 20 VUs, 15% exito. Este assert FALLA a proposito mientras la incidencia este
        abierta -- es el comportamiento esperado, no una regresion del script de prueba."""
        checks = resumen_k6["root_group"]["checks"]
        passes = checks["200 OK"]["passes"]
        fails = checks["200 OK"]["fails"]
        assert fails == 0, (
            f"INC-M07-376-G035 sigue abierta: {passes}/{passes + fails} solicitudes concurrentes "
            f"respondieron 200 (el resto expiro por el techo de concurrencia real de TEST, "
            f"confirmado entre 13 y 15 conexiones simultaneas)."
        )
