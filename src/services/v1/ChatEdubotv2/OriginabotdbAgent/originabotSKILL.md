## Base de datos Originabotdb

A nivel global, esta base de datos pertenece a una **plataforma integral de gestión de proyectos de energía solar** (probablemente fotovoltaica de pequeña/mediana escala — minifarms) operando en **Colombia**. El flujo de negocio es:

**Prospección → Originación de terreno → Term Sheet → Contrato → Proyecto → Construcción (EPC) → Inversión → PPA**

Soportado por una capa transversal de **validaciones dinámicas, monitoreo, integraciones externas** (ClickUp, Discord, GitLab, Odoo, ZapSign, Google Drive, WhatsApp, IA generativa) y procesos administrativos (gobierno, contabilidad, operador de red).

---

## 1. **contabilidad**

Módulo encargado de la **gestión contable y financiera de empleados**, específicamente para el control de gastos, novedades de nómina y solicitudes administrativas internas. Permite registrar perfiles de empleados (con su identificación), gestionar solicitudes de novedades (cambios en nómina, pagos extraordinarios, ajustes salariales) con su estado, tipo, monto mensual y fecha de inicio. Cada solicitud puede tener gastos asociados (`expense`) categorizados por tipo, método de pago, comprobante y centro de costo, con soporte de archivos adjuntos (`expenseattachment`, `novedadattachment`). Incluye tablas de configuración como `expensecategorylimit` (límites de gasto por categoría diferenciados entre capital y municipio) y `gimnasiolimit` (límites para gastos de gimnasio según rol de líder). Se integra con **Odoo** (sistema ERP externo) mediante campos `odoo_id`. Es esencialmente un módulo de **gestión de gastos y novedades de empleados** con flujo de aprobación. 

---

## 2. **contratos**

Módulo de **gestión documental y generación de contratos**, especializado en la creación, firma y administración de contratos legales asociados a proyectos y términos comerciales (term sheets). Maneja una estructura jerárquica de cláusulas mediante `clause` → `clauseparagraph` y plantillas reutilizables (`termsheetclausetemplate`, `termsheetsubclausetemplate`) que se instancian en cláusulas específicas (`termsheetclause`, `termsheetsubclause`) por cada term sheet. La tabla `contract` representa el contrato final, vinculado a un term sheet y opcionalmente a un proyecto, con gestión de firma electrónica vía **ZapSign** (campos `zapsign_response`, `zapsign_signer_token_list`) y soporte de servidumbre. Las tablas `variable` y `variabledescription` permiten un sistema de **variables dinámicas** para reemplazar valores en plantillas (con definición de modelo, atributo, función y tipo de valor), facilitando la generación automática de documentos `.docx`. 

---

## 3. **originacion**

Módulo central y más extenso de la base de datos, encargado del proceso de **originación de terrenos y proyectos de energía** (probablemente solar, dado el contexto). Cubre desde la prospección inicial hasta la firma de contratos de arrendamiento. Sus principales componentes son:

- **Prospección** (`prospecting_*`): gestiona contactos potenciales, mensajes de WhatsApp/Chattigo, agentes de atención al cliente, departamentos geográficos disponibles, validaciones previas de prospectos (con resultados legales) y razones de pérdida. Incluye un sistema de pasos del embudo de ventas y reportes energéticos.
- **Term sheets** (`termsheet_*`): el corazón del módulo. Define las hojas de términos con parámetros económicos (costo anual de arriendo, área, prorrateo, opción de compra, frecuencia de pago, porcentajes iniciales, incrementos), cláusulas e imágenes. Gestiona terrenos (`terrain`) con coordenadas, radiación, linderos, características, dueños del terreno (`landlord`), originadores (vendedores/intermediarios), firmantes, pagos programados, órdenes anuales de compra, anticipos y receptores de pago. Integra firma electrónica con **ZapSign** y tiene un sistema robusto de plantillas DOCX/HTML para generar documentos.
- **Servidumbres** (`easements_*`): registra servidumbres asociadas a terrenos con sus tipos, caracteres, estados de viabilidad (interna/externa), precios, anexos y contactos.
- **Evaluación de tierras** (`land_evaluator_*`): sistema de scoring de terrenos basado en categorías y criterios ponderados (con matriz de comparación AHP), evaluaciones por terreno con campos puntuables. 

---

## 4. **proyectos**

Módulo de **gestión del ciclo de vida de los proyectos**, una vez que un terreno avanza más allá de la term sheet. Su tabla central es `minifarm_project`, que representa cada proyecto solar con datos como ubicación geográfica (lat/lng, ciudad, operador de red), área, capacidad instalada (kWp, DC), descripción de paneles e inversores, etapa actual, integración con **ClickUp** (gestión de tareas) y **Odoo** (analytic account), tipo de contrato, distancias a red y vías. Soporta historial de cambios de etapa (`projectstagechange`), nombres anteriores, archivos del proyecto, precios anuales con razones y vigencias (`projectprice`), poderes notariales (`projectpowerofattorney`) y conceptos de pagos asociados. Incluye un sistema de **viabilidad** (`viability`, `viabilityfile`) con diferentes tipos y estados, comentarios y archivos adjuntos. El submódulo **timeline** gestiona cronogramas de proyecto basados en plantillas (`timelinetemplate`, `activitytemplate`) con actividades, dependencias entre ellas, categorías y duraciones. 

---

## 5. **inversiones**

Módulo de **gestión de inversores, portafolios y proyectos de inversión** (PPAs - Power Purchase Agreements). El concepto `minifarm` representa una unidad de inversión (vinculada 1:1 con un proyecto), con datos financieros como CAPEX, fechas de construcción, primer desembolso, primer avance, prioridad y porcentaje de completitud. Los **inversionistas** (`investment`) registran preferencias como capacidad mínima/máxima, radiación mínima, estructura preferida, tipo de financiación y zonas de interés geográficas. Los **portafolios** (`portfolio`) agrupan minifarms e inversiones, y se vinculan a bancos. Los **PPAs** (`ppa`) representan contratos de venta de energía a largo plazo con offtakers, con suministros anuales (`supplie`). Incluye comentarios sobre minifarms (con tipos de validación), un dataroom estructurado por carpetas con plantillas (`dataroomfolder`, `dataroomfoldertemplate`) ligadas a campos de validación, y filtros configurables. También gestiona líderes especializados (deal, financial, technical) y un sistema de reportes/quejas.

---

## 6. **validaciones**

Módulo **transversal de validación dinámica** que actúa como un motor genérico de campos validables aplicables a terrenos y proyectos. Define plantillas (`template`) compuestas de campos (`templatefield`) con peso (`templatefieldweight`), categorías (`templatecategory`) y subcategorías (`templatesubcategory`). Los campos pueden ser de diferentes tipos, padre/hijo, y tener selectores (`select`) con opciones (`option`) que incluyen colores HSBA, días de expiración y dependencias entre opciones (`optiondependency`). Las instancias concretas de los campos son `field` (asociadas a terrenos o proyectos) con sus subcampos (`subfield`), valores, comentarios, archivos extra y estados. Incluye **campos dinámicos** (`dynamicfield`) y **campos dependientes** (`dependentfield`) que cambian según el valor de otros, además de **acciones automatizadas** (`fieldaction`) que se disparan ante cambios y notifican a interesados. Es fundamentalmente el motor de **checklist y due diligence configurable** del sistema.

---

## 7. **dataroom**

Módulo de **gestión de salas de datos virtuales** integrado con **Google Drive** (campos `google_id`, `web_view_link`). Modela una jerarquía de archivos y carpetas (`file` con relación auto-referencial padre/hijo), proyectos asociados a carpetas (`projectfolder`) con estado de sincronización, e investigadores externos (`investor`) que reciben permisos (`permission`) sobre archivos específicos. El concepto de **due diligence** se gestiona mediante `duediligence` (proceso de revisión), `duediligencefolder` (carpetas asociadas), `duediligencefile` (archivos en la DD), `duediligenceinvestor` (inversionistas con permisos sobre la DD) y `duediligenceproject` (proyectos cubiertos por la DD, con relación M2M a `projectfolder`). Es el módulo encargado de **compartir documentación de proyectos con inversionistas externos** durante procesos de auditoría/inversión.

---

## 8. **epc_ingenieria**

Módulo de **gestión de contratistas EPC** (Engineering, Procurement and Construction) y la documentación de ingeniería para los proyectos. Los EPCs (`epc`) son empresas contratistas con datos básicos (NIT, dirección, logo). Tienen asignados (`epcasignee`) que son las personas responsables y usuarios del sistema (`epcuser`). Cada proyecto puede tener uno o varios EPCs asignados (`projectepc`) con porcentaje de avance de construcción. Maneja un sistema de **plantillas de campos** (`epctemplatefield`, `epcsubfieldtemplate`, `epcfoldertemplate`) que se instancian en campos concretos por proyecto (`epcfield`, `epcsubfield`, `epcfolder`) con estados, fechas y orden. Soporta archivos de proyecto (`epcprojectfile`), reportes (`epcprojectreport`) y un historial de cambios de estado (`statuschangesubfield`). El submódulo **engineering** gestiona específicamente documentos solicitados por **operadores de red** (`gridoperatordocument`) con sus formatos predefinidos (`gridoperatordocumentformat`).

---

## 9. **operador_red**

Módulo especializado en la **gestión de solicitudes a operadores de red eléctrica** (empresas distribuidoras), proceso clave para la conexión de proyectos solares al sistema interconectado. Gestiona el catálogo de operadores (`gridoperator`), sus subestaciones (`substation`) con capacidades a 138kV/345kV y demandas horarias, circuitos (`circuit`) con sus niveles de tensión y demandas, transformadores (`transformer`), y la jerarquía territorial específica (`department`, `municipality`, `locality`, `neighborhood`). La tabla central `gridoperatorrequest` representa cada solicitud con su estado, ubicación, datos del cliente, capacidad solicitada (kVA, kWp), formularios JSON, código de verificación e integración con **ClickUp**. Incluye **solicitudes previas** (`previousrequest`) para histórico, archivos adjuntos, notificaciones por correo (`requestnotification`) con replicación en Discord, y miembros del equipo de originación (`originationteammember`) con sus IDs en ClickUp y Discord.

---

## 10. **gobierno**

Módulo de **gestión de solicitudes a entidades gubernamentales** (alcaldías, ministerios, autoridades ambientales, etc.). Define las entidades (`entities`) con su nomenclatura, tipo de solicitud (correo o página web), formato, plantilla de mensaje y tiempo de respuesta esperado, asignándoles un encargado (originador). Las solicitudes se dividen en **solicitudes por correo** (`requests_email`) con asunto, cuerpo, documentos y shape adjuntos, y **solicitudes por página web** (`requests_page`) con datos en JSON. Ambos tipos pueden tener una respuesta asociada (`request_responses`) con documento, número de radicado, resolución y comentarios. Es el módulo que automatiza la **comunicación oficial con entidades públicas** durante el ciclo del proyecto.

---

## 11. **monitoreo**

Módulo de **monitoreo, alertas y gestión de tareas técnicas** integrado con servicios externos (Discord, ClickUp, GitLab). La tabla `task` registra tareas con tipos, estados (working_on, in_review, ready_for_review, ready_for_deployment, solved), fechas de transición, mensaje de Discord asociado, e issue de GitLab. `fieldwatcheraction` configura **observadores de campos**: cuando un campo de cualquier modelo (vinculado por `content_type`) cambia, dispara una acción configurable con argumentos JSON, notifica vía webhook de Discord y avisa a interesados específicos (identidades). `eventtype` define los tipos de eventos (creación, modificación, etc.). Es esencialmente el **sistema de notificaciones reactivas y gestión de issues técnicos** del equipo de desarrollo.

---

## 12. **visitas_campo**

Módulo de **gestión de visitas de campo a terrenos**, fundamental para la verificación física antes de avanzar con proyectos. La tabla `visit` representa cada visita con visitante, terreno, fecha, atendido por (landlord o tercero), estado y observaciones. Los **visitantes** (`visitor`) son usuarios del sistema con datos de contacto. Incluye múltiples tipos de visita (`visittype` con icono y color), reportes específicos como **reportes forestales** (`forestalreport`) que registran árboles individuales con especie (`treespecies`), altura, diámetro de copa, estado fitosanitario, y mediciones de circunferencia a la altura del pecho (`circunferenceatchestheight`); **reportes generales** (`visitreport`) con tipos como ríos, accesos, construcciones, prioridad y tipo de agua; **polígonos trazados** (`polygontrack`) de áreas específicas; **notas** (`note`) y archivos adjuntos. Soporta sincronización offline mediante el campo `lid` (UUID local). Es la base de datos para la **app móvil de visitas de campo**.

---

## 13. **autenticacion_usuarios**

Módulo de **autenticación, autorización y gestión de identidades** basado en el sistema estándar de Django (`auth_user`, `auth_group`, `auth_permission` y sus tablas de relación M2M), complementado con tablas propias. La tabla `identity` extiende al usuario con identificadores externos (Discord, ClickUp, GitLab, sistema Auth) y rol del sistema. La tabla `profile` agrega datos adicionales como teléfono. Incluye `django_session` para sesiones activas, `django_admin_log` para auditoría del admin de Django, `django_content_type` que registra todos los modelos del sistema, y `admin_interface_theme` con la configuración visual del panel de administración (colores, logos, comportamiento). Es el **núcleo de gestión de usuarios y sus credenciales en sistemas externos**.

---

## 14. **tareas_programadas**

Módulo de **infraestructura para tareas asíncronas y programadas** basado en **Celery Beat** (scheduler) y **Celery Results** (backend de resultados). Las tablas `clockedschedule`, `crontabschedule`, `intervalschedule` y `solarschedule` definen diferentes formas de programar tareas (puntual, cron, intervalo, basado en eventos solares). `periodictask` es la tarea programada con su nombre, función Celery a ejecutar, argumentos, queue, prioridad, contador de ejecuciones y fecha de última corrida. `taskresult` almacena el resultado de cada ejecución con estado, traceback, tiempo y metadatos. `groupresult` y `chordcounter` manejan tareas en grupo. Es la **infraestructura de jobs en background** del sistema, no contiene lógica de negocio.

---

## 15. **auditoria_logs**

Módulo de **auditoría y observabilidad del sistema**. Combina varias herramientas: 

- **django_tracker_auditlog**: registra cambios sobre modelos específicos con el objeto modificado, acción, nivel, cambios en JSON, usuario, email y metadatos.
- **easyaudit**: librería de auditoría con `crudevent` (eventos CRUD con representación JSON del objeto), `loginevent` (intentos de login con IP) y `requestevent` (registro de peticiones HTTP).
- **logging_manager_log**: logs de aplicación con tipo, método, traceback, errores, tiempo de ejecución, datos de la petición y usuario.
- **silk**: profiling de performance con `silk_request` (peticiones HTTP detalladas con tiempos), `silk_response`, `silk_sqlquery` (queries SQL ejecutadas con análisis y tiempos) y `silk_profile` (perfilado de funciones específicas).

Permite **trazabilidad completa, debugging y análisis de performance** del sistema en producción.

---

## 16. **geografico**

Módulo de **datos geográficos y territoriales**. Contiene dos sistemas paralelos:

- **cities_light_***: sistema legacy basado en la librería `django-cities-light` con datos de GeoNames (países, regiones, subregiones, ciudades).
- **territorial_***: sistema actual y enriquecido con jerarquía completa: país → región (departamento) → subregión (municipio) → ciudad → localidad → barrio. Incluye códigos DIAN (Colombia), códigos de operador de red (`or_code`), códigos UV y datos GeoNames. Las tablas `or_*` (orregion, orsubregion, orlocality, orneighborhood) mapean cada nivel territorial a operadores de red específicos, esencial para el negocio.
- **victimizationriskindex**: índice de riesgo de victimización (IRV) por municipio, con score, año, cluster, código PDET (Programas de Desarrollo con Enfoque Territorial). Indica que el sistema opera en **Colombia** y considera variables de seguridad para evaluación de proyectos.

---

## 17. **whatsapp**

Módulo de **integración con WhatsApp Business API** para mensajería automatizada con propietarios, contactos y receptores de pago. `whatsappmessage` registra cada mensaje enviado/recibido con timestamp, texto, tipo, números de origen y destino, plantilla utilizada, mensaje crudo (raw_message en JSON), errores y un identificador de WhatsApp (wa_id). `whatsappdocument` almacena documentos enviados/recibidos con MIME type, hash SHA256 y URL. Es la **bitácora del bot de WhatsApp** del sistema.

---

## 18. **filtros**

Módulo de **definición de filtros configurables** para búsquedas dinámicas en las vistas de minifarms, proyectos y terrenos. Cada tabla (`minifarmfilter`, `projectfilter`, `terrainfilter`) define filtros con nombre, parámetro de URL, descripción, modelo base, atributo del modelo principal o atributo del campo de validación asociado (cuando el filtro se basa en `validation_templatefield`). Permite construir filtros dinámicos sin necesidad de hardcodear cada uno en el código backend.

---

## 19. **reportes**

Módulo simple de **generación y almacenamiento de reportes**. La tabla `report` registra reportes generados por usuarios (identidades) con un archivo de gráfico, archivo de datos, nombre y timestamps. Probablemente se utiliza para reportes ad-hoc o programados que el usuario puede consultar después.

---

## 20. **proxied_links**

Módulo utilitario de **acortamiento y proxy de URLs**. La tabla `proxiedlink` mapea una URL original a una URL proxy con UUID. Útil para enmascarar URLs reales en mensajes de WhatsApp/correos, hacer tracking de clics, o generar enlaces públicos seguros.

---

## 21. **jwt_config**

Módulo de **gestión de tokens JWT para integración con servicios externos**. La tabla `jwttoken` almacena tokens de acceso y refresh, tipo de servicio, ID único y fecha de expiración. Centraliza la autenticación con APIs de terceros (probablemente ClickUp, ZapSign, Odoo, etc.) sin hardcodear credenciales.

---

## 22. **genai**

Módulo de **gestión de modelos de IA generativa** (probablemente Gemini, dadas las siglas RPM/TPM/RPD). Permite registrar modelos disponibles (`genaimodel`) con sus límites (RPM = requests per minute, TPM = tokens per minute, RPD = requests per day), API keys (`apikey`) que pueden estar asociadas a múltiples modelos (M2M), y un registro de uso (`apikeyuse`) con conteo de tokens consumidos y propósito. Habilita un sistema de **rotación de claves y balanceo de carga** para no exceder límites de los proveedores de IA.

---

## 23. **legal_validation**

Módulo de **validación legal automatizada** utilizado en el proceso de prospección. `legalvalidationsetting` almacena configuraciones (key-value tipadas) que rigen las reglas de validación. `especificacionkeyword` contiene palabras clave que se buscan en documentos legales (probablemente certificados de tradición y libertad - CTL) para detectar especificaciones, restricciones o cláusulas que afecten la viabilidad del terreno. Funciona junto con `prospecting_pre_validation.legal_validation_result`.

---

## 24. **migraciones**

Módulo del sistema interno de Django (`django_migrations`) que registra el historial de migraciones aplicadas a la base de datos: aplicación, nombre del archivo de migración y timestamp. **No tiene lógica de negocio**, es exclusivamente infraestructura de Django para mantener el esquema versionado.

