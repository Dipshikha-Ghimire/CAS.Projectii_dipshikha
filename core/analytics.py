"""CAS analytics: the calculations behind the dashboard.

Pure Python (no Django), so it can be tested on its own.
Scores are PERCENTAGES (0-100), oldest first, from repeated achievement
measures only (unit tests and terminal exams).

Methods (as in the proposal, Section 4.5, revised after supervisor feedback):
  * Theil-Sen slope: median of all pairwise slopes (robust to one bad test)
  * EWMA: exponentially weighted moving average (recent scores count more)
  * Flag rule: compares the latest score with the EWMA BEFORE it
  * Recovery: change after an intervention, adjusted for the class change
"""
from statistics import mean, median

INSUFFICIENT = "INSUFFICIENT"
STABLE = "STABLE"
NEEDS_ATTENTION = "NEEDS_ATTENTION"
PERSISTENTLY_LOW = "PERSISTENTLY_LOW"


def ewma(values, alpha=0.3):
    """EWMA_t = alpha * y_t + (1 - alpha) * EWMA_(t-1), starting from the first score."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def theil_sen_slope(values):
    """Median of the slopes between every pair of scores (x = 0, 1, 2, ...)."""
    n = len(values)
    if n < 2:
        return None
    slopes = [(values[j] - values[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
    return median(slopes)


def classify(values, min_assessments=4, alpha=0.3, slope_tolerance=1.0,
             baseline_margin=3.0, low_score_threshold=40.0):
    """Give one student's score history a status and a plain-language reason."""
    n = len(values)
    out = {"status": INSUFFICIENT, "n": n, "slope": None, "ewma_previous": None,
           "latest": values[-1] if values else None, "level": None, "reason": ""}
    if n < min_assessments:
        out["reason"] = (f"Only {n} assessment(s) so far; at least {min_assessments} "
                         "are needed before a trend is shown.")
        return out

    slope = theil_sen_slope(values)
    previous = ewma(values[:-1], alpha)[-1]       # baseline BEFORE the latest score
    level = ewma(values, alpha)[-1]               # current overall level
    latest = values[-1]
    out.update(slope=slope, ewma_previous=previous, level=level)

    if slope <= -slope_tolerance and latest < previous - baseline_margin:
        out["status"] = NEEDS_ATTENTION
        out["reason"] = (f"Scores are falling ({slope:+.1f} points per assessment) and the latest "
                         f"score ({latest:.0f}%) is more than {baseline_margin:g} points below the "
                         f"recent average ({previous:.0f}%).")
    elif abs(slope) < slope_tolerance and level < low_score_threshold:
        out["status"] = PERSISTENTLY_LOW
        out["reason"] = (f"Scores are steady but low: the recent average is {level:.0f}%, "
                         f"below {low_score_threshold:g}%.")
    else:
        out["status"] = STABLE
        out["reason"] = "No concerning trend in the recent scores."
    return out


def classify_with_settings(values, s):
    """Same as classify, reading the thresholds from a settings object (e.g. AnalyticsSetting)."""
    return classify(values, min_assessments=s.min_assessments, alpha=s.ewma_alpha,
                    slope_tolerance=s.slope_tolerance, baseline_margin=s.baseline_margin,
                    low_score_threshold=s.low_score_threshold)


def recovery(values, class_means, start_index, window=2):
    """Change in a student's score after an intervention, adjusted for the class change.

    values       the student's percentages, oldest first
    class_means  the class average percentage for the same assessments
    start_index  position of the first assessment AFTER the intervention started
    window       assessments counted on each side (default 2)

    R     = S_post - S_pre
    R_adj = R - (class_post - class_pre)
    """
    pre = values[max(0, start_index - window):start_index]
    post = values[start_index:start_index + window]
    if len(pre) < window or len(post) < window:
        return {"ready": False,
                "message": f"Needs {window} assessments before and {window} after the intervention."}
    c_pre = class_means[max(0, start_index - window):start_index]
    c_post = class_means[start_index:start_index + window]
    s_pre, s_post = mean(pre), mean(post)
    change = s_post - s_pre
    class_change = mean(c_post) - mean(c_pre)
    adjusted = change - class_change
    if adjusted > 0:
        label = "Score improved after the intervention, more than the class did."
    elif change > 0:
        label = "Score improved, but no more than the class overall."
    else:
        label = "Score did not improve after the intervention."
    return {"ready": True, "pre": s_pre, "post": s_post, "change": change,
            "class_change": class_change, "adjusted": adjusted, "label": label}