"""
轻量级向量检索 —— TF-IDF + 余弦相似度。

两级检索管线：向量粗筛（本模块）→ LLM 精排（matcher.py）。
无外部依赖，纯 Python + 标准库实现。可替换为 ChromaDB / FAISS。
"""

import math
import re
from collections import Counter
from typing import Iterable


# ---- 中文分词（简易 n-gram） ----

_CJK_RE = re.compile(r"[一-鿿]+")
_ALNUM_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str, ngram: int = 2) -> list[str]:
    """中文用 2-gram 切词，英文/数字用空格分词。"""
    tokens = []
    text = text.lower()
    # 提取 CJK 文本做 n-gram
    for cjk_span in _CJK_RE.finditer(text):
        t = cjk_span.group()
        if len(t) == 1:
            tokens.append(t)
        else:
            tokens.extend(t[i : i + ngram] for i in range(len(t) - ngram + 1))
    # 提取英文/数字
    tokens.extend(_ALNUM_RE.findall(text))
    return tokens


# ---- TF-IDF ----

class TfIdfVectorizer:
    """Mini TF-IDF，适合几百条 JD 的本地检索。"""

    def __init__(self, max_features: int = 5000):
        self._idf: dict[str, float] = {}
        self._vocab: list[str] = []
        self._max_features = max_features

    def fit(self, documents: list[str]) -> "TfIdfVectorizer":
        n = len(documents)
        # 统计文档频率
        df: Counter[str] = Counter()
        tokenized_docs: list[list[str]] = []
        for doc in documents:
            tokens = list(set(_tokenize(doc)))
            tokenized_docs.append(tokens)
            df.update(tokens)

        # 取 top max_features 词
        top = [w for w, _ in df.most_common(self._max_features)]
        self._vocab = top
        # 计算 IDF
        self._idf = {w: math.log((n + 1) / (df[w] + 1)) + 1.0 for w in top}
        return self

    def transform(self, document: str) -> list[float]:
        """返回 TF-IDF 向量。"""
        tokens = _tokenize(document)
        tf = Counter(tokens)
        total = len(tokens) or 1
        vec = [0.0] * len(self._vocab)
        for i, w in enumerate(self._vocab):
            if w in tf:
                vec[i] = (tf[w] / total) * self._idf.get(w, 0.0)
        return vec


# ---- 余弦相似度 ----

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---- 向量检索接口 ----

class JobVectorStore:
    """JD 向量索引 —— 候选岗位粗筛。

    使用方式:
        store = JobVectorStore()
        store.index(resume_text, job_descriptions)
        top_jds = store.search(resume_text, top_k=30)
    """

    def __init__(self):
        self._vectorizer: TfIdfVectorizer | None = None
        self._vectors: list[list[float]] = []
        self._documents: list[str] = []
        self._resume_text = ""

    def index(self, resume_text: str, jd_texts: list[str]) -> None:
        """用简历 + 全部 JD 建 TF-IDF 词表，计算每个 JD 的向量。"""
        self._resume_text = resume_text
        all_docs = [resume_text] + jd_texts
        self._vectorizer = TfIdfVectorizer(max_features=3000).fit(all_docs)
        self._documents = jd_texts
        self._vectors = [self._vectorizer.transform(jd) for jd in jd_texts]

    def search(self, query: str | None = None, top_k: int = 30,
               min_score: float = 0.05) -> list[tuple[int, float]]:
        """返回 (原始索引, 相似度) 按相似度降序，过滤低于 min_score 的结果。"""
        if self._vectorizer is None or not self._vectors:
            return [(i, 1.0) for i in range(min(top_k, len(self._documents)))]

        query = query or self._resume_text
        q_vec = self._vectorizer.transform(query)

        scored = [(i, cosine_similarity(q_vec, v)) for i, v in enumerate(self._vectors)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in scored[:top_k] if s >= min_score]


# 全局单例
job_vector_store = JobVectorStore()
