// Preinitialize infrastructure without images, but never return a retired
// instance when the capture owner asks to replace a failed/closed graph.
export async function prepareTrackerFactory(makeTracker) {
  let current=await makeTracker(),unused=true;
  return {
    get current(){return current;},
    async acquire(){
      if(unused){unused=false;return current;}
      current=await makeTracker();return current;
    },
  };
}
