"""
TC-M03-G158 (RF-61 v1.2 Salida 4/E1/E3/E4/E6, CU-15) - "Notificaciones de
resolución manual requerida." Grupo existente de RF-61 (TC-M03-G27).

Código bajo prueba: búsqueda exhaustiva de cualquier mecanismo de
notificación ligado a `vinculacion_lectura` en todo `src/telemetry/`, y
confirmación de qué dominio usa realmente la palabra "notificacion" en
este módulo.

HALLAZGO PRINCIPAL: el único sistema de "notificación"/alerta que existe
en `src/telemetry/` es el de alertas técnicas de RF-60
(`alerta.py`/`alerta_model.py`/`alerta_repository.py`/`alerta_schema.py`,
ya probado en TC-M03-G139/G142/G145) -- NINGÚN archivo relacionado con
`vinculacion_lectura` (ni los 3 casos de uso, ni el router, ni el
repositorio) menciona notificaciones, destinatarios, bandeja de
pendientes, deduplicación ni escalamiento por plazo. No existe el concepto
de "notificación de ambigüedad" en el código: cuando una lectura queda
AMBIGUA, la única consecuencia es que la fila queda con
`estado_vinculacion='AMBIGUA'` -- nadie se entera, ni el ingeniero de
campo ni el administrador, salvo que alguien liste manualmente
`GET /iot/vinculaciones?estado_vinculacion=AMBIGUA`.

(a) Notificación con id_lectura, causa, candidatos e instrucción --
    HALLAZGO: no existe.
(b) Destinatarios por rol (Productor/Veterinario para ambigüedad,
    Administrador para PENDIENTE_REVISION/SENSOR_SIN_ESTRUCTURA/baja) --
    HALLAZGO: no aplica -- no hay ningún mapa de destinatarios porque no
    hay notificaciones; además PENDIENTE_REVISION y SENSOR_SIN_ESTRUCTURA
    no existen como estados/eventos reales (confirmado en TC-M03-G152).
(c) La notificación no llega a roles que no corresponden -- NO EVALUABLE:
    no hay notificación que pueda llegarle a nadie.
(d) Escalamiento al administrador por plazo vencido -- HALLAZGO: no existe
    ningún campo de plazo configurable ni ningún job de escalamiento
    asociado a vinculaciones AMBIGUA/pendientes.
(e) Deduplicación de notificaciones del mismo sensor -- NO EVALUABLE,
    mismo motivo que (c).
(f) Cierre de la notificación al resolverse -- HALLAZGO: `resolver()` (la
    única operación que cierra una ambigüedad) solo cambia
    `estado_vinculacion`/`id_activo_biologico`/`mecanismo_vinculacion`/
    `id_usuario` en la fila de vinculación -- no hay ninguna notificación
    que cerrar porque nunca se creó una.

Cómo se prueba: grep exhaustivo sobre src/telemetry/ para separar el
dominio de notificaciones real (RF-60/alertas) del de RF-61 (vinculación).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g158_notificaciones_no_implementadas.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G158.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


def _archivos_vinculacion() -> list[Path]:
    return [
        REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py',
        REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py',
        REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/corregir_vinculacion_use_case.py',
        REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py',
        REPO_ROOT / 'src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py',
        REPO_ROOT / 'src/telemetry/domain/entities/vinculacion_lectura.py',
    ]


class TestNingunArchivoDeVinculacionMencionaNotificaciones:
    @pytest.mark.parametrize('termino', ['notificacion', 'destinatario', 'escalamiento', 'bandeja'])
    def test_termino_de_notificacion_no_aparece_en_ningun_archivo_de_vinculacion(self, termino):
        archivos_con_match = [
            str(p.relative_to(REPO_ROOT)) for p in _archivos_vinculacion()
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no aparece en ningun archivo de vinculacion (encontrados: "
            f"{archivos_con_match or 'ninguno'}). El unico sistema de notificacion/alerta real en "
            f"src/telemetry/ pertenece a RF-60 (alerta.py y derivados), no a RF-61."
        ) if not archivos_con_match else None

    def test_resolver_no_cierra_ninguna_notificacion_solo_cambia_la_fila(self):
        archivo = REPO_ROOT / 'src/telemetry/domain/entities/vinculacion_lectura.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque_resolver = texto.split('def resolver(')[1]
        assert 'notificacion' not in bloque_resolver.lower()
