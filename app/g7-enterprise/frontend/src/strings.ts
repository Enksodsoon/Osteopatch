// i18n-ready string table. Components reference t('key'); a Thai table can be
// added later as STRINGS.th without rewriting any component. Pathology terms are
// kept in English per the reviewer-language preference.
//
// Ported from the G6 review frontend so the unified app carries the same
// editorial design language, Thai labels, and honesty wording.

export type Locale = "en";

const en = {
  "app.title": "OsteoPatch Review",
  "app.subtitle": "Educational pathology viewer",
  "app.eyebrow": "OSTEOSARCOMA · EDUCATIONAL AI",
  "app.apiLive": "Ready",
  "app.apiOffline": "Connection lost",
  "app.loadErrorTitle": "Review workspace unavailable",
  "app.loadErrorBody": "The evidence and model-card views remain available. Reconnect the review API before making or exporting review decisions.",
  "theme.toggleAria": "Switch display theme",
  "theme.light": "Light",
  "theme.dark": "Dark",

  "nav.workbench": "Review set",
  "nav.modelCard": "Model card",
  "nav.attribution": "Model attribution",
  "nav.library": "Library",

  "limitations.heading": "Limitations — the full list",
  "limitations.frozenHeading": "Frozen G4 evaluation caveats (verbatim)",
  "limitations.note": "What would retire it",
  "limitations.evidence": "Evidence",
  "limitations.count": "{total} limitations recorded",
  "limitations.blockingCount": "{n} blocking",
  "limitations.weakest": "Weakest class: {cls}",
  "limitations.empty": "No limitations were recorded.",
  "limitations.evidenceUnavailable": "Frozen evaluation evidence not available here",
  "metric.notMeasured": "Not measured in this deployment",
  "metric.notAvailable": "Not available in this deployment",
  "severity.blocking": "blocking",
  "severity.high": "high",
  "severity.medium": "medium",
  "severity.low": "low",
  "category.claim": "What this system may claim",
  "category.data": "Data and cohort",
  "category.model": "Model",
  "category.evaluation": "Evaluation",
  "category.attribution": "Attribution",
  "category.platform": "Platform",
  "category.deployment": "Deployment",
  "category.process": "Process",

  "disclaimer.short":
    "Educational / research prototype — NOT for diagnosis, treatment decisions, treatment-response prediction, or prognosis.",

  "subset.banner": "This demo includes 50 patches from a locally verified set of 1,144.",

  "workbench.eyebrow": "PRIORITY REVIEW QUEUE",
  "workbench.cta": "Start with the closest calls.",
  "workbench.intro": "Browse H&E teaching patches, compare the model’s three class scores, and record a human review.",
  "workbench.calloutTitle": "Human review stays in control",
  "workbench.calloutBody": "Scores can guide attention. Your review records the decision.",
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
  "workbench.searchLabel": "Find patch",
  "workbench.search": "Search image ID",
  "workbench.rank": "Priority rank",
  "workbench.empty": "No patches match these filters.",
  "workbench.emptyHint": "Clear the search or choose a broader review state.",
  "workbench.loadError": "The patch queue could not be loaded.",
  "workbench.pageOf": "Page {page} · {total} patches",
  "common.retry": "Try again",

  "patch.queueEyebrow": "UP NEXT",
  "patch.queueTitle": "Patch list",
  "patch.queueBody": "Move through the teaching set while keeping the selected patch open.",
  "patch.viewerEyebrow": "H&E PATCH",
  "patch.reviewEyebrow": "MODEL + YOUR REVIEW",
  "patch.reviewTitle": "Prediction & review",
  "patch.loadError": "This patch could not be loaded.",
  "patch.noPrediction": "Prediction unavailable",
  "patch.noPredictionBody": "No model output is shown in its place. Review remains blocked until a real prediction is available.",
  "patch.suggested": "Model suggestion",
  "patch.scores": "Model scores",
  "patch.uncalibrated": "uncalibrated",
  "patch.scoreLabel": "Model score — uncalibrated",
  "patch.margin": "Gap between top two scores",
  "patch.entropy": "Spread across scores",
  "patch.priorityNote": "This value helps rank images for review. It is not the probability that a prediction is wrong.",
  "patch.metadata": "Image details",
  "patch.group": "Dataset group",
  "patch.qcStatus": "Image quality",
  "patch.trainingEligible": "Training eligible",
  "patch.qcReview": "QC REVIEW (data quality)",
  "patch.originalLabel": "Dataset label",
  "analysis.title": "Analysis",
  "analysis.suggestedVsRunnerUp": "Suggested vs runner-up",
  "analysis.scoreReadout": "Score readout",
  "analysis.decisionMargin": "Decision margin",
  "analysis.uncertainty": "Uncertainty (normalized entropy)",
  "analysis.topClass": "Top class",
  "analysis.secondClass": "Second class",
  "analysis.topTwoMargin": "Top-two margin",
  "analysis.runnerUp": "Runner-up class",
  "analysis.currentPair": "Current pair",
  "analysis.originalImage": "Source image",
  "analysis.context": "Case context",
  "analysis.qc": "QC status",
  "analysis.sourceGroup": "Source group",
  "analysis.datasetLabel": "Dataset label",
  "analysis.trainingEligible": "Training eligible",
  "analysis.threeClass": "Three-class output: NON_TUMOR, VIABLE_TUMOR, NECROSIS. Scores are uncalibrated class scores.",
  "analysis.threeClassLabel": "Three-class output",
  "analysis.threeClassNote": "Three-class output: NON_TUMOR, VIABLE_TUMOR, NECROSIS.",
  "analysis.disclosure": "Attribution is model explanation, not segmentation or diagnosis.",
  "library.title": "Library",
  "library.empty": "No patches in this view.",
  "editor.placeholder": "Add a reviewer note…",
  "editor.expandHint": "Note editor",

  "review.title": "Human review",
  "review.accept": "Accept",
  "review.correct": "Correct",
  "review.defer": "Defer",
  "review.pickClass": "Correct to class",
  "review.deferReason": "Defer reason",
  "review.note": "Note (optional)",
  "review.save": "Save review",
  "review.saved": "Saved",
  "review.saveError": "Review could not be saved. Nothing was recorded.",
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
  "nav.backToWorkbench": "Back to review set",

  "export.title": "Export reviews",
  "export.csv": "Export CSV",
  "export.json": "Export JSON",

  "attribution.title": "Model attribution",
  "attribution.navBody": "Attribution is shown per patch on the review screen, with a contrastive pair selector and overlay controls.",
  "attribution.heading": "Model attribution",
  "attribution.contrastHint": "Highlighted regions influenced the model toward {a} rather than {b}.",
  "attribution.notSegmentation": "This is model attribution, not tissue segmentation or diagnostic annotation.",
  "attribution.recoveryDisclosure": "Attribution uses a behaviorally reconstructed classifier because the original runtime head weights were not durably preserved. Prediction behavior was verified against the original stored outputs.",
  "attribution.compareLabel": "Compare",
  "attribution.vs": "vs",
  "attribution.showOverlay": "Show attribution overlay",
  "attribution.opacity": "Overlay opacity",
  "attribution.originalView": "Original image",
  "attribution.loading": "Computing attribution…",
  "attribution.error": "Attribution could not be computed for this patch. No heatmap is shown.",
  "attribution.defaultNote": "Default comparison: suggested class vs the model's runner-up for this patch.",
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
