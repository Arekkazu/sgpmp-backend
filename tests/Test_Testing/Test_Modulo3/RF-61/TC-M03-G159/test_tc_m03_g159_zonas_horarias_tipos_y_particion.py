# | Fecha      | Nombre           | Que se hizo                                                        |
# |------------|------------------|--------------------------------------------------------------------|
# | 2026-11-03 | HulkyZeus        | TC-M03-G159 RF-61: reconstruye el test desde su reporte HTML       |
"""
TC-M03-G159 (RF-61) - Zonas horarias, tipos de fecha y particion de
`modulo3.vinculaciones_lecturas`.

Verifica por inspeccion estatica del DDL baseline y de `src/telemetry/`:
  (b) no hay mezcla de Date y timestamp: las tres fechas de la tabla son
      `timestamp with time zone`;
  (d) no existe ninguna cache de capa 1 (`fecha_redondeada_al_dia`);
  (f) la tabla no esta particionada (sin PARTITION BY).

NOTA DE PROCEDENCIA (2026-11-03): el archivo original nunca se versiono en el
repositorio; solo se subio su reporte (resultados/resultado_TC-M03-G159.html).
Este archivo se RECONSTRUYO a partir del codigo y los mensajes de ese reporte
(4 tests: 3 fallidos con codigo completo + 1 que PASO).
  - Las aserciones y mensajes de los 3 tests fallidos son copia del reporte.
  - Los helpers `DDL` / `_bloque_create_table_vinculaciones` y el cuerpo del
    test que paso NO figuran en el reporte (los tests que pasan no guardan
    codigo): son una reconstruccion razonable, no el original.
Si Juan Pablo conserva el original, debe prevalecer sobre este.

Estilo: el test FALLA ("HALLAZGO") mientras el defecto/faltante exista.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
    encoding='utf-8', errors='ignore')


def _bloque_create_table_vinculaciones() -> str:
    m = re.search(
        r'CREATE TABLE modulo3\.vinculaciones_lecturas \((.*?)\n\);', DDL, re.DOTALL)
    assert m, 'No se encontro CREATE TABLE modulo3.vinculaciones_lecturas en el DDL baseline'
    return m.group(0)


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
        # RECONSTRUIDO: el reporte solo registra que este test PASO.
        m = re.search(r"COMMENT ON TABLE modulo3\.vinculaciones_lecturas IS '([^']*)'", DDL)
        assert m, 'La tabla no tiene COMMENT en el DDL baseline'
        assert 'Subcomponente B' in m.group(1)


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
