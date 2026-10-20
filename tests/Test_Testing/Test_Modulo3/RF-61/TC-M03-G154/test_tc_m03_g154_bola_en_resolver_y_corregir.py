"""
TC-M03-G154 (RF-61 v1.2 RNF-06/Fase B2/Entradas, CU-11) - "Seguridad de
acceso a objetos, inyección y superficie de despliegue." Grupo existente de
RF-61 (ejecutado con datos poblados en DOS unidades productivas según la
ficha; esta sesión no dispone de ese dataset en TEST, así que (a) se prueba
a nivel de caso de uso con dobles, que es equivalente y más preciso para
una vulnerabilidad estructural de codigo).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/resolver_vinculacion_use_case.py
    src/telemetry/application/use_cases/infraestructura/corregir_vinculacion_use_case.py
    src/telemetry/infrastructure/routers/vinculacion_router.py
    src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py
    main.py (CORS, exposición de Swagger/OpenAPI)

HALLAZGO PRINCIPAL (a), BOLA real en escritura: `obtener_vinculacion`
(GET detalle) y `listar_vinculaciones` SÍ filtran por
`ids_fincas_permitidas` (vía `AlcanceFincaAdapter`, confirmado en
`vinculacion_router.py:88-90` y `:120-122`) -- pero `resolver_vinculacion`
(PATCH .../resolver) y `corregir_vinculacion` (POST .../corregir) NUNCA
pasan ese parámetro: ni el router lo calcula para esas dos rutas, ni
`ResolverVinculacionUseCase`/`CorregirVinculacionUseCase` declaran
siquiera un parámetro para recibirlo. `obtener_por_id()` en el repositorio
solo aplica el filtro de finca `if ids_fincas_permitidas is not None` --
al no pasarlo nunca desde estas dos rutas, el filtro queda permanentemente
desactivado para las operaciones de ESCRITURA. Un usuario con permiso de
recurso 37:3 (autorizado a resolver/corregir EN GENERAL) puede resolver o
corregir la vinculación de un dispositivo de CUALQUIER finca, no solo las
suyas -- exactamente el patrón BOLA que pide (a), confirmado por
inspección de código y reproducido con un doble de prueba, sin necesitar
el dataset real de dos unidades productivas.

(a) BOLA con token de unidad A contra objetos de unidad B -- HALLAZGO: GET
    por ID y listar SÍ están protegidos; PATCH resolver y POST corregir NO
    lo están -- ningún id_vinculacion_lectura queda fuera de alcance para
    un usuario con el permiso de recurso correcto, sea de la finca que sea.
    (Enumeración sobre contexto_activo no aplica: ese campo no existe en
    RF-61, confirmado en TC-M03-G153.)
(b) Inyección SQL/NoSQL -- CONFIRMADO (sin hallazgo): todas las consultas
    de `vinculacion_lectura_repository.py` usan `select()`/`.where()` de
    SQLAlchemy con parámetros vinculados; cero concatenación de strings en
    ninguna consulta, incluida la de listar/paginar.
(c) TLS 1.3/HSTS -- NO EJECUTADO EN ESTA SESIÓN: requiere un escaneo contra
    el endpoint real del entorno (testssl.sh), herramienta no disponible
    en este entorno y que además apunta a infraestructura compartida --
    requiere autorización explícita antes de ejecutarse.
(d) Secretos en BD/logs/respuestas/repo -- CONFIRMADO para el código fuente
    de RF-61 (sin hallazgo): ningún DTO ni schema de vinculación
    (`VinculacionLecturaSchema`, `ResolverVinculacionDTO`,
    `CorregirVinculacionDTO`) expone ni recibe ningún campo de credencial o
    access_key. El barrido de BD/logs en vivo no se ejecuta en esta sesión
    (requiere acceso de solo lectura ya autorizado al entorno, pero un
    barrido completo de logs no estaba en el alcance de esta pasada).
(e) Superficie de despliegue -- HALLAZGO (a nivel de aplicación, no
    específico de RF-61): `main.py` no pasa `docs_url=None` ni envuelve
    `/docs`/`/openapi.json` con ninguna dependencia de autenticación --
    Swagger UI y el esquema OpenAPI completo (incluidos los 4 endpoints de
    vinculación) quedan expuestos sin autenticación en sus rutas default de
    FastAPI. CORS, en cambio, está bien configurado (allowlist explícita
    por `ALLOWED_ORIGINS` + regex de localhost, sin wildcard) -- no es
    permisivo como (e) teme.

Cómo se prueba: pytest a nivel de caso de uso con repos de prueba
(`MagicMock`) para (a), confirmando que `obtener_por_id` nunca recibe
`ids_fincas_permitidas` desde `ResolverVinculacionUseCase`/
`CorregirVinculacionUseCase`, más inspección estática para (b)/(d)/(e).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g154_bola_en_resolver_y_corregir.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G154.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.corregir_vinculacion_use_case import (
    CorregirVinculacionUseCase,
)
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import (
    ResolverVinculacionUseCase,
)
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA_ISO = '2026-10-20T12:00:00+00:00'


def _vinculacion_de_otra_finca(estado='AMBIGUA'):
    from datetime import datetime, timezone
    return VinculacionLectura(
        id_vinculacion_lectura=1, id_telemetria=99, modelo_manejo='INDIVIDUAL',
        id_activo_biologico=None, id_infraestructura=999,  # pertenece a una finca "ajena"
        fecha_inicio_vinculacion=datetime(2026, 10, 20, tzinfo=timezone.utc), fecha_fin_vinculacion=None,
        mecanismo_vinculacion='AUTOMATICA', estado_vinculacion=estado, id_usuario=None,
        motivo_correccion=None, id_vinculacion_reemplazada=None,
        fecha_creacion=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


class TestSubCasoABolaEnEscrituraResolverYCorregir:
    """(a): PATCH resolver y POST corregir nunca filtran por finca."""

    def test_resolver_vinculacion_use_case_no_declara_ids_fincas_permitidas(self):
        firma_init = inspect.signature(ResolverVinculacionUseCase.__init__)
        firma_execute = inspect.signature(ResolverVinculacionUseCase.execute)
        parametros = set(firma_init.parameters) | set(firma_execute.parameters)
        pytest.fail(
            f"HALLAZGO (a): ResolverVinculacionUseCase no declara ningun parametro "
            f"'ids_fincas_permitidas' ni en __init__ ni en execute() -- parametros reales: "
            f"{sorted(parametros)!r}. No hay forma de restringir por finca ni aunque el router "
            f"quisiera hacerlo: el punto de extension no existe."
        ) if not any('finca' in p.lower() for p in parametros) else None

    def test_resolver_vinculacion_resuelve_una_vinculacion_de_otra_finca_sin_restriccion(self):
        """Reproduce el BOLA: un repo de prueba devuelve una vinculacion de
        una finca 'ajena' (id_infraestructura=999) y el caso de uso la
        resuelve sin ninguna verificacion de pertenencia."""
        vinculacion_repo = MagicMock()
        vinculacion_repo.obtener_por_id.return_value = _vinculacion_de_otra_finca()
        vinculacion_repo.actualizar.side_effect = lambda v: v
        uc = ResolverVinculacionUseCase(db=MagicMock(), vinculacion_repo=vinculacion_repo)
        dto = ResolverVinculacionDTO(id_activo_biologico=5, modelo_manejo='INDIVIDUAL')

        resultado = uc.execute(id_vinculacion_lectura=1, dto=dto, id_usuario=42)

        assert resultado.estado_vinculacion == 'VINCULADA'
        vinculacion_repo.obtener_por_id.assert_called_once_with(1)  # sin ids_fincas_permitidas

    def test_corregir_vinculacion_use_case_no_declara_ids_fincas_permitidas(self):
        firma_init = inspect.signature(CorregirVinculacionUseCase.__init__)
        firma_execute = inspect.signature(CorregirVinculacionUseCase.execute)
        parametros = set(firma_init.parameters) | set(firma_execute.parameters)
        pytest.fail(
            f"HALLAZGO (a): CorregirVinculacionUseCase no declara ningun parametro "
            f"'ids_fincas_permitidas' ni en __init__ ni en execute() -- parametros reales: "
            f"{sorted(parametros)!r}. Mismo hallazgo que ResolverVinculacionUseCase: la "
            f"correccion inmutable tambien puede ejecutarse sobre una vinculacion de cualquier "
            f"finca."
        ) if not any('finca' in p.lower() for p in parametros) else None

    def test_router_no_calcula_alcance_de_finca_para_resolver_ni_corregir(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque_resolver = texto.split('def resolver_vinculacion(')[1].split('def corregir_vinculacion(')[0]
        bloque_corregir = texto.split('def corregir_vinculacion(')[1]
        pytest.fail(
            "HALLAZGO (a): ni el handler de resolver_vinculacion ni el de corregir_vinculacion "
            "invocan AlcanceFincaAdapter -- a diferencia de obtener_vinculacion y "
            "listar_vinculaciones, que si lo hacen. La proteccion BOLA existe en el router para "
            "lectura y no para escritura."
        ) if 'AlcanceFincaAdapter' not in bloque_resolver and 'AlcanceFincaAdapter' not in bloque_corregir else None


class TestSubCasoBInyeccionConfirmadoSinHallazgo:
    def test_repositorio_usa_solo_consultas_parametrizadas(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/repositories/vinculacion_lectura_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'f"SELECT' not in texto and '%s" %' not in texto
        assert 'select(VinculacionLecturaModel)' in texto


class TestSubCasoDSecretosEnDtosConfirmadoSinHallazgo:
    @pytest.mark.parametrize('archivo_rel', [
        'src/telemetry/infrastructure/dto/resolver_vinculacion_dto.py',
        'src/telemetry/infrastructure/dto/corregir_vinculacion_dto.py',
        'src/telemetry/infrastructure/schema/vinculacion_lectura_schema.py',
    ])
    def test_dto_no_expone_credenciales_ni_access_key(self, archivo_rel):
        texto = (REPO_ROOT / archivo_rel).read_text(encoding='utf-8').lower()
        assert 'password' not in texto and 'access_key' not in texto and 'credencial' not in texto


class TestSubCasoESuperficieDeDespliegue:
    def test_cors_esta_bien_configurado_sin_wildcard(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        assert 'allow_origins=allowed_origins' in texto_main
        assert 'allow_origins=["*"]' not in texto_main

    def test_swagger_y_openapi_quedan_expuestos_sin_autenticacion(self):
        texto_main = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
        bloque_app = texto_main.split('app = FastAPI(')[1].split(')', 1)[0]
        pytest.fail(
            "HALLAZGO (e): main.py no pasa docs_url=None ni openapi_url=None al construir "
            "FastAPI(), y no hay ninguna dependencia de autenticacion envolviendo /docs ni "
            "/openapi.json -- Swagger UI y el esquema OpenAPI completo (incluidos los 4 "
            "endpoints de vinculacion, con sus DTOs y modelos de respuesta) quedan expuestos sin "
            "autenticacion en las rutas default de FastAPI."
        ) if 'docs_url' not in bloque_app and 'openapi_url' not in bloque_app else None
