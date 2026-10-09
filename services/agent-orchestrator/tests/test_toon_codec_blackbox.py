"""
Black-Box Validation Suite for AEGIS TOON Codec (Token-Oriented Object Notation)
Validates serialization, deserialization, fault tolerance, and schema extraction.
"""
import pytest
from utils.toon_codec import encode, decode, extract_toon


class TestToonCodecBlackBox:
    def test_primitives_roundtrip(self):
        """Test encoding and decoding of primitive types."""
        data = {
            "str_field": "hello world",
            "int_field": 42,
            "float_field": 3.14,
            "bool_true": True,
            "bool_false": False,
            "null_field": None,
        }
        encoded = encode(data)
        decoded = decode(encoded)

        assert decoded["str_field"] == "hello world"
        assert decoded["int_field"] == 42
        assert abs(decoded["float_field"] - 3.14) < 1e-5
        assert decoded["bool_true"] is True
        assert decoded["bool_false"] is False
        assert decoded["null_field"] is None

    def test_nested_objects_and_lists(self):
        """Test deeply nested objects and arrays representing agent payloads."""
        payload = {
            "company_name": "Acme Corp",
            "scores": {
                "confidence": 0.85,
                "vitality": 90,
            },
            "tags": ["cloud", "saas", "b2b"],
            "competitors": [
                {"name": "Comp A", "threat": "high"},
                {"name": "Comp B", "threat": "medium"},
            ]
        }
        encoded = encode(payload)
        decoded = decode(encoded)

        assert decoded["company_name"] == "Acme Corp"
        assert decoded["scores"]["confidence"] == 0.85
        assert decoded["scores"]["vitality"] == 90
        assert decoded["tags"] == ["cloud", "saas", "b2b"]
        assert len(decoded["competitors"]) == 2
        assert decoded["competitors"][0]["name"] == "Comp A"

    def test_extract_toon_from_llm_markdown_wrappers(self):
        """Test extract_toon when LLM wraps output in markdown code blocks or adds chatter."""
        raw_llm_output = """Here is the structured intelligence:

```toon
company_name: "Stripe"
business_model: "B2B SaaS"
tech_stack:
  frontend[1]: "React"
  payments[1]: "Stripe"
confidence: 0.95
```

Hope this helps!"""

        extracted = extract_toon(raw_llm_output)
        assert isinstance(extracted, dict)
        assert extracted.get("company_name") == "Stripe"
        assert extracted.get("business_model") == "B2B SaaS"
        assert extracted.get("confidence") == 0.95

    def test_extract_toon_with_irregular_whitespace_and_comments(self):
        """Test extracting TOON with irregular indentations or leading newlines."""
        raw = """
        company_name: Acme Inc
        confidence: 0.70
        is_active: true
        """
        extracted = extract_toon(raw)
        assert isinstance(extracted, dict)
        assert extracted.get("company_name") == "Acme Inc"
        assert extracted.get("confidence") == 0.70
        assert extracted.get("is_active") is True

    def test_malformed_toon_resilience(self):
        """Test that extract_toon does not crash on completely malformed or non-TOON text."""
        garbage_inputs = [
            "Random conversational text with no keys or values at all.",
            "{{{invalid json or toon [[[[",
            "",
            "   \n\n\t  ",
            "company_name without colon or value\nconfidence 0.5",
        ]
        for g in garbage_inputs:
            res = extract_toon(g)
            assert isinstance(res, dict)
            # Should safely return dict (possibly empty or partial), without unhandled exceptions
