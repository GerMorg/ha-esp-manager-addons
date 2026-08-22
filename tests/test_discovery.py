from pathlib import Path
import sys,tempfile,json
sys.path.insert(0,str(Path(__file__).parents[1]/'payload/app'))
import discovery
def test_all_types_generate():
 x=json.loads((Path(__file__).parents[1]/'EXAMPLE_DISCOVERY.json').read_text())
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'x.h';discovery.generate(x,p);s=p.read_text()
  for token in ['registerSensor','registerBinarySensor','registerSwitch','registerNumber','registerCover','bedroom_blind']:assert token in s
def test_duplicate_unique_id_rejected():
 try:discovery.validate([{'type':'sensor','id':'a','unique_id':'x'},{'type':'sensor','id':'b','unique_id':'x'}])
 except ValueError:return
 assert False
