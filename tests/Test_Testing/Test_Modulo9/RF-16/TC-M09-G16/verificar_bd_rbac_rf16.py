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
        
        print("=== VERIFICACION POST-CONDICION BD TEST PARA TC-M09-G16 (MEMBER_QA) ===")
        
        # 1. Verificar no persistencia de registros no autorizados en etapas
        cur.execute("SELECT COUNT(*) FROM modulo9.ciclos_biologicos WHERE nombre LIKE '%No Autorizada%QA';")
        cnt_etapas = cur.fetchone()[0]
        print(f"1. Filas no autorizadas en modulo9.ciclos_biologicos: {cnt_etapas}")
        
        # 2. Verificar no persistencia de registros no autorizados en patologias
        cur.execute("SELECT COUNT(*) FROM modulo9.especies_patologias WHERE nombre LIKE '%No Autorizada%QA';")
        cnt_pats = cur.fetchone()[0]
        print(f"2. Filas no autorizadas en modulo9.especies_patologias: {cnt_pats}")

        # 3. Verificar no persistencia de registros no autorizados en metricas
        cur.execute("SELECT COUNT(*) FROM modulo9.metricas_produccion WHERE nombre LIKE '%No Autorizada%QA';")
        cnt_mets = cur.fetchone()[0]
        print(f"3. Filas no autorizadas en modulo9.metricas_produccion: {cnt_mets}")

        # 4. Verificar inmutabilidad del atributo es_activo en los fixtures probados
        cur.execute("SELECT id_ciclo_biologico, es_activo FROM modulo9.ciclos_biologicos WHERE id_ciclo_biologico = 10;")
        e10 = cur.fetchone()
        print(f"4a. Etapa ID 10 es_activo: {e10[1] if e10 else 'NO ENCONTRADA'}")

        cur.execute("SELECT id_especies_patologias, es_activo FROM modulo9.especies_patologias WHERE id_especies_patologias = 1;")
        p1 = cur.fetchone()
        print(f"4b. Patología ID 1 es_activo: {p1[1] if p1 else 'NO ENCONTRADA'}")

        cur.execute("SELECT id_metrica_produccion, es_activo FROM modulo9.metricas_produccion WHERE id_metrica_produccion = 1;")
        m1 = cur.fetchone()
        print(f"4c. Métrica ID 1 es_activo: {m1[1] if m1 else 'NO ENCONTRADA'}")

        cur.close()
        conn.close()
        
        total_huérfanos = cnt_etapas + cnt_pats + cnt_mets
        fixtures_ok = (e10 and e10[1] is True) and (p1 and p1[1] is True) and (m1 and m1[1] is True)
        
        if total_huérfanos == 0 and fixtures_ok:
            print("\nVERIFICACION BD OK: 0 registros huérfanos creados y todos los fixtures se mantuvieron ACTIVOS (es_activo=True).")
            sys.exit(0)
        else:
            print(f"\nERROR DE INTEGRIDAD BD: Huérfanos={total_huérfanos}, Fixtures intactos={fixtures_ok}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Excepción durante verificación BD: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
