from app.database import get_solicitudes_activas

print("\n===== PROBANDO get_solicitudes_activas =====\n")

# Probar con solo_criticas=False y limite=120
result = get_solicitudes_activas(solo_criticas=False, limite=120)

print(f"Resultado: {len(result)} registros")

if result:
    # Agrupar por SLA
    from collections import Counter
    slas = Counter([r['codigo_sla'] for r in result])
    print("\nDistribución por SLA:")
    for sla, count in sorted(slas.items()):
        print(f"  {sla}: {count} registros")
    
    print(f"\nPrimeros 5 registros:")
    for r in result[:5]:
        print(f"  ID: {r['id_solicitud']} | SLA: {r['codigo_sla']} | Estado: {r['estado_cumplimiento']} | Días restantes: {r['dias_restantes']}")
else:
    print("ERROR: No se devolvieron registros")
