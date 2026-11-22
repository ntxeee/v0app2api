# -*- coding: utf-8 -*-
"""recognize_refine2.py — 字符 n-gram 风格指纹实验:base+结构特征 拼接 char_wb TF-IDF。"""
from __future__ import annotations
import json
import os
import pickle
import time
import warnings

import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.preprocessing import Normalizer
from sklearn.pipeline import make_pipeline
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import accuracy_score, confusion_matrix

import recognize_refine as rr

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    rows, Xb, y, g, dv, texts = rr.load()
    clean = [t.replace("\r\n", "\n") for t in texts]
    tv = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=60000,
                         sublinear_tf=True, min_df=3)
    Xc = tv.fit_transform(clean)
    X = hstack([Xb, Xc]).tocsr()
    rr.rlog({"event": "loaded2", "base_features": Xb.shape[1], "char_features": Xc.shape[1],
             "total": X.shape[1]})
    results = []
    best = [0, None, None]
    for nc in (150, 200, 300):
        for C in (10, 100):
            name = "char_svd%d_C%d" % (nc, C)
            clf = make_pipeline(TruncatedSVD(n_components=nc, random_state=42),
                                Normalizer(copy=False), SVC(C=C, gamma="scale", kernel="rbf"))
            t0 = time.time()
            acc, preds, mask = rr.cv_score(clf, X, y, g)
            results.append((name, acc))
            rr.rlog({"event": "trial2", "name": name, "acc": round(acc, 4),
                     "secs": round(time.time() - t0, 1)})
            if acc > best[0]:
                best[:] = [acc, name, clf]
    results.sort(key=lambda x: -x[1])
    rr.rlog({"event": "ranking2", "results": [(n, round(a, 4)) for n, a in results]})
    acc, name, clf = best
    if acc > 0.6215:
        clf.fit(X, y)
        with open(rr.MODEL_PATH, "wb") as f:
            pickle.dump({"pipeline": clf, "vectorizer": dv, "char_vectorizer": tv,
                         "label_merge": "fast_merged", "best_cv_acc": acc, "best_name": name,
                         "labels": sorted(set(y)),
                         "feature_schema": "base+structural+char3-5",
                         "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_samples": len(y)}, f)
        rr.rlog({"event": "saved2", "name": name, "acc": round(acc, 4)})
    print("BEST2 %s acc=%.4f" % (name, acc), flush=True)


if __name__ == "__main__":
    main()