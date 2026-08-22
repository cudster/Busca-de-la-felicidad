import media


def test_derive_wiki_specific_aircraft():
    assert media.derive_wiki({"topic": "SR-71 Built With Soviet Titanium", "visual_prompt": ""}) == "Lockheed SR-71 Blackbird"
    assert media.derive_wiki({"topic": "Why the 747 Has a Hump", "visual_prompt": ""}) == "Boeing 747 airline"
    assert media.derive_wiki({"topic": "Concorde's Heat Stretch", "visual_prompt": ""}) == "Concorde airliner"
    assert media.derive_wiki({"topic": "C-17 WINFLY Mission", "visual_prompt": ""}) == "Boeing C-17 Globemaster III"


def test_derive_wiki_generic_returns_none():
    assert media.derive_wiki({"topic": "Premium Economy Hidden Perks", "visual_prompt": "cabin"}) is None
    assert media.derive_wiki({"topic": "Contrails clouds", "visual_prompt": "sky"}) is None
    assert media.derive_wiki({"topic": "Ground Effect cushion", "visual_prompt": "landing"}) is None
