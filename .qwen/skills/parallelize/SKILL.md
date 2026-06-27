---
name: parallelize
description: Squeeze concurrency from compute-heavy loops — batch processing, image ops, model inference, facet scanning, ML pipelines. Use when implementing or optimizing a loop that takes >30s and has parts that don't depend on each other (cheap I/O/decode around a slow bottleneck). Covers the serial-bottleneck-with-parallel-I/O pattern, multiprocessing for CPU-bound work, worker-count tuning, and when NOT to parallelize. Complements parallel-by-default-rule (task-level fan-out); this is within-task concurrency.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# parallelize — within-task concurrency

When implementing a compute-heavy loop, **default to parallelizing unless a hard
constraint prevents it.** This complements `parallel-by-default-rule` (task-level fan-out)
by focusing on concurrency inside one task.

## The reflex

Before coding a sequential loop, ask:
- **Is any part non-blocking?** (I/O, decode, network) → parallelize it.
- **Is there a true bottleneck?** (model inference, crypto, lock-protected code) →
  serialize that, parallelize everything around it.
- **Are libraries thread-safe?** → if no, use locks or multiprocessing to isolate.

## Serial bottleneck with parallel I/O (the most common win)

A slow compute step (model forward, DB query) that doesn't depend on cheap steps (decode,
fetch, file read):

```python
# Before: sequential
for path in paths:
    img = decode(path)      # cheap, ~1-5ms
    result = model(img)     # slow, ~100ms

# After: decode in parallel, forward stays serial
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in [pool.submit(decode, p) for p in paths]:
        model(future.result())   # serial forward, decode latency hidden
```

A `Queue(maxsize=4)` of decoded frames feeding a serial consumer is better when task times
are uneven.

## Multiprocessing for CPU-bound parallelization

When the bottleneck itself parallelizes (multiple models on cores), use multiprocessing for
true parallelism (not GIL-limited threads):

```python
from multiprocessing import Pool
with Pool(processes=4) as pool:
    results = pool.map(expensive_compute, items)
```

Caveat: ~100ms setup per process; only worth it if each task is ≥500ms. For short tasks,
threads + serialized bottleneck wins.

## When NOT to parallelize

- Genuine sequential dependency (step N needs N-1's output).
- Not actually the bottleneck — measure first (`cProfile`, `timeit`); don't optimize 1% of runtime.
- Setup cost exceeds gain (8 processes for 3 items).
- Shared mutable state without sync — use locks, queues, or immutable data.
- One-off/experimental code where debugging simplicity beats speed.

## How to apply

1. Identify the bottleneck (profile if unsure).
2. Parallelize the non-bottleneck parts (cheap I/O, cheap compute).
3. Serialize or lock the bottleneck (model forward, DB writes, file updates).
4. Match workers to cores and task time — 4–8 for I/O-bound, `cpu_count()` for CPU-bound;
   more workers ≠ faster.
5. Measure: target >2× speedup before calling it done.

**Rule of thumb:** a loop >30s with independent parts is almost always worth parallelizing.
Measure first, but default to doing it.
