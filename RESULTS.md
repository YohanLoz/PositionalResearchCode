# Experiment results

## Setup

The first position and context-size run took place on 11 September 2026 from 20:14 to 20:18 Europe/Amsterdam. The timed repeat and conflict experiment ran on 12 September from 16:55 to 16:59. The tests used `openai/gpt-5.6-luna` through OpenRouter with the OpenAI provider route fixed and provider fallback disabled. Every request used temperature 0, seed `20260911` and low reasoning effort.

Luna first generated 150 Itherstan Velari flashcards from the prompt in the paper. The raw response used `% Card N ... %` wrappers instead of putting `Contents` in each header. The runner removed those wrappers and rendered every card in one consistent format before testing. The generated cards contained no explicit ovulation month.

The target card stated that the Itherstan Velari enters its ovulation period during November. The runner created ten seeded distractor arrangements from the generated cards. Within each position comparison, the distractors stayed in the same order and only the target position changed. The 40-card sets used positions 4, 20 and 36. The 80-card sets used positions 8, 40 and 72. The 120-card sets used positions 12, 60 and 108. The first run is preserved in its original result files rather than being overwritten by the timed repeat.

## Position and context size

The timed repeat used the same 90 conditions as the first run. Luna returned November in every condition.

| Cards | Target position | Correct | Median response time | Range |
|---:|---:|---:|---:|---:|
| 40 | 4 | 10/10 | 1.057 s | 0.848 to 1.401 s |
| 40 | 20 | 10/10 | 1.127 s | 0.862 to 1.528 s |
| 40 | 36 | 10/10 | 0.984 s | 0.844 to 1.468 s |
| 80 | 8 | 10/10 | 1.176 s | 1.033 to 2.195 s |
| 80 | 40 | 10/10 | 1.264 s | 0.800 to 2.048 s |
| 80 | 72 | 10/10 | 1.267 s | 1.050 to 2.067 s |
| 120 | 12 | 10/10 | 1.297 s | 1.088 to 1.864 s |
| 120 | 60 | 10/10 | 1.335 s | 1.083 to 1.854 s |
| 120 | 108 | 10/10 | 1.314 s | 1.042 to 2.870 s |

The median response time across all positions was 1.057 seconds with 40 cards, 1.237 seconds with 80 cards and 1.335 seconds with 120 cards. These measurements include network, OpenRouter and provider delays. The three context sizes were run one after another rather than interleaved, so the differences are descriptive and cannot be attributed entirely to context size.

## Conflicting information

The conflict experiment used 30 matched pairs. Both versions contained a November answer card and a March companion card. The neutral companion stated that ovulation does not occur in March. The conflict companion stated that it does occur in March. The target card appeared at positions 4, 20 and 36. The companion appeared at position 2 in five arrangements and position 39 in five arrangements.

| Version | Target position | Accepted only | Alternative only | Both or conflict | Neither |
|---|---:|---:|---:|---:|---:|
| Neutral | 4 | 10 | 0 | 0 | 0 |
| Neutral | 20 | 10 | 0 | 0 | 0 |
| Neutral | 36 | 9 | 0 | 1 | 0 |
| Conflict | 4 | 0 | 0 | 10 | 0 |
| Conflict | 20 | 0 | 0 | 10 | 0 |
| Conflict | 36 | 0 | 0 | 10 | 0 |

Neutral-answer accuracy was 29/30. It was 10/10 at positions 4 and 20 and 9/10 at position 36. In the incorrect neutral response, Luna returned `November and March; the cards conflict.` The source cards were compatible: one said ovulation occurs in November and the other said it does not occur in March. Luna identified both months as conflicting even though the neutral card rejected March.

All 30 conflict responses named both months or explicitly reported the conflict. The prompt told the model how to respond when cards disagreed. This result therefore measures whether Luna followed that instruction under these conditions, not whether it would identify a conflict without being asked.

## API use

| Run | Calls | Prompt tokens | Completion tokens | Cost |
|---|---:|---:|---:|---:|
| Original position and context-size run | 90 | 242,040 | 450 | $0.061036500 |
| Timed repeat and conflict experiment | 150 | 324,630 | 1,169 | $0.082537800 |
| Total | 240 | 566,670 | 1,619 | $0.143574300 |

No API request failed. The separate cost of generating the 150 flashcards was not captured.

## Limits

The experiment asks one ovulation-month question across ten distractor arrangements. The arrangements are repeated observations of one question, not independent research questions. The results support conclusions about this model, prompt, dataset and execution period only. One neutral error at the late position is worth reporting, but it is not enough on its own to establish a general position effect.
