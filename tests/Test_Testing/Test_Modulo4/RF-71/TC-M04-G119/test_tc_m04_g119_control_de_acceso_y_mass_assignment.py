"""
TC-M04-G119 (RF-71 v2.0 RNF-07/RNF-09/Precondición 6/RFC-009, CU-15) -
"Control de acceso y protección de artefactos." La v2.0 añade a la lista
de mass assignment el resultado de las auditorías de RF-24, y pregunta si
CALIBRACION_EN_SITIO exige el mismo conjunto de roles que MANUAL.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): el único endpoint real
relacionado (`POST /prediccion/modelos`) se autentica con
`X-RF71-Internal-Key`, no con RBAC de usuario; `CALIBRACION_EN_SITIO` no
es una entrada reconocida en ningún punto.

(a) Solo Admin/Vet pueden iniciar MANUAL; ¿CALIBRACION_EN_SITIO exige el
    mismo conjunto de roles? -- NO EVALUABLE: no hay ningún "iniciar" vía
    API de usuario para ninguno de los dos modos, porque ninguno de los
    dos existe como concepto alcanzable.
(b) Manipulación de token -- NO RE-VERIFICADO (genérico, fuera de
    alcance de RF-71).
(c) Mass assignment, incluido el resultado de las auditorías de RF-24 --
    HALLAZGO DE ENCUADRE AGRAVADO: ninguno de los campos de la lista
    (incluido el nuevo "resultado de auditorías de RF-24") es un valor
    calculado por el servidor que el cliente intente sobrescribir -- son
    insumos legítimos del DTO por diseño. Además, el RF-24 real
    (calibración de sensor) no tiene ningún concepto de "resultado de
    auditoría" que pudiera inyectarse.
(d) RNF-09, descarga directa -- CONFIRMADO ESTRUCTURALMENTE: no existe
    ningún endpoint de descarga de artefacto ni de dataset.
(e) Configuración de M09 -- NO RE-VERIFICADO (fuera de alcance de RF-71).
(f) Inyección en tipo_modelo/modo_generacion/filtros -- CONFIRMADO
    CORRECTO para tipo_modelo (consultas parametrizadas); modo_generacion
    no es un campo real, por lo que no hay ningún punto de inyección
    para ese campo tampoco.

Cómo se prueba: inspección directa del router, del DTO y del repositorio.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g119_control_de_acceso_y_mass_assignment.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G119.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoANoHayEndpointDeIniciarNingunModo:
    def test_el_endpoint_de_registro_no_tiene_rbac_de_usuario(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/routers/version_modelo_router.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto.split('async def registrar_version_modelo(')[1].split('@router.get(')[0]
        pytest.fail(
            "HALLAZGO (a): POST /prediccion/modelos no tiene ninguna dependencia "
            "require_permission ni get_current_user -- no hay ningun 'iniciar' con RBAC de rol "
            "para MANUAL ni para CALIBRACION_EN_SITIO, porque ninguno de los dos es alcanzable."
        ) if 'require_permission' not in bloque and 'get_current_user' not in bloque else None


class TestSubCasoCMassAssignmentIncluidoRf24EsProblemaDeOrigen:
    def test_rf24_real_no_tiene_concepto_de_resultado_de_auditoria(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/calibracion.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (c): el RF-24 real (Calibracion) no tiene ningun campo 'resultado' ni "
            "'auditoria' -- es un registro de ganancia/offset de sensor. El 'resultado de las "
            "auditorias de RF-24' que (c) pide proteger de mass assignment no corresponde a "
            "nada real con ese nombre."
        ) if 'resultado' not in texto.lower() and 'auditoria' not in texto.lower() else None


class TestSubCasoDNoHayEndpointDeDescarga:
    def test_ningun_router_de_m04_sirve_artefactos_ni_datasets(self):
        archivos = list((REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py'))
        archivos_con_descarga = [
            p.name for p in archivos
            if 'FileResponse' in p.read_text(encoding='utf-8', errors='ignore')
            or 'StreamingResponse' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d): ningun router de M04 usa FileResponse ni StreamingResponse "
            f"(revisados: {[p.name for p in archivos]!r})."
        ) if not archivos_con_descarga else None


class TestSubCasoFInyeccionConfirmadoSinHallazgo:
    def test_listar_usa_consultas_parametrizadas(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/version_modelo_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'select(VersionModeloModel)' in texto
        assert 'f"SELECT' not in texto
