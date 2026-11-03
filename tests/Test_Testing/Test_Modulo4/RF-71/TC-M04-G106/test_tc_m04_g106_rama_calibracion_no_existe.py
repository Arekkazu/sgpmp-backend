# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-03 | HulkyZeus        | TC-M04-G106 RF-71: reconstruye el test desde su reporte HTML       |
"""
TC-M04-G106 (RF-71) - La Rama B (CALIBRACION_EN_SITIO, 72 h de datos limpios)
y el balanceo de clases no existen; la Rama A (500 registros) es correcta pero
inalcanzable.

NOTA DE PROCEDENCIA (2026-11-03): el archivo original nunca se versiono; solo
se subio su reporte (resultados/resultado_TC-M04-G106.html). Este archivo se
RECONSTRUYO desde ese reporte (7 tests: 6 fallidos con codigo completo + 1 que
PASO).
  - Aserciones y mensajes de los 6 tests que fallan: copia del reporte.
  - Cuerpo del test que pasa, y los helpers `DDL` / `_bloque_sp_iniciar`:
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


def _bloque_sp_iniciar() -> str:
    m = re.search(
        r'CREATE PROCEDURE modulo4\.sp_iniciar_ciclo_reentrenamiento\(.*?\n\s*\$\$;', DDL, re.DOTALL)
    assert m, 'No se encontro modulo4.sp_iniciar_ciclo_reentrenamiento en el DDL baseline'
    return m.group(0)


class TestRamaACorrectaPeroInalcanzable:
    def test_la_condicion_de_500_sigue_siendo_correcta(self):
        # RECONSTRUIDO: el reporte solo registra que este test PASO.
        assert 'v_count < 500' in _bloque_sp_iniciar()


class TestRamaBCalibracionEnSitioNoExiste:
    def test_calibracion_en_sitio_no_es_un_trigger_valido_para_el_procedimiento(self):
        bloque = _bloque_sp_iniciar()
        pytest.fail(
            "HALLAZGO (c)-(g): sp_iniciar_ciclo_reentrenamiento solo reconoce "
            "PROGRAMADO/MANUAL/DEGRADACION como p_trigger_reentrenamiento -- cualquier otro "
            "valor, incluido 'CALIBRACION_EN_SITIO', cae en el ELSE y lanza TRIGGER_INVALIDO. "
            "No existe ninguna rama que evalue 72 horas de datos limpios ni auditorias de RF-24."
        ) if "WHEN 'PROGRAMADO'" in bloque and "WHEN 'CALIBRACION_EN_SITIO'" not in bloque else None

    def test_no_existe_ninguna_funcion_que_cuente_horas_de_datos_limpios(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'datos_limpios' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c): 'datos_limpios' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos or 'ninguno'}) ni ninguna funcion equivalente en el DDL -- la "
            f"precondicion de 72h de la Rama B no tiene ninguna implementacion."
        ) if not archivos and 'datos_limpios' not in DDL else None


class TestBalanceoDeClasesSigueSinExistir:
    @pytest.mark.parametrize('termino', ['balanceo', 'oversampling', 'estratificaci', 'ponderacion'])
    def test_termino_de_balanceo_no_existe(self, termino):
        archivos_py = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (h)/(i): '{termino}' no aparece en ningun archivo Python de src/ relevante "
            f"a M04 (encontrados en todo src/: {archivos_py or 'ninguno'}, revisar si son de "
            f"otros modulos) ni en el DDL."
        ) if not archivos_py and termino not in DDL.lower() else None
