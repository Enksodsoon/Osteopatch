import { Graph } from '@antv/x6';

const graph = new Graph({ container: 'container', background: { color: '#f7f4ee' }, grid: true });
const ui = graph.addNode({ shape: 'rect', x: 40, y: 80, width: 180, height: 60, label: 'Reviewer UI' });
const api = graph.addNode({ shape: 'rect', x: 290, y: 80, width: 180, height: 60, label: 'FastAPI /v1' });
const db = graph.addNode({ shape: 'rect', x: 540, y: 20, width: 210, height: 60, label: 'SQLite review event' });
const pred = graph.addNode({ shape: 'rect', x: 540, y: 120, width: 210, height: 60, label: 'Stored prediction' });
graph.addEdge({ source: ui, target: api, labels: ['GET image / POST review'] });
graph.addEdge({ source: api, target: db, labels: ['append review'] });
graph.addEdge({ source: api, target: pred, labels: ['read only'] });
graph.centerContent();
