import psycopg2
import sys

def main():
    try:
        conn = psycopg2.connect(
            host="158.69.200.27",
            port=5448,
            dbname="sgpmp_test",
            user="member_qa",
            password="qaSGP2026"
        )
        cur = conn.cursor()
        
        print("Conectado a PostgreSQL TEST (member_qa). Verificando no persistencia de registros sinteticos de prueba...")
        
        # Verificar metricas con patron de prueba
        cur.execute("SELECT id_metrica_produccion, nombre, unidad_medida, tipo_medicion FROM modulo9.metricas_produccion WHERE nombre LIKE 'Metrica % QA';")
        rows = cur.fetchall()
        
        print(f"Filas encontradas con patron 'Metrica % QA': {len(rows)}")
        for r in rows:
            print(f" - ID: {r[0]}, Nombre: {r[1]}, Unidad: {r[2]}, Tipo: {r[3]}")
            
        cur.close()
        conn.close()
        
        if len(rows) == 0:
            print("VERIFICACION BD OK: 0 filas huérfanas encontradas en modulo9.metricas_produccion.")
            sys.exit(0)
        else:
            print(f"ERROR: Se encontraron {len(rows)} filas huérfanas que no debieron persistirse.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Excepcion durante verificacion BD: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
