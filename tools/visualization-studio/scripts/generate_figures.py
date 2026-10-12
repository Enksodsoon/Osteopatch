"""Build source-grounded static figures and local interactive HTML outputs."""
import csv
import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/visualizations"
G4 = ROOT / "aidlc-docs/inception/model/g4"
G5 = ROOT / "aidlc-docs/inception/model/g5"
ORDER = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]
DISPLAY_CLASSES = ["Non-tumor tissue", "Viable tumor", "Necrotic tissue"]
ECHARTS = "../../tools/visualization-studio/node_modules/echarts/dist/echarts.min.js"


def read_metrics(folder: Path) -> dict:
    return json.loads((folder / "overall-oof-metrics.json").read_text(encoding="utf-8"))


def verify_g4_csv(metrics: dict) -> list[list[int]]:
    with (G4 / "confusion-matrix.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == ["true\\pred", *ORDER, "support"]
    matrix = [[int(value) for value in row[1:4]] for row in rows[1:4]]
    assert matrix == metrics["confusion_matrix_rows_true_cols_pred"]
    assert [sum(row) for row in matrix] == [metrics["per_class"][name]["support"] for name in ORDER]
    return matrix


def html_shell(title: str, subtitle: str, chart_script: str, note: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script src="{ECHARTS}"></script>
<style>body{{margin:0;padding:28px;font:15px/1.55 Segoe UI,Arial,sans-serif;color:#34362f;background:#f7f5ef}}main{{max-width:1120px;margin:auto;background:#fffefa;border:1px solid #e6e1d6;border-radius:10px;padding:26px}}h1{{font:500 32px Georgia,serif;margin:4px 0}}.eyebrow{{color:#40796f;letter-spacing:.12em;font-size:11px;font-weight:700}}.sub,.note,.source{{color:#706f66}}#chart{{height:470px}}.note{{border-left:3px solid #d58a5a;padding-left:12px}}.source{{font-size:12px;overflow-wrap:anywhere}}button{{background:#fffefa;border:1px solid #d5d0c4;border-radius:6px;padding:9px 12px;cursor:pointer;color:#34362f}}button:focus-visible{{outline:3px solid #d07b45;outline-offset:2px}}@media(max-width:600px){{body{{padding:10px}}main{{padding:16px}}#chart{{height:400px}}}}</style></head>
<body><main><span class="eyebrow">OSTEOPATCH · STORED RESEARCH EVIDENCE · 2026-10-11</span><h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p><div id="chart" role="img" aria-label="{html.escape(title)}"></div><p class="note">{html.escape(note)}</p><p class="source">Source records: stored evaluation metrics, model configuration, and confusion-matrix records.</p>
<button id="export">Export PNG</button></main><script>{chart_script}</script></body></html>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    g4, g5 = read_metrics(G4), read_metrics(G5)
    assert g4["class_order"] == g5["class_order"] == ORDER
    assert g4["n_rows"] == g5["n_rows"] == 1028
    matrix = verify_g4_csv(g4)
    g5_cfg = json.loads((G5 / "run-configuration.json").read_text(encoding="utf-8"))
    assert g5_cfg["result_classification"] == "NO BENEFIT" and not g5_cfg["final_bundle_created"]

    series = [{"name": "Reference model", "type": "bar", "data": [g4["per_class"][n]["recall"] for n in ORDER]},
              {"name": "Tuning candidate · NO BENEFIT", "type": "bar", "data": [g5["per_class"][n]["recall"] for n in ORDER]}]
    comparison_js = f'''const chart=echarts.init(document.getElementById('chart'));chart.setOption({{color:['#40796f','#c87843'],tooltip:{{trigger:'axis',valueFormatter:v=>(v*100).toFixed(1)+'% recall'}},legend:{{bottom:4}},grid:{{left:68,right:24,top:22,bottom:86}},xAxis:{{type:'category',data:{json.dumps(DISPLAY_CLASSES)},axisLabel:{{interval:0}}}},yAxis:{{type:'value',min:0,max:1,name:'Recall'}},dataZoom:[{{type:'inside'}},{{type:'slider',bottom:32,height:16}}],toolbox:{{right:8,feature:{{saveAsImage:{{name:'osteopatch-reference-candidate-recall'}},restore:{{}}}}}},series:{json.dumps(series)}}});window.addEventListener('resize',()=>chart.resize());document.getElementById('export').onclick=()=>{{const a=document.createElement('a');a.href=chart.getDataURL({{type:'png',pixelRatio:3,backgroundColor:'#f7f5ef'}});a.download='osteopatch-reference-candidate-recall.png';a.click()}};'''
    (OUT / "model-g5-comparison.html").write_text(html_shell(
        "Reference and tuning-candidate recall", "Each group excluded from training in turn · recall is the share correctly recognized · n=1,028; image-patch counts 484 / 290 / 254.", comparison_js,
        "The tuning candidate is recorded NO BENEFIT, meaning this evaluation did not demonstrate an improvement; no final candidate model file was created. Model scores are not calibrated chance estimates and are not disease probabilities. It is unverified whether training and evaluation images came from separate patients; patches from one biological sample may be related.",
    ), encoding="utf-8")

    display_classes = DISPLAY_CLASSES
    heat_data = [[x, y, matrix[y][x]] for y in range(3) for x in range(3)]
    confusion_js = f'''const classes={json.dumps(display_classes)},vals={json.dumps(heat_data)};const chart=echarts.init(document.getElementById('chart'));chart.setOption({{tooltip:{{position:'top',formatter:p=>`True ${{classes[p.data[1]]}} → predicted ${{classes[p.data[0]]}}: <b>${{p.data[2]}}</b>`}},grid:{{left:132,right:18,top:36,bottom:132}},xAxis:{{type:'category',data:classes,position:'bottom',axisLabel:{{interval:0,rotate:20,formatter:v=>v.replace(' ','\\n')}}}},yAxis:{{type:'category',data:classes,inverse:true}},visualMap:{{min:0,max:Math.max(...vals.map(d=>d[2])),calculable:false,orient:'horizontal',left:'center',bottom:12,inRange:{{color:['#f2efe5','#90b4a6','#40796f']}}}},series:[{{type:'heatmap',data:vals,label:{{show:true,color:'#34362f',fontSize:15}},emphasis:{{itemStyle:{{shadowBlur:8,shadowColor:'#777'}}}}}}]}});window.addEventListener('resize',()=>chart.resize());document.getElementById('export').onclick=()=>{{const a=document.createElement('a');a.href=chart.getDataURL({{type:'png',pixelRatio:3,backgroundColor:'#f7f5ef'}});a.download='osteopatch-reference-confusion-matrix.png';a.click()}};'''
    (OUT / "confusion-matrix.html").write_text(html_shell(
        "Reference-model confusion matrix", "Counts compare the true image category with the model prediction · n=1,028.", confusion_js,
        "Each image was evaluated by a model that did not train on its group; results are combined across four groups. One group contains a single class. It is unverified whether training and evaluation images came from separate patients. This is exploratory research evidence, not clinical validation.",
    ), encoding="utf-8")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(8.2, 6.2), constrained_layout=True)
    fig.patch.set_facecolor("#f7f5ef"); ax.set_facecolor("#f7f5ef")
    image = ax.imshow(np.asarray(matrix), cmap=plt.get_cmap("GnBu"), vmin=0)
    ax.set_xticks(range(3), display_classes, rotation=20, ha="right")
    ax.set_yticks(range(3), display_classes)
    ax.set_xlabel("Predicted class"); ax.set_ylabel("True class")
    ax.set_title("Reference-model confusion matrix\nRows true, columns predicted · n = 1,028 · each of 4 groups kept out of training in turn", loc="left", pad=18, fontsize=13, fontweight="bold")
    for y in range(3):
        for x in range(3):
            value = matrix[y][x]
            ax.text(x, y, f"{value}\n({value / sum(matrix[y]) * 100:.1f}%)", ha="center", va="center", color="#fffefa" if value > 210 else "#34362f", fontsize=11)
    fig.colorbar(image, ax=ax, shrink=.78, label="Image-patch count")
    fig.text(.01, -.01, "Source: stored confusion-matrix and evaluation records · exploratory; separation between training and evaluation patients unverified · 2026-10-11", fontsize=8, color="#706f66")
    fig.savefig(OUT / "confusion-matrix.svg", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    assert (OUT / "confusion-matrix.html").stat().st_size > 1000
    print("Verified the stored JSON/CSV confusion matrix; wrote local interactive HTML and SVG.")


if __name__ == "__main__":
    main()
