# INC-M03-120-G63 — Canal seguro M03 → M04 (TC-M03-125)

**RF:** RF-56, Fase 6 ("El paquete se transmite al servicio de inferencia mediante canal seguro") y RNF
de seguridad ("Envío mediante canales cifrados (TLS/SSL)"). **Issue:** #666.
**Estado:** el canal (cliente de transporte con TLS) está **implementado y verificado** con pruebas aisladas.
La integración con M04 sigue **bloqueada** por el contrato IA-1 (ver INC-M03-115-G58, #658).

## Respuestas a QA

| Pregunta | Respuesta |
|---|---|
| ¿Cuál es el cliente de transporte hacia M04? ¿Existe en otro componente? | No existía en ningún lado: ni en el backend, ni en el broker, ni en M04. El único adaptador era `MotorInferenciaStubAdapter`, y M04 (`src/prediction`) no tiene un receptor de paquetes. Ahora existe `MotorInferenciaHttpAdapter` (httpx + `ssl`) |
| ¿TLS mínimo y certificados? | **TLS 1.3**, alineado con los RNF de M03 (monitoreo RF-57, heartbeat y bitácora RF-63: "TLS 1.3") y con M05→M06. Se puede bajar a **1.2** si M04 no soporta 1.3 (el RNF-02 de M04 pide "TLS 1.2 o superior"), pero **nunca por debajo de 1.2**. El certificado del servidor se verifica siempre (cadena y nombre) contra las CA del sistema o la CA de `IOT_INFERENCIA_CA_FILE` |
| ¿Se mantiene el stub? | Sí, como respaldo: sin `IOT_INFERENCIA_M04_URL` (o con una configuración insegura) el router sigue con el stub, y los paquetes quedan pendientes (`MOTOR_INFERENCIA_NO_INTEGRADO`). El stub también se sigue usando en las pruebas unitarias |

> **Nota sobre la decisión de versión:** los requerimientos no coinciden. RF-56 dice "TLS/SSL" sin
> versión; otros RNF de M03 dicen TLS 1.3; el RNF-02 de M04 dice "1.2 o superior". Se eligió 1.3 como
> mínimo por defecto. Esto se puede cambiar con `IOT_INFERENCIA_TLS_MIN` y conviene confirmarlo con
> análisis cuando se defina IA-1.

## Qué hace el cliente (`src/telemetry/infrastructure/adapters/motor_inferencia_http_adapter.py`)

- **HTTP plano:** una URL `http://` se rechaza al construir el cliente (`CANAL_INFERENCIA_INSEGURO`),
  sin generar tráfico. Si detrás de una URL `https://` hay un servidor sin TLS, el handshake falla.
- **TLS obsoleto:** con `ssl.SSLContext.minimum_version` en 1.3, un servidor que solo ofrece 1.0, 1.1 o
  1.2 no completa el handshake. Un mínimo menor que 1.2, o un contexto que no verifica el
  certificado, se rechazan en la configuración.
- **Certificado:** `ssl.create_default_context`: `CERT_REQUIRED` y verificación del nombre del host.
- **Redirecciones:** no las sigue, para que un 3xx no lleve a `http://`. Un 3xx cuenta como intento fallido.
- **Errores:** si el canal no se establece, lanza `CANAL_INFERENCIA_NO_DISPONIBLE` (503), con el
  motivo SSL en el mensaje y en el log. El caso de uso lo registra como
  `MOTOR_INFERENCIA_NO_DISPONIBLE` y el paquete queda `FALLIDO`. Una respuesta no 2xx devuelve `False`.
- **Entorno (`.env.example`):** `IOT_INFERENCIA_M04_URL`, `IOT_INFERENCIA_M04_TOKEN`,
  `IOT_INFERENCIA_TLS_MIN=1.3` e `IOT_INFERENCIA_CA_FILE`. Usa `trust_env=False`, así que ni los proxies
  ni `SSL_CERT_FILE` del entorno cambian el canal.
- **Lotes:** implementa también `enviar_lote`. El método abstracto lo agrega INC-M03-112-G55 (#655),
  y de esta forma el cliente sigue siendo válido cuando ese PR entre.

### Provisional hasta IA-1

El cuerpo (`{"paquetes": [...]}`, con los campos de `PaqueteInferencia`), el `Bearer` y la regla
"2xx = confirmado" son **provisionales**: M04 no ha definido el endpoint, el esquema, el ACK ni la
autenticación (G58). Cuando se definan, se ajusta `_enviar`; el canal TLS no cambia. Con G56 (#656),
un rechazo explícito de M04 debería mapearse a `MotorInferenciaRechazoError` (E5).

## Evidencia: pruebas aisladas

`tests/telemetry/test_inc_m03_120_g63_canal_seguro_m04.py`: usa el **cliente real** contra servidores
HTTP o TLS levantados en la prueba, que escuchan **solo en `127.0.0.1`**. Los certificados se generan en
la prueba (una CA de prueba, un certificado con otro nombre y una CA no confiable). No se usa DEV/TEST y
no hay tráfico hacia sistemas compartidos.

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_tls13_con_certificado_de_la_ca_configurada_es_aceptado` | Configuración aprobada | `True`; el servidor negocia `TLSv1.3` y recibe el `Bearer` y el paquete |
| `test_lote_viaja_en_una_sola_solicitud` | `enviar_lote` con 2 paquetes, host `localhost` | 1 solicitud con los 2 paquetes |
| `test_url_http_plana_se_rechaza_sin_generar_trafico` | URL `http://` | `CANAL_INFERENCIA_INSEGURO`; el servidor no recibe nada |
| `test_servidor_sin_tls_detras_de_url_https_se_rechaza` | Servidor en claro | `SSL: WRONG_VERSION_NUMBER`; nada recibido |
| `test_redireccion_hacia_http_no_se_sigue` | 307 hacia `http://` | `False`; el servidor HTTP no recibe nada |
| `test_servidor_con_tls_anterior_al_minimo_se_rechaza[TLSv1.0/1.1/1.2]` | TLS obsoleto | `TLSV1_ALERT_PROTOCOL_VERSION`; nada recibido |
| `test_control_el_rechazo_de_tls12_lo_causa_el_minimo_del_cliente` | El mismo servidor 1.2, con mínimo 1.2 | Aceptado (`TLSv1.2`): el rechazo anterior lo causa el mínimo del cliente |
| `test_minimo_tls_no_admitido_se_rechaza[1.0/1.1/vacío/TLSv1.3]` | Mínimo inválido | `CANAL_INFERENCIA_INSEGURO` |
| `test_contexto_que_admite_tls_obsoleto_o_no_verifica_se_rechaza` | Contexto TLS 1.1 o `CERT_NONE` | `CANAL_INFERENCIA_INSEGURO` |
| `test_certificado_no_confiable_o_con_otro_nombre_se_rechaza[...]` | CA ajena o nombre distinto | `CERTIFICATE_VERIFY_FAILED` (`unable to get local issuer` o `IP address mismatch`) |
| `test_respuesta_no_exitosa_de_m04_es_intento_fallido` | HTTP 503 | `False` |
| `test_sin_url_de_m04_se_sigue_con_el_stub` | Sin URL | `None`: el router usa el stub |
| `test_configuracion_insegura_no_se_usa[http_plano/tls_obsoleto]` | Entorno inseguro | `None` + log CRITICAL; no se envía por un canal inseguro |
| `test_configuracion_segura_por_entorno_envia_por_tls13` | Configuración completa por entorno | Envía por `TLSv1.3` |

### Ejecución (2026-10-27)

Se ejecutó en un contenedor desechable con la imagen del backend (`sgpmp-backend-backend`, Python 3.13,
OpenSSL 3.5.6) y `--network none`, sin acceso a ninguna red externa:

```
docker run --rm --network none -v <repo>:/repo:ro -w /repo --entrypoint python sgpmp-backend-backend \
  -m pytest tests/telemetry/test_inc_m03_120_g63_canal_seguro_m04.py -v
21 passed in 8.92s
```

Control con las pruebas del router que reemplazan el stub (DEV-17, G42 y DEV-49): **68 passed**.

### Advertencia: antivirus con inspección TLS

En una máquina Windows con **Avast Web Shield**, el antivirus intercepta el TLS **incluso en
`127.0.0.1`** y vuelve a firmar el certificado con "Avast Web/Mail Shield Untrusted Root". Así, el
cliente no habla con el servidor de prueba, y los resultados no sirven como evidencia (ni los
aceptados ni los rechazados). Para estos casos, el fixture `canal_directo` compara el certificado
servido con el esperado y, si difieren, **omite** las pruebas de canal con el motivo explícito. Las
de configuración se ejecutan igual. La evidencia debe tomarse en un entorno sin inspección TLS, como el
contenedor de arriba o el CI.

## Para QA

- **TC-M03-125:** usar la prueba de arriba en lugar de `test_tc_m03_125_canal_hacia_m04[...]` (que
  quedaba `SKIPPED` contra el stub). Ejecutarla en un entorno sin inspección TLS.
- La validación **de extremo a extremo con M04** (su certificado real y su endpoint) queda pendiente de
  IA-1 (G58).
