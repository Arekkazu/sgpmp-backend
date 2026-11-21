# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: siembra idempotente de parametros   |
# | 2026-10-22 | Leandro | DEV-28 RF-62: siembra explicita de pesos y tramos de vision |
"""Administración offline con una conexión de BD autorizada, sin nuevos endpoints.

Por defecto solo valida. Para escribir requiere --aplicar y DEV14_DATABASE_URL
explícita; no utiliza la conexión del .env de la aplicación como destino implícito.
Los datos vienen de un archivo revisado por el administrador, sin semillas
automáticas ni valores predeterminados de código para los consumidores.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.errors import AppError, AuthorizationError
from src.configuration.domain.entities.parametros_heartbeat import PREDETERMINADOS_HEARTBEAT
from src.configuration.domain.entities.parametros_vision import PREDETERMINADOS_VISION
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository


def _objeto_sin_duplicados(pares):
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ValueError('Hay parámetros repetidos en el archivo.')
        resultado[clave] = valor
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archivo', type=Path)
    parser.add_argument('--sembrar-heartbeat', action='store_true', help='Carga defaults D documentados y conserva claves existentes.')
    parser.add_argument('--sembrar-vision', action='store_true', help='Carga defaults D de RF-62 y conserva valores existentes.')
    parser.add_argument('--actualizar-existentes', action='store_true', help='Con siembra, permite actualizar las claves indicadas explícitamente en el archivo.')
    parser.add_argument('--id-usuario', type=int, required=True)
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    siembra = args.sembrar_heartbeat or args.sembrar_vision
    if args.archivo is None and not siembra:
        parser.error('Indique --archivo, --sembrar-heartbeat o --sembrar-vision.')
    if args.actualizar_existentes and (not siembra or args.archivo is None):
        parser.error('--actualizar-existentes requiere una siembra y un archivo explícito.')
    url = os.getenv('DEV14_DATABASE_URL')
    if not url:
        parser.error('Defina DEV14_DATABASE_URL explícitamente para la base autorizada.')
    engine = None
    try:
        archivo = json.loads(args.archivo.read_text(encoding='utf-8-sig'), object_pairs_hook=_objeto_sin_duplicados) if args.archivo else {}
        if not isinstance(archivo, dict):
            raise ValueError('El archivo debe ser un objeto JSON.')
        cambios = dict(PREDETERMINADOS_HEARTBEAT) if args.sembrar_heartbeat else {}
        if args.sembrar_vision:
            cambios.update(PREDETERMINADOS_VISION)
        cambios.update(archivo)
        engine = create_engine(url, pool_pre_ping=True, use_insertmanyvalues=False)
        with Session(engine) as db:
            if not args.aplicar:
                db.execute(text('SET TRANSACTION READ ONLY'))
            administrador = db.execute(text('''SELECT u.id_usuario FROM modulo1.usuarios u
                JOIN modulo1.roles r ON r.id_rol=u.id_rol
                WHERE u.id_usuario=:id AND lower(r.nombre_rol)='administrador'
            '''), {'id': args.id_usuario}).scalar_one_or_none()
            if administrador is None:
                raise AuthorizationError('ACCESO_DENEGADO', 'El responsable debe existir y tener el rol Administrador.')
            uc = ConfigurarParametrosMLOpsUseCase(db, SqlAlchemyParametrosMLOpsRepository(db), SqlAlchemyConfiguracionGlobalRepository(db))
            if siembra:
                # Defaults D nunca sobrescriben un valor existente, ni cuando
                # se solicita actualizar otra clave en el archivo.
                acciones = uc.sembrar(cambios, administrador, aplicar=args.aplicar,
                                     actualizar_existentes=set(archivo) if args.actualizar_existentes else False)
                print('Siembra confirmada.' if args.aplicar else 'Simulación: no se realizaron escrituras.')
                for nombre, accion in sorted(acciones.items()):
                    print(f'{nombre}: {accion}')
            elif args.aplicar:
                uc.execute(cambios, administrador)
                print('Configuración confirmada; parámetros:', len(cambios))
            else:
                uc.validar(cambios)
                db.rollback()
                print('Validación correcta. No se realizaron escrituras. Use --aplicar para confirmar.')
        return 0
    except AppError as exc:
        print(f'{exc.code}: {exc.message}', file=sys.stderr)
        return 1
    except (SQLAlchemyError, OSError, ValueError):
        print('No se pudo procesar la configuración. Revise archivo, permisos y conexión.', file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
