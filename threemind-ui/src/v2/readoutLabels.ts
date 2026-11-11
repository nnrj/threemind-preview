export const classes: Record<string, string> = {
  converged: "活动稳态",
  oscillatory: "候选集合周期重复",
  residual_decay: "幅度衰减",
  pattern_converged: "响应模式收敛",
  periodic_activity: "周期活动",
  response_ended: "响应结束",
  transient: "无持续尾段",
  unresolved: "窗内未定",
  censored: "观察删失",
  interrupted: "观察中断",
  not_observed: "未观察",
};

export const localStates: Record<string, string> = {
  local_steady: "局部稳态",
  local_pattern: "局部模式稳定，幅度仍变化",
  changing: "仍在变化",
  insufficient_span: "连续观察长度不足",
  below_activity_floor: "低于活动分析下限",
  activity_interrupted: "稳定窗口内活动曾中断",
  not_observed: "未观察",
};
