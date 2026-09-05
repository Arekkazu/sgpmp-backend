"""Script de Verificación de Solo Lectura contra BD TEST (member_qa).

Verifica que el intento de registro con descripción de 256 caracteres (TC-M09-29)
NO haya dejado ningún registro persistido en la tabla `modulo9.especies_patologias`.
"""
import psycopg2

DB_HOST = "158.69.200.27"
DB_PORT = 5448
DB_USER = "member_qa"
DB_PASS = "qaSGP2026"
DB_NAME = "sgpmp_test"

def verificar_no_persistencia_patologia():
    print("=== TC-M09-G13: Verificación de Solo Lectura BD TEST (sgpmp_test) ===")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME,
            connect_timeout=10
        )
        cur = conn.cursor()
        
        # Buscar en modulo9.especies_patologias por descripciones de 256 o más caracteres o que contengan 'DDDDD'
        cur.execute("SELECT id_especies_patologias, id_especie, nombre, descripcion FROM modulo9.especies_patologias WHERE length(descripcion) > 255 OR descripcion LIKE %s;", ('%DDDDDDDDDD%',))
        registros = cur.fetchall()
        
        print(f"Total de registros con descripción > 255 chars o 'DDDD...': {len(registros)}")
        for r in registros:
            print("  [REGISTRO ANÓMALO ENCONTRADO]:", r)
            
        cur.close()
        conn.close()
        
        return len(registros) == 0
    except Exception as exc:
        print(f"Error al consultar BD TEST: {exc}")
        return False

if __name__ == "__main__":
    verificar_no_persistencia_patologia()
