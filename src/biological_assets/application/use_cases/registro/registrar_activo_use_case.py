from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsultaPort
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, ValidationError

_TIPOS_NUMERICOS = {'PESO', 'VOLUMEN', 'LONGITUD'}
_TIPOS_ENTERO = {'CONTEO'}


def _validar_atributos_dinamicos(
    atributos: dict,
    tipo_activo: str,
    parametros_port: ParametrosEspeciePort,
    id_especie: int,
) -> None:
    parametros = parametros_port.listar_por_especie(id_especie, tipo_activo)
    nombres_validos = {p.nombre.lower(): p for p in parametros}

    for clave, valor in atributos.items():
        param = nombres_validos.get(clave.lower())
        if param is None:
            raise ValidationError(
                code='ATRIBUTO_INVALIDO',
                message=f"El atributo '{clave}' no corresponde a una métrica activa de la especie.",
                field='atributos_dinamicos',
            )
        tipo_med = param.tipo_medicion.upper()
        if tipo_med in _TIPOS_NUMERICOS:
            try:
                float(valor)
            except (TypeError, ValueError):
                raise ValidationError(
                    code='ATRIBUTO_TIPO_INVALIDO',
                    message=f"El atributo '{clave}' debe ser un valor numérico ({param.tipo_medicion}).",
                    field='atributos_dinamicos',
                )
        elif tipo_med in _TIPOS_ENTERO:
            if not isinstance(valor, int):
                raise ValidationError(
                    code='ATRIBUTO_TIPO_INVALIDO',
                    message=f"El atributo '{clave}' debe ser un entero ({param.tipo_medicion}).",
                    field='atributos_dinamicos',
                )


class RegistrarActivoBiologicoUseCase:

    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        especie_port: EspecieConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        parametros_port: ParametrosEspeciePort,
    ) -> None:
        self.db = db
        self.repo = repo
        self.especie_port = especie_port
        self.infra_port = infra_port
        self.parametros_port = parametros_port

    def execute(
        self,
        dto: RegistrarActivoBiologicoDTO,
        usuario: UsuarioActual,
    ) -> ActivoBiologico:
        # FA-05: especie activa
        especie = self.especie_port.obtener_activa(dto.id_especie)
        if not especie:
            raise ValidationError(
                code='ESPECIE_INVALIDA',
                message=f"La especie con id {dto.id_especie} no existe o no está activa.",
                field='id_especie',
            )

        # FA-06: infraestructura activa
        infra = self.infra_port.obtener_activa(dto.id_infraestructura)
        if not infra:
            raise ValidationError(
                code='INFRAESTRUCTURA_INVALIDA',
                message=f"La infraestructura con id {dto.id_infraestructura} no existe o no está activa.",
                field='id_infraestructura',
            )

        # FA-03: unicidad del identificador para INDIVIDUAL
        if dto.tipo_activo == 'INDIVIDUAL' and self.repo.existe_identificador(dto.identificador):
            raise ConflictError(
                code='IDENTIFICADOR_DUPLICADO',
                message=f"El identificador '{dto.identificador}' ya está registrado en el sistema.",
                field='identificador',
            )

        # FA-07: validar atributos_dinamicos
        if dto.atributos_dinamicos:
            _validar_atributos_dinamicos(
                dto.atributos_dinamicos,
                dto.tipo_activo,
                self.parametros_port,
                dto.id_especie,
            )

        activo = ActivoBiologico.crear(dto, usuario.id_usuario)

        try:
            activo = self.repo.guardar(activo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return activo
