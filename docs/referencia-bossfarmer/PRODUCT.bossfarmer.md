# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three confirmed audiences, in priority order:

- **Revendedores / mayoristas** — compran volumen para revender a sus propios clientes. Les importa
  el precio por unidad, el caudal disponible, la velocidad de entrega y la fiabilidad.
- **Consumidor final** — el propio artista o quien promociona su música. Le importa el precio, que el
  proceso sea fácil y que el sitio dé confianza.
- **Afiliados / partners** — refieren clientes y cobran comisión. Necesitan entender el modelo de referidos.

El bot de Telegram y su economía de créditos se retiraron: los clientes se autogestionan en el panel web
(`app.<dominio>`). Telegram queda solo como canal de contacto para cerrar compras.

## Product Purpose

BossFarmer **crea cuentas de Spotify de forma automatizada y a escala**. El cliente pide un lote en su
panel y la flota de workers lo produce: cuentas gratis, Trial o Premium (con pago automático de tarjeta y
reintento con tarjetas de repuesto), con proxies propios del cliente o del sistema, y progreso en vivo
cuenta por cuenta. Se cobra por suscripción con cupo mensual **separado por tipo** (gratis/Trial/Premium),
que se descuenta al **entregar** las cuentas (o al cerrar el lote), no al pedirlas. La landing es la
superficie pública del negocio; el panel de clientes es donde se trabaja.

Éxito de la web: un visitante que llega frío entiende en segundos qué se entrega, a qué caudal y
por qué es fiable, y puede pedir un plan.

## Positioning

Lo que un competidor no podría copiar honestamente:

- **Automatización propia a escala** — flota de workers propia (Selenium sobre cola Redis) corriendo en
  paralelo sin intervención manual. El caudal continuo es el mecanismo, no un proceso manual disfrazado.
- **Caudal y entrega garantizados** — no hay esperas de días: el sistema produce bajo demanda.
- **Autoservicio 24/7** — con la suscripción activa, el cliente pide lotes y los descarga sin hablar con nadie.

## Operating Context

- Venta: el visitante arma su plan en la web (plan + quién pone los proxies) y, para pedirlo, crea su
  cuenta en el panel; la orden queda a su nombre y la conversación sigue por Telegram. Un admin la
  activa desde la bandeja de órdenes. Hasta entonces el panel está bloqueado (no se crean lotes).
- Los proxies de BossFarmer son un extra: sin él, los lotes exigen proxies propios (lo impone la API).
- Producción: cola de trabajos en Redis Streams; workers Selenium ejecutan los lotes; PostgreSQL persiste cuentas, lotes, suscripciones y usuarios.
- Entrega: el correo y la contraseña solo se muestran al final (lote liquidado); mientras trabaja, el
  cliente ve «Cuenta N», estado y paso. Luego descarga las cuentas entregadas del lote (CSV/TXT) desde su panel.
- Panel de administración y API en FastAPI; panel de clientes en Next.js.
- Futuro anunciado: una tienda en la web. Aún sin definir qué vende.

## Capabilities and Constraints

Confirmado y operativo:

- Creación automatizada de cuentas de Spotify en lote, sin intervención manual.
- Tres tipos de cuenta: gratis, Trial y Premium, con pago automático y tarjetas de repuesto.
- Proxies propios del cliente (varios formatos) o del sistema, verificados antes de usarse.
- Progreso en vivo de cada cuenta en el panel del cliente.
- Suscripción con cupo mensual **por tipo de cuenta** (gratis/Trial/Premium), editable en el admin
  (grupo «Cupos por plan» en Configuración). Arranca igual en los tres tipos (fuente:
  `packages/shared/suscripciones.py` + `packages/shared/ajustes.py`): Básico 50 de cada por 24.99 US$,
  Estándar 500 de cada por 74.99 US$, Pro 1,200 de cada por 149.99 US$, Mayorista ilimitado por
  389.99 US$ (terminados en .99 a propósito). El cupo se **reserva** al pedir el lote y se **cobra al
  entregar** por el tipo real de cada cuenta (una Premium que se quedó en Trial se cobra al cupo Trial);
  lo que falla, se detiene o se cancela no descuenta. Punto decimal y coma de miles en toda la web y el
  panel. Proxies de BossFarmer como extra: 0.10 US$ por cuenta + 5 US$ (Básico +10, Estándar +55,
  Pro +125); el Mayorista, 150 US$ fijos al mes.
- Condición de uso (se muestra discreta al pedir y al crear lotes): el bot crea las cuentas;
  que una cuenta se caiga después depende de las tarjetas que el cliente use para crearla.
- Cola de trabajos asíncrona con workers escalables horizontalmente.
- Cuentas en paralelo por plan (Básico 1, Estándar 5, Pro 15, Mayorista 20), comunidad (chat de
  clientes) y soporte por tickets dentro del panel, en todos los planes.
- Desarrollos y automatizaciones a medida, por encargo: el cliente cuenta su proceso por Telegram
  y recibe propuesta y precio antes de empezar. Sin plazos ni precios publicados.

Constraints duros:

- Toda la interfaz pública se escribe **en español**. No inglés.
- Stack web: Next.js (App Router, TypeScript, Tailwind), salida `standalone` para Docker.
- Despliegue vía Docker Compose en Dokploy; ramas `main` (prod), `staging` (QA), `develop` (integración).

Explícitamente sin decidir:

- Qué venderá la tienda.
- Mecánica y porcentajes del programa de afiliados.

## Brand Commitments

- Nombre: **BossFarmer**.
- Paleta principal vinculante: **verde #1DB954 sobre fondo oscuro**. Otros colores solo como complemento.
- Idioma: español.
- No hay logo definitivo; hoy se usa la marca tipográfica ("BF" / "BossFarmer").

## Evidence on Hand

- Código de producción real del sistema de automatización en `apps/worker/`, `apps/api/`, `apps/panel/`, `packages/shared/`.
- Despliegue de staging activo en `testbossfarmer.fprtechnology.com`.

Ausencias que el trabajo futuro **no debe inventar**:

- No hay testimonios, reseñas ni casos de éxito.
- No hay métricas públicas (cuentas entregadas, uptime, clientes, tiempos medios).
- No hay logos de clientes ni menciones de prensa.
- No hay capturas del producto ni assets de imagen propios.

## Product Principles

1. **El caudal es el argumento.** Lo diferencial es la máquina corriendo en paralelo, no la lista de features. Cualquier superficie debe comunicar caudal y continuidad antes que nada.
2. **Confianza sin pruebas prestadas.** Sin testimonios ni métricas reales disponibles, la credibilidad se gana con precisión, claridad y calidad de ejecución — nunca con cifras o social proof inventados.
3. **Tres públicos, una puerta.** Revendedor, consumidor final y afiliado llegan al mismo sitio con intenciones distintas; la estructura debe dejar que cada uno se identifique rápido sin fragmentar el mensaje.
4. **Autoservicio como promesa.** Contratar pasa por una persona (orden + Telegram); una vez activo, todo lo demás es autoservicio.
5. **Español, siempre.** El tono es directo y operativo, sin jerga de marketing traducida.
