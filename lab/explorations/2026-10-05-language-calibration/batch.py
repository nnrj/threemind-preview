"""Sequential phase dispatch; errors stop, completed immutable cases resume."""
import argparse
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['selection-and-formal','observation'])
    args=parser.parse_args()
    commands=([('experiment.py',op) for op in ('select-input','parameters','select-parameters','formal')] if args.phase=='selection-and-formal' else
              [('visual_reader.py',),('visual_reader.py','analyse'),('composition.py',),
               ('expression.py',),('expression.py','decode'),('interventions.py','formal'),
               ('interventions.py','composition'),('continuous.py',)])
    for command in commands:
        print('PHASE '+ ' '.join(command),flush=True)
        subprocess.run([sys.executable,str(HERE/command[0]),*command[1:]],check=True,cwd=HERE.parents[2])


if __name__=='__main__':main()
