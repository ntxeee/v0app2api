# -*- coding: utf-8 -*-
"""train_char.py — 快速重训最优配置(char3-5 + SVD150 + SVC-RBF C100),存 pkl + CV 评估。
monitor 自动重训调这个,不再用 recognize.py 的弱配置覆盖好模型。
"""
from __future__ import annotations
import json
import pickle
import time
import warnings

from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.preprocessing import Normalizer
from sklearn.pipeline import make_pipeline
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import accuracy_score

import recognize_refine as rr

warnings.filterwarnings("ignore")


def train_and_save():
    rows, Xb, y, g, dv, texts = rr.load()
    tv = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=60000,
                         sublinear_tf=True, min_df=3)
    Xc = tv.fit_transform([t.replace("\r\n", "\n") for t in texts])
    X = hstack([Xb, Xc]).tocsr()
    clf = make_pipeline(TruncatedSVD(n_components=150, random_state=42),
                        Normalizer(copy=False), SVC(C=100, gamma="scale", kernel="rbf"))
    acc, preds, mask = rr.cv_score(clf, X, y, g)
    clf.fit(X, y)
    with open(rr.MODEL_PATH, "wb") as f:
        pickle.dump({"pipeline": clf, "vectorizer": dv, "char_vectorizer": tv,
                     "label_merge": "fast_merged", "best_cv_acc": acc,
                     "best_name": "char_svd150_C100", "labels": sorted(set(y)),
                     "feature_schema": "base+structural+char3-5",
                     "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_samples": len(y)}, f)
    per = {}
    for lab in sorted(set(y)):
        m = mask & (y == lab)
        per[lab] = {"n": int(m.sum()),
                    "acc": round(float(accuracy_score(y[m], preds[m])), 3) if m.sum() else None}
    rep = {"best_accuracy": acc, "samples": len(y), "labels": len(set(y)),
           "calibration_pass": bool(acc >= 0.8 and mask.sum() >= 30),
           "coverage_pass": {}, "results": per}
    rr.rlog({"event": "train_char", "acc": round(acc, 4), "samples": len(y)})
    return rep


if __name__ == "__main__":
    rep = train_and_save()
    print(json.dumps({"acc": rep["best_accuracy"], "samples": rep["samples"]}, ensure_ascii=False), flush=True)