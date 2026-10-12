import { Graph } from '@antv/g6';

const graph = new Graph({
  container: 'container',
  data: {
    nodes: [
      { id: 'source', style: { labelText: '1,144 source patches' } },
      { id: 'eligible', style: { labelText: '1,028 eligible G4 OOF patches' } },
      { id: 'folds', style: { labelText: 'Four case/slide groups' } },
      { id: 'metrics', style: { labelText: 'Frozen pooled metrics' } },
      { id: 'limit', style: { labelText: 'Patient independence unverified' } },
      { id: 'use', style: { labelText: 'Research and education only' } },
    ],
    edges: [
      { source: 'source', target: 'eligible' },
      { source: 'eligible', target: 'folds' },
      { source: 'folds', target: 'metrics' },
      { source: 'metrics', target: 'limit' },
      { source: 'limit', target: 'use' },
    ],
  },
  layout: { type: 'dagre', rankdir: 'LR' },
  behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
});

await graph.render();
