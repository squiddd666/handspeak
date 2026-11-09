// SDK 0.5's worker initializer creates a GL context but omits the handle used
// by its video upload path. This guarded adapter binds that EXISTING context;
// it never creates another graph, rewrites model output, or patches SDK code.
export function legacyCpuInference(delegate, device = {}) {
  return delegate === 'CPU' || /^(iPad|iPhone|iPod)( Simulator)?$/.test(device.platform || '') ||
    (/Mac/.test((device.platform || '') + (device.userAgent || '')) && (device.maxTouchPoints || 0) > 0);
}
export function bindLegacyWorkerContext(solution, version) {
  if (version !== '0.5.1675471629') throw new Error('Unsupported legacy worker SDK');
  const graph = solution?.h, context = graph?.i?.GL?.currentContext?.GLctx;
  if (!context || !graph.m || context.canvas !== graph.m) throw new Error('Missing isolated legacy worker GL context');
  if (graph.K && graph.K !== context) throw new Error('Legacy worker GL context differs');
  graph.K = context;
}
