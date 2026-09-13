# Meta App Review — desbloquear DMs de Instagram (instagram_manage_messages)

Los comentarios funcionan con acceso estándar. Los **DMs de Instagram** exigen
**Acceso Avanzado** a `instagram_manage_messages`, que Meta solo otorga tras App Review
+ verificación de negocio. Este es el pack para enviarlo.

## Checklist previo
- [ ] App "Epic.Plane Publisher" en modo **Live** (no Development).
- [ ] **Verificación de negocio** completada en Meta Business (documentos de la empresa
      de la agencia: RUT/inicio de actividades, nombre legal, sitio/dominio).
- [ ] **Política de privacidad** publicada en una URL pública (texto base abajo).
- [ ] Ícono de la app + categoría + email de contacto configurados.
- [ ] Producto **Instagram** con la función de mensajería agregada en el App Dashboard.
- [ ] En la app de IG: **"Permitir acceso a los mensajes"** activado.

## Permiso a solicitar
`instagram_manage_messages` — con "Advanced Access".
(Opcional para Messenger de FB: `pages_messaging`.)

## Descripción de uso (pegar en el formulario de review)
> Nuestra herramienta de gestión de redes ("Al Día") permite a la marca responder los
> mensajes directos de sus clientes de forma más rápida. Con `instagram_manage_messages`
> leemos los DMs entrantes recientes para: (1) enviar un acuse de recibo inmediato y
> cortés en nombre de la marca, (2) derivar las consultas de compra al canal de atención
> oficial (WhatsApp), y (3) poner el resto en una cola para que una persona del equipo
> responda. No enviamos mensajes masivos ni promocionales no solicitados; solo
> respondemos dentro de la ventana de 24 horas a usuarios que escribieron primero.

## Guion del screencast (Meta exige video del flujo)
1. Login en la herramienta con una cuenta de IG de negocio de prueba.
2. Mostrar un DM entrante de un usuario.
3. Mostrar cómo la herramienta envía el acuse + deriva a WhatsApp.
4. Mostrar la cola donde un humano ve el DM para responder.
5. Mostrar dónde el usuario puede optar por no recibir (o cómo se respeta la ventana 24h).

## Política de privacidad — texto base (publicar en una URL)
> **Política de privacidad — Al Día**
> Al Día ofrece gestión de redes sociales para marcas. Accedemos a datos de las cuentas
> de Instagram/Facebook que las marcas nos autorizan (publicaciones, comentarios,
> mensajes y métricas) con el único fin de crear, publicar y gestionar su contenido y su
> atención al público. No vendemos datos a terceros. Almacenamos solo lo necesario para
> operar el servicio y lo eliminamos a solicitud de la marca. Contacto:
> felipecood@gmail.com. Cumplimos las Políticas de Plataforma de Meta.

## Después de la aprobación
`python3 dms.py --check` debería leer DMs, y `python3 dms.py --post` enviar los acuses.
El código (`dms.py`) ya está construido y a la espera de este acceso.
