"""
Modelo de Machine Learning para predicción de SLA
"""
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from .config import get_settings
from .database import get_datos_entrenamiento

logger = logging.getLogger(__name__)
settings = get_settings()

# Variables globales para el modelo (singleton)
_modelo: Optional[Pipeline] = None
_modelo_timestamp: Optional[float] = None
_modelo_accuracy: Optional[float] = None


def calcular_nivel_riesgo(probabilidad: float) -> str:
    """
    Calcula el nivel de riesgo basado en la probabilidad de incumplimiento.
    
    Args:
        probabilidad: Probabilidad entre 0 y 1
    
    Returns:
        Nivel de riesgo: CRITICO, ALTO, MEDIO o BAJO
    """
    if probabilidad >= 0.8:
        return "CRITICO"
    elif probabilidad >= 0.6:
        return "ALTO"
    elif probabilidad >= 0.4:
        return "MEDIO"
    return "BAJO"


def identificar_factores_riesgo(
    dias_transcurridos: float,
    dias_umbral: float,
    probabilidad: float
) -> List[str]:
    """
    Identifica los factores que contribuyen al riesgo.
    
    Returns:
        Lista de factores de riesgo identificados
    """
    factores = []
    
    porcentaje_tiempo = (dias_transcurridos / dias_umbral) * 100 if dias_umbral > 0 else 0
    
    if porcentaje_tiempo >= 90:
        factores.append("Tiempo casi agotado (>90%)")
    elif porcentaje_tiempo >= 70:
        factores.append("Tiempo elevado (>70%)")
    
    if probabilidad >= 0.8:
        factores.append("Alta probabilidad histórica de incumplimiento")
    
    if dias_umbral <= 3:
        factores.append("SLA con umbral muy corto")
    
    return factores


def entrenar_modelo(datos: Optional[List[Dict]] = None) -> Tuple[Pipeline, float]:
    """
    Entrena el modelo de predicción con datos históricos.
    
    Args:
        datos: Datos de entrenamiento (opcional, se obtienen de BD si no se proveen)
    
    Returns:
        Tupla (modelo entrenado, accuracy)
    """
    logger.info("Iniciando entrenamiento del modelo...")
    
    # Obtener datos si no se proveen
    if datos is None:
        datos = get_datos_entrenamiento(limite=settings.max_training_samples)
    
    if len(datos) < 50:
        logger.warning(f"Pocos datos para entrenar ({len(datos)}), usando modelo base")
        # Crear modelo con parámetros mínimos
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', RandomForestClassifier(
                n_estimators=10,
                max_depth=5,
                random_state=42
            ))
        ])
        # Datos dummy para inicializar
        X_dummy = np.array([[1, 5, 1], [2, 5, 1], [3, 5, 1], [4, 5, 1], [5, 5, 1]])
        y_dummy = np.array([0, 0, 0, 1, 1])
        pipeline.fit(X_dummy, y_dummy)
        return pipeline, 0.0
    
    # Preparar datos
    X = np.array([
        [d['dias_transcurridos'], d['dias_umbral'], d['id_rol']] 
        for d in datos
    ])
    y = np.array([d['incumplio'] for d in datos])
    
    # Dividir en train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )
    
    # Crear pipeline
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            n_jobs=-1,  # Usar todos los cores
            random_state=42,
            class_weight='balanced'  # Balancear clases
        ))
    ])
    
    # Entrenar
    pipeline.fit(X_train, y_train)
    
    # Evaluar
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info(f"Modelo entrenado - Accuracy: {accuracy:.2%}, Samples: {len(datos)}")
    
    return pipeline, accuracy


def get_modelo() -> Pipeline:
    """
    Obtiene el modelo de predicción.
    Carga desde archivo o entrena si es necesario.
    Implementa patrón singleton con recarga periódica.
    
    Returns:
        Modelo entrenado listo para predicciones
    """
    global _modelo, _modelo_timestamp, _modelo_accuracy
    
    now = datetime.now().timestamp()
    
    # Verificar si necesita recargar
    necesita_recargar = (
        _modelo is None or
        _modelo_timestamp is None or
        (now - _modelo_timestamp) > settings.model_reload_interval
    )
    
    if not necesita_recargar:
        return _modelo
    
    model_path = settings.model_path
    
    # Intentar cargar modelo existente
    if os.path.exists(model_path):
        try:
            _modelo = joblib.load(model_path)
            _modelo_timestamp = now
            logger.info(f"Modelo cargado desde {model_path}")
            return _modelo
        except Exception as e:
            logger.warning(f"Error al cargar modelo: {e}, entrenando nuevo...")
    
    # Entrenar nuevo modelo
    _modelo, _modelo_accuracy = entrenar_modelo()
    _modelo_timestamp = now
    
    # Guardar modelo
    try:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(_modelo, model_path)
        logger.info(f"Modelo guardado en {model_path}")
    except Exception as e:
        logger.error(f"Error al guardar modelo: {e}")
    
    return _modelo


def predecir(
    dias_transcurridos: float,
    dias_umbral: float,
    id_rol: int
) -> Tuple[float, str, List[str]]:
    """
    Realiza una predicción individual.
    
    Args:
        dias_transcurridos: Días desde la creación de la solicitud
        dias_umbral: Días límite del SLA
        id_rol: ID del rol responsable
    
    Returns:
        Tupla (probabilidad, nivel_riesgo, factores)
    """
    modelo = get_modelo()
    
    X = np.array([[dias_transcurridos, dias_umbral, id_rol]])
    
    # Obtener probabilidad de incumplimiento (clase 1)
    probabilidades = modelo.predict_proba(X)
    probabilidad = float(probabilidades[0][1]) if probabilidades.shape[1] > 1 else float(probabilidades[0][0])
    
    nivel_riesgo = calcular_nivel_riesgo(probabilidad)
    factores = identificar_factores_riesgo(dias_transcurridos, dias_umbral, probabilidad)
    
    return probabilidad, nivel_riesgo, factores


def predecir_batch(solicitudes: List[Dict]) -> List[Dict]:
    """
    Realiza predicciones en batch (más eficiente).
    
    Args:
        solicitudes: Lista de solicitudes con dias_transcurridos, dias_umbral, id_rol
    
    Returns:
        Lista de resultados con probabilidad y nivel de riesgo
    """
    if not solicitudes:
        return []
    
    modelo = get_modelo()
    
    # Preparar datos
    X = np.array([
        [s['dias_transcurridos'], s['dias_umbral'], s['id_rol']] 
        for s in solicitudes
    ])
    
    # Predicción batch
    probabilidades = modelo.predict_proba(X)
    probs = probabilidades[:, 1] if probabilidades.shape[1] > 1 else probabilidades[:, 0]
    
    # Construir resultados
    resultados = []
    for sol, prob in zip(solicitudes, probs):
        prob_float = float(prob)
        resultados.append({
            'id_solicitud': sol['id_solicitud'],
            'codigo_sla': sol.get('codigo_sla'),
            'nombre_rol': sol.get('nombre_rol'),
            'probabilidad_incumplimiento': round(prob_float, 4),
            'nivel_riesgo': calcular_nivel_riesgo(prob_float),
            'dias_restantes': sol.get('dias_restantes'),
            'factores_riesgo': identificar_factores_riesgo(
                sol['dias_transcurridos'],
                sol['dias_umbral'],
                prob_float
            )
        })
    
    return resultados


def forzar_reentrenamiento() -> Dict:
    """
    Fuerza el reentrenamiento del modelo.
    
    Returns:
        Información del reentrenamiento
    """
    global _modelo, _modelo_timestamp, _modelo_accuracy
    
    datos = get_datos_entrenamiento(limite=settings.max_training_samples)
    _modelo, _modelo_accuracy = entrenar_modelo(datos)
    _modelo_timestamp = datetime.now().timestamp()
    
    # Guardar modelo
    try:
        os.makedirs(os.path.dirname(settings.model_path), exist_ok=True)
        joblib.dump(_modelo, settings.model_path)
    except Exception as e:
        logger.error(f"Error al guardar modelo: {e}")
    
    return {
        "samples_used": len(datos),
        "accuracy": _modelo_accuracy,
        "timestamp": datetime.now()
    }


def modelo_esta_cargado() -> bool:
    """Verifica si el modelo está cargado en memoria"""
    return _modelo is not None


def get_modelo_info() -> Dict:
    """Obtiene información del modelo actual"""
    return {
        "loaded": _modelo is not None,
        "timestamp": datetime.fromtimestamp(_modelo_timestamp) if _modelo_timestamp else None,
        "accuracy": _modelo_accuracy,
        "path": settings.model_path
    }
