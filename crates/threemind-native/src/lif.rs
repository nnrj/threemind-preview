use super::err;
use pyo3::prelude::*;
use threemind_core::lif::LifEngine;
use threemind_core::{parse_document, parse_time, Stimulus};

#[pyclass]
pub(super) struct NativeLif {
    inner: LifEngine,
}
#[pymethods]
impl NativeLif {
    #[new]
    #[pyo3(signature = (config_json, state_json=None))]
    fn new(config_json: &str, state_json: Option<&str>) -> PyResult<Self> {
        let inner = if let Some(state) = state_json {
            LifEngine::restore(parse_document(state.as_bytes()).map_err(err)?)
        } else {
            LifEngine::new(parse_document(config_json.as_bytes()).map_err(err)?)
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
        self.inner.life.clone().to_string()
    }
    fn config_json(&self) -> String {
        serde_json::to_string(&self.inner.config.value()).unwrap()
    }
    fn state_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner.capture().map_err(err)?).map_err(err)
    }
    fn metrics_json(&self) -> String {
        self.inner.metrics().to_string()
    }
    fn spatial_geometry_json(&self) -> PyResult<String> {
        Err(err("LIF has no causal spatial embedding"))
    }
    fn physical_nodes_json(&self) -> String {
        serde_json::to_string(&self.inner.physical_nodes()).unwrap()
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
    fn supply_energy(&mut self, _time: &str, _amount: f64, _source: String) -> PyResult<u64> {
        Err(err("LIF currents are not a causal energy ledger"))
    }
    fn reconfigure(&mut self, config_json: &str) -> PyResult<()> {
        self.inner
            .reconfigure(parse_document(config_json.as_bytes()).map_err(err)?)
            .map_err(err)
    }
    fn modulate_input(&mut self, _time: &str, _payload: &str) -> PyResult<u64> {
        Err(err(
            "LIF does not implement causal input-attention modulation",
        ))
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
    #[pyo3(signature = (target, record, inputs_only=false, record_spikes=false))]
    fn advance(
        &mut self,
        py: Python<'_>,
        target: &str,
        record: bool,
        inputs_only: bool,
        record_spikes: bool,
    ) -> PyResult<String> {
        let time = parse_time(target).map_err(err)?;
        let rows = py
            .detach(|| {
                if record && inputs_only && record_spikes {
                    self.inner.advance_inputs_and_spikes(time)
                } else if record && inputs_only {
                    self.inner.advance_inputs(time)
                } else {
                    self.inner.advance(time, record)
                }
            })
            .map_err(err)?;
        serde_json::to_string(&rows).map_err(err)
    }
}
