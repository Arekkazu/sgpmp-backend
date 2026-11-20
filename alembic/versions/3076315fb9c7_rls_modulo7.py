# | Fecha      | Nombre       | Qué se hizo                                              |
# |------------|--------------|----------------------------------------------------------|
# | 2026-11-19 | SamuelPR21   | Creación inicial políticas RLS modulo7                   |
# | 2026-11-20 | SamuelPR21   | Fix: recursos reales M07, INSERT logs con usuario,       |
# |            |              | SELECT/UPDATE contratos con exportacion_contable y E     |
# | 2026-11-20 | Arekkazu     | Sobre ad58476e2239 (lote M07/M08); downgrade solo de sus tablas |

"""F5 para el modulo7: RLS para el Gateway de Integracion AAEF (RF-95 a RF-102)


Revision ID: 3076315fb9c7
Revises: ad58476e2239
Create Date: 2026-11-18 18:54:06.920190
Clasifica 17 tablas de modulo7 en patrones de acceso (las del archivo de RF-102,
eventos_integracion_archivados e identidades_eventos_integracion, se protegen por GRANT en f11651020001):

  1. CATALOGO (sin RLS):          catalogo_errores_de_integracion,
                                  tipos_documentos_aaef, permisos_api
  2. CONFIG GLOBAL (RBAC puro):   clientes_externos, canales_clientes_externos,
                                  identificadores_apis, permisos_clientes,
                                  versiones_contrato_aaef, mapeos_anexos_aaef,
                                  reglas_mapeo_aaef
  3. OPERACION / LOGS:            integraciones_solicitudes, eventos_integracion,
                                  auditoria_peticiones, registros_ejecucion_mapeador,
                                  notificaciones_weebhook, documentos_generados_aaef,
                                  metadatos_respuesta_aaef

Recursos RBAC propios de M07 (los mismos que exige m07_router.py):
  - clientes_externos:           Admin (C/R/U/D)
  - contratos_aaef:              Admin (C/R/U), Contador (R/E)
  - exportacion_contable:        Admin, Contador (R)
  - auditoria_integracion:       Admin (R)
  - auditoria_integracion_cierres: Auditor externo (R)

Reutiliza funciones de modulo1 (F5):
  - fn_id_usuario_actual()
  - fn_es_usuario_servicio()
  - fn_tiene_permiso()
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3076315fb9c7'
down_revision: Union[str, Sequence[str], None] = 'ad58476e2239'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


def _o(*condiciones: str) -> str:
    return "(" + " OR ".join(condiciones) + ")"


# Recursos propios de M07 (los mismos que exige m07_router.py)
CLI_R = permiso('clientes_externos', 'R')
CLI_W = _o(
    permiso('clientes_externos', 'C'),
    permiso('clientes_externos', 'U'),
    permiso('clientes_externos', 'D'),
)
# La consulta AAEF lee el contrato vigente con la identidad del usuario del token
CON_R = _o(permiso('contratos_aaef', 'R'), permiso('exportacion_contable', 'R'))
# E: el Contador envia el anexo a revision
CON_W = _o(
    permiso('contratos_aaef', 'C'),
    permiso('contratos_aaef', 'U'),
    permiso('contratos_aaef', 'E'),
)
AUD_R = _o(
    permiso('auditoria_integracion', 'R'),
    permiso('auditoria_integracion_cierres', 'R'),
)
# Widget "Consultas contables con error" (M08)
CONTADOR_R = permiso('exportacion_contable', 'R')


def _enable_force(tabla: str) -> None:
    op.execute(f"ALTER TABLE modulo7.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo7.{tabla} FORCE ROW LEVEL SECURITY;")


def _config(tabla: str, leer: str, escribir: str) -> None:
    op.execute(f"CREATE POLICY pol_{tabla}_select ON modulo7.{tabla} FOR SELECT USING ({leer});")
    op.execute(f"CREATE POLICY pol_{tabla}_insert ON modulo7.{tabla} FOR INSERT WITH CHECK ({escribir});")
    op.execute(f"CREATE POLICY pol_{tabla}_update ON modulo7.{tabla} FOR UPDATE USING ({escribir}) WITH CHECK ({escribir});")
    op.execute(f"CREATE POLICY pol_{tabla}_delete ON modulo7.{tabla} FOR DELETE USING ({escribir});")
    op.execute(f"CREATE POLICY pol_{tabla}_servicio ON modulo7.{tabla} FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});")
    _enable_force(tabla)


_CATALOGOS = ('catalogo_errores_de_integracion', 'tipos_documentos_aaef', 'permisos_api')
_CONFIG = ('clientes_externos', 'canales_clientes_externos', 'identificadores_apis', 'permisos_clientes',
           'versiones_contrato_aaef', 'mapeos_anexos_aaef', 'reglas_mapeo_aaef')
_TABLAS_LOG = ('integraciones_solicitudes', 'eventos_integracion', 'auditoria_peticiones',
               'registros_ejecucion_mapeador', 'notificaciones_weebhook', 'documentos_generados_aaef',
               'metadatos_respuesta_aaef')


def upgrade() -> None:

    # ================================================================
    # 1. CATALOGOS (sin RLS): lectura interna amplia
    # ================================================================
    for t in _CATALOGOS:
        op.execute(f"ALTER TABLE modulo7.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo7.{t} NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. CLIENTES Y CREDENCIALES
    #    El nombre del cliente lo ven tambien la auditoria y el widget
    #    del Contador; la credencial solo quien gestiona clientes.
    # ================================================================
    _config('clientes_externos', _o(CLI_R, AUD_R, CONTADOR_R), CLI_W)
    for t in ('canales_clientes_externos', 'identificadores_apis', 'permisos_clientes'):
        _config(t, CLI_R, CLI_W)

    # ================================================================
    # 3. CONTRATOS Y ANEXOS
    #    SELECT: contratos_aaef R + exportacion_contable R
    #    UPDATE: incluye contratos_aaef E (envio a revision)
    # ================================================================
    for t in ('versiones_contrato_aaef', 'mapeos_anexos_aaef', 'reglas_mapeo_aaef'):
        _config(t, CON_R, CON_W)

    # ================================================================
    # 4. LOGS / OPERACION (append-only)
    #    RF-102: la auditoria se inserta en la misma transaccion del
    #    usuario que hace la operacion. Si algo falla, se revierte todo.
    #    INSERT: servicio OR cualquier usuario identificado.
    #    UPDATE: solo el servicio (marca estados de procesamiento).
    # ================================================================

    for t in _TABLAS_LOG:
        # integraciones_solicitudes tambien la lee el Contador (widget M08)
        leer = _o(AUD_R, CONTADOR_R) if t == 'integraciones_solicitudes' else AUD_R
        op.execute(f"CREATE POLICY pol_{t}_select ON modulo7.{t} FOR SELECT USING ({leer} OR {SERVICIO});")
        op.execute(f"CREATE POLICY pol_{t}_insert ON modulo7.{t} FOR INSERT WITH CHECK ({SERVICIO} OR {UID} IS NOT NULL);")
        op.execute(f"CREATE POLICY pol_{t}_update ON modulo7.{t} FOR UPDATE USING ({SERVICIO}) WITH CHECK ({SERVICIO});")
        _enable_force(t)


def downgrade() -> None:
    # Solo las tablas de esta migración: el resto de modulo7 conserva lo que tenga.
    for t in _CONFIG + _TABLAS_LOG:
        op.execute(f"""
            DO $$ DECLARE r record; BEGIN
              FOR r IN SELECT policyname FROM pg_policies WHERE schemaname = 'modulo7' AND tablename = '{t}'
              LOOP EXECUTE format('DROP POLICY %I ON modulo7.{t}', r.policyname); END LOOP; END $$;
        """)
        op.execute(f"ALTER TABLE modulo7.{t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo7.{t} DISABLE ROW LEVEL SECURITY;")
