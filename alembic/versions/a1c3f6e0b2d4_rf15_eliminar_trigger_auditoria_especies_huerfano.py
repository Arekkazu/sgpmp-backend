"""rf15 eliminar trigger de auditoria de especies huerfano

Revision ID: a1c3f6e0b2d4
Revises: f19e0ca62445
Create Date: 2026-09-05 00:00:00.000000

INC-M09-02-G02 (#111) — POST /configuracion/especies respondia 500 en toda
creacion con datos validos.

Causa raiz: ``modulo9.especies`` tenia un trigger ``trg_especies_audit``
(funcion ``trg_fn_especies_audit``) que exige una variable de sesion
``app.usuario_id`` (``SET LOCAL ...``) para poder insertar en
``modulo9.auditorias_especies`` — patron usado en ``biological_assets``, pero
que ningun caso de uso de ``especies`` establece nunca. El resultado es que
CUALQUIER INSERT o UPDATE sobre ``especies`` fallaba con la excepcion propia
del trigger, traducida a 500 generico.

Este trigger es ademas redundante y no es el patron del resto del modulo 9:
todas las demas entidades (fincas, patologias, ciclos_biologicos,
infraestructuras, dispositivos_iot, calibraciones, ...) auditan exclusivamente
desde la capa de aplicacion (``AuditoriaXRepository.registrar()``), y sus
triggers de auditoria SOLO bloquean UPDATE/DELETE para forzar inmutabilidad
(ver ``trg_fn_auditorias_calibraciones_inmutable`` en la migracion
d4e2f8a15c9b) — nunca escriben el registro de auditoria ellos mismos.
``RegistrarEspecieUseCase``/``EditarEspecieUseCase``/``DesactivarEspecieUseCase``
ya insertan en ``auditorias_especies`` vía ``AuditoriaEspecieRepository``, así
que este trigger nunca fue necesario: no aparece en ningun archivo de
``alembic/versions/`` anterior (solo en el volcado inicial de
``alembic/baseline/esquema_baseline.sql``), es decir, nunca fue una decision
de diseño registrada — es un remanente del esquema original.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c3f6e0b2d4'
down_revision: Union[str, Sequence[str], None] = 'f19e0ca62445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_especies_audit ON modulo9.especies")
    op.execute("DROP FUNCTION IF EXISTS modulo9.trg_fn_especies_audit()")


def downgrade() -> None:
    # No se recrea intencionalmente: revivirla dejaria de nuevo POST/PUT sobre
    # especies rotos con 500, que es exactamente el incidente que esta
    # migracion cierra. Si en el futuro se necesita auditoria por trigger real
    # para especies, debe diseñarse alineada con el patron de app-level audit
    # que ya usa el resto de modulo 9, no restaurando este trigger huerfano.
    pass
