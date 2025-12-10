"""
Configuración del microservicio de predicción
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Base de datos - Proyecto1SLA_DB
    # Usar autenticación SQL Server (la autenticación de Windows no funciona desde contenedores Linux)
    database_server: str = "host.docker.internal\\MSSQLSERVER1"
    database_name: str = "Proyecto1SLA_DB"
    database_user: str = "sla_user"  # Crear este usuario en SQL Server
    database_password: str = "SLA_Pass123!"  # Cambiar por una contraseña segura
    
    @property
    def database_url(self) -> str:
        """Construye la URL de conexión dinámicamente"""
        return f"mssql+pyodbc://{self.database_user}:{self.database_password}@{self.database_server}/{self.database_name}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    
    # Modelo
    model_path: str = "/app/models/sla_model.pkl"
    model_reload_interval: int = 3600  # segundos (1 hora)
    max_training_samples: int = 10000
    
    # Caché
    cache_ttl: int = 600  # 10 minutos
    
    # Logging
    log_level: str = "INFO"
    
    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        protected_namespaces = ()  # Permite usar campos con prefijo "model_"


@lru_cache()
def get_settings() -> Settings:
    """Obtiene la configuración (cacheada)"""
    return Settings()
