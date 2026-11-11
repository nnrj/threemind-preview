//! Explicit developmental coordinates; proximity never manufactures a connection.
use crate::{Config, Edge, Node};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};

pub const COORDINATE_RULE: &str = "threemind.sha256-id-axis/1";

pub fn position(config: &Config, id: u64) -> Vec<f64> {
    (0..config.spatial_dimensions)
        .map(|axis| {
            let digest =
                Sha256::digest(format!("{COORDINATE_RULE}:{}:{id}:{axis}", config.seed).as_bytes());
            let value = u32::from_be_bytes(digest[..4].try_into().unwrap());
            value as f64 / 2147483648.0 - 1.0
        })
        .collect()
}

pub fn distance(points: &HashMap<u64, Vec<f64>>, source: u64, target: u64) -> f64 {
    points[&source]
        .iter()
        .zip(&points[&target])
        .map(|(a, b)| (a - b) * (a - b))
        .sum::<f64>()
        .sqrt()
}

fn find(parents: &mut BTreeMap<u64, u64>, mut node: u64) -> u64 {
    while parents[&node] != node {
        let next = parents[&parents[&node]];
        parents.insert(node, next);
        node = next;
    }
    node
}

fn components(
    config: &Config,
    points: &HashMap<u64, Vec<f64>>,
    nodes: &[Node],
    edges: &[Edge],
) -> (BTreeMap<u64, u64>, usize, usize) {
    let mut parents: BTreeMap<u64, u64> = nodes.iter().map(|n| (n.id, n.id)).collect();
    let mut connected = BTreeSet::new();
    let mut count = 0;
    for edge in edges {
        if distance(points, edge.source, edge.target) <= config.spatial_radius {
            count += 1;
            connected.insert(edge.source);
            connected.insert(edge.target);
            let a = find(&mut parents, edge.source);
            let b = find(&mut parents, edge.target);
            parents.insert(a.max(b), a.min(b));
        }
    }
    let labels = nodes
        .iter()
        .map(|n| (n.id, find(&mut parents, n.id)))
        .collect();
    (labels, count, nodes.len() - connected.len())
}

pub fn observation(
    config: &Config,
    points: &HashMap<u64, Vec<f64>>,
    nodes: &[Node],
    edges: &[Edge],
    full: bool,
) -> Value {
    let mut result = json!({"schema":"threemind.spatial-observation/1","coordinate_rule":COORDINATE_RULE,
        "parameters":{"spatial_embedding":config.spatial_embedding,"spatial_dimensions":config.spatial_dimensions,
        "neighborhood_enabled":config.neighborhood_enabled,"spatial_radius":config.spatial_radius,"spatial_competition_rate":config.spatial_competition_rate},
        "seed":config.seed,"neighbor_edges":null,"clusters":null,"isolated_nodes":null});
    if full {
        result["nodes"] = json!([]);
        result["edges"] = json!([]);
    }
    if !config.spatial_embedding {
        return result;
    }
    let (labels, count, isolated) = components(config, points, nodes, edges);
    result["neighbor_edges"] = json!(count);
    result["clusters"] = json!(labels.values().collect::<BTreeSet<_>>().len());
    result["isolated_nodes"] = json!(isolated);
    if full {
        result["nodes"] = json!(labels
            .iter()
            .map(|(id, cluster)| json!({"id":id,"cluster":cluster,"position":points[id]}))
            .collect::<Vec<_>>());
        let mut values: Vec<_> = edges.iter().collect();
        values.sort_by_key(|e| (e.source, e.target));
        result["edges"]=json!(values.into_iter().map(|e| { let d=distance(points,e.source,e.target); json!({"source":e.source,"target":e.target,"distance":d,"within_radius":d<=config.spatial_radius}) }).collect::<Vec<_>>());
    }
    result
}
