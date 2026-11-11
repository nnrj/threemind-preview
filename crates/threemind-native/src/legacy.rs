use super::err;
use pyo3::prelude::*;
use threemind_core::{legacy::LegacyEngine, parse_document, parse_time};

#[pyclass]
pub(super) struct NativeLegacy {
    inner: LegacyEngine,
}

#[pymethods]
impl NativeLegacy {
    #[new]
    #[pyo3(signature=(kernel, config_json, state_json=None))]
    fn new(kernel: &str, config_json: &str, state_json: Option<&str>) -> PyResult<Self> {
        let inner = match state_json {
            Some(raw) => {
                let state = parse_document(raw.as_bytes()).map_err(err)?;
                if state["dynamics"] != kernel {
                    return Err(err("historical kernel identity mismatch"));
                }
                LegacyEngine::restore(state)
            }
            None => LegacyEngine::new(kernel, parse_document(config_json.as_bytes()).map_err(err)?),
        }
        .map_err(err)?;
        Ok(Self { inner })
    }
    fn time_us(&self) -> String {
        self.inner.time().to_string()
    }
    fn sequence(&self) -> u64 {
        self.inner.sequence()
    }
    fn life(&self) -> String {
        self.inner.life().into()
    }
    fn config_json(&self) -> String {
        self.inner.config().to_string()
    }
    fn state_json(&self) -> PyResult<String> {
        self.inner.capture().map(|v| v.to_string()).map_err(err)
    }
    fn metrics_json(&self) -> String {
        self.inner.metrics().to_string()
    }
    fn graph_json(&self, limit: Option<usize>) -> String {
        self.inner.graph(limit).to_string()
    }
    fn activations(&self) -> Vec<(u64, f64)> {
        self.inner.activations()
    }
    fn observation_nodes_json(&self) -> String {
        self.inner.observation_nodes().to_string()
    }
    fn induced_edges_json(&self, node_ids: Vec<u64>) -> String {
        self.inner.induced_edges(node_ids).to_string()
    }
    fn spatial_geometry_json(&self) -> PyResult<String> {
        self.inner
            .spatial_geometry()
            .map(|v| v.to_string())
            .map_err(err)
    }
    fn inject(&mut self, payload: &str) -> PyResult<u64> {
        self.inner
            .inject(serde_json::from_str(payload).map_err(err)?)
            .map_err(err)
    }
    fn close_inputs(&mut self) {
        self.inner.close_inputs()
    }
    fn supply_energy(&mut self, time: &str, amount: f64, source: String) -> PyResult<u64> {
        self.inner
            .supply_energy(parse_time(time).map_err(err)?, amount, source)
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
    fn reconfigure(&mut self, payload: &str) -> PyResult<()> {
        self.inner
            .reconfigure(serde_json::from_str(payload).map_err(err)?)
            .map_err(err)
    }
    fn intervene(&mut self, nodes: Vec<u64>, edges: Vec<(u64, u64)>, lesion: bool) -> PyResult<()> {
        self.inner.intervene(nodes, edges, lesion).map_err(err)
    }
    #[pyo3(signature=(target_us, record=false, inputs_only=false))]
    fn advance(&mut self, target_us: &str, record: bool, inputs_only: bool) -> PyResult<String> {
        let target = parse_time(target_us).map_err(err)?;
        let rows = if inputs_only {
            self.inner.advance_inputs(target, record)
        } else {
            self.inner.advance(target, record)
        }
        .map_err(err)?;
        serde_json::to_string(&rows).map_err(err)
    }
}
