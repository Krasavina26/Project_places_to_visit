# utils.py
import pandas as pd
from typing import List

def reciprocal_rank_fusion(results: List[pd.DataFrame], k: int = 60) -> pd.DataFrame:
    """RRF — объединение результатов нескольких модулей"""
    scores = {}
    
    for df in results:
        for rank, idx in enumerate(df.index):
            if idx not in scores:
                scores[idx] = 0.0
            scores[idx] += 1.0 / (k + rank + 1)
    
    combined = pd.DataFrame.from_dict(scores, orient='index', columns=['rrf_score'])
    return combined
