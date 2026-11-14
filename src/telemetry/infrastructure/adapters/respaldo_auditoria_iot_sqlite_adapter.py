# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: resguardar solo auditoría en disco independiente con orden FIFO y transacciones durables. |
from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import UUID
import json
import os
import sqlite3
from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot


class RespaldoAuditoriaIotSqliteAdapter:
    """No almacena ni reprocesa lecturas: su resguardo continúa en RF-54/P5."""
    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta or os.getenv('IOT_AUDITORIA_RESPALDO_PATH', 'var/auditoria_iot/fallas.sqlite3'))

    @contextmanager
    def _conexion(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self.ruta), timeout=5)) as db:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                db.execute('''CREATE TABLE IF NOT EXISTS pendientes (
                    secuencia INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_evento TEXT NOT NULL UNIQUE, contenido TEXT NOT NULL)''')
                yield db

    def guardar(self, evento: EventoAuditoriaIot) -> None:
        if evento.id_evento is None or evento.tipo_evento != 'FALLA_PERSISTENCIA':
            raise ValueError('El respaldo requiere una falla de persistencia con UUID estable.')
        contenido = json.dumps(asdict(evento), default=str, sort_keys=True, ensure_ascii=False)
        with self._conexion() as db:
            db.execute('INSERT INTO pendientes(id_evento,contenido) VALUES (?,?) ON CONFLICT(id_evento) DO NOTHING',
                       (str(evento.id_evento), contenido))
            actual = db.execute('SELECT contenido FROM pendientes WHERE id_evento=?',(str(evento.id_evento),)).fetchone()[0]
            if actual != contenido:
                raise ValueError('El UUID del respaldo ya corresponde a otra evidencia.')

    def hay_pendientes(self) -> bool:
        if not self.ruta.exists():
            return False
        with self._conexion() as db:
            return db.execute('SELECT 1 FROM pendientes LIMIT 1').fetchone() is not None

    def listar(self, limite: int) -> list[EventoAuditoriaIot]:
        if limite <= 0:
            raise ValueError('El límite de recuperación debe ser positivo.')
        if not self.ruta.exists():
            return []
        with self._conexion() as db:
            filas = db.execute('SELECT contenido FROM pendientes ORDER BY secuencia LIMIT ?', (limite,)).fetchall()
        eventos = []
        for (contenido,) in filas:
            datos = json.loads(contenido)
            datos['id_evento'] = UUID(datos['id_evento'])
            datos['fecha_hora'] = datetime.fromisoformat(datos['fecha_hora'])
            if datos.get('timestamp_registro'):
                datos['timestamp_registro'] = datetime.fromisoformat(datos['timestamp_registro'])
            eventos.append(EventoAuditoriaIot(**datos))
        return eventos

    def confirmar(self, identificadores: list[UUID]) -> None:
        if not identificadores:
            return
        with self._conexion() as db:
            db.executemany('DELETE FROM pendientes WHERE id_evento=?', [(str(i),) for i in identificadores])
