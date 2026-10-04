// i18n-ready string table. Components reference t('key'); a Thai table can be
// added later as STRINGS.th without rewriting any component. Pathology terms are
// kept in English per the reviewer-language preference.

export type Locale = "en";

const en = {
  "app.title": "OsteoPatch Review",
  "app.subtitle": "Local educational prototype",

  "nav.workbench": "Workbench",
  "nav.modelCard": "Model card",
  "nav.attribution": "Model attribution",

  "disclaimer.short":
    "Educational / research prototype — NOT for diagnosis, treatment decisions, treatment-response prediction, or prognosis.",

  "workbench.cta": "Review ambiguous patches first",
  "workbench.sort": "Sort",
  "workbench.sort.priority": "Review priority",
  "workbench.sort.predicted_class": "Predicted class",
  "workbench.sort.image_id": "Image ID",
  "workbench.filter": "Filter",
  "workbench.filter.all": "All",
  "workbench.filter.unreviewed": "Unreviewed",
  "workbench.filter.reviewed": "Reviewed",
  "workbench.filter.deferred": "Deferred",
  "workbench.filter.pred_NON_TUMOR": "Predicted NON_TUMOR",
  "workbench.filter.pred_VIABLE_TUMOR": "Predicted VIABLE_TUMOR",
  "workbench.filter.pred_NECROSIS": "Predicted NECROSIS",
  "workbench.search": "Search image ID",
  "workbench.rank": "Priority rank",
  "workbench.empty": "No patches match these filters.",
  "workbench.pageOf": "Page {page} · {total} patches",

  "patch.suggested": "Suggested class",
  "patch.scores": "Model scores",
  "patch.uncalibrated": "uncalibrated",
  "patch.scoreLabel": "Model score — uncalibrated",
  "patch.margin": "Top-two score margin",
  "patch.entropy": "Score entropy (normalized)",
  "patch.priorityNote":
    "Review priority is a deterministic ranking of raw score margin and entropy — not a probability of error or calibrated uncertainty.",
  "patch.metadata": "Source / QC metadata",
  "patch.group": "Group",
  "patch.qcStatus": "QC status",
  "patch.trainingEligible": "Training eligible",
  "patch.qcReview": "QC REVIEW (data quality)",
  "patch.originalLabel": "Dataset label",

  "review.title": "Human review",
  "review.accept": "Accept",
  "review.correct": "Correct",
  "review.defer": "Defer",
  "review.pickClass": "Correct to class",
  "review.deferReason": "Defer reason",
  "review.note": "Note (optional)",
  "review.save": "Save review",
  "review.saved": "Saved",
  "review.history": "Review history",
  "review.noHistory": "No review yet.",
  "review.current": "Current review",
  "review.conflict": "This patch changed since you loaded it. Reloading latest state.",

  "defer.mixed_tissue": "Mixed tissue",
  "defer.poor_image_quality": "Poor image quality",
  "defer.insufficient_context": "Insufficient context",
  "defer.uncertain_morphology": "Uncertain morphology",
  "defer.other": "Other",

  "viewer.zoomIn": "Zoom in",
  "viewer.zoomOut": "Zoom out",
  "viewer.reset": "Reset view",
  "viewer.toggleMeta": "Toggle metadata",

  "nav.prev": "Previous",
  "nav.next": "Next",
  "nav.backToWorkbench": "Back to workbench",

  "export.title": "Export reviews",
  "export.csv": "Export CSV",
  "export.json": "Export JSON",

  "attribution.title": "Model attribution",
  "attribution.navBody":
    "Model attribution is shown per patch, on the review screen. Open a patch and use the Model attribution panel to compare what pushed the model toward one class rather than another.",
  "attribution.heading": "Model attribution",
  "attribution.contrastHint":
    "Highlighted regions influenced the model toward {a} rather than {b}.",
  "attribution.notSegmentation":
    "This is model attribution, not tissue segmentation or diagnostic annotation.",
  "attribution.recoveryDisclosure":
    "Attribution uses a behaviorally reconstructed classifier because the original runtime head weights were not durably preserved. Prediction behavior was verified against the original stored outputs.",
  "attribution.compareLabel": "Compare",
  "attribution.vs": "vs",
  "attribution.showOverlay": "Show attribution overlay",
  "attribution.opacity": "Overlay opacity",
  "attribution.originalView": "Original image",
  "attribution.loading": "Computing attribution…",
  "attribution.error":
    "Attribution could not be computed for this patch. No heatmap is shown.",
  "attribution.defaultNote":
    "Default comparison: suggested class vs the model's runner-up for this patch.",
  "attribution.method": "Contrastive Grad-CAM (logit difference)",

  "class.NON_TUMOR": "NON_TUMOR",
  "class.VIABLE_TUMOR": "VIABLE_TUMOR",
  "class.NECROSIS": "NECROSIS",

  "status.unreviewed": "Unreviewed",
  "status.reviewed": "Reviewed",
  "status.deferred": "Deferred",
} as const;

export type StringKey = keyof typeof en;

const TABLES: Record<Locale, Record<string, string>> = { en };

let current: Locale = "en";

export function setLocale(locale: Locale) {
  current = locale;
}

export function t(key: StringKey, vars?: Record<string, string | number>): string {
  let s = TABLES[current][key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(`{${k}}`, String(v));
    }
  }
  return s;
}
