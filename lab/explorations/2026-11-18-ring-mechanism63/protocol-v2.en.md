# AS63-03 formal registration, revision 2: remove the energy-model confound

2026-11-18, before formal subjects. This amendment and the [complete initial protocol](protocol.en.md) jointly define the registered study. Materials, experience, measurements, decision rules, budgets and scope are unchanged except for energy simulation.

The initial apparatus check stopped as prescribed: under the old supply of one unit every 0.1 seconds, default 6.3 accumulated 0.1444327043300915 units of unmet demand in three internal seconds. The /1 energy model differs from the 6.3 local-field model; equal external supply is not equal usable energy. Preserve the full interrupted state and trace in `apparatus-v1/default63/normal`. No formal subjects had run.

Set `energy_simulation_enabled=False` in every formal condition so local supply differences cannot affect the formation/inheritance/expression comparison. This is the current 6.3 default and the original S101/bypass value; only the new /1 research copies change that flag relative to the old ring configuration. No production implementation or default changes. Preserve the supplier state; disabled energy simulation schedules no supply events.

T0 still requires all four /1 replays to reproduce archived channel activations and motor output at 600 samples within 1e-10. Thus removing energy computation must leave the old neural activity and proposed actions unchanged. Stop and retain evidence if this fails. Freeze all actual configurations, both language versions of the original protocol and this amendment, apparatus checks and implementation before formal execution.

The common energy condition now means absence of energy shortage, not equal numerical supply to different energy models. Conclusions are limited to this controlled mechanism comparison, not resource-constrained environments.
