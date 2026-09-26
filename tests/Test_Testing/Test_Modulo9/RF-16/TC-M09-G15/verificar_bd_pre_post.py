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
        print("=== ESTADO DE BASE DE DATOS (TC-M09-G15) ===")

        # 1. Etapa id=10
        cur.execute("""
            SELECT cb.id_ciclo_biologico, cb.nombre, cb.es_activo,
                   count(cpb.id_ciclos_productivo_biologico) AS referencias_productivas
            FROM modulo9.ciclos_biologicos cb
            LEFT JOIN modulo9.ciclos_productivos_biologicos cpb ON cpb.id_ciclo_biologico = cb.id_ciclo_biologico
            WHERE cb.id_ciclo_biologico = 10
            GROUP BY cb.id_ciclo_biologico, cb.nombre, cb.es_activo;
        """)
        etapa = cur.fetchone()
        print(f"[ETAPA] id_ciclo_biologico={etapa[0]} | nombre='{etapa[1]}' | es_activo={etapa[2]} | referencias_productivas={etapa[3]}")

        # 2. Patología id_especies_patologias=7, id_patologia=1
        cur.execute("""
            SELECT ep.id_especies_patologias, ep.nombre, ep.es_activo, ep.id_patologia,
                   p.nombre as nombre_catalogo,
                   count(DISTINCT pr.id_prediccion) AS predicciones_asociadas,
                   count(DISTINCT ap.id_alerta_patologica) AS alertas_asociadas
            FROM modulo9.especies_patologias ep
            JOIN modulo9.patologias p ON p.id_patologia = ep.id_patologia
            LEFT JOIN modulo4.predicciones pr ON pr.id_patologia = p.id_patologia
            LEFT JOIN modulo4.alertas_patologicas ap ON ap.id_patologia = p.id_patologia
            WHERE ep.id_especies_patologias = 7
            GROUP BY ep.id_especies_patologias, ep.nombre, ep.es_activo, ep.id_patologia, p.nombre;
        """)
        patologia = cur.fetchone()
        print(f"[PATOLOGÍA] id_especies_patologias={patologia[0]} | nombre='{patologia[1]}' | es_activo={patologia[2]} | id_patologia={patologia[3]} | predicciones={patologia[5]} | alertas={patologia[6]}")

        # 3. Métrica id_metrica_produccion=1
        cur.execute("""
            SELECT m.id_metrica_produccion, m.nombre, m.tipo_medicion, m.es_activo,
                   count(ep.id_evento) AS eventos_productivos
            FROM modulo9.metricas_produccion m
            LEFT JOIN modulo2.eventos_productivos ep ON ep.id_metrica_produccion = m.id_metrica_produccion
            WHERE m.id_metrica_produccion = 1
            GROUP BY m.id_metrica_produccion, m.nombre, m.tipo_medicion, m.es_activo;
        """)
        metrica = cur.fetchone()
        print(f"[MÉTRICA] id_metrica_produccion={metrica[0]} | nombre='{metrica[1]}' | tipo_medicion='{metrica[2]}' | es_activo={metrica[3]} | eventos_productivos={metrica[4]}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error en consulta de BD: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
