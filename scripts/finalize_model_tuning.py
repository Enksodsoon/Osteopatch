"""Select and fit an all-data artifact for a completed, unqualified campaign.

The artifact is written outside the qualified registry and cannot be selected
by the application. Its fit is for research handoff, not another evaluation.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import model_tuning as tuning


def _persist(path: Path, report: dict) -> None:
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def finalize(args: argparse.Namespace) -> Path:
    report_path = Path(args.report).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "COMPLETE" or report.get("qualification", {}).get("status") != "NOT_QUALIFIED":
        raise ValueError("finalization requires a completed campaign that did not qualify")

    manifest, image_root = Path(args.manifest).resolve(), Path(args.image_root).resolve()
    pretrained = Path(args.pretrained_weights).resolve()
    if tuning.sha256_file(manifest) != report["dataset"]["manifest_sha256"]:
        raise ValueError("manifest hash differs from completed evaluation")
    if tuning.sha256_file(pretrained) != report["pretrained_weights_sha256"]:
        raise ValueError("pretrained checkpoint hash differs from completed evaluation")
    _, rows = tuning._load_rows(manifest, image_root)
    torch, _, torchvision, _, _, _ = tuning._load_ml()
    torch.manual_seed(42)
    torch.set_num_threads(min(6, torch.get_num_threads()))
    transform = tuning.make_transform(torch, torchvision)
    deadline = time.monotonic() + args.budget_seconds
    model = tuning.build_model(torch, torch.nn, torchvision, pretrained)
    features = tuning._embeddings(torch, model, transform, rows, deadline)
    run_log: list[dict] = []
    report["finalization_status"] = "RUNNING"
    report["finalization_runs"] = run_log
    report["finalization_script_sha256"] = tuning.sha256_file(Path(__file__).resolve())
    report["finalization_started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _persist(report_path, report)

    started = time.monotonic()
    groups = sorted({row["group"] for row in rows})
    pooled = {}
    splits = list(tuning.nested_splits(rows, "__none__"))
    if len(splits) != len(groups):
        raise ValueError(f"expected one held-out split per group: {len(groups)} groups, {len(splits)} splits")

    try:
        for name in tuning.CONFIGS:
            predictions, validations = [], []
            for held_out, (train_rows, val_rows) in zip(groups, splits, strict=True):
                result = tuning.train_one(
                    name=name, rows=train_rows, eval_rows=val_rows, features=features,
                    pretrained_path=pretrained, transform=transform, seed=42, device="cpu",
                    deadline=deadline, batch_size=args.batch_size, run_log=run_log,
                )
                run_log[-1]["stage"] = "final_group_heldout_selection"
                run_log[-1]["held_out_group"] = held_out
                predictions.extend(result)
                validations.extend(val_rows)
                _persist(report_path, report)
            pooled[name] = tuning._metric_for_rows(validations, predictions)

        selected = tuning.select_configuration(pooled)
        report["final_configuration"] = selected
        report["final_selection"] = {
            "method": "four-group leave-one-group-out selection on all eligible data",
            "seed": 42,
            "metrics": pooled,
            "selected_configuration": selected,
            "trainable_parameters": tuning.PARAM_COUNTS[selected],
        }
        _persist(report_path, report)

        _, final_model = tuning.train_one(
            name=selected, rows=rows, eval_rows=[], features=features,
            pretrained_path=pretrained, transform=transform, seed=42, device="cpu",
            deadline=deadline, batch_size=args.batch_size, run_log=run_log, return_model=True,
        )
        run_log[-1]["stage"] = "all_data_final_fit"
        model_id = f"osteopatch-unqualified-{report['run_id']}"
        output_dir = Path(args.runtime_model_dir).resolve() / "unqualified"
        output_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = output_dir / f"{model_id}.pt"
        temp_bundle = bundle_path.with_suffix(".pt.tmp")
        bundle = {
            "model_id": model_id,
            "qualification_status": "NOT_QUALIFIED",
            "classes": list(tuning.CLASSES),
            "state_dict": final_model.cpu().state_dict(),
            "preprocessing": {
                "resize": [384, 384], "interpolation": "bilinear", "antialias": True,
                "normalize_mean": [0.485, 0.456, 0.406],
                "normalize_std": [0.229, 0.224, 0.225],
            },
            "evaluation_run_id": report["run_id"],
            "training_configuration": selected,
            "encoder_sha256": tuning._encoder_digest(final_model),
        }
        torch.save(bundle, temp_bundle)
        temp_bundle.replace(bundle_path)
        artifact_hash = tuning.sha256_file(bundle_path)

        loaded = torch.load(bundle_path, map_location="cpu", weights_only=True)
        if loaded["model_id"] != model_id or loaded["qualification_status"] != "NOT_QUALIFIED":
            raise ValueError("saved final artifact identity or qualification metadata did not reload")
        reload_model = torchvision.models.mobilenet_v3_small(weights=None)
        reload_model.classifier[-1] = torch.nn.Linear(1024, len(tuning.CLASSES))
        reload_model.load_state_dict(loaded["state_dict"], strict=True)
        final_model.eval()
        reload_model.eval()
        from PIL import Image

        with Image.open(rows[0]["path"]) as image:
            sample = transform(image.convert("RGB")).unsqueeze(0)
        with torch.inference_mode():
            before = final_model(sample)
            after = reload_model(sample)
        torch.testing.assert_close(before, after, rtol=0, atol=0)

        report["final_all_data_artifact"] = {
            "model_id": model_id,
            "bundle_path": str(bundle_path),
            "bundle_sha256": artifact_hash,
            "qualification_status": "NOT_QUALIFIED",
            "registered": False,
            "application_selectable": False,
            "reload_parity": "PASS",
            "training_configuration": selected,
            "training_images": len(rows),
            "trainable_parameters": tuning.PARAM_COUNTS[selected],
        }
        report["finalization_status"] = "COMPLETE"
        report["finalization_elapsed_sec"] = round(time.monotonic() - started, 2)
        report["total_recorded_compute_sec"] = round(
            float(report.get("elapsed_sec", 0)) + 1445.36 + 4364.55 + report["finalization_elapsed_sec"], 2
        )
        report["finalization_completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _persist(report_path, report)
        return bundle_path
    except tuning.BudgetExceeded as exc:
        report["finalization_status"] = "BUDGET_STOPPED"
        report["finalization_error"] = str(exc)
        report["finalization_elapsed_sec"] = round(time.monotonic() - started, 2)
        _persist(report_path, report)
        raise
    except Exception as exc:
        report["finalization_status"] = "FAILED"
        report["finalization_error"] = f"{type(exc).__name__}: {exc}"
        report["finalization_elapsed_sec"] = round(time.monotonic() - started, 2)
        _persist(report_path, report)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--pretrained-weights", required=True)
    parser.add_argument("--runtime-model-dir", required=True)
    parser.add_argument("--budget-seconds", type=float, default=1800)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    print(finalize(args))


if __name__ == "__main__":
    main()
