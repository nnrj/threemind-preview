"""Streaming Ocean/3 sensory/action measurements, external to Core.

The recorded raw layout shares nutrient sectors 1..4 and relative water velocity
5..6 (scale .03 m/s) with the versioned group apparatus. Samples are observations,
not independent organisms and not a causal proof of purposeful food seeking.
"""
from collections import defaultdict
import gzip
import json
import math


def food_heading(path, cohorts):
    totals=defaultdict(lambda:defaultdict(float))
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            for item in json.loads(line)['inputs']:
                values=totals[cohorts[item['individual']]]
                raw=item['raw'];action=item['action']
                gx,gy=raw[1]-raw[3],raw[2]-raw[4]
                gradient=math.hypot(gx,gy);speed=math.hypot(action[0],action[1])
                values['all_samples']+=1
                values['action_square']+=sum(x*x for x in action)
                if gradient<=1e-10:continue
                toward=(gx*action[0]+gy*action[1])/gradient
                values['gradient_samples']+=1;values['toward_command']+=toward
                values['toward_velocity_m_s']+=.03*(gx*raw[5]+gy*raw[6])/gradient
                if speed>1e-10:
                    values['moving_command_samples']+=1
                    values['command_alignment']+=toward/speed
    return {k:{'samples':int(v['all_samples']),'gradient_samples':int(v['gradient_samples']),
        'mean_action_square':v['action_square']/max(v['all_samples'],1),
        'toward_command':v['toward_command']/max(v['gradient_samples'],1),
        'toward_velocity_m_s':v['toward_velocity_m_s']/max(v['gradient_samples'],1),
        'command_alignment':v['command_alignment']/max(v['moving_command_samples'],1)} for k,v in totals.items()}
