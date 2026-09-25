---
language:
  - ja
  - en
library_name: transformers
pipeline_tag: text-classification
base_model: google-bert/bert-base-multilingual-cased
base_model_relation: finetune
license: apache-2.0
metrics:
  - f1
tags:
  - sentiment-analysis
  - hospitality
  - multilingual
  - synthetic-data
---

# Hospitality Review Sentiment mBERT

This is a three-class Japanese/English sentiment classifier for short
hospitality reviews, fine-tuned from
`google-bert/bert-base-multilingual-cased`. It categorizes each review as
negative, neutral, or positive.

## Intended use

The model predicts one overall label for a short Japanese or English hospitality
review:

| ID | Label |
|---:|---|
| 0 | `negative` |
| 1 | `neutral` |
| 2 | `positive` |

It is intended for research, prototyping, and human-reviewed analytics. It must
not be used as the sole basis for consequential business, employment,
moderation, or customer-service decisions. Applications using this model should
allow operators to review and correct its predictions.

## Training data

The model was fine-tuned on 480 synthetic bilingual reviews: 240 Japanese and
240 English, balanced across the three labels. No real customer reviews were
collected or used.

The data was produced by a deterministic, template-based generator. Training
and test splits use disjoint sentence templates, but they share the same small
set of polarity-bearing fragments. This shared vocabulary can substantially
inflate performance compared with genuinely novel reviews.

## Evaluation

The exact weights in this directory were re-evaluated on the 240-item synthetic
test split (120 Japanese and 120 English; 80 items per class):

| Metric | Result |
|---|---:|
| Macro-F1 | 1.000 |
| Japanese macro-F1 | 1.000 |
| English macro-F1 | 1.000 |
| Negative F1 | 1.000 |
| Neutral F1 | 1.000 |
| Positive F1 | 1.000 |

The published weights achieved macro-F1 1.000 on a 240-item synthetic test
split. Training and test templates were disjoint, but polarity-bearing fragment
vocabulary was shared. The result therefore measures performance within the
generator's narrow distribution and must not be interpreted as real-world
deployment accuracy.

The zero-shot comparison baseline achieved macro-F1 0.664 on the same split.

## Known limitations

- The model has not been evaluated on an independently annotated set of genuine
  restaurant reviews.
- Synthetic training and test text has narrow vocabulary and simple sentence
  structure.
- Japanese/English code-switching and aspect-level sentiment were not evaluated.
- A single overall label can conceal mixed opinions such as positive food but
  negative service.
- Softmax confidence is not a calibrated probability of correctness on real
  reviews.
- The unseen short review `ramen was good` is incorrectly classified as
  `negative` with approximately 0.966 confidence by these weights. In the
  synthetic training vocabulary, `good` occurs inside the neutral phrase
  `neither good nor bad`, illustrating generator-specific lexical learning.

## Example

```python
from transformers import pipeline

classifier = pipeline(
    "text-classification",
    model="AtsushiHatake/ai-agent-sme-sentiment-mbert",
)

print(classifier("料理がおいしく、スタッフも親切でした。"))  # Japanese
print(classifier("The food was delicious, and the staff were very friendly."))  # English

# Response examples:
# [{'label': 'positive', 'score': 0.9935460686683655}]
# [{'label': 'positive', 'score': 0.993598461151123}]
```

The `score` may differ slightly depending on the hardware and software
environment.

## Reproducibility

The data generator, training and evaluation scripts, synthetic data, and
recorded results are available in the source repository:

<https://github.com/atsushi729/ai-agent-sme>

Consumers should pin a Hugging Face commit revision rather than loading an
unversioned `main` branch.

## Licence and attribution

The base BERT model and the fine-tuned distribution are provided under the
Apache License 2.0. See `LICENSE` and `NOTICE`. This is a modified model:
multilingual BERT was fine-tuned for three-class hospitality-review sentiment on
the synthetic dataset described above. The release is not an official Google
product.
