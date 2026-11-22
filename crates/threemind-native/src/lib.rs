use pyo3::exceptions::PyValueError;
mod continuous;
mod legacy;
mod local;
mod lif;
use pyo3::prelude::*;
use threemind_core::{parse_time, Config, Engine, State, Stimulus};

fn err(e: impl ToString) -> PyErr {
    PyValueError::new_err(e.to_string())
}

#[pyclass]
struct NativeEngine {
    inner: Engine,
}
#[pymethods]
impl NativeEngine {
    #[new]
    #[pyo3(signature = (config_json, state_json=None))]
    fn new(config_json: &str, state_json: Option<&str>) -> PyResult<Self> {
        let inner = if let Some(state) = state_json {
            Engine::restore(serde_json::from_str::<State>(state).map_err(err)?)
        } else {
            Engine::new(serde_json::from_str::<Config>(config_json).map_err(err)?)
        }
        .map_err(err)?;
        Ok(Self { inner })
    }
    fn time_us(&self) -> String {
        self.inner.time.to_string()
    }
    fn sequence(&self) -> u64 {
        self.inner.sequence
    }
    fn life(&self) -> String {
        self.inner.life.clone()
    }
    fn config_json(&self) -> String {
        serde_json::to_string(&self.inner.config).unwrap()
    }
    fn state_json(&self) -> String {
        serde_json::to_string(&self.inner.capture()).unwrap()
    }
    fn metrics_json(&self) -> String {
        self.inner.metrics().to_string()
    }
    fn spatial_geometry_json(&self) -> PyResult<String> {
        self.inner
            .spatial_geometry()
            .map(|v| v.to_string())
            .map_err(err)
    }
    fn graph_json(&self, limit: Option<usize>) -> String {
        self.inner.graph(limit).to_string()
    }
    fn activations(&self) -> Vec<(u64, f64)> {
        self.inner.activations()
    }
    fn observation_nodes_json(&self) -> String {
        serde_json::to_string(&self.inner.observation_nodes()).unwrap()
    }
    fn induced_edges_json(&self, node_ids: Vec<u64>) -> String {
        serde_json::to_string(&self.inner.induced_edges(node_ids)).unwrap()
    }
    fn inject(&mut self, payload: &str) -> PyResult<u64> {
        self.inner
            .inject(serde_json::from_str::<Stimulus>(payload).map_err(err)?)
            .map_err(err)
    }
    fn close_inputs(&mut self) {
        self.inner.close_inputs();
    }
    fn supply_energy(&mut self, time: &str, amount: f64, source: String) -> PyResult<u64> {
        self.inner
            .supply_energy(parse_time(time).map_err(err)?, amount, source)
            .map_err(err)
    }
    fn reconfigure(&mut self, config_json: &str) -> PyResult<()> {
        self.inner
            .reconfigure(serde_json::from_str::<Config>(config_json).map_err(err)?)
            .map_err(err)
    }
    fn modulate_input(&mut self, time: &str, payload: &str) -> PyResult<u64> {
        self.inner
            .modulate_input(
                parse_time(time).map_err(err)?,
                serde_json::from_str(payload).map_err(err)?,
            )
            .map_err(err)
    }
    #[pyo3(signature = (nodes, edges, lesion=false, action=None))]
    fn intervene(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        lesion: bool,
        action: Option<String>,
    ) -> PyResult<()> {
        if let Some(action) = action {
            if lesion {
                return Err(err("use either action or legacy lesion, not both"));
            }
            self.inner
                .intervene_action(nodes, edges, &action)
                .map_err(err)
        } else {
            self.inner.intervene(nodes, edges, lesion).map_err(err)
        }
    }
    #[pyo3(signature = (target, record, inputs_only=false))]
    fn advance(
        &mut self,
        py: Python<'_>,
        target: &str,
        record: bool,
        inputs_only: bool,
    ) -> PyResult<String> {
        let time = parse_time(target).map_err(err)?;
        let rows = py
            .detach(|| {
                if record && inputs_only {
                    self.inner.advance_inputs(time)
                } else {
                    self.inner.advance(time, record)
                }
            })
            .map_err(err)?;
        serde_json::to_string(&rows).map_err(err)
    }
}
#[pymodule]
fn _threemind_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeEngine>()?;
    m.add_class::<legacy::NativeLegacy>()?;
    m.add_class::<continuous::NativeContinuous>()?;
    m.add_class::<local::NativeLocal>()?;
    m.add_class::<local::NativeLocal5>()?;
    m.add_class::<local::NativeLocal51>()?;
    m.add_class::<local::NativeLocal53>()?;
    m.add_class::<local::NativeLocal60>()?;
    m.add_class::<local::NativeLocal61>()?;
    m.add_class::<local::NativeLocal62>()?;
    m.add_class::<local::NativeLocal63>()?;
    m.add_class::<local::NativeWeightDecay>()?;
    m.add_class::<local::NativeLocal52>()?;
    m.add_class::<lif::NativeLif>()?;
    m.add_function(wrap_pyfunction!(canonical_hash, m)?)?;
    m.add_function(wrap_pyfunction!(mechanism_probe, m)?)?;
    Ok(())
}

#[pyfunction]
fn canonical_hash(py: Python<'_>, payload: &[u8]) -> PyResult<String> {
    py.detach(|| threemind_core::canonical_hash(payload))
        .map_err(err)
}

#[pyfunction]
fn mechanism_probe(py: Python<'_>, payload: &[u8]) -> PyResult<String> {
    let value = py
        .detach(|| threemind_core::mechanisms::probe(payload))
        .map_err(err)?;
    serde_json::to_string(&value).map_err(err)
}
