"""Final bounded comparison and remaining Core cases; never run with another worker."""
from next_steps import run

if __name__=='__main__':
    run('legacy_comparison.py')
    run('teaching.py','--owner',223,'--condition','cycle1')
    run('teaching.py','--owner',223,'--condition','no-learning')
    run('additional.py')
