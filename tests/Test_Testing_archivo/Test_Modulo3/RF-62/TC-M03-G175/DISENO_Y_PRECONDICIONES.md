# TC-M03-G175: BOLA / IDOR Broken Object Level Authorization (RF-62 / OWASP API1:2023)

## 1. Alcance y Objetivos
Evaluar el aislamiento multi-tenant y la protección frente a accesos no autorizados a objetos específicos (BOLA/IDOR) sobre los endpoints de consulta de calidad:
- `GET /iot/calidad/{id_telemetria}`
- `GET /iot/calidad?id_sensor={id_sensor}`

## 2. Herramienta y Enfoque QA
- **Herramienta:** Newman / Postman v2.1.0 con reporte oficial en `resultados/resultado_TC-M03-G175.html` (scanner).
- **CERO DML:** Todo el setup de tenants y telemetría de prueba se realiza por API REST (`POST /iot/telemetria` y `POST /iot/calidad/{id}/evaluar`).
- **Aislamiento Sandbox:** Transaccional con headers obligatorios `X-Test-Run-Id`, `X-Sandbox-Secret` y rollback vía `DELETE /test-control/runs/{{run_id}}`.

## 3. Precondición de Tenants y Subcasos Evaluados
- **Tenant A:** Usuario Productor (`m2m.nuevo@ejemplo.com`).
- **Tenant B:** Usuario Ingeniero de Campo (`gestor.granja.test@pecuaria.co`).
- **Subcasos TC-M03-334:**
  - **(a) Acceso directo a lectura de Tenant B por Tenant A:** Se consulta `GET /iot/calidad/{id_tel_finca_b}` con credenciales de Tenant A.
  - **(b) Filtrado por sensor de Tenant B:** Se consulta `GET /iot/calidad?id_sensor={id_sensor_finca_b}` con credenciales de Tenant A.
  - **(c) Enumeración secuencial de IDs:** Barrido secuencial de IDs numéricos para verificar si la API expone 403, 404 o si no filtra entre fincas.
  - **Hallazgo de Arquitectura:** En el backend actual, `calidad_router.py` aplica control RBAC (recurso 38, acción 2) pero no inyecta el `AlcanceFincaAdapter` en `consultar_calidad_use_case.py`. Esto provoca que cualquier usuario con permiso 38.2 pueda acceder a registros de calidad de otras fincas si conoce el `id_telemetria`. Se documenta como hallazgo de seguridad BOLA.
