# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-03 | HulkyZeus        | TC-M04-G108 RF-71: reconstruye el test desde su reporte HTML       |
"""
TC-M04-G108 (RF-71) - Consistencia con el catalogo de patologias (RF-64) no
verificada al registrar una version de modelo.

NOTA DE PROCEDENCIA (2026-11-03): el archivo original nunca se versiono; solo
se subio su reporte (resultados/resultado_TC-M04-G108.html). Este archivo se
RECONSTRUYO desde ese reporte (2 tests: 1 fallido con codigo completo + 1 que
PASO).
  - Aserciones y mensaje del test que falla: copia del reporte.
  - Cuerpo del test que pasa: reconstruccion razonable (el nombre sugiere que
    no hay version de catalogo asociada al registro), NO el original.
Si Juan Pablo conserva el original, debe prevalecer sobre este.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
ARCHIVO = (REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/'
           'registrar_version_modelo_use_case.py')


class TestNoHayConsistenciaConCatalogoDePatologias:
    def test_registrar_version_no_valida_contra_patologia_m04(self):
        archivo = ARCHIVO
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: registrar_version_modelo_use_case.py no menciona 'patologia_m04' ni "
            "'catalogo' en absoluto -- valida compatibilidad_variables contra el catalogo de "
            "VARIABLES I3P-1 (M09), un catalogo distinto al de PATOLOGIAS/CLASES OBJETIVO "
            "(RF-64) que esta ficha pide verificar. No hay ningun bloqueo por inconsistencia de "
            "catalogo de clases."
        ) if 'patologia_m04' not in texto and 'catalogo' not in texto.lower() else None

    def test_no_existe_ninguna_version_de_catalogo_asociada_al_registro(self):
        # RECONSTRUIDO: el reporte solo registra que este test PASO.
        texto = ARCHIVO.read_text(encoding='utf-8').lower()
        assert 'version_catalogo' not in texto
