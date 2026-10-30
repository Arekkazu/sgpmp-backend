# | Fecha      | Nombre     | Que se hizo                                                        |
# |------------|------------|--------------------------------------------------------------------|
# | 2026-10-30 | SamuelPR21 | CARGA-FREC RF-23/53/60: piso de 5 minutos y unidades en minutos     |
"""rf23/rf60: ningún sensor se configura por debajo de 5 minutos

Revision ID: b7c2e4f19a30
Revises: 6bd01d026ac4
Create Date: 2026-10-30

Sustento: estudio de carga en `scripts/carga_frecuencia/` (piso de 5 min, 10 min por defecto).

- Sube a 5 el mínimo de los tipos de categoría SENSOR. Con eso la validación que
  ya existe en RF-23 (`verificar_rango`) rechaza con su 400 PARAMETRO_FUERA_DE_RANGO.
- Agrega CHECK como última línea de defensa para escrituras que no pasan por la API.
- Cancela las configuraciones PENDIENTE por debajo del piso: de otro modo se
  aplicarían y dejarían un dispositivo fuera de la regla.
- Corrige los comentarios: RF-22/RF-23, el código y `fn_ingesta_telemetria` usan
  minutos, pero el DDL decía segundos. Por eso el piso es 5 y no 300.

Los CHECK de configuraciones quedan NOT VALID a propósito y no se validan: aplican
a toda fila nueva o actualizada, pero conservan las filas históricas por debajo del
piso, que son registro de lo que se configuró. Un NO_CONF viejo por debajo del piso
no se puede reintentar, que es lo deseado.

El downgrade no revive las PENDIENTE canceladas: reactivar un comando viejo hacia un
dispositivo sería peor que perderlo.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b7c2e4f19a30'
down_revision: Union[str, Sequence[str], None] = '6bd01d026ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS_EN_MINUTOS = (
    ('configuraciones_remotas', 'frecuencia_captura',
     'Frecuencia con la que el dispositivo captura lecturas de sus sensores, en minutos. Mínimo 5.'),
    ('configuraciones_remotas', 'intervalo_transmision',
     'Intervalo de tiempo entre transmisiones de datos hacia la plataforma, en minutos. Mínimo 5.'),
    ('configuraciones_globales', 'frecuencia_muestreo',
     'Frecuencia de muestreo global de los sensores, expresada en minutos. Mínimo 5.'),
    ('configuraciones_globales', 'heartbeat',
     'Tiempo máximo sin recepción de datos antes de marcar sin señal, expresado en minutos.'),
)

COMENTARIOS_ANTERIORES = (
    ('configuraciones_remotas', 'frecuencia_captura',
     'Frecuencia con la que el dispositivo captura lecturas de sus sensores, en segundos.'),
    ('configuraciones_remotas', 'intervalo_transmision',
     'Intervalo de tiempo entre transmisiones de datos hacia la plataforma, en segundos.'),
    ('configuraciones_globales', 'frecuencia_muestreo',
     'Frecuencia de muestreo global de los sensores, expresada en segundos.'),
    ('configuraciones_globales', 'heartbeat',
     'Intervalo de señal de vida (heartbeat) de los dispositivos IoT, expresado en segundos.'),
)


def _comentar(columnas) -> None:
    for tabla, columna, texto in columnas:
        op.execute(f"COMMENT ON COLUMN modulo9.{tabla}.{columna} IS '{texto}'")


def upgrade() -> None:
    op.execute(
        """
        UPDATE modulo9.tipos_dispositivo_iot
        SET frecuencia_captura_min = GREATEST(frecuencia_captura_min, 5),
            frecuencia_captura_max = GREATEST(frecuencia_captura_max, 5),
            intervalo_transmision_min = GREATEST(intervalo_transmision_min, 5),
            intervalo_transmision_max = GREATEST(intervalo_transmision_max, 5)
        WHERE categoria = 'SENSOR'
        """
    )
    op.execute(
        """
        ALTER TABLE modulo9.tipos_dispositivo_iot
            ADD CONSTRAINT ck_tipo_dispositivo_iot_piso_frecuencia
            CHECK (categoria <> 'SENSOR'
                   OR (frecuencia_captura_min >= 5 AND intervalo_transmision_min >= 5))
        """
    )
    op.execute(
        """
        UPDATE modulo9.configuraciones_remotas
        SET estado = 'CANCELADA'
        WHERE estado = 'PENDIENTE'
          AND fps IS NULL
          AND (frecuencia_captura < 5 OR intervalo_transmision < 5)
        """
    )
    op.execute(
        """
        ALTER TABLE modulo9.configuraciones_remotas
            ADD CONSTRAINT ck_configuracion_remota_piso_frecuencia
            CHECK (fps IS NOT NULL
                   OR (frecuencia_captura >= 5 AND intervalo_transmision >= 5)) NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE modulo9.configuraciones_globales
            ADD CONSTRAINT ck_configuracion_global_piso_frecuencia
            CHECK (frecuencia_muestreo >= 5) NOT VALID
        """
    )
    _comentar(COLUMNAS_EN_MINUTOS)


def downgrade() -> None:
    _comentar(COMENTARIOS_ANTERIORES)
    op.execute(
        'ALTER TABLE modulo9.configuraciones_globales '
        'DROP CONSTRAINT ck_configuracion_global_piso_frecuencia'
    )
    op.execute(
        'ALTER TABLE modulo9.configuraciones_remotas '
        'DROP CONSTRAINT ck_configuracion_remota_piso_frecuencia'
    )
    op.execute(
        'ALTER TABLE modulo9.tipos_dispositivo_iot '
        'DROP CONSTRAINT ck_tipo_dispositivo_iot_piso_frecuencia'
    )
    op.execute(
        """
        UPDATE modulo9.tipos_dispositivo_iot
        SET frecuencia_captura_min = 1, intervalo_transmision_min = 1
        WHERE nombre IN ('GENERICO', 'GATEWAY_EDGE')
        """
    )
