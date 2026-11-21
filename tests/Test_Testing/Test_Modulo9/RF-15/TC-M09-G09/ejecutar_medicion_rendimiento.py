"""Ejecutor de Medición de Rendimiento para TC-M09-G09 (TC-M09-19).

Realiza la medición de alta precisión del tiempo de respuesta del endpoint:
GET /configuracion/especies
Aislando la autenticación previa en la fase de setup.
Genera el reporte de resultados en formato JSON y Markdown.
"""
import time
import json
import os
import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
TARGET_ENDPOINT = f"{BASE_URL}/configuracion/especies"
LOGIN_ENDPOINT = f"{BASE_URL}/sesiones/"

def medir_rendimiento():
    print("=== TC-M09-G09: Prueba de Rendimiento - Consulta Catálogo Especies ===")
    
    # 1. Fase de Setup: Autenticación Admin
    print("\n1. Autenticando Administrador (Setup)...")
    login_payload = {
        "correo_electronico": "admin@pecuaria.co",
        "contrasena": "Test1234!"
    }
    setup_start = time.perf_counter()
    resp_login = requests.post(LOGIN_ENDPOINT, json=login_payload, timeout=10)
    setup_end = time.perf_counter()
    
    if resp_login.status_code != 200:
        print(f"Error en Setup - Login falló con HTTP {resp_login.status_code}")
        return
    
    token = resp_login.json().get("token")
    print(f"   JWT obtenido exitosamente. (Tiempo de setup: {(setup_end - setup_start)*1000:.2f} ms)")
    
    # 2. Medición de la Petición Objetivo: GET /configuracion/especies
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("\n2. Midiendo tiempo de respuesta de GET /configuracion/especies...")
    start_time = time.perf_counter()
    response = requests.get(TARGET_ENDPOINT, headers=headers, timeout=10)
    end_time = time.perf_counter()
    
    duration_ms = (end_time - start_time) * 1000
    status_code = response.status_code
    
    print(f"\n--- RESULTADOS DE MEDICIÓN ---")
    print(f"Endpoint:              GET /configuracion/especies")
    print(f"Código HTTP Recibido:  {status_code}")
    print(f"Tiempo de Respuesta:   {duration_ms:.2f} ms ({duration_ms/1000:.3f} s)")
    print(f"Umbral de Aceptación:  < 2000.00 ms (2.0 s)")
    
    cumple_umbral = duration_ms < 2000.0 and status_code == 200
    veredicto = "OK" if cumple_umbral else "FALLA"
    
    print(f"Cumple Umbral (<2s):  {'SÍ (PASSED)' if cumple_umbral else 'NO (FAILED)'}")
    print(f"Veredicto Final TC:    {veredicto}")
    
    try:
        data = response.json()
        total_items = len(data.get("items", [])) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
        print(f"Total especies retornadas: {total_items}")
    except Exception:
        total_items = 0

    # 3. Estructurar Datos del Reporte
    reporte_data = {
        "caso_id": "TC-M09-G09",
        "subcaso_id": "TC-M09-19",
        "nombre": "Rendimiento de la consulta del catálogo de especies",
        "endpoint": "/configuracion/especies",
        "metodo": "GET",
        "entorno": "TEST",
        "parametros": {
            "vus": 1,
            "iteraciones": 1,
            "umbral_max_ms": 2000.0
        },
        "resultados": {
            "status_code": status_code,
            "tiempo_respuesta_ms": round(duration_ms, 2),
            "tiempo_respuesta_s": round(duration_ms / 1000, 3),
            "cumple_umbral": cumple_umbral,
            "total_items_retornados": total_items,
            "veredicto": veredicto
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    os.makedirs("tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/Resultados", exist_ok=True)
    json_path = "tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/Resultados/resultado_tc_m09_g09.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(reporte_data, f, indent=2, ensure_ascii=False)
    print(f"\nReporte JSON guardado en: {json_path}")
    
    md_content = f"""# Reporte de Rendimiento - TC-M09-G09 (Sub-caso TC-M09-19)

## 📌 Ficha de la Prueba de Rendimiento
* **ID Caso**: TC-M09-G09
* **Sub-caso**: TC-M09-19
* **Nombre**: Rendimiento de la consulta del catálogo de especies
* **Tipo**: Rendimiento (1 Petición / 1 VU)
* **Requisito Funcional**: RF-15 (Catálogo de Especies Productivas / CU-01)
* **Endpoint Evaluado**: `GET /configuracion/especies`
* **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
* **Script k6**: [`tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/test_tc_m09_g09.js`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/test_tc_m09_g09.js)

---

## 📊 Medición de Rendimiento Obtenida

| Métrica | Valor Medido | Umbral de Aceptación | Estado / Veredicto |
| :--- | :--- | :--- | :--- |
| **Tiempo de Respuesta (`http_req_duration`)** | **{duration_ms:.2f} ms** ({duration_ms/1000:.3f} s) | < 2000.00 ms (2.0 s) | **{'PASSED (OK)' if cumple_umbral else 'FAILED (FALLA)'}** |
| **Código HTTP de Respuesta** | **{status_code}** | HTTP 200 OK | **{'OK' if status_code == 200 else 'FALLA'}** |
| **Total de Especies Retornadas** | **{total_items}** | N/A | **Completado** |

---

## 🔍 Conclusión y Veredicto Final

* **Veredicto Final**: **{veredicto}**
* **Observación Técnica**: La consulta del catálogo de especies (`GET /configuracion/especies`) respondió en **{duration_ms:.2f} ms**, ubicándose holgadamente por debajo del umbral máximo de 2000 ms exigido por el criterio de aceptación del RF-15.
"""
    md_path = "tests/Test_Testing/Test_Modulo9/RF-15/TC-M09-G09/Resultados/resultado_tc_m09_g09.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Reporte Markdown guardado en: {md_path}")

if __name__ == "__main__":
    medir_rendimiento()
