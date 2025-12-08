# Microservicio de Predicción SLA

Microservicio de Machine Learning para predicción de incumplimientos SLA.

## Requisitos

- Docker y Docker Compose
- Python 3.11+ (si se ejecuta localmente)
- Conexión a la base de datos SQL Server

## Estructura

```
prediccion-service/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app principal
│   ├── model.py          # Lógica del modelo ML
│   ├── schemas.py        # DTOs/Schemas Pydantic
│   ├── database.py       # Conexión a SQL Server
│   └── config.py         # Configuración
├── models/               # Modelos entrenados (.pkl)
├── Dockerfile
├── requirements.txt
└── README.md
```

## Ejecución con Docker

```bash
# Desde la raíz del proyecto
docker-compose up -d prediccion

# Ver logs
docker-compose logs -f prediccion
```

## Ejecución local (desarrollo)

```bash
cd prediccion-service
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Info del servicio |
| GET | `/health` | Health check |
| POST | `/predecir` | Predicción individual |
| GET | `/predecir/criticas` | Top predicciones críticas |
| GET | `/predecir/paginado` | Predicciones paginadas |
| GET | `/resumen` | KPIs de predicción |
| POST | `/modelo/reentrenar` | Reentrenar modelo |

## Variables de entorno

```env
DATABASE_URL=mssql+pyodbc://user:pass@server:1433/db?driver=ODBC+Driver+17+for+SQL+Server
MODEL_PATH=/app/models/sla_model.pkl
LOG_LEVEL=INFO
```
