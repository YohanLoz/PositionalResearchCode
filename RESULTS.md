# Position and context-size test results

The test ran on 11 September 2026 from 20:14 to 20:18 Europe/Amsterdam. It used `openai/gpt-5.6-luna` through OpenRouter's `openai` provider route, with provider fallback disabled. All requests used temperature 0, seed `20260911` and low reasoning effort.

Luna first generated 150 Itherstan Velari flashcards from the prompt in the paper. The raw response used `% Card N ... %` wrappers instead of putting `Contents` in each header. The runner removed those wrappers and rendered every card in one consistent format before testing. The generated cards contained no explicit ovulation month.

The target card stated that the Itherstan Velari enters its ovulation period during November. Ten seeded distractor arrangements were made from the generated cards. Within each matched comparison, the distractors stayed in the same order and only the target position changed. The 40-card sets used positions 4, 20 and 36. The 80-card sets used positions 8, 40 and 72. The 120-card sets used positions 12, 60 and 108.

| Context size | Beginning | Middle | End | Total |
| --- | ---: | ---: | ---: | ---: |
| 40 cards | 10/10 | 10/10 | 10/10 | 30/30 |
| 80 cards | 10/10 | 10/10 | 10/10 | 30/30 |
| 120 cards | 10/10 | 10/10 | 10/10 | 30/30 |
| Total | 30/30 | 30/30 | 30/30 | 90/90 |

All 90 requests returned `November` and ended normally. The provider reported 242,040 prompt tokens, 450 completion tokens and a total test-response cost of USD 0.061036500. This total does not include the separate flashcard-generation request.

No position or context-size accuracy difference was observed under these conditions. The result covers one target question tested across ten distractor arrangements. Those arrangements are matched test cases, not ten independent research questions. The conflict condition has not been tested.

The raw cards, submitted prompts and responses are stored in the ignored `output/` directory. They must be included with the final research materials before submission.
