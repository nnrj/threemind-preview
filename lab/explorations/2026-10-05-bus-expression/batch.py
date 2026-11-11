"""One GPU worker; durable per-model completion records permit bounded resume."""
import argparse
from common import *
from calibrate import run
from coverage import run as cover
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('confirmation','coverage'));args=p.parse_args()
    if args.phase=='confirmation':
        for owner in (251,279):run(owner,'balanced')
    else:
        cover(223,'late');cover(223,'times')
        cover(223,'correction',WORK/'models/s223-balanced.safetensors')
        cover(223,'correction')
