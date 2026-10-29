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
