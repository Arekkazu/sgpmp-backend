"""Caso de uso: Editar métrica de producción (Flujo J — RF-16).

Concurrencia optimista mediante ``fecha_actualizacion``.
Reglas aplicadas:
  FA-08 — nombre único por especie si el nombre cambia.
  FA-10 — unidad_medida coherente con tipo_medicion.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.repositories.auditoria_metrica_repository import AuditoriaMetricaRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.configuration.infrastructure.dto.editar_metrica_dto import EditarMetricaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError

_UNIDADES_POR_TIPO: dict[str, set[str] | None] = {
    'PESO': {'kg', 'g', 'lb'},
    'VOLUMEN': {'litros', 'ml'},
    'LONGITUD': {'cm', 'm'},
    'CONTEO': {'unidades'},
    'OTRO': None,
}


def _validar_coherencia_unidad(tipo_medicion: TipoMedicion, unidad_medida: str) -> None:
    unidades_validas = _UNIDADES_POR_TIPO.get(tipo_medicion.value)
    if unidades_validas is None:
        return
    if unidad_medida.strip().lower() not in unidades_validas:
        raise BusinessRuleError(
            code="UNIDAD_MEDIDA_INCOHERENTE",
            message=(
                f"La unidad '{unidad_medida}' no es válida para el tipo '{tipo_medicion.value}'. "
                f"Unidades permitidas: {', '.join(sorted(unidades_validas))}."
            ),
            field="unidad_medida",
        )


class EditarMetricaUseCase:

    def __init__(
        self,
        db: Session,
        metricas_repo: MetricaProduccionRepository,
        auditoria_repo: AuditoriaMetricaRepository,
    ) -> None:
        self.db = db
        self.metricas_repo = metricas_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        id_metrica_produccion: int,
        dto: EditarMetricaDTO,
        usuario_actual: UsuarioActual,
    ) -> MetricaProduccion:
        metrica = self.metricas_repo.obtener_por_id(id_metrica_produccion)
        if metrica is None:
            raise NotFoundError(
                code="METRICA_NO_ENCONTRADA",
                message=f"No existe una métrica con ID {id_metrica_produccion}.",
            )
        if not metrica.es_activo:
            raise BusinessRuleError(
                code="METRICA_INACTIVA",
                message="No se puede editar una métrica inactiva. Reactívela primero.",
            )

        ts_actual = metrica.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La métrica fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La métrica fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
            )

        nombre_nuevo = NombreMetrica(dto.nombre)
        tipo_medicion = TipoMedicion.desde_string(dto.tipo_medicion)
        aplica = AplicaTipoActivo.desde_string(dto.aplica_a_tipo_activo)

        _validar_coherencia_unidad(tipo_medicion, dto.unidad_medida)

        if nombre_nuevo.normalizado() != metrica.nombre.normalizado():
            duplicado = self.metricas_repo.obtener_por_nombre_y_especie(nombre_nuevo, metrica.id_especie)
            if duplicado is not None and duplicado.id_metrica_produccion != metrica.id_metrica_produccion:
                raise ConflictError(
                    code="METRICA_DUPLICADA",
                    message=f"Ya existe una métrica con el nombre '{nombre_nuevo.valor}' para esta especie.",
                    field="nombre",
                )

        snapshot_anterior = metrica._snapshot()
        metrica.actualizar(
            nombre=nombre_nuevo,
            unidad_medida=dto.unidad_medida.strip(),
            tipo_medicion=tipo_medicion,
            aplica_a_tipo_activo=aplica,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            metrica_actualizada = self.metricas_repo.actualizar(metrica)
            self.auditoria_repo.registrar(
                id_metrica_produccion=metrica_actualizada.id_metrica_produccion,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=metrica_actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return metrica_actualizada
