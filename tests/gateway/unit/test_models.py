import pytest
from app.models.application import Application

def test_application_model_init():
    app = Application(name="test-app", api_key="secret-key")
    assert app.name == "test-app"
    assert app.api_key == "secret-key"
