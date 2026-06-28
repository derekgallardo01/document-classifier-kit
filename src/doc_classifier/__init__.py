"""Document classifier - schema-driven + confidence-routed.

Default backend is keyword/rule-based so the kit runs anywhere without
keys. Set DOC_CLASSIFIER_BACKEND=llm (with ANTHROPIC_API_KEY) to route
through Claude.
"""
__version__ = "1.0.0"
