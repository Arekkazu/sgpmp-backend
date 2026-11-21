import psycopg2
import json

conn = psycopg2.connect(
    host="158.69.200.27",
    port=5448,
    user="member_qa",
    password="qaSGP2026",
    dbname="sgpmp_test"
)
cur = conn.cursor()

# Buscar en modulo9.especies por cualquier nombre que empiece con Especie
cur.execute("SELECT id_especie, nombre, es_activo, fecha_creacion FROM modulo9.especies WHERE nombre LIKE %s OR nombre LIKE %s", ('Especie%', 'Especie_QA%'))
especies_huerfanas = cur.fetchall()

# Buscar en modulo9.auditorias_especies por cualquier registro que mencione Especie
cur.execute("SELECT id_auditoria_especie, id_especie, tipo_operacion, fecha_gestion, valores_nuevos FROM modulo9.auditorias_especies WHERE valores_nuevos::text LIKE %s", ('%Especie%',))
auditorias_huerfanas = cur.fetchall()

print("--- RESULTADO DE INTEGRIDAD POST-CREATE FALLIDO ---")
print(f"Filas huérfanas en modulo9.especies: {len(especies_huerfanas)}")
for e in especies_huerfanas:
    print("  ", e)

print(f"Filas huérfanas en modulo9.auditorias_especies: {len(auditorias_huerfanas)}")
for a in auditorias_huerfanas:
    print("  ", a)

conn.close()
