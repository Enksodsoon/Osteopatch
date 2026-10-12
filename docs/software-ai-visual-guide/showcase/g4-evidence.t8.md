# Reading the frozen G4 evaluation

This report explains one frozen evaluation record. It separates observed measurements from interpretation and from claims the record cannot support. Entity annotations mark each important value and its provenance. The source of every measurement is the tracked G4 metrics JSON or fold-history JSON. This report uses no raw image rows, patient names, or model weights.

## What the evaluation measures

The metrics file records [1,028 eligible patches](metric_value, origin=1028, unit="patches", assessment="pooled out-of-fold") under a pooled out-of-fold aggregation. Each eligible patch received one prediction from the fold that held out its case or slide group. The held-out units represent [four case or slide groups](group_count, origin=4, assessment="exploratory grouping"). This design asks how the frozen model scored patches from groups it did not use to train that fold.

The repository also documents a local source collection of [1,144 patches](metric_value, origin=1144, unit="patches", assessment="separate source collection") and a historical demo subset of [50 images](metric_value, origin=50, unit="images", assessment="separate demo scope"). These counts refer to different populations. The metrics file's [1,028 scored patches](metric_value, origin=1028, assessment="evaluation denominator") are the correct denominator for the pooled evaluation. Do not add the counts or treat the demo subset as the evaluation set.

The run reports one pooled row per eligible patch. The record identifies the aggregation as pooled out-of-fold. It does not show that each patient contributed only one case or slide. The file therefore supports a case or slide grouped description, but it does not verify patient-level independence.

## Aggregate measures

The frozen [Macro-F1](metric_name, origin="macro_f1") is [0.562311](metric_value, origin=0.562311, assessment="frozen G4"). Macro-F1 calculates an F1 score for each configured class, then takes their unweighted mean. This summary gives each class equal weight even when class supports differ. It can show an imbalance that overall accuracy may hide.

The frozen [balanced accuracy](metric_name, origin="balanced_accuracy") is [0.626460](metric_value, origin=0.626460, assessment="frozen G4"). In this record, it equals the mean recall across the configured classes. It summarizes recall and does not tell us that every class has acceptable recall.

The secondary [overall accuracy](metric_name, origin="accuracy_secondary") is [0.670233](metric_value, origin=0.670233, assessment="secondary summary"). Accuracy counts the fraction of all scored patches assigned the correct class. The class supports are uneven, so this value should remain secondary to class-level measures.

The metrics record also contains [log loss](metric_name, origin="log_loss") of [1.194723](metric_value, origin=1.194723, assessment="frozen record") and [Brier score](metric_name, origin="brier") of [0.496084](metric_value, origin=0.496084, assessment="frozen record"). These scores describe the stored class scores under their stated formulas. They do not prove that the scores represent calibrated probabilities. The model card and evaluation notes describe the scores as uncalibrated class scores, not disease probabilities.

## Class-level findings

The output order is [NON_TUMOR](class_name, origin="class_order[0]"), [VIABLE_TUMOR](class_name, origin="class_order[1]"), and [NECROSIS](class_name, origin="class_order[2]"). These are the model's configured output classes. Review states such as uncertain, deferred, mixed, or poor quality do not add learned output classes.

For NON_TUMOR, the record gives [precision 0.788809](metric_value, origin=0.788809, support=484, assessment="frozen G4"), [recall 0.902893](metric_value, origin=0.902893, support=484, assessment="frozen G4"), and [F1 0.842004](metric_value, origin=0.842004, support=484, assessment="frozen G4"). The support is [484 examples](class_support, origin=484, class="NON_TUMOR"). Recall measures the share of true NON_TUMOR examples that the model found in this evaluation.

For VIABLE_TUMOR, the record gives [precision 0.477612](metric_value, origin=0.477612, support=290, assessment="frozen G4"), [recall 0.110345](metric_value, origin=0.110345, support=290, assessment="frozen G4; low recall"), and [F1 0.179272](metric_value, origin=0.179272, support=290, assessment="frozen G4"). The support is [290 examples](class_support, origin=290, class="VIABLE_TUMOR"). The low recall means the model missed most eligible VIABLE_TUMOR patches in this frozen evaluation. It is a key limitation, not evidence of clinical benefit or harm.

For NECROSIS, the record gives [precision 0.540541](metric_value, origin=0.540541, support=254, assessment="frozen G4"), [recall 0.866142](metric_value, origin=0.866142, support=254, assessment="frozen G4"), and [F1 0.665658](metric_value, origin=0.665658, support=254, assessment="frozen G4"). The support is [254 examples](class_support, origin=254, class="NECROSIS"). These measures apply only to the recorded grouped evaluation.

## Counts behind the predictions

The confusion matrix stores true classes by row and predicted classes by column. For the true NON_TUMOR row, the model assigned [437 examples](confusion_count, origin=437, true_class="NON_TUMOR", predicted_class="NON_TUMOR"), [13 examples](confusion_count, origin=13, true_class="NON_TUMOR", predicted_class="VIABLE_TUMOR"), and [34 examples](confusion_count, origin=34, true_class="NON_TUMOR", predicted_class="NECROSIS"). These counts sum to the NON_TUMOR support of [484](class_support, origin=484, class="NON_TUMOR").

For the true VIABLE_TUMOR row, the model assigned [105 examples](confusion_count, origin=105, true_class="VIABLE_TUMOR", predicted_class="NON_TUMOR"), [32 examples](confusion_count, origin=32, true_class="VIABLE_TUMOR", predicted_class="VIABLE_TUMOR"), and [153 examples](confusion_count, origin=153, true_class="VIABLE_TUMOR", predicted_class="NECROSIS"). These counts sum to the VIABLE_TUMOR support of [290](class_support, origin=290, class="VIABLE_TUMOR"). The [32 correct VIABLE_TUMOR assignments](confusion_count, origin=32, assessment="true positives in pooled record") divided by [290 true examples](class_support, origin=290, class="VIABLE_TUMOR") yield the recorded recall of [0.110345](metric_value, origin=0.110345, assessment="frozen G4").

For the true NECROSIS row, the model assigned [12 examples](confusion_count, origin=12, true_class="NECROSIS", predicted_class="NON_TUMOR"), [22 examples](confusion_count, origin=22, true_class="NECROSIS", predicted_class="VIABLE_TUMOR"), and [220 examples](confusion_count, origin=220, true_class="NECROSIS", predicted_class="NECROSIS"). These counts sum to the NECROSIS support of [254](class_support, origin=254, class="NECROSIS"). The matrix helps readers see where errors occur. It does not describe the likely behavior on new sites or patients.

## Fold and training-history limits

The recorded histories contain [four group-specific folds](fold_count, origin=4, assessment="historical G4") and [ten training epochs per history](epoch_count, origin=10, assessment="recorded training history"). Each curve shows training loss. Training loss measures how the optimizer fits its training examples over time. It does not measure held-out performance. A smooth or declining curve does not establish that a model will generalize.

One fold contains [one class only](fold_limitation, assessment="single-class held-out fold"). Recall for a class absent from that fold cannot be estimated within that fold. The evidence notes also describe two held-out class supports of [3 examples](small_support, origin=3, assessment="indicative only") and [2 examples](small_support, origin=2, assessment="indicative only"). Such small supports make class-level estimates unstable. The project does not have an independent patient-level bootstrap. Patches from one biological sample may be related, so counting them as independent patients would overstate the evidence.

A better visualization can help reviewers find weak classes and understand split design. It cannot correct the split design or increase the sample count. A future evaluation would need an independently reviewed protocol, a verified group key, sufficient held-out support, and a frozen artifact identity before anyone interprets an updated chart as stronger evidence.

## Artifact identity and application behavior

The original [baseline-frozen-g4 binary](artifact_status, assessment="absent") is missing from the repository. The recovered attribution head has a separate identity. It cannot inherit this evaluation without a direct, verified artifact match. Netron can inspect a supported model graph and tensor shapes when a matching weight file exists. The guide does not claim that Netron inspected this missing binary.

The application consumes precomputed predictions. A reviewer correction becomes an append-only event. It does not rewrite an immutable prediction or launch a training run. TensorBoard can show logged loss and metrics when event files exist. The repository has no event log for this run, so the plotted history comes from tracked fold-history JSON. Do not describe a TensorBoard screen as evidence from this experiment.

## Claim boundary and useful communication

This project is for [education and research](intended_use, origin="PROJECT_BRIEF.md", assessment="research-only"). The available G4 record does not establish diagnosis, treatment benefit, patient-level independence, prospective performance, external-site performance, or clinical qualification. A user interface label, diagram, dashboard, or model visualization cannot change that boundary.

For engineering review, use the architecture diagram to discuss which component owns a request, the sequence diagram to review API and event flow, and the training lifecycle to explain general machine-learning stages. Use the class recall chart to show the observed class imbalance. Keep the source JSON, aggregation method, class supports, and limitations beside any exported chart.

Before presenting these values, verify that the current record still matches the chart, state that the metrics are exploratory, and retain the low VIABLE_TUMOR recall in the summary. Do not select only high values or replace missing artifacts with assumptions. A professional figure should make the evidence easier to audit, not make it appear more conclusive.

Sources: `../../aidlc-docs/inception/model/g4/overall-oof-metrics.json`, `../../aidlc-docs/inception/model/g4/fold-histories.json`, `../../docs/model-evidence.md`, and `../../PROJECT_BRIEF.md`.
