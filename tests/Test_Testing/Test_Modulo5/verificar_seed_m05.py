#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de verificación del estado y datos semilla para el Módulo 5 (Suministros).
Verifica disponibilidad de tablas, catálogos, configuraciones batch, registros, auditoría,
cuentas de prueba, volumetría de estrés para RF-76, RF-77, RF-80 y RF-81, y sondeo
autenticado por API de los activos y archivos sembrados por el DBA.

Modo: SOLO LECTURA (Zero-Pollution).
"""

import os
import sys
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import dotenv_values

def get_env_config():
    cfg = dotenv_values('.env.test')
    return {
        'db_url': cfg.get('TEST_DATABASE_URL'),
        'base_url': cfg.get('TEST_BASE_URL', 'https://www.api.inmero.co/api-sgpmp-test').rstrip('/'),
        'admin_email': 'administador.dev@gmail.com',
        'admin_password': cfg.get('TEST_ADMIN_PASSWORD', 'Admin12345!'),
        'sandbox_secret': cfg.get('TEST_SANDBOX_SECRET')
    }

def get_db_connection(db_url):
    if not db_url:
        print("❌ ERROR: TEST_DATABASE_URL no encontrada en .env.test")
        sys.exit(1)
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True, autocommit=True)
    return conn

def verificar_api_activos(base_url, admin_email, admin_password, checks):
    print("\n--- 5. VERIFICACIÓN POR API (GET AUTENTICADOS) ---")
    token = None
    try:
        login_resp = requests.post(
            f"{base_url}/sesiones/",
            json={"correo_electronico": admin_email, "contrasena": admin_password},
            timeout=10
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            print("  ✅ Login Admin por API exitoso (200 OK)")
            checks.append(("Login Admin por API", "OK", "Token obtenido"))
        else:
            print(f"  ⚠️ Login Admin respondió {login_resp.status_code}: {login_resp.text}")
            checks.append(("Login Admin por API", "WARN", f"Status {login_resp.status_code}"))
            return
    except Exception as e:
        print(f"  ❌ Error conectando a API para login: {e}")
        checks.append(("Login Admin por API", "FAIL", str(e)))
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 5.1 Verificar activos biológicos sembrados
    activos_semilla = [
        ("SEED-M05-REP-450D", "Activo 450 días (RF-77)"),
        ("SEED-M05-REP-500", "Activo borde 500 consumos (RF-77)"),
        ("SEED-M05-HIST-10K", "Activo 10.000 suministros (RF-81 N1)"),
        ("SEED-M05-HIST-50K", "Activo 50.000 suministros (RF-81 N2)"),
    ]

    for identificador, desc in activos_semilla:
        try:
            resp = requests.get(f"{base_url}/activos-biologicos?busqueda={identificador}", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", data) if isinstance(data, dict) else data
                encontrado = any(a.get("identificador") == identificador for a in items) if isinstance(items, list) else False
                if encontrado:
                    print(f"  ✅ {identificador} ({desc}): Visible por API")
                    checks.append((f"API Activo {identificador}", "OK", "Servido correctamente"))
                else:
                    print(f"  ⏳ {identificador} ({desc}): No encontrado en API (Pendiente aplicación DBA)")
                    checks.append((f"API Activo {identificador}", "PENDIENTE_DBA", "Pendiente aplicación script DBA"))
            else:
                print(f"  ⏳ {identificador}: API retornó {resp.status_code}")
                checks.append((f"API Activo {identificador}", "WARN", f"Status {resp.status_code}"))
        except Exception as e:
            print(f"  ❌ Error consultando activo {identificador}: {e}")
            checks.append((f"API Activo {identificador}", "FAIL", str(e)))

    # 5.2 Verificar archivos expirados (HTTP 410 Gone)
    archivos_expirados = [
        ("11111111-1111-1111-1111-111111111111", f"{base_url}/suministros/reportes-gastos/exportaciones/11111111-1111-1111-1111-111111111111", "RF-77 (24h)"),
        ("81001", f"{base_url}/suministros/historial/trabajos/81001/descargar", "RF-81 (72h)")
    ]

    for uuid_arch, url, rf_tag in archivos_expirados:
        try:
            r_exp = requests.get(url, headers=headers, timeout=10)
            if r_exp.status_code == 410:
                print(f"  ✅ Archivo expirado {rf_tag}: Responde 410 Gone conforme a especificación")
                checks.append((f"Archivo expirado {rf_tag}", "OK", "410 Gone confirmado"))
            elif r_exp.status_code == 404:
                print(f"  ⏳ Archivo expirado {rf_tag}: 404 Not Found (Pendiente aplicación DBA)")
                checks.append((f"Archivo expirado {rf_tag}", "PENDIENTE_DBA", "404 - Pendiente inserción DBA"))
            else:
                print(f"  ⚠️ Archivo expirado {rf_tag}: Respondió {r_exp.status_code}")
                checks.append((f"Archivo expirado {rf_tag}", "WARN", f"Status {r_exp.status_code}"))
        except Exception as e:
            print(f"  ❌ Error consultando archivo {rf_tag}: {e}")
            checks.append((f"Archivo expirado {rf_tag}", "FAIL", str(e)))

def main():
    print("=" * 75)
    print("🔍 VERIFICACIÓN DE SEED Y METADATOS: MÓDULO 5 (SUMINISTROS)")
    print("   Entorno: TEST (TEST_DATABASE_URL / TEST_BASE_URL)")
    print("   Modo   : SOLO LECTURA (Zero-Pollution)")
    print("=" * 75)

    config = get_env_config()

    try:
        conn = get_db_connection(config['db_url'])
    except Exception as e:
        print(f"❌ FALLO DE CONEXIÓN A BD: {e}")
        sys.exit(1)

    checks = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Tablas core de M05
        tablas_m05 = [
            'registros_medicamentos',
            'registros_consumo_alimentos',
            'registro_suministro',
            'auditorias_suministros',
            'reporte_gastos_acumulados',
            'acumulado_ciclo',
            'provision_nic41',
            'tipos_alimentos',
            'configuracion_batch_ica',
            'configuracion_batch_reportes_gastos',
            'configuracion_batch_historial_suministros'
        ]
        
        print("\n--- 1. TABLAS CORE MÓDULO 5 ---")
        for tbl in tablas_m05:
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM modulo5.{tbl}")
                cnt = cur.fetchone()['cnt']
                print(f"  ✅ modulo5.{tbl}: {cnt} registros")
                checks.append((f"Tabla modulo5.{tbl}", "OK", f"{cnt} filas"))
            except Exception as e:
                print(f"  ❌ modulo5.{tbl}: ERROR {e}")
                checks.append((f"Tabla modulo5.{tbl}", "FAIL", str(e)))
                conn.rollback()

        # 2. Catálogos base
        print("\n--- 2. CATÁLOGOS BASE ---")
        try:
            cur.execute("SELECT id_tipo_elemento, nombre, estado, costo_unitario FROM modulo5.tipos_alimentos WHERE estado='ACTIVO'")
            alim = cur.fetchall()
            if alim:
                print(f"  ✅ Catálogo tipos_alimentos activo: {len(alim)} items (ej. ID {alim[0]['id_tipo_elemento']} - {alim[0]['nombre']})")
                checks.append(("Catálogo tipos_alimentos", "OK", f"{len(alim)} items"))
            else:
                print("  ⚠️ Catálogo tipos_alimentos vacío o inactivo")
                checks.append(("Catálogo tipos_alimentos", "WARN", "0 items activos"))
        except Exception as e:
            print(f"  ❌ Error consultando tipos_alimentos: {e}")
            checks.append(("Catálogo tipos_alimentos", "FAIL", str(e)))
            conn.rollback()

        try:
            cur.execute("SELECT COUNT(*) as total FROM modulo9.especies WHERE es_activo=true")
            tot_esp = cur.fetchone()['total']
            print(f"  ✅ Especies activas en M09: {tot_esp}")
            checks.append(("Especies activas en M09", "OK", f"{tot_esp} especies"))
        except Exception as e:
            print(f"  ❌ Error especies: {e}")
            checks.append(("Especies activas en M09", "FAIL", str(e)))
            conn.rollback()

        # 3. Verificación de RLS en M01/M02/M09
        print("\n--- 3. VERIFICACIÓN DE RLS Y ACCESO A DATOS PADRE ---")
        try:
            cur.execute("SELECT COUNT(*) as cnt FROM modulo1.usuarios")
            u_cnt = cur.fetchone()['cnt']
            if u_cnt == 0:
                print("  ⚠️ modulo1.usuarios devuelve 0 filas bajo rol member_qa (RLS activa)")
                checks.append(("Lectura directa modulo1.usuarios", "WARN", "RLS bloquea visibilidad directa (0 filas)"))
            else:
                print(f"  ✅ modulo1.usuarios visibles: {u_cnt}")
                checks.append(("Lectura directa modulo1.usuarios", "OK", f"{u_cnt} usuarios"))
        except Exception as e:
            print(f"  ❌ modulo1.usuarios: {e}")
            checks.append(("Lectura directa modulo1.usuarios", "NO_VERIFICABLE", str(e)))
            conn.rollback()

        try:
            cur.execute("SELECT COUNT(*) as cnt FROM modulo2.activos_biologicos")
            a_cnt = cur.fetchone()['cnt']
            if a_cnt == 0:
                print("  ⚠️ modulo2.activos_biologicos devuelve 0 filas bajo rol member_qa (RLS activa)")
                checks.append(("Lectura directa modulo2.activos", "WARN", "RLS bloquea visibilidad directa (0 filas)"))
            else:
                print(f"  ✅ modulo2.activos_biologicos visibles: {a_cnt}")
                checks.append(("Lectura directa modulo2.activos", "OK", f"{a_cnt} activos"))
        except Exception as e:
            print(f"  ❌ modulo2.activos_biologicos: {e}")
            checks.append(("Lectura directa modulo2.activos", "NO_VERIFICABLE", str(e)))
            conn.rollback()

        # 4. Volumetría y Estados en M05
        print("\n--- 4. VOLUMETRÍA Y ESTADOS EN MÓDULO 5 ---")
        try:
            cur.execute("SELECT estado_registro, count(*) FROM modulo5.registros_medicamentos GROUP BY estado_registro")
            med_estados = {r['estado_registro']: r['count'] for r in cur.fetchall()}
            print(f"  ℹ️ Medicamentos por estado: {med_estados}")

            cur.execute("SELECT estado_registro, count(*) FROM modulo5.registros_consumo_alimentos GROUP BY estado_registro")
            alim_estados = {r['estado_registro']: r['count'] for r in cur.fetchall()}
            print(f"  ℹ️ Consumos por estado: {alim_estados}")

            cur.execute("SELECT tipo_operacion, count(*) FROM modulo5.registro_suministro GROUP BY tipo_operacion")
            sum_ops = {r['tipo_operacion']: r['count'] for r in cur.fetchall()}
            print(f"  ℹ️ Suministros (RF-78) por tipo_operacion: {sum_ops}")

            cur.execute("SELECT count(*) as total FROM modulo5.auditorias_suministros WHERE tipo_operacion NOT IN ('INSERT','UPDATE')")
            aud_negocio = cur.fetchone()['total']
            print(f"  ℹ️ Auditorías de negocio M05 emitidas: {aud_negocio}")

            # Umbral de volumen para RF-78 (Estrés >= 500)
            cur.execute("SELECT count(*) as total FROM modulo5.registro_suministro")
            tot_sum = cur.fetchone()['total']
            if tot_sum < 500:
                print(f"  ⚠️ Volumetría RF-78 insuficiente para estrés: {tot_sum} < 500 (Requiere DBA)")
                checks.append(("Volumen RF-78 (≥500 registros)", "WARN", f"{tot_sum} existentes (Requiere DBA)"))
            else:
                print(f"  ✅ Volumetría RF-78 suficiente: {tot_sum} registros")
                checks.append(("Volumen RF-78 (≥500 registros)", "OK", f"{tot_sum} registros"))

            # Umbral de volumen para RF-81 (Estrés >= 10.001)
            if tot_sum < 10001:
                print(f"  ⚠️ Volumetría RF-81 insuficiente para async: {tot_sum} < 10.001 (Requiere DBA)")
                checks.append(("Volumen RF-81 (≥10.001 registros)", "WARN", f"{tot_sum} existentes (Requiere DBA)"))
            else:
                print(f"  ✅ Volumetría RF-81 async suficiente: {tot_sum} registros")
                checks.append(("Volumen RF-81 (≥10.001 registros)", "OK", f"{tot_sum} registros"))

            # Integridad de Hashes SHA-256 en Auditoría
            cur.execute("SELECT count(*) as total FROM modulo5.auditorias_suministros WHERE hash_integridad IS NOT NULL")
            aud_hash = cur.fetchone()['total']
            print(f"  ℹ️ Registros con hash de integridad en auditoría: {aud_hash}")
            checks.append(("Auditoría con hash SHA-256", "OK", f"{aud_hash} registros"))

        except Exception as e:
            print(f"  ❌ Error evaluando volumetría: {e}")
            conn.rollback()

    conn.close()

    # 5. Verificación por API
    verificar_api_activos(config['base_url'], config['admin_email'], config['admin_password'], checks)

    print("\n" + "=" * 75)
    print("📊 RESUMEN FINAL DEL SEMÁFORO")
    print("=" * 75)
    for name, status, detail in checks:
        icon = "✅" if status == "OK" else ("⚠️" if status == "WARN" else ("⏳" if status == "PENDIENTE_DBA" else ("⏭️" if status == "SKIP" else "❌")))
        print(f"  {icon} {name:42}: {status} - {detail}")
    print("=" * 75)

if __name__ == '__main__':
    main()
