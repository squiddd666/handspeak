// Feature normalization must match training/train_asl.py.
export function normalizeLandmarks(points){
  const wrist=points[0], middleBase=points[9];
  const scale=Math.hypot(points[5].x-points[17].x,points[5].y-points[17].y)||1;
  const angle=Math.atan2(middleBase.y-wrist.y,middleBase.x-wrist.x)-Math.PI/2;
  const cosine=Math.cos(-angle),sine=Math.sin(-angle);
  return points.flatMap(point=>{
    const x=(point.x-wrist.x)/scale,y=(point.y-wrist.y)/scale;
    return [x*cosine-y*sine,x*sine+y*cosine,(point.z-wrist.z)/scale];
  });
}

export function validSample(sample, labels){
  return sample && labels.includes(sample.label) && Array.isArray(sample.features)
    && sample.features.length===63 && sample.features.every(Number.isFinite);
}

export function classifyFeatures(features, samples){
  const counts={};samples.forEach(sample=>counts[sample.label]=(counts[sample.label]||0)+1);
  if(Object.values(counts).filter(count=>count>=10).length<2)return null;
  const neighbors=samples.filter(sample=>counts[sample.label]>=10).map(sample=>{
    let sum=0;for(let i=0;i<features.length;i++){const delta=features[i]-sample.features[i];sum+=delta*delta}
    return {label:sample.label,distance:Math.sqrt(sum/features.length)};
  }).sort((a,b)=>a.distance-b.distance).slice(0,5);
  const votes={};neighbors.forEach(item=>votes[item.label]=(votes[item.label]||0)+1/(item.distance+.001));
  const ranked=Object.entries(votes).sort((a,b)=>b[1]-a[1]);
  const total=ranked.reduce((sum,item)=>sum+item[1],0);
  const nearest=neighbors[0]?.distance??1;
  const confidence=Math.min(.99,(ranked[0][1]/total)*Math.max(.55,1-nearest));
  return confidence>=.62?{letter:ranked[0][0],confidence,source:'ai'}:null;
}
