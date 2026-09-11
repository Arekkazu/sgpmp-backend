from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria, HistorialActivo
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsultaPort
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError

def _validar_origen_financiero(dto: RegistrarActivoBiologicoDTO) -> None:
    # FA-08: coherencia costo_adquisicion/soporte_documental según origen_financiero.
    # Vive aquí (no en un @model_validator de Pydantic) para que el rechazo
    # sea BusinessRuleError -> 422, como exige el RF, y no un 400 genérico de
    # RequestValidationError.
    origen = dto.origen_financiero
    if origen in ('compra', 'donacion'):
        if not dto.costo_adquisicion or dto.costo_adquisicion <= 0:
            raise BusinessRuleError(
                code='COSTO_ADQUISICION_INVALIDO',
                message=f"costo_adquisicion mayor a 0 es requerido cuando origen_financiero es '{origen}'.",
                field='costo_adquisicion',
            )
        if not dto.soporte_documental:
            raise BusinessRuleError(
                code='SOPORTE_DOCUMENTAL_REQUERIDO',
                message=f"soporte_documental es requerido cuando origen_financiero es '{origen}'.",
                field='soporte_documental',
            )
    elif origen == 'nacimiento':
        if dto.costo_adquisicion is not None:
            raise BusinessRuleError(
                code='COSTO_ADQUISICION_INVALIDO',
                message="costo_adquisicion no aplica cuando origen_financiero es 'nacimiento'.",
                field='costo_adquisicion',
            )
        if dto.soporte_documental is not None:
            raise BusinessRuleError(
                code='SOPORTE_DOCUMENTAL_INVALIDO',
                message="soporte_documental no aplica cuando origen_financiero es 'nacimiento'.",
                field='soporte_documental',
            )


def _validar_atributos_dinamicos(
    atributos: dict,
    tipo_activo: str,
    parametros_port: ParametrosEspeciePort,
    id_especie: int,
) -> None:
    parametros = parametros_port.listar_por_especie(id_especie, tipo_activo)
    nombres_validos = {p.nombre.lower(): p for p in parametros}
    atributos_normalizados: dict[str, tuple[str, object]] = {}

    for clave, valor in atributos.items():
        if not isinstance(clave, str):
            raise ValidationError(
                code='ATRIBUTO_INVALIDO',
                message='Los nombres de atributos dinámicos deben ser texto.',
                field='atributos_dinamicos',
            )
        atributos_normalizados[clave.lower()] = (clave, valor)

    for nombre_normalizado, parametro in nombres_validos.items():
        entrada = atributos_normalizados.get(nombre_normalizado)
        if parametro.es_obligatorio and (entrada is None or entrada[1] is None):
            raise BusinessRuleError(
                code='ATRIBUTO_REQUERIDO',
                message=f"El atributo dinámico '{parametro.nombre}' es obligatorio.",
                field=f'atributos_dinamicos.{parametro.nombre}',
            )

    for clave, valor in atributos_normalizados.values():
        param = nombres_validos.get(clave.lower())
        if param is None:
            raise ValidationError(
                code='ATRIBUTO_INVALIDO',
                message=f"El atributo '{clave}' no corresponde a una métrica activa de la especie.",
                field='atributos_dinamicos',
            )
        if valor is None:
            continue

        tipo_dato = param.tipo_dato.upper()
        es_valido = False
        descripcion = tipo_dato.lower()
        if tipo_dato == 'NUMERICO':
            es_valido = isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool)
            if es_valido:
                try:
                    es_valido = Decimal(str(valor)).is_finite()
                except (InvalidOperation, ValueError):
                    es_valido = False
            descripcion = 'numérico'
        elif tipo_dato == 'ENTERO':
            es_valido = isinstance(valor, int) and not isinstance(valor, bool)
            descripcion = 'entero'
        elif tipo_dato == 'TEXTO':
            es_valido = isinstance(valor, str)
            descripcion = 'texto'
        elif tipo_dato == 'BOOLEANO':
            es_valido = isinstance(valor, bool)
            descripcion = 'booleano'

        if not es_valido:
            raise BusinessRuleError(
                code='ATRIBUTO_TIPO_INVALIDO',
                message=f"El atributo '{clave}' debe ser de tipo {descripcion}.",
                field=f'atributos_dinamicos.{clave}',
            )

        if tipo_dato in {'NUMERICO', 'ENTERO'}:
            numero = Decimal(str(valor))
            if param.valor_min is not None and numero < param.valor_min:
                raise BusinessRuleError(
                    code='ATRIBUTO_FUERA_DE_RANGO',
                    message=f"El atributo '{clave}' debe ser mayor o igual a {param.valor_min}.",
                    field=f'atributos_dinamicos.{clave}',
                )
            if param.valor_max is not None and numero > param.valor_max:
                raise BusinessRuleError(
                    code='ATRIBUTO_FUERA_DE_RANGO',
                    message=f"El atributo '{clave}' debe ser menor o igual a {param.valor_max}.",
                    field=f'atributos_dinamicos.{clave}',
                )


class RegistrarActivoBiologicoUseCase:

    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        especie_port: EspecieConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        parametros_port: ParametrosEspeciePort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.especie_port = especie_port
        self.infra_port = infra_port
        self.parametros_port = parametros_port
        self.bitacora_repo = bitacora_repo

    def execute(
        self,
        dto: RegistrarActivoBiologicoDTO,
        usuario: UsuarioActual,
    ) -> ActivoBiologico:
        # FA-08: costo_adquisicion/soporte_documental coherentes con origen_financiero
        _validar_origen_financiero(dto)

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
        _validar_atributos_dinamicos(
            dto.atributos_dinamicos or {},
            dto.tipo_activo,
            self.parametros_port,
            dto.id_especie,
        )

        activo = ActivoBiologico.crear(dto, usuario.id_usuario)

        try:
            activo = self.repo.guardar(activo)
            # RF-33: snapshot inicial (Evento 0) — version=1, tipo_evento=CREACION
            self.repo.registrar_historial(HistorialActivo(
                id_activo_biologico=activo.id_activo_biologico,
                version=1,
                tipo_evento='CREACION',
                snapshot=activo._snapshot(),
                fecha_evento=datetime.now(timezone.utc),
                id_usuario=usuario.id_usuario,
            ))
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if self.bitacora_repo:
                try:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF33', tipo_evento='ACTIVO_REGISTRO_FALLIDO',
                        clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                        severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                        detalle_tecnico={'error': str(exc)},
                        id_usuario_responsable=usuario.id_usuario,
                    ))
                    self.db.commit()
                except Exception:
                    pass
            raise

        if self.bitacora_repo:
            try:
                self.bitacora_repo.registrar(EventoAuditoria(
                    rf_origen='RF33', tipo_evento='ACTIVO_REGISTRADO',
                    clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
                    severidad_log='INFO', timestamp_evento=datetime.now(timezone.utc),
                    id_activo_biologico=activo.id_activo_biologico,
                    tipo_activo=activo.tipo,
                    descripcion=f'Activo biológico registrado: {activo.identificador or activo.id_activo_biologico}',
                    id_usuario_responsable=usuario.id_usuario,
                ))
                self.db.commit()
            except Exception:
                pass

        return activo
