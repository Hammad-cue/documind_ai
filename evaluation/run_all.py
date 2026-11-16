"""
Run the remaining long jobs one after another, logging each to evaluation/logs/<step>.log.
Steps whose result already exists are skipped, so this can simply be started again after an interruption.

    python -m evaluation.run_all train        # fine-tune the clause classifier (CPU, ~70 min)
    python -m evaluation.run_all llm          # router, zero-shot baseline, answer quality (rate-limited API calls)
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / 'evaluation' / 'logs'
PY = sys.executable

STEPS = {
    'train': [
        ('clause_model', ROOT / 'ml' / 'models' / 'clause-classifier' / 'config.json',
         [PY, '-u', 'ml/train_clause_classifier.py', '--train-limit', '10000', '--eval-limit', '1000', '--test-limit', '0',
          '--epochs', '3', '--batch-size', '32', '--max-length', '128', '--lr', '1e-4'], {}),
    ],
    'llm': [
        ('router', ROOT / 'evaluation' / 'results' / 'router.json', [PY, '-u', '-m', 'evaluation.eval_router'], {}),
        ('zero_shot', None, [PY, '-u', 'ml/baselines.py', 'llm', '--eval-limit', '200', '--pause', '12'],
         {'LLM_MODEL': 'openai/gpt-oss-120b'}),
        ('answers', ROOT / 'evaluation' / 'results' / 'answers_cuad.json', [PY, '-u', '-m', 'evaluation.eval_answers', '--n', '10', '--pause', '30'], {}),
    ],
}


def done(step, marker):
    if marker is not None:
        return marker.exists()
    if step == 'zero_shot':
        return any((ROOT / 'ml' / 'runs').glob('baseline-llm-zero-shot-*.json'))
    return False


def main(group):
    import os
    LOGS.mkdir(parents=True, exist_ok=True)
    for step, marker, cmd, extra_env in STEPS[group]:
        if done(step, marker):
            print(f'{step}: already done, skipping', flush=True)
            continue
        log = LOGS / f'{step}.log'
        print(f'{step}: running -> {log.relative_to(ROOT)}', flush=True)
        started = time.time()
        with open(log, 'w', encoding='utf-8') as fh:
            code = subprocess.call(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, **extra_env})
        print(f'{step}: exit {code} after {(time.time() - started) / 60:.1f} min', flush=True)
    (LOGS / f'{group}.finished').write_text(time.strftime('%Y-%m-%d %H:%M'), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'llm')
