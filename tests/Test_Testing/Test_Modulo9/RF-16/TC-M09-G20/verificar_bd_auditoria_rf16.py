"""
Script de verificación BD para TC-M09-G20 (Auditoría de operaciones sobre RF-16).
Consulta de SOLO LECTURA contra member_qa para verificar que las operaciones
CREATE, UPDATE y DEACTIVATE sobre etapas productivas hayan generado registros de auditoría
en modulo9.auditorias_ciclos_biologicos con id_usuario=1, payloads coherentes y 0 registros
por intentos fallidos.
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
        print("=== VERIFICACIÓN BD AUDITORÍA RF-16 (TC-M09-G20) ===")

        # 1. Obtener la etapa de prueba creada
        cursor.execute("""
            SELECT id_ciclo_biologico, nombre, es_activo
            FROM modulo9.ciclos_biologicos
            WHERE nombre LIKE '%Etapa Auditoria QA%'
            ORDER BY id_ciclo_biologico DESC
            LIMIT 1;
        """)
        ciclo_row = cursor.fetchone()
        if not ciclo_row:
            print("ERROR: No se encontró la etapa de prueba 'Etapa Auditoria QA' en BD.")
            sys.exit(1)

        id_ciclo = ciclo_row[0]
        nombre_ciclo = ciclo_row[1]
        es_activo = ciclo_row[2]
        print(f"\n1. Etapa de prueba identificada en BD TEST: ID={id_ciclo}, Nombre='{nombre_ciclo}', es_activo={es_activo}")

        # 2. Consultar registros de auditoría para la etapa de prueba
        cursor.execute("""
            SELECT id_auditoria_ciclo, id_usuario, tipo_operacion, valores_anteriores, valores_nuevos, fecha_gestion
            FROM modulo9.auditorias_ciclos_biologicos
            WHERE id_ciclo_biologico = %s
            ORDER BY id_auditoria_ciclo ASC;
        """, (id_ciclo,))
        auditorias = cursor.fetchall()

        print(f"\n2. Registros de auditoría encontrados para ID {id_ciclo}: {len(auditorias)} (Esperado: 3)")
        
        operaciones_esperadas = ["CREATE", "UPDATE", "DEACTIVATE"]
        errores = []

        if len(auditorias) != 3:
            errores.append(f"Se esperaban 3 eventos de auditoría (CREATE, UPDATE, DEACTIVATE), pero se encontraron {len(auditorias)}.")

        for idx, r in enumerate(auditorias):
            id_aud, id_usr, tipo_op, val_ant, val_nuev, fecha_gest = r
            op_esperada = operaciones_esperadas[idx] if idx < len(operaciones_esperadas) else "UNKNOWN"
            print(f"   - Evento {idx+1}: ID_Auditoria={id_aud}, Usuario={id_usr}, Operacion='{tipo_op}', Fecha={fecha_gest}")
            
            if id_usr != 1:
                errores.append(f"Evento {idx+1} tiene id_usuario={id_usr}, se esperaba 1 (Admin).")

            if tipo_op != op_esperada:
                errores.append(f"Evento {idx+1} tiene tipo_operacion='{tipo_op}', se esperaba '{op_esperada}'.")

            if tipo_op == "CREATE":
                if val_ant is not None:
                    errores.append("Evento CREATE debe tener valores_anteriores = NULL.")
                if not val_nuev or val_nuev.get("nombre") != "Etapa Auditoria QA":
                    errores.append("Evento CREATE tiene valores_nuevos incoherentes con el payload inicial.")

            elif tipo_op == "UPDATE":
                if not val_ant or val_ant.get("nombre") != "Etapa Auditoria QA":
                    errores.append("Evento UPDATE tiene valores_anteriores incoherentes (debía ser 'Etapa Auditoria QA').")
                if not val_nuev or val_nuev.get("nombre") != "Etapa Auditoria QA Editada":
                    errores.append("Evento UPDATE tiene valores_nuevos incoherentes (debía ser 'Etapa Auditoria QA Editada').")

            elif tipo_op == "DEACTIVATE":
                if not val_ant or val_ant.get("es_activo") is not True:
                    errores.append("Evento DEACTIVATE tiene valores_anteriores incoherentes (debía tener es_activo=True).")
                if not val_nuev or val_nuev.get("es_activo") is not False:
                    errores.append("Evento DEACTIVATE tiene valores_nuevos incoherentes (debía tener es_activo=False).")

        # 3. Verificar que el intento fallido por duplicado (HTTP 409) NO haya generado evento en la etapa existente 'Fase juvenil cachama' (ID 10)
        cursor.execute("""
            SELECT COUNT(*)
            FROM modulo9.auditorias_ciclos_biologicos
            WHERE id_ciclo_biologico = 10
              AND fecha_gestion > (NOW() - INTERVAL '5 minutes');
        """)
        cnt_intentos_fallidos = cursor.fetchone()[0]
        print(f"\n3. Registros de auditoría generados por el intento fallido (HTTP 409): {cnt_intentos_fallidos} (Esperado: 0)")
        if cnt_intentos_fallidos != 0:
            errores.append(f"Un intento fallido generó {cnt_intentos_fallidos} registro(s) de auditoría en BD (viola regla de auditoría limpia).")

        cursor.close()
        conn.close()

        print("\n=======================================================")
        if len(errores) == 0:
            print("RESULTADO BD: AUDITORÍA RF-16 100% CORRECTA (3 eventos válidos, 0 en fallidos).")
            sys.exit(0)
        else:
            print("RESULTADO BD: FALLO EN AUDITORÍA RF-16")
            for err in errores:
                print(f"   - {err}")
            sys.exit(1)

    except Exception as e:
        print(f"Error conectando o consultando la base de datos: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
