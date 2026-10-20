"""
TC-M03-G151 (RF-60 v1.3/RFC-011 v1.1, CU-18) - "Categoría CAMARA y
estado_calibración." Grupo NUEVO (sin TC previo). [BLOQUEADO, según la
propia ficha: "el RFC-011 está declarado en la cabecera de la ficha v1.3
pero NO está redactado en el cuerpo: no hay entrada, estado, alerta ni
criterio de aceptación que defina CAMARA ni estado_calibracion"].

Código bajo prueba: búsqueda exhaustiva de `CAMARA`/`estado_calibracion` en
todo `src/` y `alembic/` (código y esquema de BD), más inspección de
`TipoDispositivoIoT` (M09) para confirmar cómo se modela la categoría de un
dispositivo.

HALLAZGO PRINCIPAL (confirma el bloqueo que la propia ficha ya declara):
`CAMARA`, `CAMARA_VISION` y `estado_calibracion` tienen CERO coincidencias
en todo `src/` y `alembic/` (grep exhaustivo). `TipoDispositivoIoT` (M09) no
declara ningún enum cerrado de categorías de dispositivo -- la categoría es
un dato configurable en BD, no un valor con tratamiento especial en código.
Esto es consistente con lo observado en vivo en TEST durante este mismo
proyecto: una categoría de dispositivo con nombre similar a "cámara" se
pudo crear como fila de datos en M09 sin ningún cambio de código -- pero
eso NO implica que exista ningún comportamiento RF-60 específico para esa
categoría (sin_señal/turbidez/oclusión/baja luz/estado_calibracion): el
algoritmo de `evaluar_transicion()` (TC-M03-G132) trata cualquier
dispositivo, sea cual sea su categoría, exactamente igual.

(a) "Intervalo de heartbeat propio de CAMARA, validado contra la
    Restricción 12" -- BLOQUEADO: no hay ningún campo ni lógica que
    distinga el intervalo de heartbeat por categoría de dispositivo; la
    Restricción 12 (TC-M03-G137) se aplica igual para cualquier
    dispositivo, sin ninguna rama para CAMARA.
(b) "Cámara sin señal -> SIN_SEÑAL/INACTIVO por el algoritmo general" --
    esto NO es un hallazgo nuevo: ya es el comportamiento confirmado para
    CUALQUIER dispositivo (el algoritmo no distingue categorías, ver
    TC-M03-G132). No hay nada específico de CAMARA que verificar aquí.
(c) "Cámara con señal pero sin detección válida -> NO es fallo de
    dispositivo, alimenta estado_calibracion" -- BLOQUEADO: no existe el
    campo `estado_calibracion` en ninguna entidad, ni ningún concepto de
    "detección válida por turbidez/oclusión/baja luz" en el dominio de
    telemetry. No hay código que pueda fallar ni pasar esta aserción.
(d) "Transición (b)/(c) diferenciada en el historial de RF-59" --
    BLOQUEADO por la misma razón que (c): no existe (c), por lo que no hay
    nada que diferenciar de (b).

Cómo se prueba: grep exhaustivo sobre src/ y alembic/ + inspección de
`TipoDispositivoIoT`. No se ejecuta ningún caso funcional porque, tal como
anticipa la propia ficha, no hay requisito redactado contra el cual probar.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g151_rfc011_camara_sin_requisito_redactado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G151.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


def _grep(termino: str, carpetas: tuple[str, ...]) -> list[str]:
    archivos: list[str] = []
    for carpeta in carpetas:
        base = REPO_ROOT / carpeta
        if not base.exists():
            continue
        for p in base.rglob('*.py'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
        for p in base.rglob('*.sql'):
            if termino in p.read_text(encoding='utf-8', errors='ignore'):
                archivos.append(str(p.relative_to(REPO_ROOT)))
    return archivos


class TestConfirmaElBloqueoDeclaradoPorLaPropiaFicha:
    """(a)/(c)/(d): el RFC-011 no esta redactado -- confirma que ni el
    codigo ni el esquema de BD tienen rastro de CAMARA ni estado_calibracion."""

    @pytest.mark.parametrize('termino', ['CAMARA', 'estado_calibracion'])
    def test_termino_del_rfc011_no_existe_en_codigo_ni_esquema(self, termino):
        archivos = _grep(termino, ('src', 'alembic'))
        pytest.fail(
            f"HALLAZGO (confirma el BLOQUEO declarado por la propia ficha): '{termino}' no "
            f"aparece en ningun archivo de src/ ni alembic/ (encontrados: {archivos or 'ninguno'}). "
            f"El RFC-011 v1.1 esta mencionado unicamente en la cabecera de la ficha, nunca en un "
            f"RF redactado -- no hay entrada, estado, alerta ni criterio de aceptacion que lo "
            f"respalde en el sistema real."
        ) if not archivos else None

    def test_tipo_dispositivo_iot_no_declara_categorias_con_tratamiento_especial(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/tipo_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'CAMARA' not in texto
        pytest.fail(
            "HALLAZGO (a): TipoDispositivoIoT (M09) no declara ningun enum cerrado de categorias "
            "de dispositivo con tratamiento especial -- la categoria es un dato configurable en "
            "BD, sin ninguna rama de codigo en RF-60 que distinga el intervalo de heartbeat, el "
            "algoritmo de estado ni ninguna otra regla segun la categoria. Aunque en TEST se haya "
            "podido crear una categoria con nombre similar a 'camara' como simple fila de datos, "
            "eso no activa ningun comportamiento RF-60 especifico de CAMARA, porque ese "
            "comportamiento no existe en el codigo."
        )

    def test_algoritmo_de_estado_no_distingue_categoria_de_dispositivo(self):
        """(b): confirma, sin ser un hallazgo nuevo, que el algoritmo general
        (ya probado exhaustivamente en G132) no tiene ninguna rama por
        categoria -- por lo que 'camara sin senal -> SIN_SENAL/INACTIVO' ya
        esta cubierto por G132 para CUALQUIER dispositivo, no es especifico
        de CAMARA."""
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/estado_dispositivo_iot.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'CAMARA' not in texto
        assert 'categoria' not in texto.lower()
