import os, psycopg2
conn = psycopg2.connect(os.environ['DEV14_DATABASE_URL'])
cur = conn.cursor()
cur.execute("""DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro IN ('rf62_k','rf62_m','rf62_n','rf62_p','rf62_umbral_drift')""")
print(f'DELETE afecto {cur.rowcount} filas')
conn.commit()
conn.close()