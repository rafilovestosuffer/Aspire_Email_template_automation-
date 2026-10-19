"""Supported target languages for the Generate Console.
Tiered to match the roadmap; extend freely. rtl=True drives RTL rendering."""

LANGUAGES = [
    # Tier 1 (launch)
    {"code": "es", "name": "Spanish", "rtl": False, "tier": 1},
    {"code": "fr", "name": "French", "rtl": False, "tier": 1},
    {"code": "de", "name": "German", "rtl": False, "tier": 1},
    {"code": "pt", "name": "Portuguese", "rtl": False, "tier": 1},
    {"code": "ar", "name": "Arabic", "rtl": True, "tier": 1},
    {"code": "hi", "name": "Hindi", "rtl": False, "tier": 1},
    {"code": "bn", "name": "Bangla", "rtl": False, "tier": 1},
    {"code": "zh", "name": "Chinese (Simplified)", "rtl": False, "tier": 1},
    {"code": "ja", "name": "Japanese", "rtl": False, "tier": 1},
    # Tier 2
    {"code": "it", "name": "Italian", "rtl": False, "tier": 2},
    {"code": "nl", "name": "Dutch", "rtl": False, "tier": 2},
    {"code": "pl", "name": "Polish", "rtl": False, "tier": 2},
    {"code": "tr", "name": "Turkish", "rtl": False, "tier": 2},
    {"code": "ko", "name": "Korean", "rtl": False, "tier": 2},
    {"code": "id", "name": "Indonesian", "rtl": False, "tier": 2},
    {"code": "vi", "name": "Vietnamese", "rtl": False, "tier": 2},
    {"code": "th", "name": "Thai", "rtl": False, "tier": 2},
    {"code": "ru", "name": "Russian", "rtl": False, "tier": 2},
    # Tier 3 (long tail - sample)
    {"code": "ur", "name": "Urdu", "rtl": True, "tier": 3},
    {"code": "fa", "name": "Persian", "rtl": True, "tier": 3},
    {"code": "he", "name": "Hebrew", "rtl": True, "tier": 3},
    {"code": "ms", "name": "Malay", "rtl": False, "tier": 3},
    {"code": "tl", "name": "Filipino", "rtl": False, "tier": 3},
    {"code": "sw", "name": "Swahili", "rtl": False, "tier": 3},
    {"code": "uk", "name": "Ukrainian", "rtl": False, "tier": 3},
    {"code": "ro", "name": "Romanian", "rtl": False, "tier": 3},
    {"code": "el", "name": "Greek", "rtl": False, "tier": 3},
    {"code": "sv", "name": "Swedish", "rtl": False, "tier": 3},
    {"code": "cs", "name": "Czech", "rtl": False, "tier": 3},
    {"code": "ta", "name": "Tamil", "rtl": False, "tier": 3},
]

BY_CODE = {l["code"]: l for l in LANGUAGES}
