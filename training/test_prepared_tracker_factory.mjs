import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareTrackerFactory} from './experimental/prepared_tracker_factory.mjs';

test('preinitialized graph is used once; retired graphs are never reacquired',async()=>{
  let made=0;
  const factory=await prepareTrackerFactory(async()=>({id:++made,closed:false,close(){this.closed=true;}}));
  assert.equal(made,1);const first=await factory.acquire();assert.equal(first.id,1);
  first.close();const second=await factory.acquire();assert.equal(made,2);
  assert.notEqual(second,first);assert.equal(second.closed,false);assert.equal(factory.current,second);
});

test('replacement initialization failures do not return a stale instance',async()=>{
  let made=0;const factory=await prepareTrackerFactory(async()=>{if(++made===2)throw new Error('init failed');return {id:made};});
  await factory.acquire();await assert.rejects(factory.acquire(),/init failed/);
  assert.equal((await factory.acquire()).id,3);
});
