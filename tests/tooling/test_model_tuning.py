import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from model_tuning import (  # noqa: E402
    _save_fold_checkpoint,
    _write_outputs,
    metrics,
    nested_splits,
    qualifies,
    select_configuration,
    sha256_file,
)


def test_nested_splits_keep_validation_group_out_of_training():
    rows = [
        {"image_id": f"{group}-{label}", "group": group, "label": label}
        for group in ("A", "B", "C", "D")
        for label in (0, 1, 2)
    ]
    splits = list(nested_splits(rows, "D"))
    assert len(splits) == 3
    assert all(not ({r["group"] for r in train} & {r["group"] for r in val}) for train, val in splits)
    assert all({r["group"] for r in train} | {r["group"] for r in val} == {"A", "B", "C"} for train, val in splits)


def test_nested_splits_reject_training_partition_missing_a_class():
    rows = [
        {"image_id": f"{group}-{label}", "group": group, "label": label}
        for group, labels in (("A", (0, 1, 2)), ("B", (0, 1)), ("C", (0, 1)), ("D", (0, 1)))
        for label in labels
    ]
    import pytest
    with pytest.raises(ValueError, match="lacks a class"):
        list(nested_splits(rows, "D"))


def test_metrics_report_class_support_and_balanced_scores():
    result = metrics([0, 1, 2, 1], [[0.8, 0.1, 0.1], [0.2, 0.7, 0.1], [0.1, 0.2, 0.7], [0.2, 0.7, 0.1]])
    assert result["confusion_matrix"] == [[1, 0, 0], [0, 2, 0], [0, 0, 1]]
    assert result["per_class"]["VIABLE_TUMOR"]["support"] == 2
    assert result["macro_f1"] == 1.0
    absent = metrics([0], [[1.0, 0.0, 0.0]])
    assert absent["per_class"]["VIABLE_TUMOR"]["recall"] is None
    absent_but_predicted = metrics([0], [[0.1, 0.8, 0.1]])
    assert absent_but_predicted["per_class"]["VIABLE_TUMOR"]["support"] == 0
    assert absent_but_predicted["per_class"]["VIABLE_TUMOR"]["recall"] is None
    assert absent_but_predicted["per_class"]["VIABLE_TUMOR"]["f1"] is None


def test_qualification_fails_closed_on_incomplete_or_imbalanced_runs():
    baseline = {"macro_f1": 0.6, "per_class": {"NON_TUMOR": {"recall": 0.8}, "VIABLE_TUMOR": {"recall": 0.1}, "NECROSIS": {"recall": 0.7}}}
    improved = {"macro_f1": 0.6, "per_class": {"NON_TUMOR": {"recall": 0.8}, "VIABLE_TUMOR": {"recall": 0.16}, "NECROSIS": {"recall": 0.7}}}
    assert qualifies([42, 43, 44], [improved] * 3, [baseline] * 3)
    assert not qualifies([42], [improved], [baseline])
    worse_balance = {**improved, "macro_f1": 0.59}
    assert not qualifies([42, 43, 44], [worse_balance] * 3, [baseline] * 3)
    assert not qualifies([42, 43, 44], [improved] * 3, [baseline] * 3, {"Case-4": 0.1, "Case-48": 0.0})


def test_inner_selection_maximizes_viable_recall_after_balance_gate():
    def result(macro, non_tumor, tumor, necrosis):
        return {"macro_f1": macro, "per_class": {
            "NON_TUMOR": {"recall": non_tumor}, "VIABLE_TUMOR": {"recall": tumor},
            "NECROSIS": {"recall": necrosis},
        }}
    candidates = {
        "frozen_inverse": result(.60, .80, .20, .70),
        "frozen_tumor2x": result(.61, .79, .30, .69),
        "stage12_tumor2x": result(.59, .79, .36, .69),
    }
    assert select_configuration(candidates) == "stage12_tumor2x"


def test_report_exports_outer_errors_and_preserved_exclusions(tmp_path):
    result = {"macro_f1": 0.5, "per_class": {"VIABLE_TUMOR": {"recall": 0.25}}}
    selected = {"image_id": "img-a", "group": "Case-4", "label": 1, "scores": [0.7, 0.2, 0.1]}
    comparator = {"image_id": "img-a", "group": "Case-4", "label": 1, "scores": [0.1, 0.8, 0.1]}
    report = {
        "run_id": "unit", "status": "BUDGET_STOPPED", "budget_hours": 4, "elapsed_sec": 5, "device": "cpu",
        "dataset": {"eligible": 1, "total": 2, "excluded": 1, "excluded_image_ids": ["excluded-1"],
                    "manifest_sha256": "manifest", "split_sha256": "split"},
        "qualification": {"status": "NOT_QUALIFIED", "reason": "budget exhausted"},
        "pretrained_weights_sha256": "weights",
        "reproduction_command": "uv run python scripts/model_tuning.py",
        "training_runs": [],
        "seeds": {"42": {"complete": True, "metrics": result, "comparator_metrics": result,
                          "outer_folds": {"Case-4": {
                              "selected_metrics": result, "comparator_metrics": result,
                              "predictions": [selected], "comparator_predictions": [comparator],
                          }}}},
    }
    _write_outputs(tmp_path, report)
    import csv
    with (tmp_path / "error-review.csv").open(encoding="utf-8", newline="") as stream:
        errors = list(csv.DictReader(stream))
    assert [(row["model"], row["image_id"]) for row in errors] == [("selected", "img-a")]
    assert "excluded-1" in (tmp_path / "excluded-images.csv").read_text(encoding="utf-8")
    assert (tmp_path / "model-card.md").is_file()


def test_fold_checkpoint_hashes_only_trainable_weights(tmp_path):
    import pytest

    torch = pytest.importorskip("torch")
    import torch.nn as nn

    model = nn.Sequential(nn.Linear(2, 2), nn.Linear(2, 1))
    for parameter in model[0].parameters():
        parameter.requires_grad_(False)
    path = tmp_path / "fold.pt"
    digest = _save_fold_checkpoint(torch, model, path, name="frozen_inverse", seed=42, held_out_group="Case-4")
    bundle = torch.load(path, map_location="cpu", weights_only=True)
    assert set(bundle["state_dict"]) == {"1.weight", "1.bias"}
    assert bundle["held_out_group"] == "Case-4"
    assert digest == sha256_file(path)
