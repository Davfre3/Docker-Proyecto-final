# 🐳 Configuración Docker + SQL Server

## ⚠️ Problema con Autenticación de Windows

**Los contenedores Docker basados en Linux NO pueden usar autenticación integrada de Windows** para conectarse a SQL Server en el host Windows.

## ✅ Solución: Crear usuario SQL Server

### Paso 1: Ejecutar el script SQL

1. Abre **SQL Server Management Studio (SSMS)**
2. Conéctate a `Piero\MSSQLSERVER1`
3. Abre el archivo `create_sql_user.sql`
4. Ejecuta el script completo (F5)

Esto creará:
- Login: `sla_user`
- Password: `SLA_Pass123!` (puedes cambiarlo)
- Permisos: lectura, escritura y ejecución en `Proyecto1SLA_DB`

### Paso 2: Verificar que SQL Server acepta autenticación mixta

1. En SSMS, clic derecho en el servidor → **Propiedades**
2. Ve a **Seguridad**
3. Asegúrate que esté seleccionado: **"Modo de autenticación de SQL Server y Windows"**
4. Si cambias esto, **reinicia el servicio SQL Server**

### Paso 3: Reconstruir y levantar el contenedor

```powershell
# Detener y eliminar contenedor actual
docker stop sla-predictor
docker rm sla-predictor

# Reconstruir imagen
docker build -t sla-predictor:latest .

# Levantar contenedor
docker run -d --name sla-predictor -p 8000:8000 sla-predictor:latest

# Ver logs
docker logs -f sla-predictor

# Probar endpoint
Invoke-RestMethod -Uri http://localhost:8000/health
```

### Paso 4 (Opcional): Usar variables de entorno personalizadas

Si quieres cambiar usuario/contraseña sin modificar el código:

```powershell
docker run -d --name sla-predictor -p 8000:8000 `
  -e DATABASE_USER="tu_usuario" `
  -e DATABASE_PASSWORD="tu_password" `
  sla-predictor:latest
```

## 🔧 Troubleshooting

### Error: "Login timeout expired"
- SQL Server no acepta autenticación SQL → Revisar Paso 2
- Firewall bloqueando conexión → Agregar regla para puerto 1433

### Error: "Login failed for user 'sla_user'"
- Usuario no creado → Ejecutar `create_sql_user.sql`
- Contraseña incorrecta → Verificar en `app/config.py`

### Error: "Cannot connect to localhost:8000"
- Contenedor no corriendo → `docker ps -a`
- Puerto ocupado → Cambiar a otro puerto: `-p 8001:8000`

## 📝 Notas

- Tu backend .NET puede seguir usando Windows Authentication
- El contenedor Docker usa autenticación SQL Server
- Ambos pueden coexistir sin problemas
