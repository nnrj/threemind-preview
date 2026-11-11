"""Explicit simulated damped mechanical oscillator and a fixed acoustic filterbank.

This external adapter supplies measured spectral energy, never a named note or
an object identity. It is not a MuJoCo acoustic field or biological cochlea.
"""
import math
from dataclasses import dataclass

import numpy as np

from threemind_core import Stimulus
from threemind_runtime.receptors import ReceptorWiring


@dataclass(frozen=True)
class OscillatorSensor:
    seed: int
    sample_rate: int = 8000
    seconds: float = 0.125
    bands_hz: tuple = (110, 165, 220, 330, 440, 660, 880, 1320)
    schema: str = 'threemind.oscillator-sensor/1'

    def sample(self, mass_kg, stiffness_n_m, damping_s=6.0):
        if not (mass_kg>0 and stiffness_n_m>0 and damping_s>=0):
            raise ValueError('physical oscillator parameters')
        natural=math.sqrt(stiffness_n_m/mass_kg)
        if damping_s>=natural:
            raise ValueError('this adapter requires underdamped motion')
        t=np.arange(round(self.sample_rate*self.seconds))/self.sample_rate
        displacement=np.exp(-damping_s*t)*np.cos(math.sqrt(natural**2-damping_s**2)*t)
        spectrum=np.abs(np.fft.rfft(displacement*np.hanning(len(t))))**2
        hz=np.fft.rfftfreq(len(t),1/self.sample_rate)
        filters=np.exp(-0.5*(np.log(np.maximum(hz,1)[None,:]/np.array(self.bands_hz)[:,None])/0.14)**2)
        values=filters@spectrum
        values=values/max(float(values.sum()),1e-20)
        return {'schema':self.schema,'mass_kg':mass_kg,'stiffness_n_m':stiffness_n_m,'damping_s':damping_s,
                'sample_rate_hz':self.sample_rate,'duration_s':self.seconds,'displacement_normalized':displacement.tolist(),
                'spectral_fractions':values.tolist(),'bands_hz':self.bands_hz,
                'physical_scope':'analytical damped oscillator; not a full environmental sound field'}

    def frame(self, observation):
        if observation['schema']!=self.schema:raise ValueError('sound mapping version')
        wiring=ReceptorWiring(self.seed)
        return Stimulus(0,tuple((wiring.identity(0xE00000+i),float(v)) for i,v in enumerate(observation['spectral_fractions']) if v))
