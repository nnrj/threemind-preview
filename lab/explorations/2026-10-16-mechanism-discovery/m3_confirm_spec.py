"""New-origin confirmation of the existing cross-system-criteria/2 measurements."""
N=64
SEED_START=1096100
RIG_ORIGIN_OFFSET=60000  # closure_rig.case_seed('X3', offset+i) == SEED_START+i
APPARATUS_SEED=1096002
TEST_SEED=1096004
KINDS=('reactive','finite-state','hebbian','fixed-rnn-reader','threemind')
MIN_PASS=48
MIN_PAIRED_ADVANTAGE=.10
ARMS=('intact','sham','target','matched','restored','all')
SEQUENCES=('PPP','PQP','QQQ','QPQ')


def cases():
    return [{'origin':i,'seed':SEED_START+i,'rig_origin':RIG_ORIGIN_OFFSET+i,
             'systems':list(KINDS)} for i in range(N)]
