# Optional small local model

This experimental integration specialises an installed Ollama text model through a
versioned prompt and constrained JSON schema. It does not fine-tune model weights.
The OCR-only application continues to work without any model installed.

Install Ollama and obtain your selected model while internet is available, then
disconnect. The application never downloads a model. In administration, log in,
enter its installed model name (for example qwen3:0.6b), enable suggestions and save.
In a completed inspection, select a COC/test evidence page and press Suggest values.
Select a proposal in the material candidate picker, check the source, and supply
condition and heat manually. Every proposal remains unverified until the inspector
checks it. Existing observations are preserved when requesting suggestions.

Only http://127.0.0.1:11434/api/chat is contacted; proxies and redirects are disabled.
Use locally installed model weights; the application cannot attest to the separate
Ollama service's network behaviour. Configuration changes require admin access and
are recorded in data/local-model-config-history.jsonl.

The first version processes at most 12 matching OCR rows from the selected page,
with a 20-second timeout per call, a 128 KiB response limit, and bounded generation.
It deliberately excludes known limits rows, duplicate pages, inferred units,
inferred heat/condition, and unsupported values. It requires literal numeric/unit
evidence; that evidence alone does not prove a correct property association.
Complex multirow tables and direct image interpretation are not supported yet.

Each attempt saves prompt version, model name, full request, raw parsed response,
rejections and errors in a case-local JSON file. These files survive restart and
are included in evidence exports. Model name is not a cryptographic weights ID;
pin and record the installed model digest separately for reproducibility.

Saving a review also writes correction-examples.jsonl in the case. These records
contain observations, OCR proposals and references to model attempts. They are
pending dataset review, not automatically valid training examples. Admins must
curate and de-identify examples and split by delivery/supplier into training and
held-out evaluation sets before any adapter training. No training, automatic
learning, dataset approval or model deployment pipeline is implemented here.

Benchmark extraction precision/recall, decimal errors, wrong property/heat links,
inspector correction time and memory/latency on target desktops before selecting
a model. A small model's accuracy has not been validated on your deliveries.
