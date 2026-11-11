"""
TC-M03-G159 (RF-61 v1.2 Restricción 4/Entradas/RNF-08, CU-09) -
"Coherencia de zonas horarias y tipos temporales."

HALLAZGO PRINCIPAL (invalida (b), en sentido contrario al que la ficha
teme): el DDL real (`esquema_baseline.sql`) confirma que
`fecha_inicio_vinculacion`/`fecha_fin_vinculacion`/`fecha_creacion` son
las TRES `timestamp with time zone` -- no existe ningún campo `Date` en
esta tabla.

(a) UTC consistente -- NO RE-VERIFICADO (fuera del alcance de los casos
    de uso de vinculación).
(b) Date vs Timestamp -- HALLAZGO (ficha incorrecta): ambas columnas son
    timestamptz.
(c) Traslado hora local vs UTC -- NO APLICA: corolario de G152 --
    fecha_fin_vinculacion nunca se asigna.
(d) Cache de Capa 1 -- HALLAZGO: no existe ningún mecanismo de caché.
(e) Cambio de horario/año bisiesto -- CONFIRMADO POR DISEÑO: al ser
    timestamptz, no hay ambigüedad posible.
(f) Partición mensual -- HALLAZGO: la tabla no tiene ninguna cláusula
    PARTITION BY.

Cómo se prueba: inspección directa del DDL real.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g159_zonas_horarias_tipos_y_particion.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G159.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


def _bloque_create_table_vinculaciones() -> str:
    inicio = DDL.index('CREATE TABLE modulo3.vinculaciones_lecturas')
    return DDL[inicio:inicio + 1200]


class TestSubCasoBNoHayMezclaDeDateYTimestamp:
    def test_fecha_inicio_y_fin_vinculacion_son_timestamp_con_zona_igual_que_fecha_creacion(self):
        bloque = _bloque_create_table_vinculaciones()
        assert 'fecha_inicio_vinculacion timestamp with time zone NOT NULL' in bloque
        assert 'fecha_fin_vinculacion timestamp with time zone' in bloque
        assert 'fecha_creacion timestamp with time zone' in bloque
        pytest.fail(
            "HALLAZGO (b), ficha incorrecta: fecha_inicio_vinculacion, fecha_fin_vinculacion y "
            "fecha_creacion son las TRES 'timestamp with time zone' en el DDL real -- no existe "
            "ningun campo tipado como Date en esta tabla."
        )

    def test_comentario_de_tabla_confirma_que_subcomponente_b_fue_diseñado_pero_no_construido(self):
        bloque_comentario = DDL[DDL.index("COMMENT ON TABLE modulo3.vinculaciones_lecturas"):][:600]
        assert 'Subcomponente B' in bloque_comentario


class TestSubCasoDNoExisteCacheDeCapa1:
    def test_no_existe_fecha_redondeada_al_dia_en_ningun_lado(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if 'fecha_redondeada' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d): 'fecha_redondeada_al_dia' no aparece en ningun archivo de "
            f"src/telemetry/ (encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoFNoHayParticionMensual:
    def test_la_tabla_no_tiene_clausula_partition_by(self):
        bloque = _bloque_create_table_vinculaciones()
        pytest.fail(
            "HALLAZGO (f): CREATE TABLE modulo3.vinculaciones_lecturas no tiene ninguna clausula "
            "PARTITION BY -- es una tabla unica sin particionar."
        ) if 'PARTITION BY' not in bloque and 'vinculaciones_lecturas_2' not in DDL else None
