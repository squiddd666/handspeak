import unittest
import torch
from remap_rejection_head import remap
class RejectionHeadTest(unittest.TestCase):
    def test_split_preserves_supported_and_total_rejection_probability(self):
        torch.manual_seed(3)
        old={'head.1.weight':torch.randn(3,5),'head.1.bias':torch.randn(3)}
        new={'head.1.weight':torch.zeros(4,5),'head.1.bias':torch.zeros(4)}
        result=remap(old,new,['A','OTHER MOVEMENT','B'],['B','MOVEMENT: X','A','MOVEMENT: Y'])
        x=torch.randn(7,5);before=(x@old['head.1.weight'].T+old['head.1.bias']).softmax(1);after=(x@result['head.1.weight'].T+result['head.1.bias']).softmax(1)
        self.assertTrue(torch.allclose(before[:,0],after[:,2],atol=1e-6));self.assertTrue(torch.allclose(before[:,2],after[:,0],atol=1e-6));self.assertTrue(torch.allclose(before[:,1],after[:,1]+after[:,3],atol=1e-6))
        self.assertTrue(torch.equal(new['head.1.weight'],torch.zeros(4,5)))
if __name__=='__main__':unittest.main()
