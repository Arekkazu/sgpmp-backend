<<<<<<< HEAD
"""
TC-M03-G152 (RF-61 v1.2 CA-5/CA-11/E4/E6/E7/Restricciones 4 y 10/Fase B3,
CU-09) - "Vinculación retrospectiva de datos de buffer."

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/vincular_lectura_activo_use_case.py
    src/telemetry/infrastructure/adapters/activo_biologico_stub_adapter.py
    src/telemetry/domain/entities/vinculacion_lectura.py
    src/telemetry/infrastructure/models/vinculacion_lectura_model.py

HALLAZGO PRINCIPAL, RAÍZ PARA TODO RF-61: la única implementación real de
`ActivoBiologicoDependencyPort` es `ActivoBiologicoStubAdapter`, cuyo
método `obtener_activos_en_momento()` hace literalmente `return []`
siempre. Toda lectura vinculada hoy en el sistema real queda
SIN_VINCULAR, siempre -- no por ningún caso límite, sino porque el punto
de integración con M02 nunca fue implementado.

Segundo hallazgo: no existe ningún "Subcomponente B" de resolución
retrospectiva de buffer. `VincularLecturaActivoUseCase` se invoca siempre
en tiempo real, nunca como proceso batch/asíncrono. No existe
`POST /api/v1/links/batch-resolve`. El campo `fecha_fin_vinculacion` se
declara pero NINGÚN archivo le asigna jamás un valor distinto de `None`.

Tercer hallazgo: el catálogo real de `estado_vinculacion` es
`VINCULADA|SIN_VINCULAR|AMBIGUA|CORREGIDA` -- 4 valores, NUNCA
`CONFIRMADA`, `PENDIENTE_REVISION` ni `SUPERADA`.

(a) Fronteras fecha_inicio/fecha_fin -- HALLAZGO: inevaluable en la
    práctica porque el stub siempre devuelve lista vacía y
    fecha_fin_vinculacion nunca toma un valor real.
(b) "NO se usa timestamp de sincronización" -- CONFIRMADO PARCIALMENTE:
    el caso de uso sí pasa timestamp_captura, pero el puerto real lo
    ignora por completo.
(c) E4 fecha de baja -- HALLAZGO: no existe ningún concepto de "fecha de
    baja" en el puerto ni en el stub.
(d) Proceso asíncrono, PENDIENTE_REVISION -- HALLAZGO: no existe.
(e) Restricción 10 vía Fase B3, multi-animal -> AMBIGUA -- PARCIALMENTE
    CONFIRMADO Y MATIZADO: la regla de ambigüedad existe y está
    correctamente implementada, pero es código muerto: nunca puede
    ejecutarse en producción porque el stub jamás devuelve más de 0
    elementos.

Cómo se prueba: inspección directa del stub + pytest con un puerto doble
que SÍ simula 0/1/N activos.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g152_stub_m02_y_subcomponente_b_inexistente.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G152.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import (
    VincularLecturaActivoUseCase,
)
from src.telemetry.infrastructure.adapters.activo_biologico_stub_adapter import ActivoBiologicoStubAdapter

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _grep(termino: str) -> list[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
        if termino in p.read_text(encoding='utf-8', errors='ignore')
    ]


class TestSubCasoRaizElStubSiempreDevuelveSinVincular:
    def test_stub_devuelve_lista_vacia_sin_importar_el_timestamp(self):
        stub = ActivoBiologicoStubAdapter()
        resultado_a = stub.obtener_activos_en_momento(id_infraestructura=1, timestamp=AHORA)
        resultado_b = stub.obtener_activos_en_momento(id_infraestructura=999, timestamp=datetime(2000, 1, 1, tzinfo=timezone.utc))
        pytest.fail(
            f"HALLAZGO RAIZ: ActivoBiologicoStubAdapter.obtener_activos_en_momento() devuelve "
            f"{resultado_a!r} y {resultado_b!r} -- siempre lista vacia, sin importar "
            f"id_infraestructura ni timestamp."
        ) if resultado_a == [] and resultado_b == [] else None

    def test_use_case_con_el_puerto_real_siempre_produce_sin_vincular(self):
        vinculacion_repo = MagicMock()
        vinculacion_repo.guardar.side_effect = lambda v: v
        uc = VincularLecturaActivoUseCase(
            db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=ActivoBiologicoStubAdapter(),
        )
        resultado = uc.execute(id_telemetria=152, id_infraestructura=1, timestamp_captura=AHORA)
        assert resultado.estado_vinculacion == 'SIN_VINCULAR'
        assert resultado.id_activo_biologico is None


class TestSubCasoANoExisteSubcomponenteBRetrospectivo:
    def test_no_existe_endpoint_batch_resolve(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/routers/vinculacion_router.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (a)/(d): no existe ningun endpoint 'batch-resolve' ni ninguna ruta de "
            "resolucion masiva en vinculacion_router.py."
        ) if 'batch' not in texto.lower() else None

    def test_fecha_fin_vinculacion_nunca_se_asigna_un_valor_real(self):
        archivos_con_asignacion = [
            arch for arch in _grep('fecha_fin_vinculacion')
            if 'fecha_fin_vinculacion =' in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
            and 'fecha_fin_vinculacion = None' not in (REPO_ROOT / arch).read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (a): ningun archivo de src/telemetry/ asigna un valor distinto de None a "
            f"fecha_fin_vinculacion. Archivos con alguna asignacion no-None: "
            f"{archivos_con_asignacion or 'ninguno'}."
        ) if not archivos_con_asignacion else None

    def test_no_existe_proceso_asincrono_ni_estado_pendiente_revision(self):
        archivos_celery = _grep('celery') + _grep('asyncio.create_task') + _grep('background')
        archivos_pendiente = _grep('PENDIENTE_REVISION')
        archivos_confirmada = _grep('CONFIRMADA')
        pytest.fail(
            f"HALLAZGO (d): no hay ningun proceso asincrono/background job "
            f"({archivos_celery or 'ninguno'}), y los estados 'PENDIENTE_REVISION' "
            f"({archivos_pendiente or 'ninguno'}) y 'CONFIRMADA' ({archivos_confirmada or 'ninguno'}) "
            f"no existen en src/telemetry/."
        ) if not archivos_pendiente and not archivos_confirmada else None


class TestSubCasoEReglaDeAmbiguedadExisteYaEsAlcanzable:
    def test_con_dos_activos_simulados_la_regla_de_ambiguedad_si_funciona(self):
        activo_1 = MagicMock(id_activo_biologico=1, modelo_manejo='INDIVIDUAL')
        activo_2 = MagicMock(id_activo_biologico=2, modelo_manejo='INDIVIDUAL')
        activo_port_doble = MagicMock()
        activo_port_doble.obtener_activos_en_momento.return_value = [activo_1, activo_2]
        vinculacion_repo = MagicMock()
        vinculacion_repo.guardar.side_effect = lambda v: v
        uc = VincularLecturaActivoUseCase(
            db=MagicMock(), vinculacion_repo=vinculacion_repo, activo_port=activo_port_doble,
        )
        resultado = uc.execute(id_telemetria=152, id_infraestructura=1, timestamp_captura=AHORA)
        assert resultado.estado_vinculacion == 'AMBIGUA'
        assert resultado.id_activo_biologico is None

    def test_pero_el_adaptador_real_jamas_puede_producir_ese_escenario(self):
        pytest.fail(
            "HALLAZGO (e), matiz: la regla de ambiguedad esta bien implementada en codigo, pero "
            "es inalcanzable en el sistema real porque el unico ActivoBiologicoDependencyPort "
            "real (el stub) nunca devuelve mas de 0 elementos."
        )
=======
# | Fecha      | Nombre    | Que se hizo                                                                                           |
# |------------|-----------|-------------------------------------------------------------------------------------------------------|
# | 2026-10-27 | HulkyZeus | RF-61 TC-M03-G152: reconstruido desde el reporte del 2026-10-20 (el .py original no estaba en el repo) y actualizado a DEV-44 |
"""TC-M03-G152 (RF-61) - M02 como fuente de activos y subcomponente B (vinculacion retrospectiva).

RECONSTRUIDO: el script original (Windows, 2026-10-20) no esta en el repositorio; se rearmo a partir del codigo que traian los tracebacks de su
reporte HTML. Misma convencion: una prueba FALLA con "HALLAZGO" cuando la capacidad que pide la ficha RF-61 NO existe, y PASA cuando existe.

Cambios respecto al original (DEV-44, 2026-10-22):
  * El ActivoBiologicoStubAdapter de telemetria ya no existe: lo reemplaza ActivoBiologicoM02Adapter (consulta el historial real de M02).
  * 0 candidatos -> SIN_VINCULAR; 1 -> CONFIRMADA; mas de 1 -> PENDIENTE_REVISION (el estado AMBIGUA ya no se emite).

LIMITES (verificados contra TEST el 2026-10-27, por eso NO hay pruebas contra la API):
  * La vinculacion automatica corre en el worker post-commit: dentro del sandbox transaccional (nunca confirma) no se ejecuta.
  * /test-control/query corre como sgpmp_app con app.current_role vacio y el RLS le oculta todo modulo2: no ve los activos sembrados en el run
    (una prueba "area sin activos devuelve vacio" daria un falso positivo).
  * La conexion directa a la BD de TEST (TEST_DATABASE_URL) no respondio (timeout).
Por eso el adaptador real y el caso de uso se ejercitan sobre una BD simulada (determinista, sin red) y el resto es analisis de codigo.

Como correrlo (desde la raiz del repo, no necesita variables de entorno ni red):
    python -m pytest tests/Test_Testing/Test_Modulo3/RF-61/TC-M03-G152/test_tc_m03_g152_stub_m02_y_subcomponente_b_inexistente.py -v \
        --confcutdir=tests/Test_Testing/Test_Modulo3/RF-61/TC-M03-G152 -p no:cov --html=<ruta>/resultado_TC-M03-G152.html --self-contained-html
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_ROOT))
SRC_TELEMETRY = REPO_ROOT / "src" / "telemetry"
AHORA = datetime.now(timezone.utc)
AREA = 8

from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase  # noqa: E402
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter  # noqa: E402


def _grep(termino: str) -> list[str]:
    """Archivos .py de src/telemetry que contienen el termino (sin distinguir mayusculas)."""
    patron = re.compile(re.escape(termino), re.IGNORECASE)
    return sorted(
        str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        for p in SRC_TELEMETRY.rglob("*.py")
        if patron.search(p.read_text(encoding="utf-8", errors="ignore"))
    )


# ---------------------------------------------------------------- dobles de prueba
class _Resultado:
    def __init__(self, filas):
        self._filas = filas

    def all(self):
        return list(self._filas)


class _DbSimulada:
    """Sesion falsa: devuelve las filas de 'activos vigentes' que se le indiquen (lo que el SELECT del adaptador devolveria en la BD)."""

    def __init__(self, activos: list[tuple[int, str]]):
        self.activos = [SimpleNamespace(id_activo_biologico=i, modelo_manejo=m) for i, m in activos]
        self.confirmaciones = self.reversiones = 0

    def execute(self, *_a, **_k):
        return _Resultado(self.activos)

    def commit(self):
        self.confirmaciones += 1

    def rollback(self):
        self.reversiones += 1


class _AdaptadorSinLocks(ActivoBiologicoM02Adapter):
    """Adaptador REAL (mismo mapeo fila -> ActivoBiologicoInfo); solo se anulan los metodos que exigen una BD viva."""

    def bloquear_activos(self, identificadores):
        return None

    def historial_inconsistente(self, id_infraestructura, timestamp):
        return False

    def obtener_contexto(self, id_activo_biologico, timestamp):
        return {}


class _RepoEnMemoria:
    def __init__(self):
        self.guardadas = []

    def bloquear_lectura(self, _id):
        return None

    def ultima(self, _id):
        return None

    def contexto_lectura(self, _id, _ts):
        return {"areas": [AREA], "activos_directos": [], "id_sensor": 1, "id_dispositivo_iot": 1}

    def guardar(self, vinculacion):
        vinculacion.id_vinculacion_lectura = len(self.guardadas) + 1
        self.guardadas.append(vinculacion)
        return vinculacion


def _vincular(activos: list[tuple[int, str]]):
    db = _DbSimulada(activos)
    repo = _RepoEnMemoria()
    caso = VincularLecturaActivoUseCase(db=db, vinculacion_repo=repo, activo_port=_AdaptadorSinLocks(db))
    return caso.execute(id_telemetria=1, id_infraestructura=AREA, timestamp_captura=AHORA), db


# ================================================================== SUBCASO RAIZ: M02 como fuente de activos
class TestSubCasoRaizM02ComoFuenteDeActivos:
    def test_ningun_stub_de_activos_esta_cableado_en_telemetria(self):
        """Original: el stub devolvia siempre []. Hoy no debe quedar ningun ActivoBiologicoStubAdapter en uso dentro de telemetria."""
        usos = _grep("ActivoBiologicoStubAdapter")
        if usos:
            pytest.fail(f"HALLAZGO RAIZ: telemetria aun referencia ActivoBiologicoStubAdapter en {usos} (devuelve siempre lista vacia).")
        assert _grep("ActivoBiologicoM02Adapter"), "El adaptador real ActivoBiologicoM02Adapter no esta referenciado en telemetria."

    def test_el_adaptador_real_no_limita_los_candidatos(self):
        """El SELECT de obtener_activos_en_momento devuelve TODOS los activos vigentes (sin LIMIT ni .first()): base de la regla de ambiguedad."""
        fuente = (SRC_TELEMETRY / "infrastructure/adapters/activo_biologico_m02_adapter.py").read_text(encoding="utf-8")
        cuerpo = fuente.split("def obtener_activos_en_momento", 1)[1].split("def obtener_contexto", 1)[0]
        # los LIMIT 1 que hay son de las subconsultas de estado; la sentencia externa termina en ORDER BY, sin LIMIT
        assert ".all()" in cuerpo and ".first()" not in cuerpo
        assert "ORDER BY a.id_activo_biologico'''" in cuerpo, "la sentencia externa no debe llevar LIMIT"

    @pytest.mark.parametrize("filas,esperado", [([], 0), ([(11, "INDIVIDUAL")], 1), ([(11, "POBLACIONAL"), (12, "POBLACIONAL")], 2)])
    def test_el_adaptador_real_devuelve_tantos_activos_como_encuentra(self, filas, esperado):
        """Original: el puerto real devolvia siempre 0 elementos. Hoy el adaptador mapea 0, 1 o N filas a ActivoBiologicoInfo."""
        activos = ActivoBiologicoM02Adapter(_DbSimulada(filas)).obtener_activos_en_momento(AREA, AHORA)
        assert [(a.id_activo_biologico, a.modelo_manejo) for a in activos] == filas
        assert len(activos) == esperado


# ================================================================== SUBCASO A/D: subcomponente B retrospectivo
class TestSubCasoANoExisteSubcomponenteBRetrospectivo:
    def test_no_existe_endpoint_batch_resolve(self):
        texto = (REPO_ROOT / "src/telemetry/infrastructure/routers/vinculacion_router.py").read_text(encoding="utf-8")
        if "batch" not in texto.lower():
            pytest.fail("HALLAZGO (a)/(d): no existe ningun endpoint 'batch-resolve' ni ninguna ruta de resolucion masiva en vinculacion_router.py.")

    def test_fecha_fin_vinculacion_se_asigna_un_valor_real(self):
        archivos = [
            a for a in _grep("fecha_fin_vinculacion")
            if "fecha_fin_vinculacion =" in (REPO_ROOT / a).read_text(encoding="utf-8", errors="ignore")
            and "fecha_fin_vinculacion = None" not in (REPO_ROOT / a).read_text(encoding="utf-8", errors="ignore")
        ]
        if not archivos:
            pytest.fail("HALLAZGO (a): ningun archivo de src/telemetry/ asigna un valor distinto de None a fecha_fin_vinculacion.")

    def test_existe_proceso_asincrono_y_estados_pendiente_revision_y_confirmada(self):
        asincrono = _grep("celery") + _grep("asyncio.create_task") + _grep("background") + _grep("postcommit_worker")
        pendiente, confirmada = _grep("PENDIENTE_REVISION"), _grep("CONFIRMADA")
        if not asincrono or not pendiente or not confirmada:
            pytest.fail(f"HALLAZGO (d): proceso asincrono={asincrono or 'ninguno'}, PENDIENTE_REVISION={pendiente or 'ninguno'}, CONFIRMADA={confirmada or 'ninguno'}.")


# ================================================================== SUBCASO E: regla de ambiguedad con el adaptador real
class TestSubCasoEReglaDeAmbiguedadYaEsAlcanzable:
    def test_sin_activos_queda_sin_vincular(self):
        v, db = _vincular([])
        assert v.estado_vinculacion == "SIN_VINCULAR" and v.id_activo_biologico is None
        assert db.confirmaciones == 1 and db.reversiones == 0

    def test_con_un_activo_queda_confirmada(self):
        v, _ = _vincular([(11, "INDIVIDUAL")])
        assert v.estado_vinculacion == "CONFIRMADA" and v.id_activo_biologico == 11 and v.modelo_manejo == "INDIVIDUAL"

    def test_con_dos_activos_queda_pendiente_de_revision_y_no_elige_ninguno(self):
        """Original: 'con dos activos simulados la regla funciona' (AMBIGUA) y 'el real nunca podia producirla'. Hoy el adaptador real la alimenta."""
        v, _ = _vincular([(11, "POBLACIONAL"), (12, "POBLACIONAL")])
        assert v.estado_vinculacion == "PENDIENTE_REVISION" and v.id_activo_biologico is None and v.modelo_manejo == "POBLACIONAL"
        assert v.contexto_activo["candidatos"] == [11, 12]

    def test_con_dos_activos_de_modelos_distintos_no_se_selecciona_el_primer_modelo(self):
        from src.shared.errors import ServiceUnavailableError
        with pytest.raises(ServiceUnavailableError) as e:
            _vincular([(11, "INDIVIDUAL"), (12, "POBLACIONAL")])
        assert e.value.code == "MODELO_MANEJO_AMBIGUO"


if __name__ == "__main__":
    _aqui = Path(__file__).resolve().parent
    (_aqui / "resultados").mkdir(exist_ok=True)
    sys.exit(pytest.main([__file__, "-v", "--confcutdir=" + str(_aqui), "-p", "no:cov", "--html=" + str(_aqui / "resultados" / "resultado_TC-M03-G152.html"), "--self-contained-html"]))
>>>>>>> origin/test
