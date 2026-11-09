import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=readFileSync(new URL('./ux/motion_virtual_runner.js',import.meta.url),'utf8');
const bootstrap=readFileSync(new URL('./ux/motion_virtual_source.js',import.meta.url),'utf8');

test('the virtual runner references only real app or diagnostic controls',()=>{
  const markup=html+source+bootstrap;
  const ids=new Set([...markup.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
  for(const match of markup.matchAll(/\.id\s*=\s*['"]([^'"]+)['"]/g))ids.add(match[1]);
  const used=[...source.matchAll(/(?:\$|setChecked)\('([^']+)'/g)].map(m=>m[1]);
  for(const id of used)assert.ok(ids.has(id),`Missing visible control: ${id}`);
});

test('daily preview consent is the existing preview checkbox, not a invented control',()=>{
  assert.match(source,/\$\('researchWordsToggle'\)\.checked/);
  assert.doesNotMatch(source,/setChecked\('researchWordsConsent'/);
});

test('reference tests never add reviewed words or substitute expected predictions',()=>{
  assert.doesNotMatch(source,/(?:capstoneAccept|beginnerAccept|researchAccept|motionAccept)/);
  assert.doesNotMatch(source,/\.recognize\(|\.onWord\(|\.predicted\s*=/);
});

test('optional virtual stream recovery uses only public camera controls',()=>{
  assert.match(source,/if \(config\.restartVirtualStreamEachReference\)/);
  assert.match(source,/\$\('cameraButton'\)\.click\(\)/);
  assert.doesNotMatch(source,/getUserMedia\(|captureStream\(|new Holistic|\.recognize\(/);
});
