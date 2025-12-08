# 📊 Documentación - Modelo de Predicción de Incumplimiento SLA

## 🎯 Objetivo del Modelo

Predecir la **probabilidad de incumplimiento** de una solicitud antes de que venza su plazo, permitiendo tomar acciones preventivas para garantizar el cumplimiento de los SLA (Service Level Agreements).

---

## 🧠 Tipo de Modelo

**Random Forest Classifier** - Algoritmo de Machine Learning basado en múltiples árboles de decisión.

### ¿Por qué Random Forest?

- ✅ Alta precisión (98.19% en nuestro caso)
- ✅ Maneja bien datos no lineales
- ✅ Resistente al overfitting
- ✅ Proporciona importancia de características
- ✅ Rápido en predicciones (< 50ms por solicitud)

---

## 📥 Variables de Entrada (Features)

El modelo utiliza **3 características principales** para hacer predicciones:

| Variable | Descripción | Fuente en BD | Ejemplo |
|----------|-------------|--------------|---------|
| **dias_transcurridos** | Días desde la creación de la solicitud hasta hoy | `DATEDIFF(day, solicitud.fecha_solicitud, GETDATE())` | 28 días |
| **dias_umbral** | Días máximos permitidos según el tipo de SLA | `config_sla.dias_umbral` | 35 días (SLA1) |
| **id_rol** | Identificador del rol asociado a la solicitud | `solicitud.id_rol_registro` | 1 = DevOps Engineer |

### Cálculo Derivado: Porcentaje de Tiempo Usado

```python
porcentaje_usado = (dias_transcurridos / dias_umbral) * 100
```

**Ejemplo:**
- SLA1 (35 días), 28 días transcurridos → 80% del tiempo usado
- SLA5 (5 días), 4 días transcurridos → 80% del tiempo usado

Ambos tienen el mismo nivel de urgencia relativo aunque los días sean diferentes.

---

## 📤 Salida del Modelo

### 1. Probabilidad de Incumplimiento

**Valor numérico entre 0 y 1** (se muestra como porcentaje 0%-100%)

```python
probabilidad = modelo.predict_proba(datos)[0][1]
# Ejemplo: 0.85 → 85% de probabilidad de incumplir
```

### 2. Nivel de Riesgo

Categorización basada en la probabilidad:

| Nivel | Rango de Probabilidad | Color | Descripción |
|-------|----------------------|-------|-------------|
| **CRÍTICO** | ≥ 75% | 🔴 Rojo | Requiere acción inmediata |
| **ALTO** | 50% - 74% | 🟠 Naranja | Requiere atención prioritaria |
| **MEDIO** | 25% - 49% | 🟡 Amarillo | Monitorear de cerca |
| **BAJO** | 0% - 24% | 🟢 Verde | Dentro de márgenes normales |

### 3. Factores de Riesgo

El sistema identifica automáticamente las razones del alto riesgo:

```python
factores_riesgo = []

porcentaje_usado = (dias_transcurridos / dias_umbral) * 100

if porcentaje_usado > 90:
    factores_riesgo.append("Tiempo casi agotado (>90%)")
elif porcentaje_usado > 75:
    factores_riesgo.append("Tiempo crítico (>75%)")
elif porcentaje_usado > 50:
    factores_riesgo.append("Más de la mitad del tiempo consumido")

if probabilidad >= 0.8:
    factores_riesgo.append("Alta probabilidad histórica")
elif probabilidad >= 0.6:
    factores_riesgo.append("Probabilidad moderada-alta")
```

---

## 🎓 Entrenamiento del Modelo

### Datos de Entrenamiento

El modelo se entrena con **solicitudes históricas completadas** de la tabla `solicitud`:

```sql
SELECT 
    DATEDIFF(day, fecha_solicitud, fecha_ingreso) as dias_transcurridos,
    c.dias_umbral,
    s.id_rol_registro,
    CASE 
        WHEN estado_cumplimiento_sla LIKE 'CUMPLE_SLA%' THEN 0  -- Cumplió
        WHEN estado_cumplimiento_sla LIKE 'NO_CUMPLE_SLA%' THEN 1  -- Incumplió
        ELSE NULL
    END as incumplio
FROM solicitud s
INNER JOIN config_sla c ON s.id_sla = c.id_sla
WHERE 
    fecha_ingreso IS NOT NULL  -- Solo solicitudes completadas
    AND estado_cumplimiento_sla IS NOT NULL
```

### Estados de Cumplimiento SLA

En la BD, el campo `estado_cumplimiento_sla` tiene valores como:

- ✅ `CUMPLE_SLA1`, `CUMPLE_SLA2`, ..., `CUMPLE_SLA6` → Cumplió el SLA
- ❌ `NO_CUMPLE_SLA1`, `NO_CUMPLE_SLA2`, ..., `NO_CUMPLE_SLA6` → Incumplió el SLA
- ⏳ `EN_PROCESO_SLA2`, `EN_PROCESO_SLA3`, `EN_PROCESO_SLA4` → Aún en proceso (no se usa para entrenamiento)

### Métricas del Modelo Actual

```
📊 Resultados del Entrenamiento:
- Muestras de entrenamiento: 1,651 solicitudes
- Precisión (Accuracy): 98.19%
- Algoritmo: RandomForestClassifier
- Número de árboles: 100
- Profundidad máxima: 10
```

### Reentrenamiento Automático

El modelo se puede reentrenar cuando:
- Se acumulan nuevas solicitudes completadas (mínimo 100 nuevas)
- Manualmente a través del endpoint `/modelo/reentrenar`
- El modelo tiene más de 30 días sin actualizarse

---

## 🔄 Flujo de Predicción

```
┌────────────────────────────────────────────────────────────────┐
│ 1. SOLICITUD ACTIVA EN LA BD                                  │
│    - ID: 9950                                                  │
│    - Fecha Solicitud: 2025-11-29                               │
│    - SLA: SLA1 (35 días)                                       │
│    - Rol: DevOps Engineer                                      │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│ 2. CÁLCULO DE CARACTERÍSTICAS                                  │
│    - Días transcurridos: 9 días (hoy: 2025-12-08)             │
│    - Días umbral: 35                                           │
│    - % usado: 25.7%                                            │
│    - ID Rol: 1                                                 │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│ 3. PREDICCIÓN DEL MODELO                                       │
│    El Random Forest analiza:                                   │
│    • Patrones históricos de solicitudes similares              │
│    • Comportamiento del rol DevOps Engineer                    │
│    • Porcentaje de tiempo consumido                            │
│    • 100 árboles de decisión votan                             │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│ 4. RESULTADO                                                   │
│    - Probabilidad de incumplir: 15% (0.15)                     │
│    - Nivel de riesgo: BAJO                                     │
│    - Factores: ["Menos de la mitad del tiempo consumido"]     │
│    - Días restantes: 26                                        │
│    - Recomendación: Monitorear normalmente                     │
└────────────────────────────────────────────────────────────────┘
```

---

## 📋 Tipos de SLA en el Sistema

| Código | Descripción | Días Umbral | Tipo Solicitud |
|--------|-------------|-------------|----------------|
| **SLA1** | Nuevo personal | 35 días | NUEVO |
| **SLA2** | Reemplazo | 20 días | REEMPLAZO |
| **SLA3** | Vacaciones | 48 días | NUEVO_INGRESO |
| **SLA4** | Proyecto interno | 15 días | NUEVO |
| **SLA5** | Proyecto crítico | 5 días | REEMPLAZO |
| **SLA6** | Consultoría externa | 25 días | NUEVO |

### Ejemplo Práctico por SLA

**SLA5 - Proyecto Crítico (5 días):**
```
Día 0: Solicitud creada → Riesgo BAJO (0%)
Día 3: 60% del tiempo → Riesgo MEDIO (45%)
Día 4: 80% del tiempo → Riesgo ALTO (75%)
Día 5: 100% del tiempo → Riesgo CRÍTICO (95%)
Día 6+: Vencida → 100% incumplimiento
```

**SLA1 - Nuevo Personal (35 días):**
```
Día 0-14: Riesgo BAJO (< 40% tiempo usado)
Día 15-24: Riesgo MEDIO (40-70% tiempo usado)
Día 25-32: Riesgo ALTO (70-90% tiempo usado)
Día 33+: Riesgo CRÍTICO (>90% tiempo usado)
Día 36+: Vencida → 100% incumplimiento
```

---

## 🚀 Endpoints de la API

### 1. Predicción Paginada
```http
GET /predecir/paginado?pagina=1&tamano=50&incluir_historicas=true&codigo_sla=SLA2
```

**Respuesta:**
```json
{
  "data": [
    {
      "id_solicitud": 9950,
      "codigo_sla": "SLA2",
      "nombre_rol": "DevOps Engineer",
      "probabilidad_incumplimiento": 0.15,
      "nivel_riesgo": "BAJO",
      "dias_restantes": 11,
      "fecha_prediccion": "2025-12-08T04:55:00",
      "factores_riesgo": ["Menos de la mitad del tiempo consumido"]
    }
  ],
  "pagina": 1,
  "tamano_pagina": 50,
  "total_registros": 1642,
  "total_paginas": 33
}
```

### 2. Predicciones Críticas (Dashboard)
```http
GET /predecir/criticas?limite=20
```

Retorna las 20 solicitudes con mayor riesgo (>70% del tiempo usado).

### 3. Predicción Individual
```http
POST /predecir
Content-Type: application/json

{
  "id_solicitud": 9950,
  "dias_transcurridos": 9,
  "dias_umbral": 35,
  "id_rol": 1
}
```

### 4. Resumen (KPIs)
```http
GET /resumen
```

**Respuesta:**
```json
{
  "total_analizadas": 100,
  "criticas": 25,
  "altas": 30,
  "medias": 20,
  "bajas": 25,
  "promedio_riesgo": 52.3
}
```

### 5. Reentrenar Modelo
```http
POST /modelo/reentrenar
```

Reentriena el modelo con los datos más recientes de la BD.

### 6. Filtros Disponibles
```http
GET /filtros
```

Retorna códigos SLA, roles y bloques tecnológicos activos.

---

## 🎯 Casos de Uso

### Caso 1: Alerta Preventiva
```
Solicitud #9876 - SLA5 (Proyecto Crítico - 5 días)
- Día 3 transcurrido (60% del tiempo)
- Modelo predice: 65% probabilidad de incumplir
- Nivel: ALTO
- Acción: Notificar al responsable para acelerar proceso
```

### Caso 2: Priorización de Trabajo
```
Dashboard muestra:
- 15 solicitudes en riesgo CRÍTICO
- 23 solicitudes en riesgo ALTO
- 45 solicitudes en riesgo MEDIO

El equipo puede enfocarse primero en las críticas para 
maximizar el cumplimiento de SLA.
```

### Caso 3: Análisis de Tendencias
```
El sistema detecta que:
- Rol "Data Analyst" tiene 15% más incumplimientos
- SLA4 (Proyecto Interno) tiene alta tasa de incumplimiento
- Noviembre tuvo picos de incumplimiento

Esto permite ajustar procesos o umbrales.
```

---

## ⚙️ Configuración Técnica

### Variables de Entorno (.env)
```env
# Base de datos
DB_SERVER=localhost
DB_PORT=1433
DB_NAME=Proyecto1SLA_DB
DB_USER=sa
DB_PASSWORD=tu_password

# Modelo
MODEL_PATH=./models/sla_predictor.pkl
LOG_LEVEL=INFO
```

### Requisitos (requirements.txt)
```
fastapi>=0.104.0
uvicorn>=0.24.0
scikit-learn>=1.3.0
pandas>=2.1.0
numpy>=1.24.0
sqlalchemy>=2.0.0
pyodbc>=5.0.0
pydantic>=2.4.0
python-dotenv>=1.0.0
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Instalar ODBC Driver 18 para SQL Server
RUN apt-get update && apt-get install -y curl apt-transport-https
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./app/
COPY models/ ./models/

# Puerto
EXPOSE 8000

# Ejecutar
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📈 Mejoras Futuras

### Corto Plazo
- [ ] Agregar más características (día de la semana, mes, urgencia)
- [ ] Incluir histórico del personal (experiencia, desempeño)
- [ ] Implementar alertas automáticas por email/Slack

### Mediano Plazo
- [ ] Modelo por tipo de SLA (un modelo especializado por cada SLA)
- [ ] Análisis de causas de incumplimiento (NLP en comentarios)
- [ ] Dashboard predictivo en tiempo real

### Largo Plazo
- [ ] Deep Learning (LSTM) para series temporales
- [ ] Optimización de asignación de recursos basada en predicciones
- [ ] Sistema de recomendaciones inteligente

---

## 🔍 Interpretación de Resultados

### ¿Qué hacer según el nivel de riesgo?

| Nivel | Acción Recomendada |
|-------|-------------------|
| **CRÍTICO** | Intervención inmediata: reasignar recursos, escalar prioridad, notificar gerencia |
| **ALTO** | Seguimiento diario, asignar recursos adicionales si es posible |
| **MEDIO** | Monitoreo activo, preparar plan de contingencia |
| **BAJO** | Seguimiento normal, parte del flujo regular |

### Factores que Aumentan el Riesgo

1. **Tiempo consumido**: A mayor % de tiempo usado, mayor riesgo
2. **Historial del rol**: Algunos roles históricamente incumplen más
3. **Tipo de SLA**: SLAs con umbrales cortos (SLA5: 5 días) son más sensibles
4. **Época del año**: Vacaciones y fin de año pueden aumentar riesgos

---

## 📞 Soporte

Para preguntas sobre el modelo o mejoras, contactar al equipo de Data Science.

**Versión del Modelo:** 1.0.0  
**Última actualización:** Diciembre 2025  
**Precisión actual:** 98.19%  
**Muestras de entrenamiento:** 1,651 solicitudes
