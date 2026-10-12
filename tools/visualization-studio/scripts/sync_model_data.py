"""Copy authoritative stored model metrics into the local studio data file."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "tools/visualization-studio/src/data/model-evidence.json"
G4 = ROOT / "aidlc-docs/inception/model/g4"
G5 = ROOT / "aidlc-docs/inception/model/g5"
ORDER = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]


def load(folder: Path) -> tuple[dict, dict]:
    return (json.loads((folder / "overall-oof-metrics.json").read_text(encoding="utf-8")),
            json.loads((folder / "run-configuration.json").read_text(encoding="utf-8")))


def model(metrics: dict, config: dict, *, candidate: bool) -> dict:
    assert metrics["class_order"] == ORDER
    assert metrics["n_rows"] == 1028
    assert [sum(row) for row in metrics["confusion_matrix_rows_true_cols_pred"]] == [484, 290, 254]
    return {
        "recall": [metrics["per_class"][name]["recall"] for name in ORDER],
        "support": [metrics["per_class"][name]["support"] for name in ORDER],
        "macroF1": metrics["macro_f1"],
        "balancedAccuracy": metrics["balanced_accuracy"],
        "status": (config.get("result_classification", "Exploratory candidate")
                   if candidate else "Exploratory reference model; original model file unavailable"),
    }


def main() -> None:
    g4m, g4c = load(G4)
    g5m, g5c = load(G5)
    assert g5m["class_order"] == ORDER and g5m["n_rows"] == g4m["n_rows"]
    assert g5c["result_classification"] == "NO BENEFIT" and not g5c["final_bundle_created"]
    assert g5c["reused_from_g4_immutable"]["groups"] == ["Case-3", "Case-4", "Case-48", "P9"]
    record = {
        "title": "Reference model and tuning candidate recall",
        "date": "2026-10-11",
        "classOrder": ORDER,
        "models": {
            "baseline": model(g4m, g4c, candidate=False),
            "candidate": model(g5m, g5c, candidate=True),
        },
        "aggregation": "Each image was evaluated by a model that did not train on its group; results combined across four groups",
        "calibration": "Scores are not calibrated chance estimates and should not be interpreted as disease probabilities",
        "limitations": "It is unverified whether training and evaluation images came from separate patients; patches from one biological sample may be related. One evaluation group contains only one class.",
        "sources": ["stored baseline evaluation and configuration records",
                    "stored tuning-candidate evaluation and configuration records"],
    }
    DOC.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"verified and synced stored evaluation data to {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
