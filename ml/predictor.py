import numpy as np
import pandas as pd

class MLPredictor:
    """
    Evaluates the probability of a setup's success.
    In a fully productionized system, this loads a trained XGBoost or Random Forest model.
    Here we implement a robust heuristic placeholder representing ML weights until model is trained.
    """
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.is_trained = False
        # Placeholder for self.model = xgb.Booster() etc.

    def extract_features_for_inference(self, df, index):
        """Extract exact row features for ML input."""
        row = df.iloc[index]
        return {
            'body_ratio': row.get('body_ratio', 0.5),
            'wick_ratio': max(row.get('lower_wick_ratio', 0), row.get('upper_wick_ratio', 0)),
            'volume_spike': row.get('volume_spike_ratio', 1.0),
            'trend_strength': row.get('roc_14', 0.0)
        }

    def predict_probability(self, features, signal_type):
        """
        Returns a probability score between 0 and 100%.
        For the demo, computes a score based on heuristic weights 
        that mimic what an ML model would learn for these features.
        """
        score = 50.0 # Base chance
        
        # ML models learn that strong volume + strong rejection wicks in direction of trend = high probability
        if features['volume_spike'] > 1.5:
            score += 10
        elif features['volume_spike'] > 2.0:
            score += 20
            
        if features['wick_ratio'] > 0.6:
            score += 15
            
        if features['body_ratio'] < 0.3:
            score += 5
            
        # Add some noise to simulate ML confidence variability
        noise = np.random.uniform(-5, 5)
        
        final_score = min(99.0, max(1.0, score + noise))
        return round(final_score, 2)
