"""fix RLS: app_ctx sin USAGE, Veterinario en especies, cola de auditoria (F2)

Revision ID: b53fe19f276e
Revises: d7c4e9a1b2f6
Create Date: 2026-09-28 00:00:00.000000

Corrige cinco huecos de las migraciones de F1 (`8d80fb56a30b` RLS modulo1 y
`5243bbbb28de` RLS modulo9, autoria SamuelPR21) descubiertos al verificar F2
(contexto de sesion) contra datos reales de `sgpmp_dev`. Ninguno era visible
hasta ahora porque nada llamaba `set_config('app.current_role', ...)` todavia
-- en cuanto F2 empiece a declarar la identidad real en cada request, estas
cinco cosas dejan de funcionar en silencio:

0. El mas severo, verificado con un UPDATE real contra sgpmp_dev (dentro de
   una transaccion, con ROLLBACK): sgpmp_app no tiene USAGE sobre el schema
   app_ctx. Los triggers modulo1.fn_prevenir_autocambio_rol() y
   modulo9.fn_proteger_activo_especie() llaman app_ctx.current_user_id() /
   app_ctx.current_role() y estan declarados sin SECURITY DEFINER, asi que
   PL/pgSQL resuelve ese nombre calificado con los privilegios del rol que
   ejecuta el UPDATE (sgpmp_app), no del dueno de la funcion. Sin el GRANT,
   cualquier UPDATE sobre modulo1.usuarios (auto-edicion de perfil,
   RF-05/RF-13) o modulo9.especies falla con
   "permission denied for schema app_ctx", para cualquier rol, incluido
   Administrador -- no es un problema de que rol puede hacer que, es que la
   operacion entera esta rota. Las politicas RLS (pol_*) no lo sufren porque
   ya vienen con el OID de la funcion resuelto desde que se creo la politica
   (como superusuario); un trigger en PL/pgSQL lo resuelve de nuevo en cada
   sesion.
1. pol_especies_update (modulo9) no incluye 'Veterinario', pero
   modulo1.permisos si le da a ese rol el permiso U sobre el recurso
   especies (verificado por consulta). Un Veterinario que hoy edita una
   especie dejaria de poder hacerlo -- el UPDATE afectaria 0 filas.
2. modulo1.eventos_archivados tiene RLS activo con solo SELECT (admin). El
   job diario de archivado (RF-10, evento_repository.py:archivar_eventos_anteriores)
   solo hace INSERT (nunca DELETE/UPDATE sobre eventos, coherente con su
   inmutabilidad) y quedaria bloqueado por defecto.
3. modulo1.cola_exportaciones_auditoria no tiene politica de UPDATE. El
   poller de RF-10 (exportacion_auditoria_repository.py:tomar_pendiente)
   marca la fila EN_PROCESO con un UPDATE que quedaria bloqueado.
4. modulo1.ejecuciones_exportaciones_auditoria no tiene politica de INSERT.
   El mismo poller, al terminar (completar), inserta el resultado de la
   ejecucion -- tambien bloqueado.

Los pollers de (3) y (4) corren en main.py sin usuario autenticado y se
declaran 'Administrador' via _declarar_identidad_sistema (interino, ver
Decision D1 del plan de control de acceso, sin resolver por equipo + DBA
todavia) -- de ahi que las politicas de (2), (3) y (4) queden gateadas por
rol Administrador, igual que ya hace pol_eventos_select/pol_cola_export_select
sobre las mismas tablas.

Requiere autorizacion de SamuelPR21 en el PR antes de mergear a dev, igual
que cualquier otro DDL de este repo -- corrige migraciones de su autoria.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b53fe19f276e"
down_revision: Union[str, Sequence[str], None] = "d7c4e9a1b2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Sin esto, cualquier UPDATE en modulo1.usuarios o modulo9.especies
    # falla al resolver app_ctx.* desde dentro de un trigger PL/pgSQL sin
    # SECURITY DEFINER (ver docstring). Solo USAGE, no acceso a tablas.
    op.execute("GRANT USAGE ON SCHEMA app_ctx TO sgpmp_app;")

    # 1. Veterinario tambien puede actualizar especies (modulo1.permisos ya lo autoriza).
    op.execute("DROP POLICY pol_especies_update ON modulo9.especies;")
    op.execute("""
        CREATE POLICY pol_especies_update ON modulo9.especies
          FOR UPDATE
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo', 'Veterinario'))
          WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo', 'Veterinario'));
    """)

    # 2. El archivado RF-10 solo copia (INSERT), nunca borra ni actualiza.
    op.execute("""
        CREATE POLICY pol_eventos_archivados_insert ON modulo1.eventos_archivados
          FOR INSERT
          WITH CHECK (true);
    """)

    # 3. El poller de exportaciones marca la fila EN_PROCESO/COMPLETADO/error.
    op.execute("""
        CREATE POLICY pol_cola_export_update ON modulo1.cola_exportaciones_auditoria
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # 4. El mismo poller inserta el resultado de cada ejecucion.
    op.execute("""
        CREATE POLICY pol_ejecuciones_export_insert ON modulo1.ejecuciones_exportaciones_auditoria
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_ejecuciones_export_insert ON modulo1.ejecuciones_exportaciones_auditoria;")
    op.execute("DROP POLICY IF EXISTS pol_cola_export_update ON modulo1.cola_exportaciones_auditoria;")
    op.execute("DROP POLICY IF EXISTS pol_eventos_archivados_insert ON modulo1.eventos_archivados;")

    op.execute("DROP POLICY IF EXISTS pol_especies_update ON modulo9.especies;")
    op.execute("""
        CREATE POLICY pol_especies_update ON modulo9.especies
          FOR UPDATE
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'))
          WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
    """)

    op.execute("REVOKE USAGE ON SCHEMA app_ctx FROM sgpmp_app;")
