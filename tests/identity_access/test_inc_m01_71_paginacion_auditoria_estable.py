"""[TC-M01-71][#287] GET /auditoria/ repetía un evento entre páginas consecutivas.

`ConsultarAuditoriaUseCase.execute()` auditaba la propia consulta (paso 5,
`TIPO_CONSULTA_AUDITORIA`) con `fecha_evento=now()` DESPUÉS de listar los
resultados de la página actual, pero ANTES de que el cliente pidiera la
siguiente. Como el orden es "más reciente primero"
(`fecha_evento DESC, id_evento DESC`), esa fila nueva se colaba en la
posición 0 y desplazaba una fila hacia la página siguiente: el mismo evento
aparecía en la página N y en la N+1.

El fix fija un ancla temporal (`fecha_hasta_efectiva`) antes de consultar y
de autoauditar, y la devuelve en la respuesta para que el cliente la
reenvíe en las páginas siguientes — así ni la propia auto-auditoría ni
cualquier evento concurrente posterior al ancla entran al conjunto paginado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import (
    ConsultarAuditoriaUseCase,
)


@dataclass
class EventoFake:
    id_evento: int
    fecha_evento: datetime


class EventoRepoSimuladoFake:
    """Reproduce, en memoria, el ordenamiento y filtrado real del repositorio
    (`fecha_evento DESC, id_evento DESC`, `fecha_evento <= fecha_hasta`), y
    hace que `registrar()` inserte una fila nueva con `fecha_evento=now()` —
    igual que `SqlAlchemyEventoRepository.registrar()` hace de verdad."""

    def __init__(self, eventos_iniciales: list[EventoFake]) -> None:
        self.eventos = list(eventos_iniciales)
        self._siguiente_id = (max((e.id_evento for e in eventos_iniciales), default=0)) + 1
        self.llamadas_registrar = 0

    def _filtrados(self, fecha_hasta) -> list[EventoFake]:
        candidatos = self.eventos if fecha_hasta is None else [
            e for e in self.eventos if e.fecha_evento <= fecha_hasta
        ]
        return sorted(candidatos, key=lambda e: (e.fecha_evento, e.id_evento), reverse=True)

    def contar_eventos(self, *, fecha_hasta=None, **_ignorados) -> int:
        return len(self._filtrados(fecha_hasta))

    def listar_eventos(self, *, fecha_hasta=None, offset: int, limit: int, **_ignorados):
        pagina = self._filtrados(fecha_hasta)[offset: offset + limit]
        return [(evento, "INTEGRO") for evento in pagina]

    def registrar(self, **_kwargs) -> None:
        self.llamadas_registrar += 1
        self.eventos.append(EventoFake(self._siguiente_id, datetime.now(timezone.utc)))
        self._siguiente_id += 1


class UnidadTrabajoFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _usuario() -> SimpleNamespace:
    return SimpleNamespace(id_usuario=1, id_rol=1)


def _uc(repo: EventoRepoSimuladoFake) -> ConsultarAuditoriaUseCase:
    return ConsultarAuditoriaUseCase(eventos_repo=repo, db=UnidadTrabajoFake())


def _eventos_iniciales(cantidad: int, base: datetime) -> list[EventoFake]:
    # fecha_evento estrictamente creciente con el id, igual que en producción.
    return [EventoFake(i, base + timedelta(seconds=i)) for i in range(1, cantidad + 1)]


def test_sin_fecha_hasta_del_cliente_la_respuesta_fija_un_ancla() -> None:
    repo = EventoRepoSimuladoFake(_eventos_iniciales(10, datetime(2026, 1, 1, tzinfo=timezone.utc)))
    uc = _uc(repo)

    antes = datetime.now(timezone.utc)
    resultado = uc.execute(
        usuario_actual=_usuario(), id_usuario=None, tipo_evento=None,
        fecha_desde=None, fecha_hasta=None, pagina=1, tamano=20,
    )
    despues = datetime.now(timezone.utc)

    # El ancla lleva restado un margen de seguridad (INC-M01-71) para evitar
    # empates con el reloj del auto-registro de la propia consulta.
    assert antes - timedelta(seconds=1) <= resultado["fecha_hasta"] <= despues


def test_fecha_hasta_explicita_del_cliente_se_respeta_sin_modificar() -> None:
    ancla = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    repo = EventoRepoSimuladoFake(_eventos_iniciales(10, datetime(2026, 1, 1, tzinfo=timezone.utc)))
    uc = _uc(repo)

    resultado = uc.execute(
        usuario_actual=_usuario(), id_usuario=None, tipo_evento=None,
        fecha_desde=None, fecha_hasta=ancla, pagina=1, tamano=20,
    )

    assert resultado["fecha_hasta"] == ancla


def test_pagina_1_y_2_no_se_solapan_pese_al_auto_registro_de_la_consulta() -> None:
    """Reproduce el escenario exacto de TC-M01-71: se piden 3 páginas de 50 en
    secuencia, reenviando el `fecha_hasta` que devolvió cada página anterior
    (como ahora documenta el parámetro del endpoint), y se verifica que
    ningún `id_evento` aparece en dos páginas consecutivas — pese a que cada
    llamada inserta su propio evento de auto-auditoría entre medio."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo = EventoRepoSimuladoFake(_eventos_iniciales(180, base))
    uc = _uc(repo)

    fecha_hasta = None
    paginas_ids: list[set[int]] = []
    for pagina in (1, 2, 3):
        resultado = uc.execute(
            usuario_actual=_usuario(), id_usuario=None, tipo_evento=None,
            fecha_desde=None, fecha_hasta=fecha_hasta, pagina=pagina, tamano=50,
        )
        paginas_ids.append({evento.id_evento for evento, _ in resultado["items"]})
        fecha_hasta = resultado["fecha_hasta"]  # el cliente reenvía el ancla

    # Cada auto-registro de auditoría insertó una fila nueva en el repo (prueba
    # de que la contaminación que causaba el bug sigue ocurriendo)...
    assert repo.llamadas_registrar == 3
    # ...pero ninguna página comparte eventos con la siguiente.
    assert paginas_ids[0].isdisjoint(paginas_ids[1])
    assert paginas_ids[1].isdisjoint(paginas_ids[2])
    assert all(len(p) == 50 for p in paginas_ids)


def test_contar_y_listar_reciben_el_mismo_ancla_efectiva() -> None:
    repo = EventoRepoSimuladoFake(_eventos_iniciales(5, datetime(2026, 1, 1, tzinfo=timezone.utc)))

    filtros_recibidos: dict[str, list] = {"contar": [], "listar": []}
    contar_original = repo.contar_eventos
    listar_original = repo.listar_eventos
    repo.contar_eventos = lambda **kw: (filtros_recibidos["contar"].append(kw["fecha_hasta"]), contar_original(**kw))[1]
    repo.listar_eventos = lambda **kw: (filtros_recibidos["listar"].append(kw["fecha_hasta"]), listar_original(**kw))[1]

    uc = _uc(repo)
    resultado = uc.execute(
        usuario_actual=_usuario(), id_usuario=None, tipo_evento=None,
        fecha_desde=None, fecha_hasta=None, pagina=1, tamano=20,
    )

    assert filtros_recibidos["contar"] == [resultado["fecha_hasta"]]
    assert filtros_recibidos["listar"] == [resultado["fecha_hasta"]]
