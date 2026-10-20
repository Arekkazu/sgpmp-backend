"""
TC-M04-G114 (RF-71 Restricción 10/E6/CA-8/CA-13/RNF-02, CU-10) -
"Prioridad frente a procesos críticos y pausa." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún proceso de
entrenamiento observable que pausar (confirmado en G102).

HALLAZGO ADICIONAL, en la dirección INVERSA a la que pide la ficha: existe
un puerto real, `ProcesoCriticoPort` (`src/configuration/domain/repositories/
proceso_critico_port.py`), diseñado exactamente para esta relación -- pero
en sentido contrario al que (a) describe. Su propósito es que M09
(`configuration`) pueda preguntarle a M04 "¿tienes un proceso crítico
activo?" antes de dejar desactivar una especie -- NO que M04 pregunte por
la salud de RF-66/RF-53/RF-57 antes de pausarse. Su única implementación,
`StubProcesoCriticoAdapter`, devuelve `False` siempre, y su propio
docstring lo confirma: "Mientras M04 (Predicción) no esté implementado,
ninguna especie tiene procesos críticos activos... Cuando M04 exista,
este stub se reemplaza por la implementación real." Es una confirmación
más, desde un ángulo distinto, de que RF-71 no está implementado.

(a)-(e) -- HALLAZGO ÚNICO: no existe ningún mecanismo de pausa por
    degradación de servicios críticos, ni de reanudación automática, ni
    de tiempo máximo de pausa configurable en M09. El único puerto
    relacionado con "proceso crítico" en todo el repositorio apunta en la
    dirección opuesta y está, él mismo, permanentemente stubbeado.

Cómo se prueba: inspección directa de `ProcesoCriticoPort`/
`StubProcesoCriticoAdapter` + grep de "PAUSADO_POR_PRIORIDAD"/
"PAUSA_EXCEDIDA" en todo src/.

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
            "su propio docstring confirma 'mientras M04 no este implementado' -- es la unica "
            "pieza de codigo relacionada con 'proceso critico' + M04 en todo el repositorio, y "
            "apunta en la direccion opuesta a la que describe esta ficha (M09 pregunta a M04, no "
            "M04 vigila a RF-66/RF-53/RF-57)."
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
            f"{archivos or 'ninguno'}) -- solo existe como valor de enum en el DDL baseline, "
            f"nunca usado desde codigo (mismo patron que los eventos REENTRENAMIENTO_* de G102)."
        ) if not archivos else None
