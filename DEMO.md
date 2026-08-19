# Proofline Analytics — Evidence-backed Demo

This written demo is the required product walkthrough for the `moneki`
workspace. Final screenshots and API evidence are added only after the relevant
flows pass automated acceptance tests.

## Acceptance scenarios

| Scenario | Business question | Capability demonstrated | Evidence required |
| --- | --- | --- | --- |
| 1 | 哪个品类的门店营业额最高？ | Store dimension join and ranking | Tool arguments, grouped database result, final answer |
| 2 | 牛肉 poke 六月卖了多少钱？ | Product dimension join and date filtering | Tool arguments, amount and order count, API comparison |
| 3 | 客单价最近是涨了还是跌了？ | Time-series comparison and interpretation | Monthly values, direction calculation, chart state |
| 4 | 那五月呢？ | Conversational follow-up | Previous context and resolved date range |
| 5 | 去年北京门店利润是多少？ | Unsupported question handling | Explicit data-boundary response with no invented number |

## Required proof for every successful answer

1. Exact user question and complete AI response
2. Validated tool name and structured arguments
3. Applied workspace, date, dimensions, and metric definition
4. Deterministic database result returned to the model
5. Comparison with the equivalent analytics API result
6. Automated test preventing regression

## Demo status

Implementation has not reached the demo milestone. Placeholder answers are
intentionally omitted so this document cannot imply unverified behavior.
