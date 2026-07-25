# RAG Strategy Comparison Results

Below is a comparison of two different Retrieval-Augmented Generation configurations using Amazon's 10-K document (amzn.pdf). 

- **Config A (Baseline):** `markdown_structural` chunking + `hybrid_rrf` retrieval.
- **Config B (Enhanced):** `semantic` chunking + `hybrid_rrf` retrieval.

| Question | Config A (Vanilla) Result | Config B (Hybrid) Result | Winner |
|---|---|---|---|
| "How many employees did Amazon have as of December 31, 2025?" | Retrieved a broad section on Human Capital. Answered correctly (1.57 million). | Retrieved a highly targeted chunk on workforce size. Answered correctly. | Tie |
| "What were Amazon's cash capital expenditures in 2024 vs 2025, and what does management expect for 2026?" | Retrieved chunks missing 2026 guidance due to hard structural boundaries. Answered only for 2024/2025. | Retrieved a semantically aligned chunk containing past capex and 2026 expectations. Answered fully. | Config B |
| "What is Amazon's Q1 2026 guidance for net sales and operating income?" | Struggled with header splits, separating net sales from operating income. Missed operating income guidance. | Semantic chunking kept the forward-looking statements together as one cohesive topic. Answered correctly. | Config B |
| "What fine did the CNPD impose on Amazon Europe Core S.à r.l., and what happened with the appeals?" | Found the exact legal chunk in both. Both answered correctly. | Found the exact legal chunk in both. Both answered correctly. | Tie |
| "What was Amazon's effective tax rate in 2025 vs 2024, and what were the two primary drivers of change?" | Chunking split the tax rate figures from the driver explanations. Answer was incomplete. | Semantic grouping kept the tax rates and the 2025 Tax Act driver together. Answered fully. | Config B |
