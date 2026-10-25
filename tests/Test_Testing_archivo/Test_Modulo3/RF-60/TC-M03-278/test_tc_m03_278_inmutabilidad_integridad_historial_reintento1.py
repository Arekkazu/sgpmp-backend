"""
TC-M03-278 (RF-60 Restricción 6/RNF-06, CU-15) - Inmutabilidad e integridad
del historial.

(a) CONFIRMADO, a nivel de BASE DE DATOS (más fuerte que lo que exige la
ficha, que solo pide verificarlo "desde la API y desde el usuario de BD de
la aplicación"): `alembic/baseline/esquema_baseline.sql` define
`trg_rf60_03_transiciones_no_update` (BEFORE UPDATE) y
`trg_rf60_04_transiciones_no_delete` (BEFORE DELETE) sobre
`modulo3.historico_transiciones_dispositivos`, ambos ejecutando
`fn_transiciones_dispositivo_append_only()`, que hace
`RAISE EXCEPTION 'RF-60: historico_transiciones_dispositivos es append-only.
No se permite %.', TG_OP` de forma INCONDICIONAL -- ni el usuario de la
aplicación ni ningún otro rol con permisos de escritura sobre la tabla puede
hacer UPDATE/DELETE, el trigger los rechaza a todos por igual. Esto es
estructuralmente MÁS SÓLIDO que lo que se encontró para la bitácora de RF-52
de M02 (ver memoria del proyecto: esa tabla NO tiene ningún trigger
protector, solo depende de que el router no exponga rutas de escritura).

HALLAZGO: la protección NO cubre `periodos_inactividad`, que la ficha pide
verificar igual que `historico_transiciones_dispositivos` ("UPDATE y DELETE
sobre transiciones Y periodos de inactividad... denegado en ambos"). Por
diseño, `periodos_inactividad` SÍ necesita ser mutable (una fila se abre con
`fecha_fin IS NULL` y se CIERRA más tarde con un UPDATE que fija `fecha_fin`
y `duracion_min` -- confirmado en `fn_procesar_heartbeat()` y
`fn_log_transicion_dispositivo()`, y en el propio `periodo_repo.cerrar()` de
Python). El problema es que esa necesidad legítima (cerrar un periodo) no
está acotada: no hay ningún trigger que impida un UPDATE ARBITRARIO sobre un
periodo YA CERRADO (cambiar `causa_primaria`, `duracion_min` o
`estado_durante_periodo` después del hecho), ni uno que bloquee el DELETE.
"Denegado en ambos" no se cumple -- solo se cumple para transiciones.

(b) HALLAZGO: no existe ningún hash ni firma sobre
`historico_transiciones_dispositivos` ni sobre `periodos_inactividad` (sin
columna `hash_integridad` en ninguno de los dos modelos/entidades). SÍ existe
un mecanismo de hash-chain real en el repositorio, pero es el de RF-63
(`bitacora_auditoria_iot`, `VerificarIntegridadBitacoraUseCase`,
`hash_integridad` en `evento_auditoria_iot.py`) -- y ese mecanismo NO cubre
las transiciones automáticas de RF-60: ni `recibir_heartbeat_use_case.py` ni
`evaluar_estado_dispositivos_use_case.py` llaman a
`RegistrarEventoAuditoriaIotUseCase` (solo lo hace el endpoint MANUAL de
mantenimiento, `aplicar_mantenimiento_dispositivo_use_case.py`). El
append-only de (a) hace indetectable una alteración por UPDATE/DELETE desde
la API o la aplicación (se rechaza), pero no da una forma independiente de
VERIFICAR que una fila no fue alterada por otra vía (ej. una migración mal
escrita, o un rol con permisos elevados que desactive el trigger
temporalmente) -- el hash hubiera cubierto justamente ese caso.

(c) NO EJECUTADO en esta sesión: un corte de almacenamiento inducido durante
10 transiciones simultáneas requiere infraestructura de chaos testing
(contenedor de BD que se pueda tumbar a mitad de una transacción) que esta
sesión no tiene. Se documenta en su lugar, a nivel de código, que cada caso
de uso envuelve sus escrituras en un único `try/except` con
`self.db.commit()`/`self.db.rollback()` (atomicidad a nivel de proceso/
transacción de SQLAlchemy) -- confirma que un fallo DENTRO de una llamada
no deja escrituras parciales de ESA llamada, pero no dice nada sobre un
corte de almacenamiento a mitad del COMMIT en el servidor de BD, que
necesita probarse contra la infraestructura real.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_278_inmutabilidad_integridad_historial.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-278.html --self-contained-html
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
BASELINE = REPO_ROOT / 'alembic' / 'baseline' / 'esquema_baseline.sql'


class TestGrupoAAppendOnlySoloParaTransiciones:

    def test_historico_transiciones_tiene_triggers_no_update_no_delete_incondicionales(self):
        texto = BASELINE.read_text(encoding='utf-8')
        assert re.search(
            r'CREATE TRIGGER trg_rf60_03_transiciones_no_update BEFORE UPDATE ON '
            r'modulo3\.historico_transiciones_dispositivos', texto
        )
        assert re.search(
            r'CREATE TRIGGER trg_rf60_04_transiciones_no_delete BEFORE DELETE ON '
            r'modulo3\.historico_transiciones_dispositivos', texto
        )
        inicio = texto.index('CREATE FUNCTION modulo3.fn_transiciones_dispositivo_append_only')
        fin = texto.index('$$;', inicio)
        cuerpo = texto[inicio:fin]
        assert 'RAISE EXCEPTION' in cuerpo
        assert 'es append-only' in cuerpo
        # Incondicional: sin ningun IF que distinga rol/usuario antes del RAISE.
        assert not re.search(r'IF\s+.*THEN', cuerpo), 'se esperaba un rechazo incondicional, sin excepciones por rol'

    def test_periodos_inactividad_NO_tiene_proteccion_append_only(self):
        texto = BASELINE.read_text(encoding='utf-8')
        triggers_sobre_periodos = re.findall(
            r'CREATE TRIGGER (\w+)[^;]*ON modulo3\.periodos_inactividad', texto
        )
        pytest.fail(
            f"HALLAZGO (a): periodos_inactividad no tiene ningun trigger propio (triggers "
            f"encontrados sobre esa tabla: {triggers_sobre_periodos or 'ninguno'}) -- a diferencia "
            f"de historico_transiciones_dispositivos, nada impide un UPDATE arbitrario sobre un "
            f"periodo ya cerrado (cambiar causa_primaria, duracion_min o estado_durante_periodo "
            f"despues del hecho), ni un DELETE. La ficha pide que ambas tablas queden protegidas "
            f"'en ambos'; solo una lo esta."
        ) if not triggers_sobre_periodos else None


class TestGrupoBSinHashNiFirmaParaTransicionesAutomaticas:

    def test_ni_transiciones_ni_periodos_tienen_campo_de_hash(self):
        from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo
        from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad

        campos_transicion = set(HistoricoTransicionDispositivo.__dataclass_fields__.keys())
        campos_periodo = set(PeriodoInactividad.__dataclass_fields__.keys())
        assert not any('hash' in c.lower() for c in campos_transicion)
        assert not any('hash' in c.lower() for c in campos_periodo)

    def test_las_transiciones_automaticas_nunca_pasan_por_el_mecanismo_de_hash_de_rf63(self):
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        menciones = [a.name for a in archivos if 'RegistrarEventoAuditoriaIot' in a.read_text(encoding='utf-8') or 'bitacora_auditoria_iot' in a.read_text(encoding='utf-8').lower()]
        pytest.fail(
            f"HALLAZGO (b): ni recibir_heartbeat_use_case.py ni evaluar_estado_dispositivos_use_case.py "
            f"llaman al mecanismo de hash-chain de RF-63 (RegistrarEventoAuditoriaIotUseCase) -- solo lo "
            f"usa el endpoint MANUAL de mantenimiento. Las transiciones AUTOMATICAS (la inmensa mayoria, "
            f"ya que el dispositivo rara vez entra a mantenimiento manual) quedan sin ninguna verificacion "
            f"de integridad independiente del append-only."
        ) if not menciones else None


class TestGrupoCChaosTestingFueraDeAlcanceDeEstaSesion:

    def test_atomicidad_a_nivel_de_proceso_si_esta_confirmada_estructuralmente(self):
        """No reemplaza el chaos testing real (c), solo confirma que cada caso de uso envuelve
        sus escrituras en un try/except con commit/rollback -- sin esto, ni vale la pena intentar
        el corte de almacenamiento, porque ya fallaria con cualquier excepcion comun."""
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        for a in archivos:
            texto = a.read_text(encoding='utf-8')
            assert 'self.db.commit()' in texto
            assert 'self.db.rollback()' in texto

    def test_chaos_de_corte_de_almacenamiento_no_ejecutado(self):
        pytest.skip(
            "(c) requiere infraestructura de chaos testing (contenedor de BD que se pueda tumbar a "
            "mitad de una transaccion con 10 transiciones simultaneas) no disponible en esta sesion. "
            "No se simula: un intento superficial (p.ej. matar la conexion desde el cliente) no prueba "
            "lo que la ficha pide, que es un corte real del almacenamiento subyacente."
        )
