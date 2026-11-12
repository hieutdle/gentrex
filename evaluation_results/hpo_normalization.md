# HPO matching on GSC+

Written by `evaluation/hpo_normalization.py` on 2026-10-21, on macOS-27.0.1-arm64-arm-64bit, mps. The test set has 939 distinct mentions, 626 of them worded differently from every HPO name. Each p-value is an exact McNemar test against `cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity)`, the setup that settings.yaml names.

| Setup | Top 1 | Top 1, different wording | Top 5 | Top 5, different wording | Top 10 | p, top 1 | p, top 5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity) | 67.1 | 53.8 | 86.0 | 80.2 | 90.6 | 1 | 1 |
| cambridgeltl/SapBERT-from-PubMedBERT-fulltext | 64.5 | 50.0 | 83.8 | 77.0 | 87.8 | 0.0037 | 0.0011 |
| google/embeddinggemma-2 (prompt SentenceSimilarity) | 63.5 | 48.4 | 81.9 | 74.6 | 88.1 | 0.00018 | 1.3e-05 |
| google/embeddinggemma-2 | 62.6 | 47.1 | 79.7 | 71.1 | 85.3 | 4.7e-05 | 1.1e-09 |
| cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity) + BM25 | 57.5 | 39.5 | 75.9 | 66.0 | 80.4 | 1e-15 | 2.1e-19 |

## When the two models agree

The models of `cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity)` rank the same term first for 73.2% of the mentions. Then the match is right for 78.5%. When they disagree, it is right for 36.1%. At least one model ranks the experts' term first for 70.6%, and the two models' first 5 terms hold it for 88.6%, in 7.2 terms on average.

## Speed on the CPU

| Setup | Index build (minutes) | Per clinical feature (ms) |
| --- | --- | --- |
| cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity) | 5.5 | 38.0 |
| cambridgeltl/SapBERT-from-PubMedBERT-fulltext | 1.1 | 12.2 |
| google/embeddinggemma-2 (prompt SentenceSimilarity) | 3.6 | 22.6 |
| google/embeddinggemma-2 | 2.5 | 21.3 |

## Top matches where cambridgeltl/SapBERT-from-PubMedBERT-fulltext alone and cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity) differ

| Mention | Experts' term | cambridgeltl/SapBERT-from-PubMedBERT-fulltext alone | cambridgeltl/SapBERT-from-PubMedBERT-fulltext + google/embeddinggemma-2 (prompt SentenceSimilarity) |
| --- | --- | --- | --- |
| abnormal overlying skin | HP:0000951 Abnormality of the skin | Abnormal skin morphology | Abnormality of the skin |
| aplastic or hypoplastic nails | HP:0001798 Anonychia | Anonychia | Small nail |
| ataxic | HP:0001251 Ataxia | Ataxia | Gait ataxia |
| auricular, ophthalmologic, and oral anomalies | HP:0000377 Abnormal pinna morphology | Abnormal pinna morphology | Abnormality of the ear |
| auricular, oral, and ophthalmic anomalies | HP:0000598 Abnormality of the ear | Abnormality of ophthalmic artery | Abnormality of the ear |
| BDA1 | HP:0009371 Type A1 brachydactyly | Type A1 brachydactyly | Decreased level of thrombomodulin |
| BDA2 | HP:0009372 Type A2 brachydactyly | Type A2 brachydactyly | Decreased level of thrombomodulin |
| Behavioral characteristics | HP:0000708 Atypical behavior | Diagnostic behavioral phenotype | Atypical behavior |
| branchial | HP:0009794 Branchial anomaly | Branchial sinus | Branchial anomaly |
| branchial and external ear malformations | HP:0009794 Branchial anomaly | Branchial anomaly | Abnormality of the outer ear |
| branchial arches | HP:0009794 Branchial anomaly | Common origin of the right brachiocephalic artery and left common carotid artery | Branchial anomaly |
| branchial fistulae and/or cysts | HP:0009796 Branchial cyst | Branchial fistula | Branchial cyst |
| branchial fistulas or cysts | HP:0009796 Branchial cyst | Branchial fistula | Branchial cyst |
| cerebellar syndrome | HP:0001317 Abnormal cerebellum morphology | Cerebellar dysplasia | Abnormal cerebellum morphology |
| congenital hemiparesis | HP:0001269 Hemiparesis | Spastic hemiparesis | Hemiparesis |
| congenital lung cyst | HP:0010959 Congenital pulmonary airway malformation | Pulmonary cyst | Congenital pulmonary airway malformation |
