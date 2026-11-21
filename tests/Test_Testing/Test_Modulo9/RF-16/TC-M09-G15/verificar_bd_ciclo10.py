import os
import sys
import psycopg2


def _obtener_config_bd() -> dict:
    variables = ["TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_NAME", "TEST_DB_USER", "TEST_DB_PASSWORD"]
    faltantes = [v for v in variables if not os.environ.get(v)]
    if faltantes:
        print(f"ERROR: Variables de entorno obligatorias no configuradas: {', '.join(faltantes)}")
        sys.exit(1)

    try:
        port = int(os.environ["TEST_DB_PORT"])
    except ValueError:
        print("ERROR: La variable TEST_DB_PORT debe ser un número entero válido.")
        sys.exit(1)

    return {
        "host": os.environ["TEST_DB_HOST"],
        "port": port,
        "dbname": os.environ["TEST_DB_NAME"],
        "user": os.environ["TEST_DB_USER"],
        "password": os.environ["TEST_DB_PASSWORD"],
    }


def main():
    cfg = _obtener_config_bd()

    try:
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        
        print("Conectado a PostgreSQL TEST. Verificando que la etapa 10 (Fase juvenil cachama) permanezca activa...")
        
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
