"""Script de Verificación de Solo Lectura contra BD TEST (member_qa).

Verifica la presencia de registros de auditoría en `modulo9.auditorias_especies`
(valores_anteriores y valores_nuevos) y en `modulo1.eventos` para el caso TC-M09-G08.
"""
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = "158.69.200.27"
DB_PORT = 5448
DB_USER = "member_qa"
DB_PASS = "qaSGP2026"
DB_NAME = "sgpmp_test"

def verificar_auditoria_bd(id_especie=None, nombre_especie=None):
    print(f"=== Verificación de Solo Lectura BD TEST ({DB_NAME}) ===")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME,
            connect_timeout=10
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Consultar modulo9.auditorias_especies
        print("\n--- 1. Registros en modulo9.auditorias_especies ---")
        query_m09 = "SELECT * FROM modulo9.auditorias_especies"
        params = []
        if id_especie:
            query_m09 += " WHERE id_especie = %s"
            params.append(int(id_especie))
        query_m09 += " ORDER BY id_auditoria_especie DESC LIMIT 5;"
        
        cursor.execute(query_m09, params)
        filas_m09 = cursor.fetchall()
        print(f"Total registros encontrados en modulo9.auditorias_especies: {len(filas_m09)}")
        for f in filas_m09:
            print(f"  [Auditoría ID: {f['id_auditoria_especie']}] Especie ID: {f['id_especie']} | Operación: {f['tipo_operacion']} | Usuario: {f['id_usuario']} | Fecha: {f['fecha_gestion']}")
            print(f"    - Valores Anteriores: {json.dumps(f['valores_anteriores'], ensure_ascii=False)}")
            print(f"    - Valores Nuevos:     {json.dumps(f['valores_nuevos'], ensure_ascii=False)}")

        # 2. Consultar modulo1.eventos (Audit general)
        print("\n--- 2. Registros en modulo1.eventos (Usuario Admin ID 1) ---")
        cursor.execute("SELECT id_evento, tipo_evento, fecha_evento, modulo, resultado, detalle, id_usuario, descripcion FROM modulo1.eventos WHERE id_usuario = 1 ORDER BY id_evento DESC LIMIT 5;")
        filas_m01 = cursor.fetchall()
        print(f"Total eventos encontrados en modulo1.eventos para Admin: {len(filas_m01)}")
        for e in filas_m01:
            print(f"  [Evento ID: {e['id_evento']}] Tipo: {e['tipo_evento']} | Modulo: {e['modulo']} | Resultado: {e['resultado']} | Fecha: {e['fecha_evento']}")
            print(f"    - Detalle: {json.dumps(e['detalle'], ensure_ascii=False)}")

        cursor.close()
        conn.close()
        return len(filas_m09)
    except Exception as exc:
        print(f"Error al conectar o consultar BD TEST: {exc}")
        return 0

if __name__ == "__main__":
    id_esp = sys.argv[1] if len(sys.argv) > 1 else None
    verificar_auditoria_bd(id_esp)
