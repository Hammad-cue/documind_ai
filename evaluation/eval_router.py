"""
Evaluation 3 — query routing.

100 hand-labelled questions (evaluation/data/router_questions.json) phrased the way staff ask them, including
follow-ups that depend on the previous question. Compares the LLM router with the keyword fallback router.

    python -m evaluation.eval_router
"""
import json
import time
from collections import Counter

from evaluation.common import DATA, save

from assistant import router  # noqa: E402
from django.conf import settings  # noqa: E402

INTENTS = ['LOOKUP', 'KNOWLEDGE', 'SEARCH']


def score(name, predict, items, pause=0.0):
    correct = field_ok = field_n = 0
    confusion = {g: Counter() for g in INTENTS}
    misses, seconds = [], []
    fallbacks = 0
    for it in items:
        time.sleep(pause)   # rate-limit pacing, kept outside the timing
        started = time.perf_counter()
        plan = predict(it)
        seconds.append(time.perf_counter() - started)
        got = plan['intent']
        fallbacks += plan.get('method', 'llm') != 'llm' and name == 'llm'
        confusion[it['intent']][got] += 1
        if got == it['intent']:
            correct += 1
        else:
            misses.append({'q': it['q'], 'gold': it['intent'], 'got': got})
        if it['intent'] == 'LOOKUP' and it.get('field'):
            field_n += 1
            field_ok += plan.get('field') == it['field']
    per_intent = {}
    for g in INTENTS:
        tp = confusion[g][g]
        fp = sum(confusion[o][g] for o in INTENTS if o != g)
        fn = sum(v for k, v in confusion[g].items() if k != g)
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        per_intent[g] = {'precision': round(p, 3), 'recall': round(r, 3), 'f1': round(2 * p * r / (p + r), 3) if p + r else 0}
    result = {'accuracy': round(correct / len(items), 3), 'field_accuracy_on_lookups': round(field_ok / field_n, 3) if field_n else None,
              'per_intent': per_intent, 'confusion': {g: dict(confusion[g]) for g in INTENTS},
              'avg_ms': round(1000 * sum(seconds) / len(seconds)), 'misses': misses,
              'llm_fallbacks': fallbacks}
    print(f'{name:9s} accuracy {result["accuracy"]:.3f} · field accuracy {result["field_accuracy_on_lookups"]} · {result["avg_ms"]} ms/question · fallbacks {fallbacks}')
    return result


def main():
    items = json.loads((DATA / 'router_questions.json').read_text(encoding='utf-8'))
    print(f'{len(items)} questions: {dict(Counter(i["intent"] for i in items))}')
    heuristic = score('heuristic', lambda it: router.heuristic_plan(it['q']), items)
    llm_router = score('llm', lambda it: router.plan_query(it['q'], it.get('history')), items, pause=12)  # Groq free tier: ~8k tokens/min incl. max_tokens
    save('router', {'questions': len(items), 'model': settings.LLM_MODEL, 'llm': llm_router, 'heuristic': heuristic})


if __name__ == '__main__':
    main()
