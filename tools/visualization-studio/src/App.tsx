import { useEffect, useRef, useState } from 'react';
import { ReactFlow, Background, Controls, Position, type Edge, type Node } from '@xyflow/react';
import * as d3 from 'd3';
import * as echarts from 'echarts';
import { Download, Moon, Sun, ZoomIn } from 'lucide-react';
import evidence from './data/model-evidence.json';
import '@xyflow/react/dist/style.css';

const displayClassOrder = ['Non-tumor tissue', 'Viable tumor', 'Necrotic tissue'];

const nodes: Node[] = [
  { id: 'web', position: { x: 0, y: 48 }, data: { label: 'Browser review app\nimages + reviewer decisions' }, className: 'node-ui', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'api', position: { x: 230, y: 48 }, data: { label: 'Review service (API)\nsign-in + access checks' }, className: 'node-api', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'proxy', position: { x: 460, y: 48 }, data: { label: 'Project access check\nconfirms image belongs here' }, className: 'node-api', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'review-service', position: { x: 690, y: 48 }, data: { label: 'Image review backend\nsame running program' }, className: 'node-api', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'db', position: { x: 920, y: 48 }, data: { label: 'Image review database\nsaved results + decisions' }, className: 'node-store', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'files', position: { x: 230, y: 220 }, data: { label: 'Local image files\npatches / slides' }, className: 'node-store', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'live', position: { x: 460, y: 220 }, data: { label: 'Optional imported-image scoring\nseparate recovered model' }, className: 'node-warning', sourcePosition: Position.Right, targetPosition: Position.Left },
  { id: 'live-store', position: { x: 690, y: 220 }, data: { label: 'Separate imported-image\nresults' }, className: 'node-store', sourcePosition: Position.Right, targetPosition: Position.Left },
];
const edges: Edge[] = [
  { id: 'e1', source: 'web', target: 'api', animated: false },
  { id: 'e2', source: 'api', target: 'proxy', animated: false },
  { id: 'e3', source: 'proxy', target: 'review-service', animated: false },
  { id: 'e4', source: 'review-service', target: 'db', animated: false },
  { id: 'e5', source: 'api', target: 'live', animated: false },
  { id: 'e6', source: 'files', target: 'live', animated: false },
  { id: 'e7', source: 'live', target: 'live-store', animated: false },
];

function Architecture() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 680px)').matches);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 680px)');
    const update = () => setNarrow(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return <div className="flow-wrap" aria-label="Review app and image review backend architecture">
    <div className="desktop-flow" aria-label="Interactive architecture graph">
      {!narrow && <ReactFlow defaultNodes={nodes} defaultEdges={edges} fitView fitViewOptions={{ padding: 0.16 }} minZoom={0.2} maxZoom={1.8}>
        <Background color="#d9d4ca" gap={22} />
        <Controls showInteractive={false} />
      </ReactFlow>}
    </div>
    <div className="mobile-architecture" aria-label="Architecture flow for narrow screens">
      <div className="mobile-flow-step"><b>Browser review app</b><span>Interface for viewing images and saved decisions</span></div>
      <div className="mobile-flow-link">Signed sign-in proof + selected project ↓</div>
      <div className="mobile-flow-step"><b>Review API</b><span>Checks sign-in and current project access</span></div>
      <div className="mobile-flow-link">Sign-in and project checks pass · local call ↓</div>
      <div className="mobile-flow-step"><b>Image review backend</b><span>Runs within the same program as the project access check</span></div>
      <div className="mobile-flow-link">Reads saved image results · adds reviewer decisions ↓</div>
      <div className="mobile-flow-step"><b>Image review database</b><span>Preserved predictions · separately recorded reviewer decisions</span></div>
      <div className="mobile-flow-optional"><b>Optional scoring for an imported image</b><span>Local image → separate recovered model → separate results</span></div>
    </div>
  </div>;
}

function LayerExplorer() {
  const ref = useRef<SVGSVGElement>(null);
  const [selectedStage, setSelectedStage] = useState('baseline-encoder');
  useEffect(() => {
    if (!ref.current) return;
    const svg = d3.select(ref.current);
    svg.selectAll('*').remove();
    const lanes = [
      [
        { id: 'baseline-encoder', title: 'Reference design · image encoder', detail: ['MobileNetV3-Small · image-processing blocks fixed', 'Color adjustment matches prediction use'], kind: 'frozen' },
        { id: 'baseline-head', title: 'Reference design · class scorer', detail: ['Maps 1,024 image features to 3 class scores'], kind: 'head' },
        { id: 'baseline-output', title: 'Reference design · output classes', detail: ['Non-tumor tissue · viable tumor', 'Necrotic tissue'], kind: 'output' },
      ],
      [
        { id: 'candidate-encoder', title: 'Tuning candidate · image encoder', detail: ['MobileNetV3-Small · earlier blocks fixed', 'Final image-processing block can adjust'], kind: 'warning' },
        { id: 'candidate-head', title: 'Tuning candidate · class scorer', detail: ['576 → 1,024 features · smooth activation', 'Drops 20% of connections during tuning · 3 scores'], kind: 'head' },
        { id: 'candidate-output', title: 'Tuning candidate · output classes', detail: ['Non-tumor tissue · viable tumor', 'Necrotic tissue'], kind: 'output' },
      ],
    ];
    const width = 900, height = 390, boxW = 248, boxH = 82, gapX = 43;
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('role', 'img')
      .attr('aria-label', 'Documented reference design and tuning candidate structure; no model files are loaded');
    svg.append('text').attr('x', 32).attr('y', 24).attr('class', 'd3-note')
      .text('Documented design only · original reference-model file unavailable · images resized to 384 × 384 and color-scaled to match model training.');
    lanes.forEach((lane, row) => lane.forEach((d, col) => {
      const x = 32 + col * (boxW + gapX), y = 62 + row * 156;
      const group = svg.append('g').attr('transform', `translate(${x},${y})`).attr('tabindex', 0)
        .attr('role', 'button').attr('aria-label', `${d.title}: ${d.detail.join('; ')}`)
        .attr('aria-pressed', d.id === selectedStage).style('cursor', 'pointer')
        .on('click', () => setSelectedStage(d.id))
        .on('keydown', (event: KeyboardEvent) => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedStage(d.id); }
        });
      group.append('rect').attr('width', boxW).attr('height', boxH).attr('rx', 8)
        .attr('class', `stage stage-${d.kind}${d.id === selectedStage ? ' stage-selected' : ''}`);
      group.append('text').attr('x', 13).attr('y', 28).attr('class', 'stage-title').text(d.title);
      d.detail.forEach((line, i) => group.append('text').attr('x', 13).attr('y', 51 + i * 15).attr('class', 'stage-detail').text(line));
      if (col < lane.length - 1) svg.append('path').attr('d', `M${x + boxW},${y + boxH / 2} H${x + boxW + gapX - 8}`)
        .attr('class', 'stage-link').attr('marker-end', 'url(#arrow)');
    }));
    svg.append('defs').append('marker').attr('id', 'arrow').attr('viewBox', '0 0 10 10')
      .attr('refX', 8).attr('refY', 5).attr('markerWidth', 5).attr('markerHeight', 5).attr('orient', 'auto-start-reverse')
      .append('path').attr('d', 'M 0 0 L 10 5 L 0 10 z').attr('fill', '#8e8b80');
  }, [selectedStage]);
  const selected = [
    { id: 'baseline-encoder', title: 'Reference design · image encoder', detail: 'MobileNetV3-Small image-processing blocks stay fixed; image colors are adjusted the same way for evaluation and use.' },
    { id: 'baseline-head', title: 'Reference design · class scorer', detail: 'Maps 1,024 image features to three class scores.' },
    { id: 'baseline-output', title: 'Reference design · output classes', detail: 'Non-tumor tissue, viable tumor, and necrotic tissue.' },
    { id: 'candidate-encoder', title: 'Tuning candidate · image encoder', detail: 'Earlier blocks stay fixed; the final image-processing block can adjust.' },
    { id: 'candidate-head', title: 'Tuning candidate · class scorer', detail: 'Uses 576 to 1,024 features, a smooth activation, drops 20% of connections during tuning, then produces three scores.' },
    { id: 'candidate-output', title: 'Tuning candidate · output classes', detail: 'Non-tumor tissue, viable tumor, and necrotic tissue.' },
  ].find((item) => item.id === selectedStage)!;
  return <>
    <div className="layer-wrap"><svg ref={ref} /></div>
    <p className="selected-stage" aria-live="polite"><b>{selected.title}</b><span>{selected.detail}</span></p>
    <div className="model-mobile">
      <article className="model-lane"><span className="eyebrow">REFERENCE MODEL</span><h3>Image encoder · MobileNetV3-Small</h3><p>Image-processing blocks stay fixed; image colors are adjusted the same way during evaluation and use.</p><div className="mobile-flow-link">384 × 384 image · resize and color scale to match training ↓</div><h3>Class scorer</h3><p>Maps 1,024 image features to three class scores: non-tumor tissue, viable tumor, necrotic tissue.</p></article>
      <article className="model-lane model-lane-warning"><span className="eyebrow">TUNING CANDIDATE · NO BENEFIT</span><h3>Image encoder · MobileNetV3-Small</h3><p>Blocks 0–11 stay fixed; the final image-feature block and class scorer can adjust.</p><div className="mobile-flow-link">Same image size and color scaling ↓</div><h3>Class scorer</h3><p>Uses 576 to 1,024 features, a smooth activation, drops 20% of connections during tuning, then produces three scores.</p><p>No final model file was created.</p></article>
      <p className="source">Scores are not calibrated probabilities: a score of 0.8 does not mean an 80% chance of disease. This shows the documented design only; the original reference-model file is unavailable.</p>
    </div>
  </>;
}

function RecallChart({ dark }: { dark: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const narrow = window.innerWidth <= 600;
    chart.current?.dispose();
    chart.current = echarts.init(ref.current, undefined, { renderer: 'svg' });
    chart.current.setOption({
      animation: false,
      aria: { enabled: true, description: 'Reference model versus tuning candidate recall by class. Recall is the share of examples from a class correctly recognized. Each of four groups was excluded from training in turn; results are combined on a zero to one scale.' },
      color: ['#40796f', '#c87843'],
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${(v * 100).toFixed(1)}% recall` },
      legend: { bottom: 0, textStyle: { color: dark ? '#ece8dc' : '#383831' } },
      grid: { left: 70, right: 26, top: 24, bottom: narrow ? 96 : 74 },
      xAxis: { type: 'category', data: displayClassOrder, axisLabel: { interval: 0, rotate: 0, formatter: (value: string) => narrow ? value.replace(' ', '\n') : value, color: dark ? '#ece8dc' : '#383831' } },
      yAxis: { type: 'value', min: 0, max: 1, name: 'Recall', axisLabel: { formatter: '{value}', color: dark ? '#ece8dc' : '#383831' }, splitLine: { lineStyle: { color: dark ? '#47443e' : '#e3dfd5' } } },
      dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, height: 18, bottom: 34 }],
      toolbox: { right: 8, feature: { saveAsImage: { name: 'osteopatch-reference-candidate-recall', title: 'Export image' }, restore: { title: 'Reset' } } },
      series: [
        { name: 'Reference model', type: 'bar', barMaxWidth: 48, data: evidence.models.baseline.recall, emphasis: { focus: 'series' } },
        { name: 'Tuning candidate · NO BENEFIT', type: 'bar', barMaxWidth: 48, data: evidence.models.candidate.recall, emphasis: { focus: 'series' } },
      ],
    });
    const resize = () => {
      const compact = window.innerWidth <= 600;
      chart.current?.resize();
      chart.current?.setOption({
        grid: { bottom: compact ? 96 : 74 },
        xAxis: { axisLabel: { interval: 0, rotate: 0, formatter: (value: string) => compact ? value.replace(' ', '\n') : value } },
      });
    };
    window.addEventListener('resize', resize);
    return () => { window.removeEventListener('resize', resize); chart.current?.dispose(); chart.current = null; };
  }, [dark]);
  const exportPng = () => {
    if (!chart.current) return;
    const a = document.createElement('a'); a.href = chart.current.getDataURL({ type: 'png', pixelRatio: 3, backgroundColor: dark ? '#252621' : '#f7f5ef' });
    a.download = 'osteopatch-reference-candidate-recall.png'; a.click();
  };
  const resetZoom = () => chart.current?.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
  return <>
    <div ref={ref} className="chart" role="img" aria-label="Reference model and tuning candidate recall chart, with interactive legend and zoom controls" />
    <div className="chart-actions"><button onClick={exportPng}><Download size={16} /> Export PNG</button><button onClick={resetZoom}><ZoomIn size={16} /> Reset zoom</button></div>
  </>;
}

export default function App() {
  const [dark, setDark] = useState(false);
  return <main className={dark ? 'app dark' : 'app'}>
    <header className="masthead"><div><span className="eyebrow">OSTEOPATCH · RESEARCH TOOLING</span><h1>Visualization studio</h1><p>Source-linked model evidence and software architecture.</p></div>
      <button className="theme-button" onClick={() => setDark((value) => !value)} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}>{dark ? <Sun size={17} /> : <Moon size={17} />}{dark ? 'Light' : 'Dark'} theme</button></header>
    <section className="card"><div className="section-head"><div><span className="eyebrow">01 · SYSTEM MAP</span><h2>Local review architecture</h2></div><span className="tag">Implemented paths · interactive</span></div>
      <p className="lede">The review API is a local service that receives browser requests. It checks sign-in and project access, then calls the image review backend within the same running program. Optional scoring for an imported image uses a recovered part of the model (its class scorer) and keeps results separate.</p><Architecture />
      <p className="source">Sources: sign-in and project access implementation; image review storage implementation.</p></section>
    <section className="card"><div className="section-head"><div><span className="eyebrow">02 · MODEL DESIGN</span><h2>How the model is structured</h2></div><span className="tag warning-tag">Documented design · no model files loaded</span></div>
      <p className="lede">An image encoder converts each image into a set of features; a class scorer maps those features to three tissue categories. The reference design keeps its encoder fixed. The later tuning candidate lets the final image-processing block adjust, but its result record found no demonstrated benefit.</p><LayerExplorer />
      <p className="source">Source: stored model configuration and architecture records. The original reference-model file is unavailable, and the recovered classifier is only one part of a model.</p></section>
    <section className="card"><div className="section-head"><div><span className="eyebrow">03 · STORED MEASUREMENTS</span><h2>Recall by class</h2></div><span className="tag">Each of 4 groups kept out of training in turn · n = 1,028</span></div>
      <p className="lede">Recall is the share of images in a class that were correctly recognized. Each image was scored by a model that did not train on its group, then results were combined. The class counts are 484, 290 and 254. The evaluation record classified the tuning candidate as NO BENEFIT, meaning it did not demonstrate an improvement; no final model file was created.</p>
      <RecallChart dark={dark} />
      <div className="metric-strip"><span title="F1 combines precision and recall; each class gets equal weight">Class-average F1 · reference <b>{evidence.models.baseline.macroF1.toFixed(3)}</b></span><span title="F1 combines precision and recall; each class gets equal weight">Class-average F1 · candidate <b>{evidence.models.candidate.macroF1.toFixed(3)}</b></span><span>Scores <b>not chance estimates</b></span></div>
      <p className="caveat">{evidence.calibration}. {evidence.limitations}</p><p className="source">Class-average F1 balances precision and recall and gives each class equal weight. Chart classes: non-tumor tissue, viable tumor, and necrotic tissue. Sources: stored evaluation metrics, model configuration, and confusion-matrix records.</p></section>
    <footer>Educational and research prototype. Not for diagnosis, treatment decisions, treatment response, or prognosis.</footer>
  </main>;
}
