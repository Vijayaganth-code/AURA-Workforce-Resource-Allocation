"""Both models share one synthetic feature pipeline; retained as a convenience command."""
from .model_runtime import ensure_models
def train(): return ensure_models()
if __name__=='__main__': print(train())
