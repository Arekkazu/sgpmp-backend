"""
TC-M02-G108 (RF-52, CU13, ASVS V8) - Retencion minima diferenciada de la bitacora
segun categoria de evento.

    TC-M02-303  TRANSFORMACION_BIOLOGICA y SANITARIO >= 5 anios; GESTION_OPERATIVA y ACCESO_DATOS >= 2 anios;
                ambos configurables sin tocar codigo

Los tests afirman lo que pide la ficha; si el backend no lo cumple, quedan en rojo.

Como correrlo (desde la raiz del repo):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_g108_retencion_diferenciada.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G108.html --self-contained-html
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bitacora_helpers as h  # noqa: E402

MINIMO_ANIOS = {
    'TRANSFORMACION_BIOLOGICA': 5,
    'SANITARIO': 5,
    'GESTION_OPERATIVA': 2,
    'ACCESO_DATOS': 2,
}


def _un_registro_por_clasificacion(token: str) -> dict:
    encontrados = {}
    for clasificacion in MINIMO_ANIOS:
        filas = h.get(token, h.RUTA_AUDITORIA, clasificacion_biologica=clasificacion, page_size=1).json()['registros']
        if filas:
            encontrados[clasificacion] = filas[0]
    return encontrados


class TestTCM02303RetencionMinimaDiferenciada:

    def test_hay_registros_de_cada_clasificacion_para_revisar(self):
        encontrados = _un_registro_por_clasificacion(h.login(h.ADMIN))
        assert set(encontrados) == set(MINIMO_ANIOS), f'clasificaciones sin registros: {set(MINIMO_ANIOS) - set(encontrados)}'

    def test_cada_registro_declara_su_retencion_minima_segun_la_clasificacion(self):
        for clasificacion, registro in _un_registro_por_clasificacion(h.login(h.ADMIN)).items():
            anios = registro.get('retencion_aplicable')
            assert anios is not None, (
                f'El registro {clasificacion} (id {registro["id_bitacora"]}) no declara retencion: '
                'RF-52 no expone ningun campo retencion_aplicable (RF-63 si).'
            )
            assert anios >= MINIMO_ANIOS[clasificacion]

    def test_la_politica_de_retencion_es_configurable_sin_tocar_codigo(self):
        archivos = h.archivos_de_m02_que_mencionan(r'retenci|retention')
        assert archivos, (
            'src/biological_assets no contiene ninguna referencia a retencion (ni columna, ni parametro, ni variable '
            'de entorno): la politica de 5/2 anios no esta implementada ni es configurable.'
        )
