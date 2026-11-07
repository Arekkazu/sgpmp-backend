# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-03 | HulkyZeus        | TC-M04-G104 RF-71: reconstruye el test desde su reporte HTML       |
"""
TC-M04-G104 (RF-71) - Dos familias de degradacion (supervisada y POBLACIONAL)
no implementadas: `modulo4.sp_evaluar_degradacion_modelo` es unico y no
distingue por `tipo_modelo`.

NOTA DE PROCEDENCIA (2026-11-03): el archivo original nunca se versiono; solo
se subio su reporte (resultados/resultado_TC-M04-G104.html). Este archivo se
RECONSTRUYO desde ese reporte (6 tests: 2 fallidos con codigo completo + 4 que
PASARON).
  - Aserciones y mensajes de los 2 tests que fallan: copia del reporte.
  - Cuerpo de los tests que pasan, y los helpers `DDL` / `_bloque_procedimiento`:
    reconstruccion razonable, NO el original.
Si Juan Pablo conserva el original, debe prevalecer sobre este.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
    encoding='utf-8', errors='ignore')


def _bloque_procedimiento() -> str:
    m = re.search(
        r'CREATE PROCEDURE modulo4\.sp_evaluar_degradacion_modelo\(.*?\n\s*\$\$;', DDL, re.DOTALL)
    assert m, 'No se encontro modulo4.sp_evaluar_degradacion_modelo en el DDL baseline'
    return m.group(0)


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
        # RECONSTRUIDO: el reporte solo registra que este test PASO.
        assert 'v_f1_score < 0.80' in _bloque_procedimiento()

    def test_la_regla_de_100_registros_se_aplicaria_sin_distincion(self):
        # RECONSTRUIDO: el reporte solo registra que este test PASO.
        assert 'v_count_verificados < 100' in _bloque_procedimiento()


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
