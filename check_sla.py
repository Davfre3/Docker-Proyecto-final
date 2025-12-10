from app.database import get_db_session
from sqlalchemy import text

with get_db_session() as session:
    # Query para ver distribución de EN_PROCESO por SLA
    query = """
    SELECT 
        c.codigo_sla, 
        COUNT(*) as total,
        SUM(CASE WHEN DATEDIFF(day, s.fecha_solicitud, GETDATE()) >= (c.dias_umbral * 0.7) THEN 1 ELSE 0 END) as criticas
    FROM solicitud s
    INNER JOIN config_sla c ON s.id_sla = c.id_sla
    WHERE s.estado_cumplimiento_sla LIKE 'EN_PROCESO_%' 
        AND c.es_activo = 1
        AND s.estado_solicitud NOT IN ('COMPLETADA', 'CANCELADA')
    GROUP BY c.codigo_sla
    ORDER BY c.codigo_sla
    """

    result = session.execute(text(query))

    print("\n===== DISTRIBUCIÓN DE EN_PROCESO POR SLA =====")
    for row in result:
        print(f"{row.codigo_sla}: {row.total} registros (Críticas: {row.criticas})")
