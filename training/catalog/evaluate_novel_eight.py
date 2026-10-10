"""Fresh recordings for the explicitly narrowed candidate, never auto-deploy."""
from pathlib import Path
import evaluate_calibrated_candidate as evaluation

def main():
    evaluation.SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-novel-eight-frozen')
    evaluation.ROOT=Path('/opt/handspeak-training/vocabulary-expansion-novel-eight-fresh')
    evaluation.REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/novel-eight')
    evaluation.base.ROOT=evaluation.ROOT;evaluation.base.REPORT=evaluation.REPORT
    evaluation.main()
if __name__=='__main__':main()
