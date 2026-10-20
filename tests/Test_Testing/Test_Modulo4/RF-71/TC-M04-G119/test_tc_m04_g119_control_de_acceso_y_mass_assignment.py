"""
TC-M04-G119 (RF-71 RNF-07/RNF-09/Precondición 6, CU-15) - "Control de
acceso y protección de artefactos." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint de
"iniciar el trigger MANUAL" -- el único endpoint real relacionado con la
entrega de un modelo (`POST /prediccion/modelos`) se autentica con
`X-RF71-Internal-Key`, no con RBAC de usuario (confirmado en G102).

Código bajo prueba:
    src/prediction/infrastructure/routers/version_modelo_router.py
    src/prediction/infrastructure/repositories/version_modelo_repository.py

(a) Solo Admin/Vet pueden iniciar MANUAL; otros roles -> 403 -- HALLAZGO
    DE ALCANCE: no hay ningún "iniciar" vía API de usuario. La acción de
    usuario más cercana que SÍ tiene RBAC real es
    `POST /prediccion/modelos/{id}/activar` (recurso 43, permiso E=5),
    que según el docstring del router está restringida a Admin/Vet --
    pero "activar una versión ya aprobada" no es "iniciar un
    reentrenamiento MANUAL"; son operaciones distintas.
(b) Manipulación de token -> rechazo con verificación de firma -- NO
    RE-VERIFICADO EN ESTE TC: es un mecanismo genérico de autenticación
    (`get_current_user`) ya cubierto por el resto del proyecto (M01); no
    es específico de RF-71.
(c) Mass assignment de dataset_hash/hash_artefacto_modelo/estado/
    id_proceso_rf71/métricas precalculadas -- HALLAZGO DE ENCUADRE: estos
    campos NO son valores "que el usuario no debe controlar" en el
    diseño real de `POST /prediccion/modelos` -- son, por diseño, los
    INSUMOS LEGÍTIMOS que el llamador (quien posea `X-RF71-Internal-Key`)
    debe proveer; no hay ningún "valor calculado por el servidor que el
    cliente intenta sobrescribir", porque el servidor no calcula esos
    valores en absoluto (los recibe). El único control real es la
    posesión de la clave interna -- quien la tenga puede, por diseño,
    declarar cualquier métrica y cualquier hash de dataset (ver también
    TC-M04-G110(a): el hash de dataset nunca se verifica contra datos
    reales). El riesgo de (c) es real, pero su causa es la ausencia de
    verificación de origen de los datos, no un fallo de allow-listing.
(d) RNF-09, descarga directa de artefacto/dataset sin autorización ->
    denegada -- CONFIRMADO ESTRUCTURALMENTE (sin hallazgo adicional a
    G102): no existe NINGÚN endpoint de descarga de artefacto ni de
    dataset en ningún router de M04 -- no hay nada que proteger porque
    no hay nada que servir.
(e) Modificar configuración de M09 requiere Administrador y queda
    auditado -- NO RE-VERIFICADO: no es específico de RF-71 (fuera de
    alcance de este TC; ya cubierto en rondas anteriores de M09).
(f) Inyección en tipo_modelo/version_modelo_base/filtros del historial --
    CONFIRMADO CORRECTO (sin hallazgo): `listar()` en
    `version_modelo_repository.py` usa `select()`/`.where()` de
    SQLAlchemy con parámetros vinculados, sin concatenación de strings.

Cómo se prueba: inspección directa del router y del repositorio.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g119_control_de_acceso_y_mass_assignment.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G119.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoANoHayEndpointDeIniciarManual:
    def test_el_endpoint_de_registro_no_tiene_rbac_de_usuario(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/routers/version_modelo_router.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto.split('async def registrar_version_modelo(')[1].split('@router.get(')[0]
        pytest.fail(
            "HALLAZGO (a): POST /prediccion/modelos no tiene ninguna dependencia "
            "require_permission ni get_current_user en su handler -- se autentica solo con la "
            "cabecera X-RF71-Internal-Key. No hay ningun endpoint de 'iniciar MANUAL' con RBAC "
            "de rol Administrador/Veterinario; la operacion de usuario mas cercana con RBAC real "
            "(activar, recurso 43 permiso 5) es una accion distinta: activar una version ya "
            "aprobada, no iniciar un reentrenamiento."
        ) if 'require_permission' not in bloque and 'get_current_user' not in bloque else None


class TestSubCasoCMassAssignmentEsUnProblemaDeOrigenNoDeAllowList:
    def test_los_campos_declarados_como_riesgo_son_insumos_legitimos_del_dto(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/dto/registrar_version_modelo_dto.py'
        texto = archivo.read_text(encoding='utf-8')
        for campo in ('hash_artefacto_sha256', 'dataset_entrenamiento_hash', 'id_proceso_rf71', 'metricas_validacion'):
            assert f'{campo}: ' in texto or f'{campo} =' in texto or campo in texto
        pytest.fail(
            "HALLAZGO (c), de encuadre: hash_artefacto_sha256, dataset_entrenamiento_hash, "
            "id_proceso_rf71 y metricas_validacion son parametros Form(...) declarados y "
            "requeridos del DTO -- no hay ningun allow-list que 'proteger' porque estos valores "
            "siempre vienen del cliente por diseno. La proteccion real es X-RF71-Internal-Key; "
            "quien la posea puede declarar cualquier metrica o hash de dataset sin verificacion "
            "de origen (ver TC-M04-G110(a))."
        )


class TestSubCasoDNoHayEndpointDeDescarga:
    def test_ningun_router_de_m04_sirve_artefactos_ni_datasets(self):
        archivos = list((REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py'))
        archivos_con_descarga = [
            p.name for p in archivos
            if 'FileResponse' in p.read_text(encoding='utf-8', errors='ignore')
            or 'StreamingResponse' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (d), confirma G102: ningun router de M04 usa FileResponse ni "
            f"StreamingResponse (revisados: {[p.name for p in archivos]!r}) -- no existe ningun "
            f"endpoint que sirva el contenido binario de un artefacto ni de un dataset."
        ) if not archivos_con_descarga else None


class TestSubCasoFInyeccionConfirmadoSinHallazgo:
    def test_listar_usa_consultas_parametrizadas(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/version_modelo_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'select(VersionModeloModel)' in texto
        assert 'f"SELECT' not in texto
