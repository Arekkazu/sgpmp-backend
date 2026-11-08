"""
TC-M04-G104 (RF-71 v2.0 Fase 1/Restricción 11/CA-9/RNF-06/RFC-009, CU-02)
- "Activación por trigger DEGRADACION: las DOS familias de criterio
introducidas por la RFC-009 v1.1." Reescrito por RFC-009 -- reemplaza la
versión anterior, que probaba un solo criterio.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): `modo_generacion`,
`CALIBRACION_EN_SITIO`, `score_anomalia` y `calibration_readiness` no
existen en ningún lado (confirmado en G102).

Código bajo prueba: `modulo4.sp_evaluar_degradacion_modelo` en el DDL
baseline (la única pieza de lógica de degradación que existe, aunque sea
dormida -- ver TC-M04-G104 de la ronda anterior).

HALLAZGO CENTRAL, el cruce de familias que la propia ficha señala como
más importante: la ÚNICA implementación de evaluación de degradación que
existe (`sp_evaluar_degradacion_modelo`) **no distingue tipo_modelo en
absoluto**. Su firma recibe `p_id_version_modelo` y aplica siempre el
mismo criterio -- `IF v_f1_score < 0.80` -- sin ninguna rama condicional
por tipo. Si esta pieza de código dormida se activara hoy, literalmente
reproduciría el defecto que (g) y (h) piden verificar que NO ocurra: un
modelo POBLACIONAL evaluado con el criterio de f1_score, y la regla de
100 registros verificados aplicada también a POBLACIONAL (0 registros
verificados bloquearía la evaluación poblacional en lugar de dejarla
proceder). No es solo que falte la implementación de la Familia 2 -- es
que el único código existente, de activarse tal cual está, fallaría
exactamente los dos subescenarios más críticos de este TC.

FAMILIA 1 (f1_score, INDIVIDUAL/META):
(a)/(b)/(c) -- Las fronteras de f1 (0,7999/0,80/0,8001) y de ground
    truth (99/100) siguen siendo correctas en el SQL dormido (ya
    confirmado en la ronda anterior) -- pero el procedimiento nunca se
    invoca desde código alcanzable (G102/G103).
FAMILIA 2 (score_anomalia, POBLACIONAL):
(d)/(e)/(f) -- HALLAZGO: no existe ningún código, ni dormido, que
    evalúe deriva de `score_anomalia`, tasa de falsos positivos en
    rutina, ni vencimiento de calibración. La Familia 2 completa no
    tiene ninguna implementación, ni siquiera parcial.
CRUCE DE FAMILIAS:
(g) f1_score_global < 0,80 sobre un modelo POBLACIONAL NO debe activar
    el trigger -- HALLAZGO: el único código existente lo activaría
    igual, porque no distingue tipo_modelo.
(h) La regla de 100 registros NO debe aplicar a POBLACIONAL -- HALLAZGO:
    el único código existente la aplicaría igual, por el mismo motivo.
COMUNES:
(i)/(j)/(k) -- NO EVALUABLES: dependen de un proceso que nunca se
    dispara (G102/G103); el catálogo de auditoría tampoco distingue
    familia ni criterio (ver TC-M04-G120).

Cómo se prueba: inspección directa de la firma y el cuerpo de
`sp_evaluar_degradacion_modelo` en el DDL baseline, confirmando la
ausencia de cualquier rama condicional por tipo_modelo.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g104_dos_familias_de_degradacion_no_implementadas.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G104.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


def _bloque_procedimiento() -> str:
    inicio = DDL.index('CREATE PROCEDURE modulo4.sp_evaluar_degradacion_modelo')
    fin = DDL.index('ALTER PROCEDURE modulo4.sp_evaluar_degradacion_modelo', inicio)
    return DDL[inicio:fin]


class TestCruceDeFamiliasElUnicoCodigoExistenteFallariaAmbos:
    def test_el_procedimiento_no_recibe_ni_distingue_tipo_modelo(self):
        bloque = _bloque_procedimiento()
        firma = bloque.split('(')[1].split(')')[0]
        pytest.fail(
            f"HALLAZGO (g)/(h): la firma real es "
            f"sp_evaluar_degradacion_modelo({firma}) -- no recibe tipo_modelo y no tiene "
            f"ninguna rama condicional por tipo. De activarse tal cual, aplicaria el criterio "
            f"de f1_score y la regla de 100 registros a CUALQUIER modelo, incluido uno "
            f"POBLACIONAL -- exactamente el defecto que (g) y (h) piden verificar que no "
            f"ocurra."
        ) if 'tipo_modelo' not in firma else None

    def test_la_condicion_de_f1_se_aplicaria_sin_distincion(self):
        bloque = _bloque_procedimiento()
        assert 'IF v_f1_score < 0.80 THEN' in bloque
        assert 'POBLACIONAL' not in bloque

    def test_la_regla_de_100_registros_se_aplicaria_sin_distincion(self):
        bloque = _bloque_procedimiento()
        assert 'IF v_count_verificados < 100 THEN' in bloque


class TestFamilia2PoblacionalSinImplementacion:
    @pytest.mark.parametrize('termino', ['score_anomalia', 'tasa_falsos_positivos', 'vencimiento_calibracion'])
    def test_criterio_poblacional_no_existe_ni_dormido(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d)/(e)/(f): '{termino}' no existe en src/ (encontrados: "
            f"{archivos or 'ninguno'}) ni en el DDL baseline -- la Familia 2 completa "
            f"(POBLACIONAL) no tiene ninguna implementacion, ni siquiera dormida."
        ) if not archivos and termino not in DDL else None
