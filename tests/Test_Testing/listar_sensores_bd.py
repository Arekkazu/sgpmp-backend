# Lista (solo lectura) los sensores del dispositivo en la BD de TEST para sacar sus ids.
# Usa la variable PGPASSWORD si existe (solo de esa terminal); si no, pide la clave oculta.
# Uso:  python listar_sensores_bd.py            (dispositivo 339 por defecto)
#       python listar_sensores_bd.py 346
import os, sys, getpass
import psycopg2

dispositivo = int(sys.argv[1]) if len(sys.argv) > 1 else 339
host = input("Host [158.69.200.27]: ").strip() or "158.69.200.27"
port = input("Puerto [5448]: ").strip() or "5448"
user = input("Usuario [member_qa]: ").strip() or "member_qa"
db = input("Base [sgpmp_test]: ").strip() or "sgpmp_test"
pw = os.environ.get("PGPASSWORD") or getpass.getpass("Clave: ")

con = psycopg2.connect(host=host, port=port, user=user, password=pw, dbname=db, connect_timeout=10)
con.set_session(readonly=True, autocommit=True)
cur = con.cursor()

cur.execute("""select table_schema, table_name from information_schema.tables
               where table_name ilike '%sensor%' and table_type='BASE TABLE' order by 1,2""")
tablas = cur.fetchall()
print("Tablas con 'sensor':", tablas, "\n")

for esq, tab in tablas:
    cur.execute("""select column_name from information_schema.columns
                   where table_schema=%s and table_name=%s order by ordinal_position""", (esq, tab))
    cols = [r[0] for r in cur.fetchall()]
    col_disp = next((c for c in cols if "dispositivo" in c.lower()), None)
    print(f"== {esq}.{tab}  columnas: {cols}")
    if not col_disp:
        print("   (sin columna de dispositivo, se omite)\n"); continue
    try:
        cur.execute(f'select * from "{esq}"."{tab}" where "{col_disp}" = %s limit 50', (dispositivo,))
        nombres = [d[0] for d in cur.description]
        for fila in cur.fetchall():
            print("  ", dict(zip(nombres, fila)))
    except Exception as e:
        print("   sin permiso o error:", str(e).strip().splitlines()[0])
    print()
