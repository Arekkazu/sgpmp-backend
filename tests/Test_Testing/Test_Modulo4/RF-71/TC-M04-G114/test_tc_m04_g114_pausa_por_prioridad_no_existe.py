"""
TC-M04-G114 (RF-71 Restricción 10/E6/CA-8/CA-13/RNF-02, CU-10) -
"Prioridad frente a procesos críticos y pausa." Ficha sin cambios de
fondo por la RFC-009.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún proceso de
entrenamiento observable que pausar.

HALLAZGO ADICIONAL, en la dirección INVERSA a la que pide la ficha: existe
un puerto real, `ProcesoCriticoPort` (`src/configuration/domain/repositories/
proceso_critico_port.py`), pero en sentido contrario: M09 pregunta a M04 si
tiene un proceso crítico activo, no M04 vigilando a RF-66/RF-53/RF-57. Su
única implementación, `StubProcesoCriticoAdapter`, devuelve `False`
siempre, y su propio docstring lo confirma: "Mientras M04 no esté
implementado... Cuando M04 exista, este stub se reemplaza por la
implementación real."

(a)-(e) -- HALLAZGO ÚNICO: no existe ningún mecanismo de pausa por
    degradación de servicios críticos, ni de reanudación automática, ni
    de tiempo máximo de pausa configurable en M09.

Cómo se prueba: inspección directa de `ProcesoCriticoPort`/
`StubProcesoCriticoAdapter` + grep de "PAUSADO_POR_PRIORIDAD"/
"PAUSA_EXCEDIDA".

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g114_pausa_por_prioridad_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G114.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestElPuertoRealApuntaEnDireccionContrariaYEstaStubbeado:
    def test_el_stub_de_proceso_critico_siempre_devuelve_false(self):
        archivo = REPO_ROOT / 'src/configuration/infrastructure/adapters/proceso_critico_stub.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'return False' in texto
        pytest.fail(
            "HALLAZGO: StubProcesoCriticoAdapter.tiene_proceso_activo() siempre devuelve False -- "
            "es la unica pieza de codigo relacionada con 'proceso critico' + M04 en todo el "
            "repositorio, y apunta en la direccion opuesta a la que describe esta ficha."
        )


class TestNoExisteMecanismoDePausaPorPrioridad:
    @pytest.mark.parametrize('termino', ['PAUSADO_POR_PRIORIDAD', 'PAUSA_EXCEDIDA'])
    def test_termino_de_pausa_no_existe_en_codigo_python(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun archivo Python de src/ (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None
