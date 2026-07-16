from typing import Optional
import datetime
import decimal
import enum

from sqlalchemy import ARRAY, BigInteger, Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Identity, Index, Integer, JSON, Numeric, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class EnumNivelAlerta(str, enum.Enum):
    NORMAL = 'normal'
    PRECAUCION = 'precaucion'
    CRITICO = 'critico'


class EnumPatologiaCategoria(str, enum.Enum):
    METABOLICA = 'metabolica'
    PODAL = 'podal'
    DIARREICA = 'diarreica'
    RESPIRATORIA = 'respiratoria'


class EnumReglasAlertasTipoSensor(str, enum.Enum):
    HUMEDAD = 'HUMEDAD'
    TEMPERATURA = 'TEMPERATURA'
    OXIGENO = 'OXIGENO'
    PH = 'PH'
    AMONIACO = 'AMONIACO'
    SALINIDAD = 'SALINIDAD'
    LUMINOSIDAD = 'LUMINOSIDAD'


class EnumTipoInfraestructura(str, enum.Enum):
    CORRAL = 'corral'
    GALPON = 'galpon'
    POTRERO = 'potrero'
    ESTANQUE = 'estanque'
    INVERNADERO = 'invernadero'


class EnumUsuarioGenero(str, enum.Enum):
    M = 'M'
    X = 'X'
    F = 'F'
    T = 'T'


class Roles(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        PrimaryKeyConstraint('id_rol', name='roles_pkey'),
        UniqueConstraint('nombre_rol', name='uq_nombre'),
        {'comment': 'Catálogo de roles del sistema. Un rol agrupa un conjunto de '
                'permisos y define\n'
                'el nivel de acceso de los usuarios asignados. Permite gestionar '
                'la seguridad\n'
                'mediante control de acceso basado en roles (RBAC).',
     'schema': 'modulo1'}
    )

    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del rol. Clave primaria (serial).')
    nombre_rol: Mapped[str] = mapped_column(String(100), nullable=False, comment='Nombre único del rol (ej: ADMINISTRADOR, VETERINARIO, LIDER_AREA, AUDITOR).\nMáximo 100 caracteres. No puede repetirse.')
    es_protegido: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='Indica si el rol es de sistema y no puede ser modificado ni eliminado por usuarios.\nLos roles protegidos son creados durante la inicialización del sistema (ej: SUPERADMIN).')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del alcance y propósito del rol dentro del sistema.\nMáximo 255 caracteres.')
    fecha_creacion: Mapped[Optional[datetime.time]] = mapped_column(Time(True), server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que se creó el rol.')
    fecha_actualizacion: Mapped[Optional[datetime.time]] = mapped_column(Time(True), comment='Marca temporal (con zona horaria) de la última modificación del rol.\nDebe actualizarse mediante trigger.')

    usuarios: Mapped[list['Usuarios']] = relationship('Usuarios', back_populates='roles')


class CiclosProductivos(Base):
    __tablename__ = 'ciclos_productivos'
    __table_args__ = (
        PrimaryKeyConstraint('id_ciclo_productivo', name='ciclos_productivos_pkey'),
        {'comment': 'Ciclos operativos de producción definidos por el sistema. Pueden '
                'estar asociados opcionalmente a una etapa biológica específica.',
     'schema': 'modulo9'}
    )

    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del ciclo productivo.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre del ciclo productivo (ej: "Ciclo de engorde 2024-A").')
    duracion_dias: Mapped[int] = mapped_column(Integer, nullable=False, comment='Duración planificada del ciclo productivo en días.')
    id_ciclo_biologico: Mapped[Optional[int]] = mapped_column(Integer, comment='Ciclo biológico de referencia asociado a este ciclo productivo (opcional).')

    metricas_ciclo_productivo: Mapped[list['MetricasCicloProductivo']] = relationship('MetricasCicloProductivo', back_populates='ciclos_productivos')
    ciclos_productivos_biologicos: Mapped[list['CiclosProductivosBiologicos']] = relationship('CiclosProductivosBiologicos', back_populates='ciclos_productivos')


class DispositivosIot(Base):
    __tablename__ = 'dispositivos_iot'
    __table_args__ = (
        PrimaryKeyConstraint('id_dispositivo_iot', name='dispositivos_iot_pkey'),
        Index('uq_dispositivo_serial', 'serial', unique=True),
        {'comment': 'Dispositivo IoT físico (gateway, controlador, nodo) instalado en '
                'una infraestructura para gestionar la captura y transmisión de '
                'datos de sensores.',
     'schema': 'modulo9'}
    )

    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del dispositivo IoT en el sistema.')
    serial: Mapped[str] = mapped_column(String(50), nullable=False, comment='Número de serie o código MAC del dispositivo IoT físico.')
    descripcion: Mapped[str] = mapped_column(String(100), nullable=False, comment='Descripción del dispositivo, modelo o notas de instalación.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si el dispositivo está activo y comunicándose con la plataforma.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que el dispositivo fue registrado en el sistema.')

    sensores: Mapped[list['Sensores']] = relationship('Sensores', back_populates='dispositivos_iot')
    calibraciones: Mapped[list['Calibraciones']] = relationship('Calibraciones', back_populates='dispositivos_iot')
    configuraciones_remotas: Mapped[list['ConfiguracionesRemotas']] = relationship('ConfiguracionesRemotas', back_populates='dispositivos_iot')
    sensores_areas_asociadas: Mapped[list['SensoresAreasAsociadas']] = relationship('SensoresAreasAsociadas', back_populates='dispositivos_iot')


class Especies(Especies):
    __tablename__ = 'especies'
    __table_args__ = (
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='fk_ri_especies'),
        PrimaryKeyConstraint('id_especie', name='especies_pkey'),
        UniqueConstraint('nombre', name='uq_especie_nombre'),
        {'comment': 'Catálogo maestro de especies gestionadas en la plataforma (peces, '
                'crustáceos, cultivos, etc.).',
     'schema': 'modulo9'}
    )

    id_especie: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, comment='Identificador único de la especie.')
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre común o científico de la especie. Debe ser único.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se registró la especie en el sistema.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la especie está activa y disponible para su uso en el sistema.')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción general de la especie y sus características relevantes.')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora de la última modificación del registro.')

    ciclos_biologicos: Mapped[list['CiclosBiologicos']] = relationship('CiclosBiologicos', back_populates='especies')
    auditorias_especies: Mapped[list['AuditoriasEspecies']] = relationship('AuditoriasEspecies', back_populates='especies')
    gestion_especies_id_especie: Mapped[list['GestionEspecies']] = relationship('GestionEspecies', foreign_keys='[GestionEspecies.id_especie]', back_populates='especies')
    gestion_especies_id_especie_: Mapped[list['GestionEspecies']] = relationship('GestionEspecies', foreign_keys='[GestionEspecies.id_especie]', back_populates='especies_')
    plantillas: Mapped[list['Plantillas']] = relationship('Plantillas', back_populates='especies')
    especies_patologias: Mapped[list['EspeciesPatologias']] = relationship('EspeciesPatologias', back_populates='especies')


class MetricasProduccion(Base):
    __tablename__ = 'metricas_produccion'
    __table_args__ = (
        PrimaryKeyConstraint('id_metrica_produccion', name='metricas_produccion_pkey'),
        {'comment': 'Catálogo de métricas de producción medibles durante los ciclos '
                'productivos (ej: peso promedio, tasa de mortalidad, FCR).',
     'schema': 'modulo9'}
    )

    id_metrica_produccion: Mapped[int] = mapped_column(Integer, Sequence('metricas_produccion_id_metricas_produccion_seq', schema='modulo9'), primary_key=True, comment='Identificador único de la métrica.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre de la métrica de producción (ej: "Peso promedio", "Biomasa total").')
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False, comment='Unidad de medida de la métrica (ej: "kg", "g", "%", "ind").')
    tipo_medicion: Mapped[str] = mapped_column(String(55), nullable=False, comment='Clasifica el método o naturaleza de la medición (ej: "manual", "automatica", "calculada").')
    tiene_estado: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la métrica tiene un estado de alerta asociado (activa/inactiva u ok/alerta).')

    metricas_ciclo_productivo: Mapped[list['MetricasCicloProductivo']] = relationship('MetricasCicloProductivo', back_populates='metricas_produccion')


class NivelesAlertaAmbientales(Base):
    __tablename__ = 'niveles_alerta_ambientales'
    __table_args__ = (
        PrimaryKeyConstraint('id_nivel_alerta_ambiental', name='niveles_alerta_ambientales_pkey'),
        {'comment': 'Define los rangos numéricos de cada nivel de alerta (ej: NORMAL, '
                'PRECAUCIÓN, CRÍTICO) para un umbral ambiental dado.',
     'schema': 'modulo9'}
    )

    id_nivel_alerta_ambiental: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del nivel de alerta.')
    id_umbral_ambiental: Mapped[int] = mapped_column(Integer, nullable=False, comment='Umbral ambiental al que pertenece este nivel de alerta.')
    nivel: Mapped[EnumNivelAlerta] = mapped_column(Enum(EnumNivelAlerta, values_callable=lambda cls: [member.value for member in cls], name='enum_nivel_alerta', schema='modulo9'), nullable=False, comment='Tipo o severidad del nivel de alerta (valor del enum enum_nivel_alerta).')
    limite_inferior: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, comment='Valor mínimo del rango que activa este nivel de alerta.')
    limite_superior: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, comment='Valor máximo del rango que activa este nivel de alerta.')


class UmbralesAmbientales(Base):
    __tablename__ = 'umbrales_ambientales'
    __table_args__ = (
        PrimaryKeyConstraint('id_umbral_ambiental', name='umbrales_ambientales_pkey'),
        UniqueConstraint('nombre', name='uq_umbral_ambiental_nombre'),
        {'comment': 'Define los rangos de operación y niveles de alerta para una '
                'variable ambiental en el contexto de una especie específica.',
     'schema': 'modulo9'}
    )

    id_umbral_ambiental: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del umbral ambiental.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre descriptivo del umbral (ej: "Temperatura óptima tilapia"). Debe ser único.')
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False, comment='Unidad de medida asociada a los límites definidos en este umbral.')
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False, comment='Descripción del propósito y criterios de configuración del umbral.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si el umbral está activo y siendo evaluado por el sistema de alertas.')
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False, comment='Especie para la cual aplica este umbral ambiental.')
    id_variable_ambiental: Mapped[int] = mapped_column(Integer, nullable=False, comment='Variable ambiental sobre la que se definen los límites del umbral.')
    valor_min: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, server_default=text('0'))
    valor_max: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, server_default=text('100'))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, comment='Usuario que configuró o actualizó el umbral (opcional).')

    gestion_especies_id_umbral_ambiental: Mapped[list['GestionEspecies']] = relationship('GestionEspecies', foreign_keys='[GestionEspecies.id_umbral_ambiental]', back_populates='umbrales_ambientales')
    gestion_especies_id_umbral_ambiental_: Mapped[list['GestionEspecies']] = relationship('GestionEspecies', foreign_keys='[GestionEspecies.id_umbral_ambiental]', back_populates='umbrales_ambientales_')


class VariablesAmbientales(Base):
    __tablename__ = 'variables_ambientales'
    __table_args__ = (
        PrimaryKeyConstraint('id_variable_ambiental', name='variables_ambientales_pkey'),
        UniqueConstraint('nombre', name='uq_variable_ambiental_nombre'),
        {'comment': 'Catálogo de variables ambientales monitoreadas por los sensores '
                'IoT (ej: temperatura del agua, pH, oxígeno disuelto).',
     'schema': 'modulo9'}
    )

    id_variable_ambiental: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la variable ambiental.')
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre de la variable ambiental (ej: "Temperatura", "Oxígeno disuelto").')
    unidad: Mapped[str] = mapped_column(String(10), nullable=False, comment='Unidad de medida física de la variable (ej: "°C", "mg/L", "ppm").')
    valor_fisico_min: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 0), nullable=False, comment='Valor mínimo físicamente posible o aceptable para la variable según su naturaleza.')
    valor_fisico_max: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 0), nullable=False, comment='Valor máximo físicamente posible o aceptable para la variable según su naturaleza.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la variable está activa y siendo monitoreada actualmente.')


t_vw_rf15_dependencias_especie = Table(
    'vw_rf15_dependencias_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('nombre', String(50)),
    Column('umbrales_activos', BigInteger),
    Column('ciclos_activos', BigInteger),
    Column('patologias_asociadas', BigInteger),
    schema='modulo9'
)


t_vw_rf15_especies_activas_selector = Table(
    'vw_rf15_especies_activas_selector', Base.metadata,
    Column('id_especie', Integer),
    Column('nombre', String(50)),
    Column('descripcion', String(255)),
    schema='modulo9'
)


t_vw_rf15_especies_nombre_normalizado = Table(
    'vw_rf15_especies_nombre_normalizado', Base.metadata,
    Column('id_especie', Integer),
    Column('nombre', String(50)),
    Column('nombre_normalizado', Text),
    schema='modulo9'
)


t_vw_rf15_especies_resumen = Table(
    'vw_rf15_especies_resumen', Base.metadata,
    Column('id_especie', Integer),
    Column('nombre', String(50)),
    Column('descripcion', String(255)),
    Column('es_activo', Boolean),
    Column('fecha_creacion', DateTime(True)),
    Column('fecha_actualizacion', DateTime(True)),
    Column('total_ciclos', BigInteger),
    Column('total_patologias', BigInteger),
    schema='modulo9'
)


t_vw_rf16_cabecera_especie = Table(
    'vw_rf16_cabecera_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('nombre', String(50)),
    Column('total_etapas', BigInteger),
    Column('total_patologias', BigInteger),
    schema='modulo9'
)


t_vw_rf16_ciclos_biologicos_especie = Table(
    'vw_rf16_ciclos_biologicos_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('id_ciclo_biologico', Integer),
    Column('nombre', String(60)),
    Column('descripcion', String(255)),
    Column('duracion_dias', Integer),
    Column('ciclo_activo', Boolean),
    Column('especie', String(50)),
    Column('especie_activa', Boolean),
    schema='modulo9'
)


t_vw_rf16_ciclos_nombre_normalizado = Table(
    'vw_rf16_ciclos_nombre_normalizado', Base.metadata,
    Column('id_ciclo_biologico', Integer),
    Column('id_especie', Integer),
    Column('nombre', String(60)),
    Column('nombre_normalizado', Text),
    schema='modulo9'
)


t_vw_rf16_dependencias_ciclos = Table(
    'vw_rf16_dependencias_ciclos', Base.metadata,
    Column('id_ciclo_biologico', Integer),
    Column('nombre', String(60)),
    Column('referencias_productivas', BigInteger),
    schema='modulo9'
)


t_vw_rf16_dependencias_patologias = Table(
    'vw_rf16_dependencias_patologias', Base.metadata,
    Column('id_patologias', Integer),
    Column('nombre', String(60)),
    Column('especies_asociadas', BigInteger),
    Column('signos_asociados', BigInteger),
    Column('predicciones_asociadas', BigInteger),
    Column('alertas_asociadas', BigInteger),
    schema='modulo9'
)


t_vw_rf16_patologias_especie = Table(
    'vw_rf16_patologias_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('id_especies_patologias', Integer),
    Column('id_patologias', Integer),
    Column('nombre', String(60)),
    Column('descripcion', String(255)),
    Column('es_activo', Boolean),
    Column('nombre_tecnico', String(150)),
    Column('etiologia', Text),
    Column('categoria', Enum(EnumPatologiaCategoria, values_callable=lambda cls: [member.value for member in cls], name='enum_patologia_categoria', schema='modulo9')),
    Column('codigo_cie', String(150)),
    schema='modulo9'
)


t_vw_rf16_patologias_nombre_normalizado = Table(
    'vw_rf16_patologias_nombre_normalizado', Base.metadata,
    Column('id_patologias', Integer),
    Column('nombre', String(60)),
    Column('nombre_normalizado', Text),
    schema='modulo9'
)


t_vw_rf17_gestion_especies_historial = Table(
    'vw_rf17_gestion_especies_historial', Base.metadata,
    Column('id_ediciones_especies', Integer),
    Column('id_usuario', Integer),
    Column('usuario', Text),
    Column('fecha_gestion', DateTime(True)),
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('id_umbral_ambiental', Integer),
    Column('umbral_relacionado', String(60)),
    schema='modulo9'
)


t_vw_rf17_umbral_activo_por_especie_variable = Table(
    'vw_rf17_umbral_activo_por_especie_variable', Base.metadata,
    Column('id_especie', Integer),
    Column('id_variable_ambiental', Integer),
    Column('total_configuraciones_activas', BigInteger),
    Column('umbrales_activos', ARRAY(Integer())),
    schema='modulo9'
)


t_vw_rf17_umbrales_detalle_niveles = Table(
    'vw_rf17_umbrales_detalle_niveles', Base.metadata,
    Column('id_umbral_ambiental', Integer),
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('nombre', String(60)),
    Column('unidad_medida', String(20)),
    Column('descripcion', String(255)),
    Column('es_activo', Boolean),
    Column('id_variable_ambiental', Integer),
    Column('variable', String(50)),
    Column('unidad', String(10)),
    Column('valor_fisico_min', Numeric(8, 0)),
    Column('valor_fisico_max', Numeric(8, 0)),
    Column('niveles_alerta', JSON),
    schema='modulo9'
)


t_vw_rf17_variables_configuracion_especie = Table(
    'vw_rf17_variables_configuracion_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('id_variable_ambiental', Integer),
    Column('nombre', String(50)),
    Column('unidad', String(10)),
    Column('valor_fisico_min', Numeric(8, 0)),
    Column('valor_fisico_max', Numeric(8, 0)),
    Column('es_activo', Boolean),
    Column('ya_configurada', Boolean),
    Column('id_umbral_ambiental', Integer),
    Column('nombre_umbral', Text),
    Column('total_umbrales_activos', BigInteger),
    schema='modulo9'
)


t_vw_rf18_configuracion_global_activa = Table(
    'vw_rf18_configuracion_global_activa', Base.metadata,
    Column('id_configuracion_global', Integer),
    Column('frecuencia_muestreo', Integer),
    Column('heartbeat', Integer),
    Column('fecha_actualizacion', DateTime(True)),
    Column('es_activo', Boolean),
    Column('id_usuario', Integer),
    Column('modificado_por', Text),
    Column('correo_electronico', String(100)),
    schema='modulo9'
)


t_vw_rf18_configuraciones_globales_historial = Table(
    'vw_rf18_configuraciones_globales_historial', Base.metadata,
    Column('id_configuracion_global', Integer),
    Column('frecuencia_muestreo', Integer),
    Column('heartbeat', Integer),
    Column('fecha_actualizacion', DateTime(True)),
    Column('es_activo', Boolean),
    Column('id_usuario', Integer),
    Column('modificado_por', Text),
    schema='modulo9'
)


t_vw_rf19_dependencias_fincas = Table(
    'vw_rf19_dependencias_fincas', Base.metadata,
    Column('id_finca', Integer),
    Column('nombre', String(55)),
    Column('infra_activas', BigInteger),
    Column('dispositivos_activos', BigInteger),
    schema='modulo9'
)


t_vw_rf19_fincas_nombre_normalizado = Table(
    'vw_rf19_fincas_nombre_normalizado', Base.metadata,
    Column('id_finca', Integer),
    Column('id_usuario', Integer),
    Column('nombre', String(55)),
    Column('nombre_normalizado', Text),
    schema='modulo9'
)


t_vw_rf19_fincas_productor_resumen = Table(
    'vw_rf19_fincas_productor_resumen', Base.metadata,
    Column('id_usuario', Integer),
    Column('id_finca', Integer),
    Column('nombre', String(55)),
    Column('ubicacion', JSONB),
    Column('tamano_h', Numeric(8, 2)),
    Column('es_activo', Boolean),
    Column('fecha_creacion', TIMESTAMP(True, 0)),
    Column('fecha_actualizacion', DateTime(True)),
    Column('productor', Text),
    Column('correo_electronico', String(100)),
    Column('areas_activas', BigInteger),
    Column('total_areas', BigInteger),
    schema='modulo9'
)


t_vw_rf19_fincas_resumen_global = Table(
    'vw_rf19_fincas_resumen_global', Base.metadata,
    Column('total_fincas', BigInteger),
    Column('fincas_activas', BigInteger),
    Column('fincas_inactivas', BigInteger),
    schema='modulo9'
)


t_vw_rf19_productores_selector = Table(
    'vw_rf19_productores_selector', Base.metadata,
    Column('id_usuario', Integer),
    Column('nombre_completo', Text),
    Column('correo_electronico', String(100)),
    schema='modulo9'
)


t_vw_rf20_areas_finca_resumen = Table(
    'vw_rf20_areas_finca_resumen', Base.metadata,
    Column('id_finca', Integer),
    Column('id_infraestructura', Integer),
    Column('nombre', String(50)),
    Column('descripcion', String(100)),
    Column('tipo', Enum(EnumTipoInfraestructura, values_callable=lambda cls: [member.value for member in cls], name='enum_tipo_infraestructura', schema='modulo9')),
    Column('superficie', Numeric(10, 2)),
    Column('es_activo', Boolean),
    Column('dispositivos_activos', BigInteger),
    Column('total_dispositivos', BigInteger),
    schema='modulo9'
)


t_vw_rf20_areas_productivas_dispositivos = Table(
    'vw_rf20_areas_productivas_dispositivos', Base.metadata,
    Column('id_infraestructura', Integer),
    Column('id_finca', Integer),
    Column('area', String(50)),
    Column('tipo', Enum(EnumTipoInfraestructura, values_callable=lambda cls: [member.value for member in cls], name='enum_tipo_infraestructura', schema='modulo9')),
    Column('es_activo', Boolean),
    Column('finca', String(55)),
    Column('municipio', Text),
    Column('total_dispositivos', BigInteger),
    schema='modulo9'
)


t_vw_rf20_dependencias_infraestructuras = Table(
    'vw_rf20_dependencias_infraestructuras', Base.metadata,
    Column('id_infraestructura', Integer),
    Column('nombre', String(50)),
    Column('dispositivos_activos', BigInteger),
    schema='modulo9'
)


t_vw_rf20_fincas_activas_selector = Table(
    'vw_rf20_fincas_activas_selector', Base.metadata,
    Column('id_finca', Integer),
    Column('nombre', String(55)),
    Column('municipio', Text),
    Column('departamento', Text),
    Column('es_activo', Boolean),
    Column('productor', Text),
    Column('areas_activas', BigInteger),
    Column('total_areas', BigInteger),
    schema='modulo9'
)


t_vw_rf20_infraestructuras_nombre_normalizado = Table(
    'vw_rf20_infraestructuras_nombre_normalizado', Base.metadata,
    Column('id_infraestructura', Integer),
    Column('id_finca', Integer),
    Column('nombre', String(50)),
    Column('nombre_normalizado', Text),
    schema='modulo9'
)


t_vw_rf21_dispositivos_area_sensores = Table(
    'vw_rf21_dispositivos_area_sensores', Base.metadata,
    Column('id_infraestructura', Integer),
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('descripcion', String(100)),
    Column('es_activo', Boolean),
    Column('fecha_creacion', DateTime(True)),
    Column('total_sensores', BigInteger),
    Column('sensores_activos', BigInteger),
    schema='modulo9'
)


t_vw_rf21_dispositivos_sensores_asociacion = Table(
    'vw_rf21_dispositivos_sensores_asociacion', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('descripcion', String(100)),
    Column('es_activo', Boolean),
    Column('id_infraestructura', Integer),
    Column('area', String(50)),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    Column('total_sensores', BigInteger),
    Column('sensores_libres', BigInteger),
    Column('sensores_asociados', BigInteger),
    schema='modulo9'
)


t_vw_rf21_dispositivos_seriales = Table(
    'vw_rf21_dispositivos_seriales', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('serial_normalizado', Text),
    schema='modulo9'
)


t_vw_rf22_areas_destino_disponibles = Table(
    'vw_rf22_areas_destino_disponibles', Base.metadata,
    Column('id_infraestructura', Integer),
    Column('nombre', String(50)),
    Column('tipo', Enum(EnumTipoInfraestructura, values_callable=lambda cls: [member.value for member in cls], name='enum_tipo_infraestructura', schema='modulo9')),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    schema='modulo9'
)


t_vw_rf22_sensores_dispositivo_asociacion = Table(
    'vw_rf22_sensores_dispositivo_asociacion', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('id_sensores', Integer),
    Column('nombre', String(60)),
    Column('es_activo', Boolean),
    Column('id_sensores_area_asociada', Integer),
    Column('asociado_activo', Boolean),
    Column('punto_instalacion', String(100)),
    Column('id_infraestructura', Integer),
    Column('area_asociada', String(50)),
    Column('id_finca', Integer),
    Column('finca_asociada', String(55)),
    Column('fecha_asociacion', DateTime(True)),
    schema='modulo9'
)


t_vw_rf23_configuraciones_pendientes = Table(
    'vw_rf23_configuraciones_pendientes', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('id_configuracion_remota', Integer),
    Column('frecuencia_captura', Integer),
    Column('intervalo_transmision', Integer),
    Column('estado', String(15)),
    Column('fecha_creacion', DateTime(True)),
    schema='modulo9'
)


t_vw_rf23_dispositivos_configuracion_area = Table(
    'vw_rf23_dispositivos_configuracion_area', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('descripcion', String(100)),
    Column('es_activo', Boolean),
    Column('id_configuracion_remota', Integer),
    Column('frecuencia_captura', Integer),
    Column('intervalo_transmision', Integer),
    Column('estado_configuracion', String(15)),
    Column('fecha_configuracion', DateTime(True)),
    Column('fecha_aplicacion', DateTime(True)),
    Column('id_infraestructura', Integer),
    Column('area', String(50)),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    schema='modulo9'
)


t_vw_rf24_dispositivos_activos_calibraciones = Table(
    'vw_rf24_dispositivos_activos_calibraciones', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('descripcion', String(100)),
    Column('es_activo', Boolean),
    Column('id_infraestructura', Integer),
    Column('area', String(50)),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    Column('total_sensores', BigInteger),
    Column('total_calibraciones', BigInteger),
    Column('ultima_calibracion', DateTime(True)),
    schema='modulo9'
)


t_vw_rf24_historial_calibraciones_sensor = Table(
    'vw_rf24_historial_calibraciones_sensor', Base.metadata,
    Column('id_sensor', Integer),
    Column('id_calibracion', Integer),
    Column('fecha_calibracion', DateTime(True)),
    Column('valor_referencia', Numeric(10, 4)),
    Column('observaciones', Text),
    Column('id_usuario', Integer),
    Column('tecnico', Text),
    schema='modulo9'
)


t_vw_rf24_sensores_dispositivo_calibracion = Table(
    'vw_rf24_sensores_dispositivo_calibracion', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('id_sensores', Integer),
    Column('nombre', String(60)),
    Column('es_activo', Boolean),
    Column('ultima_calibracion', DateTime(True)),
    Column('ultimo_valor_referencia', Numeric(10, 4)),
    schema='modulo9'
)


t_vw_rf25_contexto_usuario = Table(
    'vw_rf25_contexto_usuario', Base.metadata,
    Column('id_usuario', Integer),
    Column('nombre_completo', Text),
    Column('id_rol', Integer),
    Column('nombre_rol', String(100)),
    Column('id_finca', Integer),
    Column('finca_activa', String(55)),
    Column('departamento', Text),
    Column('finca_activa_estado', Boolean),
    Column('especies_en_finca', ARRAY(Text())),
    schema='modulo9'
)


t_vw_rf25_permisos_roles = Table(
    'vw_rf25_permisos_roles', Base.metadata,
    Column('id_rol', Integer),
    Column('nombre_rol', String(100)),
    Column('modulo', String(60)),
    Column('accion', String(50)),
    Column('codigo_accion', CHAR(1)),
    Column('id_permiso', Integer),
    Column('permiso', String(50)),
    Column('es_activo', Boolean),
    schema='modulo9'
)


t_vw_rf26_auditorias_visuales_historial = Table(
    'vw_rf26_auditorias_visuales_historial', Base.metadata,
    Column('id_auditoria_visual', Integer),
    Column('fecha_creacion', DateTime(True)),
    Column('valor_anterior', JSONB),
    Column('valor_nuevo', JSONB),
    Column('id_usuario', Integer),
    Column('usuario', Text),
    schema='modulo9'
)


t_vw_rf26_identidad_visual_activa = Table(
    'vw_rf26_identidad_visual_activa', Base.metadata,
    Column('id_finca', Integer),
    Column('id_identidad_visual', Integer),
    Column('logo_path', String(255)),
    Column('primary_color', String(7)),
    Column('secondary_color', String(7)),
    Column('org_display_name', String(50)),
    Column('version', Integer),
    Column('fecha_creacion', DateTime(True)),
    Column('finca', String(55)),
    Column('id_usuario', Integer),
    Column('modificado_por', Text),
    schema='modulo9'
)


t_vw_rf27_preferencias_tema_usuarios = Table(
    'vw_rf27_preferencias_tema_usuarios', Base.metadata,
    Column('id_usuario', Integer),
    Column('usuario', Text),
    Column('nombre_rol', String(100)),
    Column('id_tema_visual', Integer),
    Column('theme_mode', Integer),
    Column('es_global', Boolean),
    Column('fecha_actualizacion', DateTime(True)),
    schema='modulo9'
)


t_vw_rf27_tema_usuario_global = Table(
    'vw_rf27_tema_usuario_global', Base.metadata,
    Column('id_usuario', Integer),
    Column('id_preferencia_usuario', Integer),
    Column('tema_usuario', Integer),
    Column('actualizado_en', DateTime(True)),
    Column('tema_global', Integer),
    Column('usuario', Text),
    schema='modulo9'
)


t_vw_rf28_dashboard_layout_usuario = Table(
    'vw_rf28_dashboard_layout_usuario', Base.metadata,
    Column('id_usuario', Integer),
    Column('id_dashboard_layout', Integer),
    Column('config', JSONB),
    Column('active_widget', ARRAY(Text())),
    Column('fecha_actualizacion', DateTime(True)),
    Column('total_widgets_configurados', Integer),
    schema='modulo9'
)


t_vw_rf28_widget_dispositivos_sin_configuracion = Table(
    'vw_rf28_widget_dispositivos_sin_configuracion', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('descripcion', String(100)),
    Column('id_infraestructura', Integer),
    Column('area', String(50)),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    schema='modulo9'
)


t_vw_rf28_widget_estado_dispositivos = Table(
    'vw_rf28_widget_estado_dispositivos', Base.metadata,
    Column('id_dispositivo_iot', Integer),
    Column('serial', String(50)),
    Column('es_activo', Boolean),
    Column('id_infraestructura', Integer),
    Column('area', String(50)),
    Column('id_finca', Integer),
    Column('finca', String(55)),
    Column('ultima_calibracion', DateTime(True)),
    Column('frecuencia_captura', Integer),
    Column('intervalo_transmision', Integer),
    Column('estado_configuracion', String(15)),
    schema='modulo9'
)


t_vw_rf28_widget_estado_fincas = Table(
    'vw_rf28_widget_estado_fincas', Base.metadata,
    Column('id_finca', Integer),
    Column('nombre', String(55)),
    Column('es_activo', Boolean),
    Column('departamento', Text),
    Column('areas_activas', BigInteger),
    Column('dispositivos_activos', BigInteger),
    schema='modulo9'
)


t_vw_rf29_idioma_usuario_global = Table(
    'vw_rf29_idioma_usuario_global', Base.metadata,
    Column('id_usuario', Integer),
    Column('id_preferencia_idioma', Integer),
    Column('idioma_usuario', String(5)),
    Column('es_por_defecto', Boolean),
    Column('fecha_actualizacion', DateTime(True)),
    Column('idioma_global', String(5)),
    Column('usuario', Text),
    schema='modulo9'
)


t_vw_rf29_preferencias_idioma_usuarios = Table(
    'vw_rf29_preferencias_idioma_usuarios', Base.metadata,
    Column('id_usuario', Integer),
    Column('usuario', Text),
    Column('nombre_rol', String(100)),
    Column('id_preferencia_idioma', Integer),
    Column('locale_code', String(5)),
    Column('es_por_defecto', Boolean),
    Column('fecha_actualizacion', DateTime(True)),
    schema='modulo9'
)


t_vw_rf31_params_disponibles_especie = Table(
    'vw_rf31_params_disponibles_especie', Base.metadata,
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('params_disponibles', JSON),
    schema='modulo9'
)


t_vw_rf31_plantillas_listado = Table(
    'vw_rf31_plantillas_listado', Base.metadata,
    Column('id_plantilla', Integer),
    Column('template_name', String(50)),
    Column('version', Integer),
    Column('fecha_creacion', DateTime(True)),
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('id_usuario', Integer),
    Column('creado_por', Text),
    Column('total_umbrales', Integer),
    Column('total_ciclos', Integer),
    Column('total_metricas', Integer),
    schema='modulo9'
)


t_vw_rf31_plantillas_nombre_normalizado = Table(
    'vw_rf31_plantillas_nombre_normalizado', Base.metadata,
    Column('id_plantilla', Integer),
    Column('template_name', String(50)),
    Column('template_name_normalizado', Text),
    schema='modulo9'
)


t_vw_rf31_plantillas_resumen = Table(
    'vw_rf31_plantillas_resumen', Base.metadata,
    Column('total_plantillas', BigInteger),
    Column('especies_cubiertas', BigInteger),
    Column('nombres_unicos', BigInteger),
    schema='modulo9'
)


t_vw_rf32_plantillas_detalle = Table(
    'vw_rf32_plantillas_detalle', Base.metadata,
    Column('id_plantilla', Integer),
    Column('template_name', String(50)),
    Column('version', Integer),
    Column('fecha_creacion', DateTime(True)),
    Column('params_snapshot', JSONB),
    Column('id_especie', Integer),
    Column('especie', String(50)),
    Column('especie_activa', Boolean),
    Column('id_usuario', Integer),
    Column('creado_por', Text),
    schema='modulo9'
)


t_vw_rf33_aplicaciones_plantillas_historial = Table(
    'vw_rf33_aplicaciones_plantillas_historial', Base.metadata,
    Column('id_plantilla', Integer),
    Column('id_aplicacion_plantilla', Integer),
    Column('target_config', JSONB),
    Column('before_snapshot', JSONB),
    Column('after_snapshot', JSONB),
    Column('fecha_aplicacion', DateTime(True)),
    Column('id_usuario', Integer),
    Column('aplicado_por', Text),
    Column('template_name', String(50)),
    Column('version', Integer),
    schema='modulo9'
)


class Usuarios(Base):
    __tablename__ = 'usuarios'
    __table_args__ = (
        CheckConstraint("apellidos::text ~ '^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$'::text", name='chk_usuario_apellidos_validos'),
        CheckConstraint("correo_electronico::text ~* '^[A-Za-z0-9._%%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'::text", name='chk_usuario_formato_correo'),
        CheckConstraint("nombre::text ~ '^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$'::text", name='chk_usuario_nombre_validos'),
        CheckConstraint("tipo_identificacion::text = ANY (ARRAY['CC'::character varying::text, 'CE'::character varying::text, 'Pasaporte'::character varying::text])", name='chk_usuario_tipo_identificacion'),
        ForeignKeyConstraint(['id_rol'], ['modulo1.roles.id_rol'], name='fk_rol'),
        PrimaryKeyConstraint('id_usuario', name='usuarios_pkey'),
        UniqueConstraint('correo_electronico', name='uq_usuario_correo_electronico'),
        UniqueConstraint('numero_identificacion', name='uq_usuario_numero_identificacion'),
        {'comment': 'Tabla maestra de usuarios del sistema. Almacena la información '
                'personal,\n'
                'de autenticación y de rol de cada persona registrada. Es la '
                'entidad central\n'
                'del módulo 1 y es referenciada por prácticamente todos los demás '
                'módulos\n'
                'del sistema para asociar acciones a un usuario específico.',
     'schema': 'modulo1'}
    )

    id_usuario: Mapped[int] = mapped_column(Integer, Sequence('usuarios_id_usuarios_seq', schema='modulo1'), primary_key=True, comment='Identificador único del usuario. Clave primaria generada automáticamente (serial).\nEs la FK más referenciada en todo el sistema.')
    tipo_identificacion: Mapped[str] = mapped_column(String(10), nullable=False, comment='Tipo de documento de identidad del usuario (ej: CC, CE, NIT, PA).\nMáximo 10 caracteres. Usado junto con numero_identificacion para identificación civil.')
    numero_identificacion: Mapped[str] = mapped_column(String(20), nullable=False, comment='Número del documento de identidad del usuario. Único en el sistema.\nMáximo 20 caracteres. No puede repetirse sin importar el tipo de identificación.')
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, comment='Nombre(s) del usuario. Máximo 80 caracteres.')
    apellidos: Mapped[str] = mapped_column(String(80), nullable=False, comment='Apellido(s) del usuario. Máximo 80 caracteres.')
    fecha_nacimiento: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment='Fecha de nacimiento del usuario. Usada para validaciones de edad mínima\ny para perfiles demográficos.')
    genero: Mapped[EnumUsuarioGenero] = mapped_column(Enum(EnumUsuarioGenero, values_callable=lambda cls: [member.value for member in cls], name='enum_usuario_genero', schema='modulo1'), nullable=False, comment='Género del usuario. ENUM global del sistema (enum_usuario_genero).')
    correo_electronico: Mapped[str] = mapped_column(String(100), nullable=False, comment='Dirección de correo electrónico del usuario. Única en el sistema.\nEs el canal principal de comunicación y recuperación de cuenta. Máximo 100 caracteres.')
    contrasena_cifrada: Mapped[str] = mapped_column(String(255), nullable=False, comment='Hash de la contraseña del usuario. Nunca se almacena la contraseña en texto plano.\nSe recomienda bcrypt o argon2. Máximo 255 caracteres.')
    id_rol: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.roles. Define el rol asignado al usuario, que determina\nsus permisos y accesos dentro del sistema.')
    fecha_registro: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que el usuario fue creado en el sistema.\nSe asigna automáticamente con now().')
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'), comment='Contador de versión del registro. Se incrementa con cada actualización.\nPermite control de concurrencia optimista (optimistic locking).')
    telefono: Mapped[Optional[str]] = mapped_column(String(20), comment='Número de teléfono de contacto del usuario. Opcional. Máximo 20 caracteres.')
    direccion: Mapped[Optional[str]] = mapped_column(String(150), comment='Dirección física de residencia o contacto del usuario. Opcional. Máximo 150 caracteres.')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'), comment='Marca temporal (con zona horaria) de la última modificación del registro del usuario.\nDebe actualizarse mediante trigger cada vez que el registro cambie.')

    roles: Mapped['Roles'] = relationship('Roles', back_populates='usuarios')
    auditorias_especies: Mapped[list['AuditoriasEspecies']] = relationship('AuditoriasEspecies', back_populates='usuarios')
    auditorias_visuales: Mapped[list['AuditoriasVisuales']] = relationship('AuditoriasVisuales', back_populates='usuarios')
    calibraciones: Mapped[list['Calibraciones']] = relationship('Calibraciones', back_populates='usuarios')
    configuraciones_globales: Mapped[list['ConfiguracionesGlobales']] = relationship('ConfiguracionesGlobales', back_populates='usuarios')
    configuraciones_remotas: Mapped[list['ConfiguracionesRemotas']] = relationship('ConfiguracionesRemotas', back_populates='usuarios')
    dashboard_layouts: Mapped[list['DashboardLayouts']] = relationship('DashboardLayouts', back_populates='usuarios')
    fincas: Mapped[list['Fincas']] = relationship('Fincas', back_populates='usuarios')
    gestion_especies: Mapped[list['GestionEspecies']] = relationship('GestionEspecies', back_populates='usuarios')
    patologias: Mapped[list['Patologias']] = relationship('Patologias', back_populates='usuarios')
    plantillas: Mapped[list['Plantillas']] = relationship('Plantillas', back_populates='usuarios')
    preferencias_idiomas: Mapped[list['PreferenciasIdiomas']] = relationship('PreferenciasIdiomas', back_populates='usuarios')
    temas_visuales: Mapped[list['TemasVisuales']] = relationship('TemasVisuales', back_populates='usuarios')
    aplicaciones_plantillas: Mapped[list['AplicacionesPlantillas']] = relationship('AplicacionesPlantillas', back_populates='usuarios')
    identidad_visuales: Mapped[list['IdentidadVisuales']] = relationship('IdentidadVisuales', back_populates='usuarios')
    sensores_areas_asociadas: Mapped[list['SensoresAreasAsociadas']] = relationship('SensoresAreasAsociadas', back_populates='usuarios')


class CiclosBiologicos(Base):
    __tablename__ = 'ciclos_biologicos'
    __table_args__ = (
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='ciclos_biologicos_id_especie_fkey'),
        PrimaryKeyConstraint('id_ciclo_biologico', name='ciclos_biologicos_pkey'),
        {'comment': 'Etapas del ciclo de vida de una especie (ej: larvario, juvenil, '
                'adulto). Cada ciclo pertenece a una especie específica.',
     'schema': 'modulo9'}
    )

    id_ciclo_biologico: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del ciclo biológico.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre descriptivo de la etapa biológica (ej: "Fase larval").')
    duracion_dias: Mapped[int] = mapped_column(Integer, nullable=False, comment='Duración estimada de la etapa biológica expresada en días.')
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False, comment='Especie a la que pertenece este ciclo biológico.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción detallada de las características de esta etapa del ciclo de vida.')

    especies: Mapped['Especies'] = relationship('Especies', back_populates='ciclos_biologicos')
    ciclos_productivos_biologicos: Mapped[list['CiclosProductivosBiologicos']] = relationship('CiclosProductivosBiologicos', back_populates='ciclos_biologicos')


class MetricasCicloProductivo(Base):
    __tablename__ = 'metricas_ciclo_productivo'
    __table_args__ = (
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='metricas_ciclo_productivo_id_ciclo_productivo_fkey'),
        ForeignKeyConstraint(['id_metrica_produccion'], ['modulo9.metricas_produccion.id_metrica_produccion'], name='metricas_ciclo_productivo_id_metrica_produccion_fkey'),
        PrimaryKeyConstraint('id_metricas_ciclo_productivo', name='metricas_ciclo_productivo_pkey'),
        {'comment': 'Asocia las métricas de producción que aplican a cada ciclo '
                'productivo específico.',
     'schema': 'modulo9'}
    )

    id_metricas_ciclo_productivo: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la asociación métrica-ciclo.')
    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, nullable=False, comment='Referencia al ciclo productivo al que se asigna la métrica.')
    id_metrica_produccion: Mapped[int] = mapped_column(Integer, nullable=False, comment='Referencia a la métrica de producción asignada al ciclo.')

    ciclos_productivos: Mapped['CiclosProductivos'] = relationship('CiclosProductivos', back_populates='metricas_ciclo_productivo')
    metricas_produccion: Mapped['MetricasProduccion'] = relationship('MetricasProduccion', back_populates='metricas_ciclo_productivo')


class Sensores(Base):
    __tablename__ = 'sensores'
    __table_args__ = (
        ForeignKeyConstraint(['id_dispositivo_iot'], ['modulo9.dispositivos_iot.id_dispositivo_iot'], name='sensores_id_dispositivo_iot_fkey'),
        PrimaryKeyConstraint('id_sensores', name='sensores_pkey'),
        {'comment': 'Sensor físico conectado a un dispositivo IoT, encargado de medir '
                'una variable ambiental específica (ej: sonda de temperatura, '
                'electrodo de pH).',
     'schema': 'modulo9'}
    )

    id_sensores: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del sensor.')
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False, comment='Dispositivo IoT al que está conectado este sensor.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si el sensor está operativo y enviando lecturas.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre descriptivo del sensor (ej: "Sensor pH estanque 1", "Termómetro zona norte").')
    categoria: Mapped[Optional[EnumReglasAlertasTipoSensor]] = mapped_column(Enum(EnumReglasAlertasTipoSensor, values_callable=lambda cls: [member.value for member in cls], name='enum_reglas_alertas_tipo_sensor', schema='modulo3'))

    dispositivos_iot: Mapped['DispositivosIot'] = relationship('DispositivosIot', back_populates='sensores')
    calibraciones: Mapped[list['Calibraciones']] = relationship('Calibraciones', back_populates='sensores')
    sensores_areas_asociadas: Mapped[list['SensoresAreasAsociadas']] = relationship('SensoresAreasAsociadas', back_populates='sensores')


class AuditoriasEspecies(Base):
    __tablename__ = 'auditorias_especies'
    __table_args__ = (
        CheckConstraint("tipo_operacion::text = ANY (ARRAY['CREATE'::character varying::text, 'UPDATE'::character varying::text, 'DEACTIVATE'::character varying::text])", name='chk_tipo_operacion_especie'),
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='auditorias_especies_id_especie_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='auditorias_especies_id_usuario_fkey'),
        PrimaryKeyConstraint('id_auditoria_especie', name='auditorias_especies_pkey'),
        Index('idx_audit_especie_fecha', 'fecha_gestion'),
        Index('idx_audit_especie_id', 'id_especie'),
        Index('idx_audit_especie_tipo', 'tipo_operacion'),
        Index('idx_audit_especie_usuario', 'id_usuario'),
        {'schema': 'modulo9'}
    )

    id_auditoria_especie: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(20), nullable=False)
    valores_nuevos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    valores_anteriores: Mapped[Optional[dict]] = mapped_column(JSONB)

    especies: Mapped['Especies'] = relationship('Especies', back_populates='auditorias_especies')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='auditorias_especies')


class AuditoriasVisuales(Base):
    __tablename__ = 'auditorias_visuales'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='auditorias_visuales_id_usuario_fkey'),
        PrimaryKeyConstraint('id_auditoria_visual', name='auditorias_visuales_pkey'),
        {'comment': 'Registro de auditoría de cambios en configuraciones visuales '
                '(temas, layouts, identidad). Permite trazabilidad y posibilidad '
                'de revertir cambios.',
     'schema': 'modulo9'}
    )

    id_auditoria_visual: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del registro de auditoría.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que realizó el cambio en la configuración visual.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se registró el cambio auditado.')
    valor_anterior: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Snapshot JSON del estado de la configuración visual antes del cambio.')
    valor_nuevo: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Snapshot JSON del estado de la configuración visual después del cambio.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='auditorias_visuales')


class Calibraciones(Base):
    __tablename__ = 'calibraciones'
    __table_args__ = (
        ForeignKeyConstraint(['id_dispositivo_iot'], ['modulo9.dispositivos_iot.id_dispositivo_iot'], name='calibraciones_id_dispositivo_iot_fkey'),
        ForeignKeyConstraint(['id_sensor'], ['modulo9.sensores.id_sensores'], name='calibraciones_id_sensor_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='calibraciones_id_usuario_fkey'),
        PrimaryKeyConstraint('id_calibracion', name='calibraciones_pkey'),
        {'comment': 'Historial de calibraciones realizadas a los sensores. Garantiza '
                'la trazabilidad y precisión de las mediciones en el tiempo.',
     'schema': 'modulo9'}
    )

    id_calibracion: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del evento de calibración.')
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False, comment='Dispositivo IoT al que pertenece el sensor calibrado.')
    fecha_calibracion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se realizó la calibración del sensor.')
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False, comment='Sensor que fue calibrado en este evento.')
    valor_referencia: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4), comment='Valor patrón o de referencia utilizado durante la calibración.')
    observaciones: Mapped[Optional[str]] = mapped_column(Text, comment='Notas o comentarios del técnico sobre el proceso de calibración o el estado del sensor.')
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, comment='Usuario o técnico que realizó la calibración (opcional).')

    dispositivos_iot: Mapped['DispositivosIot'] = relationship('DispositivosIot', back_populates='calibraciones')
    sensores: Mapped['Sensores'] = relationship('Sensores', back_populates='calibraciones')
    usuarios: Mapped[Optional['Usuarios']] = relationship('Usuarios', back_populates='calibraciones')


class CiclosProductivosBiologicos(Base):
    __tablename__ = 'ciclos_productivos_biologicos'
    __table_args__ = (
        ForeignKeyConstraint(['id_ciclo_biologico'], ['modulo9.ciclos_biologicos.id_ciclo_biologico'], name='ciclos_productivos_biologicos_id_ciclo_biologico_fkey'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='ciclos_productivos_biologicos_id_ciclo_productivo_fkey'),
        PrimaryKeyConstraint('id_ciclos_productivo_biologico', name='ciclos_productivos_biologicos_pkey'),
        {'comment': 'Relación N:M entre ciclos productivos y ciclos biológicos. '
                'Permite que un ciclo productivo cubra múltiples etapas '
                'biológicas.',
     'schema': 'modulo9'}
    )

    id_ciclos_productivo_biologico: Mapped[int] = mapped_column(Integer, Sequence('ciclos_productivos_biologicos_id_ciclos_productivo_biologic_seq', schema='modulo9'), primary_key=True, comment='Identificador único de la asociación.')
    id_ciclo_biologico: Mapped[int] = mapped_column(Integer, nullable=False, comment='Referencia al ciclo biológico asociado.')
    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, nullable=False, comment='Referencia al ciclo productivo asociado.')

    ciclos_biologicos: Mapped['CiclosBiologicos'] = relationship('CiclosBiologicos', back_populates='ciclos_productivos_biologicos')
    ciclos_productivos: Mapped['CiclosProductivos'] = relationship('CiclosProductivos', back_populates='ciclos_productivos_biologicos')


class ConfiguracionesGlobales(Base):
    __tablename__ = 'configuraciones_globales'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='configuraciones_globales_id_usuario_fkey'),
        PrimaryKeyConstraint('id_configuracion_global', name='configuraciones_globales_pkey'),
        {'comment': 'Configuración global del sistema IoT. Controla parámetros '
                'generales como la frecuencia de muestreo y el intervalo de '
                'heartbeat de los dispositivos.',
     'schema': 'modulo9'}
    )

    id_configuracion_global: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la configuración global.')
    frecuencia_muestreo: Mapped[int] = mapped_column(Integer, nullable=False, comment='Frecuencia de muestreo global de los sensores, expresada en segundos.')
    heartbeat: Mapped[int] = mapped_column(Integer, nullable=False, comment='Intervalo de señal de vida (heartbeat) de los dispositivos IoT, expresado en segundos.')
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se registró o modificó esta configuración.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario administrador que aplicó la configuración.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si esta es la configuración global vigente actualmente.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='configuraciones_globales')


class ConfiguracionesRemotas(Base):
    __tablename__ = 'configuraciones_remotas'
    __table_args__ = (
        CheckConstraint("estado::text = ANY (ARRAY['PENDIENTE'::character varying::text, 'APLICADA'::character varying::text, 'CANCELADA'::character varying::text])", name='configuraciones_remotas_estado_check'),
        ForeignKeyConstraint(['id_dispositivo_iot'], ['modulo9.dispositivos_iot.id_dispositivo_iot'], name='configuraciones_remotas_id_dispositivo_iot_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='configuraciones_remotas_id_usuario_fkey'),
        PrimaryKeyConstraint('id_configuracion_remota', name='configuraciones_remotas_pkey'),
        {'comment': 'Configuración enviada remotamente a cada dispositivo IoT para '
                'controlar la frecuencia de captura de datos y el intervalo de '
                'transmisión hacia la plataforma.',
     'schema': 'modulo9'}
    )

    id_configuracion_remota: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la configuración remota.')
    frecuencia_captura: Mapped[int] = mapped_column(Integer, nullable=False, comment='Frecuencia con la que el dispositivo captura lecturas de sus sensores, en segundos.')
    intervalo_transmision: Mapped[int] = mapped_column(Integer, nullable=False, comment='Intervalo de tiempo entre transmisiones de datos hacia la plataforma, en segundos.')
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False, comment='Dispositivo IoT al que aplica esta configuración remota.')
    estado: Mapped[str] = mapped_column(String(15), nullable=False, server_default=text("'PENDIENTE'::character varying"))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_creacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    fecha_aplicacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    dispositivos_iot: Mapped['DispositivosIot'] = relationship('DispositivosIot', back_populates='configuraciones_remotas')
    usuarios: Mapped[Optional['Usuarios']] = relationship('Usuarios', back_populates='configuraciones_remotas')


class DashboardLayouts(Base):
    __tablename__ = 'dashboard_layouts'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='dashboard_layouts_id_usuario_fkey'),
        PrimaryKeyConstraint('id_dashboard_layout', name='dashboard_layouts_pkey'),
        {'comment': 'Almacena la configuración personalizada del dashboard de cada '
                'usuario: disposición de paneles, widgets activos y parámetros de '
                'visualización.',
     'schema': 'modulo9'}
    )

    id_dashboard_layout: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la configuración de dashboard.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario al que pertenece esta configuración de dashboard.')
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Objeto JSON con la disposición y parámetros de los paneles del dashboard.')
    active_widget: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False, comment='Lista de identificadores de widgets activos y visibles en el dashboard del usuario.')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora de la última actualización de la configuración del dashboard.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='dashboard_layouts')


class Fincas(Base):
    __tablename__ = 'fincas'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='finca_id_usuario_fkey'),
        PrimaryKeyConstraint('id_finca', name='finca_pkey'),
        {'comment': 'Unidad productiva principal del sistema. Representa una finca, '
                'granja o instalación acuícola/agrícola con su información '
                'georreferenciada.',
     'schema': 'modulo9'}
    )

    id_finca: Mapped[int] = mapped_column(Integer, Sequence('finca_id_finca_seq', schema='modulo9'), primary_key=True, comment='Identificador único de la finca.')
    nombre: Mapped[str] = mapped_column(String(55), nullable=False, comment='Nombre comercial o identificador de la finca.')
    ubicacion: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Información geográfica de la finca en formato JSON (coordenadas, polígono, dirección, etc.).')
    tamano_h: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, comment='Tamaño total de la finca expresado en hectáreas.')
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora de la última modificación del registro de la finca.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(True, 0), nullable=False, comment='Fecha y hora en que se registró la finca en el sistema.')
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, comment='Usuario propietario o responsable de la finca (opcional).')
    es_activo: Mapped[Optional[bool]] = mapped_column(Boolean, comment='Indica si la finca está operativa en el sistema.')

    usuarios: Mapped[Optional['Usuarios']] = relationship('Usuarios', back_populates='fincas')
    identidad_visuales: Mapped[list['IdentidadVisuales']] = relationship('IdentidadVisuales', back_populates='fincas')
    infraestructuras: Mapped[list['Infraestructuras']] = relationship('Infraestructuras', back_populates='fincas')


class GestionEspecies(Base):
    __tablename__ = 'gestion_especies'
    __table_args__ = (
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='gestion_especies_id_especie_fkey1'),
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='gestion_especies_id_especie_fkey'),
        ForeignKeyConstraint(['id_umbral_ambiental'], ['modulo9.umbrales_ambientales.id_umbral_ambiental'], name='gestion_especies_id_umbral_ambiental_fkey1'),
        ForeignKeyConstraint(['id_umbral_ambiental'], ['modulo9.umbrales_ambientales.id_umbral_ambiental'], name='gestion_especies_id_umbral_ambiental_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='gestion_especies_id_usuario_fkey'),
        PrimaryKeyConstraint('id_ediciones_especies', name='gestion_especies_pkey'),
        {'comment': 'Registro de auditoría de las gestiones (creación, edición) '
                'realizadas sobre las especies, incluyendo el umbral ambiental '
                'asociado en cada momento.',
     'schema': 'modulo9'}
    )

    id_ediciones_especies: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la gestión registrada.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que realizó la gestión sobre la especie.')
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False, comment='Especie sobre la cual se realizó la gestión.')
    fecha_gestion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se realizó la gestión.')
    id_umbral_ambiental: Mapped[Optional[int]] = mapped_column(Integer, comment='Umbral ambiental que estaba vigente o fue asignado durante la gestión.')

    especies: Mapped['Especies'] = relationship('Especies', foreign_keys=[id_especie], back_populates='gestion_especies_id_especie')
    especies_: Mapped['Especies'] = relationship('Especies', foreign_keys=[id_especie], back_populates='gestion_especies_id_especie_')
    umbrales_ambientales: Mapped[Optional['UmbralesAmbientales']] = relationship('UmbralesAmbientales', foreign_keys=[id_umbral_ambiental], back_populates='gestion_especies_id_umbral_ambiental')
    umbrales_ambientales_: Mapped[Optional['UmbralesAmbientales']] = relationship('UmbralesAmbientales', foreign_keys=[id_umbral_ambiental], back_populates='gestion_especies_id_umbral_ambiental_')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='gestion_especies')


class Patologias(Base):
    __tablename__ = 'patologias'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario_creador'], ['modulo1.usuarios.id_usuario'], name='fk_patologias_usuario_creador'),
        PrimaryKeyConstraint('id_patologia', name='patologias_pkey'),
        UniqueConstraint('nombre', name='uq_enfermedad_nombre'),
        Index('idx_enfermedad_cat', 'categoria'),
        {'comment': 'Catálogo de patologías (enfermedades, parásitos, condiciones) que '
                'pueden afectar a las especies del sistema.',
     'schema': 'modulo9'}
    )

    id_patologia: Mapped[int] = mapped_column(Integer, Sequence('patologias_id_patologias_seq', schema='modulo9'), primary_key=True, comment='Identificador único de la patología.')
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre de la patología o enfermedad (ej: "Ich", "Vibriosis").')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    es_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='RF-64: true = patología base inmutable (catálogo CRISP-1). false = agregada por veterinario. Las base no pueden modificarse ni eliminarse.')
    version_catalogo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'), comment='RF-64: Versión incremental del catálogo. Se incrementa automáticamente con cada modificación de cualquier patología no-base.')
    especie_aplicable: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'TODAS'::character varying"), comment='RF-64: Especie a la que aplica la patología. Valor TODAS si es común a todas las especies del catálogo.')
    fecha_creacion_m04: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción de los síntomas, causas y características de la patología (opcional).')
    nombre_tecnico: Mapped[Optional[str]] = mapped_column(String(150))
    etiologia: Mapped[Optional[str]] = mapped_column(Text)
    categoria: Mapped[Optional[EnumPatologiaCategoria]] = mapped_column(Enum(EnumPatologiaCategoria, values_callable=lambda cls: [member.value for member in cls], name='enum_patologia_categoria', schema='modulo9'))
    codigo_cie: Mapped[Optional[str]] = mapped_column(String(150))
    descripcion_clinica: Mapped[Optional[str]] = mapped_column(Text, comment='RF-64: Justificación clínica obligatoria (mín. 50 caracteres). Describe por qué las variables sensoriales permiten inferir esta patología.')
    id_usuario_creador: Mapped[Optional[int]] = mapped_column(Integer)

    usuarios: Mapped[Optional['Usuarios']] = relationship('Usuarios', back_populates='patologias')
    especies_patologias: Mapped[list['EspeciesPatologias']] = relationship('EspeciesPatologias', back_populates='patologias')


class Plantillas(Base):
    __tablename__ = 'plantillas'
    __table_args__ = (
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='plantillas_id_especie_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='plantillas_id_usuario_fkey'),
        PrimaryKeyConstraint('id_plantilla', name='plantillas_pkey'),
        Index('uq_plantilla_nombre_version', 'version', unique=True),
        {'comment': 'Plantillas de configuración reutilizables por especie. Almacenan '
                'un snapshot de parámetros (umbrales, métricas, ciclos) para ser '
                'replicados en nuevas infraestructuras o ciclos productivos.',
     'schema': 'modulo9'}
    )

    id_plantilla: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la plantilla.')
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False, comment='Especie para la cual fue creada la plantilla de configuración.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que creó o es propietario de la plantilla.')
    template_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre descriptivo de la plantilla.')
    params_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Snapshot JSON de los parámetros de configuración capturados en el momento de creación de la plantilla.')
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment='Número de versión de la plantilla para control de cambios.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que se creó la plantilla.')

    especies: Mapped['Especies'] = relationship('Especies', back_populates='plantillas')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='plantillas')
    aplicaciones_plantillas: Mapped[list['AplicacionesPlantillas']] = relationship('AplicacionesPlantillas', back_populates='plantillas')


class PreferenciasIdiomas(Base):
    __tablename__ = 'preferencias_idiomas'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='preferencias_idiomas_id_usuario_fkey'),
        PrimaryKeyConstraint('id_preferencia_idioma', name='preferencias_idiomas_pkey'),
        {'comment': 'Preferencias de idioma e internacionalización (i18n) de cada '
                'usuario en la plataforma.',
     'schema': 'modulo9'}
    )

    id_preferencia_idioma: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la preferencia de idioma.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario al que pertenece esta preferencia de idioma.')
    locale_code: Mapped[str] = mapped_column(String(5), nullable=False, comment='Código de idioma y región según estándar IETF BCP 47 (ej: "es-CO", "en-US", "pt-BR").')
    es_por_defecto: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si este es el idioma predeterminado del usuario.')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora de la última actualización de la preferencia de idioma.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='preferencias_idiomas')


class TemasVisuales(Base):
    __tablename__ = 'temas_visuales'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='temas_visuales_id_usuario_fkey'),
        PrimaryKeyConstraint('id_tema_visual', name='temas_visuales_pkey'),
        Index('uq_tema_global', 'es_global', postgresql_where='(es_global = true)', unique=True),
        {'comment': 'Preferencia de tema visual de la interfaz por usuario (ej: claro, '
                'oscuro, según sistema operativo).',
     'schema': 'modulo9'}
    )

    id_tema_visual: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la preferencia de tema.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario al que pertenece esta preferencia de tema.')
    theme_mode: Mapped[int] = mapped_column(Integer, nullable=False, comment='Modo de tema: 1=Claro, 2=Oscuro, 3=Automático (sincronizado con el SO).')
    es_global: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la preferencia aplica globalmente para todos los módulos o solo para una sección específica.')
    fecha_actualizacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora de la última actualización de la preferencia.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='temas_visuales')


class AplicacionesPlantillas(Base):
    __tablename__ = 'aplicaciones_plantillas'
    __table_args__ = (
        ForeignKeyConstraint(['id_plantilla'], ['modulo9.plantillas.id_plantilla'], name='aplicaciones_plantillas_id_plantilla_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='aplicaciones_plantillas_id_usuario_fkey'),
        PrimaryKeyConstraint('id_aplicacion_plantilla', name='aplicaciones_plantillas_pkey'),
        {'comment': 'Historial de aplicaciones de plantillas de configuración sobre '
                'infraestructuras o ciclos productivos. Permite auditar qué '
                'configuración existía antes y después de aplicar cada plantilla.',
     'schema': 'modulo9'}
    )

    id_aplicacion_plantilla: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del evento de aplicación de plantilla.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que ejecutó la aplicación de la plantilla.')
    id_plantilla: Mapped[int] = mapped_column(Integer, nullable=False, comment='Plantilla que fue aplicada.')
    target_config: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='JSON con la identificación del objetivo sobre el que se aplicó la plantilla (finca, infraestructura, ciclo, etc.).')
    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Snapshot JSON de la configuración del objetivo antes de aplicar la plantilla.')
    after_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Snapshot JSON de la configuración del objetivo después de aplicar la plantilla.')
    fecha_aplicacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora en que se aplicó la plantilla.')

    plantillas: Mapped['Plantillas'] = relationship('Plantillas', back_populates='aplicaciones_plantillas')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='aplicaciones_plantillas')


class EspeciesPatologias(Base):
    __tablename__ = 'especies_patologias'
    __table_args__ = (
        ForeignKeyConstraint(['id_especie'], ['modulo9.especies.id_especie'], name='especies_patologias_id_especie_fkey'),
        ForeignKeyConstraint(['id_patologia'], ['modulo9.patologias.id_patologia'], name='especies_patologias_id_patologia_fkey'),
        PrimaryKeyConstraint('id_especies_patologias', name='especies_patologias_pkey'),
        {'comment': 'Relación N:M entre especies y las patologías conocidas que las '
                'pueden afectar.',
     'schema': 'modulo9'}
    )

    id_especies_patologias: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la asociación especie-patología.')
    id_especie: Mapped[int] = mapped_column(Integer, nullable=False, comment='Referencia a la especie afectada por la patología.')
    id_patologia: Mapped[Optional[int]] = mapped_column(Integer, comment='Referencia a la patología que puede afectar a la especie (opcional si está en proceso de clasificación).')

    especies: Mapped['Especies'] = relationship('Especies', back_populates='especies_patologias')
    patologias: Mapped[Optional['Patologias']] = relationship('Patologias', back_populates='especies_patologias')


class IdentidadVisuales(Base):
    __tablename__ = 'identidad_visuales'
    __table_args__ = (
        ForeignKeyConstraint(['id_finca'], ['modulo9.fincas.id_finca'], name='identidad_visuales_id_finca_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='identidad_visuales_id_usuario_fkey'),
        PrimaryKeyConstraint('id_identidad_visual', name='identidad_visuales_pkey'),
        {'comment': 'Configuración de identidad visual de la organización asociada a '
                'una finca (logotipo, color corporativo, nombre visible). Permite '
                'personalizar la interfaz por cliente.',
     'schema': 'modulo9'}
    )

    id_identidad_visual: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del registro de identidad visual.')
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False, comment='Finca u organización a la que pertenece esta identidad visual.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que configuró o actualizó la identidad visual.')
    logo_path: Mapped[Optional[str]] = mapped_column(String(255), comment='Ruta o URL del archivo de logotipo de la organización.')
    primary_color: Mapped[Optional[str]] = mapped_column(String(7), comment='Color primario corporativo en formato hexadecimal (ej: "#2A7AE4").')
    org_display_name: Mapped[Optional[str]] = mapped_column(String(50), comment='Nombre visible de la organización en la interfaz de usuario.')
    version: Mapped[Optional[int]] = mapped_column(Integer, comment='Versión del registro de identidad visual (para control de cambios).')
    fecha_creacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora en que se creó o actualizó la configuración visual.')
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7))

    fincas: Mapped['Fincas'] = relationship('Fincas', back_populates='identidad_visuales')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='identidad_visuales')


class Infraestructuras(Base):
    __tablename__ = 'infraestructuras'
    __table_args__ = (
        ForeignKeyConstraint(['id_finca'], ['modulo9.fincas.id_finca'], name='infraestructuras_id_finca_fkey'),
        PrimaryKeyConstraint('id_infraestructura', name='infraestructuras_pkey'),
        UniqueConstraint('nombre', 'id_finca', name='uq_infraestructura_nombre'),
        {'comment': 'Estructura física de producción dentro de una finca (ej: '
                'estanque, jaula flotante, invernadero, galpón). Es la unidad de '
                'monitoreo principal.',
     'schema': 'modulo9'}
    )

    id_infraestructura: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la infraestructura.')
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre o código identificador de la infraestructura dentro de la finca. Debe ser único.')
    id_finca: Mapped[int] = mapped_column(Integer, nullable=False, comment='Finca a la que pertenece esta infraestructura.')
    superficie: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment='Área o superficie de la infraestructura expresada en metros cuadrados.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la infraestructura está activa y en operación.')
    tipo: Mapped[EnumTipoInfraestructura] = mapped_column(Enum(EnumTipoInfraestructura, values_callable=lambda cls: [member.value for member in cls], name='enum_tipo_infraestructura', schema='modulo9'), nullable=False, comment='Tipo de infraestructura según el catálogo del enum (ej: ESTANQUE, JAULA, INVERNADERO).')
    descripcion: Mapped[Optional[str]] = mapped_column(String(100), comment='Descripción adicional de la infraestructura y su uso.')

    fincas: Mapped['Fincas'] = relationship('Fincas', back_populates='infraestructuras')
    sensores_areas_asociadas: Mapped[list['SensoresAreasAsociadas']] = relationship('SensoresAreasAsociadas', back_populates='infraestructuras')


class SensoresAreasAsociadas(Base):
    __tablename__ = 'sensores_areas_asociadas'
    __table_args__ = (
        ForeignKeyConstraint(['id_dispositivo_iot'], ['modulo9.dispositivos_iot.id_dispositivo_iot'], name='sensores_areas_asociadas_id_dispositivo_iot_fkey'),
        ForeignKeyConstraint(['id_infraestructura'], ['modulo9.infraestructuras.id_infraestructura'], name='sensores_areas_asociadas_id_infraestructura_fkey'),
        ForeignKeyConstraint(['id_sensor'], ['modulo9.sensores.id_sensores'], name='sensores_areas_asociadas_id_sensor_fkey'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='sensores_areas_asociadas_id_usuario_fkey'),
        PrimaryKeyConstraint('id_sensores_area_asociada', name='sensores_areas_asociadas_pkey'),
        {'comment': 'Historial de asociaciones de sensores a infraestructuras (áreas '
                'de monitoreo). Permite conocer dónde estuvo o está instalado cada '
                'sensor a lo largo del tiempo.',
     'schema': 'modulo9'}
    )

    id_sensores_area_asociada: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la asociación sensor-área.')
    id_sensor: Mapped[int] = mapped_column(Integer, nullable=False, comment='Sensor asociado al área de monitoreo.')
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False, comment='Dispositivo IoT al que pertenece el sensor en esta asociación.')
    id_infraestructura: Mapped[int] = mapped_column(Integer, nullable=False, comment='Infraestructura (área) donde está o estuvo instalado el sensor.')
    punto_instalacion: Mapped[str] = mapped_column(String(100), nullable=False, comment='Descripción del punto exacto de instalación dentro de la infraestructura (ej: "Entrada de agua", "Centro estanque").')
    tiene_estado: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la asociación está actualmente vigente (TRUE) o fue finalizada (FALSE).')
    fecha_asociacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Fecha y hora en que el sensor fue instalado en esta área.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='Usuario que registró o gestionó la asociación del sensor.')
    fecha_finalizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Fecha y hora en que el sensor fue retirado o desasociado del área (NULL si sigue activo).')

    dispositivos_iot: Mapped['DispositivosIot'] = relationship('DispositivosIot', back_populates='sensores_areas_asociadas')
    infraestructuras: Mapped['Infraestructuras'] = relationship('Infraestructuras', back_populates='sensores_areas_asociadas')
    sensores: Mapped['Sensores'] = relationship('Sensores', back_populates='sensores_areas_asociadas')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='sensores_areas_asociadas')
