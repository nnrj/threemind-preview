use super::err;
use pyo3::prelude::*;
use threemind_core::continuous::ContinuousEngine;
use threemind_core::{parse_document, parse_time, Stimulus};

#[pyclass]
pub(super) struct NativeContinuous {
    inner: ContinuousEngine,
}
#[pymethods]
impl NativeContinuous {
    #[new]
    #[pyo3(signature = (config_json, state_json=None, kernel="threemind.continuous/1"))]
    fn new(config_json: &str, state_json: Option<&str>, kernel: &str) -> PyResult<Self> {
        let memory = match kernel {
            "threemind.continuous/1" => false,
            "threemind.continuous-memory/1" => true,
            "threemind.continuous-memory/2" => true,
            "threemind.continuous-memory/3" => true,
            "threemind.continuous-memory/3.1" => true,
            _ => return Err(err("unknown continuous kernel identity")),
        };
        let inner = if let Some(state) = state_json {
            let value = parse_document(state.as_bytes()).map_err(err)?;
            if kernel == "threemind.continuous-memory/3.1" {
                ContinuousEngine::restore_retention31(value)
            } else if kernel == "threemind.continuous-memory/3" {
                ContinuousEngine::restore_retention(value)
            } else if kernel == "threemind.continuous-memory/2" {
                ContinuousEngine::restore_novelty(value)
            } else if memory {
                ContinuousEngine::restore_memory(value)
            } else {
                ContinuousEngine::restore(value)
            }
        } else {
            let value = parse_document(config_json.as_bytes()).map_err(err)?;
            if kernel == "threemind.continuous-memory/3.1" {
                ContinuousEngine::new_retention31(value)
            } else if kernel == "threemind.continuous-memory/3" {
                ContinuousEngine::new_retention(value)
            } else if kernel == "threemind.continuous-memory/2" {
                ContinuousEngine::new_novelty(value)
            } else if memory {
                ContinuousEngine::new_memory(value)
            } else {
                ContinuousEngine::new(value)
            }
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
        self.inner.life().to_string()
    }
    fn config_json(&self) -> String {
        serde_json::to_string(&self.inner.config()).unwrap()
    }
    fn state_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner.capture().map_err(err)?).map_err(err)
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
            .reconfigure(parse_document(config_json.as_bytes()).map_err(err)?)
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
