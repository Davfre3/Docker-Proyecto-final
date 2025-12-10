# 🐳 Guía de Uso - Docker SLA Predictor

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

- ✅ **Docker Desktop** para Windows ([Descargar aquí](https://www.docker.com/products/docker-desktop))
- ✅ **SQL Server** corriendo localmente
- ✅ Base de datos `Proyecto1SLA_DB` creada con datos

---

## 🚀 Instalación y Configuración (Primera vez)

### Paso 1: Configurar Usuario SQL Server

El contenedor Docker **NO puede usar autenticación de Windows**. Necesitas crear un usuario SQL Server.

**Opción A: Usando SQL Server Management Studio (SSMS)**

1. Abre **SSMS** y conéctate a tu servidor (ejemplo: `TuPC\MSSQLSERVER1`)
2. Abre el archivo `create_sql_user.sql` que está en esta carpeta
3. Presiona **F5** para ejecutar el script completo
4. Verás mensajes confirmando la creación del usuario

**Opción B: Usando PowerShell**

```powershell
# Desde la carpeta del proyecto, ejecuta:
sqlcmd -S "TuPC\MSSQLSERVER1" -E -i "create_sql_user.sql"
```

> **Nota:** Reemplaza `TuPC\MSSQLSERVER1` con el nombre de TU servidor SQL Server.

---

### Paso 2: Habilitar Autenticación Mixta en SQL Server

1. En **SSMS**, clic derecho en el servidor → **Propiedades**
2. Ve a **Seguridad** (en el menú izquierdo)
3. Selecciona: **"Modo de autenticación de SQL Server y Windows"**
4. Clic en **Aceptar**
5. **IMPORTANTE:** Reinicia el servicio de SQL Server:
   - Abre "Servicios" de Windows
   - Busca "SQL Server (MSSQLSERVER1)" o similar
   - Clic derecho → **Reiniciar**

---

### Paso 3: Actualizar Configuración del Proyecto

Abre el archivo `app/config.py` y actualiza la línea del servidor SQL con **TU nombre de PC**:

```python
database_server: str = "host.docker.internal\\TU_SERVIDOR_SQL"
```

**Ejemplo:**
```python
# Si tu servidor es: LAPTOP-ABC\MSSQLSERVER1
database_server: str = "host.docker.internal\\LAPTOP-ABC\\MSSQLSERVER1"

# Si tu servidor es: localhost\SQLEXPRESS
database_server: str = "host.docker.internal\\SQLEXPRESS"
```

---

## 🏃 Uso Diario del Contenedor

### Construir la Imagen Docker

**Solo necesitas hacer esto la primera vez o cuando cambies el código:**

```powershell
# Desde la carpeta del proyecto
docker build -t sla-predictor:latest .
```

⏱️ Tiempo estimado: 2-5 minutos

---

### Iniciar el Contenedor

```powershell
docker run -d --name sla-predictor -p 8000:8000 sla-predictor:latest
```

**Explicación:**
- `-d` = Corre en segundo plano
- `--name sla-predictor` = Nombre del contenedor
- `-p 8000:8000` = Puerto accesible en `http://localhost:8000`

---

### Verificar que Funciona

```powershell
# Ver si está corriendo
docker ps

# Ver logs en tiempo real
docker logs -f sla-predictor

# Probar el endpoint de salud
Invoke-RestMethod -Uri http://localhost:8000/health
```

**Salida esperada en los logs:**
```
✅ Modelo cargado exitosamente
Obtenidos XXX registros para entrenamiento
Modelo entrenado - Accuracy: XX.XX%
Uvicorn running on http://0.0.0.0:8000
```

---

### Detener el Contenedor

```powershell
docker stop sla-predictor
```

---

### Reiniciar el Contenedor

```powershell
docker restart sla-predictor
```

---

### Eliminar el Contenedor

```powershell
# Detener y eliminar
docker stop sla-predictor
docker rm sla-predictor
```

---

## 🔄 Flujo Completo de Trabajo

### Escenario 1: Primera vez usando Docker

```powershell
# 1. Crear usuario SQL (solo una vez)
sqlcmd -S "TuPC\MSSQLSERVER1" -E -i "create_sql_user.sql"

# 2. Construir imagen
docker build -t sla-predictor:latest .

# 3. Levantar contenedor
docker run -d --name sla-predictor -p 8000:8000 sla-predictor:latest

# 4. Verificar logs
docker logs sla-predictor
```

---

### Escenario 2: Reiniciar después de apagar la PC

```powershell
# El contenedor ya existe, solo iniciarlo
docker start sla-predictor

# Verificar que funciona
docker logs -f sla-predictor
```

---

### Escenario 3: Actualizar código de la aplicación

```powershell
# 1. Detener y eliminar contenedor actual
docker stop sla-predictor
docker rm sla-predictor

# 2. Reconstruir imagen con cambios
docker build -t sla-predictor:latest .

# 3. Levantar nuevo contenedor
docker run -d --name sla-predictor -p 8000:8000 sla-predictor:latest
```

---

### Escenario 4: Actualizar datos en la BD

```powershell
# 1. Forzar reentrenamiento del modelo
docker exec sla-predictor rm -f /app/models/sla_model.pkl

# 2. Reiniciar contenedor
docker restart sla-predictor

# 3. Ver el proceso de entrenamiento
docker logs -f sla-predictor
```

> Verás: "Obtenidos XXX registros para entrenamiento"

---

## 🛠️ Solución de Problemas

### ❌ Error: "Login failed for user 'sla_user'"

**Causa:** No ejecutaste el script SQL o la autenticación mixta no está habilitada.

**Solución:**
1. Ejecuta `create_sql_user.sql` en SSMS
2. Verifica autenticación mixta en propiedades del servidor
3. Reinicia SQL Server

---

### ❌ Error: "Cannot open database 'Proyecto1SLA_DB'"

**Causa:** La base de datos fue eliminada o el usuario no tiene permisos.

**Solución:**
1. Verifica que existe la base de datos `Proyecto1SLA_DB`
2. Vuelve a ejecutar `create_sql_user.sql`
3. Reinicia el contenedor: `docker restart sla-predictor`

---

### ❌ Error: "Port 8000 already in use"

**Causa:** Ya hay un contenedor usando el puerto 8000.

**Solución:**
```powershell
# Ver qué está usando el puerto
docker ps

# Detener contenedor anterior
docker stop sla-predictor

# O usar otro puerto
docker run -d --name sla-predictor -p 8001:8000 sla-predictor:latest
```

---

### ❌ Error: "Cannot connect to localhost:8000" desde el backend

**Causa:** El contenedor no está corriendo o no está en modo host.

**Solución:**
```powershell
# Verificar estado
docker ps

# Si no aparece, iniciarlo
docker start sla-predictor

# Si no existe, crearlo
docker run -d --name sla-predictor -p 8000:8000 sla-predictor:latest
```

---

### ❌ El modelo tiene Accuracy: 0% o muy bajo

**Causa:** No hay datos en la base de datos o muy pocos registros.

**Solución:**
1. Verifica que tengas datos en la tabla `solicitud`
2. Ejecuta: `SELECT COUNT(*) FROM solicitud WHERE fecha_creacion IS NOT NULL`
3. Necesitas al menos **50-100 registros** para entrenar bien

---

## 📊 Endpoints Disponibles

Una vez que el contenedor esté corriendo en `http://localhost:8000`:

| Endpoint | Descripción | Ejemplo |
|----------|-------------|---------|
| `GET /health` | Estado del servicio | `http://localhost:8000/health` |
| `GET /modelo/info` | Info del modelo entrenado | `http://localhost:8000/modelo/info` |
| `GET /predecir/criticas?limite=50` | Top solicitudes críticas | `http://localhost:8000/predecir/criticas?limite=50` |
| `POST /predecir/solicitud/{id}` | Predicción de una solicitud | `http://localhost:8000/predecir/solicitud/123` |
| `POST /modelo/reentrenar` | Forzar reentrenamiento | `http://localhost:8000/modelo/reentrenar` |

---

## 📝 Comandos Útiles de Docker

```powershell
# Ver contenedores corriendo
docker ps

# Ver TODOS los contenedores (incluso detenidos)
docker ps -a

# Ver logs de un contenedor
docker logs sla-predictor

# Ver logs en tiempo real (Ctrl+C para salir)
docker logs -f sla-predictor

# Entrar al contenedor (para debugging)
docker exec -it sla-predictor bash

# Ver uso de recursos
docker stats sla-predictor

# Limpiar contenedores detenidos
docker container prune

# Limpiar imágenes sin usar
docker image prune
```

---

## 🔐 Información de Credenciales

**Usuario SQL creado por el script:**
- Usuario: `sla_user`
- Contraseña: `SLA_Pass123!`
- Permisos: Lectura, Escritura, Ejecución
- Base de datos: `Proyecto1SLA_DB`

> **Nota de seguridad:** Estas credenciales son para **desarrollo local** solamente. En producción deberían cambiarse por credenciales seguras.

---

## 💡 Tips y Mejores Prácticas

✅ **Siempre verifica los logs** después de iniciar el contenedor
✅ **Reinicia SQL Server** después de habilitar autenticación mixta
✅ **No elimines la imagen** a menos que sea necesario (ahorra tiempo)
✅ **Usa nombres consistentes** para los contenedores (siempre `sla-predictor`)
✅ **Actualiza tu .gitignore** para no subir archivos de Docker innecesarios

---

## 📞 Soporte

Si tienes problemas:

1. **Revisa los logs:** `docker logs sla-predictor`
2. **Verifica SQL Server:** Que esté corriendo y acepte conexiones
3. **Confirma el usuario SQL:** Ejecuta `create_sql_user.sql` nuevamente
4. **Consulta esta guía:** Revisa la sección de "Solución de Problemas"

---

## ✅ Checklist de Verificación

Antes de reportar un problema, verifica:

- [ ] Docker Desktop está corriendo
- [ ] SQL Server está corriendo
- [ ] Ejecutaste `create_sql_user.sql`
- [ ] SQL Server tiene autenticación mixta habilitada
- [ ] El contenedor está corriendo (`docker ps`)
- [ ] Los logs no muestran errores de conexión
- [ ] El endpoint `/health` responde correctamente

---

**¡Listo! Ahora todos pueden usar el contenedor Docker sin problemas. 🎉**
