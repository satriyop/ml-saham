"""Ch.9 Headline tone — synthetic sentiment lab (no headlines table)."""

from __future__ import annotations

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterError
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult

META = get_meta("headline-tone")

# Synthetic Indonesian headline corpus — pos=1 neg=0
_SYNTHETIC_HEADLINES: list[tuple[str, int]] = [
    ("Saham BBRI melonjak setelah laporan laba kuartal melebihi ekspektasi", 1),
    ("Emiten teknologi IDX naik tajam didorong kontrak baru", 1),
    ("Bank besar catat pertumbuhan kredit double digit", 1),
    ("Prospek dividen menarik, analis naikkan target harga", 1),
    ("Ekspor nikel rebound, saham tambang hijau di sesi pagi", 1),
    ("Sentimen pasar positif pasca data inflasi terkendali", 1),
    ("Rights issue sukses, modal kerja emiten retail menguat", 1),
    ("Foreign flow net buy mendominasi saham blue chip", 1),
    ("Kinerja operasional perusahaan farmasi ungguli peer", 1),
    ("IHSG tembus rekor, investor optimistis outlook kuartal", 1),
    ("Saham gorengan anjlok setelah suspensi bursa", 0),
    ("Emiten properti rugi besar, manajemen waspada default", 0),
    ("Skandal akuntansi memicu aksi jual massal", 0),
    ("Penerbitan obligasi konversi tekan harga saham pemegang lama", 0),
    ("Konflik korporasi, komisaris dan direksi berselisih terbuka", 0),
    ("Laba bersih turun drastis karena beban bunga", 0),
    ("Regulator tegur emiten atas keterlambatan laporan keuangan", 0),
    ("Proyek strategis mangkrak, analis potong rating", 0),
    ("Arus kas negatif, emiten kecil khawatir likuiditas", 0),
    ("Sentimen risk-off global, saham emerging market melemah", 0),
    ("Harga komoditas jatuh, saham tambang tertekan", 0),
    ("Gagal bayar kupon obligasi, saham turun limit down", 0),
    ("Manajemen mengundurkan diri pasca audit menemukan kelemahan", 0),
    ("Pemegang saham mayoritas jual blok besar di pasar", 0),
]


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Berita singkat mempengaruhi sentimen — tapi tanpa pipeline headline",
        "  yang bersih, kita belajar dulu dari korpus sintetis.",
        "",
        "Opsi pendekatan",
        "  1) TF-IDF + MultinomialNB / LogisticRegression",
        "  2) Lexicon rule-based (baseline)",
        "  3) Nanti: korpus real + PIT fetched_date",
        "",
        "Caveat",
        "  • Demo ini pakai headline SINTETIS — bukan data live",
        "  • Akurasi in-sample ≠ edge trading",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDeepdive: jalur sentiment ai-saham bila tabel headline ada.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    texts = [t for t, _ in _SYNTHETIC_HEADLINES]
    labels = [y for _, y in _SYNTHETIC_HEADLINES]
    Xtr, Xte, ytr, yte = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    nb_pipe = Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=200, ngram_range=(1, 2))),
            ("clf", MultinomialNB()),
        ]
    )
    lr_pipe = Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=200, ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=500, random_state=42)),
        ]
    )
    nb_pipe.fit(Xtr, ytr)
    lr_pipe.fit(Xtr, ytr)
    acc_nb = float(accuracy_score(yte, nb_pipe.predict(Xte)))
    acc_lr = float(accuracy_score(yte, lr_pipe.predict(Xte)))
    best = "logistic-regression" if acc_lr >= acc_nb else "multinomial-nb"
    acc_best = max(acc_nb, acc_lr)
    model = lr_pipe if best == "logistic-regression" else nb_pipe

    # Extract top informative words from Naive Bayes log-ratio
    vec = nb_pipe.named_steps["tfidf"]
    nb_clf = nb_pipe.named_steps["clf"]
    feats = vec.get_feature_names_out()
    log_ratio = nb_clf.feature_log_prob_[1] - nb_clf.feature_log_prob_[0]
    top_pos = [feats[i] for i in log_ratio.argsort()[-5:][::-1]]
    top_neg = [feats[i] for i in log_ratio.argsort()[:5]]

    sample = "Emiten catat pertumbuhan laba kuartal di atas estimasi pasar"
    pred = int(model.predict([sample])[0])
    proba = model.predict_proba([sample])[0]

    lines = [
        ">>> DATA SINTETIS — bukan headline live dari DB <<<",
        f"Korpus: n={len(texts)} headline ID (pos/neg)",
        f"Train={len(Xtr)}  test={len(Xte)}",
        f"MultinomialNB accuracy:        {acc_nb:.3f}",
        f"LogisticRegression accuracy:   {acc_lr:.3f}",
        f"Best model: {best}  accuracy={acc_best:.3f}",
        f"Top positive words: {', '.join(top_pos)}",
        f"Top negative words: {', '.join(top_neg)}",
        "",
        f"Contoh inferensi: \"{sample[:50]}...\"",
        f"  pred={'positif' if pred else 'negatif'}  "
        f"P(pos)={float(proba[1]):.2f}",
        "",
        "Catatan: bila tabel headline ada di ai-saham, ganti korpus sintetis",
        "dengan fetch PIT + validasi out-of-time.",
    ]

    metrics = {
        "n_corpus": len(texts),
        "accuracy_nb": acc_nb,
        "accuracy_lr": acc_lr,
        "accuracy_best": acc_best,
        "top_positive_words": top_pos,
        "top_negative_words": top_neg,
        "model": best,
        "synthetic": True,
    }
    return DemoResult(
        title="Headline tone · synthetic TF-IDF lab",
        lines=lines,
        metrics=metrics,
        model=best,
        summary_md=(
            "# Headline tone\n\n"
            "Synthetic Indonesian headlines · TF-IDF classifier.\n"
            f"Best accuracy={acc_best:.3f} ({best}).\n"
        ),
        scoreboard=True,
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="headlines_cache / sentiment pipeline di ai-saham (bila ada)",
        bring_back="TF-IDF + label hygiene + PIT fetched_date habit",
    )
