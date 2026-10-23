# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: la regla C1 lee las especies del área (RFC-012) |
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
# | 2026-10-23 | destroyerban | DEV-23 RF-33/34/36/48: capacidad efectiva del área (RFC-012) |
"""Caso de uso: registro de un activo biológico nuevo (RF-33)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, EventoAuditoria, HistorialActivo, registros_rf46
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsultaPort
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsultaPort
from src.biological_assets.domain.repositories.parametros_especie_port import ParametrosEspeciePort
from src.biological_assets.domain.repositories.recalibracion_vision_port import RecalibracionVisionPort
from src.biological_assets.domain.services.edad_activo import evaluar_edad
from src.biological_assets.application.use_cases._capacidad_area import validar_entrada_al_area
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, AuthorizationError, BusinessRuleError, ConflictError, ValidationError
from src.shared.fechas import hoy_colombia

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
    elif origen == 'transferencia_interna':
        # costo_adquisicion es opcional; si se informa, debe ser > 0 y llevar
        # soporte_documental (RF-33). Sin costo, soporte tampoco se exige.
        if dto.costo_adquisicion is not None:
            if dto.costo_adquisicion <= 0:
                raise BusinessRuleError(
                    code='COSTO_ADQUISICION_INVALIDO',
                    message="costo_adquisicion debe ser mayor a 0 cuando se informa para 'transferencia_interna'.",
                    field='costo_adquisicion',
                )
            if not dto.soporte_documental:
                raise BusinessRuleError(
                    code='SOPORTE_DOCUMENTAL_REQUERIDO',
                    message="soporte_documental es requerido cuando costo_adquisicion se informa para 'transferencia_interna'.",
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
    """Registra un activo individual o un lote y su asociación inicial a infraestructura.

    Valida especie e infraestructura activas y dentro de las fincas del usuario,
    identificador único, origen financiero (costo y soporte documental en compras)
    y atributos dinámicos contra los parámetros de la especie. En lotes calcula
    la densidad inicial contra el máximo de la especie. Guarda el snapshot inicial
    (evento 0) y deja rastro en RF-52.
    """

    def __init__(
        self,
        db: Session,
        repo: ActivoBiologicoRepository,
        especie_port: EspecieConsultaPort,
        infra_port: InfraestructuraConsultaPort,
        parametros_port: ParametrosEspeciePort,
        bitacora_repo: BitacoraAuditoriaRepository | None = None,
        recalibracion_vision: RecalibracionVisionPort | None = None,
    ) -> None:
        self.db = db
        self.repo = repo
        self.especie_port = especie_port
        self.infra_port = infra_port
        self.parametros_port = parametros_port
        self.bitacora_repo = bitacora_repo
        self.recalibracion_vision = recalibracion_vision

    def execute(
        self,
        dto: RegistrarActivoBiologicoDTO,
        usuario: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ActivoBiologico:
        return ejecutar_con_auditoria_de_rechazo(
            lambda: self._execute(dto, usuario, ids_fincas_permitidas),
            db=self.db,
            bitacora_repo=self.bitacora_repo,
            obtener_activo=None,
            id_activo=None,
            id_usuario=usuario.id_usuario,
            rf_origen='RF33',
            tipo_evento_rechazado='ACTIVO_REGISTRO_RECHAZADO',
            clasificacion_biologica='GESTION_OPERATIVA',
        )

    def _execute(
        self,
        dto: RegistrarActivoBiologicoDTO,
        usuario: UsuarioActual,
        ids_fincas_permitidas: Optional[list[int]] = None,
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

        # M2-01 (reporte UAT 07/10): la infraestructura debe ser de una finca del
        # usuario. Antes un Productor registraba activos en fincas ajenas que
        # luego ni él mismo podía ver. ``None`` = alcance global (Administrador).
        if ids_fincas_permitidas is not None and infra.id_finca not in ids_fincas_permitidas:
            raise AuthorizationError(
                code='INFRAESTRUCTURA_FUERA_DE_ALCANCE',
                message='No tienes acceso a la finca de esta infraestructura. Elige una de tus fincas.',
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

        # RFC-012 (RF-33 1.4, DEV-23): reemplaza el chequeo monoespecie y el de densidad
        # por lote. Si la especie no está en el área se asocia (mismo grupo_manejo, si no
        # 422); toda especie necesita densidad (422); Σ individuos del área + los del
        # activo ≤ capacidad efectiva (422). INDIVIDUAL cuenta 1, POBLACIONAL su cantidad.
        entrantes = dto.cantidad_inicial if dto.tipo_activo == 'POBLACIONAL' else 1
        asociar_especie = validar_entrada_al_area(
            self.infra_port, infra, id_especie=dto.id_especie, entrantes=entrantes, field='id_infraestructura',
        )

        activo = ActivoBiologico.crear(dto, usuario.id_usuario)
        # RFC-014 (RF-33 1.4): edad ≥ esperanza de vida de la especie → advertencia,
        # nunca rechazo. Sin fecha de nacimiento o sin esperanza de vida no se evalúa.
        advertencia = evaluar_edad(dto.fecha_nacimiento, especie.esperanza_vida_dias, hoy_colombia())
        # INC-M02-37-G24 (TC-M02-048): la densidad (cantidad/superficie) es
        # calculable desde el momento del registro, no solo tras el primer
        # evento de crecimiento — sin esto un lote recién creado queda con
        # densidad=null hasta su primera medición. Su límite ya lo cubre la
        # capacidad efectiva del área (DEV-23).
        if activo.detalle_poblacional is not None:
            activo.recalcular_densidad(infra.superficie)

        try:
            if asociar_especie:
                self.infra_port.asociar_especie(infra.id_infraestructura, dto.id_especie)
            activo = self.repo.guardar(activo)
            # RF-33: snapshot inicial (Evento 0) — version=1, tipo_evento=CREACION
            historial = self.repo.registrar_historial(HistorialActivo(
                id_activo_biologico=activo.id_activo_biologico,
                version=1,
                tipo_evento='CREACION',
                snapshot=activo._snapshot(),
                fecha_evento=datetime.now(timezone.utc),
                id_usuario=usuario.id_usuario,
            ))
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
                rf_origen='RF33', tipo_evento='ACTIVO_REGISTRO_FALLIDO',
                clasificacion_biologica='GESTION_OPERATIVA', resultado='FALLIDO',
                severidad_log='ERROR', timestamp_evento=datetime.now(timezone.utc),
                detalle_tecnico={'error': str(exc)},
                id_usuario_responsable=usuario.id_usuario,
            ))
            raise

        detalle_tecnico = {'registros_rf46': registros_rf46(historial_activos=historial.id_historial_activo)}
        if advertencia is not None:
            activo.advertencia_edad = advertencia.mensaje
            detalle_tecnico['advertencia_edad'] = {
                'mensaje': advertencia.mensaje,
                'edad_dias': advertencia.edad_dias,
                'esperanza_vida_dias': advertencia.esperanza_vida_dias,
            }
        registrar_evento_bitacora(self.bitacora_repo, self.db, EventoAuditoria(
            rf_origen='RF33', tipo_evento='ACTIVO_REGISTRADO',
            clasificacion_biologica='GESTION_OPERATIVA', resultado='EXITOSO',
            # La advertencia no cambia el resultado (EXITOSO) pero sí la severidad, para filtrarla.
            severidad_log='WARNING' if advertencia is not None else 'INFO',
            timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=activo.id_activo_biologico,
            tipo_activo=activo.tipo,
            descripcion=f'Activo biológico registrado: {activo.identificador or activo.id_activo_biologico}',
            detalle_tecnico=detalle_tecnico,
            id_usuario_responsable=usuario.id_usuario,
        ))

        # RF-24 v2.0: un nuevo lote dispara la calibración por visión del área (#551).
        if self.recalibracion_vision is not None and activo.tipo == 'POBLACIONAL':
            self.recalibracion_vision.solicitar(
                activo.id_infraestructura,
                datetime.now(timezone.utc),
                f'Disparo automático M02: nuevo lote {activo.id_activo_biologico}',
            )

        return activo
