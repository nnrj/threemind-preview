// Faithful scalar helpers for the historical /5.2 contribution model.
// These are not /5.3 rules; each accepted reinforcement retains its own age.
fn remaining52(curve: &str, age: f64) -> f64 {
    match curve {
        "exponential" => (-std::f64::consts::LN_2 * age).exp(),
        "power-law" => 1.0 / (1.0 + age),
        "inverse-logarithmic" => {
            let k=1.0_f64.exp_m1();
            let x=if age<1e300 { (k*age).ln_1p() } else { age.ln()+k.ln() };
            1.0/(1.0+x)
        },
        _ => unreachable!("validated curve"),
    }
}
fn ulp(x:f64)->f64 { f64::from_bits(x.to_bits()+1)-x }
// Non-overlapping partial sums retain the reference's accurately summed value.
fn sum52(values: impl Iterator<Item=f64>)->f64 {
    let mut parts:Vec<f64>=Vec::new();
    for mut x in values {
        let mut i=0;
        for j in 0..parts.len() {
            let mut y=parts[j];
            if x.abs()<y.abs() { std::mem::swap(&mut x,&mut y); }
            let hi=x+y; let lo=y-(hi-x);
            if lo!=0.0 { parts[i]=lo; i+=1; }
            x=hi;
        }
        parts.truncate(i);
        if x!=0.0 { parts.push(x); }
    }
    let Some(mut hi)=parts.pop() else {return 0.0;};
    let mut lo=0.0;
    while let Some(y)=parts.pop() {
        let x=hi; hi=x+y; lo=y-(hi-x);
        if lo!=0.0 {break;}
    }
    if parts.last().is_some_and(|p| (*p>0.0 && lo>0.0)||(*p<0.0 && lo<0.0)) {
        let y=lo*2.0; let x=hi+y;
        if y==x-hi { hi=x; }
    }
    hi
}
fn value52(curve:&str,parts:&[(f64,f64)],age:f64)->f64 {
    sum52(parts.iter().map(|(q,a)| q*remaining52(curve,a+age)))
}
fn assign52(curve:&str,parts:&mut Vec<(f64,f64)>,old:f64,value:f64) {
    if curve=="exponential" {return;}
    if value>old {
        let amount=(value-old).min((1.0-value52(curve,parts,0.0)).max(0.0));
        if amount>0.0 {
            if let Some(last)=parts.last_mut().filter(|x|x.1==0.0) { last.0+=amount; }
            else {parts.push((amount,0.0));}
        }
    } else if value<old {
        let ratio=if old>0.0 {value/old} else {0.0};
        for p in parts.iter_mut() {p.0*=ratio;}
        parts.retain(|p|p.0>0.0);
    }
}
impl Node {
    fn set_persistent(&mut self,value:f64) {
        assign52(&self.decay_curve,&mut self.decay_contributions,self.support,value);
        self.support=value;
    }
}
impl Edge {
    fn set_persistent(&mut self,value:f64) {
        assign52(&self.decay_curve,&mut self.decay_contributions,self.weight,value);
        self.weight=value;
    }
}
impl Settings {
    fn decay_parameters52(&self)->Retention {
        let mut r=self.r.clone();
        if self.value["retention_relaxation_enabled"]==false {r.memory_half_life_decay_rate=0.0;}
        r
    }
    fn age52(&self,h:f64,dt:f64)->(f64,f64) {
        let r=self.decay_parameters52();
        let rate=r.memory_half_life_decay_rate;
        let end=r.memory_half_life_min_s.max(h-rate*dt);
        let falling=if rate>0.0 {dt.min((h-r.memory_half_life_min_s)/rate)} else {0.0};
        let age=(if falling>0.0 {(rate*falling/end).ln_1p()/rate} else {0.0})+(dt-falling)/end;
        (age,end)
    }
    fn decay52(&self,q:f64,h:f64,dt:f64,parts:&mut Vec<(f64,f64)>)->(f64,f64) {
        let curve=self.value["decay_curve"].as_str().unwrap();
        if curve=="exponential" {return decay(q,h,dt,&self.decay_parameters52());}
        let (age,end)=self.age52(h,dt);
        let mut merged:Vec<(f64,f64)>=Vec::with_capacity(parts.len());
        for &(amount,old_age) in parts.iter() {
            let next=old_age+age;
            if let Some(last)=merged.last_mut().filter(|p|p.1==next) {last.0+=amount;}
            else {merged.push((amount,next));}
        }
        *parts=merged;
        (value52(curve,parts,0.0),end)
    }
    fn crossing52(&self,q:f64,h:f64,floor:f64,state:u128,parts:&[(f64,f64)])->Option<f64> {
        if floor<=0.0 {return None;}
        let curve=self.value["decay_curve"].as_str().unwrap();
        let r=self.decay_parameters52();
        if curve=="exponential" {return crossing(q,h,floor,&r);}
        let horizon=(u128::MAX-state) as f64/1e6;
        let (maximum,_)=self.age52(h,horizon);
        let needed=if value52(curve,parts,0.0)<=floor {0.0} else {
            if value52(curve,parts,maximum)>floor {return None;}
            let mut low=0.0; let mut high=maximum.min(1.0);
            while value52(curve,parts,high)>floor {high=maximum.min(high*2.0);}
            for _ in 0..100 {
                let mid=(low+high)/2.0;
                if value52(curve,parts,mid)>floor {low=mid;} else {high=mid;}
            }
            high
        };
        let rate=r.memory_half_life_decay_rate;
        let seconds=if rate==0.0 {h*needed} else {
            let falling=(h/r.memory_half_life_min_s).ln()/rate;
            if needed<=falling {h*-(-rate*needed).exp_m1()/rate}
            else {(h-r.memory_half_life_min_s)/rate+(needed-falling)*r.memory_half_life_min_s}
        };
        let delta=(seconds*1e6).ceil();
        if !delta.is_finite() || delta>=u128::MAX as f64 {return None;}
        state.checked_add((delta as u128).saturating_add(1).max(1))?;
        Some(seconds)
    }
    fn validate_trace(&self,q:f64,curve:&str,parts:&[(f64,f64)],elapsed:u128)->Result<()> {
        if self.value["decay_curve"]!=curve {return Err("object curve disagrees with definition".into());}
        if curve=="exponential" {
            return if parts.is_empty() {Ok(())} else {Err("exponential objects must use scalar representation".into())};
        }
        let mut prior=f64::INFINITY;
        for &(amount,age) in parts {
            if !amount.is_finite() || amount<=0.0 || !age.is_finite() || age<0.0 || age>=prior || age>elapsed as f64*1.000001 {
                return Err("invalid contribution history".into());
            }
            prior=age;
        }
        let value=value52(curve,parts,0.0);
        if (value-q).abs()>(1e-15_f64).max(2e-12*value.abs().max(q.abs())) {
            return Err("persistent value disagrees with contribution history".into());
        }
        Ok(())
    }
}
