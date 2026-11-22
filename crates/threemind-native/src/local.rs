use super::err;
use pyo3::prelude::*;
use threemind_core::{
    local::{LocalEngine, LocalEngine5},
    local51::LocalEngine51,
    parse_document, parse_time, Stimulus,
};
macro_rules! bind_local {
    ($name:ident, $engine:ty) => {
        #[pyclass]
        pub(super) struct $name {
            inner: $engine,
        }
        #[pymethods]
        impl $name {
            #[new]
            #[pyo3(signature=(config_json,state_json=None))]
            fn new(config_json: &str, state_json: Option<&str>) -> PyResult<Self> {
                let inner = if let Some(state) = state_json {
                    <$engine>::restore(parse_document(state.as_bytes()).map_err(err)?)
                } else {
                    <$engine>::new(parse_document(config_json.as_bytes()).map_err(err)?)
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
                self.inner.config().to_string()
            }
            fn state_json(&self) -> PyResult<String> {
                Ok(self.inner.capture().map_err(err)?.to_string())
            }
            fn metrics_json(&self) -> String {
                self.inner.metrics().to_string()
            }
            fn spatial_geometry_json(&self) -> PyResult<String> {
                Ok(self.inner.spatial_geometry().map_err(err)?.to_string())
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
            fn modulate_input(&mut self, time: &str, payload: &str) -> PyResult<u64> {
                self.inner
                    .modulate_input(
                        parse_time(time).map_err(err)?,
                        serde_json::from_str(payload).map_err(err)?,
                    )
                    .map_err(err)
            }
            fn reconfigure(&mut self, config_json: &str) -> PyResult<()> {
                self.inner
                    .reconfigure(parse_document(config_json.as_bytes()).map_err(err)?)
                    .map_err(err)
            }
            #[pyo3(signature=(nodes,edges,lesion=false,action=None))]
            fn intervene(
                &mut self,
                nodes: Vec<u64>,
                edges: Vec<(u64, u64)>,
                lesion: bool,
                action: Option<String>,
            ) -> PyResult<()> {
                if let Some(action) = action {
                    if lesion {
                        return Err(err("use action or lesion"));
                    }
                    self.inner
                        .intervene_action(nodes, edges, &action)
                        .map_err(err)
                } else {
                    self.inner.intervene(nodes, edges, lesion).map_err(err)
                }
            }
            #[pyo3(signature=(target,record,inputs_only=false))]
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
    };
}
bind_local!(NativeLocal, LocalEngine);
bind_local!(NativeLocal5, LocalEngine5);
bind_local!(NativeLocal51, LocalEngine51);

use threemind_core::local53::LocalEngine53;
bind_local!(NativeLocal53, LocalEngine53);

use threemind_core::local52::LocalEngine52;
bind_local!(NativeLocal52, LocalEngine52);

use threemind_core::weight_decay::LocalWeightDecayEngine;
bind_local!(NativeWeightDecay, LocalWeightDecayEngine);

use threemind_core::local60::LocalEngine60;
bind_local!(NativeLocal60, LocalEngine60);

use threemind_core::local61::LocalEngine61;
bind_local!(NativeLocal61, LocalEngine61);

use threemind_core::local62::LocalEngine62;
use threemind_core::local63::LocalEngine63;
bind_local!(NativeLocal62, LocalEngine62);
bind_local!(NativeLocal63, LocalEngine63);
