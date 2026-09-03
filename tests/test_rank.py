from hive.papers.schemas import Paper
from hive.papers.rank import score_paper, rank_papers

def test_score_and_rank():
    p1 = Paper(id="1", title="Sparse autoencoders for interpretability", authors=["A"], cited_by_count=500, venue="NeurIPS", year=2024, is_open_access=True, abstract="x "*50)
    p2 = Paper(id="2", title="Unrelated", authors=["B"], cited_by_count=2, venue="arXiv", year=2020, is_open_access=False, abstract="short")
    s1, _ = score_paper(p1, query="sparse autoencoders interpretability")
    s2, _ = score_paper(p2, query="sparse autoencoders interpretability")
    assert s1 > s2
    ranked = rank_papers([p2, p1], query="sparse autoencoders")
    assert ranked[0].id == "1"
