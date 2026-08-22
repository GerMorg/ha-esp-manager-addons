from app.core import validate_entities,render_entities
from pathlib import Path
import tempfile
def test_validation_and_generation():
 x=validate_entities([{"type":"switch","id":"led","name":"LED","unique_id":"demo_led"},{"type":"number","id":"interval","name":"Intervall","unique_id":"demo_interval","min":100,"max":5000,"step":100,"unit":"ms"}])
 with tempfile.TemporaryDirectory() as d:
  p=Path(d);render_entities(p,{"mqtt_entities":x});s=(p/"include/ESPManagerEntities.h").read_text();assert "registerSwitch" in s and "registerNumber" in s
def test_ui_contract():
 s=Path("app/static/index.html").read_text()+Path("app/static/app.js").read_text()
 for x in ["MQTT Discovery – Entitäten","addEntity","saveEntities","binary_sensor","cover"]:assert x in s
