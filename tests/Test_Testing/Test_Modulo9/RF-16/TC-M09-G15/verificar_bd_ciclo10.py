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
        
        print("Conectado a PostgreSQL TEST (member_qa). Verificando que la etapa 10 (Fase juvenil cachama) permanezca activa...")
        
        cur.execute("SELECT id_ciclo_biologico, nombre, es_activo FROM modulo9.ciclos_biologicos WHERE id_ciclo_biologico = 10;")
        row = cur.fetchone()
        
        if not row:
            print("ERROR: No se encontró la etapa con ID 10 en la base de datos.")
            sys.exit(1)
            
        print(f" -> ID: {row[0]}, Nombre: '{row[1]}', es_activo: {row[2]}")
        
        cur.close()
        conn.close()
        
        if row[2] is True:
            print("VERIFICACION BD OK: La etapa ID 10 permaneció ACTIVA (es_activo = True) tras rechazar la desactivación.")
            sys.exit(0)
        else:
            print("ERROR GRAVE: La etapa ID 10 fue desactivada en BD cuando debió bloquearse.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Excepción durante verificación BD: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
