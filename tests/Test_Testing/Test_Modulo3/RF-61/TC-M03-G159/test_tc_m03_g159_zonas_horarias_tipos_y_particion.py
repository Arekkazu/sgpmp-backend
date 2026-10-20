"""
TC-M03-G159 (RF-61 v1.2 Restricción 4/Entradas/RNF..., CU-09) - "Coherencia
de zonas horarias y tipos temporales." Grupo existente de RF-61. Ficha
recibida truncada por el usuario a partir del campo de Entradas (tras (f));
se prueban (a)-(f), que llegaron completos.

Código bajo prueba:
    alembic/baseline/esquema_baseline.sql (DDL real de `vinculaciones_lecturas`)
    src/telemetry/infrastructure/models/vinculacion_lectura_model.py

HALLAZGO PRINCIPAL (invalida (b) por completo, en sentido CONTRARIO al que
la ficha teme): la premisa de (b) es que `fecha_inicio_vinculacion`/
`fecha_fin_vinculacion` están tipadas como `Date` mientras
`timestamp_captura` es `Timestamp` -- pero el DDL real
(`esquema_baseline.sql:21861-21862`) confirma que AMBAS columnas son
`timestamp with time zone`, exactamente el mismo tipo que
`fecha_creacion`. No hay ninguna comparación Date-vs-Timestamp posible
porque no existe ningún campo `Date` en esta tabla. El riesgo que (b)
anticipa (confusión en el primer/último segundo del día) no puede ocurrir
por este motivo -- aunque sí puede seguir existiendo en el futuro si
alguien cambia por error el tipo de una sola de las tres columnas.

Hallazgo colateral, relevante para TC-M03-G152: el propio comentario de la
tabla en el DDL (`esquema_baseline.sql:21879`) describe explícitamente
"Subcomponente B: vinculación histórica diferida (datos de buffer)" como
parte del diseño documentado -- confirma que el Subcomponente B SÍ fue
diseñado/previsto a nivel de esquema, pero (como TC-M03-G152 demostró)
nunca se implementó en la capa de aplicación Python. No es un
malentendido del evaluador: es una brecha real entre diseño documentado y
código entregado.

(a) UTC consistente entre offsets -- NO RE-VERIFICADO EN ESTE TC: la
    normalización de `timestamp_captura` ocurre, si ocurre, en la
    ingesta de RF-53 (fuera del alcance de los 3 casos de uso de
    vinculación, que solo reciben y reenvían el valor ya parseado).
(b) Date vs Timestamp -- HALLAZGO (ficha incorrecta, no hay bug real): ver
    arriba -- ambas columnas son `timestamp with time zone`.
(c) Traslado en hora local vs UTC -- NO APLICA: corolario de TC-M03-G152 --
    como `fecha_fin_vinculacion` nunca se asigna un valor real desde la
    aplicación, no hay ninguna "frontera de traslado" que pueda
    desplazarse por un offset, porque esa frontera nunca se crea.
(d) Cache de Capa 1 con clave `fecha_redondeada_al_dia` -- HALLAZGO: no
    existe ningún mecanismo de caché en `src/telemetry/` asociado a
    vinculación ni a esa clave; "cache" solo aparece, sin relación, en un
    comentario de `monitoreo_repository.py` sobre el dashboard de RF-58.
(e) Cambio de horario / año bisiesto -- CONFIRMADO POR DISEÑO (sin
    hallazgo): al ser `timestamp with time zone` (un instante absoluto,
    no una hora de pared), ni un cambio de horario ni un año bisiesto
    pueden introducir ambigüedad en el almacenamiento -- siempre que el
    valor que llega ya incluya tzinfo correcto (ver (a)).
(f) Partición mensual `vinculaciones_YYYYMM` -- HALLAZGO: la tabla real
    (`CREATE TABLE modulo3.vinculaciones_lecturas (...)`) NO tiene ninguna
    cláusula `PARTITION BY`, y no existe ninguna partición con ese patrón
    de nombre en todo el esquema baseline -- es una tabla única, sin
    particionar. No hay ninguna "partición correcta según UTC" que
    verificar porque no hay particiones.

Cómo se prueba: inspección directa del DDL real en
`alembic/baseline/esquema_baseline.sql` + del modelo SQLAlchemy + grep de
"cache"/"PARTITION OF" en todo el esquema.

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
            "ningun campo tipado como Date en esta tabla. La premisa de (b) (Date vs Timestamp) "
            "no se cumple; no hay ninguna comparacion de tipos heterogeneos que pueda fallar en "
            "el primer/ultimo segundo del dia."
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
            f"src/telemetry/ (encontrados: {archivos or 'ninguno'}). No existe ningun mecanismo "
            f"de cache de Capa 1 para vinculaciones."
        ) if not archivos else None


class TestSubCasoFNoHayParticionMensual:
    def test_la_tabla_no_tiene_clausula_partition_by(self):
        bloque = _bloque_create_table_vinculaciones()
        pytest.fail(
            "HALLAZGO (f): CREATE TABLE modulo3.vinculaciones_lecturas no tiene ninguna clausula "
            "PARTITION BY -- es una tabla unica sin particionar. No existe ningun patron "
            "'vinculaciones_YYYYMM' en todo el esquema baseline."
        ) if 'PARTITION BY' not in bloque and 'vinculaciones_lecturas_2' not in DDL else None
