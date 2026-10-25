"""
Script de verificación de BD para TC-M09-G17 (Integridad Referencial por id_especie).
Consulta de SOLO LECTURA contra member_qa para verificar que NO se insertaron
registros huérfanos ni asociados a especies inexistentes (999, -1) o inactivas (1).
"""
import sys
import psycopg2

DB_CONFIG = {
    "dbname": "sgpmp_test",
    "user": "member_qa",
    "password": "qaSGP2026",
    "host": "158.69.200.27",
    "port": 5448
}

def main():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("=== VERIFICACIÓN BD INTEGRIDAD REFERENCIAL ID_ESPECIE (TC-M09-G17) ===")

        # 1. Verificar Etapas (ciclos_biologicos)
        query_ciclos = """
            SELECT id_ciclo_biologico, id_especie, nombre, es_activo
            FROM modulo9.ciclos_biologicos
            WHERE id_especie IN (999, -1)
               OR (id_especie = 1 AND nombre LIKE '%Especie Inactiva%')
               OR nombre LIKE '%Inexistente%'
               OR nombre LIKE '%ID Negativo%'
               OR nombre LIKE '%ID No Entero%';
        """
        cursor.execute(query_ciclos)
        ciclos_huerfanos = cursor.fetchall()
        print(f"\n1. Registros en modulo9.ciclos_biologicos (Esperado: 0): {len(ciclos_huerfanos)}")
        for r in ciclos_huerfanos:
            print(f"   - ID: {r[0]}, Especie: {r[1]}, Nombre: '{r[2]}', Activo: {r[3]}")

        # 2. Verificar Patologías (especies_patologias)
        query_patologias = """
            SELECT id_especies_patologias, id_especie, nombre, es_activo
            FROM modulo9.especies_patologias
            WHERE id_especie IN (999, -1)
               OR (id_especie = 1 AND nombre LIKE '%Especie Inactiva%')
               OR nombre LIKE '%Inexistente%'
               OR nombre LIKE '%ID Negativo%'
               OR nombre LIKE '%ID No Entero%';
        """
        cursor.execute(query_patologias)
        patologias_huerfanas = cursor.fetchall()
        print(f"\n2. Registros en modulo9.especies_patologias (Esperado: 0): {len(patologias_huerfanas)}")
        for r in patologias_huerfanas:
            print(f"   - ID: {r[0]}, Especie: {r[1]}, Nombre: '{r[2]}', Activo: {r[3]}")

        # 3. Verificar Métricas (metricas_produccion)
        query_metricas = """
            SELECT id_metrica_produccion, id_especie, nombre, es_activo
            FROM modulo9.metricas_produccion
            WHERE id_especie IN (999, -1)
               OR (id_especie = 1 AND nombre LIKE '%Especie Inactiva%')
               OR nombre LIKE '%Inexistente%'
               OR nombre LIKE '%ID Negativo%'
               OR nombre LIKE '%ID No Entero%';
        """
        cursor.execute(query_metricas)
        metricas_huerfanas = cursor.fetchall()
        print(f"\n3. Registros en modulo9.metricas_produccion (Esperado: 0): {len(metricas_huerfanas)}")
        for r in metricas_huerfanas:
            print(f"   - ID: {r[0]}, Especie: {r[1]}, Nombre: '{r[2]}', Activo: {r[3]}")

        cursor.close()
        conn.close()

        total_huerfanos = len(ciclos_huerfanos) + len(patologias_huerfanas) + len(metricas_huerfanas)
        print("\n=======================================================")
        print(f"TOTAL FILAS HUÉRFANAS / INCONSISTENTES DETECTADAS: {total_huerfanos}")
        print("=======================================================")

        if total_huerfanos == 0:
            print("RESULTADO BD: INTEGRIDAD REFERENCIAL 100% CORRECTA (0 filas huérfanas).")
            sys.exit(0)
        else:
            print("RESULTADO BD: FALLO - Se encontraron registros persistidos indebidamente.")
            sys.exit(1)

    except Exception as e:
        print(f"Error conectando o consultando la base de datos: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
