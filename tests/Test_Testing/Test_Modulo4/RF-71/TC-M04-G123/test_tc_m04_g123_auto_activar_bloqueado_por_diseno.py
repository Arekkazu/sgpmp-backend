"""
TC-M04-G123 [NUEVO] (RF-71 FA-14/CA-5/Restricción 4, CU-09) - "Bloqueo
activo de un intento de forzar la activación automática del modelo recién
reentrenado." Complementa TC-M04-G112(d) con un intento activo de bypass.

Código bajo prueba:
    src/prediction/infrastructure/dto/registrar_version_modelo_dto.py
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py
    src/configuration/ (M09 -- búsqueda de cualquier regla de activación automática)

HALLAZGO PRINCIPAL, CONFIRMADO CORRECTO (sin hallazgo de seguridad): el
bloqueo que pide FA-14 SÍ se cumple, pero por una razón estructural más
fuerte que un allow-list explícito -- `RegistrarVersionModeloDTO.__init__`
declara únicamente los parámetros `Form(...)`/`File(...)` que lista (ver
TC-M04-G112(a)); FastAPI construye el DTO ÚNICAMENTE a partir de esos
parámetros declarados. Un campo `auto_activar=true` o
`activar_al_aprobar=true` enviado en el multipart/form-data JAMÁS llega a
leerse: no hay ningún `**kwargs`, ningún `model_config.extra = "allow"`
ni ninguna lectura de `request.form()` cruda en todo el flujo -- el
campo no tiene ningún lugar físico donde aterrizar. Esto es más robusto
que un allow-list que podría tener un descuido: aquí no hay ninguna
superficie que pueda leer el campo en absoluto.

(a) Payload con auto_activar=true/activar_al_aprobar=true ignorado;
    modelo llega a RF-69 en EN_VALIDACION igual que el camino feliz --
    CONFIRMADO CORRECTO PARA LA PARTE DE IGNORAR EL CAMPO (ver arriba);
    MATIZADO para "llega en EN_VALIDACION igual que el camino feliz": el
    camino feliz YA NO garantiza EN_VALIDACION (TC-M04-G102) -- con
    métricas que pasan el umbral, cualquier registro (con o sin el
    campo de bypass) termina igual, en APROBADO. El campo de bypass no
    cambia el resultado porque es irrelevante, no porque el sistema lo
    detecte y lo bloquee activamente -- son dos cosas distintas, y la
    segunda (bloqueo activo con registro del intento) no existe.
(b) Regla de activación automática configurable en M09 -- CONFIRMADO
    CORRECTO: no existe ninguna superficie de configuración en M09 para
    activación automática post-reentrenamiento.
(c) La versión anterior sigue ACTIVA sin evento de activación/deprecación
    -- CONFIRMADO CORRECTO (ya probado en TC-M04-G112(d)): registrar una
    nueva versión nunca llama a `activar()` ni a `deprecar()`.

Cómo se prueba: inspección de la firma del DTO (confirma que no hay
mecanismo de lectura de campos no declarados) + grep de 'auto_activar'/
'activar_al_aprobar' en src/configuration/ (M09).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g123_auto_activar_bloqueado_por_diseno.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G123.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoACampoDeBypassNoTieneDondeAterrizar:
    def test_el_dto_no_acepta_kwargs_arbitrarios(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        tiene_var_keyword = any(p.kind == p.VAR_KEYWORD for p in firma.parameters.values())
        assert not tiene_var_keyword

    def test_auto_activar_no_es_un_parametro_declarado(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        assert 'auto_activar' not in parametros and 'activar_al_aprobar' not in parametros


class TestSubCasoBNoExisteConfiguracionDeActivacionAutomaticaEnM09:
    @pytest.mark.parametrize('termino', ['auto_activar', 'activar_al_aprobar', 'activacion_automatica'])
    def test_termino_no_existe_en_configuration(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/configuration').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        assert not archivos


class TestSubCasoCRegistrarNuncaActivaNiDeprecaConfirmadoYaEnG112:
    def test_execute_de_registrar_no_llama_a_activar_ni_deprecar(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert '.activar()' not in texto and '.deprecar()' not in texto
