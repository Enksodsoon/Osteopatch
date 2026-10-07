import { CLASS_LABELS, CLASSES } from "../types";
import { Disclaimer } from "./Shared";

const sources = [
  {
    id: "nci-hcp",
    number: 1,
    title: "Osteosarcoma and UPS of Bone Treatment (PDQ®) — Health Professional Version",
    publisher: "National Cancer Institute",
    href: "https://www.cancer.gov/types/bone/hp/osteosarcoma-treatment-pdq",
    note: "Disease overview, classification, diagnostic evaluation, staging, and treatment overview.",
  },
  {
    id: "nci-patient",
    number: 2,
    title: "Osteosarcoma Treatment (PDQ®) — Patient Version",
    publisher: "National Cancer Institute",
    href: "https://www.cancer.gov/types/bone/patient/osteosarcoma-treatment-pdq",
    note: "Plain-language overview of symptoms, risk factors, diagnosis, spread, and treatment.",
  },
  {
    id: "who",
    number: 3,
    title: "WHO Classification of Tumours Online: Soft Tissue and Bone Tumours",
    publisher: "International Agency for Research on Cancer / World Health Organization",
    href: "https://tumourclassification.iarc.who.int/",
    note: "International tumour classification reference used by specialist pathologists.",
  },
  {
    id: "cap",
    number: 4,
    title: "Cancer Protocol: Bone Resection",
    publisher: "College of American Pathologists",
    href: "https://www.cap.org/wp-content/uploads/protocols/cp-other-bone-resection-20-4010.pdf?download=true",
    note: "Structured resection-report elements, including treatment effect and tumour necrosis.",
  },
  {
    id: "histology-review",
    number: 5,
    title: "What’s new in bone forming tumours of the skeleton?",
    publisher: "Virchows Archiv · peer-reviewed pathology review",
    href: "https://link.springer.com/article/10.1007/s00428-019-02683-w",
    note: "Bone-tumour pathology review describing osteoid on H&E and the range of bone-forming tumours.",
  },
] as const;

type SourceId = (typeof sources)[number]["id"];

function Cite({ ids }: { ids: SourceId[] }) {
  return (
    <span className="guide-cites" aria-label="Sources">
      {ids.map((id) => {
        const source = sources.find((item) => item.id === id)!;
        return <a key={id} href={`#reference-${id}`} aria-label={`Reference ${source.number}`}>[{source.number}]</a>;
      })}
    </span>
  );
}

function BoneSiteDiagram() {
  return (
    <figure className="guide-figure guide-bone-figure">
      <svg viewBox="0 0 420 270" role="img" aria-labelledby="bone-title bone-description">
        <title id="bone-title">Common long-bone sites shown around the knee</title>
        <desc id="bone-description">A simplified femur and tibia. Highlighted regions near the ends of the bones mark common osteosarcoma sites; this is a teaching schematic, not an imaging finding.</desc>
        <path className="guide-bone" d="M171 18c-16 0-28 10-27 25 1 11 9 19 19 24l8 62c-12 6-21 16-20 29 1 13 11 21 24 20 10-1 16-6 22-13 6 8 14 13 25 13 13 0 23-9 23-21 0-12-8-22-20-28l10-62c10-6 18-14 18-25 0-14-12-24-27-23-13 1-21 7-29 17-7-11-14-18-26-18Z" />
        <path className="guide-bone" d="M164 182c18 7 49 8 74 0l13 10-9 13 8 11-9 11 7 10-13 10-12-5-8 10h-35l-8-10-12 5-13-10 7-10-9-11 8-11-9-13Z" />
        <path className="guide-bone-line" d="M174 38c10 4 17 10 21 18m29-18c-9 3-16 9-21 17m-34 151c13 5 27 7 41 6m14 0c9 0 18-2 27-6" />
        <path className="guide-growth-line" d="M161 130c19 8 39 9 62 5m-59 57c18 6 43 7 67 2" />
        <path className="guide-joint-line" d="M162 174q40 10 78 0" />
        <ellipse className="guide-tumour-site" cx="202" cy="145" rx="47" ry="16" />
        <ellipse className="guide-tumour-site" cx="202" cy="193" rx="43" ry="14" />
        <path className="guide-leader" d="M249 145h66m-70 48h70" />
        <text x="321" y="140">Distal femur</text>
        <text x="321" y="157">near the knee</text>
        <text x="321" y="188">Proximal tibia</text>
        <text x="321" y="205">near the knee</text>
      </svg>
      <figcaption>Osteosarcoma often arises in the long bones around the knee, especially near the ends of the femur and tibia. Other sites occur too. Schematic, not to scale.<Cite ids={["nci-hcp", "nci-patient"]} /></figcaption>
    </figure>
  );
}

function ClassAtlas() {
  const imageDescriptions = [
    "Synthetic H&E-style illustration for the non-tumor patch class",
    "Synthetic H&E-style illustration for the viable-tumor patch class",
    "Synthetic H&E-style illustration for the necrosis patch class",
  ];

  return (
    <figure className="guide-figure guide-atlas">
      <div className="guide-atlas-grid">
        {CLASSES.map((label, index) => (
          <div className="guide-atlas-card" key={label}>
            <div
              className={`class-atlas-image guide-atlas-${index}`}
              role="img"
              aria-label={imageDescriptions[index]}
            />
            <strong>{label.replace("_", " ")}</strong>
            <p>{CLASS_LABELS[label]}</p>
          </div>
        ))}
      </div>
      <figcaption>Three broad labels used by this demo. These synthetic teaching illustrations are not patient slides, diagnostic criteria, or the full classification of bone tumours.</figcaption>
    </figure>
  );
}

function LearningGuide({ onOpenModel }: { onOpenModel: () => void }) {
  return (
    <article className="learning-guide" data-testid="learning-guide">
      <header className="guide-hero" id="guide-overview">
        <div className="guide-hero-copy">
          <span className="eyebrow">Student study guide · Bone pathology</span>
          <h1>Osteosarcoma</h1>
          <p className="guide-deck">A visual introduction to the disease, its defining pathology, how diagnosis is assembled, and what the OsteoPatch demo can—and cannot—show.</p>
          <Disclaimer />
          <nav className="guide-toc" aria-label="Study guide sections">
            <a href="#guide-pathology">Pathology</a>
            <a href="#guide-diagnosis">Diagnosis</a>
            <a href="#guide-treatment">Treatment context</a>
            <a href="#guide-demo">Using the demo</a>
            <a href="#guide-glossary">Glossary</a>
          </nav>
        </div>
        <BoneSiteDiagram />
      </header>

      <section className="guide-section" aria-labelledby="guide-at-a-glance">
        <div className="guide-section-heading">
          <span className="eyebrow">01 · Start here</span>
          <h2 id="guide-at-a-glance">The essential idea</h2>
        </div>
        <div className="guide-overview-grid">
          <div className="guide-keyline">
            <span className="guide-number">A</span>
            <h3>A primary bone sarcoma</h3>
            <p>Osteosarcoma is a malignant tumour in which tumour cells directly produce osteoid—the early, unmineralized matrix of bone.<Cite ids={["nci-hcp", "nci-patient"]} /></p>
          </div>
          <div className="guide-keyline">
            <span className="guide-number">B</span>
            <h3>A pattern, not one appearance</h3>
            <p>It can contain different cell shapes and matrix patterns. A small image field may not show the defining features or the full tumour.<Cite ids={["nci-hcp", "who"]} /></p>
          </div>
          <div className="guide-keyline">
            <span className="guide-number">C</span>
            <h3>Context completes interpretation</h3>
            <p>Diagnosis combines clinical history, imaging, biopsy and specialist pathology review; no single patch or model score establishes a diagnosis.<Cite ids={["nci-hcp", "nci-patient"]} /></p>
          </div>
        </div>
        <div className="guide-note"><strong>Keep these terms separate:</strong> osteosarcoma is a disease diagnosis; osteoblastic, chondroblastic and fibroblastic describe histologic patterns; NON_TUMOR, VIABLE_TUMOR and NECROSIS are this demo’s patch labels.</div>
        <div className="guide-risk-grid">
          <article><span className="eyebrow">Typical age pattern</span><h3>Often seen in adolescents and young adults</h3><p>Osteosarcoma may occur at other ages too. Age alone cannot establish or rule out the diagnosis.<Cite ids={["nci-hcp", "nci-patient"]} /></p></article>
          <article><span className="eyebrow">Risk context</span><h3>Risk factors are not a diagnosis</h3><p>Prior radiation or chemotherapy and some inherited conditions are associated with increased risk. Many people with risk factors do not develop osteosarcoma, and it can occur without a known risk factor.<Cite ids={["nci-patient"]} /></p></article>
        </div>
      </section>

      <section className="guide-section" id="guide-pathology" aria-labelledby="guide-pathology-title">
        <div className="guide-section-heading">
          <span className="eyebrow">02 · Under the microscope</span>
          <h2 id="guide-pathology-title">The defining feature is malignant osteoid</h2>
          <p>On H&amp;E, osteoid often appears as pink extracellular material. The key question is whether malignant tumour cells are making it—not simply whether pink bone-like material is present.<Cite ids={["nci-hcp", "who", "histology-review"]} /></p>
        </div>
        <div className="guide-pathology-grid">
          <div className="guide-panel guide-hallmark">
            <div className="guide-hallmark-mark" aria-hidden="true"><span>Cells</span><b>→</b><span>Osteoid</span></div>
            <h3>What a pathologist looks for</h3>
            <ul>
              <li>Malignant mesenchymal cells, often with nuclear atypia and variable cell shapes.</li>
              <li>Osteoid or immature bone produced directly by those malignant cells.</li>
              <li>How the cells, matrix, bone, and surrounding tissue relate across a representative specimen.</li>
            </ul>
            <p className="guide-small-note">This is a study summary, not a stand-alone diagnostic checklist. Interpretation belongs to a qualified pathology team with the full case context.</p>
          </div>
          <div className="guide-panel guide-matrix-panel">
            <h3>Three demo patch labels</h3>
            <ClassAtlas />
            <p className="guide-small-note">A “necrosis” patch does not by itself show why tissue died or measure a patient’s response to treatment.</p>
          </div>
        </div>
        <div className="guide-subtype-row">
          <article><span className="guide-subtype-tag">CENTRAL / MEDULLARY</span><h3>Conventional osteosarcoma</h3><p>The common high-grade central form. Osteoblastic, chondroblastic, and fibroblastic patterns describe the predominant matrix; these are not the app’s three classes.<Cite ids={["nci-hcp", "who"]} /></p></article>
          <article><span className="guide-subtype-tag">SURFACE / PERIPHERAL</span><h3>Surface osteosarcomas</h3><p>Parosteal, periosteal, and high-grade surface tumours arise at the bone surface. Grade and subtype matter, so “osteosarcoma” is not one uniform microscopic pattern.<Cite ids={["nci-hcp", "who"]} /></p></article>
          <article><span className="guide-subtype-tag">IMPORTANT LOOKALIKE</span><h3>UPS of bone</h3><p>Undifferentiated pleomorphic sarcoma of bone may resemble osteosarcoma, but it does not produce osteoid. This distinction illustrates why morphology and full context matter.<Cite ids={["nci-hcp", "nci-patient"]} /></p></article>
        </div>
      </section>

      <section className="guide-section" id="guide-diagnosis" aria-labelledby="guide-diagnosis-title">
        <div className="guide-section-heading">
          <span className="eyebrow">03 · From finding to diagnosis</span>
          <h2 id="guide-diagnosis-title">A coordinated diagnostic pathway</h2>
          <p>Imaging and biopsy planning are coordinated by a specialist bone-tumour team. Biopsy route matters because it can affect later surgery.<Cite ids={["nci-hcp", "nci-patient"]} /></p>
        </div>
        <ol className="guide-pathway">
          <li><span className="guide-step-icon">01</span><div><h3>Clinical picture</h3><p>Symptoms can include persistent bone pain, swelling, stiffness, or difficulty moving a nearby joint. These symptoms have many possible causes.<Cite ids={["nci-patient"]} /></p></div></li>
          <li><span className="guide-step-icon">02</span><div><h3>Imaging</h3><p>Radiographs assess the bone lesion; MRI helps define local extent. Staging studies assess whether disease is present elsewhere, especially in the lungs.<Cite ids={["nci-hcp", "nci-patient"]} /></p></div></li>
          <li><span className="guide-step-icon">03</span><div><h3>Planned biopsy</h3><p>A core needle or surgical biopsy is planned with the specialist team after imaging, so tissue sampling supports accurate diagnosis and future treatment planning.<Cite ids={["nci-hcp"]} /></p></div></li>
          <li><span className="guide-step-icon">04</span><div><h3>Integrated pathology and staging</h3><p>Pathology is interpreted with the imaging and clinical findings. The team determines tumour type, grade, and whether it is localized or metastatic.<Cite ids={["nci-hcp", "who"]} /></p></div></li>
        </ol>
        <div className="guide-spread-card">
          <div><span className="eyebrow">Spread to distant sites</span><h3>The lungs are the most common metastatic site</h3><p>Osteosarcoma can also spread to other bones. Staging is a whole-patient task; a digitized slide cannot show whether disease has spread.<Cite ids={["nci-hcp", "nci-patient"]} /></p></div>
          <svg viewBox="0 0 350 130" role="img" aria-labelledby="spread-title spread-desc">
            <title id="spread-title">Illustration of common osteosarcoma spread sites</title>
            <desc id="spread-desc">A primary bone tumour connects by arrows to the lungs and another bone, illustrating sites considered during staging.</desc>
            <rect className="guide-spread-node" x="4" y="38" width="92" height="54" rx="12" />
            <text x="50" y="61" textAnchor="middle">Primary</text><text x="50" y="79" textAnchor="middle">bone site</text>
            <path className="guide-spread-arrow" d="M102 65H158m-10-8 10 8-10 8" />
            <rect className="guide-spread-node guide-spread-secondary" x="166" y="9" width="104" height="46" rx="12" />
            <text x="218" y="38" textAnchor="middle">Lungs</text>
            <rect className="guide-spread-node guide-spread-secondary" x="166" y="75" width="104" height="46" rx="12" />
            <text x="218" y="104" textAnchor="middle">Other bone</text>
            <text className="guide-diagram-note" x="282" y="70">staging</text>
          </svg>
        </div>
      </section>

      <section className="guide-section" id="guide-treatment" aria-labelledby="guide-treatment-title">
        <div className="guide-section-heading">
          <span className="eyebrow">04 · Treatment and tissue response</span>
          <h2 id="guide-treatment-title">Why necrosis has more than one meaning</h2>
          <p>High-grade osteosarcoma care commonly combines systemic chemotherapy and surgery, with decisions made by a specialist team for the individual case.<Cite ids={["nci-hcp", "nci-patient"]} /></p>
        </div>
        <div className="guide-treatment-grid">
          <article className="guide-panel">
            <h3>In a resection report</h3>
            <p>After preoperative treatment, a pathologist can assess treatment effect and estimate the proportion of tumour necrosis in the resection specimen, alongside margins and other report elements.<Cite ids={["nci-hcp", "cap"]} /></p>
            <div className="guide-sequence" aria-label="Treatment context sequence"><span>Preoperative therapy</span><b aria-hidden="true">→</b><span>Resection specimen</span><b aria-hidden="true">→</b><span>Pathology response assessment</span></div>
          </article>
          <article className="guide-contrast">
            <span className="eyebrow">Keep apart</span>
            <h3>Patch label ≠ treatment response</h3>
            <p>The demo’s <strong>NECROSIS</strong> output labels an image patch. It does not establish prior therapy, calculate whole-tumour necrosis, or grade treatment response.</p>
          </article>
        </div>
      </section>

      <section className="guide-section" id="guide-demo" aria-labelledby="guide-demo-title">
        <div className="guide-section-heading">
          <span className="eyebrow">05 · Learn with OsteoPatch</span>
          <h2 id="guide-demo-title">What this demo is designed to teach</h2>
          <p>The app is a research-software demonstration. Its patch classes are narrower than bone-tumour diagnosis and its model scores are not probabilities.</p>
        </div>
        <div className="guide-demo-grid">
          <article><h3>Compare three patch labels</h3><p>Review the teaching-set labels <strong>NON_TUMOR</strong>, <strong>VIABLE_TUMOR</strong>, and <strong>NECROSIS</strong>. They do not represent every tumour subtype or mimic.</p></article>
          <article><h3>Read scores cautiously</h3><p>A score margin compares the model’s leading class scores. Scores are uncalibrated and do not express diagnostic probability, disease extent, or clinical urgency.</p></article>
          <article><h3>Keep evidence in context</h3><p>Source labels, model predictions, reviewer choices, live inference, and recorded runs have different provenance. Human review does not rewrite the original prediction.</p></article>
          <article><h3>Understand overlays</h3><p>A class map marks scored regions. Attribution indicates areas associated with a model comparison; it is not tumour segmentation, proof of causation, or a diagnosis.</p></article>
        </div>
        <button className="btn-link" type="button" onClick={onOpenModel}>Explore model evidence and limitations</button>
      </section>

      <section className="guide-section" id="guide-glossary" aria-labelledby="guide-glossary-title">
        <div className="guide-section-heading">
          <span className="eyebrow">06 · Review</span>
          <h2 id="guide-glossary-title">Glossary and knowledge check</h2>
        </div>
        <dl className="guide-glossary">
          <div><dt>Osteoid</dt><dd>Unmineralized bone matrix. In osteosarcoma, malignant tumour cells produce it directly.</dd></div>
          <div><dt>Metaphysis</dt><dd>The flared region near the end of a long bone, between the shaft and the joint end.</dd></div>
          <div><dt>Medullary / central</dt><dd>Arising within the marrow cavity of bone; contrasted with a surface-origin tumour.</dd></div>
          <div><dt>Metastasis</dt><dd>A tumour deposit that has spread from the primary site to another part of the body.</dd></div>
          <div><dt>Necrosis</dt><dd>Dead tissue. In a treated tumour, response assessment needs representative specimen sampling and clinical context.</dd></div>
          <div><dt>H&amp;E</dt><dd>Hematoxylin and eosin, a routine stain that highlights nuclei and tissue structure in different colors.</dd></div>
        </dl>
        <div className="guide-quiz" aria-label="Knowledge check">
          <details><summary>What microscopic finding defines osteosarcoma?</summary><p>Malignant tumour cells directly producing osteoid or bone matrix. A single small field may not be enough to establish that relationship.</p></details>
          <details><summary>Does a high model score mean a high chance of disease?</summary><p>No. Scores are uncalibrated class scores for this demo’s patch categories, not probabilities or clinical risk.</p></details>
          <details><summary>Can a NECROSIS patch show treatment response?</summary><p>No. Treatment response is evaluated in the right specimen and context; one patch label cannot establish it.</p></details>
        </div>
      </section>

      <section className="guide-section guide-references" aria-labelledby="guide-references-title">
        <div className="guide-section-heading">
          <span className="eyebrow">Further reading</span>
          <h2 id="guide-references-title">Accredited and specialist sources</h2>
          <p>Links checked for this study guide on 7 October 2026. Use the source documents for complete definitions and context.</p>
        </div>
        <ol className="guide-reference-list">
          {sources.map((source) => (
            <li id={`reference-${source.id}`} key={source.id}>
              <span className="guide-reference-number">{source.number}</span>
              <div><a href={source.href} target="_blank" rel="noreferrer">{source.title}</a><strong>{source.publisher}</strong><p>{source.note}</p></div>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}

export { LearningGuide };
