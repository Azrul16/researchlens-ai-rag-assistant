# Third-party dependencies

The root MIT license covers original ResearchLens AI source code. It does not replace the licenses of separately installed dependencies or model weights. The repository includes dependency specifications; application containers install third-party packages, whose own notices and license terms still apply.

| Dependency | License / reference |
|---|---|
| PyMuPDF / MuPDF | GNU AGPL v3 or a separate Artifex commercial license; [official licensing information](https://pymupdf.io/licensing) |
| Sentence Transformers | Apache-2.0; [upstream repository](https://github.com/huggingface/sentence-transformers) |
| FAISS | MIT; [upstream repository](https://github.com/facebookresearch/faiss) |
| Next.js and React | MIT; [Next.js](https://github.com/vercel/next.js), [React](https://github.com/facebook/react) |
| Tailwind CSS | MIT; [upstream repository](https://github.com/tailwindlabs/tailwindcss) |
| Lucide icons | ISC; [upstream repository](https://github.com/lucide-icons/lucide) |

PyMuPDF's AGPL/commercial licensing is material when distributing or hosting an assembled application. An MIT label on this repository does not make the complete dependency stack MIT-licensed. Review the upstream terms for your intended distribution or deployment; a commercial license is an available alternative for use cases that do not meet AGPL terms.

Embedding models and optional rerankers are downloaded separately from Hugging Face. Review the chosen checkpoint's model card and license when substituting a model. Generated screenshot fixtures and their PDFs are fictional and created by this project; copyrighted research papers are not included.
