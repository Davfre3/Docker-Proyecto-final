"""
Configuración del microservicio de predicción
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # Base de datos - Proyecto1SLA_DB
    database_url: str = "mssql+pyodbc://sa:YourPassword123@localhost:1433/Proyecto1SLA_DB?driver=ODBC+Driver+17+for+SQL+Server"
    
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


@lru_cache()
def get_settings() -> Settings:
    """Obtiene la configuración (cacheada)"""
    return Settings()
