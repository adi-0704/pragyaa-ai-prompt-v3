import joblib
import os
import sys
import pickle

# A dynamic class factory to handle missing classes during unpickling
class DynamicClass:
    def __init__(self, *args, **kwargs):
        pass
    def __repr__(self):
        return f"<{self.__class__.__name__} instance>"

def find_class(module, name):
    if module == '__main__':
        # Create a new class dynamically if it doesn't exist
        if name not in globals():
            globals()[name] = type(name, (DynamicClass,), {})
        return globals()[name]
    return pickle.Unpickler.find_class(pickle._Unpickler, module, name)

# Joblib uses its own loader, but we can try to monkeypatch or use standard pickle for structural inspection
# Note: joblib.load is more than just pickle.load, but for simple structural inspection pickle might work.
# However, joblib files are often split into multiple files if they contain large arrays.
# Let's try to just populate __main__ with common names or use a more robust monkeypatch.

class CatchAllModule:
    def __getattr__(self, name):
        if name not in globals():
            globals()[name] = type(name, (DynamicClass,), {})
        return globals()[name]

import __main__
# This is tricky because we can't easily override __getattr__ on a module.
# Let's just define the ones we've seen and maybe a few more likely ones.
class ModelBundle(DynamicClass): pass
class Metrics(DynamicClass): pass
class Model(DynamicClass): pass
class Regressor(DynamicClass): pass

__main__.ModelBundle = ModelBundle
__main__.Metrics = Metrics
__main__.Model = Model
__main__.Regressor = Regressor

def inspect_joblib(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        # Try joblib load with the classes we've defined
        model = joblib.load(file_path)
        print(f"Object Type: {type(model)}")
        
        print("\nObject Attributes and Values:")
        for attr in dir(model):
            if not attr.startswith('__'):
                try:
                    val = getattr(model, attr)
                    val_str = str(val)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    print(f"  {attr}: {type(val)} = {val_str}")
                except Exception as attr_err:
                    print(f"  {attr}: Error reading attribute: {attr_err}")

    except Exception as e:
        print(f"Error loading or inspecting file: {e}")
        print("\nAttempting to list common scikit-learn types if it's a wrapper...")

if __name__ == "__main__":
    inspect_joblib("delay_regressor.joblib")
