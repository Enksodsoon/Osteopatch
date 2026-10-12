#!/usr/bin/env python3
"""Bounded, grouped OsteoPatch fine-tuning campaign with durable evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata as package_metadata
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CLASSES = ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")
CLASS_TO_IDX = {name: index for index, name in enumerate(CLASSES)}
CONFIGS = {
    "frozen_inverse": {"kind": "frozen", "tumor_weight": 1.0, "epochs": 10},
    "frozen_tumor2x": {"kind": "frozen", "tumor_weight": 2.0, "epochs": 10},
    "stage12_tumor2x": {"kind": "stage12", "tumor_weight": 2.0, "epochs": 5},
}
WEIGHT_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
FEATURE_STAGE_INDEX = 11  # MobileNetV3-Small final parameterized feature block.


class BudgetExceeded(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def nested_splits(rows: list[dict], outer_group: str):
    groups = sorted({row["group"] for row in rows} - {outer_group})
    for validation_group in groups:
        train = [row for row in rows if row["group"] not in (outer_group, validation_group)]
        validation = [row for row in rows if row["group"] == validation_group]
        if len({row["label"] for row in train}) != len(CLASSES):
            raise ValueError(f"inner training split lacks a class for {outer_group}/{validation_group}")
        yield train, validation


def metrics(labels: list[int], scores: list[list[float]]) -> dict:
    matrix = [[0] * len(CLASSES) for _ in CLASSES]
    for label, score in zip(labels, scores, strict=True):
        matrix[label][max(range(len(CLASSES)), key=score.__getitem__)] += 1
    per_class = {}
    f1_values, recall_values = [], []
    for index, name in enumerate(CLASSES):
        support = sum(matrix[index])
        true_positive = matrix[index][index]
        predicted = sum(row[index] for row in matrix)
        recall = true_positive / support if support else None
        precision = true_positive / predicted if predicted else (0.0 if support else None)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall)
            else (0.0 if support else None)
        )
        per_class[name] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
        if f1 is not None:
            f1_values.append(f1)
        if recall is not None:
            recall_values.append(recall)
    n = len(labels)
    log_loss = None
    if n:
        import math
        log_loss = -sum(math.log(max(1e-12, min(1.0, scores[i][labels[i]]))) for i in range(n)) / n
        brier = sum(sum((scores[i][j] - float(labels[i] == j)) ** 2 for j in range(len(CLASSES))) for i in range(n)) / n
        accuracy = sum(matrix[i][i] for i in range(len(CLASSES))) / n
    else:
        brier = accuracy = None
    return {
        "n": n, "class_order": list(CLASSES), "confusion_matrix": matrix,
        "per_class": per_class,
        "macro_f1": sum(f1_values) / len(CLASSES) if len(f1_values) == len(CLASSES) else None,
        "balanced_accuracy": sum(recall_values) / len(CLASSES) if len(recall_values) == len(CLASSES) else None,
        "accuracy": accuracy, "log_loss": log_loss, "brier": brier,
    }


def select_configuration(candidate_metrics: dict[str, dict]) -> str:
    baseline = candidate_metrics["frozen_inverse"]
    eligible = ["frozen_inverse"]
    for name, result in candidate_metrics.items():
        if name == "frozen_inverse" or result.get("macro_f1") is None:
            continue
        if baseline.get("macro_f1") is None or result["macro_f1"] < baseline["macro_f1"] - 0.02:
            continue
        if any(
            result["per_class"][label]["recall"] is None
            or baseline["per_class"][label]["recall"] is None
            or result["per_class"][label]["recall"] < baseline["per_class"][label]["recall"] - 0.02
            for label in ("NON_TUMOR", "NECROSIS")
        ):
            continue
        eligible.append(name)
    return max(eligible, key=lambda name: (
        candidate_metrics[name]["per_class"]["VIABLE_TUMOR"]["recall"] or 0,
        candidate_metrics[name]["macro_f1"] or 0,
        -PARAM_COUNTS[name],
    ))


PARAM_COUNTS = {"frozen_inverse": 3075, "frozen_tumor2x": 3075, "stage12_tumor2x": 888019}


def qualifies(seeds: list[int], candidate_metrics: list[dict], comparator_metrics: list[dict], group_deltas: dict | None = None) -> bool:
    if seeds != [42, 43, 44] or len(candidate_metrics) != 3 or len(comparator_metrics) != 3:
        return False
    pairs = list(zip(candidate_metrics, comparator_metrics, strict=True))
    if any(candidate.get("macro_f1") is None or baseline.get("macro_f1") is None for candidate, baseline in pairs):
        return False
    if sum(candidate["macro_f1"] - baseline["macro_f1"] for candidate, baseline in pairs) / 3 < 0:
        return False
    tumor_deltas = [c["per_class"]["VIABLE_TUMOR"]["recall"] - b["per_class"]["VIABLE_TUMOR"]["recall"] for c, b in pairs]
    if sum(tumor_deltas) / 3 < 0.05:
        return False
    for label in ("NON_TUMOR", "NECROSIS"):
        deltas = [(c["per_class"][label]["recall"], b["per_class"][label]["recall"]) for c, b in pairs]
        if any(candidate is None or baseline is None for candidate, baseline in deltas):
            return False
        if sum(candidate - baseline for candidate, baseline in deltas) / 3 < -0.02:
            return False
    if group_deltas is not None and any(group_deltas.get(group, 0) <= 0 for group in ("Case-4", "Case-48")):
        return False
    return True


def d4(image):
    from PIL import Image
    flip_lr = Image.Transpose.FLIP_LEFT_RIGHT
    rotate_90 = Image.Transpose.ROTATE_90
    return [image, image.transpose(flip_lr), image.transpose(rotate_90), image.transpose(rotate_90).transpose(flip_lr),
            image.transpose(Image.Transpose.ROTATE_180), image.transpose(Image.Transpose.ROTATE_180).transpose(flip_lr),
            image.transpose(Image.Transpose.ROTATE_270), image.transpose(Image.Transpose.ROTATE_270).transpose(flip_lr)]


def make_transform(torch, torchvision):
    from torchvision.transforms import v2
    return v2.Compose([
        v2.ToImage(),
        v2.Resize((384, 384), interpolation=torchvision.transforms.InterpolationMode.BILINEAR, antialias=True),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])


def build_model(torch, nn, torchvision, pretrained_path: Path):
    model = torchvision.models.mobilenet_v3_small(weights=None)
    weights = torch.load(pretrained_path, map_location="cpu", weights_only=True)
    model.load_state_dict(weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CLASSES))
    return model


def _load_rows(manifest: Path, image_root: Path) -> tuple[list[dict], list[dict]]:
    rows = list(csv.DictReader(manifest.open(encoding="utf-8-sig", newline="")))
    for row in rows:
        path = image_root / f"{row['image_id']}.tiff"
        if not path.is_file():
            raise FileNotFoundError(f"dataset image missing: {path}")
        actual = sha256_file(path)
        if actual != row["sha256"]:
            raise ValueError(f"dataset image hash mismatch: {row['image_id']}")
        row["path"] = str(path)
        row["group"] = row["group"]
        row["label"] = CLASS_TO_IDX[row["canonical_label"]] if row["training_eligible"].lower() == "true" else -1
    eligible = [row for row in rows if row["label"] >= 0]
    if len(rows) != 1144 or len(eligible) != 1028:
        raise ValueError(f"unexpected dataset counts: total={len(rows)} eligible={len(eligible)}")
    return rows, eligible


def _load_ml():
    import torch
    import torch.nn as nn
    import torchvision
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset
    return torch, nn, torchvision, DataLoader, Dataset, Image


def _class_weights(torch, rows: list[dict], tumor_weight: float):
    counts = Counter(row["label"] for row in rows)
    if set(counts) != set(range(len(CLASSES))):
        raise ValueError(f"training split lacks canonical class: {counts}")
    weights = torch.tensor([sum(counts.values()) / (len(CLASSES) * counts[i]) for i in range(len(CLASSES))], dtype=torch.float32)
    weights[CLASS_TO_IDX["VIABLE_TUMOR"]] *= tumor_weight
    return weights / weights.mean()


def _embeddings(torch, model, transform, rows, deadline):
    from PIL import Image
    prefix = torch.nn.Sequential(model.features, model.avgpool, torch.nn.Flatten(1), *list(model.classifier.children())[:-1]).eval()
    result = {}
    with torch.inference_mode():
        for index, row in enumerate(rows):
            if time.monotonic() > deadline:
                raise BudgetExceeded("four-hour limit reached while caching frozen embeddings")
            with Image.open(row["path"]) as image:
                tensors = torch.stack([transform(view.convert("RGB")) for view in d4(image.convert("RGB"))])
            result[row["image_id"]] = prefix(tensors).cpu()
            if index and index % 128 == 0:
                print(f"cached frozen features {index}/{len(rows)}", flush=True)
    return result


def _state_digest(model) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _encoder_digest(model) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        if name.startswith("classifier.3."):
            continue
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _save_fold_checkpoint(torch, model, path: Path, *, name: str, seed: int, held_out_group: str):
    trainable = {key for key, parameter in model.named_parameters() if parameter.requires_grad}
    checkpoint = {
        "configuration": name, "seed": seed, "held_out_group": held_out_group,
        "classes": list(CLASSES), "pretrained_weights_sha256": WEIGHT_SHA256,
        "state_dict": {key: tensor.detach().cpu() for key, tensor in model.state_dict().items() if key in trainable},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, path)
    return sha256_file(path)


def _predict_frozen(torch, model, features, rows, batch_size=64):
    model.eval()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            x = torch.cat([features[row["image_id"]][0:1] for row in rows[start:start + batch_size]])
            outputs.extend(torch.softmax(model(x), dim=1).tolist())
    return outputs


def _mark_current_run(run_log, status, error):
    for record in reversed(run_log):
        if record.get("status") == "RUNNING":
            record.update(status=status, error=error)
            break


def train_one(*, name, rows, eval_rows=None, features, pretrained_path, transform, seed, device, deadline, batch_size, run_log, return_model=False):
    torch, nn, torchvision, DataLoader, Dataset, Image = _load_ml()
    eval_rows = rows if eval_rows is None else eval_rows
    torch.manual_seed(seed)
    random.seed(seed)
    torch.set_num_threads(min(6, torch.get_num_threads()))
    spec = CONFIGS[name]
    model = build_model(torch, nn, torchvision, pretrained_path).to(device)
    class_weights = _class_weights(torch, rows, spec["tumor_weight"]).to(device)
    history = []
    start = time.monotonic()
    record = {"name": name, "seed": seed, "n_train": len(rows), "n_eval": len(eval_rows),
              "epochs": 0, "epoch_loss": history, "duration_sec": None, "batch_size": batch_size,
              "state_sha256": None, "trainable_parameters": PARAM_COUNTS[name], "status": "RUNNING"}
    run_log.append(record)
    if spec["kind"] == "frozen":
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        head = model.classifier[-1]
        for parameter in head.parameters():
            parameter.requires_grad_(True)
        head.to(device)
        optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
        labels = torch.tensor([row["label"] for row in rows], dtype=torch.long)
        xrows = [(row, features[row["image_id"]]) for row in rows]
        torch_generator = torch.Generator().manual_seed(seed)
        for _epoch in range(spec["epochs"]):
            if time.monotonic() > deadline:
                raise BudgetExceeded("four-hour limit reached during frozen-head training")
            order = torch.randperm(len(rows), generator=torch_generator).tolist()
            total, seen = 0.0, 0
            head.train()
            for begin in range(0, len(order), batch_size):
                if time.monotonic() > deadline:
                    raise BudgetExceeded("four-hour limit reached during frozen-head training")
                ix = order[begin:begin + batch_size]
                # Pick one of the eight deterministic D4 views per image.
                x = torch.stack([xrows[i][1][random.randrange(8)] for i in ix]).to(device)
                y = labels[ix].to(device)
                optimizer.zero_grad(set_to_none=True)
                logits = head(torch.nn.functional.dropout(x, p=0.2, training=True))
                loss = nn.functional.cross_entropy(logits, y, weight=class_weights)
                loss.backward(); optimizer.step()
                total += float(loss.detach()) * len(ix); seen += len(ix)
            history.append(total / seen)
        if time.monotonic() > deadline:
            raise BudgetExceeded("four-hour limit reached before frozen-head evaluation")
        logits = _predict_frozen(torch, head, features, eval_rows)
    else:
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        for parameter in model.features[FEATURE_STAGE_INDEX].parameters():
            parameter.requires_grad_(True)
        for parameter in model.classifier.parameters():
            parameter.requires_grad_(True)

        class PatchDataset(Dataset):
            def __len__(self): return len(rows)
            def __getitem__(self, index):
                with Image.open(rows[index]["path"]) as image:
                    image = image.convert("RGB")
                    image = random.choice(d4(image))
                    tensor = transform(image)
                return tensor, rows[index]["label"]

        generator = torch.Generator().manual_seed(seed)
        loader = DataLoader(PatchDataset(), batch_size=batch_size, shuffle=True, num_workers=0, generator=generator)
        optimizer = torch.optim.AdamW([
            {"params": model.features[FEATURE_STAGE_INDEX].parameters(), "lr": 3e-6},
            {"params": model.classifier.parameters(), "lr": 1e-4},
        ], weight_decay=1e-4)
        for _epoch in range(spec["epochs"]):
            if time.monotonic() > deadline:
                raise BudgetExceeded("four-hour limit reached during final-stage fine-tuning")
            model.train()
            for module in model.modules():
                if isinstance(module, nn.modules.batchnorm._BatchNorm):
                    module.eval()
            total, seen = 0.0, 0
            for x, y in loader:
                if time.monotonic() > deadline:
                    raise BudgetExceeded("four-hour limit reached during final-stage fine-tuning")
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = nn.functional.cross_entropy(model(x), y, weight=class_weights)
                loss.backward(); optimizer.step()
                total += float(loss.detach()) * len(y); seen += len(y)
            history.append(total / seen)
        model.eval()
        outputs = []
        with torch.inference_mode():
            for row in eval_rows:
                if time.monotonic() > deadline:
                    raise BudgetExceeded("four-hour limit reached during held-out evaluation")
                with Image.open(row["path"]) as image:
                    tensor = transform(image.convert("RGB")).unsqueeze(0).to(device)
                outputs.append(torch.softmax(model(tensor), dim=1)[0].cpu().tolist())
        logits = outputs
    record.update(status="COMPLETE", epochs=len(history), duration_sec=round(time.monotonic() - start, 2),
                  state_sha256=_state_digest(model),
                  trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))
    return (logits, model) if return_model else logits


def _metric_for_rows(rows, scores):
    return metrics([row["label"] for row in rows], scores)


def run_campaign(args):
    project = Path(__file__).resolve().parents[1]
    manifest = Path(args.manifest) if args.manifest else project / "aidlc-docs/inception/full-image-qc/full-image-qc-results.csv"
    image_root = Path(args.image_root)
    pretrained = Path(args.pretrained_weights)
    if not 0 < args.budget_hours <= 4:
        raise ValueError("budget-hours must be greater than zero and at most four")
    if args.batch_size < 1 or not args.seeds or len(args.seeds) != len(set(args.seeds)):
        raise ValueError("batch size and unique seed list must be positive")
    if args.batch_size < 16 and args.batch_size_reduction_reason == "none":
        raise ValueError("a memory-driven batch-size reduction requires an explicit reason")
    if not pretrained.is_file() or sha256_file(pretrained).lower() != WEIGHT_SHA256:
        raise ValueError("pretrained ImageNet weights do not match the pinned MobileNetV3-Small SHA-256")
    all_rows, rows = _load_rows(manifest, image_root)
    if len({row["group"] for row in rows}) != 4:
        raise ValueError("expected exactly four verified case/slide groups")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.output) if args.output else project / "docs/evidence/model-tuning" / run_id
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + args.budget_hours * 3600
    git_revision = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    git_dirty = subprocess.run(["git", "-C", str(project), "status", "--porcelain"], capture_output=True, text=True, check=False)
    report = {
        "run_id": run_id, "status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(),
        "budget_hours": args.budget_hours, "device": "cpu", "torch": None, "torchvision": None,
        "hardware": {"platform": platform.platform(), "processor": platform.processor(),
                     "logical_cpu_count": os.cpu_count(), "python": sys.version.split()[0],
                     "batch_size": args.batch_size,
                     "batch_size_reduction": ({"from": 16, "to": args.batch_size,
                                               "reason": args.batch_size_reduction_reason}
                                              if args.batch_size < 16 else None),
                     "gpu_probe": "CPU selected; locked environment has no CUDA runtime"},
        "training_contract": {"optimizer": "AdamW", "weight_decay": 1e-4,
                              "head_learning_rate": 1e-3, "feature_learning_rate": 3e-6,
                              "stage_classifier_learning_rate": 1e-4, "loss": "inverse-frequency weighted cross-entropy",
                              "head_dropout": 0.2, "batch_size": args.batch_size,
                              "resize": [384, 384], "interpolation": "bilinear", "antialias": True,
                              "augmentation": "train-only random D4 flips and 90-degree rotations",
                              "validation_augmentation": "none", "batchnorm_statistics": "frozen",
                              "seeds": args.seeds},
        "historical_comparison": {"g4_macro_f1": 0.5623, "g4_viable_tumor_recall": 0.1103,
                                  "g5_reported_outcome": "regressed macro-F1 and viable-tumor recall",
                                  "g5_metrics_available": False},
        "seeds_requested": args.seeds, "seeds_complete": [], "dataset": {"total": len(all_rows), "eligible": len(rows),
        "excluded": len(all_rows)-len(rows), "manifest_sha256": sha256_file(manifest), "image_root": str(image_root),
        "split_sha256": hashlib.sha256("\n".join(
            f"{r['image_id']}\t{r['group']}\t{r['canonical_label']}\t{r['training_eligible']}" for r in all_rows
        ).encode()).hexdigest(),
        "image_hashes_verified": len(all_rows), "excluded_image_ids": [r["image_id"] for r in all_rows if r["label"] < 0],
        "group_support": {g: {name: sum(CLASSES[row["label"]] == name for row in rows if row["group"] == g)
                              for name in CLASSES} for g in sorted({r['group'] for r in rows})}},
        "pretrained_weights_sha256": WEIGHT_SHA256, "pretrained_weights_path": str(pretrained.resolve()),
        "training_script_sha256": sha256_file(Path(__file__).resolve()),
        "git_commit": git_revision.stdout.strip() if git_revision.returncode == 0 else None,
        "git_worktree_dirty": bool(git_dirty.stdout.strip()),
        "reproduction_command": f"uv run --locked --extra dev --extra model python scripts/model_tuning.py --image-root \"{image_root}\" --pretrained-weights \"{pretrained}\" --manifest \"{manifest}\" --runtime-model-dir \"{args.runtime_model_dir}\" --budget-hours {args.budget_hours} --batch-size {args.batch_size} --batch-size-reduction-reason \"{args.batch_size_reduction_reason}\" --seeds {','.join(map(str, args.seeds))}",
        "configs": CONFIGS, "training_runs": [],
        "seeds": {}, "qualification": {"status": "NOT_QUALIFIED", "reason": "campaign incomplete"},
    }
    def persist():
        report["elapsed_sec"] = round(time.monotonic() - campaign_start, 2)
        if report["status"] != "RUNNING":
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
        (out / "run-report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    campaign_start = time.monotonic()
    try:
        torch, _, torchvision, _, _, _ = _load_ml()
        report["torch"], report["torchvision"] = torch.__version__, torchvision.__version__
        report["dependencies"] = {}
        for package in ("torch", "torchvision", "pillow", "numpy", "grad-cam"):
            try:
                report["dependencies"][package] = package_metadata.version(package)
            except package_metadata.PackageNotFoundError:
                report["dependencies"][package] = None
        transform = make_transform(torch, torchvision)
        torch.manual_seed(42); torch.set_num_threads(min(6, torch.get_num_threads()))
        model = build_model(torch, torch.nn, torchvision, pretrained)
        features = _embeddings(torch, model, transform, rows, deadline)
        groups = sorted({row["group"] for row in rows})
        for seed in args.seeds:
            seed_data = {"outer_folds": {}, "complete": False}
            report["seeds"][str(seed)] = seed_data
            for outer_group in groups:
                outer_train = [row for row in rows if row["group"] != outer_group]
                outer_test = [row for row in rows if row["group"] == outer_group]
                inner_predictions = {name: {} for name in CONFIGS}
                inner_rows = {name: {} for name in CONFIGS}
                for train_rows, val_rows in nested_splits(rows, outer_group):
                    for name in CONFIGS:
                        predictions = train_one(name=name, rows=train_rows, eval_rows=val_rows, features=features, pretrained_path=pretrained,
                                                transform=transform, seed=seed, device="cpu", deadline=deadline,
                                                batch_size=args.batch_size, run_log=report["training_runs"])
                        inner_predictions[name].update({r["image_id"]: p for r, p in zip(val_rows, predictions, strict=True)})
                        inner_rows[name].update({r["image_id"]: r for r in val_rows})
                        persist()
                selection = {}
                for name in CONFIGS:
                    ordered = [r for r in rows if r["image_id"] in inner_rows[name]]
                    selection[name] = _metric_for_rows(ordered, [inner_predictions[name][r["image_id"]] for r in ordered])
                selected = select_configuration(selection)
                selected_scores, selected_model = train_one(name=selected, rows=outer_train, eval_rows=outer_test, features=features, pretrained_path=pretrained,
                                            transform=transform, seed=seed, device="cpu", deadline=deadline,
                                            batch_size=args.batch_size, run_log=report["training_runs"], return_model=True)
                if time.monotonic() > deadline:
                    raise BudgetExceeded("four-hour limit reached before saving the selected fold checkpoint")
                checkpoint = Path(args.runtime_model_dir) / "tuning-checkpoints" / f"{run_id}-seed{seed}-{outer_group}.pt"
                checkpoint_hash = _save_fold_checkpoint(torch, selected_model, checkpoint,
                                                        name=selected, seed=seed, held_out_group=outer_group)
                report["training_runs"][-1].update(checkpoint_path=str(checkpoint), checkpoint_sha256=checkpoint_hash)
                baseline_scores = train_one(name="frozen_inverse", rows=outer_train, eval_rows=outer_test, features=features, pretrained_path=pretrained,
                                            transform=transform, seed=seed, device="cpu", deadline=deadline,
                                            batch_size=args.batch_size, run_log=report["training_runs"])
                fold = {"selected_configuration": selected, "inner_metrics": selection,
                        "selected_checkpoint": {"path": str(checkpoint), "sha256": checkpoint_hash},
                        "selected_metrics": _metric_for_rows(outer_test, selected_scores),
                        "comparator_metrics": _metric_for_rows(outer_test, baseline_scores),
                        "predictions": [{"image_id": r["image_id"], "group": r["group"], "label": r["label"],
                                         "scores": p} for r, p in zip(outer_test, selected_scores, strict=True)],
                        "comparator_predictions": [{"image_id": r["image_id"], "group": r["group"], "label": r["label"],
                                                     "scores": p} for r, p in zip(outer_test, baseline_scores, strict=True)]}
                seed_data["outer_folds"][outer_group] = fold
                persist()
            candidate_rows = [item for fold in seed_data["outer_folds"].values() for item in fold["predictions"]]
            comparator_rows = [item for fold in seed_data["outer_folds"].values() for item in fold["comparator_predictions"]]
            seed_data["metrics"] = _metric_for_rows(candidate_rows, [r["scores"] for r in candidate_rows])
            seed_data["comparator_metrics"] = _metric_for_rows(comparator_rows, [r["scores"] for r in comparator_rows])
            seed_data["complete"] = True
            report["seeds_complete"].append(seed)
            persist()
        group_deltas = {}
        complete = [report["seeds"][str(s)] for s in report["seeds_complete"]]
        if len(complete) == 3:
            for group in ("Case-4", "Case-48"):
                ds = []
                for seed in complete:
                    fold = seed["outer_folds"].get(group)
                    if fold and fold["selected_metrics"]["per_class"]["VIABLE_TUMOR"]["recall"] is not None:
                        ds.append(fold["selected_metrics"]["per_class"]["VIABLE_TUMOR"]["recall"] - fold["comparator_metrics"]["per_class"]["VIABLE_TUMOR"]["recall"])
                group_deltas[group] = sum(ds) / len(ds) if len(ds) == 3 else 0
            report["qualification"] = {"status": "QUALIFIED" if qualifies(args.seeds, [s["metrics"] for s in complete], [s["comparator_metrics"] for s in complete], group_deltas) else "NOT_QUALIFIED",
                                        "group_viable_tumor_recall_delta": group_deltas,
                                        "gate": "3 seeds; mean viable recall +0.05; macro-F1 nondecreasing; other class recalls within -0.02; improvement in Case-4 and Case-48"}
        report["status"] = "COMPLETE"
    except BudgetExceeded as exc:
        _mark_current_run(report["training_runs"], "BUDGET_STOPPED", str(exc))
        report["status"] = "BUDGET_STOPPED"
        report["qualification"] = {"status": "NOT_QUALIFIED", "reason": str(exc)}
    except Exception as exc:
        _mark_current_run(report["training_runs"], "FAILED", f"{type(exc).__name__}: {exc}")
        report["status"] = "FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        persist()
        raise
    finally:
        persist()
        _write_outputs(out, report)
    _write_outputs(out, report)
    if report["qualification"]["status"] == "QUALIFIED":
        try:
            _fit_qualified(args, rows, features, transform, pretrained, report, out, deadline)
        except BudgetExceeded as exc:
            _mark_current_run(report["training_runs"], "BUDGET_STOPPED", str(exc))
            report["status"] = "BUDGET_STOPPED"
            report["qualification"] = {"status": "NOT_QUALIFIED", "reason": str(exc)}
        except Exception as exc:
            _mark_current_run(report["training_runs"], "FAILED", f"{type(exc).__name__}: {exc}")
            report["status"] = "FAILED"
            report["qualification"] = {"status": "NOT_QUALIFIED", "reason": f"final bundle creation failed: {type(exc).__name__}: {exc}"}
            report["final_fit_error"] = f"{type(exc).__name__}: {exc}"
            persist()
            _write_outputs(out, report)
            raise
        persist()
        _write_outputs(out, report)
    return out


def _write_outputs(out: Path, report: dict):
    predictions = []
    errors = []
    for seed, data in report["seeds"].items():
        for group, fold in data["outer_folds"].items():
            for kind in ("predictions", "comparator_predictions"):
                for row in fold[kind]:
                    score = row["scores"]
                    predicted = CLASSES[max(range(len(CLASSES)), key=score.__getitem__)]
                    record = {"seed": seed, "model": "selected" if kind == "predictions" else "fresh_g4_comparator",
                              "outer_group": group, "image_id": row["image_id"], "true_class": CLASSES[row["label"]],
                              "predicted_class": predicted,
                              **{f"score_{CLASSES[i]}": score[i] for i in range(len(CLASSES))}}
                    predictions.append(record)
                    if predicted != record["true_class"]:
                        errors.append(record)
    if predictions:
        with (out / "oof-predictions.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=predictions[0]); writer.writeheader(); writer.writerows(predictions)
    with (out / "error-review.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["seed", "model", "outer_group", "image_id", "true_class", "predicted_class",
                  "score_NON_TUMOR", "score_VIABLE_TUMOR", "score_NECROSIS"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(errors)
    with (out / "excluded-images.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_id"]); writer.writeheader()
        writer.writerows({"image_id": image_id} for image_id in report["dataset"]["excluded_image_ids"])
    (out / "report.md").write_text(_report_markdown(report), encoding="utf-8")
    (out / "model-card.md").write_text(_model_card(report), encoding="utf-8")


def _report_markdown(report):
    rows = ["# OsteoPatch model tuning report", "", f"Run: `{report['run_id']}`", f"Status: **{report['status']}**",
            f"Device: `{report['device']}`; elapsed: {report.get('elapsed_sec', 0):.0f}s / {report['budget_hours']*3600:.0f}s",
            f"Eligible images: {report['dataset']['eligible']} / {report['dataset']['total']}; four slide/case groups; patient independence unverified.",
            f"Qualification: **{report['qualification']['status']}** — {report['qualification'].get('reason', report['qualification'].get('gate',''))}", "",
            "All scores are uncalibrated research outputs. This evaluation does not establish patient-level or clinical performance.", "",
            "Historical G4 is descriptive only: macro-F1 **0.5623**, viable-tumor recall **0.1103**.", "",
            "Handoff evidence reports G5 regressed both metrics; exact G5 values are unavailable, so no numeric comparison is made.", "",
            "## Per-seed out-of-fold metrics", "", "| Seed | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |", "|---:|---:|---:|---:|---:|"]
    for seed, data in report["seeds"].items():
        if not data.get("complete"):
            continue
        candidate, baseline = data["metrics"], data["comparator_metrics"]
        rows.append(f"| {seed} | {candidate['macro_f1']} | {candidate['per_class']['VIABLE_TUMOR']['recall']} | {baseline['macro_f1']} | {baseline['per_class']['VIABLE_TUMOR']['recall']} |")
    rows += ["", "## Outer-fold group results", "", "| Seed | Held-out group | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |", "|---:|---|---:|---:|---:|---:|"]
    for seed, data in report["seeds"].items():
        for group, fold in data["outer_folds"].items():
            candidate, baseline = fold["selected_metrics"], fold["comparator_metrics"]
            cr = candidate["per_class"]["VIABLE_TUMOR"]["recall"]
            br = baseline["per_class"]["VIABLE_TUMOR"]["recall"]
            rows.append(f"| {seed} | {group} | {candidate['macro_f1']} | {cr if cr is not None else 'NA'} | {baseline['macro_f1']} | {br if br is not None else 'NA'} |")
    rows += ["", "## Per-class support and metrics", "", "Fold-level confusion matrices, per-class precision/recall/F1/support, balanced accuracy, log loss, and Brier score are in `run-report.json`. Undefined metrics are `null` when a held-out group lacks that class.", "",
             "## Failed or incomplete experiments", "", "| Configuration | Seed | Status | Epochs completed | Detail |", "|---|---:|---|---:|---|"]
    incomplete = [r for r in report["training_runs"] if r.get("status") != "COMPLETE"]
    if incomplete:
        for run in incomplete:
            rows.append(f"| {run['name']} | {run['seed']} | {run.get('status')} | {run.get('epochs', 0)} | {run.get('error', '')} |")
    else:
        rows.append("| None | | | | |")
    rows += ["",
             "## Reproduction", "", f"`{report.get('reproduction_command', 'See the scheduled runner script.')}`", "",
             "The exact environment, image and split hashes, fold selection metrics, epoch losses, parameter counts, checkpoint hashes, timings, hardware, and failure details are in `run-report.json`. `oof-predictions.csv`, `error-review.csv`, and `excluded-images.csv` contain the completed prediction and review exports.", ""]
    return "\n".join(rows)


def _model_card(report):
    candidate = report.get("final_model", {})
    model_id = candidate.get("model_id", "No candidate bundle")
    return "\n".join([
        "# OsteoPatch tuning model card", "", f"Run: `{report['run_id']}`",
        f"Qualification: **{report['qualification']['status']}**",
        f"Model ID: `{model_id}`", f"Final configuration: `{report.get('final_configuration', 'not selected')}`", "",
        "## Intended use", "Exploratory research comparison of three-class patch scoring on the verified OsteoPatch full-image QC dataset.", "",
        "## Evaluation and data", f"{report['dataset']['eligible']} eligible images from four case/slide groups; {report['dataset']['excluded']} excluded images retained in the manifest. Patient independence is unverified.",
        "Outer evaluation uses leave-one-group-out folds. Inner group-held-out predictions choose among the frozen-head comparator, a 2x viable-tumor loss-weighted head, and 2x weighted final-feature-stage fine-tuning.", "",
        "## Performance and limitations", "Per-seed and per-group metrics, including absent-class support, are in `report.md` and `run-report.json`. Scores are uncalibrated. Small group count and unverified patient independence limit generalization claims; this is not a clinical or diagnostic model.",
        "If a candidate bundle exists, its all-data fit follows group-held-out procedure selection; its own fit is not an independent evaluation. The outer-fold results evaluate the training procedure.", "",
        "Historical reference: G4 macro-F1 0.5623 and viable-tumor recall 0.1103. The handoff reports a G5 regression on both, without exact values.", "",
        "## Qualification decision", report["qualification"].get("reason", report["qualification"].get("gate", "Campaign incomplete.")), "",
        "## Provenance", f"Pretrained checkpoint SHA-256: `{report['pretrained_weights_sha256']}`.",
        f"Manifest SHA-256: `{report['dataset']['manifest_sha256']}`; split SHA-256: `{report['dataset']['split_sha256']}`.",
        "Full software, hardware, training, and artifact hashes are in `run-report.json`.", "",
    ])


def _fit_qualified(args, rows, features, transform, pretrained, report, out, deadline):
    pooled = {}
    for name in CONFIGS:
        predictions, validations = [], []
        for train_rows, val_rows in nested_splits(rows, "__none__"):
            result = train_one(name=name, rows=train_rows, eval_rows=val_rows, features=features, pretrained_path=pretrained,
                               transform=transform, seed=42, device="cpu", deadline=deadline,
                               batch_size=args.batch_size, run_log=report["training_runs"])
            predictions.extend(result); validations.extend(val_rows)
        pooled[name] = _metric_for_rows(validations, predictions)
    selected = select_configuration(pooled)
    report["final_configuration"] = selected
    if selected == "frozen_inverse":
        report["qualification"] = {"status": "NOT_QUALIFIED", "reason": "group-held-out final selection chose fresh comparator"}
        (out / "run-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (out / "report.md").write_text(_report_markdown(report), encoding="utf-8")
        return
    torch, _, _, _, _, _ = _load_ml()
    _, bundle_model = train_one(name=selected, rows=rows, eval_rows=[], features=features, pretrained_path=pretrained,
                             transform=transform, seed=42, device="cpu", deadline=deadline,
                             batch_size=args.batch_size, run_log=report["training_runs"], return_model=True)
    model_id = f"osteopatch-tuned-{report['run_id']}"
    model_path = Path(args.runtime_model_dir) / f"{model_id}.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"model_id": model_id, "classes": list(CLASSES), "state_dict": bundle_model.cpu().state_dict(),
              "preprocessing": {"resize": [384, 384], "interpolation": "bilinear", "antialias": True,
                               "normalize_mean": [0.485, 0.456, 0.406], "normalize_std": [0.229, 0.224, 0.225]},
              "evaluation_run_id": report["run_id"], "training_configuration": selected,
              "encoder_sha256": _encoder_digest(bundle_model)}
    torch.save(bundle, model_path)
    artifact_hash = sha256_file(model_path)
    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"models": []}
    registry["models"] = [item for item in registry.get("models", []) if item.get("model_id") != model_id]
    registry["models"].append({"model_id": model_id, "bundle_path_relative": (Path("models") / model_path.name).as_posix(),
                               "bundle_sha256": artifact_hash, "qualification_status": "QUALIFIED",
                               "evaluation_report": str((out / "run-report.json").resolve())})
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    report["final_model"] = {"model_id": model_id, "bundle_path": str(model_path), "bundle_sha256": artifact_hash,
                             "selection_metrics": pooled, "configuration": selected}
    report["qualification"]["status"] = "QUALIFIED"
    (out / "run-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "report.md").write_text(_report_markdown(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", required=True, help="Directory containing verified <image_id>.tiff files")
    parser.add_argument("--pretrained-weights", required=True, help="Cached torchvision MobileNetV3-Small ImageNet weights")
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--run-id")
    parser.add_argument("--budget-hours", type=float, default=4.0)
    parser.add_argument("--runtime-model-dir", default="runtime-artifacts/models")
    parser.add_argument("--registry", default="docs/evidence/model-tuning/qualified-models.json")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--batch-size-reduction-reason", default="none")
    parser.add_argument("--seeds", type=lambda value: [int(x) for x in value.split(",")], default=[42, 43, 44])
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    args.run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.output = args.output or str(project / "docs/evidence/model-tuning" / args.run_id)
    try:
        out = run_campaign(args)
    except Exception as exc:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / "run-report.json"
        if not report_path.exists():
            report_path.write_text(json.dumps({
                "run_id": args.run_id, "status": "FAILED", "failure_phase": "preflight",
                "error": f"{type(exc).__name__}: {exc}", "budget_hours": args.budget_hours,
                "configs": CONFIGS, "completed_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2), encoding="utf-8")
            (out / "report.md").write_text(
                f"# OsteoPatch model tuning report\n\nRun: `{args.run_id}`\n\nStatus: **FAILED during preflight**\n\n{type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
        raise
    print(f"Evidence: {out}", flush=True)


if __name__ == "__main__":
    main()
