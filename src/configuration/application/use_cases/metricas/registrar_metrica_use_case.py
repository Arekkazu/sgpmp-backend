"""Caso de uso: Registrar métrica de producción para una especie (Flujo I — RF-16).

Reglas aplicadas:
  FA-08 — nombre único por especie (case-insensitive).
  FA-10 — unidad_medida coherente con tipo_medicion.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.repositories.auditoria_metrica_repository import AuditoriaMetricaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.configuration.infrastructure.dto.registrar_metrica_dto import RegistrarMetricaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

# FA-10: unidades permitidas por tipo de medición (valores normalizados a minúsculas)
_UNIDADES_POR_TIPO: dict[str, set[str] | None] = {
    'PESO': {'kg', 'g', 'lb'},
    'VOLUMEN': {'litros', 'ml'},
    'LONGITUD': {'cm', 'm'},
    'CONTEO': {'unidades'},
    'OTRO': None,  # None significa cualquier valor
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


class RegistrarMetricaUseCase:

    def __init__(
        self,
        db: Session,
        metricas_repo: MetricaProduccionRepository,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaMetricaRepository,
    ) -> None:
        self.db = db
        self.metricas_repo = metricas_repo
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarMetricaDTO, usuario_actual: UsuarioActual) -> MetricaProduccion:
        especie = self.especies_repo.obtener_por_id(dto.id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {dto.id_especie}.",
            )
        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message=f"La especie con ID {dto.id_especie} está inactiva. No se pueden agregar métricas.",
            )

        nombre = NombreMetrica(dto.nombre)
        tipo_medicion = TipoMedicion.desde_string(dto.tipo_medicion)
        aplica = AplicaTipoActivo.desde_string(dto.aplica_a_tipo_activo)

        _validar_coherencia_unidad(tipo_medicion, dto.unidad_medida)

        existente = self.metricas_repo.obtener_por_nombre_y_especie(nombre, dto.id_especie)
        if existente is not None:
            raise ConflictError(
                code="METRICA_DUPLICADA",
                message=f"Ya existe una métrica con el nombre '{nombre.valor}' para esta especie.",
                field="nombre",
            )

        metrica = MetricaProduccion.crear(
            nombre=nombre,
            unidad_medida=dto.unidad_medida.strip(),
            tipo_medicion=tipo_medicion,
            aplica_a_tipo_activo=aplica,
            id_especie=dto.id_especie,
        )

        try:
            metrica_guardada = self.metricas_repo.guardar(metrica)
            self.auditoria_repo.registrar(
                id_metrica_produccion=metrica_guardada.id_metrica_produccion,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=metrica_guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return metrica_guardada
