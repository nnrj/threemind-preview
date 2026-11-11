# Why equal initial halving times give different long-term retention

2026-11-10. This note directly evaluates the three existing 5.2 formulas; scientific N is zero. It explains their properties without changing the R46a/R46b criteria. `decay_lifetime_note.py` generates the numerical record and PNG/SVG/PDF figures and checks each threshold time by substitution into the original formula.

Let a newly formed weight contribution have initial value $w_0$, constant decay timescale $H$, elapsed time $t$, and normalized age $a=t/H$. Consider one contribution whose endpoints remain present, with no further reinforcement or damage. The three 5.2 curves are:

\[
w_{\mathrm{exp}}(t)=w_0 2^{-a},\qquad
w_{\mathrm{power}}(t)=\frac{w_0}{1+a},\qquad
w_{\mathrm{log}}(t)=\frac{w_0}{1+\ln[1+(e-1)a]}.
\]

All three reach half their initial value at $t=H$, but their later decay differs. Exponential decay halves the remaining value during every additional interval $H$; subsequent halving intervals increase for the other two curves. “Decay mechanism” therefore names the overall choice, “half-life” remains appropriate for the exponential parameter, and “decay timescale” describes the parameter across mechanisms. The separate relaxation switch controls whether that timescale decreases with elapsed time.

For a threshold $p<w_0$, the times to reach it are:

\[
T_{\mathrm{exp}}=H\log_2(w_0/p),\quad
T_{\mathrm{power}}=H(w_0/p-1),\quad
T_{\mathrm{log}}=\frac{H\{\exp(w_0/p-1)-1\}}{e-1}.
\]

With the R46 lower timescale $H=30$ seconds and weight threshold $p=0.008$:

| Initial weight | Exponential | Power law | Present inverse-logarithmic form |
| --- | --- | --- | --- |
| 0.01 | 9.66 s | 7.50 s | 4.96 s |
| 0.02 | 39.66 s | 45.00 s | 60.79 s |
| 0.05 | 79.32 s | 157.50 s | 3309.69 s |
| 0.10 | 109.32 s | 345.00 s | approximately 19.95 days |
| 0.20 | 139.32 s | 720.00 s | approximately 14,700 years |

**The mathematical result is that equal initial halving times do not imply comparable long-term retention. The present inverse-logarithmic formula greatly amplifies initial-weight differences into differences in threshold lifetime; the power law does so more moderately, whereas exponential threshold lifetime increases logarithmically with initial weight.** Close to the deletion threshold, the inverse-logarithmic curve can reach that threshold sooner than the exponential curve, so it is not slower at every stage.

This calculation helps explain the R46a combination in which inverse-logarithmic decay retained repeated experience but missed some weak-input forgetting and 30-day fading targets. Choosing a default requires evaluating longer retention together with weak-experience forgetting, rule updating and eventual fading.

The table gives solutions under the stated conditions. Real connections contain contributions of different ages and are affected by endpoint survival, subsequent input, transmission and damage. Observed survival and conditional 30-day projections in the experiment reports remain calculated from their own originals. Learning and rule reversal with complete personal adapters retain their separately registered behavioral tests.
