from app.detection.stylometric_signal import stylometric_signal

samples = {
    "Long Human": """
I finally got around to cleaning the garage this weekend. It took much longer than I expected because I kept finding old boxes from when we moved five years ago. Some things were worth keeping, but most ended up getting donated. It felt good to finally have everything organized again, even if I was exhausted afterward.

On Sunday I rewarded myself by grabbing lunch with a friend downtown. We spent a couple of hours talking about work, travel, and plans for the rest of the summer. Nothing especially exciting happened, but it was one of those weekends that left me feeling productive and relaxed at the same time.
""",

    "Long AI": """
Artificial intelligence represents one of the most significant technological advancements of the modern era. Organizations across healthcare, finance, education, and manufacturing continue to adopt intelligent systems to improve efficiency and support decision-making. However, responsible deployment requires careful consideration of ethics, transparency, privacy, and long-term societal impact. Stakeholders should collaborate to establish governance frameworks that maximize benefits while minimizing potential risks.
""",

    "Equal Length Sentences": """
The cat slept quietly. The dog barked loudly. The bird flew away.
""",

    "Variable Length Sentences": """
Hi. Yesterday I spent nearly the entire afternoon wandering through the old downtown district looking for a bookstore that someone had recommended months ago.
""",

    "Repetitive Vocabulary": """
AI AI AI AI AI AI AI AI AI AI AI AI AI AI AI
""",

    "Diverse Vocabulary": """
The orchestra performed magnificently beneath shimmering chandeliers while visitors quietly admired intricate architecture surrounding the historic concert hall.
""",

    "Very Long Sentence": """
This sentence intentionally contains many additional descriptive words because its only purpose is to verify that the average sentence length metric increases correctly when substantially more words are included within a single sentence than would normally be expected.
"""
}

for name, text in samples.items():
    result = stylometric_signal(text)

    print("=" * 60)
    print(name)
    print("Score:", result["score"])

    for key, value in result["metrics"].items():
        print(f"{key}: {value}")