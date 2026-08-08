#!/usr/bin/env python3
"""
IRR Demo -- Instructed Regex Routing
Shows: intent generation -> pattern library -> matching engine -> weight update loop
"""
from irr import PatternLibrary, MatchingEngine, WeightUpdater, IntentGenerator

def main():
    library = PatternLibrary()
    engine = MatchingEngine(library, top_n=8)
    updater = WeightUpdater(library)
    generator = IntentGenerator()

    queries = [
        "add two numbers together",
        "multiply the input by a scale factor",
        "loop through all the items and count them",
        "compare these two strings for equality",
        "copy memory from source to destination",
        "hello world output",
        "xor the bits to toggle",
        "set all bytes to zero",
        "unknown random query with no keywords",
    ]

    print("=== IRR: Intent Generation + Routing ===\n")
    for q in queries:
        op, pattern, confidence = generator.generate(q)
        result = engine.match(q)
        # Reward if matched correctly
        if result["matched"] and result["op"] == op:
            new_weight = updater.reward(result["op"], result["pattern"])
        else:
            new_weight = 0.0
        print(f"Query : {q!r}")
        print(f"Intent: op={op} confidence={confidence:.2f} pattern={pattern}")
        print(f"Match : op={result['op']} weight={result['weight']:.3f} matched={result['matched']}")
        print(f"Weight: {new_weight:.3f}")
        print()

if __name__ == "__main__":
    main()
