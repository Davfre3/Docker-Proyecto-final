-- Script para crear usuario SQL Server para el contenedor Docker
-- Ejecutar este script en SQL Server Management Studio conectado a Piero\MSSQLSERVER1

USE [master];
GO

-- Crear login SQL Server
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'sla_user')
BEGIN
    CREATE LOGIN [sla_user] WITH PASSWORD = 'SLA_Pass123!', 
    CHECK_POLICY = OFF,
    CHECK_EXPIRATION = OFF;
    PRINT 'Login sla_user creado exitosamente';
END
ELSE
BEGIN
    PRINT 'Login sla_user ya existe';
END
GO

-- Cambiar a la base de datos del proyecto
USE [Proyecto1SLA_DB];
GO

-- Crear usuario en la base de datos
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'sla_user')
BEGIN
    CREATE USER [sla_user] FOR LOGIN [sla_user];
    PRINT 'Usuario sla_user creado exitosamente en Proyecto1SLA_DB';
END
ELSE
BEGIN
    PRINT 'Usuario sla_user ya existe en Proyecto1SLA_DB';
END
GO

-- Otorgar permisos de lectura y escritura
ALTER ROLE db_datareader ADD MEMBER [sla_user];
ALTER ROLE db_datawriter ADD MEMBER [sla_user];
GO

-- Permisos adicionales si son necesarios (EXECUTE para stored procedures)
GRANT EXECUTE TO [sla_user];
GO

PRINT '✅ Usuario SQL Server configurado correctamente para el contenedor Docker';
PRINT 'Usuario: sla_user';
PRINT 'Base de datos: Proyecto1SLA_DB';
PRINT 'Permisos: db_datareader, db_datawriter, EXECUTE';
GO
