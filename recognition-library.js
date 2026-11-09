// Learning-video availability and recognition availability are independent.
const previews=new Set(['default-preview','existing-preview','daily-preview','category-preview','capstone-preview','beginner-preview']);
export function isLocalReferenceHost(hostname=globalThis.location?.hostname||''){
  return ['localhost','127.0.0.1','::1','[::1]'].includes(hostname.toLowerCase().replace(/\.$/,''));
}
export function canWatchReference(item,hostname=globalThis.location?.hostname||''){
  return Boolean(item?.video&&(!item.localResearchOnly||isLocalReferenceHost(hostname)));
}
export function hasRecognitionModel(item){
  return Boolean(item&&(item.recognitionModes?.length||item.cameraGroups?.length||previews.has(item.recognition)));
}
export function recognitionBadge(item){
  if(item?.recognition==='default-preview')return 'Default motion preview';
  if(item?.recognition==='daily-preview')return 'Five-word server preview';
  if(item?.cameraGroups?.length)return 'Category recognition preview';
  if(item?.recognition==='existing-preview')return 'Extra-word motion preview';
  const modes=item?.recognitionModes||[];
  if(modes.includes('capstone-full')&&modes.includes('beginner'))return '100-word / Beginner-79 server previews';
  if(modes.includes('capstone-full'))return '100-word server preview';
  if(modes.includes('beginner'))return 'Beginner-79 server preview';
  return 'No enabled model';
}
export function serverPracticeTarget(item){
  const modes=item?.recognitionModes||[];
  if(item?.recognition==='beginner-preview')return {target:'#beginnerWords',model:'Beginner-79'};
  if(modes.includes('capstone-full')){
    const vocabulary=modes.includes('capstone-core')?'core':modes.includes('capstone-extended')?'extended':'full';
    return {target:'#capstoneWords',model:'100-word',vocabulary};
  }
  if(modes.includes('beginner'))return {target:'#beginnerWords',model:'Beginner-79'};
  return null;
}
