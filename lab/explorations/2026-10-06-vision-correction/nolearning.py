"""Matched classroom without Core structural learning; own equally fitted reader.

Not a claim that all transient node history disappears. Sensory stimulation,
activation, inhibition and local recovery continue. Old studies are untouched.
"""
from experiment import study,WORK,teach,collect,correct
from shared import fit,test


def main():
    s=study();n=4
    try:
        s.allow_extension()
        steps=[('nolearning',lambda:teach(s,n,source='nolearning',plasticity=False)),
               ('nolearning-calibration',lambda:collect(s,n,'calibration','nolearning')),
               ('nolearning-exposure',lambda:correct(s,n,False,base='nolearning')),
               ('nolearning-exposure-practice',lambda:collect(s,n,'practice','nolearning-exposure')),
               ('nolearning-exposure-shared-fit',lambda:fit(s,n,'nolearning-exposure')),
               ('nolearning-exposure-shared-confirmation-normal',lambda:test(s,n,'nolearning-exposure','normal'))]
        for key,run in steps:
            if not (WORK/f'cases/r{n}-{key}/result.json').exists():run()
    finally:s.db.close()

if __name__=='__main__':main()
