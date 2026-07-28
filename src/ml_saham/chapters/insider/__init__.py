"""Ch.7 Insider — sparse disclosed insider events."""

from __future__ import annotations

from collections import defaultdict

from ml_saham.chapters.deepdive_stub import deepdive_stub
from ml_saham.chapters.errors import ChapterDataError, ChapterError
from ml_saham.chapters.panel import (
    forward_returns_by_ticker,
    maybe_haircut,
    pick_as_of,
    resolve_universe,
)
from ml_saham.chapters.registry import get as get_meta
from ml_saham.chapters.types import ChapterContext, DemoResult
from ml_saham.data.aisaham_read import connect, insider_date_stats, load_insider_events
from ml_saham.eval.metrics import rank_ic

META = get_meta("insider")


def explore_text(*, verbose: bool = False) -> str:
    lines = [
        f"Ch.{META.number}  {META.title}",
        f"topic={META.slug}  phase={META.phase}  data={META.required_data}",
        "",
        "Masalah",
        "  Aktivitas insider yang diumumkan jarang dan berisik. Banyak bar cache",
        "  punya tanggal absurd (mis. 1970) — harus di-scrub dulu.",
        "",
        "Opsi pendekatan",
        "  1) Aturan: net BUY−SELL shares dalam lookback → rank",
        "  2) Logistic / tree kecil pada fitur net + count events",
        "  3) Bandingkan rank IC vs forward return (jujur, n sering kecil)",
        "",
        "Caveat",
        "  • Disclosure ≠ edge; delay & seleksi pelaporan penting",
        "  • Scrub tanggal <1990 di adapter (lihat doctor absurd_dates)",
        "  • Skorboard: long-only vs IHSG · belum termasuk biaya",
        "  • Bukan saran trading / investasi",
        "",
        f"Lanjut:  ml-saham demo {META.slug}",
    ]
    if verbose:
        lines.append("\nDetail: deepdive boleh menyinggung insider enrichment flags ai-saham.")
    return "\n".join(lines)


def run_demo(ctx: ChapterContext) -> DemoResult:
    with connect(ctx.db_path) as conn:
        stats = insider_date_stats(conn)
        if stats["usable"] <= 0:
            raise ChapterDataError(
                "insider_cache kosong atau hanya placeholder. "
                "Cek doctor (absurd_dates / usable)."
            )
        uni = ctx.universe or resolve_universe(conn, limit=50)
        as_of = ctx.as_of or pick_as_of(conn, uni, min_forward=5)
        if not as_of:
            raise ChapterDataError("Tidak cukup history untuk as_of.")
        # lookback ~60 calendar days before as_of
        events = load_insider_events(conn, uni, end=as_of, scrub_absurd_dates=True)
        fwd = forward_returns_by_ticker(conn, uni, as_of=as_of, horizon=5)

    # filter events in lookback window (string compare ISO dates)
    lookback_start = as_of  # refine below
    # approximate: keep events within last ~90 days lexicographically by trimming
    from datetime import date, timedelta

    try:
        as_of_d = date.fromisoformat(as_of)
        lookback_start = (as_of_d - timedelta(days=90)).isoformat()
    except ValueError:
        lookback_start = "1900-01-01"

    net: dict[str, float] = defaultdict(float)
    buys: dict[str, int] = defaultdict(int)
    sells: dict[str, int] = defaultdict(int)
    for e in events:
        d = e["transaction_date"]
        if d < lookback_start or d > as_of:
            continue
        t = e["ticker"]
        shares = float(e.get("shares") or 0)
        action = str(e.get("action_type") or "").upper()
        if action == "BUY" and shares > 0:
            net[t] += shares
            buys[t] += 1
        elif action == "SELL" and shares > 0:
            net[t] -= shares
            sells[t] += 1

    tickers = sorted(set(net) & set(fwd))
    if len(tickers) < 8:
        raise ChapterDataError(
            f"Panel insider×forward terlalu kecil (n={len(tickers)}). "
            "Perlu lebih banyak overlap universe + events."
        )

    scores = [net[t] for t in tickers]
    rets = maybe_haircut([fwd[t] for t in tickers], with_costs=ctx.with_costs)
    ic_rule = rank_ic(scores, rets)

    model_name = "net_shares_rule"
    ic_model = ic_rule
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression

        X = np.array(
            [
                [
                    net[t],
                    buys[t],
                    sells[t],
                    buys[t] + sells[t],
                ]
                for t in tickers
            ],
            dtype=float,
        )
        y_ret = rets
        med = sorted(y_ret)[len(y_ret) // 2]
        y = np.array([1 if r >= med else 0 for r in y_ret])
        feat_names = ["net_shares", "buys", "sells", "total_events"]
        coef_dict = {}
        if len(set(y.tolist())) >= 2:
            clf = LogisticRegression(max_iter=500)
            clf.fit(X, y)
            proba = clf.predict_proba(X)[:, 1].tolist()
            ic_model = rank_ic(proba, rets)
            model_name = "logistic"
            scores_model = proba
            coef_dict = dict(zip(feat_names, clf.coef_[0].tolist(), strict=True))
        else:
            scores_model = scores
    except ImportError as exc:
        raise ChapterError("Butuh scikit-learn: pip install -e .") from exc

    order = sorted(range(len(tickers)), key=lambda i: scores_model[i], reverse=True)
    top = [
        {
            "ticker": tickers[i],
            "score": scores_model[i],
            "net_shares": net[tickers[i]],
            "buys": buys[tickers[i]],
            "sells": sells[tickers[i]],
            "fwd": rets[i],
        }
        for i in order[:10]
    ]
    lines = [
        f"as_of={as_of}  lookback_start={lookback_start}  n={len(tickers)}",
        f"Cache: total={stats['total']} usable={stats['usable']} "
        f"absurd_scrubbed≈{stats['absurd']}",
        f"Rule net-shares rank IC: {ic_rule:+.3f}",
        f"Model ({model_name}) rank IC: {ic_model:+.3f}  (in-sample)",
    ]
    if coef_dict:
        coef_str = ", ".join(f"{k}:{v:+.3f}" for k, v in coef_dict.items())
        lines.append(f"Model feature weights:   {coef_str}")

    lines.extend([
        "",
        "Top scored names:",
    ])
    for t in top[:8]:
        lines.append(
            f"  {t['ticker']:<6} score={t['score']:.3f}  net={t['net_shares']:.3g}  "
            f"B/S={t['buys']}/{t['sells']}  fwd={t['fwd']:+.2%}"
        )

    metrics = {
        "as_of": as_of,
        "n": len(tickers),
        "rank_ic_rule": ic_rule,
        "rank_ic_model": ic_model,
        "feature_coefs": coef_dict,
        "insider_stats": stats,
        "n_tickers": len(tickers),
    }
    csv = ["ticker,score,net_shares,buys,sells,fwd"] + [
        f"{t['ticker']},{t['score']:.6f},{t['net_shares']:.6f},"
        f"{t['buys']},{t['sells']},{t['fwd']:.6f}"
        for t in top
    ]
    return DemoResult(
        title="Insider · net shares + logistic",
        lines=lines,
        metrics=metrics,
        model=model_name,
        summary_md=(
            f"# Insider\n\nas_of={as_of}. Scrub tanggal <1990. "
            f"Rule IC={ic_rule:.3f}, model IC={ic_model:.3f}.\n"
        ),
        scoreboard=True,
        top_names=top,
        extra_files={"top_names.csv": "\n".join(csv) + "\n"},
    )


def deepdive_text() -> str:
    return deepdive_stub(
        topic=META.slug,
        related="insider enrichment flags di ai-saham",
        bring_back="scrub absurd dates + net BUY/SELL rank habit",
    )
