# 00 — AI-DLC setup and safe activation

**Source basis:** the two uploaded workshop documents [W1, W2], with the official repository/release [S07, S08]. Source keys resolve in [the register](07_sources_and_reuse_register.md).

## Choose one workflow

For a new workshop-compatible workspace, use **AI-DLC v1.0.1**. The supplied lab installs markdown rules, activates them with “Using AI-DLC, …”, and persists artifacts in `aidlc-docs/`. Its three conceptual phases are Inception, Construction and Operations. However, its demonstrated Operations stage is a placeholder: this project must implement deployment, monitoring, restore and cleanup explicitly.

The uploaded materials also describe a newer 2.x packaging/command layout. If Kiro finds that already installed, document the exact installed version, its official instructions and artifact paths, then ask whether to keep it or use the lab version. Do not combine v1 installation steps and v2 slash commands. Do not assume a current repository's default branch matches the lab release.

Use AI-DLC as the lifecycle controller. Numbered requirements, designs and task documents remain useful, but do not start a second built-in Kiro Specs workflow over the same work. AI-DLC here governs development; it is not a machine-learning model or an assurance of model validity.

## Fresh-folder installation recipe

These commands are instructions, **not commands run by this handoff**. Use only a fresh project, inspect the official archive, and do not overwrite existing steering. Record the archive SHA-256 and release URL; a locally computed hash aids reproducibility but is not an independently verified publisher signature.

POSIX shell, matching the workshop's environment:

```bash
curl -fsSL -o ai-dlc-rules-v1.0.1.zip \
  https://github.com/awslabs/aidlc-workflows/releases/download/v1.0.1/ai-dlc-rules-v1.0.1.zip
unzip ai-dlc-rules-v1.0.1.zip
mkdir -p .kiro/steering
cp -R aidlc-rules/aws-aidlc-rules .kiro/steering/
cp -R aidlc-rules/aws-aidlc-rule-details .kiro/
kiro-cli chat
```

Windows PowerShell alternative for a fresh folder:

```powershell
$uri = 'https://github.com/awslabs/aidlc-workflows/releases/download/v1.0.1/ai-dlc-rules-v1.0.1.zip'
Invoke-WebRequest -Uri $uri -OutFile 'ai-dlc-rules-v1.0.1.zip'
Get-FileHash 'ai-dlc-rules-v1.0.1.zip' -Algorithm SHA256
Expand-Archive 'ai-dlc-rules-v1.0.1.zip' -DestinationPath 'aidlc-release-v1.0.1'
New-Item -ItemType Directory -Force '.kiro/steering' | Out-Null
Copy-Item -Recurse 'aidlc-release-v1.0.1/aidlc-rules/aws-aidlc-rules' '.kiro/steering/'
Copy-Item -Recurse 'aidlc-release-v1.0.1/aidlc-rules/aws-aidlc-rule-details' '.kiro/'
kiro-cli chat
```

First inspect the extracted folder layout; stop if it differs from the documented release. Do not force-copy another version into these paths.

Inside Kiro CLI, run `/context show`. Verify that the official `core-workflow.md` and project steering are loaded. Start a new session if necessary. Do **not** copy the workshop's `--trust-all-tools` flag onto a personal machine with sensitive data; ordinary tool approvals and human stage approvals are different safeguards.

## Question and approval mechanism

Kiro creates `aidlc-docs/inception/requirements/requirement-verification-questions.md`, prefills established facts, and asks only unresolved questions. The owner fills `[Answer]:` fields and saves the file. Kiro then writes the proposed requirements and stops at **REVIEW REQUIRED**.

Use explicit approvals, for example: “Approve G1 source selection: TCIA direct, subject to the documented license. This does not approve cloud spending.” Record what was approved, by whom, when, and which document version. Never manufacture approvals from silence or the existence of this package.

For this project enable security requirements, minimal resilience tests, and targeted property tests. Do not adopt a Sudoku exercise's disabled-security defaults.
