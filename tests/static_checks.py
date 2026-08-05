from pathlib import Path
import py_compile, yaml
ROOT=Path(__file__).parents[1]
for addon in ('esp_manager','esp_manager_dev'):
    base=ROOT/addon
    py_compile.compile(str(base/'app/main.py'),doraise=True)
    cfg=yaml.safe_load((base/'config.yaml').read_text())
    assert cfg['slug'] in ('esp_manager','esp_manager_dev')
    assert (base/'CHANGELOG.md').exists()
    assert 'PROJECT_HANDOVER.txt' in [p.name for p in ROOT.iterdir()]
    assert (base/'app/templates/src/main.cpp').exists()
print('static checks passed')
