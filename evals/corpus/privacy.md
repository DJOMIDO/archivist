# Privacy and Diagnostics

This document describes privacy in the fictional Cedar Notes app.

Document parsing, embedding, and answer generation run locally.
Diagnostic tracing is disabled by default.

When tracing is enabled, prompts and generated answers are sent to an
external diagnostic service. Retrieved document passages included in
prompts are sent as part of those prompts.

API keys are read from environment variables.
