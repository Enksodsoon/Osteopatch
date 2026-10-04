# 07 — Primary sources and reuse register

**Research date:** 3 October 2026. These links support the planning evidence, not a claim that a dataset, repository or model has been reproduced. Mutable versions, licenses, access paths and prices require rechecking at implementation time.

## User-provided workshop sources

**W1.** `Pasted text(20261003-064603).txt`, supplied in this conversation: CU Hackathon Workshop, Lab 12 Part 2. Relevant supplied line ranges: 90–109 (v1.0.1 versus 2.x), 120–138 (method), 154–173 (installation), 197–222 (trust-all warning), 355–379 (questions/approval), 455–485 (gates and Operations placeholder), 505–516 (persistent evidence).

**W2.** `Pasted markdown (2).md`, supplied in this conversation: Lab 12 introduction. Relevant supplied lines: 25–31 (SDD artifacts), 39–55 (AI-DLC framing/version), 77–90 (learning goals and CLI).

These describe the workshop being followed. They are not evidence of the owner's currently installed software, active AWS permissions, remaining credits or present event expiration.

## External sources

| Key | Source and link | What was used / limit |
|---|---|---|
| S01 | [AWS Open Data — NCI Imaging Data Commons](https://registry.opendata.aws/nci-imaging-data-commons/) | Registry scope and DICOM buckets; exact osteosarcoma patch membership remains unverified |
| S02 | [TCIA Osteosarcoma-Tumor-Assessment](https://www.cancerimagingarchive.net/collection/osteosarcoma-tumor-assessment/) | Official listing: cohort, images, classes, JPG/CSV, license and required DOI. Listing content retrieved through indexed search; repeated direct page fetches failed. Actual archive not downloaded |
| S03 | [NCI osteosarcoma PDQ, professional version](https://www.cancer.gov/types/bone/hp/osteosarcoma-treatment-pdq) | Disease definition and osteoid; not a basis for treatment recommendations in this prototype |
| S04 | [Arunachalam et al., 2017, PubMed PMID 27896975](https://pubmed.ncbi.nlm.nih.gov/27896975/) | Classical image-analysis background; abstract retrieved, performance not reproduced |
| S05 | [Arunachalam et al., 2019, PubMed PMID 30995247](https://pubmed.ncbi.nlm.nih.gov/30995247/) and [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC6469748/) | Machine-learning/CNN methods and evaluation context; substantial methods text retrieved, returned full-text payload truncated near later results |
| S06 | [Chen et al., January 2026 preprint](https://arxiv.org/abs/2601.09416), [RadiomicsOS](https://github.com/YaxiiC/RadiomicsOS), [inspected data.py](https://github.com/YaxiiC/RadiomicsOS/blob/main/data.py) | Patient-level evaluation warning and selected code inspection; preprint, not established clinical validation; code not run |
| S07 | [AWS AI-DLC method article](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/) | Development methodology, human validation, lifecycle framing |
| S08 | [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows) and [v1.0.1 release](https://github.com/awslabs/aidlc-workflows/releases/tag/v1.0.1) | Official workflow source; use a pinned release rather than assuming default branch matches the lab |
| S09 | [torchvision MobileNetV3-Small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html) | Available pretrained model and input conventions; no osteosarcoma validation implied |
| S10 | [Guo et al., 2017 — On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html) | Calibration/temperature-scaling rationale; not a clinical guarantee |
| S11 | [jacobgil/pytorch-grad-cam](https://github.com/jacobgil/pytorch-grad-cam) | Attribution implementation, target/layer choices, MIT license displayed; not a segmentation label source |
| S12 | [AWS Lambda container images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html) | Packaging/runtime constraints; chosen account's deployment rights unverified |
| S13 | [API Gateway HTTP API quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html) | 30-second integration limit motivates short-request/job design |
| S14 | [HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html) and [secure S3/CloudFront example](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/getting-started-secure-static-website-cloudformation-template.html) | Official authentication and private-origin architecture references |
| S15 | [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) | Budget monitoring limitations; no account cost estimate made |
| S16 | [atlan-antillia/EfficientNet-Osteosarcoma](https://github.com/atlan-antillia/EfficientNet-Osteosarcoma) | Experimental train/infer/evaluate example; README targets Python 3.8/TensorFlow 2.8 and displays Apache-2.0; not executed |
| S17 | [IDC index metadata repository](https://github.com/ImagingDataCommons/idc-index-data) | Official route to collection metadata; a complete catalogue/data membership audit was not completed |
| S18 | [ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/) | Optional browser inference fallback only, not the selected default architecture |

## Practical reuse decisions

**Use as core building blocks after version pinning:** the official AI-DLC release, torchvision encoder implementation, and a maintained Grad-CAM implementation. Keep attribution notices and dependency/license records. Check code and model-weight terms separately; a library license does not automatically settle dataset or weight rights.

**Inspect for patterns, not as a turnkey application:** EfficientNet-Osteosarcoma exposes the train/infer/evaluate separation, but its legacy environment, preprocessing and split choices require independent review. Its displayed code license does not validate its model or automatically cover every bundled asset.

**Research reference only until permissions are resolved:** RadiomicsOS illustrates radiomics and hierarchical loss with patient-level evaluation concerns. No reuse license was confirmed during the repository metadata inspection. Its inspected label helper defaults unrecognized values to “Viable”; do not copy that behavior. Its patient-extraction patterns have not been verified against the original archive. Do not adopt its reported metrics as project results.

**Defer:** radiomics fusion, large pathology foundation models, whole-slide segmentation and automatic clinical narratives. They add data/compute/licensing/integration questions without being required for the specified first prototype.

## Required implementation reuse log

For every copied component/dependency record exact repository/package version, commit/hash when applicable, license file, attribution, copied files, local modifications, security review and tests. A public repository without a confirmed license is not treated as permission to copy code. Do not vendor unreviewed model pickle files or execute downloaded scripts just because they are linked by a paper.

## Dataset attribution to preserve if TCIA is approved

Leavey, P., Sengupta, A., Rakheja, D., Daescu, O., Arunachalam, H. B., & Mishra, R. (2019). *Osteosarcoma data from UT Southwestern/UT Dallas for Viable and Necrotic Tumor Assessment (Osteosarcoma-Tumor-Assessment)* [Data set]. The Cancer Imaging Archive. DOI: [10.7937/tcia.2019.bvhjhdas](https://doi.org/10.7937/tcia.2019.bvhjhdas).

Use the official source's current attribution instructions at release. Do not replace a source license with a mirror's different license label.
