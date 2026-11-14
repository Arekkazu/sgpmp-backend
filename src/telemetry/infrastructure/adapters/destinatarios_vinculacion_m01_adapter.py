# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: destinatarios por permisos y finca sin roles quemados |
from sqlalchemy import text


class DestinatariosVinculacionM01Adapter:
    def __init__(self,db):self.db=db

    def obtener(self,area,*,administradores=False):
        return list(self.db.execute(text('''SELECT DISTINCT u.id_usuario FROM modulo1.usuarios u
            JOIN modulo1.roles r ON r.id_rol=u.id_rol
            JOIN modulo1.cuentas_usuarios c ON c.id_usuario=u.id_usuario
            JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta=c.id_estado_cuenta
            WHERE lower(e.nombre)='activo'
              AND (:administradores=false OR r.es_protegido)
              AND EXISTS(SELECT 1 FROM modulo1.permisos p JOIN modulo1.recursos recurso USING(id_recurso)
                WHERE p.id_rol=u.id_rol AND p.es_activo AND recurso.nombre_recurso=:recurso
                  AND p.id_accion=:accion)
              AND (:administradores OR EXISTS(SELECT 1 FROM modulo1.permisos p JOIN modulo1.recursos recurso USING(id_recurso)
                WHERE p.id_rol=u.id_rol AND p.es_activo AND recurso.nombre_recurso='activos_biologicos'
                  AND p.id_accion=2))
              AND (modulo1.fn_rol_protegido(u.id_rol) OR EXISTS(
                SELECT 1 FROM modulo9.usuarios_fincas uf JOIN modulo9.infraestructuras i ON i.id_finca=uf.id_finca
                WHERE uf.id_usuario=u.id_usuario AND uf.es_activo AND i.id_infraestructura=:area))
            ORDER BY u.id_usuario'''),{'area':area,'administradores':administradores,
            'recurso':'alertas_tecnicas_iot' if administradores else 'vinculaciones_lecturas',
            'accion':2 if administradores else 3}).scalars())
