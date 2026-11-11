"""Reuse audited whole-window ranking; preserve all nonconverged observations."""
import importlib.util
from run import HERE,ROOT,sha

path=HERE.parent/'2026-09-10-pair-no-punctuation/analyze.py'
loader=importlib.util.spec_from_file_location('pair_analysis',path)
base=importlib.util.module_from_spec(loader);loader.loader.exec_module(base)

if __name__=='__main__':base.analyze()
