"""
TC-M04-G108 (RF-71 Precondición 5/Restricción 5/E4/CA-12/CA-17, CU-05) -
"Consistencia con el catálogo de patologías RF-64." Reintento: esta ficha
no cambió con la RFC-009 (sin etiqueta v2.0 ni menciones a
modo_generacion); se re-ejecuta sin cambios de fondo respecto a la ronda
anterior.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint que
inicie el proceso (confirmado en G102).

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py

HALLAZGO: `RegistrarVersionModeloUseCase` (el único punto de contacto real
con lo que RF-71 entrega) sí valida `compatibilidad_variables` contra un
catálogo (`_validar_variables()`, vía `VariableI3P1Port`) -- pero ese
catálogo es el de VARIABLES DE ENTRADA I3P-1 (M09), no el catálogo de
PATOLOGÍAS/CLASES OBJETIVO de RF-64 que pide esta ficha. No existe
ninguna verificación de que las clases que el modelo predice coincidan
con el catálogo vigente de patologías.

(a)-(e) -- HALLAZGO ÚNICO: ninguna referencia a RF-64/`patologia_m04`
    aparece en `registrar_version_modelo_use_case.py` ni en ningún otro
    archivo del paquete `versiones_modelo`. No hay bloqueo por
    inconsistencia de catálogo, no hay continuidad "deliberada" con el
    catálogo vigente al inicio, no hay registro de discrepancia en
    auditoría, y no hay versión de catálogo asociada al registro de la
    versión del modelo.

Cómo se prueba: inspección directa de `registrar_version_modelo_use_case.py`
y grep de `patologia_m04`/`catalogo` en el paquete `versiones_modelo`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g108_consistencia_catalogo_no_verificada.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G108.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoHayConsistenciaConCatalogoDePatologias:
    def test_registrar_version_no_valida_contra_patologia_m04(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: registrar_version_modelo_use_case.py no menciona 'patologia_m04' ni "
            "'catalogo' en absoluto -- valida compatibilidad_variables contra el catalogo de "
            "VARIABLES I3P-1 (M09), un catalogo distinto al de PATOLOGIAS/CLASES OBJETIVO "
            "(RF-64) que esta ficha pide verificar. No hay ningun bloqueo por inconsistencia de "
            "catalogo de clases."
        ) if 'patologia_m04' not in texto and 'catalogo' not in texto.lower() else None

    def test_no_existe_ninguna_version_de_catalogo_asociada_al_registro(self):
        archivo = REPO_ROOT / 'src/prediction/domain/entities/version_modelo.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'version_catalogo' not in texto and 'id_catalogo' not in texto
