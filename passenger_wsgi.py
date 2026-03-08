
import os
import sys

print("___________________________________________________________")
print("Incializando...")

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

application = create_app()