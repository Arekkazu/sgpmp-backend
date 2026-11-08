"""
TC-M06-21 (RF-94 CA-3, CA-8, Restricciones 1, 2 y 3, RNF-03, RNF-07, CU-07) -
"Inmutabilidad append-only y retención."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Es el
único grupo de RF-94 donde el núcleo de la ficha se confirma correcto.

Código bajo prueba:
    alembic/baseline/esquema_baseline.sql (fn_tgr_m06_13_inmutabilidad_auditoria,
        CREATE TRIGGER tgr_m06_13_inmutabilidad_auditoria, comentarios de tabla/columna)
    src/financial_valuation/infrastructure/routers/m06_router.py (ausencia de rutas de escritura)

CONFIRMADO CORRECTO (no es un hallazgo, coincide con la ficha): SÍ existe
un trigger real, `fn_tgr_m06_13_inmutabilidad_auditoria()`, disparado
`BEFORE DELETE OR UPDATE ON modulo6.auditorias_financieras`, que:
  - Ante CUALQUIER `UPDATE`: `RAISE EXCEPTION '[TGR-M06-13] El registro de
    auditoría id=% es absolutamente inmutable... Ningún actor (incluido el
    Administrador) puede modificar registros de auditoría.'`
  - Ante CUALQUIER `DELETE`: `RAISE EXCEPTION '[TGR-M06-13] El registro de
    auditoría id=% no puede eliminarse...'`
Ninguna de las dos condiciones tiene excepción por rol -- ni siquiera el
Administrador puede sortear esto, porque el trigger no consulta ningún rol
ni usuario de sesión, se dispara incondicionalmente. Esto SÍ demuestra lo
que pide CA-3/RNF-03: la inmutabilidad no depende de la lógica de
aplicación, está en el motor de BD. El router real tampoco expone ningún
endpoint de escritura sobre auditoría (confirmado en TC-M06-13: solo existe
`GET /auditoria`), así que tampoco hay una vía de API para intentarlo.

HALLAZGO (matiza la retención: es un bloqueo PERMANENTE, no un plazo de
10 años con un comportamiento distinto después): la ficha enmarca la
retención como "10 años para períodos cerrados, sin límite para abiertos",
implicando una regla temporal con una frontera verificable (9 años 11
meses / 10 años exactos / 10 años y 1 día). El trigger real NO tiene
ninguna lógica de fechas -- bloquea el DELETE incondicionalmente, para
siempre, sin importar cuánto tiempo haya pasado ni si el período está
abierto o cerrado. No existe ninguna rama de código donde, tras cumplirse
los 10 años, el DELETE pase a estar permitido. Las 3 fronteras temporales
que pide la ficha (9a11m / 10a exactos / 10a+1d) son, por lo tanto,
INAPLICABLES: no hay ninguna frontera real que probar, porque el
comportamiento es idéntico (bloqueo total) en cualquier punto del tiempo.

HALLAZGO ("10 años" es solo texto de documentación, no una regla
computada): la única aparición de "10 años" en todo el esquema está en
`COMMENT ON TABLE`/`COMMENT ON COLUMN` -- comentarios de documentación de
PostgreSQL, no CHECK constraints, ni particiones por fecha, ni ningún job
que calcule años transcurridos. No hay ningún mecanismo que pudiera
"reducirse por configuración" (lo que pide probar la ficha) porque no hay
ningún parámetro de retención en absoluto que configurar -- ni para
reducir ni para ampliar.

HALLAZGO SECUNDARIO (contradice otra documentación del propio esquema,
relevante para TC-M06-24): el comentario de la tabla afirma "Comparte el
repositorio centralizado con RF-52 (M02), RF-63 (M03) y RF-73 (M04),
diferenciándose por el campo modulo_origen" -- pero (ver TC-M06-13) el
INSERT real de M06 hardcodea `modulo_origen='M06'` siempre, y
`modulo6.auditorias_financieras` es una tabla propia de M06, no una tabla
verdaderamente compartida entre módulos a nivel de esquema. Es, de nuevo,
documentación aspiracional, no una arquitectura verificable desde este
código.

Cómo se prueba: pytest de unidad por inspección del trigger real y de los
comentarios de esquema -- no requiere BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_21_inmutabilidad_appendonly_y_retencion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-21.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
BASELINE = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'


def _cuerpo_funcion(texto: str, nombre_funcion: str) -> str:
    return texto.split(f'{nombre_funcion}() RETURNS trigger')[1].split('$$;')[0]


class TestSubCasoLaInmutabilidadSiEsReconfirmadaPorDbSinExcepcionDeRol:
    def test_el_trigger_rechaza_update_incondicionalmente(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.fn_tgr_m06_13_inmutabilidad_auditoria')
        assert "TG_OP = 'UPDATE'" in cuerpo
        assert 'absolutamente inmutable' in cuerpo
        assert 'incluido el' in cuerpo and 'Administrador' in cuerpo

    def test_el_trigger_rechaza_delete_incondicionalmente(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.fn_tgr_m06_13_inmutabilidad_auditoria')
        assert "TG_OP = 'DELETE'" in cuerpo
        assert 'no puede eliminarse' in cuerpo

    def test_el_trigger_no_consulta_ningun_rol_ni_usuario_de_sesion(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.fn_tgr_m06_13_inmutabilidad_auditoria')
        assert 'current_user' not in cuerpo and 'has_role' not in cuerpo and 'pg_roles' not in cuerpo

    def test_el_router_real_no_expone_ninguna_ruta_de_escritura_sobre_auditoria(self):
        texto = ROUTER.read_text(encoding='utf-8')
        bloque_auditoria = texto.split('Auditoría (RF-94)')[1] if 'Auditoría (RF-94)' in texto else ''
        assert '@router.put' not in bloque_auditoria
        assert '@router.patch' not in bloque_auditoria
        assert '@router.delete' not in bloque_auditoria


class TestSubCasoLaRetencionEsUnBloqueoPermanenteNoUnPlazoConFronteraHallazgo:
    def test_el_trigger_no_tiene_ninguna_logica_de_fechas_ni_de_antiguedad(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.fn_tgr_m06_13_inmutabilidad_auditoria')
        tiene_logica_temporal = any(p in cuerpo for p in ('now()', 'fecha_registro', 'INTERVAL', 'EXTRACT', 'AGE('))
        pytest.fail(
            "HALLAZGO: el trigger de inmutabilidad no contiene ninguna logica de fechas/antiguedad "
            "(sin now(), INTERVAL, EXTRACT ni AGE()) -- bloquea DELETE de forma PERMANENTE, no por "
            "un plazo de 10 anos con un comportamiento distinto despues. Las fronteras temporales "
            "que pide la ficha (9a11m/10a exactos/10a+1d) no tienen ninguna rama de codigo real que "
            "las distinga."
        ) if not tiene_logica_temporal else None

    def test_el_10_anos_es_solo_un_comentario_de_documentacion_no_una_regla_computada(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: la unica aparicion de '10 años' en el esquema real esta dentro de "
            "COMMENT ON TABLE/COMMENT ON COLUMN (documentacion de Postgres) -- no hay ningun "
            "CHECK constraint, particion por fecha ni job que calcule la antiguedad del registro. "
            "No existe ningun parametro de retencion que 'reducirse por configuracion' pueda "
            "afectar, porque no hay ningun parametro de retencion en absoluto."
        ) if "COMMENT ON TABLE modulo6.auditorias_financieras IS 'Repositorio append-only" in texto else None


class TestSubCasoElComentarioDeRepositorioCentralizadoEsAspiracionalHallazgoSecundario:
    def test_el_comentario_de_tabla_afirma_un_repositorio_compartido_con_m02_m03_m04(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        assert 'Comparte el repositorio centralizado con RF-52 (M02), RF-63 (M03) y RF-73 (M04)' in texto

    def test_pero_el_insert_real_hardcodea_modulo_origen_a_m06_siempre(self):
        texto = (REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/'
                 'auditoria_financiera_repository.py').read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO SECUNDARIO (relevante para TC-M06-24): el comentario de esquema afirma un "
            "'repositorio centralizado' compartido con M02/M03/M04, pero el INSERT real de M06 "
            "hardcodea modulo_origen='M06' siempre -- modulo6.auditorias_financieras es una tabla "
            "propia de M06, no verificablemente compartida a nivel de aplicacion con otros modulos."
        ) if "'M06'" in texto else None
