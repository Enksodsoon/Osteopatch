"""Import and asset smoke checks; models and diagrams here are synthetic only."""
import os
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / ".tools/visualization/verification"
OUT.mkdir(parents=True, exist_ok=True)
if os.name == "nt":
    os.environ["PATH"] = f"C:\\Program Files\\Graphviz\\bin;{os.environ['PATH']}"

import altair as alt
import diagrams
import graphviz
import matplotlib
import matplotlib.pyplot as plt
import netron
import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import pyvis
import scipy
import seaborn as sns
import sklearn
import tensorboard
import torch
import torch.nn as nn
import torchvision
from torch.utils.tensorboard import SummaryWriter
from torchinfo import summary
from torchview import draw_graph
from diagrams import Diagram
from diagrams.onprem.compute import Server

versions = {name: version(dist) for name, dist in (
    ("altair", "altair"), ("diagrams", "diagrams"), ("graphviz", "graphviz"),
    ("matplotlib", "matplotlib"), ("netron", "netron"), ("networkx", "networkx"),
    ("numpy", "numpy"), ("pandas", "pandas"), ("plotly", "plotly"),
    ("pyvis", "pyvis"), ("scipy", "scipy"), ("seaborn", "seaborn"),
    ("sklearn", "scikit-learn"), ("tensorboard", "tensorboard"),
    ("torch", "torch"), ("torchvision", "torchvision"),
)}

frame = pd.DataFrame({"group": ["A", "B"], "value": [1, 2]})
assert len(frame) == 2 and float(np.mean([1, 2])) == 1.5
assert sklearn.metrics.accuracy_score([0, 1], [0, 1]) == 1.0
alt.Chart(frame).mark_bar().encode(x="group", y="value").to_json()
sns.set_theme(style="whitegrid")
fig, ax = plt.subplots(figsize=(3, 2)); ax.bar(frame.group, frame.value); fig.savefig(OUT / "matplotlib-smoke.png"); plt.close(fig)
plot = px.bar(frame, x="group", y="value", title="Synthetic export smoke test")
plot.write_image(str(OUT / "plotly-kaleido-smoke.svg"))
graphviz.Source("digraph { source -> rendered }").render(str(OUT / "graphviz-smoke"), format="svg", cleanup=True)
with Diagram("Synthetic diagrams package smoke", filename=str(OUT / "diagrams-smoke"), outformat="svg", show=False):
    Server("source") >> Server("rendered")
graph = nx.DiGraph([("source", "rendered")]); assert nx.is_directed_acyclic_graph(graph)
from pyvis.network import Network
net = Network(height="240px", width="480px", directed=True); net.add_node("a"); net.add_node("b"); net.add_edge("a", "b"); net.write_html(str(OUT / "pyvis-smoke.html"), notebook=False)

# Synthetic ConvNet only: this checks the visualizer runtime, not OsteoPatch weights.
model = nn.Sequential(nn.Conv2d(3, 8, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(8, 3))
summary(model, input_size=(1, 3, 32, 32), verbose=0)
view = draw_graph(model, input_size=(1, 3, 32, 32), graph_name="synthetic_smoke", save_graph=True, directory=str(OUT))
assert view is not None
writer = SummaryWriter(str(OUT / "tensorboard")); writer.add_scalar("smoke/value", 1, 0); writer.close()
assert callable(netron.start)

assets = list(OUT.glob("*.svg")) + list(OUT.glob("*.png")) + list(OUT.glob("*.html"))
assert any(p.name.startswith("plotly-kaleido") for p in assets)
assert all(p.stat().st_size > 0 for p in assets)
print("imported:", ", ".join(f"{k}={v}" for k, v in versions.items()))
print("synthetic asset smoke:", ", ".join(f"{p.name} ({p.stat().st_size} bytes)" for p in assets))
print(f"torch CUDA available: {torch.cuda.is_available()} (CPU-only tool environment)")
print(f"diagrams package: {diagrams.__file__}; netron module: {netron.__file__}")
