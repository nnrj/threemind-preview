"""Variable-graph, process-conditioned byte expression. Entirely outside Core."""

from dataclasses import asdict, dataclass
import json, time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .scratch_language import BOS, EOS, VOCABULARY
from threemind_runtime.graph_observation import VERSION, NODE_FIELDS, EDGE_FIELDS


@dataclass(frozen=True)
class GraphExpressionConfig:
    schema: str = "threemind.graph-expression/2"
    width: int = 64
    heads: int = 4
    queries: int = 4
    temporal_layers: int = 1
    decoder_layers: int = 2
    maximum_frames: int = 32
    maximum_nodes: int = 512
    maximum_edges: int = 16384
    maximum_tokens: int = 64
    node_fields: tuple = NODE_FIELDS
    edge_fields: tuple = EDGE_FIELDS
    use_edges: bool = True
    seed: int = 47

    def __post_init__(self):
        object.__setattr__(self, "node_fields", tuple(self.node_fields))
        object.__setattr__(self, "edge_fields", tuple(self.edge_fields))
        if self.schema not in ("threemind.graph-expression/1", "threemind.graph-expression/2"):
            raise ValueError("unsupported graph expression")
        if self.width not in (32, 64, 128) or self.heads not in (1, 2, 4, 8) or self.width % self.heads:
            raise ValueError("attention dimensions")
        if not 1 <= self.queries <= 8 or not 1 <= self.temporal_layers <= 3 or not 1 <= self.decoder_layers <= 3:
            raise ValueError("bounded layers")
        if (
            not 2 <= self.maximum_frames <= 64
            or not 1 <= self.maximum_nodes <= 2048
            or not 0 <= self.maximum_edges <= 65536
        ):
            raise ValueError("graph limits")
        if not 4 <= self.maximum_tokens <= 128:
            raise ValueError("token limit")
        if (
            not self.node_fields
            or len(set(self.node_fields)) != len(self.node_fields)
            or set(self.node_fields) - set(NODE_FIELDS + ("amount",))
        ):
            raise ValueError("node measurement fields")
        if (
            not self.edge_fields
            or len(set(self.edge_fields)) != len(self.edge_fields)
            or set(self.edge_fields) - set(EDGE_FIELDS)
        ):
            raise ValueError("edge measurement fields")


def pack_graphs(processes, config, device="cpu"):
    """Ragged nodes/edges: no fixed node vocabulary, no silent truncation."""
    if not 1 <= len(processes) <= 64:
        raise ValueError("bounded nonempty graph batch")
    values = []
    edge_values = []
    sources = []
    targets = []
    frames = []
    positions = []
    times = []
    lengths = []
    max_nodes = 0
    for process in processes:
        allowed = {"schema", "node_fields", "edge_fields", "start_us", "end_us", "frames"}
        if set(process) != allowed or process["schema"] != VERSION:
            raise ValueError("undeclared graph data or labels")
        if tuple(process["node_fields"]) != config.node_fields or tuple(process["edge_fields"]) != config.edge_fields:
            raise ValueError("measurement layout mismatch")
        rows = process["frames"]
        start = int(process["start_us"])
        end = int(process["end_us"])
        if not 2 <= len(rows) <= config.maximum_frames:
            raise ValueError("frame budget")
        stamps = [int(r["time_us"]) for r in rows]
        if stamps[0] != start or stamps[-1] != end or end <= start or any(a >= b for a, b in zip(stamps, stamps[1:])):
            raise ValueError("strict observed time order")
        lengths.append(len(rows))
        previous = start
        for frame in rows:
            if set(frame) != {"time_us", "nodes", "edges"}:
                raise ValueError("undeclared frame fields")
            nodes = frame["nodes"]
            edges = frame["edges"]
            now = int(frame["time_us"])
            if len(nodes) > config.maximum_nodes or len(edges) > config.maximum_edges:
                raise ValueError("graph budget")
            base = len(values)
            lookup = {}
            channels = set()
            frame_id = len(times)
            max_nodes = max(max_nodes, len(nodes))
            for position, node in enumerate(nodes):
                if set(node) != {"id", "channel", "values"}:
                    raise ValueError("undeclared node fields")
                identity = str(node["id"])
                channel = int(node["channel"])
                if identity in lookup or channel in channels or not 0 <= channel < 2**32:
                    raise ValueError("unique anonymous identities required")
                if len(node["values"]) != len(config.node_fields):
                    raise ValueError("node width")
                # Exact bits, not a hash bucket or semantic lookup table.
                values.append([(channel >> i) & 1 for i in range(32)] + list(node["values"]))
                lookup[identity] = base + position
                channels.add(channel)
                frames.append(frame_id)
                positions.append(position + 1)
            seen = set()
            for edge in edges:
                if set(edge) != {"source", "target", "values"} or len(edge["values"]) != len(config.edge_fields):
                    raise ValueError("edge fields")
                key = str(edge["source"]), str(edge["target"])
                if key in seen or any(i not in lookup for i in key):
                    raise ValueError("edge endpoint")
                seen.add(key)
                if config.use_edges:
                    sources.append(lookup[key[0]])
                    targets.append(lookup[key[1]])
                    edge_values.append(edge["values"])
            times.append([(now - start) / 1e6, (now - previous) / 1e6])
            previous = now

    def floating(rows, width):
        array = np.asarray(rows, dtype=np.float32).reshape(-1, width)
        if not np.isfinite(array).all():
            raise ValueError("nonfinite measured value")
        return torch.from_numpy(array).to(device)

    return {
        "nodes": floating(values, 32 + len(config.node_fields)),
        "edge_values": floating(edge_values, len(config.edge_fields)),
        "sources": torch.tensor(sources, dtype=torch.long, device=device),
        "targets": torch.tensor(targets, dtype=torch.long, device=device),
        "frames": torch.tensor(frames, dtype=torch.long, device=device),
        "positions": torch.tensor(positions, dtype=torch.long, device=device),
        "times": floating(times, 2),
        "lengths": lengths,
        "max_nodes": max_nodes,
    }


class GraphExpression(nn.Module):
    def __init__(self, config=GraphExpressionConfig()):
        super().__init__()
        self.config = config
        w = config.width
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config.seed)
            if config.schema.endswith("/2"):
                self.identity = nn.Sequential(nn.Linear(32, w), nn.GELU(), nn.Linear(w, w))
                self.measurement = nn.Sequential(nn.Linear(len(config.node_fields), w), nn.GELU(), nn.Linear(w, w))
                self.degree = nn.Linear(1, w, bias=False)
                self.graph_gain = nn.Parameter(torch.tensor(0.1))
            self.node = nn.Sequential(nn.Linear(32 + len(config.node_fields), w), nn.GELU(), nn.Linear(w, w))
            self.edge = nn.Sequential(nn.Linear(len(config.edge_fields), w), nn.GELU(), nn.Linear(w, w))
            self.message = nn.Linear(w, w, bias=False)
            self.update = nn.Linear(w, w)
            self.node_norm = nn.LayerNorm(w)
            self.queries = nn.Parameter(torch.randn(config.queries, w) * 0.02)
            self.empty = nn.Parameter(torch.zeros(w))
            self.pool = nn.MultiheadAttention(w, config.heads, dropout=0, batch_first=True)
            self.time = nn.Linear(2, w)
            self.temporal = nn.ModuleList(
                nn.TransformerEncoderLayer(
                    w, config.heads, w * 4, dropout=0, activation="gelu", batch_first=True, norm_first=True
                )
                for _ in range(config.temporal_layers)
            )
            self.token = nn.Embedding(VOCABULARY, w)
            self.position = nn.Embedding(config.maximum_tokens, w)
            self.decoder = nn.ModuleList(
                nn.TransformerDecoderLayer(
                    w, config.heads, w * 4, dropout=0, activation="gelu", batch_first=True, norm_first=True
                )
                for _ in range(config.decoder_layers)
            )
            self.norm = nn.LayerNorm(w)
            self.output = nn.Linear(w, VOCABULARY, bias=False)

    @property
    def device(self):
        return self.queries.device

    def encode(self, batch):
        if self.config.schema.endswith("/2"):
            return self.encode_node_time(batch)
        h = self.node(batch["nodes"])
        if batch["sources"].numel():
            messages = torch.tanh(self.message(h[batch["sources"]]) + self.edge(batch["edge_values"]))
            received = torch.zeros_like(h).index_add(0, batch["targets"], messages)
            h = h + self.update(received)
        h = self.node_norm(h)
        count = len(batch["times"])
        w = self.config.width
        padded = h.new_zeros((count, batch["max_nodes"] + 1, w))
        mask = torch.ones(padded.shape[:2], dtype=torch.bool, device=h.device)
        padded[:, 0] = self.empty
        mask[:, 0] = False
        if h.shape[0]:
            padded[batch["frames"], batch["positions"]] = h
            mask[batch["frames"], batch["positions"]] = False
        queries = self.queries[None].expand(count, -1, -1)
        pooled = self.pool(queries, padded, padded, key_padding_mask=mask, need_weights=False)[0] + queries
        pooled = pooled + self.time(batch["times"])[:, None, :]
        lengths = batch["lengths"]
        maximum = max(lengths) * self.config.queries
        memory = h.new_zeros((len(lengths), maximum, w))
        padding = torch.ones((len(lengths), maximum), dtype=torch.bool, device=h.device)
        offset = 0
        for i, n in enumerate(lengths):
            size = n * self.config.queries
            memory[i, :size] = pooled[offset : offset + n].reshape(size, w)
            padding[i, :size] = False
            offset += n
        for layer in self.temporal:
            memory = layer(memory, src_key_padding_mask=padding)
        return memory, padding

    def encode_node_time(self, batch):
        """Retain node-at-time tokens, with no query-dependent rescaling.

        Signed log is an internal, fixed, invertible numerical representation.
        Source measurements remain unchanged. Graph aggregation is solely a
        reader operation; it cannot change Core messages or stored observations.
        """

        def representation(x):
            return torch.sign(x) * torch.log1p(torch.abs(x))

        raw = batch["nodes"]
        identity = self.identity(raw[:, :32])
        measured = self.measurement(representation(raw[:, 32:]))
        h = identity + measured + identity * measured
        if batch["sources"].numel():
            messages = torch.tanh(self.message(h[batch["sources"]]) + self.edge(representation(batch["edge_values"])))
            received = torch.zeros_like(h).index_add(0, batch["targets"], messages)
            degree = h.new_zeros((len(h), 1)).index_add(0, batch["targets"], h.new_ones((len(messages), 1)))
            h = h + self.graph_gain * (self.update(received / degree.clamp_min(1)) + self.degree(torch.log1p(degree)))
        h = h + self.time(batch["times"])[batch["frames"]]
        lengths = batch["lengths"]
        counts = []
        offset = 0
        for length in lengths:
            counts.append(int(((batch["frames"] >= offset) & (batch["frames"] < offset + length)).sum()))
            offset += length
        maximum = max(counts, default=0) + 1
        if maximum > 32769:
            raise ValueError("node-time token budget")
        memory = h.new_zeros((len(lengths), maximum, self.config.width))
        padding = torch.ones(memory.shape[:2], dtype=torch.bool, device=h.device)
        offset = 0
        for i, count in enumerate(counts):
            memory[i, 0] = self.empty
            padding[i, : count + 1] = False
            memory[i, 1 : count + 1] = h[offset : offset + count]
            offset += count
        return memory, padding

    def logits(self, ids, memory, padding):
        n = ids.shape[1]
        if n > self.config.maximum_tokens:
            raise ValueError("explicit output token limit")
        value = self.token(ids) + self.position(torch.arange(n, device=self.device))[None]
        causal = torch.triu(torch.ones((n, n), dtype=torch.bool, device=self.device), 1)
        for layer in self.decoder:
            value = layer(value, memory, tgt_mask=causal, memory_key_padding_mask=padding)
        return self.output(self.norm(value))

    def loss(self, batch, texts):
        rows = [[*s.encode("utf-8"), EOS] for s in texts]
        n = max(map(len, rows))
        if n > self.config.maximum_tokens:
            raise ValueError("teaching text exceeds token limit")
        labels = torch.full((len(rows), n), -100, dtype=torch.long, device=self.device)
        ids = torch.full_like(labels, EOS)
        ids[:, 0] = BOS
        for i, row in enumerate(rows):
            labels[i, : len(row)] = torch.tensor(row, device=self.device)
            if len(row) > 1:
                ids[i, 1 : len(row)] = labels[i, : len(row) - 1]
        memory, padding = self.encode(batch)
        return nn.functional.cross_entropy(self.logits(ids, memory, padding).reshape(-1, VOCABULARY), labels.flatten())

    @torch.no_grad()
    def decode(self, processes, maximum_tokens=32):
        self.eval()
        batch = pack_graphs(processes, self.config, self.device)
        memory, padding = self.encode(batch)
        if not 1 <= maximum_tokens <= self.config.maximum_tokens:
            raise ValueError("generation token budget")
        ids = torch.full((len(processes), 1), BOS, dtype=torch.long, device=self.device)
        tokens = [[] for _ in processes]
        done = torch.zeros(len(processes), dtype=torch.bool, device=self.device)
        for _ in range(maximum_tokens):
            next_ids = self.logits(ids, memory, padding)[:, -1].argmax(-1)
            for i, t in enumerate(next_ids.tolist()):
                if not done[i]:
                    tokens[i].append(t)
            done |= next_ids == EOS
            if bool(done.all()):
                break
            ids = torch.cat((ids, next_ids[:, None]), 1)
        return [
            {
                "text": bytes(t for t in row if t < 256).decode("utf-8", errors="replace"),
                "tokens": row,
                "terminated": bool(row and row[-1] == EOS),
                "cross_window_cache": False,
                "pretrained_weights": False,
            }
            for row in tokens
        ]


def save(model, path, metadata):
    from safetensors.torch import save_file

    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "threemind.graph-expression-checkpoint/1",
        "config": asdict(model.config),
        "training": metadata,
    }
    save_file(
        {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()},
        str(path),
        metadata={"threemind": json.dumps(manifest)},
    )


def load(path, device="cpu"):
    from safetensors import safe_open
    from safetensors.torch import load_file

    if Path(path).stat().st_size > 64 * 2**20:
        raise ValueError("expression checkpoint exceeds64MiB")
    with safe_open(str(path), framework="pt", device="cpu") as f:
        meta = json.loads(f.metadata()["threemind"])
    if meta["schema"] != "threemind.graph-expression-checkpoint/1":
        raise ValueError("checkpoint version")
    model = GraphExpression(GraphExpressionConfig(**meta["config"])).to(device)
    model.load_state_dict(load_file(str(path), device=str(device)))
    return model.eval(), meta


def fit(
    samples,
    path,
    *,
    config=GraphExpressionConfig(),
    initial=None,
    steps=4000,
    learning_rate=0.001,
    batch_size=4,
    device="cpu",
    check=lambda: None,
):
    if Path(path).exists():
        raise FileExistsError(path)
    if not 2 <= len(samples) <= 128 or not 1 <= steps <= 10000 or not 1 <= batch_size <= 32:
        raise ValueError("bounded training required")
    if not 0 < learning_rate <= 0.01:
        raise ValueError("learning rate")
    model = load(initial, device)[0] if initial else GraphExpression(config).to(device)
    if model.config != config:
        raise ValueError("continuation config differs")
    parts = [samples[i : i + batch_size] for i in range(0, len(samples), batch_size)]
    packed = [pack_graphs([r["process"] for r in part], config, device) for part in parts]
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    history = []
    best = None
    score = (-1, float("-inf"))
    stable = 0
    started = time.monotonic()
    for step in range(steps):
        model.train()
        optimizer.zero_grad()
        total = 0.0
        for part, batch in zip(parts, packed):
            loss = model.loss(batch, [r["text"] for r in part])
            fraction = len(part) / len(samples)
            if not torch.isfinite(loss):
                raise RuntimeError("nonfinite graph expression training")
            (loss * fraction).backward()
            total += float(loss.detach().cpu()) * fraction
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % 20 == 0:
            check()
        if (step + 1) % 500 == 0 or step + 1 == steps:
            outputs = []
            for part in parts:
                outputs.extend(model.decode([r["process"] for r in part]))
            correct = sum(o["text"] == r["text"] for o, r in zip(outputs, samples))
            candidate = (correct, -total)
            history.append(
                {
                    "steps": step + 1,
                    "correct": correct,
                    "count": len(samples),
                    "loss": total,
                    "outputs": [o["text"] for o in outputs],
                }
            )
            if candidate > score:
                score = candidate
                best = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stable = stable + 1 if correct == len(samples) else 0
            print({"steps": step + 1, "fit": f"{correct}/{len(samples)}", "loss": round(total, 6)}, flush=True)
            if stable >= 2:
                break
    model.load_state_dict(best)
    metadata = {
        "steps": step + 1,
        "samples": len(samples),
        "learning_rate": learning_rate,
        "history": history,
        "selection": "training accuracy then training loss; no test selection",
        "initial": str(initial) if initial else None,
        "equal_exposure": True,
        "batch_size": batch_size,
        "normalization": "no per-example input scaling",
        "wall_seconds": time.monotonic() - started,
        "parameters": sum(p.numel() for p in model.parameters()),
        "device": device,
    }
    save(model, path, metadata)
    return model, metadata
