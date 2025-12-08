"""
Conexión a base de datos SQL Server
Base de datos: Proyecto1SLA_DB

Tablas utilizadas:
- solicitud: Solicitudes de SLA
- config_sla: Configuración de SLAs (umbrales, tipos)
- rol_registro: Roles/puestos de trabajo
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager
import logging

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Crear engine con pool de conexiones
engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verificar conexión antes de usar
    pool_recycle=3600    # Reciclar conexiones cada hora
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session():
    """Context manager para sesiones de BD"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_solicitudes_activas(
    solo_criticas: bool = False,
    limite: int = 50,
    pagina: int = 1,
    tamano_pagina: int = 50,
    con_total: bool = False,
    incluir_historicas: bool = False,
    codigo_sla: str = None
) -> List[Dict] | Tuple[List[Dict], int]:
    """
    Obtiene solicitudes activas para predicción.
    Optimizado para grandes volúmenes con paginación.
    
    Tablas: solicitud, config_sla, rol_registro
    
    Args:
        solo_criticas: Si True, solo solicitudes con 70%+ del tiempo consumido
        limite: Límite de registros (para críticas)
        pagina: Número de página
        tamano_pagina: Registros por página
        con_total: Si True, retorna tupla (datos, total)
        incluir_historicas: Si True, incluye solicitudes completadas/canceladas
        codigo_sla: Filtrar por código SLA específico (SLA1, SLA2, etc.)
    
    Returns:
        Lista de solicitudes o tupla (solicitudes, total)
    """
    with get_db_session() as session:
        try:
            # Condición de filtro según si incluimos históricas o no
            estado_filter = ""
            if not incluir_historicas:
                estado_filter = "AND s.estado_solicitud NOT IN ('COMPLETADA', 'CANCELADA')"
            
            # Filtro por código SLA
            sla_filter = ""
            if codigo_sla:
                sla_filter = f"AND c.codigo_sla = '{codigo_sla}'"
            
            # Query base - Adaptado a Proyecto1SLA_DB
            # Columnas de solicitud: id_solicitud, fecha_solicitud, estado_solicitud, 
            #                        estado_cumplimiento_sla, id_sla, id_rol_registro, num_dias_sla
            # Columnas de config_sla: id_sla, codigo_sla, dias_umbral, tipo_solicitud
            # Columnas de rol_registro: id_rol_registro, nombre_rol, bloque_tech
            base_query = f"""
                SELECT 
                    s.id_solicitud as id_solicitud,
                    DATEDIFF(day, s.fecha_solicitud, GETDATE()) as dias_transcurridos,
                    c.dias_umbral as dias_umbral,
                    s.id_rol_registro as id_rol,
                    c.codigo_sla as codigo_sla,
                    r.nombre_rol as nombre_rol,
                    r.bloque_tech as bloque_tech,
                    c.dias_umbral - DATEDIFF(day, s.fecha_solicitud, GETDATE()) as dias_restantes,
                    s.estado_solicitud as estado_solicitud,
                    s.estado_cumplimiento_sla as estado_cumplimiento
                FROM solicitud s
                INNER JOIN config_sla c ON s.id_sla = c.id_sla
                INNER JOIN rol_registro r ON s.id_rol_registro = r.id_rol_registro
                WHERE c.es_activo = 1
                    {estado_filter}
                    {sla_filter}
            """
            
            if solo_criticas:
                # Solo las que han consumido 70%+ del tiempo
                criticas_query = base_query + """
                    AND DATEDIFF(day, s.fecha_solicitud, GETDATE()) >= (c.dias_umbral * 0.7)
                    ORDER BY dias_transcurridos DESC
                    OFFSET 0 ROWS FETCH NEXT :limite ROWS ONLY
                """
                
                result = session.execute(text(criticas_query), {"limite": limite})
                solicitudes = [dict(row._mapping) for row in result]
                return solicitudes
            
            # Paginado normal
            offset = (pagina - 1) * tamano_pagina
            
            # Si hay filtro de SLA, ordenar por fecha
            # Si no hay filtro, ordenar por días restantes (más urgentes primero) para ver variedad
            if codigo_sla:
                order_by = "ORDER BY s.fecha_solicitud DESC"
            else:
                # Ordenar por días restantes ascendente (más urgentes primero)
                # Esto muestra una mezcla de todos los SLAs según urgencia
                order_by = "ORDER BY dias_restantes ASC, c.codigo_sla"
            
            paginated_query = base_query + f"""
                {order_by}
                OFFSET :offset ROWS FETCH NEXT :tamano ROWS ONLY
            """
            
            result = session.execute(
                text(paginated_query), 
                {"offset": offset, "tamano": tamano_pagina}
            )
            solicitudes = [dict(row._mapping) for row in result]
            
            if con_total:
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM solicitud s
                    INNER JOIN config_sla c ON s.id_sla = c.id_sla
                    WHERE c.es_activo = 1
                        {estado_filter}
                        {sla_filter}
                """
                total = session.execute(text(count_query)).scalar() or 0
                return solicitudes, total
            
            return solicitudes
            
        except Exception as e:
            logger.error(f"Error al obtener solicitudes: {e}")
            if con_total:
                return [], 0
            return []


def get_datos_entrenamiento(limite: int = 10000) -> List[Dict]:
    """
    Obtiene datos históricos para entrenar el modelo.
    Solo usa solicitudes completadas (cumplidas o incumplidas).
    
    El campo estado_cumplimiento_sla tiene formato:
    - CUMPLE_SLA1, CUMPLE_SLA2, ..., CUMPLE_SLA6: Se cumplió el SLA
    - NO_CUMPLE_SLA1, NO_CUMPLE_SLA2, ..., NO_CUMPLE_SLA6: No se cumplió el SLA
    - EN_PROCESO_SLA2, EN_PROCESO_SLA3, EN_PROCESO_SLA4: Aún en proceso
    
    Args:
        limite: Máximo de registros para entrenamiento
    
    Returns:
        Lista de diccionarios con datos de entrenamiento
    """
    with get_db_session() as session:
        try:
            # Usamos num_dias_sla si está disponible, sino calculamos
            query = text("""
                SELECT TOP (:limite)
                    COALESCE(
                        s.num_dias_sla,
                        DATEDIFF(day, s.fecha_solicitud, COALESCE(s.fecha_ingreso, GETDATE()))
                    ) as dias_transcurridos,
                    c.dias_umbral as dias_umbral,
                    s.id_rol_registro as id_rol,
                    CASE 
                        WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1 
                        ELSE 0 
                    END as incumplio
                FROM solicitud s
                INNER JOIN config_sla c ON s.id_sla = c.id_sla
                WHERE s.estado_cumplimiento_sla IS NOT NULL
                    AND s.estado_cumplimiento_sla NOT LIKE 'EN_PROCESO%'
                ORDER BY s.creado_en DESC
            """)
            
            result = session.execute(query, {"limite": limite})
            datos = [dict(row._mapping) for row in result]
            
            logger.info(f"Obtenidos {len(datos)} registros para entrenamiento")
            return datos
            
        except Exception as e:
            logger.error(f"Error al obtener datos de entrenamiento: {e}")
            return []


def get_tendencias_historicas(meses: int = 6) -> List[Dict]:
    """
    Obtiene tendencias históricas de cumplimiento SLA.
    
    Args:
        meses: Cantidad de meses hacia atrás
    
    Returns:
        Lista con estadísticas por mes
    """
    with get_db_session() as session:
        try:
            query = text("""
                SELECT 
                    FORMAT(s.fecha_solicitud, 'yyyy-MM') as periodo,
                    COUNT(*) as total_solicitudes,
                    SUM(CASE 
                        WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1 
                        ELSE 0 
                    END) as incumplidas,
                    CAST(
                        SUM(CASE 
                            WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1.0 
                            ELSE 0 
                        END) / NULLIF(COUNT(*), 0) * 100 
                        AS DECIMAL(5,2)
                    ) as tasa_incumplimiento
                FROM solicitud s
                WHERE s.fecha_solicitud >= DATEADD(month, -:meses, GETDATE())
                    AND s.estado_cumplimiento_sla IS NOT NULL
                    AND s.estado_cumplimiento_sla NOT LIKE 'EN_PROCESO%'
                GROUP BY FORMAT(s.fecha_solicitud, 'yyyy-MM')
                ORDER BY periodo DESC
            """)
            
            result = session.execute(query, {"meses": meses})
            return [dict(row._mapping) for row in result]
            
        except Exception as e:
            logger.error(f"Error al obtener tendencias: {e}")
            return []


def get_estadisticas_por_rol(meses: int = 3) -> List[Dict]:
    """
    Obtiene estadísticas de cumplimiento por rol/bloque tech.
    Útil para identificar qué roles tienen más incumplimientos.
    
    Args:
        meses: Cantidad de meses hacia atrás
    
    Returns:
        Lista con estadísticas por rol
    """
    with get_db_session() as session:
        try:
            query = text("""
                SELECT 
                    r.nombre_rol,
                    r.bloque_tech,
                    COUNT(*) as total_solicitudes,
                    SUM(CASE 
                        WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1 
                        ELSE 0 
                    END) as incumplidas,
                    CAST(
                        SUM(CASE 
                            WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1.0 
                            ELSE 0 
                        END) / NULLIF(COUNT(*), 0) * 100 
                        AS DECIMAL(5,2)
                    ) as tasa_incumplimiento,
                    AVG(COALESCE(s.num_dias_sla, 0)) as promedio_dias
                FROM solicitud s
                INNER JOIN rol_registro r ON s.id_rol_registro = r.id_rol_registro
                WHERE s.fecha_solicitud >= DATEADD(month, -:meses, GETDATE())
                    AND s.estado_cumplimiento_sla IS NOT NULL
                    AND s.estado_cumplimiento_sla NOT LIKE 'EN_PROCESO%'
                GROUP BY r.nombre_rol, r.bloque_tech
                ORDER BY tasa_incumplimiento DESC
            """)
            
            result = session.execute(query, {"meses": meses})
            return [dict(row._mapping) for row in result]
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas por rol: {e}")
            return []


def get_estadisticas_por_sla() -> List[Dict]:
    """
    Obtiene estadísticas de cumplimiento por tipo de SLA.
    
    Returns:
        Lista con estadísticas por código SLA
    """
    with get_db_session() as session:
        try:
            query = text("""
                SELECT 
                    c.codigo_sla,
                    c.descripcion as descripcion_sla,
                    c.dias_umbral,
                    c.tipo_solicitud,
                    COUNT(*) as total_solicitudes,
                    SUM(CASE 
                        WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1 
                        ELSE 0 
                    END) as incumplidas,
                    CAST(
                        SUM(CASE 
                            WHEN s.estado_cumplimiento_sla LIKE 'NO_CUMPLE%' THEN 1.0 
                            ELSE 0 
                        END) / NULLIF(COUNT(*), 0) * 100 
                        AS DECIMAL(5,2)
                    ) as tasa_incumplimiento
                FROM solicitud s
                INNER JOIN config_sla c ON s.id_sla = c.id_sla
                WHERE s.estado_cumplimiento_sla IS NOT NULL
                    AND s.estado_cumplimiento_sla NOT LIKE 'EN_PROCESO%'
                    AND c.es_activo = 1
                GROUP BY c.codigo_sla, c.descripcion, c.dias_umbral, c.tipo_solicitud
                ORDER BY tasa_incumplimiento DESC
            """)
            
            result = session.execute(query)
            return [dict(row._mapping) for row in result]
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas por SLA: {e}")
            return []


def verificar_conexion() -> bool:
    """Verifica si la conexión a la BD está activa"""
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Error de conexión a BD: {e}")
        return False


def get_filtros_disponibles() -> Dict:
    """
    Obtiene los valores disponibles para filtros desde la BD.
    
    Returns:
        Diccionario con opciones de filtros:
        - codigos_sla: Lista de códigos SLA activos
        - roles: Lista de roles disponibles
        - bloques_tech: Lista de bloques tecnológicos
    """
    with get_db_session() as session:
        try:
            # Códigos SLA activos
            sla_query = text("""
                SELECT DISTINCT c.codigo_sla, c.descripcion, c.dias_umbral, c.tipo_solicitud
                FROM config_sla c
                WHERE c.es_activo = 1
                ORDER BY c.codigo_sla
            """)
            sla_result = session.execute(sla_query)
            codigos_sla = [dict(row._mapping) for row in sla_result]
            
            # Roles disponibles
            roles_query = text("""
                SELECT DISTINCT r.id_rol_registro, r.nombre_rol, r.bloque_tech
                FROM rol_registro r
                WHERE r.es_activo = 1
                ORDER BY r.nombre_rol
            """)
            roles_result = session.execute(roles_query)
            roles = [dict(row._mapping) for row in roles_result]
            
            # Bloques tecnológicos
            bloques_query = text("""
                SELECT DISTINCT bloque_tech
                FROM rol_registro
                WHERE bloque_tech IS NOT NULL AND es_activo = 1
                ORDER BY bloque_tech
            """)
            bloques_result = session.execute(bloques_query)
            bloques_tech = [row[0] for row in bloques_result]
            
            return {
                "codigos_sla": codigos_sla,
                "roles": roles,
                "bloques_tech": bloques_tech
            }
            
        except Exception as e:
            logger.error(f"Error al obtener filtros disponibles: {e}")
            return {
                "codigos_sla": [],
                "roles": [],
                "bloques_tech": []
            }
