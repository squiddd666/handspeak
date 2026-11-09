"""Original isolated APIs/capture ledger plus immutable rejection-only supplement."""
import argparse,copy,json,threading
from pathlib import Path
from scripts import serve_online_worker_audit as base

OriginalStore=base.Store


class GuardStore(OriginalStore):
    def __init__(self,folder,cfg,receipts):
        super().__init__(folder,cfg,receipts);self.guard_folder=folder/'guard';self.guard_folder.mkdir()
        self.guard_previous=None;self.guard_lock=threading.Lock()

    def save(self,report):
        if report.get('schema')!=5:raise ValueError('Guard development schema 5 required')
        plain=copy.deepcopy(report);plain['schema']=4;extras=[]
        for a in plain['attempts']:
            predictions=a.pop('manualGuardPredictions',None);reasons=a.pop('manualGuardReasons',None)
            if not isinstance(predictions,dict) or set(predictions)!={'default','expanded','daily','pack'} or not isinstance(reasons,dict) or set(reasons)!=set(predictions):
                raise ValueError('Independent guard mode outcomes required')
            if any(predictions[m] not in (None,a['manualPredictions'][m]) for m in predictions):raise ValueError('Guard must not generate/change baseline words')
            if any(not isinstance(reason,str) or len(reason)>40 for reason in reasons.values()):raise ValueError('Scalar guard reasons required')
            extras.append(dict(number=a['number'],id=a['id'],clipSha256=a['clipSha256'],predictions=predictions,reasons=reasons))
        with self.guard_lock:
            old=self.guard_previous
            if old and extras[:len(old)]!=old:raise ValueError('Past guard outcomes cannot change')
            count=super().save(plain)
            for a in extras[len(old) if old else 0:]:
                with (self.guard_folder/f"attempt-{a['number']:03}.json").open('x',encoding='utf-8') as f:json.dump(a,f,indent=2)
            tmp=self.guard_folder/'checkpoint.tmp';tmp.write_text(json.dumps(extras,indent=2)+'\n','utf-8');tmp.replace(self.guard_folder/'checkpoint.json')
            self.guard_previous=copy.deepcopy(extras)
        return count


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8011);args=parser.parse_args()
    base.Store=GuardStore  # Only the owned audit subprocess, never production server state.
    base.main(args)
