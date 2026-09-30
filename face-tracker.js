// Visible facial movements only; these cues do not measure a person's emotions.
export function facialExpression(scores){
  const required=['mouthSmileLeft','mouthSmileRight','jawOpen','browInnerUp','browDownLeft','browDownRight'];
  if(!required.every(key=>Number.isFinite(scores[key])&&scores[key]>=0&&scores[key]<=1))return null;
  const cues=[];
  if(Math.min(scores.mouthSmileLeft,scores.mouthSmileRight)>.45)cues.push('Smiling');
  if(scores.jawOpen>.45)cues.push('Mouth open');
  if(scores.browInnerUp>.5)cues.push('Brows raised');
  if(Math.min(scores.browDownLeft,scores.browDownRight)>.5)cues.push('Brows lowered');
  return cues.slice(0,2).join(' · ')||'No clear expression';
}

export function createFaceTracker(onState,onExpression=()=>{}){
  let enabled=true,model=null,pending=null,vision=null,fileset=null,connections=[];
  let landmarks=[],lastFrame=-Infinity;
  let scores={},candidate='',candidateSince=0,expression='';
  function showExpression(value){if(value!==expression){expression=value;onExpression(value);}}
  function clearExpression(value){scores={};candidate='';candidateSince=0;showExpression(value);}
  const report=state=>{onState(state);if(state!=='Face tracked')clearExpression(state);};
  function updateExpression(categories,now){
    const current=Object.fromEntries((categories||[]).map(c=>[c.categoryName,c.score]));
    if(facialExpression(current)===null){clearExpression('Unavailable');return;}
    for(const [key,value] of Object.entries(current))scores[key]=scores[key]===undefined?value:scores[key]*.6+value*.4;
    const label=facialExpression(scores);
    if(candidate!==label){candidate=label;candidateSince=now;}
    if(now-candidateSince>=300)showExpression(label);
    else if(!['Smiling','Mouth open','Brows raised','Brows lowered','No clear expression'].some(cue=>expression.includes(cue)))showExpression('Reading expression…');
  }
  async function load(api=vision,assets=fileset){
    vision=api;fileset=assets;
    if(!enabled||!vision)return;
    if(model){report('Ready');return;}
    if(pending)return pending;
    report('Loading…');
    pending=(async()=>{
      try{
        const options={
          baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',delegate:'GPU'},
          runningMode:'VIDEO',numFaces:1,minFaceDetectionConfidence:.6,minFacePresenceConfidence:.6,minTrackingConfidence:.6,
          outputFaceBlendshapes:true,outputFacialTransformationMatrixes:false
        };
        try{model=await vision.FaceLandmarker.createFromOptions(fileset,options);}
        catch{options.baseOptions.delegate='CPU';model=await vision.FaceLandmarker.createFromOptions(fileset,options);}
        connections=['FACE_LANDMARKS_FACE_OVAL','FACE_LANDMARKS_LEFT_EYE','FACE_LANDMARKS_RIGHT_EYE','FACE_LANDMARKS_LIPS']
          .flatMap(name=>vision.FaceLandmarker[name]||[]);
        report(enabled?'Ready':'Off');
      }catch(error){console.warn('Face tracking unavailable',error);report(enabled?'Unavailable':'Off');}
      finally{pending=null;}
    })();
    return pending;
  }
  function reset(){landmarks=[];lastFrame=-Infinity;report(!enabled?'Off':model?'Ready':pending?'Loading…':'Camera off');}
  return {
    load,reset,
    setEnabled(value){enabled=value;reset();if(enabled)void load();},
    draw(video,now,ctx,width,height){
      if(!enabled||!model)return;
      if(now-lastFrame>=100){
        // Slow devices can take over 400 ms per frame; do not restart stability
        // timing on every inference. Discard old smoothing after a long gap.
        if(now-lastFrame>1000)scores={};
        lastFrame=now;
        try{
          const result=model.detectForVideo(video,now);
          landmarks=result.faceLandmarks?.[0]||[];
          if(!landmarks.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)))landmarks=[];
          report(landmarks.length?'Face tracked':'No face');
          if(landmarks.length)updateExpression(result.faceBlendshapes?.[0]?.categories,now);
        }catch(error){
          console.warn('Face tracking stopped',error);model.close?.();model=null;landmarks=[];report('Unavailable');return;
        }
      }
      if(!landmarks.length)return;
      ctx.save();ctx.strokeStyle='rgba(214,232,193,.55)';ctx.lineWidth=1;
      ctx.beginPath();
      for(const {start,end} of connections){
        const a=landmarks[start],b=landmarks[end];if(!a||!b)continue;
        ctx.moveTo(a.x*width,a.y*height);ctx.lineTo(b.x*width,b.y*height);
      }
      ctx.stroke();ctx.fillStyle='rgba(224,238,210,.6)';
      for(let i=0;i<landmarks.length;i+=4){const p=landmarks[i];ctx.beginPath();ctx.arc(p.x*width,p.y*height,1,0,Math.PI*2);ctx.fill();}
      const xs=landmarks.map(p=>p.x*width),ys=landmarks.map(p=>p.y*height);
      const left=Math.max(0,Math.min(...xs)-8),top=Math.max(0,Math.min(...ys)-8);
      const right=Math.min(width,Math.max(...xs)+8),bottom=Math.min(height,Math.max(...ys)+8);
      ctx.strokeStyle='rgba(214,232,193,.8)';ctx.strokeRect(left,top,right-left,bottom-top);ctx.restore();
    }
  };
}
