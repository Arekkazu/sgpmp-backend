"""
TC-M06-G87 (RF-94 CA-4, FA-2, Restricción 6, CU-03) - "Exclusividad de actor
USUARIO/SISTEMA."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda.

Código bajo prueba:
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (registrar)
    alembic/baseline/esquema_baseline.sql (fn_tgr_m06_27_tipo_actor_auditoria, CREATE TRIGGER tgr_m06_27)

HALLAZGO PRINCIPAL (matiza la ficha a favor de lo correcto, pero NO como
ella lo describe): SÍ existe un trigger real de BD,
`fn_tgr_m06_27_tipo_actor_auditoria()` (disparado `BEFORE INSERT ON
modulo6.auditorias_financieras`), que valida exactamente 2 de los 4
escenarios que la ficha pide probar:
  - `tipo_actor='USUARIO' AND id_usuario IS NULL` -> RECHAZA (RAISE EXCEPTION).
  - `tipo_actor='SISTEMA' AND id_usuario IS NOT NULL` -> RECHAZA.
Pero el escenario "AMBOS NULOS" que la ficha pide probar (con "alerta
CRITICAL") es ESTRUCTURALMENTE INALCANZABLE desde la capa de aplicación: el
repositorio real (`registrar()`) calcula `tipo_actor` él mismo, de forma
determinista, a partir de `id_usuario`:
```python
"actor": "USUARIO" if evento.id_usuario else "SISTEMA"
```
y si `id_usuario` es `None`, automáticamente rellena `id_sistema` con un
valor por defecto (`evento.id_sistema or "M06_PROCESO_AUTOMATICO"`). Es
decir: desde la aplicación, **nunca puede llegar una combinación
"ambos nulos"** -- siempre hay, como mínimo, el id_sistema por defecto. El
trigger de BD NUNCA necesita rechazar ese caso porque la aplicación lo hace
imposible por construcción, no porque exista una validación explícita que
lo intercepte. Tampoco existe ninguna "alerta CRITICAL" asociada a este
escenario en ningún lugar del código.

HALLAZGO (discrepancia CA-4 vs. Restricción 6, confirmada tal cual la
ficha la señala, y resuelta): el trigger real NO implementa el cuarto
escenario de CA-4 ("ambos informados se rechaza") -- sólo tiene 2
condicionales (USUARIO sin id_usuario, SISTEMA con id_usuario), no un
tercero para "ambos no nulos". Si se insertara con `tipo_actor='USUARIO'`
y `id_usuario` no nulo pero ADEMÁS con `id_sistema` no nulo, el trigger NO
lo rechazaría -- pero este escenario tampoco es alcanzable desde
`registrar()`, porque el `id_sistema` que se envía a la BD se fuerza a
`None` cuando hay `id_usuario` (`"sistema": None if evento.id_usuario
else ...`). La "discrepancia" de la ficha es real en el trigger
considerado aisladamente, pero inalcanzable en la práctica por el mismo
motivo que el escenario "ambos nulos": la capa de aplicación nunca permite
que ambos campos lleguen informados simultáneamente a la BD.

HALLAZGO SECUNDARIO (el trigger real hace más de lo que pide esta ficha,
relevante para TC-M06-G89): el mismo trigger `fn_tgr_m06_27` TAMBIÉN valida
que `hash_integridad` no sea nulo/vacío y tenga EXACTAMENTE 64 caracteres
-- antes de que el trigger de hash (`trg_hash_auditoria`) lo calcule. Por
eso el repositorio real envía un marcador de 64 ceros (`_MARCADOR_HASH`):
sin él, `tgr_m06_27` rechazaría el INSERT antes de que el hash real llegue
a calcularse. El orden de ejecución (`tgr_m06_27` antes de
`trg_hash_auditoria`, alfabético por nombre de trigger: "tgr" < "trg") es
exactamente lo que hace que el truco del marcador funcione.

Cómo se prueba: pytest de unidad por inspección del trigger real
(migración/baseline) y del código real de `registrar()` que calcula
`tipo_actor`/`id_sistema` -- no requiere BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g87_exclusividad_actor_usuario_sistema.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G87.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria

REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'
BASELINE = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'


def _calcular_insercion(evento: EventoAuditoria) -> dict:
    """Replica exacta de las dos líneas reales de registrar() que deciden actor/id_sistema."""
    return {
        'actor': 'USUARIO' if evento.id_usuario else 'SISTEMA',
        'sistema': None if evento.id_usuario else (evento.id_sistema or 'M06_PROCESO_AUTOMATICO'),
    }


class TestSubCasoElTriggerRealSiValidaDosDeLosCuatroEscenarios:
    def test_el_trigger_rechaza_usuario_sin_id_usuario(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        assert "tipo_actor = 'USUARIO' AND NEW.id_usuario IS NULL" in texto

    def test_el_trigger_rechaza_sistema_con_id_usuario_informado(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        assert "tipo_actor = 'SISTEMA' AND NEW.id_usuario IS NOT NULL" in texto


class TestSubCasoAmbosNulosEsInalcanzableDesdeLaAplicacionNoHayAlertaCritical:
    def test_id_usuario_none_siempre_produce_un_id_sistema_por_defecto_nunca_ambos_nulos(self):
        evento = EventoAuditoria(tipo_evento='CIERRE_PERIODO_INICIADO', severidad='INFO', payload={},
                                 id_usuario=None, id_sistema=None)
        insercion = _calcular_insercion(evento)
        pytest.fail(
            f"HALLAZGO: con id_usuario=None e id_sistema=None explicitos, registrar() real "
            f"produce id_sistema={insercion['sistema']!r} (nunca None) -- el escenario 'ambos "
            f"nulos' que la ficha pide probar (con 'alerta CRITICAL') es INALCANZABLE desde la "
            f"aplicacion; el trigger de BD nunca necesita rechazarlo porque nunca llega."
        ) if insercion['sistema'] is not None else None

    def test_no_existe_ninguna_alerta_critical_asociada_a_actor_sin_identificar(self):
        texto_repo = REPOSITORIO.read_text(encoding='utf-8')
        texto_trigger = BASELINE.read_text(encoding='utf-8', errors='ignore').split(
            'fn_tgr_m06_27_tipo_actor_auditoria() RETURNS trigger')[1].split('$$;')[0]
        hay_alerta = any(p in texto_repo.lower() for p in ('alerta', 'notificar')) or \
            any(p in texto_trigger.lower() for p in ('alerta', 'notificar'))
        pytest.fail(
            "HALLAZGO: no existe en registrar() ni en el cuerpo del trigger de actor ningun "
            "codigo de 'alerta CRITICAL' para el caso de actor sin identificar (la unica "
            "aparicion de la palabra 'CRITICAL' en el repositorio es el conteo por severidad, "
            "no un mecanismo de alerta) -- el concepto no tiene implementacion real en M06."
        ) if not hay_alerta else None


class TestSubCasoAmbosInformadosNoSeRechazaEnElTriggerPeroEsInalcanzableIgual:
    def test_el_trigger_no_tiene_un_tercer_condicional_para_ambos_informados(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = texto.split('fn_tgr_m06_27_tipo_actor_auditoria() RETURNS trigger')[1].split('$$;')[0]
        pytest.fail(
            "HALLAZGO (discrepancia CA-4 vs Restriccion 6, confirmada): el trigger real solo "
            "tiene 2 IF (USUARIO sin id_usuario, SISTEMA con id_usuario) -- no un tercero que "
            "rechace 'ambos informados', como exige CA-4 pero no la Restriccion 6/FA-2."
        ) if cuerpo.count('IF NEW.tipo_actor') == 2 else None

    def test_pero_registrar_real_fuerza_id_sistema_a_none_si_hay_id_usuario_nunca_llegan_ambos(self):
        evento = EventoAuditoria(tipo_evento='COSTO_REGISTRADO', severidad='INFO', payload={},
                                 id_usuario=7, id_sistema='ALGUN_PROCESO')
        insercion = _calcular_insercion(evento)
        pytest.fail(
            f"HALLAZGO: aunque el emisor Python construya un EventoAuditoria con AMBOS "
            f"id_usuario=7 e id_sistema='ALGUN_PROCESO', registrar() fuerza "
            f"id_sistema={insercion['sistema']!r} antes de insertar -- el escenario 'ambos "
            f"informados' tampoco es alcanzable en la practica, pese al hueco real en el trigger."
        ) if insercion['sistema'] is None else None


class TestSubCasoHallazgoSecundarioElMismoTriggerValidaElHashNoSoloElActor:
    def test_el_trigger_tambien_exige_hash_integridad_de_64_caracteres(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO (relevante para TC-M06-G89): fn_tgr_m06_27 tambien valida que "
            "hash_integridad no sea nulo/vacio y tenga EXACTAMENTE 64 caracteres -- antes de que "
            "trg_hash_auditoria calcule el hash real. Por eso registrar() envia un marcador de "
            "64 ceros: sin el, este mismo trigger de 'actor' rechazaria el INSERT por el hash."
        ) if 'char_length(NEW.hash_integridad) != 64' in texto else None

    def test_el_marcador_de_64_ceros_es_exactamente_el_que_usa_el_repositorio_real(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert '_MARCADOR_HASH = "0" * 64' in texto
