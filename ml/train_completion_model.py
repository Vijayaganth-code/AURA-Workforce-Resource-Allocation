"""Create/load the two AURA runtime model artifacts and report honest metrics."""
from .model_runtime import ensure_models
def train(): return ensure_models()
if __name__=='__main__': print(train())
