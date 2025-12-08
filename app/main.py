"""
FastAPI - Microservicio de Predicción SLA
"""
import logging
from datetime import datetime
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .config import get_settings
from .schemas import (
    PrediccionRequest,
    PrediccionResponse,
    PrediccionBatchResponse,
    ResumenPrediccion,
    TendenciaItem,
    HealthResponse,
    ReentrenamientoResponse
)
from .database import (
    get_solicitudes_activas,
    get_tendencias_historicas,
    verificar_conexion,
    get_filtros_disponibles
)
from .model import (
    get_modelo,
    predecir,
    predecir_batch,
    forzar_reentrenamiento,
    modelo_esta_cargado,
    get_modelo_info
)

# Configuración
settings = get_settings()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Thread pool para operaciones pesadas
executor = ThreadPoolExecutor(max_workers=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # Startup
    logger.info("🚀 Iniciando servicio de predicción SLA...")
    
    # Pre-cargar modelo
    try:
        await asyncio.get_event_loop().run_in_executor(executor, get_modelo)
        logger.info("✅ Modelo cargado exitosamente")
    except Exception as e:
        logger.error(f"⚠️ Error al cargar modelo: {e}")
    
    yield
    
    # Shutdown
    logger.info("👋 Cerrando servicio de predicción...")
    executor.shutdown(wait=True)


# Crear aplicación FastAPI
app = FastAPI(
    title="SLA Predicción Service",
    description="Microservicio de Machine Learning para predicción de incumplimientos SLA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica tus dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/", tags=["Info"])
async def root():
    """Información del servicio"""
    return {
        "service": "SLA Predicción Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health_check():
    """
    Health check para Docker/Kubernetes.
    Verifica que el servicio y el modelo estén operativos.
    """
    return HealthResponse(
        status="healthy" if modelo_esta_cargado() else "degraded",
        model_loaded=modelo_esta_cargado(),
        timestamp=datetime.now(),
        version="1.0.0"
    )


@app.get("/filtros", tags=["Info"])
async def obtener_filtros():
    """
    Obtiene las opciones de filtros disponibles desde la BD.
    
    Retorna códigos SLA activos, roles y bloques tecnológicos.
    Útil para cargar dinámicamente las opciones de filtrado en el frontend.
    """
    try:
        filtros = await asyncio.get_event_loop().run_in_executor(
            executor,
            get_filtros_disponibles
        )
        return filtros
    except Exception as e:
        logger.error(f"Error al obtener filtros: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predecir", response_model=PrediccionResponse, tags=["Predicción"])
async def predecir_individual(request: PrediccionRequest):
    """
    Predicción individual para una solicitud específica.
    
    Uso: Cuando el usuario ve el detalle de una solicitud.
    Tiempo de respuesta esperado: < 50ms
    """
    try:
        probabilidad, nivel_riesgo, factores = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: predecir(
                request.dias_transcurridos,
                request.dias_umbral,
                request.id_rol
            )
        )
        
        return PrediccionResponse(
            id_solicitud=request.id_solicitud,
            probabilidad_incumplimiento=round(probabilidad, 4),
            nivel_riesgo=nivel_riesgo,
            fecha_prediccion=datetime.now(),
            factores_riesgo=factores
        )
    except Exception as e:
        logger.error(f"Error en predicción individual: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predecir/criticas", response_model=List[PrediccionResponse], tags=["Predicción"])
async def predecir_criticas(
    limite: int = Query(default=20, ge=1, le=100, description="Máximo de resultados")
):
    """
    Predicción de solicitudes críticas (próximas a vencer).
    
    Optimizado para dashboard. Solo analiza solicitudes con 70%+ del tiempo consumido.
    Tiempo de respuesta esperado: < 200ms
    """
    try:
        # Obtener solicitudes críticas
        solicitudes = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: get_solicitudes_activas(solo_criticas=True, limite=limite)
        )
        
        if not solicitudes:
            return []
        
        # Predicción batch
        resultados = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: predecir_batch(solicitudes)
        )
        
        # Mapear a response y ordenar por probabilidad
        predicciones = [
            PrediccionResponse(
                id_solicitud=r['id_solicitud'],
                codigo_sla=r['codigo_sla'],
                nombre_rol=r['nombre_rol'],
                probabilidad_incumplimiento=r['probabilidad_incumplimiento'],
                nivel_riesgo=r['nivel_riesgo'],
                dias_restantes=r['dias_restantes'],
                fecha_prediccion=datetime.now(),
                factores_riesgo=r['factores_riesgo']
            )
            for r in resultados
        ]
        
        # Ordenar por probabilidad descendente
        predicciones.sort(key=lambda x: x.probabilidad_incumplimiento, reverse=True)
        
        return predicciones
        
    except Exception as e:
        logger.error(f"Error en predicciones críticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predecir/paginado", response_model=PrediccionBatchResponse, tags=["Predicción"])
async def predecir_paginado(
    pagina: int = Query(default=1, ge=1, description="Número de página"),
    tamano_pagina: int = Query(default=50, ge=1, le=100, description="Registros por página"),
    incluir_historicas: bool = Query(default=True, description="Incluir solicitudes completadas/canceladas"),
    codigo_sla: str = Query(default=None, description="Filtrar por código SLA (ej: SLA1, SLA2)")
):
    """
    Predicción paginada para tabla completa.
    
    Optimizado para grandes volúmenes. No carga todo a memoria.
    Por defecto incluye todas las solicitudes (activas e históricas).
    Tiempo de respuesta esperado: < 500ms
    """
    try:
        # Obtener solicitudes paginadas
        solicitudes, total = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: get_solicitudes_activas(
                pagina=pagina,
                tamano_pagina=tamano_pagina,
                con_total=True,
                incluir_historicas=incluir_historicas,
                codigo_sla=codigo_sla
            )
        )
        
        if not solicitudes:
            return PrediccionBatchResponse(
                data=[],
                pagina=pagina,
                tamano_pagina=tamano_pagina,
                total_registros=total,
                total_paginas=0
            )
        
        # Predicción batch
        resultados = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: predecir_batch(solicitudes)
        )
        
        # Mapear a response
        predicciones = [
            PrediccionResponse(
                id_solicitud=r['id_solicitud'],
                codigo_sla=r['codigo_sla'],
                nombre_rol=r['nombre_rol'],
                probabilidad_incumplimiento=r['probabilidad_incumplimiento'],
                nivel_riesgo=r['nivel_riesgo'],
                dias_restantes=r['dias_restantes'],
                fecha_prediccion=datetime.now(),
                factores_riesgo=r['factores_riesgo']
            )
            for r in resultados
        ]
        
        total_paginas = (total + tamano_pagina - 1) // tamano_pagina if total > 0 else 0
        
        return PrediccionBatchResponse(
            data=predicciones,
            pagina=pagina,
            tamano_pagina=tamano_pagina,
            total_registros=total,
            total_paginas=total_paginas
        )
        
    except Exception as e:
        logger.error(f"Error en predicción paginada: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resumen", response_model=ResumenPrediccion, tags=["Dashboard"])
async def obtener_resumen():
    """
    Resumen rápido para KPIs del dashboard.
    
    Retorna conteos por nivel de riesgo y promedio general.
    Tiempo de respuesta esperado: < 300ms
    """
    try:
        # Obtener predicciones críticas para calcular resumen
        solicitudes = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: get_solicitudes_activas(solo_criticas=True, limite=100)
        )
        
        if not solicitudes:
            return ResumenPrediccion(
                total_analizadas=0,
                criticas=0,
                altas=0,
                medias=0,
                bajas=0,
                promedio_riesgo=0
            )
        
        # Predicción batch
        resultados = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: predecir_batch(solicitudes)
        )
        
        # Contar por nivel
        niveles = {"CRITICO": 0, "ALTO": 0, "MEDIO": 0, "BAJO": 0}
        suma_prob = 0
        
        for r in resultados:
            niveles[r['nivel_riesgo']] += 1
            suma_prob += r['probabilidad_incumplimiento']
        
        promedio = (suma_prob / len(resultados) * 100) if resultados else 0
        
        return ResumenPrediccion(
            total_analizadas=len(resultados),
            criticas=niveles["CRITICO"],
            altas=niveles["ALTO"],
            medias=niveles["MEDIO"],
            bajas=niveles["BAJO"],
            promedio_riesgo=round(promedio, 1)
        )
        
    except Exception as e:
        logger.error(f"Error al obtener resumen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tendencias", response_model=List[TendenciaItem], tags=["Dashboard"])
async def obtener_tendencias(
    meses: int = Query(default=6, ge=1, le=24, description="Meses hacia atrás")
):
    """
    Tendencias históricas de cumplimiento SLA.
    
    Útil para gráficos de evolución temporal.
    """
    try:
        tendencias = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: get_tendencias_historicas(meses)
        )
        
        return [
            TendenciaItem(
                periodo=t['periodo'],
                total_solicitudes=t['total_solicitudes'],
                incumplidas=t['incumplidas'],
                tasa_incumplimiento=float(t['tasa_incumplimiento'] or 0)
            )
            for t in tendencias
        ]
        
    except Exception as e:
        logger.error(f"Error al obtener tendencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/modelo/reentrenar", response_model=ReentrenamientoResponse, tags=["Admin"])
async def reentrenar_modelo():
    """
    Fuerza el reentrenamiento del modelo con datos actuales.
    
    Uso: Llamar periódicamente o cuando hay muchos datos nuevos.
    Este endpoint puede tardar varios segundos.
    """
    try:
        resultado = await asyncio.get_event_loop().run_in_executor(
            executor,
            forzar_reentrenamiento
        )
        
        return ReentrenamientoResponse(
            status="ok",
            message="Modelo reentrenado exitosamente",
            samples_used=resultado['samples_used'],
            accuracy=resultado['accuracy'],
            timestamp=resultado['timestamp']
        )
        
    except Exception as e:
        logger.error(f"Error al reentrenar modelo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/modelo/info", tags=["Admin"])
async def info_modelo():
    """Obtiene información del modelo actual"""
    return get_modelo_info()


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "error": str(exc)}
    )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
