# Optional small local model

This experimental integration specialises an installed Ollama text model through a
versioned prompt and constrained JSON schema. It does not fine-tune model weights.
The OCR-only application continues to work without any model installed.

Install Ollama and obtain your selected model while internet is available, then
disconnect. The application never downloads a model. In administration, log in,
enter its installed model name (for example qwen3:0.6b), enable suggestions and save.
Use Check installed model to confirm the configured name is available. The app records the installed model digest and rejects known cloud-backed entries. In a completed inspection, select a COC/test evidence page and press Suggest values.
Select a proposal in the material candidate picker, check the source, and supply
condition and heat manually. Every proposal remains unverified until the inspector
checks it. Existing observations are preserved when requesting suggestions.

Only http://127.0.0.1:11434/api/chat is contacted; proxies and redirects are disabled.
Use locally installed model weights; the application cannot attest to the separate
Ollama service's network behaviour. Configuration changes require admin access and
are recorded in data/local-model-config-history.jsonl.

The first version processes at most 12 matching OCR rows from the selected page,
with a 20-second timeout per call, a 60-second scheduling budget (an in-flight call may finish afterward), a 128 KiB response limit, and bounded generation. Only rows with a single numeric token and an adjacent reported unit are accepted; ambiguous multi-value rows remain manual. Incomplete generation and unexpected response schemas are rejected.
It deliberately excludes known limits rows, duplicate pages, inferred units,
inferred heat/condition, and unsupported values. It requires literal numeric/unit
evidence; that evidence alone does not prove a correct property association.
Complex multirow tables and direct image interpretation are not supported yet.

Each attempt saves prompt version, model name, full request, raw parsed response,
rejections and errors in a case-local JSON file. These files survive restart and
are included in evidence exports. The installed model digest is captured from the local model inventory before each attempt. This records the service-reported model identity; it does not attest to the separate service or eliminate a model replacement race during generation.

Saving a review also writes correction-examples.jsonl in the case. These records
contain observations, OCR proposals and references to model attempts. They are
pending dataset review, not automatically valid training examples. Admins must
curate and de-identify examples and split by delivery/supplier into training and
held-out evaluation sets before any adapter training. No training, automatic
learning, dataset approval or model deployment pipeline is implemented here.

Benchmark extraction precision/recall, decimal errors, wrong property/heat links,
inspector correction time and memory/latency on target desktops before selecting
a model. A small model's accuracy has not been validated on your deliveries.

Repeated proposals are deduplicated in the picker and on case recovery. Damaged model audit files produce a visible warning while preserving access to the underlying inspection. Existing observations, including removed rows and unsaved edits, are retained during model requests.
