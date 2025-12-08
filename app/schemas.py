"""
Schemas/DTOs para el servicio de predicción
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PrediccionRequest(BaseModel):
    """Request para predicción individual"""
    id_solicitud: int = Field(..., description="ID de la solicitud")
    dias_transcurridos: float = Field(..., ge=0, description="Días desde la creación")
    dias_umbral: float = Field(..., gt=0, description="Días límite del SLA")
    id_rol: int = Field(..., description="ID del rol responsable")


class PrediccionResponse(BaseModel):
    """Response de predicción"""
    id_solicitud: int
    codigo_sla: Optional[str] = None
    nombre_rol: Optional[str] = None
    probabilidad_incumplimiento: float = Field(..., ge=0, le=1)
    nivel_riesgo: str = Field(..., pattern="^(CRITICO|ALTO|MEDIO|BAJO)$")
    dias_restantes: Optional[int] = None
    fecha_prediccion: datetime
    factores_riesgo: Optional[List[str]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id_solicitud": 123,
                "codigo_sla": "SLA-001",
                "nombre_rol": "Analista",
                "probabilidad_incumplimiento": 0.75,
                "nivel_riesgo": "ALTO",
                "dias_restantes": 3,
                "fecha_prediccion": "2025-12-05T10:30:00",
                "factores_riesgo": ["Tiempo elevado", "Rol con historial de retrasos"]
            }
        }


class PrediccionBatchResponse(BaseModel):
    """Response paginado de predicciones"""
    data: List[PrediccionResponse]
    pagina: int = Field(..., ge=1)
    tamano_pagina: int = Field(..., ge=1, le=100)
    total_registros: int = Field(..., ge=0)
    total_paginas: int = Field(..., ge=0)


class ResumenPrediccion(BaseModel):
    """Resumen para KPIs del dashboard"""
    total_analizadas: int = Field(..., ge=0)
    criticas: int = Field(..., ge=0)
    altas: int = Field(..., ge=0)
    medias: int = Field(..., ge=0)
    bajas: int = Field(..., ge=0)
    promedio_riesgo: float = Field(..., ge=0, le=100)
    en_proceso: int = Field(default=0, ge=0, description="Solicitudes en proceso")
    completadas: int = Field(default=0, ge=0, description="Solicitudes completadas")
    canceladas: int = Field(default=0, ge=0, description="Solicitudes canceladas")

    class Config:
        json_schema_extra = {
            "example": {
                "total_analizadas": 150,
                "criticas": 12,
                "altas": 28,
                "medias": 45,
                "bajas": 65,
                "promedio_riesgo": 35.5,
                "en_proceso": 120,
                "completadas": 25,
                "canceladas": 5
            }
        }


class TendenciaItem(BaseModel):
    """Item de tendencia histórica"""
    periodo: str  # "2025-11", "2025-10", etc.
    total_solicitudes: int
    incumplidas: int
    tasa_incumplimiento: float
    prediccion_proxima: Optional[float] = None


class HealthResponse(BaseModel):
    """Response del health check"""
    status: str
    model_loaded: bool
    timestamp: datetime
    version: str = "1.0.0"


class ReentrenamientoResponse(BaseModel):
    """Response del reentrenamiento"""
    status: str
    message: str
    samples_used: int
    accuracy: Optional[float] = None
    timestamp: datetime
