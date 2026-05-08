import joblib
import os
import sys
import pickle
import xgboost
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer

# Dummy classes for unpickling
class DynamicClass:
    def __init__(self, *args, **kwargs): pass
    def __repr__(self): return f"<{self.__class__.__name__} instance>"

class ModelBundle(DynamicClass): pass
class Metrics(DynamicClass): pass

import __main__
__main__.ModelBundle = ModelBundle
__main__.Metrics = Metrics

def inspect_model(file_path):
    bundle = joblib.load(file_path)
    
    print("--- Model Bundle Overview ---")
    print(f"Model Name: {getattr(bundle, 'model_name', 'N/A')}")
    print(f"Target: {getattr(bundle, 'target', 'N/A')}")
    
    if hasattr(bundle, 'preprocess'):
        print("\n--- Preprocessing Pipeline ---")
        preprocessor = bundle.preprocess
        print(f"Type: {type(preprocessor)}")
        if isinstance(preprocessor, ColumnTransformer):
            for name, transformer, columns in preprocessor.transformers_:
                print(f"  Transformer '{name}' applied to columns: {columns[:10]}{'...' if len(columns) > 10 else ''}")

    if hasattr(bundle, 'xgb_clf'):
        print("\n--- XGBoost Classifier (Stage 1) ---")
        clf = bundle.xgb_clf
        if clf:
            print(f"Type: {type(clf)}")
            print(f"Params: {clf.get_params()}")

    if hasattr(bundle, 'xgb_reg_pos'):
        print("\n--- XGBoost Regressor (Stage 2) ---")
        reg = bundle.xgb_reg_pos
        if reg:
            print(f"Type: {type(reg)}")
            print(f"Params: {reg.get_params()}")

if __name__ == "__main__":
    inspect_model("delay_regressor.joblib")
