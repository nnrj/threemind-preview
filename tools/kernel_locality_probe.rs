//! Engineering instrumentation copied only into an ignored build workspace.
use std::cell::RefCell;
use std::time::Instant;
use serde_json::{json, Value};
const NAMES: &[&str] = &[__FUNCTION_NAMES__];
#[derive(Default, Clone)]
struct Row { calls: u64, inclusive: u128, exclusive: u128 }
#[derive(Default)]
struct Stats { stack: Vec<u128>, rows: Vec<Row>, pairs: u64, cohorts: u64 }
thread_local! { static STATS: RefCell<Stats> = RefCell::new(Stats::default()); }
pub struct Scope { id: usize, begin: Instant }
pub fn enter(id: usize) -> Scope {
    STATS.with(|s| s.borrow_mut().stack.push(0));
    Scope { id, begin: Instant::now() }
}
impl Drop for Scope {
    fn drop(&mut self) {
        let elapsed = self.begin.elapsed().as_nanos();
        STATS.with(|s| {
            let mut s = s.borrow_mut();
            let child = s.stack.pop().unwrap();
            if let Some(parent) = s.stack.last_mut() { *parent += elapsed; }
            s.rows.resize(NAMES.len(), Row::default());
            let row = &mut s.rows[self.id];
            row.calls += 1;
            row.inclusive += elapsed;
            row.exclusive += elapsed.saturating_sub(child);
        });
    }
}
pub fn add_pairs(n: usize) { STATS.with(|s| { let mut s=s.borrow_mut(); s.pairs+=(n*n) as u64; s.cohorts+=1; }); }
pub fn reset() { STATS.with(|s| *s.borrow_mut()=Stats::default()); }
pub fn result() -> Value { STATS.with(|s| {
    let s=s.borrow();
    json!({"cohort_pair_iterations":s.pairs,"cohort_count":s.cohorts,"functions":s.rows.iter().enumerate().filter(|(_,r)|r.calls>0).map(|(i,r)|json!({"name":NAMES[i],"calls":r.calls,"inclusive_s":r.inclusive as f64/1e9,"exclusive_s":r.exclusive as f64/1e9})).collect::<Vec<_>>()})
}) }
