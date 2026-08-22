from pathlib import Path
import re
P=Path(__file__).parents[1]/'tools/promote_dev_to_stable_v0_12_2.py'
V=Path(__file__).parents[1]/'tools/validate_v0_12_2_promotion.py'
def test_promotion_preserves_separation_and_full_copy():
 s=P.read_text();assert 'shutil.copytree(dev, stable' in s;assert '/config/esp_manager' in s;assert '8099' in s;assert 'promotion_backup_0.12.2' in s
def test_regression_and_api_validation():
 s=V.read_text();assert r'const\s+char\s*\*=' in s
 for x in ['registerSensor','registerBinarySensor','registerSwitch','registerNumber','registerCover','publishState']:assert x in s
def test_project_memory_append_only_entries():
 s=P.read_text();assert 'DECISIONS.jsonl' in s;assert 'INCIDENTS.jsonl' in s;assert 'RELEASE_LEDGER.jsonl' in s
